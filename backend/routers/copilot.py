"""
AI Copilot API Router
Real DB-backed RAG + Ollama Qwen 2.5 7B + Smart Export
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional
import json
import httpx
import asyncio
import os
import io
import csv
import uuid
from datetime import datetime

from models import SessionLocal
from dependencies import check_upload_owner, get_current_user, get_user_from_query_token

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


router = APIRouter(prefix="/api/copilot", tags=["AI Copilot"])

# ── Config ────────────────────────────────────────────────────────────
from config import LLM_MODEL as MODEL_NAME, OLLAMA_URL
COST_PER_HOUR = 850
EXPORT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "copilot_exports")
os.makedirs(EXPORT_DIR, exist_ok=True)


# ── Request/Response Models ───────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
    upload_id: int
    conversation_history: Optional[List[dict]] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[str]
    suggestions: List[str]
    export_file: Optional[str] = None  # download URL if export was generated
    export_filename: Optional[str] = None


# ── Ollama Health Check ───────────────────────────────────────────────
async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                return any(m["name"] == MODEL_NAME for m in models)
    except:
        pass
    return False


# ── Export Detection ──────────────────────────────────────────────────
EXPORT_KEYWORDS = ["export", "download", "csv", "excel", "xlsx", "spreadsheet", "ppt", "pptx", "powerpoint", "presentation", "save as", "generate report", "create report"]

TOPIC_QUERIES = {
    "cluster": {
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
    "team": {
        "label": "Team Performance",
        "sql": """
            SELECT assignment_group as "Team",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(reassignment_count)::numeric, 2) as "Avg Reassignments",
                   ROUND(AVG(reopen_count)::numeric, 2) as "Avg Reopens",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Automation Score",
                   COUNT(*) FILTER (WHERE can_be_automated = true) as "Automatable",
                   COUNT(*) FILTER (WHERE is_already_automated = true) as "Already Automated"
            FROM tickets
            WHERE upload_id = :uid AND assignment_group IS NOT NULL
            GROUP BY assignment_group
            ORDER BY COUNT(*) DESC
        """,
    },
    "automation": {
        "label": "Automation Opportunities",
        "sql": """
            SELECT aiops_automation_status as "Automation Status",
                   aiops_solution_lever as "Solution Lever",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Score",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(mttr_hours)::numeric * COUNT(*) * 850 / 100000, 2) as "Annual Cost (Lakhs)",
                   MODE() WITHIN GROUP (ORDER BY assignment_group) as "Top Team",
                   MODE() WITHIN GROUP (ORDER BY l2_subcategory) as "Top Category"
            FROM tickets
            WHERE upload_id = :uid AND aiops_automation_status IS NOT NULL
            GROUP BY aiops_automation_status, aiops_solution_lever
            ORDER BY COUNT(*) DESC
        """,
    },
    "sla": {
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
                   ROUND(AVG(reassignment_count)::numeric, 2) as "Avg Reassignments"
            FROM tickets
            WHERE upload_id = :uid AND priority IS NOT NULL
            GROUP BY priority
            ORDER BY priority
        """,
    },
    "category": {
        "label": "Category Breakdown",
        "sql": """
            SELECT l1_category as "L1 Category",
                   l2_subcategory as "L2 Subcategory",
                   COUNT(*) as "Ticket Count",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Automation Score",
                   MODE() WITHIN GROUP (ORDER BY assignment_group) as "Top Team"
            FROM tickets
            WHERE upload_id = :uid AND l2_subcategory IS NOT NULL
            GROUP BY l1_category, l2_subcategory
            ORDER BY COUNT(*) DESC
            LIMIT 50
        """,
    },
    "monthly": {
        "label": "Monthly Trend",
        "sql": """
            SELECT TO_CHAR(opened, 'YYYY-MM') as "Month",
                   COUNT(*) as "Total Tickets",
                   ROUND(AVG(mttr_hours)::numeric, 2) as "Avg MTTR (hrs)",
                   COUNT(*) FILTER (WHERE can_be_automated = true) as "Automatable",
                   COUNT(*) FILTER (WHERE is_already_automated = true) as "Already Automated",
                   ROUND(AVG(automation_potential_score)::numeric, 2) as "Avg Auto Score"
            FROM tickets
            WHERE upload_id = :uid AND opened IS NOT NULL
            GROUP BY TO_CHAR(opened, 'YYYY-MM')
            ORDER BY "Month"
        """,
    },
    "ticket": {
        "label": "Full Ticket Export",
        "sql": """
            SELECT ticket_number as "Ticket #",
                   priority as "Priority",
                   assignment_group as "Team",
                   short_description as "Description",
                   l1_category as "L1 Category",
                   l2_subcategory as "L2 Subcategory",
                   l3_automation_feasibility as "Automation Feasibility",
                   aiops_automation_status as "Automation Status",
                   aiops_solution_lever as "Solution Lever",
                   ROUND(automation_potential_score::numeric, 2) as "Auto Score",
                   ROUND(mttr_hours::numeric, 2) as "MTTR (hrs)",
                   cluster_id as "Cluster",
                   opened as "Opened",
                   closed as "Closed",
                   reassignment_count as "Reassignments",
                   reopen_count as "Reopens"
            FROM tickets
            WHERE upload_id = :uid
            ORDER BY opened DESC
            LIMIT 10000
        """,
    },
}


