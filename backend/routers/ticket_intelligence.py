"""
routers/ticket_intelligence.py (v2)
=====================================
API endpoints for Ticket Intelligence tab.

Changes from v1:
  - Dynamic taxonomy from DB (not hardcoded lists)
  - New filters: channel, priority, assignment_group, resolved_by, mttr_range, solution_lever
  - New response fields: channel, resolved_by, reassignment_count, aio_detail, evidence, cluster_count, est_savings
  - Counts in taxonomy for dropdown display
  - Better stats with FCR%, SLA breach, estimated savings
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import func, distinct, case, and_, or_, text
from typing import Optional, List
from datetime import datetime
import io
import csv
import json

from models import SessionLocal, Ticket, Upload, TrainingData
from dependencies import get_current_user, require_upload_access
from utils import automation_savings, months_covered, ticket_effort_saving_inr

router = APIRouter()


# ============================================================
# HELPER: Get DB session
# ============================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ============================================================
# 1. DYNAMIC TAXONOMY (from actual DB data, not hardcoded)
# ============================================================

@router.get("/api/ticket-intelligence/taxonomy/{upload_id}")
def get_taxonomy(upload_id: int, user: dict = Depends(require_upload_access)):
    """
    Return actual distinct values + counts from DB.
    Dropdowns show: "Server (31,205)" not just "Server"
    """
    db = SessionLocal()
    try:
        base = db.query(Ticket).filter(Ticket.upload_id == upload_id)

        def get_distinct_with_counts(column):
            """Get distinct values with their counts, sorted by count desc."""
            results = (
                db.query(column, func.count(Ticket.id))
                .filter(Ticket.upload_id == upload_id)
                .filter(column.isnot(None), column != '')
                .group_by(column)
                .order_by(func.count(Ticket.id).desc())
                .all()
            )
            return [{"value": r[0], "count": r[1]} for r in results if r[0]]

        return {
            "towers": get_distinct_with_counts(Ticket.aio_tower),
            "categories": get_distinct_with_counts(Ticket.aio_category),
            "subcategories": get_distinct_with_counts(Ticket.aio_subcategory),
            "details": get_distinct_with_counts(Ticket.aio_detail),
            "channels": get_distinct_with_counts(Ticket.channel),
            "priorities": get_distinct_with_counts(Ticket.priority),
            "assignment_groups": get_distinct_with_counts(Ticket.assignment_group),
            "resolved_by": [
                {"value": r[0], "count": r[1]} for r in
                db.query(Ticket.resolved_by, func.count(Ticket.id))
                .filter(Ticket.upload_id == upload_id)
                .filter(Ticket.resolved_by.isnot(None), Ticket.resolved_by != '')
                .group_by(Ticket.resolved_by)
                .order_by(func.count(Ticket.id).desc())
                .limit(50)
                .all()
            ],
            "automation_statuses": get_distinct_with_counts(Ticket.aiops_automation_status),
            "solution_levers": get_distinct_with_counts(Ticket.aiops_solution_lever),
        }
    finally:
        db.close()


# ============================================================
# 2. STATS (enhanced with FCR%, SLA breach, savings)
# ============================================================

@router.get("/api/ticket-intelligence/{upload_id}/stats")
def get_stats(upload_id: int, user: dict = Depends(require_upload_access)):
    """Enhanced stats with business metrics."""
    db = SessionLocal()
    try:
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        if not upload:
            raise HTTPException(404, "Upload not found")

        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id)
        total = tickets.count()
        if total == 0:
            raise HTTPException(404, "No tickets")

        already = tickets.filter(Ticket.is_already_automated == True).count()
        can_be = tickets.filter(Ticket.can_be_automated == True, Ticket.is_already_automated == False).count()
        manual = total - already - can_be

        # MTTR: the shared definition (services/metrics.py), so this tab matches the dashboard.
        # A 720-hour cap here once dropped long tickets and showed 20.21 h against 21.99 h.
        from services.metrics import mttr_by_status
        avg_mttr = mttr_by_status(db, upload_id, user["team_id"])["overall"]["avg_hours"] or 0

        # First Contact Resolution (0 reassignments)
        fcr_count = tickets.filter(Ticket.reassignment_count == 0).count()
        fcr_pct = round(fcr_count / total * 100, 1) if total > 0 else 0

        # SLA breach estimate (P1 > 4h, P2 > 8h, P3 > 24h, P4 > 48h)
        sla_breach = 0
        for priority, threshold in [('1', 4), ('2', 8), ('3', 24), ('4', 48)]:
            breach = tickets.filter(
                Ticket.priority.contains(priority),
                Ticket.mttr_hours > threshold
            ).count()
            sla_breach += breach
        sla_breach_pct = round(sla_breach / total * 100, 1) if total > 0 else 0

        # Estimated annual savings (same rule as the ROI view: analyst effort removed per ticket)
        first_opened, last_opened = db.query(func.min(Ticket.opened), func.max(Ticket.opened))             .filter(Ticket.upload_id == upload_id).one()
        annual_savings = automation_savings(can_be, months_covered(first_opened, last_opened))["annual_savings_inr"]

        # AIO confidence
        avg_confidence = db.query(func.avg(Ticket.aio_confidence)).filter(
            Ticket.upload_id == upload_id, Ticket.aio_confidence.isnot(None)
        ).scalar() or 0

        # Needs review count
        needs_review = tickets.filter(Ticket.aio_needs_review == True).count()

        # Tower distribution (for mini chart)
        tower_dist = (
            db.query(Ticket.aio_tower, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.aio_tower.isnot(None))
            .group_by(Ticket.aio_tower)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        # Channel distribution (for mini chart)
        channel_dist = (
            db.query(Ticket.channel, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.channel.isnot(None), Ticket.channel != '')
            .group_by(Ticket.channel)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        # Priority distribution
        priority_dist = (
            db.query(Ticket.priority, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.priority.isnot(None))
            .group_by(Ticket.priority)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        # Solution lever distribution
        lever_dist = (
            db.query(Ticket.aiops_solution_lever, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.aiops_solution_lever.isnot(None), Ticket.aiops_solution_lever != '')
            .group_by(Ticket.aiops_solution_lever)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        # Top 10 subcategories
        top_subcats = (
            db.query(Ticket.aio_subcategory, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.aio_subcategory.isnot(None), Ticket.aio_subcategory != '')
            .group_by(Ticket.aio_subcategory)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        return {
            "upload_id": upload_id,
            "filename": upload.filename,
            "record_type": upload.record_type or "incident",
            "total_tickets": total,
            "already_automated": already,
            "already_automated_pct": round(already / total * 100, 1),
            "can_be_automated": can_be,
            "can_be_automated_pct": round(can_be / total * 100, 1),
            "manual": manual,
            "manual_pct": round(manual / total * 100, 1),
            "avg_mttr_hours": round(float(avg_mttr), 2),
            "fcr_pct": fcr_pct,
            "sla_breach_pct": sla_breach_pct,
            "estimated_annual_savings": annual_savings,
            "needs_review": needs_review,
            "avg_aio_confidence": round(float(avg_confidence) * 100, 1) if avg_confidence else 0,
            "tower_distribution": [{"name": r[0], "count": r[1]} for r in tower_dist],
            "channel_distribution": [{"name": r[0] or "Unknown", "count": r[1]} for r in channel_dist],
            "priority_distribution": [{"name": r[0], "count": r[1]} for r in priority_dist],
            "lever_distribution": [{"name": r[0], "count": r[1]} for r in lever_dist],
            "top_subcategories": [{"name": r[0], "count": r[1]} for r in top_subcats],
        }
    finally:
        db.close()


# ============================================================
# 3. DATA TABLE (enhanced with all new columns and filters)
# ============================================================

@router.get("/api/ticket-intelligence/{upload_id}/table")
def get_table(
    upload_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=10, le=200),
    search: Optional[str] = None,
    aio_tower: Optional[str] = None,
    aio_category: Optional[str] = None,
    aio_subcategory: Optional[str] = None,
    needs_review: Optional[bool] = None,
    automation_status: Optional[str] = None,
    channel: Optional[str] = None,
    priority: Optional[str] = None,
    assignment_group: Optional[str] = None,
    resolved_by: Optional[str] = None,
    solution_lever: Optional[str] = None,
    mttr_min: Optional[float] = None,
    mttr_max: Optional[float] = None,
    sort_by: Optional[str] = "ticket_number",
    sort_dir: Optional[str] = "asc",
    user: dict = Depends(require_upload_access),
):
    """Enhanced data table with all filters and new columns."""
    db = SessionLocal()
    try:
        q = db.query(Ticket).filter(Ticket.upload_id == upload_id)

        # --- Filters ---
        if search:
            search_term = f"%{search}%"
            q = q.filter(or_(
                Ticket.short_description.ilike(search_term),
                Ticket.ticket_number.ilike(search_term),
                Ticket.aio_subcategory.ilike(search_term),
                Ticket.aio_detail.ilike(search_term),
                Ticket.assignment_group.ilike(search_term),
                Ticket.resolved_by.ilike(search_term),
            ))

        if aio_tower:
            q = q.filter(Ticket.aio_tower == aio_tower)
        if aio_category:
            q = q.filter(Ticket.aio_category == aio_category)
        if aio_subcategory:
            q = q.filter(Ticket.aio_subcategory == aio_subcategory)
        if needs_review is not None:
            q = q.filter(Ticket.aio_needs_review == needs_review)
        if channel:
            q = q.filter(Ticket.channel == channel)
        if priority:
            q = q.filter(Ticket.priority.contains(priority))
        if assignment_group:
            q = q.filter(Ticket.assignment_group == assignment_group)
        if resolved_by:
            q = q.filter(Ticket.resolved_by == resolved_by)
        if solution_lever:
            q = q.filter(Ticket.aiops_solution_lever == solution_lever)
        if mttr_min is not None:
            q = q.filter(Ticket.mttr_hours >= mttr_min)
        if mttr_max is not None:
            q = q.filter(Ticket.mttr_hours <= mttr_max)

        if automation_status:
            if automation_status == 'Already Automated':
                q = q.filter(Ticket.is_already_automated == True)
            elif automation_status == 'Can Be Automated':
                q = q.filter(Ticket.can_be_automated == True, Ticket.is_already_automated == False)
            elif automation_status in ['Manual', 'Manual Only']:
                q = q.filter(Ticket.is_already_automated == False, Ticket.can_be_automated == False)

        # --- Count ---
        total = q.count()

        # --- Sort ---
        sort_column = getattr(Ticket, sort_by, Ticket.ticket_number)
        if sort_dir == "desc":
            q = q.order_by(sort_column.desc())
        else:
            q = q.order_by(sort_column.asc())

        # --- Paginate ---
        offset = (page - 1) * page_size
        rows = q.offset(offset).limit(page_size).all()

        # --- Build cluster count cache ---
        cluster_ids = list(set(r.cluster_id for r in rows if r.cluster_id is not None))
        cluster_counts = {}
        if cluster_ids:
            counts = (
                db.query(Ticket.cluster_id, func.count(Ticket.id))
                .filter(Ticket.upload_id == upload_id, Ticket.cluster_id.in_(cluster_ids))
                .group_by(Ticket.cluster_id).all()
            )
            cluster_counts = {c[0]: c[1] for c in counts}

        # --- Build evidence and format rows ---
        from services.aio_classifier import build_evidence_line, build_meaningful_action

        result_rows = []
        for r in rows:
            # Evidence line
            evidence = build_evidence_line(r)

            # Meaningful action
            action = build_meaningful_action(
                r.aiops_automation_status or 'Manual',
                r.aiops_solution_lever or '',
                r.resolved_by or '',
                r.assignment_group or '',
                r.aio_subcategory or '',
                r.short_description or '',
            )

            # Estimated savings
            est_savings = ticket_effort_saving_inr(bool(r.can_be_automated) and not r.is_already_automated)

            # Automation status display
            if r.is_already_automated:
                auto_status = 'Already Automated'
            elif r.can_be_automated:
                auto_status = 'Can Be Automated'
            else:
                auto_status = 'Manual'

            # Cluster count
            cluster_count = cluster_counts.get(r.cluster_id, 0) if r.cluster_id else 0

            result_rows.append({
                "id": r.id,
                "ticket_number": r.ticket_number,
                "short_description": r.short_description or '',
                "channel": r.channel or '',
                "assignment_group": r.assignment_group or '',
                "resolved_by": r.resolved_by or '',
                "priority": r.priority or '',
                "mttr_hours": round(r.mttr_hours, 2) if r.mttr_hours else None,
                "reassignment_count": r.reassignment_count or 0,
                "reopen_count": r.reopen_count or 0,
                # AIO columns
                "aio_tower": r.aio_tower or '',
                "aio_category": r.aio_category or '',
                "aio_subcategory": r.aio_subcategory or '',
                "aio_detail": r.aio_detail or '',
                "aio_summary": r.aio_summary or '',
                "aio_confidence": round(r.aio_confidence * 100, 1) if r.aio_confidence else 0,
                "aio_classified_by": r.aio_classified_by or '',
                "aio_needs_review": r.aio_needs_review or False,
                # Automation
                "automation_status": auto_status,
                "action": action,
                "solution_lever": r.aiops_solution_lever or '',
                # New columns
                "evidence": evidence,
                "cluster_id": r.cluster_id,
                "cluster_count": cluster_count,
                "est_savings": est_savings,
                # Original SN fields (for detail modal)
                "category": r.category or '',
                "subcategory": r.subcategory or '',
                "state": r.state or '',
                "caller_id": r.caller_id or '',
            })

        return {
            "rows": result_rows,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    finally:
        db.close()


# ============================================================
# 4. TICKET DETAIL (for modal — full ticket data + ML intel)
# ============================================================

@router.get("/api/ticket-intelligence/ticket/{ticket_id}")
def get_ticket_detail(ticket_id: int, user: dict = Depends(get_current_user)):
    """Full ticket detail for the detail modal."""
    db = SessionLocal()
    try:
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(404, "Ticket not found")

        # Get cluster info
        cluster_info = None
        similar_tickets = []
        if ticket.cluster_id is not None:
            cluster_count = db.query(func.count(Ticket.id)).filter(
                Ticket.upload_id == ticket.upload_id,
                Ticket.cluster_id == ticket.cluster_id
            ).scalar()

            # Automation % in cluster
            cluster_auto = db.query(func.count(Ticket.id)).filter(
                Ticket.upload_id == ticket.upload_id,
                Ticket.cluster_id == ticket.cluster_id,
                or_(Ticket.is_already_automated == True, Ticket.can_be_automated == True)
            ).scalar()

            # Avg MTTR in cluster
            cluster_mttr = db.query(func.avg(Ticket.mttr_hours)).filter(
                Ticket.upload_id == ticket.upload_id,
                Ticket.cluster_id == ticket.cluster_id,
                Ticket.mttr_hours.isnot(None), Ticket.mttr_hours > 0
            ).scalar()

            cluster_new_auto = db.query(func.count(Ticket.id)).filter(
                Ticket.upload_id == ticket.upload_id,
                Ticket.cluster_id == ticket.cluster_id,
                Ticket.can_be_automated == True, Ticket.is_already_automated == False
            ).scalar()

            cluster_info = {
                "cluster_id": ticket.cluster_id,
                "can_automate": cluster_new_auto,
                "total_tickets": cluster_count,
                "automation_pct": round(cluster_auto / max(cluster_count, 1) * 100, 1),
                "avg_mttr": round(float(cluster_mttr or 0), 2),
            }

            # Similar tickets (same cluster, limit 5)
            similar = (
                db.query(Ticket)
                .filter(
                    Ticket.upload_id == ticket.upload_id,
                    Ticket.cluster_id == ticket.cluster_id,
                    Ticket.id != ticket.id
                )
                .limit(5).all()
            )
            similar_tickets = [{
                "ticket_number": s.ticket_number,
                "short_description": (s.short_description or '')[:80],
                "mttr_hours": round(s.mttr_hours, 2) if s.mttr_hours else None,
                "automation_status": "Already Automated" if s.is_already_automated else (
                    "Can Be Automated" if s.can_be_automated else "Manual"
                ),
            } for s in similar]

        # Build evidence chain
        from services.aio_classifier import build_evidence_line, build_meaningful_action
        evidence = build_evidence_line(ticket)
        action = build_meaningful_action(
            ticket.aiops_automation_status or 'Manual',
            ticket.aiops_solution_lever or '',
            ticket.resolved_by or '',
            ticket.assignment_group or '',
            ticket.aio_subcategory or '',
            ticket.short_description or '',
        )

        # Effort saving (analyst time removed, not calendar duration); see utils.automation_savings
        ticket_savings = ticket_effort_saving_inr(bool(ticket.can_be_automated) and not ticket.is_already_automated)
        cluster_savings = 0
        if cluster_info and ticket.can_be_automated:
            cluster_savings = round(cluster_info.get('can_automate', 0) * ticket_effort_saving_inr(True), 0)

        return {
            # Identity
            "id": ticket.id,
            "ticket_number": ticket.ticket_number,
            "record_type": ticket.record_type or 'incident',

            # Description
            "short_description": ticket.short_description or '',
            "description": ticket.description or '',
            "resolution_notes": ticket.resolution_notes or '',
            "close_notes": ticket.close_notes or '',
            "work_notes": (ticket.work_notes or '')[:2000],

            # Routing
            "channel": ticket.channel or '',
            "category": ticket.category or '',
            "subcategory": ticket.subcategory or '',
            "assignment_group": ticket.assignment_group or '',
            "assigned_to": ticket.assigned_to or '',
            "resolved_by": ticket.resolved_by or '',
            "resolved_by_group": ticket.resolved_by_group or '',
            "priority": ticket.priority or '',
            "state": ticket.state or '',
            "caller_id": ticket.caller_id or '',

            # Timing
            "opened": ticket.opened.isoformat() if ticket.opened else None,
            "resolved": ticket.resolved.isoformat() if ticket.resolved else None,
            "closed": ticket.closed.isoformat() if ticket.closed else None,
            "mttr_hours": round(ticket.mttr_hours, 2) if ticket.mttr_hours else None,
            "business_duration": round(ticket.business_duration, 2) if ticket.business_duration else None,

            # Complexity
            "reassignment_count": ticket.reassignment_count or 0,
            "reopen_count": ticket.reopen_count or 0,

            # Infrastructure
            "configuration_item": ticket.configuration_item or '',
            "location": ticket.location or '',
            "company": ticket.company or '',
            "business_unit": ticket.business_unit or '',

            # AIO Classification
            "aio_tower": ticket.aio_tower or '',
            "aio_category": ticket.aio_category or '',
            "aio_subcategory": ticket.aio_subcategory or '',
            "aio_detail": ticket.aio_detail or '',
            "aio_summary": ticket.aio_summary or '',
            "aio_confidence": round(ticket.aio_confidence * 100, 1) if ticket.aio_confidence else 0,
            "aio_classified_by": ticket.aio_classified_by or '',

            # Automation
            "automation_status": "Already Automated" if ticket.is_already_automated else (
                "Can Be Automated" if ticket.can_be_automated else "Manual"
            ),
            "automation_score": ticket.automation_potential_score or 0,
            "solution_lever": ticket.aiops_solution_lever or '',
            "action": action,
            "evidence": evidence,
            "reasoning": ticket.aiops_additional_info or '',

            # ML Intelligence
            "cluster_info": cluster_info,
            "similar_tickets": similar_tickets,

            # Value
            "ticket_savings": ticket_savings,
            "cluster_savings": cluster_savings,

            # Human override
            "human_override": ticket.human_override or '',
        }
    finally:
        db.close()


# ============================================================
# 5. OVERRIDE (human correction)
# ============================================================

@router.post("/api/ticket-intelligence/override")
def override_classification(
    data: dict,
    user: dict = Depends(get_current_user),
):
    """Human correction — override any AIO field."""
    db = SessionLocal()
    try:
        ticket_id = data.get("ticket_id")
        ticket = db.query(Ticket).filter(Ticket.id == ticket_id).first()
        if not ticket:
            raise HTTPException(404, "Ticket not found")

        # Update overridable fields
        field = data.get("field")
        value = data.get("value")

        if field == "aio_tower":
            ticket.aio_tower = value
        elif field == "aio_category":
            ticket.aio_category = value
        elif field == "aio_subcategory":
            ticket.aio_subcategory = value
        elif field == "aio_detail":
            ticket.aio_detail = value
        elif field == "aio_summary":
            ticket.aio_summary = value
        elif field == "automation_status":
            ticket.human_override = value
            ticket.label_source = "ticket_view"
            if value == 'Already Automated':
                ticket.is_already_automated = True
                ticket.can_be_automated = False
            elif value == 'Can Be Automated':
                ticket.is_already_automated = False
                ticket.can_be_automated = True
            elif value == 'Manual':
                ticket.is_already_automated = False
                ticket.can_be_automated = False
            ticket.aiops_automation_status = value
        elif field == "action":
            ticket.aiops_solution_lever = value

        # Mark as human classified
        ticket.aio_classified_by = "human"
        ticket.aio_confidence = 1.0
        ticket.aio_needs_review = False

        # Save to training data
        existing = db.query(TrainingData).filter(
            TrainingData.upload_id == ticket.upload_id,
            TrainingData.short_description == ticket.short_description
        ).first()

        if existing:
            existing.aio_tower = ticket.aio_tower
            existing.aio_category = ticket.aio_category
            existing.aio_subcategory = ticket.aio_subcategory
            existing.is_verified = True
            existing.label_source = "human"
        else:
            td = TrainingData(
                upload_id=ticket.upload_id,
                short_description=ticket.short_description,
                category=ticket.category,
                assignment_group=ticket.assignment_group,
                channel=ticket.channel,
                mttr_hours=ticket.mttr_hours,
                reassignment_count=ticket.reassignment_count,
                resolved_by=ticket.resolved_by,
                aio_tower=ticket.aio_tower,
                aio_category=ticket.aio_category,
                aio_subcategory=ticket.aio_subcategory,
                aiops_automation_status=ticket.aiops_automation_status,
                aiops_solution_lever=ticket.aiops_solution_lever,
                label_source="human",
                is_verified=True,
            )
            db.add(td)

        db.commit()
        return {"status": "ok", "ticket_id": ticket_id, "field": field, "value": value}
    finally:
        db.close()


# ============================================================
# 6. PIVOTS
# ============================================================

@router.get("/api/ticket-intelligence/{upload_id}/pivots")
def get_pivots(upload_id: int, user: dict = Depends(require_upload_access)):
    """Generate auto-pivot data."""
    db = SessionLocal()
    try:
        from services.pivot_generator import generate_all_pivots
        return generate_all_pivots(upload_id, db)
    except Exception as e:
        return []
    finally:
        db.close()


@router.post("/api/ticket-intelligence/{upload_id}/custom-pivot")
def custom_pivot(upload_id: int, data: dict, user: dict = Depends(require_upload_access)):
    """Custom pivot builder."""
    db = SessionLocal()
    try:
        from services.pivot_generator import generate_custom_pivot
        return generate_custom_pivot(upload_id, data, db)
    except Exception as e:
        raise HTTPException(400, str(e))
    finally:
        db.close()


# ============================================================
# 7. EXPORTS (CSV, Excel, PPT)
# ============================================================

@router.get("/api/ticket-intelligence/{upload_id}/export/csv")
def export_csv(upload_id: int, user: dict = Depends(require_upload_access)):
    """Export enriched CSV with all AIO columns."""
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        if not tickets:
            raise HTTPException(404, "No tickets")

        from services.aio_classifier import build_evidence_line, build_meaningful_action

        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            'Ticket#', 'Short Description', 'Channel', 'Assignment Group',
            'Resolved By', 'Priority', 'MTTR(h)', 'Reassignments',
            'Tower', 'Category', 'Sub Category', 'Sub Category 1',
            'Summary', 'Automation Status', 'Action', 'Evidence',
            'Confidence', 'Classified By', 'Cluster ID',
            'SN Category', 'SN SubCategory',
        ]
        writer.writerow(headers)

        for t in tickets:
            auto_status = 'Already Automated' if t.is_already_automated else (
                'Can Be Automated' if t.can_be_automated else 'Manual'
            )
            action = build_meaningful_action(
                t.aiops_automation_status or 'Manual', t.aiops_solution_lever or '',
                t.resolved_by or '', t.assignment_group or '',
                t.aio_subcategory or '', t.short_description or ''
            )
            evidence = build_evidence_line(t)

            writer.writerow([
                t.ticket_number, t.short_description, t.channel, t.assignment_group,
                t.resolved_by, t.priority, round(t.mttr_hours, 2) if t.mttr_hours else '',
                t.reassignment_count,
                t.aio_tower, t.aio_category, t.aio_subcategory, t.aio_detail,
                t.aio_summary, auto_status, action, evidence,
                round(t.aio_confidence * 100, 1) if t.aio_confidence else '',
                t.aio_classified_by, t.cluster_id,
                t.category, t.subcategory,
            ])

        output.seek(0)
        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        filename = f"TicketIntelligence_{upload.filename if upload else upload_id}.csv"

        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8-sig')),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        db.close()


@router.get("/api/ticket-intelligence/{upload_id}/export/excel")
def export_excel(upload_id: int, user: dict = Depends(require_upload_access)):
    """Export multi-sheet Excel workbook."""
    db = SessionLocal()
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

        tickets = db.query(Ticket).filter(Ticket.upload_id == upload_id).all()
        if not tickets:
            raise HTTPException(404, "No tickets")

        from services.aio_classifier import build_evidence_line, build_meaningful_action

        wb = Workbook()
        ws = wb.active
        ws.title = "Enriched Data"

        # Header style
        header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=10)

        headers = [
            'Ticket#', 'Description', 'Channel', 'Assignment Group',
            'Resolved By', 'Priority', 'MTTR(h)', 'Reassignments',
            'Tower', 'Category', 'Sub Category', 'Sub Category 1',
            'Summary', 'Automation Status', 'Action', 'Evidence',
            'Confidence', 'Classified By',
        ]

        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col, value=header)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center')

        # Auto status colors
        status_fills = {
            'Already Automated': PatternFill(start_color="D5F5E3", fill_type="solid"),
            'Can Be Automated': PatternFill(start_color="D6EAF8", fill_type="solid"),
            'Manual': PatternFill(start_color="FADBD8", fill_type="solid"),
        }

        for row_idx, t in enumerate(tickets, 2):
            auto_status = 'Already Automated' if t.is_already_automated else (
                'Can Be Automated' if t.can_be_automated else 'Manual'
            )
            action = build_meaningful_action(
                t.aiops_automation_status or 'Manual', t.aiops_solution_lever or '',
                t.resolved_by or '', t.assignment_group or '',
                t.aio_subcategory or '', t.short_description or ''
            )

            values = [
                t.ticket_number, (t.short_description or '')[:100], t.channel,
                t.assignment_group, t.resolved_by, t.priority,
                round(t.mttr_hours, 2) if t.mttr_hours else None,
                t.reassignment_count, t.aio_tower, t.aio_category,
                t.aio_subcategory, t.aio_detail, t.aio_summary,
                auto_status, action, build_evidence_line(t),
                round(t.aio_confidence * 100, 1) if t.aio_confidence else None,
                t.aio_classified_by,
            ]

            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row_idx, column=col, value=val)

            # Color the automation status cell
            status_cell = ws.cell(row=row_idx, column=14)
            if auto_status in status_fills:
                status_cell.fill = status_fills[auto_status]

        # Auto-width
        for col in ws.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            ws.column_dimensions[col[0].column_letter].width = min(max_len + 2, 40)

        # Freeze header
        ws.freeze_panes = 'A2'
        ws.auto_filter.ref = ws.dimensions

        # Save
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        filename = f"TicketIntelligence_{upload.filename if upload else upload_id}.xlsx"

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        db.close()


@router.post("/api/ticket-intelligence/{upload_id}/export/ppt")
def export_ppt(upload_id: int, data: dict, user: dict = Depends(require_upload_access)):
    """Generate PowerPoint presentation."""
    db = SessionLocal()
    try:
        from services.ppt_generator import generate_ppt

        stats = get_stats(upload_id, user)
        from services.pivot_generator import generate_all_pivots
        pivots = generate_all_pivots(upload_id, db)
        
        buffer = generate_ppt(
            stats=stats,
            pivots=pivots,
            slides=data.get('slides', ['title', 'exec_summary', 'tower_split', 'automation_overview']),
            client_name=data.get('client_name', 'Client'),
            date_str=data.get('date_str', datetime.now().strftime('%B %Y')),
        )

        upload = db.query(Upload).filter(Upload.id == upload_id).first()
        filename = f"AIO_Report_{data.get('client_name', 'Client')}.pptx"

        return StreamingResponse(
            buffer,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    finally:
        db.close()


# ============================================================
# 8. TOP 10 WIDGETS
# ============================================================

@router.get("/api/ticket-intelligence/{upload_id}/top10")
def get_top10(upload_id: int, user: dict = Depends(require_upload_access)):
    """Top 10 widgets for quick insights."""
    db = SessionLocal()
    try:
        # Top 10 SubCategories by volume
        top_subcats = (
            db.query(Ticket.aio_subcategory, func.count(Ticket.id).label('count'))
            .filter(Ticket.upload_id == upload_id, Ticket.aio_subcategory.isnot(None), Ticket.aio_subcategory != '')
            .group_by(Ticket.aio_subcategory)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        # Top 10 Assignment Groups by volume
        top_groups = (
            db.query(Ticket.assignment_group, func.count(Ticket.id).label('count'))
            .filter(Ticket.upload_id == upload_id, Ticket.assignment_group.isnot(None), Ticket.assignment_group != '')
            .group_by(Ticket.assignment_group)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )

        # Top 10 Quick Wins (highest automation % × volume, min 20 tickets)
        quick_wins_raw = (
            db.query(
                Ticket.aio_subcategory,
                func.count(Ticket.id).label('total'),
                func.sum(case((or_(Ticket.is_already_automated == True, Ticket.can_be_automated == True), 1), else_=0)).label('auto_count'),
                func.sum(case((and_(Ticket.can_be_automated == True, Ticket.is_already_automated == False), 1), else_=0)).label('new_auto'),
                func.avg(Ticket.mttr_hours).label('avg_mttr'),
            )
            .filter(Ticket.upload_id == upload_id, Ticket.aio_subcategory.isnot(None), Ticket.aio_subcategory != '')
            .group_by(Ticket.aio_subcategory)
            .having(func.count(Ticket.id) >= 20)
            .all()
        )

        quick_wins = []
        for row in quick_wins_raw:
            total = row.total
            auto = row.auto_count or 0
            pct = round(auto / max(total, 1) * 100, 1)
            avg_mttr = float(row.avg_mttr or 0)
            est_savings = round((row.new_auto or 0) * ticket_effort_saving_inr(True), 0)
            quick_wins.append({
                "subcategory": row.aio_subcategory,
                "total": total,
                "automatable": auto,
                "automation_pct": pct,
                "avg_mttr": round(avg_mttr, 2),
                "est_savings": est_savings,
            })

        quick_wins.sort(key=lambda x: x['est_savings'], reverse=True)

        return {
            "top_subcategories": [{"name": r[0], "count": r[1]} for r in top_subcats],
            "top_assignment_groups": [{"name": r[0], "count": r[1]} for r in top_groups],
            "quick_wins": quick_wins[:10],
        }
    finally:
        db.close()