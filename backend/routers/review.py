"""
Review queue: analysts label tickets, which (a) measures the automation
classifier's accuracy on this dataset and (b) becomes training data.

Two ways to pick the next ticket:
  random     fixed pseudo-random order per upload; an unbiased sample, the only
             labels used to measure accuracy
  uncertain  least confident first; the daily triage mode (biased towards hard
             tickets, so excluded from the accuracy estimate)
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, text

from dependencies import require_upload_access
from models import SessionLocal, Ticket

router = APIRouter(prefix="/api/review", tags=["Review"])

STATUSES = ["Already Automated", "Can Be Automated", "Manual Only"]
SKIPPED = "Skipped"
MODE_SOURCE = {"random": "random_sample", "uncertain": "uncertainty_queue"}
MIN_LABELS_FOR_ACCURACY = 30

# automation_confidence is stored as text; only numeric values are model confidences
LEAST_CONFIDENT_FIRST = text("CASE WHEN automation_confidence ~ '^[0-9.]+$' THEN automation_confidence::float ELSE 1.0 END ASC")


class LabelRequest(BaseModel):
    ticket_id: int
    label: str
    mode: Literal["random", "uncertain"] = "random"


def wilson_interval(correct: int, n: int, z: float = 1.96):
    """95% confidence interval for a proportion (Wilson score), sensible for small n."""
    if n == 0:
        return None, None
    p = correct / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return round(centre - half, 4), round(centre + half, 4)


def _active_model_cutoff() -> Optional[datetime]:
    """
    When the active model was retrained on analyst labels: its training time in UTC.
    Random-sample labels made before then may be in its training data, so they no
    longer measure it (unless they are in the frozen gold set, which is never trained on).
    """
    from services.automation_scoring import load_automation_model
    bundle = load_automation_model() or {}
    if "analyst labels" not in (bundle.get("training_data") or "") or not bundle.get("trained_at"):
        return None
    local = datetime.fromisoformat(bundle["trained_at"])
    # trained_at is the run's start, cut to whole seconds, and labels are read a moment later:
    # a minute's margin keeps labels from the same moment out of the estimate
    return local.astimezone(timezone.utc).replace(tzinfo=None) + timedelta(minutes=1)   # override_at is naive UTC


def measures_active_model(ticket_id: int, override_at: Optional[datetime], cutoff: Optional[datetime]) -> bool:
    from services.model_lifecycle import _gold_bucket
    return cutoff is None or _gold_bucket(ticket_id) or (override_at is not None and override_at > cutoff)


def _unlabelled(db, upload_id: int):
    return db.query(Ticket).filter(
        Ticket.upload_id == upload_id,
        (Ticket.human_override == None) | (Ticket.human_override == ""),
    )


@router.get("/{upload_id}/next")
def next_ticket(upload_id: int, mode: Literal["random", "uncertain"] = "random",
                user: dict = Depends(require_upload_access)):
    db = SessionLocal()
    try:
        q = _unlabelled(db, upload_id)
        if mode == "random":
            # md5 of the ticket id gives a stable shuffled order: a fair sample that
            # doesn't change between requests or reviewers
            q = q.order_by(func.md5(func.concat(Ticket.id, "-", upload_id)))
        else:
            q = q.order_by(LEAST_CONFIDENT_FIRST, Ticket.id)
        t = q.first()
        if t is None:
            return {"ticket": None}
        return {"ticket": {
            "id": t.id,
            "number": t.ticket_number,
            "short_description": t.short_description,
            "description": t.description,
            "close_notes": t.close_notes or t.resolution_notes,
            "resolved_by": t.resolved_by,
            "assignment_group": t.assignment_group,
            "priority": t.priority,
            "channel": t.channel or t.contact_type,
            "category": t.category,
            "mttr_hours": round(t.mttr_hours, 2) if t.mttr_hours else None,
            "reassignment_count": t.reassignment_count,
            # revealed in the UI only after the analyst answers, to avoid anchoring
            "model": {"status": t.model_status,
                      "confidence": float(t.automation_confidence) if (t.automation_confidence or "").replace(".", "", 1).isdigit() else None},
        }}
    finally:
        db.close()


@router.post("/{upload_id}/label")
def label_ticket(upload_id: int, req: LabelRequest, user: dict = Depends(require_upload_access)):
    if req.label not in STATUSES + [SKIPPED]:
        raise HTTPException(422, f"label must be one of {STATUSES + [SKIPPED]}")
    db = SessionLocal()
    try:
        t = db.query(Ticket).filter(Ticket.id == req.ticket_id, Ticket.upload_id == upload_id).first()
        if t is None:
            raise HTTPException(404, "Ticket not found")
        t.human_override = req.label
        t.override_by = user["user_id"]
        t.override_at = datetime.utcnow()
        t.label_source = MODE_SOURCE[req.mode]
        if req.label != SKIPPED:
            # the analyst's answer is what the dashboard shows from now on
            t.is_already_automated = req.label == "Already Automated"
            t.can_be_automated = req.label == "Can Be Automated"
            t.aiops_automation_status = req.label
        db.commit()
        return {"ok": True}
    finally:
        db.close()


@router.get("/{upload_id}/summary")
def summary(upload_id: int, user: dict = Depends(require_upload_access)):
    db = SessionLocal()
    try:
        rows = db.query(Ticket.id, Ticket.override_at, Ticket.human_override, Ticket.model_status,
                        Ticket.label_source).filter(
            Ticket.upload_id == upload_id, Ticket.human_override != None, Ticket.human_override != "").all()
        total = db.query(func.count(Ticket.id)).filter(Ticket.upload_id == upload_id).scalar() or 0

        labelled = [r for r in rows if r.human_override != SKIPPED]
        random_labels = [r for r in labelled if r.label_source == "random_sample" and r.model_status]
        cutoff = _active_model_cutoff()
        sample = [r for r in random_labels if measures_active_model(r.id, r.override_at, cutoff)]
        correct = sum(r.human_override == r.model_status for r in sample)
        lo, hi = wilson_interval(correct, len(sample))

        per_class = {}
        for s in STATUSES:
            truth = [r for r in sample if r.human_override == s]
            per_class[s] = {"labelled": len(truth),
                            "recall": round(sum(r.model_status == s for r in truth) / len(truth), 4) if truth else None}
        confusion = {a: {p: sum(1 for r in sample if r.human_override == a and r.model_status == p) for p in STATUSES}
                     for a in STATUSES}

        return {
            "upload_id": upload_id,
            "total_tickets": total,
            "labelled": len(labelled),
            "skipped": len(rows) - len(labelled),
            "by_source": {src: sum(1 for r in labelled if r.label_source == src)
                          for src in ("random_sample", "uncertainty_queue", "ticket_view")},
            "label_counts": {s: sum(1 for r in labelled if r.human_override == s) for s in STATUSES},
            "accuracy": {
                "sample_size": len(sample),
                "excluded_seen_in_training": len(random_labels) - len(sample),
                "min_sample": MIN_LABELS_FOR_ACCURACY,
                "accuracy": round(correct / len(sample), 4) if sample else None,
                "ci95": [lo, hi] if sample else None,
                "reportable": len(sample) >= MIN_LABELS_FOR_ACCURACY,
                "per_class": per_class,
                "confusion": confusion,
            },
        }
    finally:
        db.close()
