"""Pure helpers: priority normalisation, savings, dump-type detection, date parsing."""

from datetime import datetime

import pandas as pd
import pytest

from utils import (automation_savings, detect_dump_content, months_covered, normalize_priority,
                   ticket_effort_saving_inr)


@pytest.mark.parametrize("raw,expected", [
    ("1 - Critical", "P1"), ("P2", "P2"), ("2 - High", "P2"), ("3 - Moderate", "P3"),
    ("4 - Low", "P4"), ("p1", "P1"), ("Critical", "P1"), ("medium", "P3"),
    ("10 - something", "Unknown"), (None, "Unknown"), ("", "Unknown"),
])
def test_normalize_priority(raw, expected):
    assert normalize_priority(raw) == expected


def test_months_covered():
    assert months_covered(None, None) == 1.0
    assert months_covered(datetime(2025, 1, 1), datetime(2025, 1, 10)) == 1.0      # minimum one month
    assert months_covered(datetime(2025, 1, 1), datetime(2025, 7, 1)) == pytest.approx(5.95, abs=0.01)


def test_automation_savings_uses_effort_not_duration():
    s = automation_savings(can_automate=100, months=2)
    # 100 tickets x 15 min = 25 h over 2 months = 12.5 h/month; x Rs 850 = 10,625 per month
    assert s["monthly_savings_inr"] == 10625
    assert s["annual_savings_inr"] == 127500
    assert s["assumptions"] == {"effort_minutes_per_ticket": 15, "hourly_cost_inr": 850, "months_covered": 2}


def test_ticket_effort_saving_matches_bulk_rule():
    per_ticket = ticket_effort_saving_inr(True)
    assert per_ticket == 212.5
    assert ticket_effort_saving_inr(False) == 0
    # the per-ticket figure and the dataset figure must agree (no second costing rule)
    assert automation_savings(40, 1)["monthly_savings_inr"] == 40 * per_ticket


@pytest.mark.parametrize("numbers,expected", [
    (["INC001", "INC002", "INC003"], "incident"),
    (["RITM001", "REQ002", "RITM003"], "request"),
    (["CHG001", "CHG002"], "change"),
    (["PRB001"], "problem"),
])
def test_dump_type_from_content(numbers, expected):
    assert detect_dump_content(pd.DataFrame({"number": numbers}))["type"] == expected


def test_dump_type_ignores_file_name_and_detects_mix():
    df = pd.DataFrame({"number": ["INC1"] * 6 + ["RITM1"] * 4})
    out = detect_dump_content(df)
    assert out["type"] == "mixed"
    assert out["mix"] == {"incident": 0.6, "request": 0.4}


def test_dump_type_unknown_without_evidence():
    assert detect_dump_content(pd.DataFrame({"foo": [1, 2]}))["type"] == "unknown"


def test_dates_iso_not_day_first():
    """Regression: ISO dates read day-first turned 2025-08-04 into 8 April and inflated MTTR."""
    from chunk_processor import parse_ticket_dates
    out = parse_ticket_dates(pd.Series(["2025-08-04 11:53:50", "04/08/2025 10:00"]))
    assert out[0] == pd.Timestamp("2025-08-04 11:53:50")
    assert out[1] == pd.Timestamp("2025-08-04 10:00")     # slash dates from Indian exports: day first
