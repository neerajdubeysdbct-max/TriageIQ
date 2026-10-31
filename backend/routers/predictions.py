"""
Predictions API Router
Real database queries for SLA risk, anomalies, volume forecast, ticket predictions
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, desc, asc, extract
from typing import List, Optional
from datetime import datetime, timedelta
from collections import Counter
import math
import numpy as np

from models import SessionLocal, Ticket, Upload
from dependencies import get_current_user, require_upload_access


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/api/predictions", tags=["Predictions"])


# Priority parsing and SLA targets are shared with the rest of the app (utils.py)
from utils import SLA_HOURS, normalize_priority


def get_sla_deadline(priority: str) -> float:
    """SLA resolution target in hours for any priority label (P3 target if unreadable)."""
    return SLA_HOURS.get(normalize_priority(priority), SLA_HOURS["P3"])
    p = priority.lower().strip()
    if "1" in p or "critical" in p:
        return "P1"
    if "2" in p or "high" in p:
        return "P2"
    if "3" in p or "moderate" in p or "medium" in p:
        return "P3"
    if "4" in p or "low" in p:
        return "P4"
    return "P3"


@router.get("/{upload_id}/ticket/{ticket_id}")
async def get_ticket_predictions(
    upload_id: int,
    ticket_id: str,
    user: dict = Depends(require_upload_access),
):
    """Get all ML predictions for a single ticket — from real DB columns"""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            or_(
                Ticket.ticket_number == ticket_id,
                Ticket.id == int(ticket_id) if ticket_id.isdigit() else False,
            )
        ).first()

        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        sla_deadline = get_sla_deadline(ticket.priority)
        mttr = ticket.mttr_hours or 0
        risk_pct = min(round((mttr / sla_deadline) * 100, 1), 100) if sla_deadline > 0 else 0

        # Determine risk level
        if risk_pct >= 90:
            risk_level = "Critical"
        elif risk_pct >= 70:
            risk_level = "High"
        elif risk_pct >= 40:
            risk_level = "Medium"
        else:
            risk_level = "Low"

        # Find similar tickets by cluster
        similar = []
        if ticket.cluster_id is not None:
            similar_tickets = db.query(Ticket).filter(
                Ticket.upload_id == upload_id,
                Ticket.team_id == user["team_id"],
                Ticket.cluster_id == ticket.cluster_id,
                Ticket.id != ticket.id,
            ).order_by(desc(Ticket.cluster_similarity)).limit(5).all()

            similar = [
                {
                    "ticket_id": t.ticket_number or f"TKT-{t.id}",
                    "similarity": round(t.cluster_similarity or 0, 2),
                    "resolution_hours": round(t.mttr_hours, 1) if t.mttr_hours else None,
                    "short_description": (t.short_description or "")[:80],
                }
                for t in similar_tickets
            ]

        return {
            "ticket_id": ticket.ticket_number or f"TKT-{ticket.id}",
            "short_description": ticket.short_description,
            "predictions": {
                "category": {
                    "l1": ticket.l1_category,
                    "l2": ticket.l2_subcategory,
                    "l3": ticket.l3_automation_feasibility,
                    "l4": ticket.l4_automation_type,
                    "l1_confidence": ticket.l1_confidence,
                    "l2_confidence": ticket.l2_confidence,
                    "l3_confidence": ticket.l3_confidence,
                    "l4_confidence": ticket.l4_confidence,
                },
                "aiops": {
                    "type": ticket.aiops_type,
                    "category": ticket.aiops_category,
                    "subcategory": ticket.aiops_subcategory,
                    "automation_status": ticket.aiops_automation_status,
                    "solution_lever": ticket.aiops_solution_lever,
                    "confidence": ticket.aiops_confidence,
                    "predicted_by": ticket.aiops_predicted_by,
                    "additional_info": ticket.aiops_additional_info,
                },
                "mttr": {
                    "actual_hours": round(mttr, 2) if mttr else None,
                    "sla_deadline_hours": sla_deadline,
                    "risk_pct": risk_pct,
                    "risk_level": risk_level,
                },
                "quality": {
                    "reassignment_count": ticket.reassignment_count or 0,
                    "reopen_count": ticket.reopen_count or 0,
                },
                "cluster": {
                    "cluster_id": ticket.cluster_id,
                    "similarity": round(ticket.cluster_similarity or 0, 2),
                },
            },
            "similar_tickets": similar,
        }
    finally:
        db.close()


@router.get("/{upload_id}/sla-risk")
async def get_sla_risk_tickets(
    upload_id: int,
    min_risk: float = 30,
    limit: int = 50,
    user: dict = Depends(require_upload_access),
):
    """Get tickets at risk of SLA breach — computed from real MTTR + priority"""
    db = SessionLocal()
    try:
        # Get all tickets with MTTR and priority
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.mttr_hours != None,
            Ticket.priority != None,
        ).all()

        at_risk = []
        for t in tickets:
            sla_deadline = get_sla_deadline(t.priority)
            mttr = t.mttr_hours or 0
            if sla_deadline <= 0:
                continue

            risk_pct = min(round((mttr / sla_deadline) * 100, 1), 100)

            if risk_pct >= min_risk:
                if risk_pct >= 90:
                    risk_level = "Critical"
                elif risk_pct >= 70:
                    risk_level = "High"
                elif risk_pct >= 40:
                    risk_level = "Medium"
                else:
                    risk_level = "Low"

                at_risk.append({
                    "ticket_id": t.ticket_number or f"TKT-{t.id}",
                    "priority": normalize_priority(t.priority),
                    "actual_mttr": round(mttr, 2),
                    "sla_deadline": sla_deadline,
                    "risk_pct": risk_pct,
                    "risk_level": risk_level,
                    "assignment_group": t.assignment_group,
                    "short_description": (t.short_description or "")[:100],
                    "category": t.l1_category or t.category,
                    "is_breached": mttr > sla_deadline,
                })

        # Sort by risk descending
        at_risk.sort(key=lambda x: x["risk_pct"], reverse=True)

        # Calculate summary stats
        total_tickets = len(tickets)
        breached = [t for t in at_risk if t["is_breached"]]
        critical = [t for t in at_risk if t["risk_level"] == "Critical"]
        high = [t for t in at_risk if t["risk_level"] == "High"]

        # Risk distribution
        risk_distribution = {
            "critical": len(critical),
            "high": len(high),
            "medium": len([t for t in at_risk if t["risk_level"] == "Medium"]),
            "low": len([t for t in at_risk if t["risk_level"] == "Low"]),
        }

        # SLA compliance
        sla_compliance = round((1 - len(breached) / max(total_tickets, 1)) * 100, 1)

        # Average risk for at-risk tickets
        avg_risk = round(
            sum(t["risk_pct"] for t in at_risk) / max(len(at_risk), 1), 1
        )

        # Top at-risk groups
        group_risks = {}
        for t in at_risk:
            grp = t["assignment_group"] or "Unknown"
            if grp not in group_risks:
                group_risks[grp] = {"count": 0, "total_risk": 0}
            group_risks[grp]["count"] += 1
            group_risks[grp]["total_risk"] += t["risk_pct"]

        top_risk_groups = sorted(
            [
                {"group": g, "at_risk_count": v["count"], "avg_risk": round(v["total_risk"] / v["count"], 1)}
                for g, v in group_risks.items()
            ],
            key=lambda x: x["at_risk_count"],
            reverse=True,
        )[:10]

        return {
            "upload_id": upload_id,
            "total_tickets": total_tickets,
            "at_risk_count": len(at_risk),
            "breached_count": len(breached),
            "sla_compliance_pct": sla_compliance,
            "avg_risk_score": avg_risk,
            "risk_distribution": risk_distribution,
            "top_risk_groups": top_risk_groups,
            "tickets": at_risk[:limit],
        }
    finally:
        db.close()


@router.get("/{upload_id}/anomalies")
async def get_anomalies(
    upload_id: int,
    limit: int = 50,
    user: dict = Depends(require_upload_access),
):
    """
    IsolationForest anomaly detection with per-ticket-type context
    (ml/anomaly_model.py). Evaluation against planted anomalies:
    reports/anomaly_report.json.
    """
    import json
    import os
    import pandas as pd
    from ml.anomaly_model import CONTAMINATION, build_features, score

    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
        ).all()
        if len(tickets) < 50:
            return {"upload_id": upload_id, "total_tickets": len(tickets), "total_anomalies": 0, "anomalies": [],
                    "message": "Too few tickets for anomaly detection"}

        df = pd.DataFrame([{
            "mttr_hours": t.mttr_hours, "reassignment_count": t.reassignment_count or 0,
            "reopen_count": t.reopen_count or 0, "opened": t.opened,
            "priority_level": normalize_priority(t.priority),
            "group": t.l2_subcategory or t.subcategory or t.category,
        } for t in tickets])
        features = build_features(df)
        scored = score(features)

        flagged = scored[scored["is_anomaly"]].sort_values("anomaly_score", ascending=False)
        # Severity by rank within the flagged set: top third Critical, then High, then Medium
        n = len(flagged)
        severity = ["Critical" if i < n / 3 else "High" if i < 2 * n / 3 else "Medium" for i in range(n)]

        anomalies = []
        for (i, row), sev in zip(flagged.iterrows(), severity):
            t = tickets[i]
            anomalies.append({
                "ticket_id": t.ticket_number or f"TKT-{t.id}",
                "short_description": (t.short_description or "")[:120],
                "score": round(float(row.anomaly_score), 2),
                "severity": sev,
                "reasons": row.reasons,
                "mttr_hours": round(t.mttr_hours, 1) if t.mttr_hours else None,
                "priority": normalize_priority(t.priority),
                "assignment_group": t.assignment_group,
                "category": t.l2_subcategory or t.l1_category or t.category,
                "reassignment_count": t.reassignment_count or 0,
                "reopen_count": t.reopen_count or 0,
                "cluster_id": t.cluster_id,
            })
        severity_counts = Counter(a["severity"] for a in anomalies)

        # Histograms: anomaly score of every ticket, and resolution time
        score_bins = pd.cut(scored["anomaly_score"], bins=[i / 10 for i in range(11)], include_lowest=True)
        threshold = flagged["anomaly_score"].min() if n else 1.0
        score_histogram = [{"range": f"{iv.left:.1f}", "count": int(c), "is_anomalous": bool(iv.right > threshold)}
                           for iv, c in score_bins.value_counts(sort=False).items()]
        mttr = pd.to_numeric(df["mttr_hours"], errors="coerce").dropna()
        edges = sorted(set([0, 1, 4, 8, 24, 48, 96, 168, max(169, float(mttr.max()) + 1)]))
        mttr_bins = pd.cut(mttr, bins=edges, include_lowest=True)
        flagged_mttr = pd.to_numeric(df.loc[flagged.index, "mttr_hours"], errors="coerce")
        mttr_histogram = [{"range": f"{int(iv.left)}-{int(iv.right)}h", "count": int(c),
                           "is_anomalous": bool(((flagged_mttr > iv.left) & (flagged_mttr <= iv.right)).any())}
                          for iv, c in mttr_bins.value_counts(sort=False).items()]

        evaluation = None
        if os.path.exists("reports/anomaly_report.json"):
            with open("reports/anomaly_report.json", encoding="utf-8") as f:
                evaluation = json.load(f)

        return {
            "upload_id": upload_id,
            "method": "IsolationForest on per-ticket-type features",
            "contamination": CONTAMINATION,
            "total_tickets": len(tickets),
            "total_anomalies": n,
            "mean_mttr": round(float(mttr.mean()), 2) if len(mttr) else 0,
            "std_mttr": round(float(mttr.std()), 2) if len(mttr) > 1 else 0,
            "severity_distribution": {
                "critical": severity_counts.get("Critical", 0),
                "high": severity_counts.get("High", 0),
                "medium": severity_counts.get("Medium", 0),
                "low": 0,
            },
            "confidence_histogram": score_histogram,
            "mttr_histogram": mttr_histogram,
            "anomalies": anomalies[:limit],
            "evaluation": evaluation,
        }
    finally:
        db.close()


@router.get("/{upload_id}/volume-forecast")
async def get_volume_forecast(
    upload_id: int,
    days: int = 30,
    user: dict = Depends(require_upload_access),
):
    """
    Daily volume forecast. Candidate models (seasonal naive, weekday mean,
    ridge on lags, LSTM) are compared in a rolling-origin backtest; the
    simplest model within 3% of the best MAE is used, with 80% intervals from
    its backtest errors (ml/forecast_model.py).
    """
    from ml.forecast_model import daily_series, forecast as run_forecast

    db = SessionLocal()
    try:
        opened = [row[0] for row in db.query(Ticket.opened).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.opened != None,
        ).all()]
        if not opened:
            return {"upload_id": upload_id, "message": "No ticket dates available for forecasting",
                    "historical": [], "forecast": []}

        series = daily_series(opened)
        if len(series) < 70:
            return {"upload_id": upload_id, "data_points": len(series),
                    "message": "At least 10 weeks of history are needed for a backtested forecast",
                    "historical": [{"date": d.strftime("%Y-%m-%d"), "volume": int(v)} for d, v in series.items()],
                    "forecast": []}

        result = run_forecast(series, days)
        historical = [{"date": d.strftime("%Y-%m-%d"), "volume": int(v)} for d, v in series.items()]
        forecast = [{
            "date": f["date"],
            "predicted_volume": f["predicted"],
            "confidence_lower": f["lower"],
            "confidence_upper": f["upper"],
            "day_of_week": datetime.strptime(f["date"], "%Y-%m-%d").strftime("%A"),
        } for f in result["forecast"]]

        recent = series.iloc[-30:].to_numpy()
        slope = float(np.polyfit(np.arange(len(recent)), recent, 1)[0]) if len(recent) > 1 else 0.0

        # Hourly pattern (for intraday view)
        hourly_counts = db.query(
            extract("hour", Ticket.opened).label("hour"),
            func.count(Ticket.id).label("count"),
        ).filter(
            Ticket.upload_id == upload_id,
            Ticket.team_id == user["team_id"],
            Ticket.opened != None,
        ).group_by(
            extract("hour", Ticket.opened)
        ).order_by(
            asc(extract("hour", Ticket.opened))
        ).all()

        hourly_pattern = [
            {"hour": int(row.hour), "avg_volume": round(row.count / max(len(series), 1), 1)}
            for row in hourly_counts
        ]

        forecast_volumes = [f["predicted_volume"] for f in forecast]
        peak_day = max(forecast, key=lambda x: x["predicted_volume"]) if forecast else None

        return {
            "upload_id": upload_id,
            "data_points": len(series),
            "date_range": {"start": historical[0]["date"], "end": historical[-1]["date"]},
            "model": {
                "selected": result["model"],
                "lowest_mae": result["lowest_mae_model"],
                "selection_rule": f"simplest model within {result['parsimony_tolerance']:.0%} of the best backtest MAE",
                "backtest": result["backtest"],
                "backtest_origins": result["origins"],
                "horizon_days": result["horizon"],
                "interval": "80% (10th-90th percentile of backtest errors)",
            },
            "statistics": {
                "overall_avg": round(float(series.mean()), 1),
                "overall_std": round(float(series.std()), 1),
                "trend_slope": round(slope, 3),
                "trend_direction": "increasing" if slope > 0.5 else "decreasing" if slope < -0.5 else "stable",
            },
            "historical": historical[-60:],
            "forecast": forecast,
            "hourly_pattern": hourly_pattern,
            "summary": {
                "avg_daily_forecast": round(sum(forecast_volumes) / max(len(forecast_volumes), 1), 1),
                "peak_day": peak_day["date"] if peak_day else None,
                "peak_volume": peak_day["predicted_volume"] if peak_day else None,
            },
        }
    finally:
        db.close()
