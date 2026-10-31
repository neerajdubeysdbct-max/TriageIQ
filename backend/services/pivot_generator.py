"""
pivot_generator.py (v2)
========================
Generates auto-pivot charts for Ticket Intelligence.

Changes from v1:
  - Clean labels (no "AIO" prefix in chart titles)
  - Dynamic taxonomy (reads from actual DB data)
  - New pivots: Channel analysis, Priority split, Quick Wins
  - Custom pivot supports new fields (channel, resolved_by, aio_detail)
"""

from sqlalchemy import func, case, or_, and_
from collections import defaultdict
from typing import Dict, List, Optional
from models import Ticket


# ============================================================
# AUTO-PIVOT GENERATION (12 charts)
# ============================================================

def generate_all_pivots(upload_id: int, db) -> List[Dict]:
    """Generate 12 auto-pivot datasets for charts."""
    pivots = []
    
    try:
        # 1. Volume by Tower (bar)
        tower_data = (
            db.query(Ticket.aio_tower, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.aio_tower.isnot(None), Ticket.aio_tower != '')
            .group_by(Ticket.aio_tower)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )
        pivots.append({
            "id": "tower_volume",
            "title": "Volume by Tower",
            "chart_type": "bar",
            "data": [{"name": r[0], "count": r[1]} for r in tower_data],
            "x_key": "name", "y_key": "count",
        })

        # 2. Volume by Category (bar)
        cat_data = (
            db.query(Ticket.aio_category, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.aio_category.isnot(None), Ticket.aio_category != '')
            .group_by(Ticket.aio_category)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )
        pivots.append({
            "id": "category_volume",
            "title": "Volume by Category",
            "chart_type": "bar",
            "data": [{"name": r[0], "count": r[1]} for r in cat_data],
            "x_key": "name", "y_key": "count",
        })

        # 3. Top 20 SubCategories (horizontal bar)
        subcat_data = (
            db.query(Ticket.aio_subcategory, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.aio_subcategory.isnot(None), Ticket.aio_subcategory != '')
            .group_by(Ticket.aio_subcategory)
            .order_by(func.count(Ticket.id).desc())
            .limit(20).all()
        )
        pivots.append({
            "id": "top_subcategories",
            "title": "Top 20 Sub Categories",
            "chart_type": "horizontal_bar",
            "data": [{"name": r[0], "count": r[1]} for r in subcat_data],
            "x_key": "count", "y_key": "name",
        })

        # 4. Tower × Automation Status (stacked bar)
        tower_auto = (
            db.query(
                Ticket.aio_tower,
                func.sum(case((Ticket.is_already_automated == True, 1), else_=0)).label('already'),
                func.sum(case((and_(Ticket.can_be_automated == True, Ticket.is_already_automated == False), 1), else_=0)).label('can_be'),
                func.sum(case((and_(Ticket.is_already_automated == False, Ticket.can_be_automated == False), 1), else_=0)).label('manual'),
            )
            .filter(Ticket.upload_id == upload_id, Ticket.aio_tower.isnot(None), Ticket.aio_tower != '')
            .group_by(Ticket.aio_tower)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )
        pivots.append({
            "id": "tower_automation",
            "title": "Tower × Automation Status",
            "chart_type": "stacked_bar",
            "data": [{"tower": r[0], "Already Automated": r[1], "Can Be Automated": r[2], "Manual": r[3]} for r in tower_auto],
            "x_key": "tower",
            "series": ["Already Automated", "Can Be Automated", "Manual"],
        })

        # 5. Channel Distribution (bar)
        channel_data = (
            db.query(Ticket.channel, func.count(Ticket.id))
            .filter(Ticket.upload_id == upload_id, Ticket.channel.isnot(None), Ticket.channel != '')
            .group_by(Ticket.channel)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )
        pivots.append({
            "id": "channel_volume",
            "title": "Volume by Channel",
            "chart_type": "bar",
            "data": [{"name": r[0], "count": r[1]} for r in channel_data],
            "x_key": "name", "y_key": "count",
        })

        # 6. Tower × Avg MTTR (table/heatmap)
        tower_mttr = (
            db.query(
                Ticket.aio_tower,
                func.avg(Ticket.mttr_hours).label('avg_mttr'),
                func.min(Ticket.mttr_hours).label('min_mttr'),
                func.max(Ticket.mttr_hours).label('max_mttr'),
                func.count(Ticket.id).label('count'),
            )
            .filter(
                Ticket.upload_id == upload_id,
                Ticket.aio_tower.isnot(None), Ticket.aio_tower != '',
                Ticket.mttr_hours.isnot(None), Ticket.mttr_hours > 0, Ticket.mttr_hours < 720
            )
            .group_by(Ticket.aio_tower)
            .order_by(func.avg(Ticket.mttr_hours).desc())
            .all()
        )
        pivots.append({
            "id": "tower_mttr",
            "title": "Tower × Avg MTTR (hours)",
            "chart_type": "table",
            "data": [{
                "tower": r[0],
                "avg_mttr": round(float(r[1]), 2),
                "min_mttr": round(float(r[2]), 2),
                "max_mttr": round(float(r[3]), 2),
                "count": r[4],
            } for r in tower_mttr],
        })

        # 7. Assignment Group × Tower (top 15 groups)
        group_tower = (
            db.query(Ticket.assignment_group, Ticket.aio_tower, func.count(Ticket.id))
            .filter(
                Ticket.upload_id == upload_id,
                Ticket.assignment_group.isnot(None), Ticket.assignment_group != '',
                Ticket.aio_tower.isnot(None), Ticket.aio_tower != ''
            )
            .group_by(Ticket.assignment_group, Ticket.aio_tower)
            .all()
        )
        # Pivot into matrix
        group_totals = defaultdict(int)
        matrix = defaultdict(lambda: defaultdict(int))
        for group, tower, count in group_tower:
            group_totals[group] += count
            matrix[group][tower] = count

        top_groups = sorted(group_totals.keys(), key=lambda g: group_totals[g], reverse=True)[:15]
        all_towers = sorted(set(t for g in top_groups for t in matrix[g].keys()))

        group_tower_data = []
        for g in top_groups:
            row = {"assignment_group": g, "total": group_totals[g]}
            for t in all_towers:
                row[t] = matrix[g].get(t, 0)
            group_tower_data.append(row)

        pivots.append({
            "id": "group_tower",
            "title": "Assignment Group × Tower",
            "chart_type": "table",
            "data": group_tower_data,
        })

        # 8. Monthly Trend by Tower (line)
        try:
            monthly = (
                db.query(
                    func.to_char(Ticket.opened, 'YYYY-MM').label('month'),
                    Ticket.aio_tower,
                    func.count(Ticket.id)
                )
                .filter(
                    Ticket.upload_id == upload_id,
                    Ticket.opened.isnot(None),
                    Ticket.aio_tower.isnot(None), Ticket.aio_tower != ''
                )
                .group_by('month', Ticket.aio_tower)
                .order_by('month')
                .all()
            )

            months_set = sorted(set(r[0] for r in monthly))
            towers_set = sorted(set(r[1] for r in monthly))
            monthly_matrix = defaultdict(lambda: defaultdict(int))
            for month, tower, count in monthly:
                monthly_matrix[month][tower] = count

            line_data = []
            for month in months_set:
                row = {"month": month}
                for tower in towers_set:
                    row[tower] = monthly_matrix[month].get(tower, 0)
                line_data.append(row)

            pivots.append({
                "id": "monthly_trend",
                "title": "Monthly Trend by Tower",
                "chart_type": "line",
                "data": line_data,
                "x_key": "month",
                "series": towers_set,
            })
        except Exception:
            pass  # Skip if date functions not supported

        # 9. Solution Lever Distribution (bar)
        lever_data = (
            db.query(Ticket.aiops_solution_lever, func.count(Ticket.id))
            .filter(
                Ticket.upload_id == upload_id,
                Ticket.aiops_solution_lever.isnot(None),
                Ticket.aiops_solution_lever != '',
                Ticket.aiops_solution_lever != 'Manual Process'
            )
            .group_by(Ticket.aiops_solution_lever)
            .order_by(func.count(Ticket.id).desc())
            .all()
        )
        pivots.append({
            "id": "solution_lever",
            "title": "Recommended Actions Distribution",
            "chart_type": "bar",
            "data": [{"name": r[0], "count": r[1]} for r in lever_data],
            "x_key": "name", "y_key": "count",
        })

        # 10. Quick Wins — Top automatable subcategories (table)
        quick_wins = (
            db.query(
                Ticket.aio_subcategory,
                func.count(Ticket.id).label('total'),
                func.sum(case((Ticket.is_already_automated == True, 1), else_=0)).label('already'),
                func.sum(case((and_(Ticket.can_be_automated == True, Ticket.is_already_automated == False), 1), else_=0)).label('can_be'),
                func.sum(case((and_(Ticket.is_already_automated == False, Ticket.can_be_automated == False), 1), else_=0)).label('manual'),
                func.avg(Ticket.mttr_hours).label('avg_mttr'),
            )
            .filter(
                Ticket.upload_id == upload_id,
                Ticket.aio_subcategory.isnot(None), Ticket.aio_subcategory != ''
            )
            .group_by(Ticket.aio_subcategory)
            .having(func.count(Ticket.id) >= 10)
            .order_by(func.count(Ticket.id).desc())
            .limit(20).all()
        )
        pivots.append({
            "id": "quick_wins",
            "title": "Automation by Sub Category (Quick Wins)",
            "chart_type": "table",
            "data": [{
                "sub_category": r[0],
                "total": r[1],
                "already_automated": r[2],
                "can_automate": r[3],
                "manual": r[4],
                "automation_pct": round((r[2] + r[3]) / max(r[1], 1) * 100, 1),
                "avg_mttr": round(float(r[5] or 0), 2),
                "est_savings": round(r[3] * float(r[5] or 0) * 15 * 0.7, 0),
            } for r in quick_wins],
        })

        # 11. Priority × Automation (stacked bar)
        priority_auto = (
            db.query(
                Ticket.priority,
                func.sum(case((Ticket.is_already_automated == True, 1), else_=0)).label('already'),
                func.sum(case((and_(Ticket.can_be_automated == True, Ticket.is_already_automated == False), 1), else_=0)).label('can_be'),
                func.sum(case((and_(Ticket.is_already_automated == False, Ticket.can_be_automated == False), 1), else_=0)).label('manual'),
            )
            .filter(Ticket.upload_id == upload_id, Ticket.priority.isnot(None))
            .group_by(Ticket.priority)
            .order_by(Ticket.priority)
            .all()
        )
        pivots.append({
            "id": "priority_automation",
            "title": "Priority × Automation Status",
            "chart_type": "stacked_bar",
            "data": [{"priority": r[0], "Already Automated": r[1], "Can Be Automated": r[2], "Manual": r[3]} for r in priority_auto],
            "x_key": "priority",
            "series": ["Already Automated", "Can Be Automated", "Manual"],
        })

        # 12. Channel × Automation (stacked bar)
        channel_auto = (
            db.query(
                Ticket.channel,
                func.sum(case((Ticket.is_already_automated == True, 1), else_=0)).label('already'),
                func.sum(case((and_(Ticket.can_be_automated == True, Ticket.is_already_automated == False), 1), else_=0)).label('can_be'),
                func.sum(case((and_(Ticket.is_already_automated == False, Ticket.can_be_automated == False), 1), else_=0)).label('manual'),
            )
            .filter(Ticket.upload_id == upload_id, Ticket.channel.isnot(None), Ticket.channel != '')
            .group_by(Ticket.channel)
            .order_by(func.count(Ticket.id).desc())
            .limit(10).all()
        )
        pivots.append({
            "id": "channel_automation",
            "title": "Channel × Automation Status",
            "chart_type": "stacked_bar",
            "data": [{"channel": r[0], "Already Automated": r[1], "Can Be Automated": r[2], "Manual": r[3]} for r in channel_auto],
            "x_key": "channel",
            "series": ["Already Automated", "Can Be Automated", "Manual"],
        })

    except Exception as e:
        print(f"Pivot generation error: {e}")
        import traceback
        traceback.print_exc()

    return pivots