def detect_export_intent(message: str) -> tuple[bool, str, str]:
    """
    Detect if user wants to export data.
    Returns (is_export, topic_key, file_format)
    """
    msg = message.lower()

    # Check for export keywords
    wants_export = any(kw in msg for kw in EXPORT_KEYWORDS)
    if not wants_export:
        return False, "", ""

    # Detect format
    file_format = "xlsx"  # default
    if any(kw in msg for kw in ["csv"]):
        file_format = "csv"
    elif any(kw in msg for kw in ["ppt", "pptx", "powerpoint", "presentation", "slide", "deck"]):
        file_format = "pptx"

    # Detect topic
    topic = "cluster"  # default
    if any(kw in msg for kw in ["team", "group", "assign", "resource", "struggling"]):
        topic = "team"
    elif any(kw in msg for kw in ["automat", "rpa", "opportunity", "bot"]):
        topic = "automation"
    elif any(kw in msg for kw in ["sla", "breach", "risk", "priority"]):
        topic = "sla"
    elif any(kw in msg for kw in ["category", "l2", "subcategory", "breakdown"]):
        topic = "category"
    elif any(kw in msg for kw in ["month", "trend", "volume", "time"]):
        topic = "monthly"
    elif any(kw in msg for kw in ["ticket", "full", "all data", "raw", "complete"]):
        topic = "ticket"
    elif any(kw in msg for kw in ["cluster", "bert", "pattern"]):
        topic = "cluster"
    elif any(kw in msg for kw in ["summary", "overview", "cxo", "executive"]):
        topic = "cluster"  # CXO summary defaults to cluster view

    return True, topic, file_format


def generate_csv_file(db: Session, upload_id: int, topic: str) -> tuple[str, str]:
    """Generate CSV and return (filepath, filename)"""
    query_info = TOPIC_QUERIES[topic]
    result = db.execute(text(query_info["sql"]), {"uid": upload_id})
    rows = result.fetchall()
    columns = list(result.keys())

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"TriageIQ_{query_info['label'].replace(' ', '_')}_{timestamp}.csv"
    filepath = os.path.join(EXPORT_DIR, filename)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([str(v) if v is not None else "" for v in row])

    return filepath, filename


