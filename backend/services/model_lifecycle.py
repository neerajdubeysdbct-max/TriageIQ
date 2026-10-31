"""
Model lifecycle for the automation classifier: retrain from analyst labels,
gate the candidate against the active model on a frozen test set, track every
run in MLflow, version every model file, and roll back on demand.

Data
  base     labelled dataset (config.BASE_TRAINING_*)
  analyst  tickets labelled in the Review Queue (human_override)

Frozen gold test set (never trained on)
  - the base dataset's 20% held-out split (same split as train_automation_model.py)
  - 20% of random-sample analyst labels, chosen by a hash of the ticket id so the
    choice never changes between runs

Promotion rule
  candidate macro F1 on the gold set improves by >= MIN_GAIN (or by >= MIN_GAIN_ANALYST
  on the analyst part of the gold set, once it has >= MIN_ANALYST_GOLD tickets),
  and it does not drop by more than MAX_BASE_DROP on the base part.
"""

import hashlib
import json
import os
import shutil
import traceback
from datetime import datetime
from typing import Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from config import BASE_TRAINING_LABELS, BASE_TRAINING_TICKETS, MLFLOW_ARTIFACT_ROOT, MLFLOW_TRACKING_URI
from ml.automation_model import CLASSES, AutomationClassifier, prepare_frame
from models import MLModel, SessionLocal, Ticket
from services.automation_scoring import INPUT_COLUMNS, MODEL_PATH, load_automation_model

SEED = 42
VERSION_DIR = "models/versions"
STATUS_PATH = "outputs/retrain_status.json"
EXPERIMENT = "automation_classifier"
MIN_GAIN = 0.005
MIN_GAIN_ANALYST = 0.01
MAX_BASE_DROP = 0.01
MIN_ANALYST_GOLD = 30
GOLD_SHARE_BUCKETS = 5          # 1 in 5 random-sample analyst labels goes to the gold set


# ---------------- data ----------------

def _gold_bucket(ticket_id: int) -> bool:
    return int(hashlib.md5(str(ticket_id).encode()).hexdigest(), 16) % GOLD_SHARE_BUCKETS == 0


def base_dataset():
    raw = pd.read_csv(BASE_TRAINING_TICKETS).merge(
        pd.read_csv(BASE_TRAINING_LABELS)[["number", "true_automation_status"]], on="number")
    return prepare_frame(raw), raw["true_automation_status"].to_numpy()


def analyst_dataset():
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.human_override.in_(CLASSES)).all()
        if not tickets:
            return None
        raw = pd.DataFrame([{**{c: getattr(t, c) for c in INPUT_COLUMNS}, "id": t.id, "label": t.human_override,
                             "label_source": t.label_source} for t in tickets])
    finally:
        db.close()
    raw["gold"] = [(src == "random_sample") and _gold_bucket(i) for i, src in zip(raw["id"], raw["label_source"])]
    return prepare_frame(raw), raw["label"].to_numpy(), raw["gold"].to_numpy()


def build_splits():
    X_base, y_base = base_dataset()
    Xb_pool, Xb_gold, yb_pool, yb_gold = train_test_split(X_base, y_base, test_size=0.2, stratify=y_base,
                                                          random_state=SEED)
    pools_X, pools_y = [Xb_pool], [yb_pool]
    gold = {"base": (Xb_gold, yb_gold)}
    analyst = analyst_dataset()
    n_analyst = 0
    if analyst is not None:
        Xa, ya, is_gold = analyst
        n_analyst = len(ya)
        if is_gold.any():
            gold["analyst"] = (Xa[is_gold], ya[is_gold])
        pools_X.append(Xa[~is_gold])
        pools_y.append(ya[~is_gold])
    X_pool = pd.concat(pools_X, ignore_index=True)
    y_pool = np.concatenate(pools_y)
    X_train, X_val, y_train, y_val = train_test_split(X_pool, y_pool, test_size=0.25, stratify=y_pool,
                                                      random_state=SEED)
    return {"train": (X_train, y_train), "val": (X_val, y_val), "gold": gold,
            "n_analyst_labels": n_analyst, "n_analyst_gold": len(gold.get("analyst", ((), []))[1])}


def evaluate(clf, X, y) -> Dict:
    pred = clf.predict(X)
    return {"macro_f1": round(float(f1_score(y, pred, labels=CLASSES, average="macro", zero_division=0)), 4),
            "accuracy": round(float(accuracy_score(y, pred)), 4), "n": int(len(y))}


