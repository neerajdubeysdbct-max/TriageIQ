"""
Structured data tools for numeric questions. The LLM chooses a metric, an optional
group-by dimension and filters from fixed lists; the query is built here from
whitelisted SQLAlchemy expressions with bound parameters, so model output never
becomes SQL text.
"""

import re
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, cast, func

from models import SessionLocal, Ticket
from utils import priority_level_sql, sla_breach_sql

DIMENSIONS = {
    "priority": lambda: priority_level_sql(Ticket.priority),
    "team": lambda: Ticket.assignment_group,
    "channel": lambda: func.coalesce(Ticket.channel, Ticket.contact_type),
    "category": lambda: func.coalesce(Ticket.l2_subcategory, Ticket.category),
    "automation_status": lambda: Ticket.aiops_automation_status,
    "resolver": lambda: Ticket.resolved_by,
    "month": lambda: func.to_char(func.date_trunc("month", Ticket.opened), "YYYY-MM"),
    "theme": lambda: Ticket.cluster_id,
}

METRICS = {
    "count": lambda: func.count(Ticket.id),
    "avg_resolution_hours": lambda: func.avg(Ticket.mttr_hours),
    "sla_breach_rate": lambda: func.avg(case((sla_breach_sql(Ticket.priority, Ticket.mttr_hours), 1.0), else_=0.0)),
    "automatable_rate": lambda: func.avg(case((Ticket.aiops_automation_status.in_(
        ["Already Automated", "Can Be Automated"]), 1.0), else_=0.0)),
}

METRIC_LABELS = {"count": "tickets", "avg_resolution_hours": "average resolution hours",
                 "sla_breach_rate": "share breaching SLA", "automatable_rate": "share automatable"}


class AggregateQuery(BaseModel):
    metric: str = "count"
    group_by: Optional[str] = None
    filters: Dict[str, str] = Field(default_factory=dict)
    top: int = 10
    order: str = "desc"

    @field_validator("group_by", mode="before")
    @classmethod
    def _group_none(cls, v):
        return None if v in (None, "", "null", "none") else v

    @field_validator("filters", mode="before")
    @classmethod
    def _filters_clean(cls, v):
        # models often return every dimension with a null value; keep only real filters
        if not isinstance(v, dict):
            return {}
        return {k: str(val) for k, val in v.items() if val not in (None, "", "null", "all", "any")}

    @field_validator("metric")
    @classmethod
    def _metric(cls, v):
        if v not in METRICS:
            raise ValueError(f"metric must be one of {list(METRICS)}")
        return v

    @field_validator("group_by")
    @classmethod
    def _group(cls, v):
        if v is not None and v not in DIMENSIONS:
            raise ValueError(f"group_by must be one of {list(DIMENSIONS)}")
        return v

    @field_validator("filters")
    @classmethod
    def _filters(cls, v):
        bad = [k for k in v if k not in DIMENSIONS]
        if bad:
            raise ValueError(f"unknown filter dimensions {bad}")
        return {k: str(val)[:100] for k, val in v.items()}

    @field_validator("top")
    @classmethod
    def _top(cls, v):
        return max(1, min(int(v), 25))

    @field_validator("order")
    @classmethod
    def _order(cls, v):
        return "asc" if str(v).lower() == "asc" else "desc"


def run_aggregate(upload_id: int, team_id: str, q: AggregateQuery) -> Dict:
    metric = METRICS[q.metric]()
    db = SessionLocal()
    try:
        base = [Ticket.upload_id == upload_id, Ticket.team_id == team_id]
        if q.metric in ("avg_resolution_hours", "sla_breach_rate"):
            base += [Ticket.mttr_hours != None, Ticket.mttr_hours > 0]
        for dim, value in q.filters.items():
            expr = DIMENSIONS[dim]()
            base.append(func.lower(cast(expr, Ticket.assignment_group.type)).like(f"%{value.lower()}%"))
        if q.group_by is None:
            value = db.query(metric).filter(*base).scalar()
            rows = [{"value": _round(value, q.metric)}]
        else:
            dim = DIMENSIONS[q.group_by]()
            if q.group_by == "month":
                order = dim.asc() if q.order == "asc" else dim.desc()   # chronological
            else:
                order = metric.desc() if q.order == "desc" else metric.asc()
            # every grouped row also carries its average resolution time, for compound questions
            # such as "which resolver closes most tickets and what is their MTTR"
            avg_hours = func.avg(case((Ticket.mttr_hours > 0, Ticket.mttr_hours)))
            result = db.query(dim.label("key"), metric.label("value"), func.count(Ticket.id).label("n"),
                              avg_hours.label("avg_hours")) \
                .filter(*base).group_by(dim).order_by(order).limit(q.top).all()
            rows = [{"key": str(r.key), "value": _round(r.value, q.metric), "tickets": int(r.n),
                     "avg_hours": _round(r.avg_hours, "avg_resolution_hours")} for r in result]
        baseline = None
        if q.filters and q.metric != "count":
            unfiltered = [Ticket.upload_id == upload_id, Ticket.team_id == team_id]
            if q.metric in ("avg_resolution_hours", "sla_breach_rate"):
                unfiltered += [Ticket.mttr_hours != None, Ticket.mttr_hours > 0]
            baseline = _round(db.query(METRICS[q.metric]()).filter(*unfiltered).scalar(), q.metric)
        return {"query": q.model_dump(), "description": describe_query(q.model_dump()),
                "metric_label": METRIC_LABELS[q.metric], "rows": rows, "baseline": baseline}
    finally:
        db.close()


