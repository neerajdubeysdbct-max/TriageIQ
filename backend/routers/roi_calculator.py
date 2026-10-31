"""
ROI Calculator API - provides ticket complexity breakdown for frontend calculator
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import SessionLocal, Ticket
from dependencies import get_current_user, require_upload_access

router = APIRouter(prefix="/api/roi-calculator", tags=["ROI Calculator"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/breakdown")
async def get_breakdown(
    upload_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_upload_access),
):
    """Get ticket complexity breakdown for ROI calculation"""
    tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
    if not tickets:
        return {"breakdown": None, "waste": None, "total_tickets": 0}

    simple = medium = complex_t = automated = 0
    total_reassign = 0
    total_reopen = 0

    for t in tickets:
        ra = t.reassignment_count or 0
        ro = t.reopen_count or 0
        mt = t.mttr_hours or 0
        total_reassign += ra
        total_reopen += ro

        if t.is_already_automated:
            automated += 1
        elif ra >= 2 or ro >= 1 or mt > 48:
            complex_t += 1
        elif ra >= 1 or mt > 8:
            medium += 1
        else:
            simple += 1

    total = len(tickets)
    avg_ra = round(total_reassign / max(total, 1), 2)
    avg_ro = round(total_reopen / max(total, 1), 2)

    # Annualization factor
    first_date = db.query(func.min(Ticket.opened)).filter(
        Ticket.upload_id == upload_id
    ).scalar()
    last_date = db.query(func.max(Ticket.opened)).filter(
        Ticket.upload_id == upload_id
    ).scalar()

    if first_date and last_date and last_date != first_date:
        data_days = max((last_date - first_date).days, 1)
        ann_factor = 365 / data_days
    else:
        ann_factor = 1.0

    return {
        "breakdown": {
            "simple": simple,
            "medium": medium,
            "complex": complex_t,
            "automated": automated,
            "total": total,
        },
        "waste": {
            "avg_reassignments": avg_ra,
            "avg_reopens": avg_ro,
            "total_reassignment_waste": round(total_reassign * 700),
            "total_reopen_waste": round(total_reopen * 900),
        },
        "annualization_factor": round(ann_factor, 2),
        "total_tickets": total,
    }