def evaluate_on_gold(clf, gold: Dict) -> Dict:
    out = {part: evaluate(clf, X, y) for part, (X, y) in gold.items()}
    X_all = pd.concat([X for X, _ in gold.values()], ignore_index=True)
    y_all = np.concatenate([y for _, y in gold.values()])
    out["all"] = evaluate(clf, X_all, y_all)
    return out


def decide(candidate: Dict, current: Dict) -> Dict:
    gain = candidate["all"]["macro_f1"] - current["all"]["macro_f1"]
    base_drop = current["base"]["macro_f1"] - candidate["base"]["macro_f1"]
    analyst_gain = None
    if "analyst" in candidate and candidate["analyst"]["n"] >= MIN_ANALYST_GOLD:
        analyst_gain = candidate["analyst"]["macro_f1"] - current["analyst"]["macro_f1"]
    improves = gain >= MIN_GAIN or (analyst_gain is not None and analyst_gain >= MIN_GAIN_ANALYST)
    if base_drop > MAX_BASE_DROP:
        promote, reason = False, f"worse on the base test set by {base_drop:.3f} macro F1 (limit {MAX_BASE_DROP})"
    elif not improves:
        promote, reason = False, (f"no meaningful improvement: {gain:+.3f} macro F1 overall"
                                  + (f", {analyst_gain:+.3f} on analyst labels" if analyst_gain is not None else "")
                                  + f" (needs +{MIN_GAIN} overall or +{MIN_GAIN_ANALYST} on analyst labels)")
    else:
        promote, reason = True, (f"{gain:+.3f} macro F1 overall"
                                 + (f", {analyst_gain:+.3f} on analyst labels" if analyst_gain is not None else "")
                                 + f", base change {-base_drop:+.3f}")
    return {"promote": promote, "reason": reason, "gain": round(gain, 4),
            "analyst_gain": None if analyst_gain is None else round(analyst_gain, 4),
            "base_drop": round(base_drop, 4)}


# ---------------- versions ----------------

def _version_path(version: str) -> str:
    return os.path.join(VERSION_DIR, f"automation_classifier_{version}.joblib")


def _archive_active():
    """Make sure the currently active model file is also stored under its version."""
    bundle = load_automation_model()
    if bundle is None:
        return None
    version = bundle.get("version")
    if not version:
        db = SessionLocal()
        try:
            row = db.query(MLModel).filter(MLModel.model_name == "automation_classifier",
                                           MLModel.status == "active").order_by(MLModel.created_at.desc()).first()
            version = row.version if row else "initial"
        finally:
            db.close()
        bundle["version"] = version
    os.makedirs(VERSION_DIR, exist_ok=True)
    if not os.path.exists(_version_path(version)):
        joblib.dump(bundle, _version_path(version))
    return bundle


def activate(version: str, by: str) -> Dict:
    """Make a stored version the active model (used for promotion and rollback)."""
    path = _version_path(version)
    if not os.path.exists(path):
        raise FileNotFoundError(f"No stored model file for version {version}")
    _archive_active()
    shutil.copyfile(path, MODEL_PATH)
    db = SessionLocal()
    try:
        db.query(MLModel).filter(MLModel.model_name == "automation_classifier", MLModel.status == "active") \
            .update({"status": "deprecated"})
        row = db.query(MLModel).filter(MLModel.model_name == "automation_classifier",
                                       MLModel.version == version).first()
        if row:
            row.status = "active"
            row.deployed_on = datetime.now()
        db.commit()
    finally:
        db.close()
    _log_event({"type": "activate", "version": version, "by": by, "time": datetime.now().isoformat(timespec="seconds")})
    return {"active_version": version}


# ---------------- retraining ----------------

def _write_status(status: Dict):
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    with open(STATUS_PATH, "w", encoding="utf-8") as f:
        json.dump(status, f, indent=2, default=str)


def read_status() -> Optional[Dict]:
    if not os.path.exists(STATUS_PATH):
        return None
    with open(STATUS_PATH, encoding="utf-8") as f:
        return json.load(f)


STALE_RUN_HOURS = 1   # a run takes seconds; "running" this old means the server died mid-run


def is_running(status: Optional[Dict], now: Optional[datetime] = None) -> bool:
    if not status or status.get("state") != "running":
        return False
    started = datetime.fromisoformat(status["started_at"])
    return (now or datetime.now()) - started < pd.Timedelta(hours=STALE_RUN_HOURS)


def _log_event(event: Dict):
    path = "outputs/model_events.jsonl"
    os.makedirs("outputs", exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, default=str) + "\n")


