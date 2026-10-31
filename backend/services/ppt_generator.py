"""
services/ppt_generator.py
---------------------------
Generates configurable PowerPoint presentation using python-pptx.
THE PILLAR FEATURE — replaces 2-3 days of manual pre-sales work.

Available slides (user picks which to include):
  1. title          — Title slide with client name + date
  2. exec_summary   — Total tickets, automation %, savings estimate
  3. tower_split    — Volume by Tower (bar chart)
  4. category_split — Volume by Category (bar chart)
  5. top_subcats    — Top 15 SubCategories (horizontal bar)
  6. automation_overview — Donut + numbers
  7. automation_tower    — Stacked bar: Tower × Automation
  8. mttr_analysis       — Tower × avg resolution time
  9. quick_wins          — Top 10 automatable subcategories table
  10. solution_roadmap   — Implementation timeline + effort
  11. roi_projection     — 12/24 month savings
  12. appendix           — Full data summary
"""

import io
from typing import List, Dict, Any
from datetime import datetime

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.enum.text import PP_ALIGN, MSO_AUTO_SIZE
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import CategoryChartData


# Deck colour palette
BRAND_BLUE = RGBColor(0x00, 0x44, 0x8B)
BRAND_DARK = RGBColor(0x1A, 0x1A, 0x2E)
BRAND_LIGHT_BLUE = RGBColor(0x2E, 0x75, 0xB6)
BRAND_GREEN = RGBColor(0x2E, 0xCC, 0x71)
BRAND_ORANGE = RGBColor(0xF3, 0x9C, 0x12)
BRAND_RED = RGBColor(0xE7, 0x4C, 0x3C)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0x66, 0x66, 0x66)


def generate_ppt(
    stats: Dict,
    pivots: List[Dict],
    slides: List[str],
    client_name: str = "Client",
    date_str: str = "",
) -> io.BytesIO:
    """
    Generate a PowerPoint presentation with selected slides.
    
    Args:
        stats: From /api/ticket-intelligence/{id}/stats
        pivots: From /api/ticket-intelligence/{id}/pivots
        slides: List of slide IDs to include
        client_name: Client name for title slide
        date_str: Date string for title slide
    
    Returns:
        BytesIO buffer containing .pptx file
    """
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    
    if not date_str:
        date_str = datetime.now().strftime("%B %Y")
    
    # Build pivot lookup
    pivot_map = {p["id"]: p for p in pivots} if pivots else {}
    
    # Generate requested slides
    
    slide_generators = {
        "title": lambda: _slide_title(prs, client_name, date_str, stats),
        "exec_summary": lambda: _slide_exec_summary(prs, stats),
        "tower_split": lambda: _slide_bar_chart(prs, pivot_map.get("tower_volume"), "Volume Split by Tower", "name"),
        "category_split": lambda: _slide_bar_chart(prs, pivot_map.get("category_volume"), "Volume Split by Category", "name"),
        "top_subcats": lambda: _slide_table(prs, pivot_map.get("top_subcategories"), "Top 15 Sub Categories by Volume"),
        "automation_overview": lambda: _slide_automation_overview(prs, stats),
        "automation_tower": lambda: _slide_stacked_chart(prs, pivot_map.get("tower_automation")),
        "mttr_analysis": lambda: _slide_table(prs, pivot_map.get("tower_mttr"), "MTTR Analysis by Tower"),
        "quick_wins": lambda: _slide_quick_wins(prs, pivot_map.get("quick_wins"), stats),
        "solution_roadmap": lambda: _slide_solution_roadmap(prs, stats),
        "roi_projection": lambda: _slide_roi_projection(prs, stats),
        "appendix": lambda: _slide_appendix(prs, stats, pivots),
    }
    
    for slide_id in slides:
        generator = slide_generators.get(slide_id)
        if generator:
            try:
                generator()
            except Exception as e:
                print(f"  PPT: Skipped slide '{slide_id}': {e}")
    
    # Save to buffer
    output = io.BytesIO()
    prs.save(output)
    output.seek(0)
    return output