def generate_excel_file(db: Session, upload_id: int, topic: str) -> tuple[str, str]:
    """Generate styled Excel and return (filepath, filename)"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    query_info = TOPIC_QUERIES[topic]
    result = db.execute(text(query_info["sql"]), {"uid": upload_id})
    rows = result.fetchall()
    columns = list(result.keys())

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = query_info["label"][:31]

    # Styles
    header_font = Font(bold=True, color="FFFFFF", size=11, name="Arial")
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin", color="D9E2F3"),
        right=Side(style="thin", color="D9E2F3"),
        top=Side(style="thin", color="D9E2F3"),
        bottom=Side(style="thin", color="D9E2F3"),
    )
    alt_fill = PatternFill(start_color="F2F7FB", end_color="F2F7FB", fill_type="solid")
    title_font = Font(bold=True, size=14, color="1F4E79", name="Arial")
    body_font = Font(size=10, name="Arial")

    # Title
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    tc = ws.cell(row=1, column=1)
    tc.value = f"TriageIQ — {query_info['label']}"
    tc.font = title_font
    tc.alignment = Alignment(horizontal="center")

    # Timestamp
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(columns))
    ts = ws.cell(row=2, column=1)
    ts.value = f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')} | Dataset: Upload #{upload_id}"
    ts.font = Font(size=9, color="666666", italic=True, name="Arial")
    ts.alignment = Alignment(horizontal="center")

    # Headers (row 4)
    for ci, col in enumerate(columns, 1):
        cell = ws.cell(row=4, column=ci)
        cell.value = col
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = thin_border

    # Data
    for ri, row in enumerate(rows, 5):
        for ci, val in enumerate(row, 1):
            cell = ws.cell(row=ri, column=ci)
            cell.value = val if val is not None else ""
            cell.border = thin_border
            cell.font = body_font
            cell.alignment = Alignment(vertical="center")
            if (ri - 5) % 2 == 1:
                cell.fill = alt_fill

    # Summary row
    summary_row = len(rows) + 6
    ws.cell(row=summary_row, column=1).value = f"Total Records: {len(rows)}"
    ws.cell(row=summary_row, column=1).font = Font(bold=True, size=10, color="1F4E79", name="Arial")

    # Auto-width
    for ci, col in enumerate(columns, 1):
        max_len = len(str(col))
        for row in rows[:100]:
            vl = len(str(row[ci - 1])) if row[ci - 1] else 0
            max_len = max(max_len, vl)
        ws.column_dimensions[openpyxl.utils.get_column_letter(ci)].width = min(max_len + 4, 50)

    ws.freeze_panes = "A5"

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"TriageIQ_{query_info['label'].replace(' ', '_')}_{timestamp}.xlsx"
    filepath = os.path.join(EXPORT_DIR, filename)
    wb.save(filepath)

    return filepath, filename


def generate_pptx_file(db: Session, upload_id: int, topic: str) -> tuple[str, str]:
    """Generate PowerPoint with data table and return (filepath, filename)"""
    from pptx import Presentation
    from pptx.util import Inches, Pt, Emu
    from pptx.dml.color import RGBColor
    from pptx.enum.text import PP_ALIGN

    query_info = TOPIC_QUERIES[topic]
    result = db.execute(text(query_info["sql"]), {"uid": upload_id})
    rows = result.fetchall()
    columns = list(result.keys())

    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    # ── Title Slide ──
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank
    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = RGBColor(0x1F, 0x4E, 0x79)

    # Title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = f"TriageIQ Analytics"
    p.font.size = Pt(44)
    p.font.bold = True
    p.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    p.alignment = PP_ALIGN.LEFT

    # Subtitle
    txBox2 = slide.shapes.add_textbox(Inches(1), Inches(3.5), Inches(11), Inches(1))
    tf2 = txBox2.text_frame
    p2 = tf2.paragraphs[0]
    p2.text = query_info["label"]
    p2.font.size = Pt(24)
    p2.font.color.rgb = RGBColor(0xCA, 0xDC, 0xFC)
    p2.alignment = PP_ALIGN.LEFT

    # Date
    txBox3 = slide.shapes.add_textbox(Inches(1), Inches(4.5), Inches(11), Inches(0.5))
    tf3 = txBox3.text_frame
    p3 = tf3.paragraphs[0]
    p3.text = f"Generated: {datetime.now().strftime('%d %B %Y')} | {len(rows)} records analyzed"
    p3.font.size = Pt(14)
    p3.font.color.rgb = RGBColor(0x90, 0xB0, 0xD0)

    # ── Data Table Slide(s) ──
    max_rows_per_slide = 15
    display_cols = columns[:8]  # Limit columns for readability
    col_count = len(display_cols)

    for page_start in range(0, len(rows), max_rows_per_slide):
        page_rows = rows[page_start:page_start + max_rows_per_slide]
        row_count = len(page_rows) + 1  # +1 for header

        slide = prs.slides.add_slide(prs.slide_layouts[6])

        # Slide title
        txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.3), Inches(12), Inches(0.6))
        tf = txBox.text_frame
        p = tf.paragraphs[0]
        page_num = (page_start // max_rows_per_slide) + 1
        total_pages = (len(rows) + max_rows_per_slide - 1) // max_rows_per_slide
        p.text = f"{query_info['label']} ({page_num}/{total_pages})"
        p.font.size = Pt(20)
        p.font.bold = True
        p.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)

        # Table
        table_width = Inches(12.33)
        table_height = Inches(5.5)
        left = Inches(0.5)
        top = Inches(1.2)

        table_shape = slide.shapes.add_table(
            row_count, col_count, left, top, table_width, table_height
        )
        table = table_shape.table

        # Header row
        for ci, col in enumerate(display_cols):
            cell = table.cell(0, ci)
            cell.text = str(col)
            for paragraph in cell.text_frame.paragraphs:
                paragraph.font.size = Pt(10)
                paragraph.font.bold = True
                paragraph.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                paragraph.alignment = PP_ALIGN.CENTER
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor(0x1F, 0x4E, 0x79)

        # Data rows
        for ri, row in enumerate(page_rows, 1):
            for ci, col in enumerate(display_cols):
                col_idx = columns.index(col)
                cell = table.cell(ri, ci)
                val = row[col_idx]
                cell.text = str(val) if val is not None else ""
                for paragraph in cell.text_frame.paragraphs:
                    paragraph.font.size = Pt(9)
                    paragraph.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
                if ri % 2 == 0:
                    cell.fill.solid()
                    cell.fill.fore_color.rgb = RGBColor(0xF2, 0xF7, 0xFB)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"TriageIQ_{query_info['label'].replace(' ', '_')}_{timestamp}.pptx"
    filepath = os.path.join(EXPORT_DIR, filename)
    prs.save(filepath)

    return filepath, filename


# ── Real DB Context Queries ───────────────────────────────────────────
def get_cluster_summary(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT cluster_id, COUNT(*) as ticket_count,
               ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr,
               ROUND(AVG(automation_potential_score)::numeric, 2) as avg_auto_score,
               MODE() WITHIN GROUP (ORDER BY assignment_group) as top_team,
               MODE() WITHIN GROUP (ORDER BY aiops_solution_lever) as top_solution,
               MODE() WITHIN GROUP (ORDER BY l2_subcategory) as top_category
        FROM tickets WHERE upload_id = :uid AND cluster_id IS NOT NULL
        GROUP BY cluster_id ORDER BY ticket_count DESC LIMIT 15
    """), {"uid": upload_id}).fetchall()
    if not result: return "No cluster data available."
    lines = ["BERT Cluster Summary (Top 15 by volume):"]
    for r in result:
        lines.append(f"- Cluster {r.cluster_id}: {r.ticket_count} tickets, MTTR={r.avg_mttr}h, Auto={r.avg_auto_score}, Team={r.top_team}, Solution={r.top_solution}, Category={r.top_category}")
    return "\n".join(lines)