def retrain(triggered_by: str) -> Dict:
    started = datetime.now()
    _write_status({"state": "running", "started_at": started.isoformat(timespec="seconds"), "by": triggered_by})
    try:
        current_bundle = _archive_active()
        splits = build_splits()
        X_train, y_train = splits["train"]
        X_val, y_val = splits["val"]

        candidate = AutomationClassifier(random_state=SEED).fit(X_train, y_train, X_val, y_val)
        cand_eval = evaluate_on_gold(candidate, splits["gold"])
        curr_eval = evaluate_on_gold(current_bundle["classifier"], splits["gold"]) if current_bundle else None
        decision = decide(cand_eval, curr_eval) if curr_eval else {"promote": True, "reason": "no active model"}

        version = started.strftime("%Y%m%d-%H%M%S")
        training_data = os.path.basename(BASE_TRAINING_TICKETS) + (
            f" + {splits['n_analyst_labels']} analyst labels" if splits["n_analyst_labels"] else "")
        candidate._explainer = None
        bundle = {"classifier": candidate, "version": version, "trained_at": started.isoformat(timespec="seconds"),
                  "training_data": training_data, "n_train": int(len(y_train)),
                  "test_macro_f1": cand_eval["all"]["macro_f1"], "gold": cand_eval}
        os.makedirs(VERSION_DIR, exist_ok=True)
        joblib.dump(bundle, _version_path(version))

        run_id = _log_mlflow(version, candidate, splits, cand_eval, curr_eval, decision, triggered_by)

        db = SessionLocal()
        try:
            db.add(MLModel(
                model_name="automation_classifier", version=version, framework="xgboost + sklearn",
                accuracy=cand_eval["all"]["accuracy"], f1_score=cand_eval["all"]["macro_f1"],
                status="candidate" if decision["promote"] else "rejected",
                model_path=_version_path(version), trained_on=started, training_samples=int(len(y_train)),
                metrics=json.dumps({"gold": cand_eval, "active_gold": curr_eval, "decision": decision,
                                    "mlflow_run_id": run_id, "training_data": training_data}, default=str)))
            db.commit()
        finally:
            db.close()
        if decision["promote"]:
            activate(version, by=f"retraining ({triggered_by})")

        result = {"state": "done", "version": version, "promoted": decision["promote"], "reason": decision["reason"],
                  "candidate": cand_eval, "active_before": curr_eval, "training_rows": int(len(y_train)),
                  "analyst_labels": splits["n_analyst_labels"], "analyst_gold": splits["n_analyst_gold"],
                  "mlflow_run_id": run_id, "started_at": started.isoformat(timespec="seconds"),
                  "finished_at": datetime.now().isoformat(timespec="seconds"), "by": triggered_by}
        _write_status(result)
        _log_event({"type": "retrain", **{k: result[k] for k in ("version", "promoted", "reason", "finished_at", "by")}})
        return result
    except Exception as e:
        traceback.print_exc()
        result = {"state": "failed", "error": f"{e.__class__.__name__}: {e}",
                  "started_at": started.isoformat(timespec="seconds"), "by": triggered_by}
        _write_status(result)
        return result


def _log_mlflow(version, candidate, splits, cand_eval, curr_eval, decision, triggered_by) -> Optional[str]:
    try:
        import mlflow
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        if mlflow.get_experiment_by_name(EXPERIMENT) is None:
            mlflow.create_experiment(EXPERIMENT, artifact_location=MLFLOW_ARTIFACT_ROOT.replace("\\", "/"))
        mlflow.set_experiment(EXPERIMENT)
        with mlflow.start_run(run_name=version) as run:
            params = {k: v for k, v in candidate.model.get_params().items()
                      if k in ("n_estimators", "learning_rate", "max_depth", "subsample", "colsample_bytree",
                               "min_child_weight", "reg_lambda")}
            mlflow.log_params({**params, "best_iteration": candidate.model.best_iteration,
                               "training_rows": len(splits["train"][1]),
                               "analyst_labels": splits["n_analyst_labels"]})
            for part, m in cand_eval.items():
                mlflow.log_metrics({f"gold_{part}_macro_f1": m["macro_f1"], f"gold_{part}_accuracy": m["accuracy"]})
            if curr_eval:
                mlflow.log_metrics({f"active_gold_{p}_macro_f1": m["macro_f1"] for p, m in curr_eval.items()})
            mlflow.set_tags({"promoted": str(decision["promote"]), "decision": decision["reason"],
                             "triggered_by": triggered_by, "version": version})
            mlflow.log_artifact(_version_path(version), artifact_path="model")
            return run.info.run_id
    except Exception as e:
        print(f"MLflow logging skipped: {e}")
        return None