# ============================================================
# HELPER: Add slide with consistent styling
# ============================================================

def _add_slide(prs, title_text: str, subtitle_text: str = ""):
    """Add a blank slide with title bar."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])  # Blank layout
    
    # Title bar background
    from pptx.util import Inches
    left = Inches(0)
    top = Inches(0)
    width = prs.slide_width
    height = Inches(1.0)
    
    shape = slide.shapes.add_shape(
        1, left, top, width, height  # Rectangle
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = BRAND_BLUE
    shape.line.fill.background()
    
    # Title text
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(0.15), Inches(10), Inches(0.7))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(28)
    p.font.color.rgb = WHITE
    p.font.bold = True
    
    if subtitle_text:
        p2 = tf.add_paragraph()
        p2.text = subtitle_text
        p2.font.size = Pt(14)
        p2.font.color.rgb = RGBColor(0xBB, 0xDE, 0xFB)
    
    return slide


def _add_kpi_card(slide, left, top, width, height, label, value, color=BRAND_BLUE):
    """Add a KPI card to a slide."""
    shape = slide.shapes.add_shape(1, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    
    # Value
    txBox = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.15), width - Inches(0.4), Inches(0.6))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = str(value)
    p.font.size = Pt(32)
    p.font.color.rgb = WHITE
    p.font.bold = True
    p.alignment = PP_ALIGN.CENTER
    
    # Label
    p2 = tf.add_paragraph()
    p2.text = label
    p2.font.size = Pt(12)
    p2.font.color.rgb = RGBColor(0xDD, 0xDD, 0xFF)
    p2.alignment = PP_ALIGN.CENTER


# ============================================================
# SLIDE GENERATORS
# ============================================================

def _slide_title(prs, client_name, date_str, stats):
    """Slide 1: Title slide."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    
    # Full slide background
    bg = slide.shapes.add_shape(1, Inches(0), Inches(0), prs.slide_width, prs.slide_height)
    bg.fill.solid()
    bg.fill.fore_color.rgb = BRAND_DARK
    bg.line.fill.background()
    
    # Title
    txBox = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(11), Inches(1.5))
    tf = txBox.text_frame
    p = tf.paragraphs[0]
    p.text = "IT Service Management"
    p.font.size = Pt(20)
    p.font.color.rgb = RGBColor(0x88, 0xBB, 0xFF)
    
    p2 = tf.add_paragraph()
    p2.text = "Automation Intelligence Report"
    p2.font.size = Pt(44)
    p2.font.color.rgb = WHITE
    p2.font.bold = True
    
    # Client info
    txBox2 = slide.shapes.add_textbox(Inches(1), Inches(4.5), Inches(11), Inches(1))
    tf2 = txBox2.text_frame
    p3 = tf2.paragraphs[0]
    p3.text = f"{client_name} | {date_str}"
    p3.font.size = Pt(18)
    p3.font.color.rgb = RGBColor(0xBB, 0xBB, 0xBB)
    
    p4 = tf2.add_paragraph()
    total = stats.get("total_tickets", 0)
    p4.text = f"Analysis of {total:,} tickets | Generated by TriageIQ"
    p4.font.size = Pt(14)
    p4.font.color.rgb = RGBColor(0x88, 0x88, 0x88)