def get_automation_summary(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT aiops_automation_status, COUNT(*) as cnt,
               ROUND(AVG(automation_potential_score)::numeric, 2) as avg_score,
               ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr
        FROM tickets WHERE upload_id = :uid AND aiops_automation_status IS NOT NULL
        GROUP BY aiops_automation_status ORDER BY cnt DESC
    """), {"uid": upload_id}).fetchall()
    if not result: return "No automation data available."
    total = sum(r.cnt for r in result)
    lines = [f"Automation Breakdown ({total:,} total tickets):"]
    for r in result:
        pct = round(r.cnt / total * 100, 1)
        lines.append(f"- {r.aiops_automation_status}: {r.cnt:,} ({pct}%), Score={r.avg_score}, MTTR={r.avg_mttr}h")
    return "\n".join(lines)


def get_team_performance(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT assignment_group, COUNT(*) as ticket_count,
               ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr,
               ROUND(AVG(reassignment_count)::numeric, 2) as avg_reassign,
               ROUND(AVG(reopen_count)::numeric, 2) as avg_reopen,
               ROUND(AVG(automation_potential_score)::numeric, 2) as avg_auto
        FROM tickets WHERE upload_id = :uid AND assignment_group IS NOT NULL
        GROUP BY assignment_group ORDER BY ticket_count DESC LIMIT 10
    """), {"uid": upload_id}).fetchall()
    if not result: return "No team data available."
    lines = ["Team Performance (Top 10):"]
    for r in result:
        lines.append(f"- {r.assignment_group}: {r.ticket_count:,} tickets, MTTR={r.avg_mttr}h, Reassign={r.avg_reassign}, Reopen={r.avg_reopen}, Auto={r.avg_auto}")
    return "\n".join(lines)


