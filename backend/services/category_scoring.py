"""
Apply the trained category classifier (train_category_model.py) to an upload.

Writes L1 tower / L2 subcategory and their real (model) confidences to the
tickets table. Without a trained model the keyword-rule labels stay in place.
"""

import json
import os
from typing import Dict, Optional

import pandas as pd

from models import SessionLocal, Ticket
from services.automation_scoring import INPUT_COLUMNS

MODEL_PATH = "models/category_classifier.joblib"
AUTO_ROUTE_THRESHOLD = 0.9  # see reports/category_model_report.json, selective accuracy

_cache: Dict = {}


def load_category_model() -> Optional[Dict]:
    if not os.path.exists(MODEL_PATH):
        return None
    mtime = os.path.getmtime(MODEL_PATH)
    if _cache.get("mtime") != mtime:
        import joblib
        _cache.update(bundle=joblib.load(MODEL_PATH), mtime=mtime)
    return _cache["bundle"]


def apply_category_model(upload_id: int) -> Optional[Dict]:
    bundle = load_category_model()
    if bundle is None:
        print(f"Category model not found at {MODEL_PATH}; keeping keyword-rule categories")
        return None

    from ml.category_model import frame_for

    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        if not tickets:
            return None
        raw = pd.DataFrame([{c: getattr(t, c) for c in INPUT_COLUMNS} for t in tickets])
        pred = bundle["classifier"].predict(frame_for(raw))

        for t, row in zip(tickets, pred.itertuples(index=False)):
            if t.human_override:
                continue
            t.l1_category, t.l1_confidence = row.l1, float(row.l1_confidence)
            t.l2_subcategory, t.l2_confidence = row.l2, float(row.l2_confidence)
        db.commit()

        confident = (pred["l2_confidence"] >= AUTO_ROUTE_THRESHOLD)
        summary = {
            "upload_id": upload_id,
            "model": {k: bundle.get(k) for k in ("trained_at", "training_data", "n_train")},
            "l1_counts": pred["l1"].value_counts().to_dict(),
            "l2_counts": pred["l2"].value_counts().to_dict(),
            "auto_route_threshold": AUTO_ROUTE_THRESHOLD,
            "auto_routable_share": round(float(confident.mean()), 4),
        }
        out_dir = f"outputs/upload_{upload_id}"
        os.makedirs(out_dir, exist_ok=True)
        with open(f"{out_dir}/category_model.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Category model applied to upload {upload_id}: "
              f"{summary['auto_routable_share']:.0%} auto-routable at confidence >= {AUTO_ROUTE_THRESHOLD}")
        return summary
    finally:
        db.close()
