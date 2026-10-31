"""
Apply the trained automation classifier to an upload.

If models/automation_classifier.joblib exists (see train_automation_model.py),
every ticket gets a model-based status, calibrated confidence, automation score
and feasibility tier, and the upload gets real SHAP feature importance.
Without a trained model nothing changes and the legacy rules stay in place.
"""

import json
import os
from typing import Dict, Optional

import joblib
import pandas as pd

from models import SessionLocal, Ticket

MODEL_PATH = "models/automation_classifier.joblib"

# Ticket columns the model's feature preparation can use
INPUT_COLUMNS = [
    "short_description", "description", "close_notes", "resolution_notes", "priority",
    "contact_type", "channel", "assignment_group", "category", "opened", "resolved",
    "mttr_hours", "reassignment_count", "reopen_count", "resolved_by", "sys_updated_by",
    "caller_id", "assigned_to", "requested_for", "location",
]

_bundle_cache: Dict = {}


def load_automation_model() -> Optional[Dict]:
    """Load the trained model bundle, re-reading it if the file was retrained."""
    if not os.path.exists(MODEL_PATH):
        return None
    mtime = os.path.getmtime(MODEL_PATH)
    if _bundle_cache.get("mtime") != mtime:
        _bundle_cache["bundle"] = joblib.load(MODEL_PATH)
        _bundle_cache["mtime"] = mtime
    return _bundle_cache["bundle"]


def apply_automation_model(upload_id: int, shap_sample: int = 1000) -> Optional[Dict]:
    """
    Score every ticket of an upload with the trained classifier and persist results.
    Returns a summary dict, or None when no trained model is available.
    """
    bundle = load_automation_model()
    if bundle is None:
        print(f"Automation model not found at {MODEL_PATH}; keeping rule-based flags")
        return None

    from ml.automation_model import prepare_frame
    clf = bundle["classifier"]

    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        if not tickets:
            return None

        raw = pd.DataFrame([{c: getattr(t, c) for c in INPUT_COLUMNS} for t in tickets])
        X = prepare_frame(raw)
        scored = clf.score(X)

        # Does this upload look like the training data? (services/drift.py)
        from services import drift
        drift_report = drift.assess(clf, X, scored["confidence"].to_numpy())
        if drift_report:
            drift.save(upload_id, drift_report)

        # How often the upload-time rule detector (aiops_*) agreed with the classifier, before aligning it
        llm_status = [t.aiops_automation_status for t in tickets]
        compared = [(a, p) for a, p in zip(llm_status, scored["predicted_status"]) if a]
        rule_agreement = round(sum(a == p for a, p in compared) / len(compared), 4) if compared else None
        levers = reconcile_levers(tickets, scored["predicted_status"].tolist())

        for t, row, lever in zip(tickets, scored.itertuples(index=False), levers):
            t.model_status = row.predicted_status   # kept even when an analyst has labelled the ticket
            if t.human_override:
                continue  # never overwrite an analyst's correction
            t.is_already_automated = row.predicted_status == "Already Automated"
            t.can_be_automated = row.predicted_status == "Can Be Automated"
            t.automation_potential_score = float(row.automation_score)
            t.l3_automation_feasibility = row.feasibility_tier
            t.automation_confidence = float(row.confidence)
            # One automation status across every tab; the lever must not contradict it
            t.aiops_automation_status = row.predicted_status
            t.aiops_solution_lever = lever
        db.commit()

        sample = X.sample(min(shap_sample, len(X)), random_state=42)
        importance = clf.global_importance(sample, top_n=20)

        summary = {
            "upload_id": upload_id,
            "model": {k: bundle.get(k) for k in ("version", "trained_at", "training_data", "n_train", "test_macro_f1")},
            "status_counts": scored["predicted_status"].value_counts().to_dict(),
            "tier_counts": scored["feasibility_tier"].value_counts().to_dict(),
            "mean_confidence": round(float(scored["confidence"].mean()), 4),
            "rule_detector_agreement": rule_agreement,
            "drift_status": drift_report["status"] if drift_report else None,
            "feature_importance_shap": importance,
        }
        out_dir = f"outputs/upload_{upload_id}"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/automation_model.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, default=str)

        try:
            import numpy as np
            from services.ml_models import visualize_xgboost_features
            top = importance["overall"][:15]
            visualize_xgboost_features(np.array([x["importance"] for x in top]), [x["feature"] for x in top],
                                       output_path=f"{out_dir}/2_xgboost_features.png")
        except Exception as e:
            print(f"SHAP chart skipped: {e}")

        print(f"Automation model applied to upload {upload_id}: {summary['status_counts']}, "
              f"tiers {summary['tier_counts']}")
        return summary
    finally:
        db.close()


EXISTING_LEVERS = {"Existing Automation", "Self-Healing", "Automation Tuning"}
NON_ACTIONABLE = EXISTING_LEVERS | {"Manual Process", "", None}


def reconcile_levers(tickets, statuses):
    """
    Solution lever consistent with the automation status:
      Manual Only        -> Manual Process
      Already Automated  -> keep an existing-automation lever, else Existing Automation
      Can Be Automated   -> keep an actionable lever; if the LLM gave a contradictory one,
                            use the most common actionable lever among tickets of the same
                            subcategory, else Script/Runbook
    """
    from collections import Counter, defaultdict
    by_type = defaultdict(Counter)
    for t, status in zip(tickets, statuses):
        if status == "Can Be Automated" and t.aiops_solution_lever not in NON_ACTIONABLE:
            by_type[t.l2_subcategory or t.subcategory or t.category][t.aiops_solution_lever] += 1
    levers = []
    for t, status in zip(tickets, statuses):
        current = t.aiops_solution_lever
        if status == "Manual Only":
            levers.append("Manual Process")
        elif status == "Already Automated":
            levers.append(current if current in EXISTING_LEVERS else "Existing Automation")
        elif current not in NON_ACTIONABLE:
            levers.append(current)
        else:
            common = by_type.get(t.l2_subcategory or t.subcategory or t.category)
            levers.append(common.most_common(1)[0][0] if common else "Script/Runbook")
    return levers


def shap_importance_for_chart(upload_id: int, top_n: int = 10):
    """(importances, names) from the upload's saved SHAP summary, for the static chart."""
    path = f"outputs/upload_{upload_id}/automation_model.json"
    if not os.path.exists(path):
        return None, None
    with open(path, encoding="utf-8") as f:
        overall = json.load(f)["feature_importance_shap"]["overall"][:top_n]
    return [x["importance"] for x in overall], [x["feature"] for x in overall]