def get_sla_risk(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT priority, COUNT(*) as total, ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr,
               COUNT(*) FILTER (WHERE mttr_hours > CASE priority WHEN '1 - Critical' THEN 4 WHEN '2 - High' THEN 8 WHEN '3 - Medium' THEN 24 ELSE 48 END) as breached
        FROM tickets WHERE upload_id = :uid AND priority IS NOT NULL
        GROUP BY priority ORDER BY priority
    """), {"uid": upload_id}).fetchall()
    if not result: return "No SLA data available."
    lines = ["SLA Risk by Priority:"]
    for r in result:
        bp = round(r.breached / r.total * 100, 1) if r.total > 0 else 0
        lines.append(f"- {r.priority}: {r.total:,} tickets, MTTR={r.avg_mttr}h, Breached={r.breached} ({bp}%)")
    return "\n".join(lines)


def get_category_breakdown(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT l2_subcategory, COUNT(*) as cnt, ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr,
               ROUND(AVG(automation_potential_score)::numeric, 2) as avg_auto
        FROM tickets WHERE upload_id = :uid AND l2_subcategory IS NOT NULL
        GROUP BY l2_subcategory ORDER BY cnt DESC LIMIT 10
    """), {"uid": upload_id}).fetchall()
    if not result: return "No category data available."
    lines = ["Top 10 Categories (L2):"]
    for r in result:
        lines.append(f"- {r.l2_subcategory}: {r.cnt:,} tickets, MTTR={r.avg_mttr}h, Auto={r.avg_auto}")
    return "\n".join(lines)


