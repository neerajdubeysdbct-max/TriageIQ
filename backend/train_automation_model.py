"""
Train and evaluate the automation status classifier.

    python train_automation_model.py \
        --tickets ../sample_data/northwind_incidents.csv \
        --labels  ../sample_data/northwind_ground_truth.csv

Protocol:
  - stratified 60/20/20 train / validation / test split
  - validation is used for early stopping and probability calibration only
  - the test split is scored exactly once, at the end
  - baselines (majority class, single "resolved by bot" rule, logistic
    regression on the same features) are scored on the same test split

Outputs:
  models/automation_classifier.joblib
  reports/automation_model_report.json
  reports/automation_model_report.md
"""

import argparse
import json
import os
from datetime import datetime

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, classification_report,
                             confusion_matrix, f1_score)
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from xgboost import XGBClassifier

from ml.automation_model import (AUTOMATABLE, CLASSES, TIERS, AutomationClassifier,
                                 build_preprocessor, prepare_frame)

SEED = 42


def expected_calibration_error(y_true_idx: np.ndarray, proba: np.ndarray, n_bins: int = 10) -> float:
    """ECE on the top-class confidence: avg |accuracy - confidence| over equal-width bins."""
    conf = proba.max(axis=1)
    correct = (proba.argmax(axis=1) == y_true_idx).astype(float)
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf > lo) & (conf <= hi)
        if mask.any():
            ece += mask.mean() * abs(correct[mask].mean() - conf[mask].mean())
    return float(ece)


def multiclass_brier(y_true_idx: np.ndarray, proba: np.ndarray) -> float:
    onehot = np.eye(proba.shape[1])[y_true_idx]
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def summarize(name: str, y_true, y_pred) -> dict:
    report = classification_report(y_true, y_pred, labels=CLASSES, output_dict=True, zero_division=0)
    return {
        "model": name,
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, labels=CLASSES, average="macro", zero_division=0), 4),
        "per_class": {c: {k: round(report[c][k], 4) for k in ("precision", "recall", "f1-score", "support")}
                      for c in CLASSES},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=CLASSES).tolist(),
    }


