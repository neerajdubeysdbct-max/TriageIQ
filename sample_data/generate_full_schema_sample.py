"""
A 1,000-ticket synthetic dump with the full set of columns seen in real ServiceNow
incident exports: every column of the real customer dumps the tool was built on
(same names, same order), plus the richer fields of the Northwind generator and a
few standard export fields (impact, urgency, made_sla, opened_by, closed_by).

All values are synthetic (fictional "Northwind Retail"); only column names follow
the real exports. Ground truth is written alongside, as for the other dumps.

    python generate_full_schema_sample.py            # writes northwind_full_* files
"""

import os

import numpy as np
import pandas as pd

from generate_synthetic_tickets import FIRST, LAST, generate, plant_anomalies

# Column order of the real exports, then the extra columns
REAL_EXPORT_COLUMNS = [
    "number", "business_service.ref_cmdb_ci_service_auto.u_service_offerings", "cmdb_ci", "opened_at",
    "short_description", "caller_id", "priority", "state", "category", "assignment_group", "assigned_to",
    "sys_updated_on", "sys_updated_by", "business_service.company", "business_service.business_unit",
    "resolved_at", "calendar_duration", "business_duration", "resolved_by",
]
EXTRA_COLUMNS = [
    "description", "close_notes", "subcategory", "contact_type", "impact", "urgency", "made_sla",
    "reassignment_count", "reopen_count", "location", "opened_by", "closed_by", "closed_at",
]

SERVICE_OFFERINGS = {
    "Network": "Store Network Services", "Database": "Database Hosting", "Hardware": "End User Computing",
    "Software": "Business Applications", "Access Management": "Identity and Access", "Email": "Collaboration",
    "Security": "Security Operations", "Server": "Server Hosting", "Application": "Business Applications",
}
COMPANIES = ["Northwind Retail", "Northwind Logistics", "Northwind Finance Services"]
BUSINESS_UNITS = ["Stores", "Supply Chain", "Finance", "HR", "E-commerce", "Corporate IT"]
SLA_HOURS = {"1": 4, "2": 8, "3": 24, "4": 72}
IMPACT_URGENCY = {"1": [("1 - High", "1 - High")], "2": [("1 - High", "2 - Medium"), ("2 - Medium", "1 - High")],
                  "3": [("2 - Medium", "2 - Medium"), ("1 - High", "3 - Low"), ("3 - Low", "1 - High")],
                  "4": [("3 - Low", "3 - Low"), ("2 - Medium", "3 - Low"), ("3 - Low", "2 - Medium")]}
FMT = "%Y-%m-%d %H:%M:%S"


def add_export_columns(df: pd.DataFrame, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n = len(df)
    p = df["priority"].astype(str).str[0]

    offering = df["category"].map(SERVICE_OFFERINGS).fillna("General IT Support")
    df["business_service.ref_cmdb_ci_service_auto.u_service_offerings"] = offering.where(rng.random(n) < 0.2, "")
    has_company = rng.random(n) < 0.31
    df["business_service.company"] = np.where(has_company, rng.choice(COMPANIES, n), "")
    df["business_service.business_unit"] = np.where(has_company, rng.choice(BUSINESS_UNITS, n), "")

    resolved = pd.to_datetime(df["resolved_at"])
    closed = pd.to_datetime(df["closed_at"]) if "closed_at" in df else resolved
    df["sys_updated_on"] = (closed + pd.to_timedelta(rng.integers(0, 600, n), unit="m")).dt.strftime(FMT)
    df["sys_updated_by"] = np.where(rng.random(n) < 0.4, "system", df["resolved_by"].astype(str).str.split().str[0].str.lower())

    pairs = [IMPACT_URGENCY[x][rng.integers(len(IMPACT_URGENCY[x]))] if x in IMPACT_URGENCY else ("3 - Low", "3 - Low")
             for x in p]
    df["impact"] = [a for a, _ in pairs]
    df["urgency"] = [b for _, b in pairs]
    hours = (resolved - pd.to_datetime(df["opened_at"])).dt.total_seconds() / 3600
    df["made_sla"] = np.where(hours <= p.map(SLA_HOURS).fillna(24), "true", "false")
    df["opened_by"] = df["caller_id"]
    df["closed_by"] = df["resolved_by"]
    return df[REAL_EXPORT_COLUMNS + EXTRA_COLUMNS]


def main():
    df, truth = generate(1000, seed=11, first_number=4000000)
    df, truth = plant_anomalies(df, truth, 11)
    df = add_export_columns(df, seed=11)
    out = os.path.dirname(os.path.abspath(__file__))
    df.to_csv(os.path.join(out, "northwind_full_incidents.csv"), index=False)
    truth.to_csv(os.path.join(out, "northwind_full_ground_truth.csv"), index=False)
    print(f"Wrote {len(df)} tickets with {len(df.columns)} columns")


if __name__ == "__main__":
    main()