def get_solution_lever_summary(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT aiops_solution_lever, COUNT(*) as cnt,
               ROUND(AVG(automation_potential_score)::numeric, 2) as avg_score,
               ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr
        FROM tickets WHERE upload_id = :uid AND aiops_solution_lever IS NOT NULL
        GROUP BY aiops_solution_lever ORDER BY cnt DESC
    """), {"uid": upload_id}).fetchall()
    if not result: return "No solution lever data."
    total = sum(r.cnt for r in result)
    lines = ["Solution Lever Breakdown:"]
    for r in result:
        pct = round(r.cnt / total * 100, 1)
        lines.append(f"- {r.aiops_solution_lever}: {r.cnt:,} ({pct}%), Score={r.avg_score}, MTTR={r.avg_mttr}h")
    return "\n".join(lines)


def get_overall_stats(db: Session, upload_id: int) -> str:
    result = db.execute(text("""
        SELECT COUNT(*) as total, COUNT(DISTINCT cluster_id) as num_clusters,
               ROUND(AVG(mttr_hours)::numeric, 2) as avg_mttr,
               ROUND(AVG(automation_potential_score)::numeric, 2) as avg_auto,
               COUNT(DISTINCT assignment_group) as num_teams,
               MIN(opened) as first_date, MAX(opened) as last_date
        FROM tickets WHERE upload_id = :uid
    """), {"uid": upload_id}).fetchone()
    if not result: return "No data available."
    return (f"Dataset: {result.total:,} tickets, {result.num_clusters} clusters, {result.num_teams} teams, "
            f"MTTR={result.avg_mttr}h, Auto Score={result.avg_auto}, Range: {result.first_date} to {result.last_date}")


# ── Smart Context Builder ─────────────────────────────────────────────
def build_context(message: str, db: Session, upload_id: int) -> tuple[str, list[str]]:
    msg = message.lower()
    context_parts = [get_overall_stats(db, upload_id)]
    sources = ["Dataset Overview"]

    if any(kw in msg for kw in ["cluster", "bert", "pattern", "segment"]):
        context_parts.append(get_cluster_summary(db, upload_id))
        sources.append("BERT Clustering")
    if any(kw in msg for kw in ["automat", "rpa", "self-service", "bot", "script", "opportunity", "roi", "saving"]):
        context_parts.append(get_automation_summary(db, upload_id))
        context_parts.append(get_solution_lever_summary(db, upload_id))
        sources.extend(["Automation Classifier", "Solution Levers"])
    if any(kw in msg for kw in ["team", "group", "assign", "resource", "struggling", "workload"]):
        context_parts.append(get_team_performance(db, upload_id))
        sources.append("Team Analytics")
    if any(kw in msg for kw in ["sla", "breach", "risk", "priority", "critical", "escalat"]):
        context_parts.append(get_sla_risk(db, upload_id))
        sources.append("SLA Risk")
    if any(kw in msg for kw in ["category", "type", "breakdown", "l2", "l3"]):
        context_parts.append(get_category_breakdown(db, upload_id))
        sources.append("Category Analysis")
    if any(kw in msg for kw in ["solution", "lever", "remediation"]):
        context_parts.append(get_solution_lever_summary(db, upload_id))
        sources.append("Solution Levers")
    if len(context_parts) == 1:
        context_parts.extend([get_cluster_summary(db, upload_id), get_automation_summary(db, upload_id), get_team_performance(db, upload_id)])
        sources.extend(["BERT Clustering", "Automation Classifier", "Team Analytics"])

    return "\n\n".join(context_parts), list(dict.fromkeys(sources))


SYSTEM_PROMPT = """You are the TriageIQ AI Copilot — an expert ITSM analytics assistant for enterprise IT operations.

Your role:
- Analyze IT service ticket data and provide actionable insights
- Help pre-sales teams understand automation opportunities and ROI
- Present findings in a clear, CXO-friendly manner

Guidelines:
- Use specific numbers and metrics from the provided context
- Format with markdown: **bold** for key metrics, bullet points for lists
- Be concise but thorough — aim for 150-300 words
- When discussing savings, use Indian currency (₹) with Lakhs/Crores
- Cost per ticket hour = ₹850
- Always suggest a follow-up action or deeper analysis
- If the data doesn't contain what's asked, say so honestly
- When an export file has been generated, mention it briefly and focus on the analysis

You are analyzing real ServiceNow ticket data processed through ML models including BERT clustering, XGBoost automation scoring, and multi-task classification."""


def get_smart_suggestions(message: str) -> list[str]:
    msg = message.lower()
    if any(kw in msg for kw in ["automat", "opportunity", "rpa"]):
        return ["Export automation opportunities as Excel", "Which clusters have the highest ROI?", "Which teams benefit most from automation?"]
    elif any(kw in msg for kw in ["team", "struggling", "resource"]):
        return ["Export team performance as Excel", "What automation reduces workload?", "Show SLA breach rate by team"]
    elif any(kw in msg for kw in ["sla", "breach", "risk"]):
        return ["Export SLA risk as CSV", "Which teams have highest breach rates?", "How can automation reduce breaches?"]
    elif any(kw in msg for kw in ["cluster", "bert", "pattern"]):
        return ["Export cluster summary as Excel", "Which clusters need automation?", "Show ROI per cluster"]
    elif any(kw in msg for kw in ["export", "download"]):
        return ["Export team performance as Excel", "Export automation opportunities as CSV", "Create cluster summary PowerPoint"]
    else:
        return ["What are the top automation opportunities?", "Export team data as Excel", "Show me the SLA risk analysis"]


# ── Chat Endpoint (Non-Streaming) ────────────────────────────────────
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    check_upload_owner(request.upload_id, current_user)
    context, sources = build_context(request.message, db, request.upload_id)

    # Check for export intent
    is_export, topic, file_format = detect_export_intent(request.message)
    export_file = None
    export_filename = None

    if is_export:
        try:
            if file_format == "csv":
                filepath, filename = generate_csv_file(db, request.upload_id, topic)
            elif file_format == "pptx":
                filepath, filename = generate_pptx_file(db, request.upload_id, topic)
            else:
                filepath, filename = generate_excel_file(db, request.upload_id, topic)
            export_file = f"/api/copilot/download/{filename}"
            export_filename = filename
        except Exception as e:
            print(f"Export error: {e}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if request.conversation_history:
        for msg in request.conversation_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    export_note = ""
    if export_file:
        export_note = f"\n\n[NOTE: A {file_format.upper()} file '{export_filename}' has been generated for download. Mention this in your response.]"

    messages.append({
        "role": "user",
        "content": f"Data Context:\n{context}{export_note}\n\nUser Question: {request.message}"
    })

    response_text = None
    ollama_available = await check_ollama()

    if ollama_available:
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{OLLAMA_URL}/api/chat", json={
                    "model": MODEL_NAME, "messages": messages, "stream": False,
                    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 1024}
                })
                if resp.status_code == 200:
                    response_text = resp.json().get("message", {}).get("content", "")
        except Exception as e:
            print(f"Ollama error: {e}")

    if not response_text:
        if export_file:
            response_text = f"✅ Your **{TOPIC_QUERIES[topic]['label']}** report has been generated as {file_format.upper()}. Click the download button below.\n\nHere's a quick summary from the data:\n\n{context}"
        else:
            response_text = f"⚠️ LLM offline. Raw context:\n\n{context}"

    return ChatResponse(
        response=response_text,
        sources=sources,
        suggestions=get_smart_suggestions(request.message),
        export_file=export_file,
        export_filename=export_filename,
    )


# ── Streaming Chat Endpoint ───────────────────────────────────────────
@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    check_upload_owner(request.upload_id, current_user)
    context, sources = build_context(request.message, db, request.upload_id)

    # Check for export intent
    is_export, topic, file_format = detect_export_intent(request.message)
    export_file = None
    export_filename = None

    if is_export:
        try:
            if file_format == "csv":
                filepath, filename = generate_csv_file(db, request.upload_id, topic)
            elif file_format == "pptx":
                filepath, filename = generate_pptx_file(db, request.upload_id, topic)
            else:
                filepath, filename = generate_excel_file(db, request.upload_id, topic)
            export_file = f"/api/copilot/download/{filename}"
            export_filename = filename
        except Exception as e:
            print(f"Export error: {e}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if request.conversation_history:
        for msg in request.conversation_history[-6:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

    export_note = ""
    if export_file:
        export_note = f"\n\n[NOTE: A {file_format.upper()} file '{export_filename}' has been generated for download. Mention this briefly in your response.]"

    messages.append({
        "role": "user",
        "content": f"Data Context:\n{context}{export_note}\n\nUser Question: {request.message}"
    })

    ollama_available = await check_ollama()
    if not ollama_available:
        async def offline_stream():
            if export_file:
                msg = f"✅ Your **{TOPIC_QUERIES[topic]['label']}** report is ready for download.\n\n{context}"
            else:
                msg = f"⚠️ LLM offline. Raw context:\n\n{context}"
            yield f"data: {json.dumps({'token': msg, 'done': False})}\n\n"
            yield f"data: {json.dumps({'token': '', 'done': True, 'sources': sources, 'suggestions': get_smart_suggestions(request.message), 'export_file': export_file, 'export_filename': export_filename})}\n\n"
        return StreamingResponse(offline_stream(), media_type="text/event-stream")

    async def stream_response():
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", f"{OLLAMA_URL}/api/chat", json={
                    "model": MODEL_NAME, "messages": messages, "stream": True,
                    "options": {"temperature": 0.3, "top_p": 0.9, "num_predict": 1024}
                }) as resp:
                    async for line in resp.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                token = data.get("message", {}).get("content", "")
                                done = data.get("done", False)
                                if token:
                                    yield f"data: {json.dumps({'token': token, 'done': False})}\n\n"
                                if done:
                                    yield f"data: {json.dumps({'token': '', 'done': True, 'sources': sources, 'suggestions': get_smart_suggestions(request.message), 'export_file': export_file, 'export_filename': export_filename})}\n\n"
                            except json.JSONDecodeError:
                                continue
        except Exception as e:
            yield f"data: {json.dumps({'token': f'Error: {str(e)}', 'done': True, 'sources': [], 'suggestions': [], 'export_file': None, 'export_filename': None})}\n\n"

    return StreamingResponse(stream_response(), media_type="text/event-stream")


# ── Download Endpoint ─────────────────────────────────────────────────
@router.get("/download/{filename}")
async def download_file(filename: str, user: dict = Depends(get_user_from_query_token)):
    """Download an exported file (authenticated; file name must stay inside EXPORT_DIR)"""
    export_root = os.path.realpath(EXPORT_DIR)
    filepath = os.path.realpath(os.path.join(export_root, os.path.basename(filename)))
    if os.path.dirname(filepath) != export_root or not os.path.isfile(filepath):
        raise HTTPException(status_code=404, detail="File not found")

    media_types = {
        ".csv": "text/csv",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    }
    ext = os.path.splitext(filename)[1]
    mt = media_types.get(ext, "application/octet-stream")

    return FileResponse(filepath, media_type=mt, filename=filename)


# ── Health Check ──────────────────────────────────────────────────────
@router.get("/health")
async def copilot_health():
    ollama_ok = await check_ollama()
    return {
        "status": "online" if ollama_ok else "degraded",
        "llm": MODEL_NAME if ollama_ok else "offline",
        "ollama_url": OLLAMA_URL,
    }


@router.get("/suggestions")
async def get_suggestions(upload_id: int):
    return {
        "suggestions": [
            "What are the top SLA risks right now?",
            "Summarize the automation opportunities",
            "Which teams are struggling the most?",
            "Show me BERT cluster insights",
            "Export team performance as Excel",
            "Export automation opportunities as CSV",
            "Create a cluster summary PowerPoint",
            "Give me a CXO-ready summary",
        ]
    }