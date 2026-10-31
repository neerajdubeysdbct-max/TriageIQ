"""
Copilot Export Helper
Generates CSV/Excel exports from copilot queries
"""

import io
import csv
from datetime import datetime
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import SessionLocal
from dependencies import get_current_user, require_upload_access_query_token


router = APIRouter(prefix="/api/copilot/export", tags=["Copilot Export"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


EXPORT_QUERIES = {
    "cluster_summary": {
        "label": "BERT Cluster Summary",
        "sql": """
            SELECT cluster_id as "Cluster ID",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Automation Score",
                   MODE() WITHIN GROUP (ORDER BY assignment_group) as "Top Team",
                   MODE() WITHIN GROUP (ORDER BY aiops_solution_lever) as "Top Solution",
                   MODE() WITHIN GROUP (ORDER BY l2_subcategory) as "Top Category",
                   ROUND(AVG(reassignment_count)::numeric, 2) as "Avg Reassignments",
                   ROUND(AVG(reopen_count)::numeric, 2) as "Avg Reopens"
            FROM tickets
            WHERE upload_id = :uid AND cluster_id IS NOT NULL
            GROUP BY cluster_id
            ORDER BY COUNT(*) DESC
        """,
    },
    "team_performance": {
        "label": "Team Performance",
        "sql": """
            SELECT assignment_group as "Team",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(reassignment_count)::numeric, 2) as "Avg Reassignments",
                   ROUND(AVG(reopen_count)::numeric, 2) as "Avg Reopens",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Automation Score",
                   COUNT(*) FILTER (WHERE can_be_automated = true) as "Automatable Tickets",
                   COUNT(*) FILTER (WHERE is_already_automated = true) as "Already Automated"
            FROM tickets
            WHERE upload_id = :uid AND assignment_group IS NOT NULL
            GROUP BY assignment_group
            ORDER BY COUNT(*) DESC
        """,
    },
    "automation_opportunities": {
        "label": "Automation Opportunities",
        "sql": """
            SELECT aiops_automation_status as "Automation Status",
                   aiops_solution_lever as "Solution Lever",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Score",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(mttr_hours)::numeric * COUNT(*) * 850 / 100000, 2) as "Annual Cost (₹ Lakhs)",
                   MODE() WITHIN GROUP (ORDER BY assignment_group) as "Top Team",
                   MODE() WITHIN GROUP (ORDER BY l2_subcategory) as "Top Category"
            FROM tickets
            WHERE upload_id = :uid AND aiops_automation_status IS NOT NULL
            GROUP BY aiops_automation_status, aiops_solution_lever
            ORDER BY COUNT(*) DESC
        """,
    },
    "sla_risk": {
        "label": "SLA Risk Analysis",
        "sql": """
            SELECT priority as "Priority",
                   COUNT(*) as "Total Tickets",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   COUNT(*) FILTER (WHERE mttr_hours > 
                       CASE priority 
                           WHEN '1 - Critical' THEN 4
                           WHEN '2 - High' THEN 8
                           WHEN '3 - Medium' THEN 24
                           ELSE 48
                       END
                   ) as "SLA Breached",
                   ROUND(
                       COUNT(*) FILTER (WHERE mttr_hours > 
                           CASE priority 
                               WHEN '1 - Critical' THEN 4
                               WHEN '2 - High' THEN 8
                               WHEN '3 - Medium' THEN 24
                               ELSE 48
                           END
                       )::numeric / NULLIF(COUNT(*), 0) * 100, 1
                   ) as "Breach Rate (%)",
                   ROUND(AVG(reassignment_count)::numeric, 2) as "Avg Reassignments"
            FROM tickets
            WHERE upload_id = :uid AND priority IS NOT NULL
            GROUP BY priority
            ORDER BY priority
        """,
    },
    "category_breakdown": {
        "label": "Category Breakdown",
        "sql": """
            SELECT l1_category as "L1 Category",
                   l2_subcategory as "L2 Subcategory",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Automation Score",
                   MODE() WITHIN GROUP (ORDER BY assignment_group) as "Top Team",
                   MODE() WITHIN GROUP (ORDER BY aiops_solution_lever) as "Top Solution"
            FROM tickets
            WHERE upload_id = :uid AND l2_subcategory IS NOT NULL
            GROUP BY l1_category, l2_subcategory
            ORDER BY COUNT(*) DESC
            LIMIT 50
        """,
    },
    "monthly_trend": {
        "label": "Monthly Ticket Trend",
        "sql": """
            SELECT TO_CHAR(opened, 'YYYY-MM') as "Month",
                   COUNT(*) as "Total Tickets",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   COUNT(*) FILTER (WHERE can_be_automated = true) as "Automatable",
                   COUNT(*) FILTER (WHERE is_already_automated = true) as "Already Automated",
                   COUNT(*) - COUNT(*) FILTER (WHERE can_be_automated = true) - COUNT(*) FILTER (WHERE is_already_automated = true) as "Manual Only",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Auto Score",
                   COUNT(DISTINCT assignment_group) as "Active Teams"
            FROM tickets
            WHERE upload_id = :uid AND opened IS NOT NULL
            GROUP BY TO_CHAR(opened, 'YYYY-MM')
            ORDER BY "Month"
        """,
    },
    "full_ticket_export": {
        "label": "Full Ticket Data",
        "sql": """
            SELECT ticket_number as "Ticket #",
                   priority as "Priority",
                   assignment_group as "Team",
                   short_description as "Description",
                   l1_category as "L1 Category",
                   l2_subcategory as "L2 Subcategory",
                   l3_automation_feasibility as "Automation Feasibility",
                   l4_automation_type as "Automation Type",
                   aiops_automation_status as "Automation Status",
                   aiops_solution_lever as "Solution Lever",
                   ROUND(automation_potential_score::numeric, 2) as "Auto Score",
                   ROUND(mttr_hours::numeric, 2) as "MTTR (hrs)",
                   cluster_id as "Cluster",
                   opened as "Opened",
                   closed as "Closed",
                   reassignment_count as "Reassignments",
                   reopen_count as "Reopens",
                   channel as "Channel"
            FROM tickets
            WHERE upload_id = :uid
            ORDER BY opened DESC
            LIMIT 10000
        """,
    },
}


def generate_csv(db: Session, upload_id: int, report_type: str) -> io.StringIO:
    """Generate CSV from a report query"""
    query_info = EXPORT_QUERIES.get(report_type)
    if not query_info:
        raise ValueError(f"Unknown report type: {report_type}")

    result = db.execute(text(query_info["sql"]), {"uid": upload_id})
    rows = result.fetchall()
    columns = list(result.keys())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    for row in rows:
        writer.writerow([str(v) if v is not None else "" for v in row])

    output.seek(0)
    return output


@router.get("/csv/{report_type}")
async def export_csv(
    report_type: str,
    upload_id: int = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_upload_access_query_token),
):
    """Export a report as CSV"""
    if report_type not in EXPORT_QUERIES:
        return {"error": f"Unknown report type. Available: {list(EXPORT_QUERIES.keys())}"}

    csv_data = generate_csv(db, upload_id, report_type)
    label = EXPORT_QUERIES[report_type]["label"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"TriageIQ_{label.replace(' ', '_')}_{timestamp}.csv"

    return StreamingResponse(
        iter([csv_data.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/excel/{report_type}")
async def export_excel(
    report_type: str,
    upload_id: int = Query(...),
    db: Session = Depends(get_db),
    user: dict = Depends(require_upload_access_query_token),
):
    """Export a report as Excel"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    except ImportError:
        return {"error": "openpyxl not installed. Run: pip install openpyxl"}

    if report_type not in EXPORT_QUERIES:
        return {"error": f"Unknown report type. Available: {list(EXPORT_QUERIES.keys())}"}

    query_info = EXPORT_QUERIES[report_type]
    result = db.execute(text(query_info["sql"]), {"uid": upload_id})
    rows = result.fetchall()
    columns = list(result.keys())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = query_info["label"][:31]  # Excel tab name limit

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3"),
    )
    alt_fill = PatternFill(start_color="F2F7FB", end_color="F2F7FB", fill_type="solid")

    # Title row
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    title_cell = ws.cell(row=1, column=1)
    title_cell.value = f"TriageIQ — {query_info['label']}"
    title_cell.font = Font(bold=True, size=14, color="1F4E79")
    title_cell.alignment = Alignment(horizontal="center")

    # Timestamp
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    ts_cell = ws.cell(row=2, column=1)
    ts_cell.value = f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}"
    ts_cell.font = Font(size=10, color="666666", italic=True)
    ts_cell.alignment = Alignment(horizontal="center")

    # Headers (row 4)
    for col_idx, col_name in enumerate(columns, 1):
        cell = ws.cell(row=4, column=col_idx)
        cell.value = col_name
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    # Data rows
    for row_idx, row in enumerate(rows, 5):
        for col_idx, value in enumerate(row, 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            cell.value = value if value is not None else ""
            cell.border = thin_border
            cell.alignment = Alignment(vertical="center")
            if (row_idx - 5) % 2 == 1:
                cell.fill = alt_fill

    # Auto-width columns
    for col_idx, col_name in enumerate(columns, 1):
        max_len = len(str(col_name))
        for row in rows[:50]:  # Sample first 50 rows
            val_len = len(str(row[col_idx - 1])) if row[col_idx - 1] else 0
            max_len = max(max_len, val_len)
        ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = min(max_len + 4, 50)

    # Freeze header row
    ws.freeze_panes = "A5"

    # Save to buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    label = query_info["label"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"TriageIQ_{label.replace(' ', '_')}_{timestamp}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/available")
async def list_exports():
    """List available export types"""
    return {
        "exports": [
            {"key": k, "label": v["label"]}
            for k, v in EXPORT_QUERIES.items()
        ]
    }