def _slide_exec_summary(prs, stats):
    """Slide 2: Executive Summary with KPI cards."""
    slide = _add_slide(prs, "Executive Summary", "Key Findings at a Glance")
    
    total = stats.get("total_tickets", 0)
    auto = stats.get("already_automated", 0)
    can_auto = stats.get("can_be_automated", 0)
    manual = stats.get("manual", 0)
    avg_mttr = stats.get("avg_mttr_hours", 0)
    
    # KPI cards row
    card_w = Inches(2.8)
    card_h = Inches(1.4)
    y = Inches(1.5)
    gap = Inches(0.3)
    start_x = Inches(0.5)
    
    _add_kpi_card(slide, start_x, y, card_w, card_h,
                  "Total Tickets", f"{total:,}", BRAND_BLUE)
    _add_kpi_card(slide, start_x + card_w + gap, y, card_w, card_h,
                  "Already Automated", f"{auto:,} ({stats.get('already_automated_pct', 0)}%)", BRAND_GREEN)
    _add_kpi_card(slide, start_x + 2 * (card_w + gap), y, card_w, card_h,
                  "Automation Opportunity", f"{can_auto:,} ({stats.get('can_be_automated_pct', 0)}%)", BRAND_LIGHT_BLUE)
    _add_kpi_card(slide, start_x + 3 * (card_w + gap), y, card_w, card_h,
                  "Manual Required", f"{manual:,} ({stats.get('manual_pct', 0)}%)", BRAND_RED)
    
    # Key insights text
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(3.5), Inches(12), Inches(3.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    
    insights = [
        f"• {total:,} tickets analyzed across {len(stats.get('tower_distribution', {}))} technology towers",
        f"• {auto + can_auto:,} tickets ({(auto + can_auto) / total * 100:.0f}%) have automation potential" if total > 0 else "",
        f"• Average resolution time: {avg_mttr:.1f} hours",
        f"• Top tower: {max(stats.get('tower_distribution', {'N/A': 0}), key=stats.get('tower_distribution', {}).get)}",
        f"• ML classification confidence: {stats.get('avg_aio_confidence', 0):.0%}",
    ]
    
    for i, insight in enumerate(insights):
        if not insight:
            continue
        if i == 0:
            tf.paragraphs[0].text = insight
            tf.paragraphs[0].font.size = Pt(16)
            tf.paragraphs[0].font.color.rgb = GRAY
        else:
            p = tf.add_paragraph()
            p.text = insight
            p.font.size = Pt(16)
            p.font.color.rgb = GRAY
            p.space_before = Pt(8)


def _slide_bar_chart(prs, pivot_data, title, x_field):
    """Generic bar chart slide."""
    slide = _add_slide(prs, title)
    
    if not pivot_data or not pivot_data.get("data"):
        return
    
    chart_data = CategoryChartData()
    labels = [str(d.get(x_field, "")) for d in pivot_data["data"][:15]]
    values = [d.get("count", 0) for d in pivot_data["data"][:15]]
    
    chart_data.categories = labels
    chart_data.add_series("Tickets", values)
    
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        Inches(0.5), Inches(1.3), Inches(12), Inches(5.5),
        chart_data
    ).chart
    
    chart.has_legend = False
    
    # Style
    series = chart.series[0]
    series.format.fill.solid()
    series.format.fill.fore_color.rgb = BRAND_LIGHT_BLUE


def _slide_stacked_chart(prs, pivot_data):
    """Stacked bar: Tower × Automation."""
    slide = _add_slide(prs, "Automation Potential by Tower")
    
    if not pivot_data or not pivot_data.get("data"):
        return
    
    chart_data = CategoryChartData()
    labels = [d.get("tower", "") for d in pivot_data["data"]]
    chart_data.categories = labels
    
    for series_name in ["Already Automated", "Can Be Automated", "Manual"]:
        values = [d.get(series_name, 0) for d in pivot_data["data"]]
        chart_data.add_series(series_name, values)
    
    chart_frame = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_STACKED,
        Inches(0.5), Inches(1.3), Inches(12), Inches(5.5),
        chart_data
    )
    
    chart = chart_frame.chart
    chart.has_legend = True
    
    # Color series
    colors = [BRAND_GREEN, BRAND_LIGHT_BLUE, BRAND_RED]
    for i, color in enumerate(colors):
        if i < len(chart.series):
            chart.series[i].format.fill.solid()
            chart.series[i].format.fill.fore_color.rgb = color