def _round(v, metric: str = ""):
    """Hours to 2 decimals; shares keep 4 so they can be shown as a percentage to 2 decimals."""
    if v is None:
        return None
    if isinstance(v, int):
        return v
    return round(float(v), 2 if metric == "avg_resolution_hours" else 4)


def describe_tools() -> str:
    return (
        "aggregate(metric, group_by, filters, top, order)\n"
        f"  metric: one of {list(METRICS)}\n"
        f"  group_by: null or one of {list(DIMENSIONS)}\n"
        f"  filters: object mapping any of {list(DIMENSIONS)} to a text value (substring match), e.g. "
        '{"priority": "P1"} or {"team": "service desk"}\n'
        "  top: 1-25 rows, order: desc or asc"
    )


METRIC_PHRASES = {"count": "Number of tickets", "avg_resolution_hours": "Average resolution time (hours)",
                  "sla_breach_rate": "Share of tickets that breached their SLA",
                  "automatable_rate": "Share of tickets that are automated or automatable"}


def describe_query(q: Dict) -> str:
    """Plain-English description of a query, so the answer model knows what each number means."""
    text = METRIC_PHRASES[q["metric"]]
    if q.get("filters"):
        text += " where " + " and ".join(f"{k} matches '{v}'" for k, v in q["filters"].items())
    if q.get("group_by"):
        text += f", per {q['group_by'].replace('_', ' ')}"
        if q["group_by"] != "month":
            direction = "highest" if q.get("order", "desc") == "desc" else "lowest"
            text += f", the {q.get('top', 10)} {direction} by this measure only"
    return text


# Dimensions whose values are matched literally in the question (entity linking)
LINKABLE = ("team", "channel", "resolver")
_PRIORITY_IN_TEXT = re.compile(r"\bP([1-4])\b|\bpriority\s*([1-4])\b", re.I)


def link_entities(upload_id: int, team_id: str, question: str, q: AggregateQuery) -> List[str]:
    """
    Add filters for values the question names but the planner left out, e.g. a team
    name. Values come from this dataset, longest first, so 'App Support L3' wins over
    'App Support'. Returns the dimensions that were added.
    """
    added = []
    text = question.lower()
    m = _PRIORITY_IN_TEXT.search(question)
    if m and "priority" not in q.filters and q.group_by != "priority":
        q.filters["priority"] = f"P{m.group(1) or m.group(2)}"
        added.append("priority")
    db = SessionLocal()
    try:
        for dim in LINKABLE:
            if dim in q.filters or q.group_by == dim:
                continue
            expr = DIMENSIONS[dim]()
            values = [v for (v,) in db.query(expr).filter(Ticket.upload_id == upload_id, Ticket.team_id == team_id)
                      .distinct().all() if v and len(v) >= 3]
            for v in sorted(values, key=len, reverse=True):
                if re.search(rf"(?<![\w.]){re.escape(v.lower())}(?![\w.])", text):
                    q.filters[dim] = v
                    added.append(dim)
                    break
    finally:
        db.close()
    return added


def format_table(result: Dict) -> str:
    rows: List[Dict] = result["rows"]
    q = result["query"]
    lines = [describe_query(q) + ":"]
    if not rows:
        lines.append("no matching tickets")
    elif "key" not in rows[0]:
        lines.append(str(rows[0]["value"]))
    else:
        if q["metric"] == "avg_resolution_hours":
            lines.append(f"{q['group_by']} | average resolution hours | tickets")
            lines += [f"{r['key']} | {r['value']} | {r['tickets']}" for r in rows]
        else:
            lines.append(f"{q['group_by']} | {METRIC_LABELS[q['metric']]} | tickets | average resolution hours")
            lines += [f"{r['key']} | {r['value']} | {r['tickets']} | {r.get('avg_hours')}" for r in rows]
    if result.get("baseline") is not None:
        lines.append(f"For comparison, {METRIC_PHRASES[q['metric']].lower()} over all tickets: {result['baseline']}")
    return "\n".join(lines)