def load_data(tickets_path: str, labels_path: str):
    tickets = pd.read_csv(tickets_path)
    labels = pd.read_csv(labels_path)[["number", "true_automation_status"]]
    df = tickets.merge(labels, on="number", how="inner")
    if len(df) < len(tickets):
        print(f"Warning: {len(tickets) - len(df)} tickets had no label and were dropped")
    return prepare_frame(df), df["true_automation_status"].to_numpy(), df["number"].to_numpy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickets", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--model-out", default="models/automation_classifier.joblib")
    ap.add_argument("--report-dir", default="reports")
    args = ap.parse_args()

    X, y, ids = load_data(args.tickets, args.labels)
    print(f"Loaded {len(X)} labelled tickets: {pd.Series(y).value_counts().to_dict()}")

    X_tmp, X_test, y_tmp, y_test = train_test_split(X, y, test_size=0.20, stratify=y, random_state=SEED)
    X_train, X_val, y_train, y_val = train_test_split(X_tmp, y_tmp, test_size=0.25, stratify=y_tmp,
                                                      random_state=SEED)
    print(f"Split: train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")

    # ---------------- baselines ----------------
    results = []
    majority = pd.Series(y_train).mode()[0]
    results.append(summarize("Majority class", y_test, np.full(len(y_test), majority)))

    rest = pd.Series(y_train[X_train["resolver_is_bot"].to_numpy() == 0]).mode()[0]
    bot_rule = np.where(X_test["resolver_is_bot"] == 1, "Already Automated", rest)
    results.append(summarize('Rule: "resolved by bot"', y_test, bot_rule))

    logreg = make_pipeline(build_preprocessor(),
                           LogisticRegression(max_iter=2000, C=2.0, class_weight="balanced"))
    logreg.fit(X_train, y_train)
    results.append(summarize("Logistic regression", y_test, logreg.predict(X_test)))

    # ---------------- main model ----------------
    clf = AutomationClassifier(random_state=SEED).fit(X_train, y_train, X_val, y_val)
    print(f"XGBoost early-stopped at {clf.model.best_iteration + 1} trees")
    xgb_pred = clf.predict(X_test)
    results.append(summarize("XGBoost (calibrated)", y_test, xgb_pred))

    # ---------------- calibration ----------------
    y_test_idx = clf.encoder.transform(y_test)
    raw_p = clf.predict_proba(X_test, calibrated=False)
    cal_p = clf.predict_proba(X_test, calibrated=True)
    calibration = {
        "ece_before": round(expected_calibration_error(y_test_idx, raw_p), 4),
        "ece_after": round(expected_calibration_error(y_test_idx, cal_p), 4),
        "brier_before": round(multiclass_brier(y_test_idx, raw_p), 4),
        "brier_after": round(multiclass_brier(y_test_idx, cal_p), 4),
    }
    automatable_true = np.isin(y_test, AUTOMATABLE).astype(int)
    automatable_p = cal_p[:, [list(clf.encoder.classes_).index(c) for c in AUTOMATABLE]].sum(axis=1)
    calibration["brier_automatable_binary"] = round(brier_score_loss(automatable_true, automatable_p), 4)

    # ---------------- score tiers ----------------
    scored = clf.score(X_test)
    tiers = []
    for _, tier in TIERS:
        mask = (scored["feasibility_tier"] == tier).to_numpy()
        tiers.append({
            "tier": tier,
            "tickets": int(mask.sum()),
            "share_of_tickets": round(float(mask.mean()), 4),
            "actually_automatable": round(float(automatable_true[mask].mean()), 4) if mask.any() else None,
        })

    # ---------------- cross-validation (robustness) ----------------
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    X_dev, y_dev = pd.concat([X_train, X_val]), np.concatenate([y_train, y_val])
    y_dev_idx = clf.encoder.transform(y_dev)
    xgb_fixed = make_pipeline(build_preprocessor(), XGBClassifier(
        objective="multi:softprob", n_estimators=clf.model.best_iteration + 1, learning_rate=0.05,
        max_depth=4, subsample=0.8, colsample_bytree=0.5, min_child_weight=5, reg_lambda=5.0, tree_method="hist",
        random_state=SEED, n_jobs=-1))
    cv_scores = {
        "Logistic regression": cross_val_score(logreg, X_dev, y_dev, cv=cv, scoring="f1_macro"),
        "XGBoost": cross_val_score(xgb_fixed, X_dev, y_dev_idx, cv=cv, scoring="f1_macro"),
    }
    cross_validation = {k: {"macro_f1_mean": round(v.mean(), 4), "macro_f1_std": round(v.std(), 4)}
                        for k, v in cv_scores.items()}

    # ---------------- explanations ----------------
    importance = clf.global_importance(X_test, top_n=20)
    errors = X_test.assign(true=y_test, pred=xgb_pred, id=ids[X_test.index])
    errors = errors[errors["true"] != errors["pred"]]
    error_examples = [{"number": r.id, "true": r.true, "predicted": r.pred, "text": r.text[:160]}
                      for r in errors.head(8).itertuples()]

    # ---------------- save ----------------
    os.makedirs(os.path.dirname(args.model_out) or ".", exist_ok=True)
    os.makedirs(args.report_dir, exist_ok=True)
    clf._explainer = None
    trained_at = datetime.now()
    version = trained_at.strftime("%Y%m%d-%H%M%S")
    bundle = {"classifier": clf, "version": version, "trained_at": trained_at.isoformat(timespec="seconds"),
              "training_data": os.path.basename(args.tickets), "n_train": len(X_train),
              "test_macro_f1": results[-1]["macro_f1"]}
    joblib.dump(bundle, args.model_out)
    # versioned copy, so this model can be rolled back to (services/model_lifecycle.py)
    os.makedirs("models/versions", exist_ok=True)
    joblib.dump(bundle, f"models/versions/automation_classifier_{version}.joblib")

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "data": {"tickets": os.path.basename(args.tickets), "labels": os.path.basename(args.labels),
                 "n": len(X), "class_counts": pd.Series(y).value_counts().to_dict(),
                 "split": {"train": len(X_train), "val": len(X_val), "test": len(X_test)}},
        "test_results": results,
        "calibration": calibration,
        "score_tiers": tiers,
        "cross_validation": cross_validation,
        "xgboost_trees": int(clf.model.best_iteration + 1),
        "feature_importance_shap": importance,
        "error_examples": error_examples,
    }
    with open(os.path.join(args.report_dir, "automation_model_report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    with open(os.path.join(args.report_dir, "automation_model_report.md"), "w", encoding="utf-8") as f:
        f.write(render_markdown(report))

    register_model(args.model_out, report, len(X_train), version)

    print_summary(report)
    print(f"\nModel  -> {args.model_out}\nReport -> {args.report_dir}/automation_model_report.md")


def register_model(model_path: str, report: dict, n_train: int, version: str):
    """Record this training run in the ml_models registry; it becomes the active version."""
    from models import MLModel, SessionLocal
    best = report["test_results"][-1]
    now = datetime.now()
    db = SessionLocal()
    try:
        db.query(MLModel).filter(MLModel.model_name == "automation_classifier",
                                 MLModel.status == "active").update({"status": "deprecated"})
        db.add(MLModel(
            model_name="automation_classifier", version=version,
            framework="xgboost + sklearn", accuracy=best["accuracy"], f1_score=best["macro_f1"],
            status="active", model_path=model_path, trained_on=now, deployed_on=now,
            training_samples=n_train,
            metrics=json.dumps({"calibration": report["calibration"], "cross_validation": report["cross_validation"],
                                "data": report["data"]}, default=str),
        ))
        db.commit()
    finally:
        db.close()


def render_markdown(r: dict) -> str:
    lines = [f"# Automation classifier: evaluation report",
             f"_Generated {r['generated_at']} on `{r['data']['tickets']}` "
             f"({r['data']['n']} tickets; split {r['data']['split']})_", "",
             "## Held-out test results", "",
             "| Model | Accuracy | Macro F1 |", "|---|---|---|"]
    lines += [f"| {m['model']} | {m['accuracy']:.1%} | {m['macro_f1']:.3f} |" for m in r["test_results"]]
    best = r["test_results"][-1]
    lines += ["", f"### {best['model']}: per class", "",
              "| Class | Precision | Recall | F1 | Support |", "|---|---|---|---|---|"]
    lines += [f"| {c} | {v['precision']:.3f} | {v['recall']:.3f} | {v['f1-score']:.3f} | {int(v['support'])} |"
              for c, v in best["per_class"].items()]
    lines += ["", "Confusion matrix (rows = true, columns = predicted):", "",
              "| | " + " | ".join(CLASSES) + " |", "|---" * (len(CLASSES) + 1) + "|"]
    lines += [f"| **{c}** | " + " | ".join(str(v) for v in row) + " |"
              for c, row in zip(CLASSES, best["confusion_matrix"])]
    c = r["calibration"]
    lines += ["", "## Calibration", "",
              f"- Expected calibration error: {c['ece_before']:.3f} raw → {c['ece_after']:.3f} after isotonic calibration",
              f"- Multi-class Brier score: {c['brier_before']:.3f} → {c['brier_after']:.3f}", "",
              "## Automation score tiers (test set)", "",
              "| Tier | Tickets | Share | Actually automatable |", "|---|---|---|---|"]
    lines += [f"| {t['tier']} | {t['tickets']} | {t['share_of_tickets']:.1%} | "
              f"{'—' if t['actually_automatable'] is None else format(t['actually_automatable'], '.1%')} |"
              for t in r["score_tiers"]]
    lines += ["", "## 5-fold cross-validation (train + validation)", ""]
    lines += [f"- {k}: macro F1 {v['macro_f1_mean']:.3f} ± {v['macro_f1_std']:.3f}"
              for k, v in r["cross_validation"].items()]
    lines += ["", "## Top features (mean |SHAP|, all classes)", ""]
    lines += [f"{i}. {f['feature']} ({f['importance']:.3f})"
              for i, f in enumerate(r["feature_importance_shap"]["overall"][:15], 1)]
    lines += ["", "## Example errors", ""]
    lines += [f"- `{e['number']}` true **{e['true']}**, predicted **{e['predicted']}**: {e['text']}"
              for e in r["error_examples"]]
    return "\n".join(lines) + "\n"


def print_summary(r: dict):
    print("\n=== Held-out test set ===")
    for m in r["test_results"]:
        print(f"  {m['model']:28s} acc {m['accuracy']:.1%}   macro-F1 {m['macro_f1']:.3f}")
    c = r["calibration"]
    print(f"\nCalibration ECE {c['ece_before']:.3f} -> {c['ece_after']:.3f},  "
          f"Brier {c['brier_before']:.3f} -> {c['brier_after']:.3f}")
    print("\nTiers:", ", ".join(f"{t['tier']} {t['tickets']} ({t['actually_automatable']})" for t in r["score_tiers"]))
    print("CV:", r["cross_validation"])
    print("\nTop SHAP features:", [f["feature"] for f in r["feature_importance_shap"]["overall"][:8]])


if __name__ == "__main__":
    main()
