import re
import pandas as pd
from sqlalchemy import case

# ---------------------------------------------------------------------------
# Priority normalisation
# ITSM tools export priority in many shapes: "1 - Critical", "P1", "Critical", "1".
# Everything downstream works on the canonical levels P1..P4.
# Patterns are written in the subset of regex syntax shared by Python and
# PostgreSQL so the same rules drive both in-memory and SQL-side grouping.
# ---------------------------------------------------------------------------
PRIORITY_PATTERNS = [
    ("P1", r"^\s*p?\s*1([^0-9]|$)|critical|urgent"),
    ("P2", r"^\s*p?\s*2([^0-9]|$)|high"),
    ("P3", r"^\s*p?\s*3([^0-9]|$)|moderate|medium"),
    ("P4", r"^\s*p?\s*4([^0-9]|$)|low|planning"),
]

# Resolution SLA targets in hours per canonical priority
SLA_HOURS = {"P1": 4.0, "P2": 8.0, "P3": 24.0, "P4": 72.0}


def normalize_priority(priority) -> str:
    """Map any priority label to P1..P4, or "Unknown" if it can't be read."""
    if priority is None:
        return "Unknown"
    text = str(priority).lower()
    for level, pattern in PRIORITY_PATTERNS:
        if re.search(pattern, text):
            return level
    return "Unknown"


def priority_level_sql(column):
    """SQL CASE expression mapping a priority column to P1..P4 (PostgreSQL regex)."""
    return case(
        *[(column.op("~*")(pattern), level) for level, pattern in PRIORITY_PATTERNS],
        else_="Unknown",
    )


def sla_breach_sql(priority_column, mttr_column):
    """SQL boolean: ticket resolved slower than the SLA for its priority."""
    level = priority_level_sql(priority_column)
    return mttr_column > case(
        *[(level == lvl, hours) for lvl, hours in SLA_HOURS.items()],
        else_=SLA_HOURS["P3"],
    )


# Comprehensive column mappings based on ServiceNow/Jira/BMC standards
COLUMN_MAPPINGS = {
    # Ticket Identification
    'ticket_number': ['number', 'ticket_number', 'ticket_id', 'incident_number', 'inc_number', 'sys_id'],
    
    # Categorization (Type of Issue)
    'category': ['category', 'service_offering', 'ci_category', 'issue_type', 'type'],
    'subcategory': ['subcategory', 'u_subcategory', 'service_component'],
    
    # Assignment (Who handles it)
    'assignment_group': ['assignment_group', 'assigned_group', 'support_group', 'team', 'group_name'],
    'assigned_to': ['assigned_to', 'assignee', 'resolver', 'technician'],
    
    # Priority & Impact
    'priority': ['priority', 'ticket_priority'],
    'urgency': ['urgency'],
    'impact': ['impact'],
    
    # Description
    'short_description': ['short_description', 'summary', 'subject', 'title'],
    'description': ['description', 'details', 'long_description', 'notes'],
    'close_notes': ['close_notes', 'resolution_notes', 'work_notes', 'close_code'],
    
    # Contact Information
    'contact_type': ['contact_type', 'source', 'channel', 'origin'],  # Phone, Email, Portal, etc.
    'caller_id': ['caller_id', 'opened_by', 'reporter', 'requester'],
    
    # Dates
    'created_at': ['created_at', 'opened_at', 'created', 'open_time', 'sys_created_on', 'opened'],
    'resolved_at': ['resolved_at', 'closed_at', 'resolved', 'close_time', 'sys_resolved_at', 'closed'],
    'updated_at': ['updated_at', 'sys_updated_on', 'modified'],
    
    # Status & State
    'state': ['state', 'status', 'incident_state'],
    
    # Business Context
    'configuration_item': ['configuration_item', 'cmdb_ci', 'ci', 'asset'],
    'location': ['location', 'site', 'office'],
    'company': ['company', 'organization', 'client'],
    
    # Performance Metrics
    'reassignment_count': ['reassignment_count', 'reassigned', 'transfer_count'],
}