def _slide_automation_overview(prs, stats):
    """Automation overview with numbers."""
    slide = _add_slide(prs, "Automation Overview")
    
    total = stats.get("total_tickets", 1)
    auto = stats.get("already_automated", 0)
    can_auto = stats.get("can_be_automated", 0)
    manual = stats.get("manual", 0)
    
    # Big numbers
    y = Inches(2.0)
    card_w = Inches(3.5)
    card_h = Inches(3.0)
    
    _add_kpi_card(slide, Inches(0.8), y, card_w, card_h,
                  f"Already Automated\n{auto/total*100:.1f}%", f"{auto:,}", BRAND_GREEN)
    _add_kpi_card(slide, Inches(4.8), y, card_w, card_h,
                  f"Can Be Automated\n{can_auto/total*100:.1f}%", f"{can_auto:,}", BRAND_LIGHT_BLUE)
    _add_kpi_card(slide, Inches(8.8), y, card_w, card_h,
                  f"Manual Required\n{manual/total*100:.1f}%", f"{manual:,}", BRAND_RED)


def _slide_table(prs, pivot_data, title):
    """Generic table slide from pivot data."""
    slide = _add_slide(prs, title)
    
    if not pivot_data or not pivot_data.get("data"):
        return
    
    data = pivot_data["data"][:15]
    if not data:
        return
    
    cols = list(data[0].keys())
    n_rows = len(data) + 1
    n_cols = min(len(cols), 8)
    
    table = slide.shapes.add_table(
        n_rows, n_cols,
        Inches(0.5), Inches(1.3), Inches(12), Inches(5.5)
    ).table
    
    # Headers
    for j, col in enumerate(cols[:n_cols]):
        cell = table.cell(0, j)
        cell.text = col.replace("_", " ").title()
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(10)
            p.font.bold = True
            p.font.color.rgb = WHITE
        cell.fill.solid()
        cell.fill.fore_color.rgb = BRAND_BLUE
    
    # Data
    for i, row in enumerate(data):
        for j, col in enumerate(cols[:n_cols]):
            cell = table.cell(i + 1, j)
            val = row.get(col, "")
            cell.text = str(round(val, 2) if isinstance(val, float) else val)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(9)
            
            if i % 2 == 0:
                cell.fill.solid()
                cell.fill.fore_color.rgb = RGBColor(0xF0, 0xF4, 0xF8)


def _slide_quick_wins(prs, pivot_data, stats):
    """Quick wins — top automatable subcategories."""
    slide = _add_slide(prs, "Quick Wins — Top Automation Opportunities",
                       "Highest volume subcategories with automation potential")
    
    if not pivot_data or not pivot_data.get("data"):
        return
    
    # Filter to high automation potential
    data = [d for d in pivot_data["data"] if d.get("automation_pct", 0) > 50][:10]
    
    if not data:
        data = pivot_data["data"][:10]
    
    cols = ["subcategory", "total", "can_automate", "automation_pct", "avg_mttr"]
    headers = ["SubCategory", "Total", "Automatable", "Auto %", "Avg MTTR (h)"]
    
    n_rows = len(data) + 1
    n_cols = len(cols)
    
    table = slide.shapes.add_table(
        n_rows, n_cols,
        Inches(0.5), Inches(1.5), Inches(12), Inches(5)
    ).table
    
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(11)
            p.font.bold = True
            p.font.color.rgb = WHITE
        cell.fill.solid()
        cell.fill.fore_color.rgb = BRAND_BLUE
    
    for i, row in enumerate(data):
        for j, col in enumerate(cols):
            cell = table.cell(i + 1, j)
            val = row.get(col, "")
            if col == "automation_pct":
                cell.text = f"{val}%"
            elif isinstance(val, float):
                cell.text = f"{val:.1f}"
            else:
                cell.text = str(val)
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(10)


