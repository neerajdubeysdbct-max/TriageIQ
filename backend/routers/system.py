"""
System API Router
Live pipeline configuration, activity log and model evaluation.
Every value is read from code constants, saved model artefacts or the
database; nothing here is typed in by hand.
"""

import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc

from dependencies import get_current_user, require_upload_access
from models import SessionLocal, Upload

router = APIRouter(prefix="/api/system", tags=["System"])

REPORT_DIR = "reports"
TRAINING_REPORT = os.path.join(REPORT_DIR, "automation_model_report.json")


def _read_json(path: str):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _mtime(path: str):
    return datetime.fromtimestamp(os.path.getmtime(path)).isoformat(timespec="seconds") if os.path.exists(path) else None


@router.get("/config")
def get_config(user: dict = Depends(get_current_user)):
    """The pipeline configuration as the code actually runs it."""
    from chunk_processor import CHUNK_SIZE
    from routers.copilot import MODEL_NAME, OLLAMA_URL
    from services.automation_scoring import MODEL_PATH, load_automation_model
    from services.ml_analysis import MAX_BERT_TICKETS
    from services.cluster_selection import CANDIDATE_KS
    from services.ml_models import bert_clustering

    settings = [
        {"label": "Embedding model", "value": bert_clustering.model_name,
         "desc": "Sentence-transformer used to embed ticket descriptions (384 dimensions)"},
        {"label": "Clustering", "value": f"KMeans, k = {min(CANDIDATE_KS)}-{max(CANDIDATE_KS)} by silhouette",
         "desc": f"Cluster count chosen per upload on cosine-normalised embeddings; "
                 f"up to {MAX_BERT_TICKETS:,} tickets embedded per upload"},
        {"label": "Copilot LLM", "value": f"{MODEL_NAME} via Ollama",
         "desc": f"Local model at {OLLAMA_URL}; ticket data never leaves the machine"},
        {"label": "Upload chunk size", "value": f"{CHUNK_SIZE:,} tickets",
         "desc": "Rows written to Postgres per batch during upload"},
    ]

    bundle = load_automation_model()
    if bundle:
        clf = bundle["classifier"]
        params = clf.model.get_params()
        settings += [
            {"label": "Automation classifier",
             "value": f"XGBoost, {clf.model.best_iteration + 1} trees, depth {params['max_depth']}",
             "desc": f"Trained {bundle['trained_at']} on {bundle['n_train']:,} labelled tickets "
                     f"({bundle['training_data']}); isotonic calibration"},
            {"label": "Classifier features", "value": f"{len(clf.feature_names):,}",
             "desc": "TF-IDF text terms + priority, channel, team, category, MTTR, reassignments, bot resolver"},
        ]
    else:
        settings.append({"label": "Automation classifier", "value": "not trained",
                         "desc": f"Run train_automation_model.py to create {MODEL_PATH}; rules are used meanwhile"})
    return {"settings": settings}


@router.get("/activity")
def get_activity(limit: int = 30, user: dict = Depends(get_current_user)):
    """Real pipeline events: uploads, their outcome, and model training runs."""
    db = SessionLocal()
    try:
        uploads = (db.query(Upload).filter(Upload.team_id == user["team_id"])
                   .order_by(desc(Upload.created_at)).limit(limit).all())
    finally:
        db.close()

    events = []
    for u in uploads:
        status = u.status or "unknown"
        events.append({
            "time": (u.completed_at or u.created_at).isoformat(timespec="seconds") if (u.completed_at or u.created_at) else None,
            "type": {"completed": "success", "failed": "error"}.get(status, "info"),
            "title": f"Upload #{u.id} {status}: {u.filename}",
            "desc": f"{u.total_tickets or 0:,} tickets",
        })
        applied = _read_json(f"outputs/upload_{u.id}/automation_model.json")
        if applied:
            counts = ", ".join(f"{k} {v:,}" for k, v in applied["status_counts"].items())
            events.append({
                "time": _mtime(f"outputs/upload_{u.id}/automation_model.json"),
                "type": "info",
                "title": f"Automation classifier scored upload #{u.id}",
                "desc": f"{counts}; mean confidence {applied['mean_confidence']:.1%}",
            })

    report = _read_json(TRAINING_REPORT)
    if report:
        best = report["test_results"][-1]
        events.append({
            "time": report["generated_at"], "type": "success",
            "title": "Automation classifier trained",
            "desc": f"Held-out test: accuracy {best['accuracy']:.1%}, macro F1 {best['macro_f1']:.3f} "
                    f"on {report['data']['split']['test']} tickets",
        })

    events.sort(key=lambda e: e["time"] or "", reverse=True)
    return {"events": events[:limit]}


@router.get("/model-evaluation/{upload_id}")
def get_model_evaluation(upload_id: int, user: dict = Depends(require_upload_access)):
    """
    Offline evaluation from training (held-out test, baselines, calibration,
    SHAP) plus what the model did on this upload, and the end-to-end check
    against ground truth if one was run for it (evaluate_upload.py).
    """
    training = _read_json(TRAINING_REPORT)
    if training is None:
        raise HTTPException(404, "No trained automation model. Run train_automation_model.py first.")
    out = f"outputs/upload_{upload_id}"
    return {
        "training": training,
        "upload": _read_json(f"{out}/automation_model.json"),
        "ground_truth_check": _read_json(os.path.join(REPORT_DIR, f"upload_{upload_id}_evaluation.json")),
        "category": _read_json(os.path.join(REPORT_DIR, "category_model_report.json")),
        "category_upload": _read_json(f"{out}/category_model.json"),
        "clustering": _read_json(os.path.join(REPORT_DIR, "clustering_report.json")),
        "cluster_quality": _read_json(f"{out}/cluster_quality.json"),
        "anomaly": _read_json(os.path.join(REPORT_DIR, "anomaly_report.json")),
    }