# ============================================================
# CUSTOM PIVOT (drag-and-drop builder)
# ============================================================

ALLOWED_FIELDS = {
    'aio_tower', 'aio_category', 'aio_subcategory', 'aio_detail',
    'aiops_solution_lever', 'aiops_automation_status',
    'is_already_automated', 'can_be_automated',
    'assignment_group', 'category', 'subcategory', 'priority',
    'channel', 'cluster_id', 'resolved_by', 'state',
}


def generate_custom_pivot(upload_id: int, config: dict, db) -> Dict:
    """Generate custom pivot from user configuration."""
    rows = config.get('rows', [])
    columns = config.get('columns', [])
    values = config.get('values', 'count')
    filters = config.get('filters', {})

    if not rows:
        return {"error": "At least one row field required", "data": []}

    # Validate fields
    all_fields = rows + columns
    for f in all_fields:
        if f not in ALLOWED_FIELDS:
            return {"error": f"Invalid field: {f}", "data": []}

    # Build query
    group_cols = [getattr(Ticket, f) for f in all_fields]
    
    if values == 'count':
        value_col = func.count(Ticket.id).label('value')
    elif values == 'avg_mttr':
        value_col = func.avg(Ticket.mttr_hours).label('value')
    elif values == 'sum_mttr':
        value_col = func.sum(Ticket.mttr_hours).label('value')
    else:
        value_col = func.count(Ticket.id).label('value')

    q = db.query(*group_cols, value_col).filter(Ticket.upload_id == upload_id)

    # Apply filters
    for field, val in filters.items():
        if field in ALLOWED_FIELDS and val:
            q = q.filter(getattr(Ticket, field) == val)

    q = q.group_by(*group_cols).order_by(value_col.desc()).limit(500)

    results = q.all()

    data = []
    for r in results:
        row = {}
        for i, f in enumerate(all_fields):
            row[f] = r[i] if r[i] is not None else ''
        row['value'] = round(float(r[-1]), 2) if r[-1] is not None else 0
        data.append(row)

    title_parts = [f.replace('aio_', '').replace('aiops_', '').replace('_', ' ').title() for f in rows]
    col_parts = [f.replace('aio_', '').replace('aiops_', '').replace('_', ' ').title() for f in columns] if columns else []
    
    title = f"Custom: {' × '.join(title_parts)}"
    if col_parts:
        title += f" by {' × '.join(col_parts)}"

    return {
        "title": title,
        "data": data,
        "rows": rows,
        "columns": columns,
        "values": values,
        "total_rows": len(data),
    }