def _slide_solution_roadmap(prs, stats):
    """Solution roadmap with phases."""
    slide = _add_slide(prs, "Solution Roadmap", "Implementation Timeline")
    
    phases = [
        ("Phase 1: Quick Wins\n(Weeks 1-4)", "Self-service portal for password resets\nAuto-remediation for disk space alerts\nScript automation for service restarts", BRAND_GREEN),
        ("Phase 2: Core Automation\n(Weeks 5-12)", "RPA for provisioning workflows\nChatbot for L1 queries\nMonitoring optimization", BRAND_LIGHT_BLUE),
        ("Phase 3: Advanced\n(Weeks 13-24)", "AI-driven ticket routing\nPredictive analytics\nContinuous improvement", BRAND_ORANGE),
    ]
    
    y = Inches(1.5)
    for i, (title, desc, color) in enumerate(phases):
        x = Inches(0.5 + i * 4.2)
        w = Inches(3.8)
        h = Inches(5.0)
        
        shape = slide.shapes.add_shape(1, x, y, w, h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        
        txBox = slide.shapes.add_textbox(x + Inches(0.2), y + Inches(0.2), w - Inches(0.4), h - Inches(0.4))
        tf = txBox.text_frame
        tf.word_wrap = True
        
        p = tf.paragraphs[0]
        p.text = title
        p.font.size = Pt(16)
        p.font.color.rgb = WHITE
        p.font.bold = True
        
        p2 = tf.add_paragraph()
        p2.text = "\n" + desc
        p2.font.size = Pt(12)
        p2.font.color.rgb = RGBColor(0xEE, 0xEE, 0xEE)


def _slide_roi_projection(prs, stats):
    """ROI projection slide."""
    slide = _add_slide(prs, "ROI Projection", "Estimated Savings Over 12-24 Months")
    
    total = stats.get("total_tickets", 0)
    can_auto = stats.get("can_be_automated", 0)
    
    # Conservative estimates
    cost_per_ticket = 15  # USD
    automation_reduction = 0.6  # 60% ticket reduction
    monthly_tickets = total / 12  # Assume 12 months of data
    
    monthly_savings = monthly_tickets * automation_reduction * cost_per_ticket * (can_auto / max(total, 1))
    annual_savings = monthly_savings * 12
    
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(12), Inches(5.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    
    lines = [
        f"Tickets Analyzed: {total:,}",
        f"Automation Candidates: {can_auto:,}",
        f"",
        f"Assumptions:",
        f"  • Average cost per ticket: ${cost_per_ticket}",
        f"  • Expected ticket reduction: {automation_reduction*100:.0f}%",
        f"  • Monthly ticket volume: {monthly_tickets:,.0f}",
        f"",
        f"Projected Savings:",
        f"  • 12 Months: ${annual_savings:,.0f}",
        f"  • 24 Months: ${annual_savings * 2:,.0f}",
        f"",
        f"Note: Actual savings depend on implementation scope and ticket complexity.",
    ]
    
    for i, line in enumerate(lines):
        if i == 0:
            tf.paragraphs[0].text = line
            tf.paragraphs[0].font.size = Pt(16)
            tf.paragraphs[0].font.color.rgb = GRAY
        else:
            p = tf.add_paragraph()
            p.text = line
            p.font.size = Pt(16) if "Projected" in line or "$" in line else Pt(14)
            p.font.color.rgb = BRAND_BLUE if "$" in line else GRAY
            p.font.bold = "$" in line


def _slide_appendix(prs, stats, pivots):
    """Appendix with data summary."""
    slide = _add_slide(prs, "Appendix — Data Summary")
    
    txBox = slide.shapes.add_textbox(Inches(0.5), Inches(1.5), Inches(12), Inches(5.5))
    tf = txBox.text_frame
    tf.word_wrap = True
    
    tower_dist = stats.get("tower_distribution", {})
    
    lines = [
        f"Upload: {stats.get('filename', 'N/A')}",
        f"Record Type: {stats.get('record_type', 'N/A')}",
        f"Total Tickets: {stats.get('total_tickets', 0):,}",
        f"Average MTTR: {stats.get('avg_mttr_hours', 0):.2f} hours",
        f"ML Confidence: {stats.get('avg_aio_confidence', 0):.1%}",
        f"Needs Review: {stats.get('needs_review', 0)} tickets",
        f"",
        f"Tower Distribution:",
    ]
    
    for tower, count in sorted(tower_dist.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"  {tower}: {count:,}")
    
    for i, line in enumerate(lines):
        if i == 0:
            tf.paragraphs[0].text = line
            tf.paragraphs[0].font.size = Pt(14)
        else:
            p = tf.add_paragraph()
            p.text = line
            p.font.size = Pt(14)
            p.font.color.rgb = GRAY