def map_csv_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Auto-detect and map CSV columns to standard format
    Handles ServiceNow, Jira, BMC Remedy variations
    """
    column_mapping = {}
    
    # Convert all column names to lowercase for matching
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    
    # Find matches
    for standard_col, possible_names in COLUMN_MAPPINGS.items():
        for col in df.columns:
            if col in [name.lower() for name in possible_names]:
                column_mapping[col] = standard_col
                break
    
    # Rename columns
    df = df.rename(columns=column_mapping)
    
    # Check if required columns exist
    required = ['ticket_number', 'assignment_group', 'created_at']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise ValueError(f"Missing required columns: {missing}.\nFound columns: {list(df.columns)}")
    
    return df

# ---------------------------------------------------------------------------
# Automation savings
# Two explicit assumptions, returned with every figure so the UI can show them.
# Monthly figures are normalised by the period the dump actually covers.
# ---------------------------------------------------------------------------
EFFORT_MINUTES_PER_TICKET = 15   # analyst hands-on time removed per automated ticket
HOURLY_COST_INR = 850            # blended cost of an analyst hour

AVG_DAYS_PER_MONTH = 30.44


def months_covered(first_opened, last_opened) -> float:
    """Length of the dump in months (minimum one month)."""
    if first_opened is None or last_opened is None:
        return 1.0
    days = (last_opened - first_opened).total_seconds() / 86400
    return max(days / AVG_DAYS_PER_MONTH, 1.0)


def ticket_effort_saving_inr(can_automate: bool) -> float:
    """Saving from automating one ticket: the analyst effort it removes, not its calendar duration."""
    return round(EFFORT_MINUTES_PER_TICKET / 60 * HOURLY_COST_INR, 2) if can_automate else 0.0


def automation_savings(can_automate: int, months: float) -> dict:
    hours_per_month = can_automate * EFFORT_MINUTES_PER_TICKET / 60 / months
    monthly_inr = hours_per_month * HOURLY_COST_INR
    return {
        "hours_saved_monthly": round(hours_per_month, 0),
        "monthly_savings_inr": round(monthly_inr, 0),
        "annual_savings_inr": round(monthly_inr * 12, 0),
        "assumptions": {
            "effort_minutes_per_ticket": EFFORT_MINUTES_PER_TICKET,
            "hourly_cost_inr": HOURLY_COST_INR,
            "months_covered": round(months, 1),
        },
    }


# ---------------------------------------------------------------------------
# Dump type detection (from content only; the file name is never used)
# ---------------------------------------------------------------------------
RECORD_TYPES = {
    "incident": {"label": "Incident", "prefixes": ("INC",),
                 "columns": {"impact", "urgency", "caller_id", "caller", "incident_state", "severity"}},
    "request": {"label": "Service Request", "prefixes": ("RITM", "REQ", "SCTASK", "SR"),
                "columns": {"cat_item", "catalog_item", "catalog", "requested_for", "approval", "stage", "request"}},
    "change": {"label": "Change", "prefixes": ("CHG", "CTASK"),
               "columns": {"start_date", "end_date", "planned_start", "planned_end", "cab_required",
                           "implementation_plan", "backout_plan", "risk", "change_type", "type_of_change"}},
    "problem": {"label": "Problem", "prefixes": ("PRB", "PTASK"),
                "columns": {"root_cause", "known_error", "workaround", "cause_notes", "problem_state"}},
}
_TICKET_COLUMNS = ("number", "ticket_number", "incident_number", "ticket_id", "id")


def detect_dump_content(df: pd.DataFrame) -> dict:
    """
    Classify a ticket export as incident / request / change / problem (or mixed)
    from its ticket-number prefixes (every row) and type-specific columns.
    Returns type, label, confidence, per-type mix of ticket numbers and the evidence used.
    """
    cols = {str(c).strip().lower().replace(" ", "_") for c in df.columns}
    evidence, scores = [], {t: 0.0 for t in RECORD_TYPES}

    mix = {}
    num_col = next((c for c in df.columns if str(c).strip().lower().replace(" ", "_") in _TICKET_COLUMNS), None)
    if num_col is not None:
        numbers = df[num_col].dropna().astype(str).str.upper().str.strip()
        if len(numbers):
            for rtype, spec in RECORD_TYPES.items():
                share = float(numbers.str.startswith(spec["prefixes"]).mean())
                if share > 0:
                    mix[rtype] = round(share, 4)
                    scores[rtype] += 2 * share
            if mix:
                top = max(mix, key=mix.get)
                evidence.append(f"{mix[top]:.0%} of ticket numbers start with "
                                f"{'/'.join(RECORD_TYPES[top]['prefixes'])}")

    for rtype, spec in RECORD_TYPES.items():
        found = sorted(cols & spec["columns"])
        if found:
            scores[rtype] += min(len(found), 3) / 3
            evidence.append(f"{spec['label'].lower()} columns: {', '.join(found[:4])}")

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return {"type": "unknown", "label": "Ticket", "confidence": 0.0, "mix": {}, "evidence": ["no type-specific prefixes or columns found"]}
    total = sum(scores.values())
    secondary = [t for t, s in mix.items() if t != best and s >= 0.1]
    rtype = "mixed" if secondary else best
    label = ("Mixed: " + ", ".join(f"{RECORD_TYPES[t]['label']} {mix[t]:.0%}" for t in sorted(mix, key=mix.get, reverse=True))
             if rtype == "mixed" else RECORD_TYPES[best]["label"])
    return {"type": rtype, "primary": best, "label": label,
            "confidence": round(scores[best] / total, 3), "mix": mix, "evidence": evidence}
