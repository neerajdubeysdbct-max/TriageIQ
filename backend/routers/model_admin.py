"""
Model lifecycle API: retrain from analyst labels, see versions and their gate
results, roll back, re-score a dataset, and read drift reports.

Retraining and activation change the model for every team, so they need the
admin role; reading status and re-scoring a team's own dataset do not.
"""

import json

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException

from dependencies import get_current_user, require_admin, require_upload_access
from models import MLModel, SessionLocal

router = APIRouter(prefix="/api/models", tags=["Model lifecycle"])


@router.post("/automation/retrain")
def start_retraining(background: BackgroundTasks, user: dict = Depends(require_admin)):
    from services import model_lifecycle
    if model_lifecycle.is_running(model_lifecycle.read_status()):
        raise HTTPException(409, "A retraining run is already in progress")
    background.add_task(model_lifecycle.retrain, user["user_id"])
    return {"state": "running"}


@router.get("/automation/retrain-status")
def retraining_status(user: dict = Depends(get_current_user)):
    from services import model_lifecycle
    return model_lifecycle.read_status() or {"state": "never_run"}


@router.get("/automation/versions")
def versions(user: dict = Depends(get_current_user)):
    import os
    from services.model_lifecycle import _version_path
    db = SessionLocal()
    try:
        rows = db.query(MLModel).filter(MLModel.model_name == "automation_classifier") \
            .order_by(MLModel.created_at.desc()).limit(50).all()
    finally:
        db.close()
    out = []
    for r in rows:
        metrics = json.loads(r.metrics) if r.metrics else {}
        out.append({
            "version": r.version, "status": r.status, "accuracy": r.accuracy, "macro_f1": r.f1_score,
            "training_rows": r.training_samples, "trained_on": r.trained_on.isoformat() if r.trained_on else None,
            "deployed_on": r.deployed_on.isoformat() if r.deployed_on else None,
            "training_data": metrics.get("training_data") or (metrics.get("data") or {}).get("tickets"),
            "decision": (metrics.get("decision") or {}).get("reason"),
            "mlflow_run_id": metrics.get("mlflow_run_id"),
            "can_activate": r.status != "active" and os.path.exists(_version_path(r.version)),
        })
    return {"versions": out}


@router.post("/automation/versions/{version}/activate")
def activate_version(version: str, user: dict = Depends(require_admin)):
    from services import model_lifecycle
    try:
        return model_lifecycle.activate(version, by=user["user_id"])
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@router.post("/rescore/{upload_id}")
def rescore(upload_id: int, background: BackgroundTasks, user: dict = Depends(require_upload_access)):
    """Re-apply the active automation and category models to a dataset (analyst labels are kept)."""
    def run():
        from services.category_scoring import apply_category_model
        from services.automation_scoring import apply_automation_model
        apply_category_model(upload_id)
        apply_automation_model(upload_id)
    background.add_task(run)
    return {"state": "running"}


@router.get("/drift/{upload_id}")
def drift_report(upload_id: int, user: dict = Depends(require_upload_access)):
    from services import drift
    return drift.load(upload_id) or {"status": "unknown", "findings": [], "recommendation": "No drift report yet."}
