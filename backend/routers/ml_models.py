"""
ML Models API Router
Real database queries for model status, metrics, training history
"""

from config import LLM_MODEL
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, desc
from typing import List, Optional
from datetime import datetime
import json
import os

from models import SessionLocal, Ticket, Upload, MLModel
from dependencies import get_current_user, require_upload_access


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/api/ml-models", tags=["ML Models"])


@router.get("/{upload_id}")
async def get_model_metrics(
    upload_id: int,
    user: dict = Depends(require_upload_access),
):
    """Get all ML model metrics — computed from real data + model registry"""
    db = SessionLocal()
    try:
        # Base query for this upload
        base = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
        )

        total = base.count()
        if total == 0:
            raise HTTPException(status_code=404, detail="No tickets found for this upload")

        # ========== BERT Clustering Metrics (from real data) ==========
        clustered = base.filter(Ticket.cluster_id != None).count()
        distinct_clusters = db.query(func.count(func.distinct(Ticket.cluster_id))).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
        ).scalar() or 0

        avg_cluster_similarity = db.query(func.avg(Ticket.cluster_similarity)).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_similarity != None,
        ).scalar() or 0

        has_tsne = base.filter(Ticket.tsne_x != None).count() > 0

        # Whether categories were assigned (model or keyword rules)
        categorised = base.filter(Ticket.l1_category != None).count()

        # ========== Automation Detection Metrics ==========
        # Same flags the overview dashboard uses (set by the automation classifier)
        already_auto = base.filter(Ticket.is_already_automated == True).count()
        can_auto = base.filter(Ticket.is_already_automated != True, Ticket.can_be_automated == True).count()
        manual = total - already_auto - can_auto

        # Held-out test metrics of the active classifier (train_automation_model.py)
        report_path = "reports/automation_model_report.json"
        test_metrics = None
        if os.path.exists(report_path):
            with open(report_path, encoding="utf-8") as f:
                best = json.load(f)["test_results"][-1]
            test_metrics = {"accuracy": best["accuracy"], "macro_f1": best["macro_f1"]}

        # XGBoost automation scoring stats
        scored_tickets = base.filter(Ticket.automation_potential_score != None).count()
        avg_auto_score = db.query(func.avg(Ticket.automation_potential_score)).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.automation_potential_score != None,
        ).scalar() or 0

        # ========== MTTR Statistics (for LSTM-like forecasting metrics) ==========
        mttr_stats = db.query(
            func.avg(Ticket.mttr_hours).label("avg"),
            func.min(Ticket.mttr_hours).label("min"),
            func.max(Ticket.mttr_hours).label("max"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.mttr_hours != None,
            Ticket.mttr_hours > 0,
        ).first()

        # Resolution time by automation status: same definition as the overview (services/metrics.py)
        from services.metrics import mttr_by_status
        mttr_status = mttr_by_status(db, upload_id, user["team_id"])

        # ========== Per-upload model outputs and training provenance ==========
        def read_json(path):
            if not os.path.exists(path):
                return None
            with open(path, encoding="utf-8") as f:
                return json.load(f)

        out_dir = f"outputs/upload_{upload_id}"
        auto_summary = read_json(f"{out_dir}/automation_model.json") or {}
        cat_summary = read_json(f"{out_dir}/category_model.json") or {}
        cluster_quality = read_json(f"{out_dir}/cluster_quality.json") or {}
        cat_report = read_json("reports/category_model_report.json")
        cat_test = None
        if cat_report:
            cat_test = {lvl: v["test_results"][-1]["accuracy"] for lvl, v in cat_report["levels"].items()}
        validated = os.path.exists(f"reports/upload_{upload_id}_evaluation.json")
        llm_classified = base.filter(Ticket.aio_classified_by == "llm_qwen").count()
        llm_towers = db.query(func.count(func.distinct(Ticket.aio_tower))).filter(
            Ticket.upload_id == upload_id, Ticket.team_id == user["team_id"], Ticket.aio_tower != None).scalar() or 0
        llm_conf = db.query(func.avg(Ticket.aio_confidence)).filter(
            Ticket.upload_id == upload_id, Ticket.team_id == user["team_id"], Ticket.aio_classified_by == "llm_qwen").scalar()
        analyst_corrections = base.filter(Ticket.human_override != None, Ticket.human_override != "").count()

        # ========== Model Registry (from MLModel table) ==========
        registered_models = db.query(MLModel).order_by(desc(MLModel.created_at)).limit(20).all()

        model_registry = [
            {
                "name": m.model_name,
                "version": m.version,
                "framework": m.framework,
                "accuracy": m.accuracy,
                "f1_score": m.f1_score,
                "status": m.status,
                "trained_on": m.trained_on.isoformat() if m.trained_on else None,
                "deployed_on": m.deployed_on.isoformat() if m.deployed_on else None,
                "training_samples": m.training_samples,
            }
            for m in registered_models
        ]

        # ========== Build Response ==========
        return {
            "upload_id": upload_id,
            "total_tickets": total,
            "models": {
                "bert_clustering": {
                    "name": "Sentence Embeddings + KMeans",
                    "drill": "bert",
                    "status": "trained" if clustered > 0 else "not_run",
                    "type": "embedding",
                    "dimensions": 384 if clustered > 0 else None,
                    "tickets_processed": clustered,
                    "clusters_found": distinct_clusters,
                    "avg_similarity": round(avg_cluster_similarity, 3),
                    "has_tsne": has_tsne,
                    "coverage_pct": round(clustered / max(total, 1) * 100, 1),
                    "k_selection": cluster_quality.get("method"),
                    "silhouette": cluster_quality.get("final_silhouette"),
                },
                "xgboost_scorer": {
                    "name": "Automation Classifier (XGBoost)",
                    "drill": "xgboost",
                    "status": "trained" if test_metrics else "rules",
                    "type": "classifier",
                    "test_metrics": test_metrics,
                    "tickets_scored": scored_tickets,
                    "avg_score": round(avg_auto_score, 3),
                    "automation_breakdown": {
                        "already_automated": already_auto,
                        "can_automate": can_auto,
                        "manual_only": manual,
                    },
                    "coverage_pct": round(scored_tickets / max(total, 1) * 100, 1),
                    "mean_confidence": auto_summary.get("mean_confidence"),
                    "rule_detector_agreement": auto_summary.get("rule_detector_agreement", auto_summary.get("llm_status_agreement")),
                    "validated_on_dataset": validated,
                    "model": auto_summary.get("model"),
                },
                "category_classifier": {
                    "name": "Category Classifier (L1 / L2)",
                    "status": "trained" if cat_summary else ("rules" if categorised > 0 else "not_run"),
                    "type": "classifier",
                    "test_accuracy": cat_test,
                    "tickets_labelled": categorised,
                    "auto_routable_share": cat_summary.get("auto_routable_share"),
                    "auto_route_threshold": cat_summary.get("auto_route_threshold"),
                    "validated_on_dataset": validated,
                    "model": cat_summary.get("model"),
                },
                "aiops_classifier": {
                    "name": "LLM Category Layer (Qwen)",
                    "status": "pretrained" if llm_classified else "not_run",
                    "tickets_classified": llm_classified,
                    "towers_found": llm_towers,
                    # share of a cluster's sample tickets on which the LLM agreed (majority vote)
                    "mean_sample_agreement": round(float(llm_conf), 4) if llm_conf else None,
                    "model": f"{LLM_MODEL}, a few sample tickets per cluster, result propagated to the cluster",
                },
            },
            "mttr_analysis": {
                "avg_hours": round(mttr_stats.avg, 2) if mttr_stats and mttr_stats.avg else 0,
                "min_hours": round(mttr_stats.min, 2) if mttr_stats and mttr_stats.min else 0,
                "max_hours": round(mttr_stats.max, 2) if mttr_stats and mttr_stats.max else 0,
                "tickets_with_mttr": mttr_stats.count if mttr_stats else 0,
                "by_status": mttr_status,
            },
            "training_data": {
                "automation_model": auto_summary.get("model"),
                "category_model": cat_summary.get("model"),
                "analyst_corrections": analyst_corrections,
            },
            "model_registry": model_registry,
        }
    finally:
        db.close()


@router.get("/{upload_id}/bert/embeddings")
async def get_bert_embeddings_sample(
    upload_id: int,
    limit: int = 10,
    user: dict = Depends(require_upload_access),
):
    """Get sample tickets with their cluster assignments and similar tickets"""
    db = SessionLocal()
    try:
        # Get tickets with embeddings/clusters
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
        ).order_by(desc(Ticket.cluster_similarity)).limit(limit).all()

        samples = []
        for t in tickets:
            # Find similar tickets in same cluster
            similar = db.query(Ticket).filter(
                Ticket.upload_id == upload_id,
                Ticket.team_id == user["team_id"],
                Ticket.cluster_id == t.cluster_id,
                Ticket.id != t.id,
            ).order_by(desc(Ticket.cluster_similarity)).limit(3).all()

            samples.append({
                "ticket_id": t.ticket_number or f"TKT-{t.id}",
                "short_description": (t.short_description or "")[:100],
                "cluster_id": t.cluster_id,
                "similarity": round(t.cluster_similarity or 0, 3),
                "tsne_x": round(t.tsne_x, 4) if t.tsne_x else None,
                "tsne_y": round(t.tsne_y, 4) if t.tsne_y else None,
                "similar_tickets": [
                    {
                        "ticket_id": s.ticket_number or f"TKT-{s.id}",
                        "similarity": round(s.cluster_similarity or 0, 3),
                        "short_description": (s.short_description or "")[:80],
                    }
                    for s in similar
                ],
            })

        # Total stats
        total_vectors = db.query(func.count(Ticket.id)).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
        ).scalar() or 0

        total_clusters = db.query(func.count(func.distinct(Ticket.cluster_id))).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.cluster_id != None,
        ).scalar() or 0

        return {
            "upload_id": upload_id,
            "total_vectors": total_vectors,
            "total_clusters": total_clusters,
            "dimensions": 384,
            "samples": samples,
        }
    finally:
        db.close()