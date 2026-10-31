"""
Every page must show the same numbers. These tests compute the expected values with
pandas from the seeded tickets and compare them with the API and the shared helpers.
"""

import pytest

from models import SessionLocal
from services.metrics import mttr_by_status
from tests.conftest import TEAM_A, auth
from utils import automation_savings, months_covered


@pytest.fixture(scope="module")
def kpis(client, seeded):
    r = client.get(f"/api/dashboard-kpis/{seeded['upload_a']}", headers=auth("pytest_alice"))
    assert r.status_code == 200
    return r.json()


def test_mttr_by_status_matches_pandas(seeded, frame):
    db = SessionLocal()
    try:
        m = mttr_by_status(db, seeded["upload_a"], TEAM_A)
    finally:
        db.close()
    assert m["overall"] == {"avg_hours": round(frame.mttr_hours.mean(), 2), "tickets": 48}
    auto = frame[frame.is_already_automated]
    assert m["automated"]["avg_hours"] == round(auto.mttr_hours.mean(), 2)
    manual = frame[~frame.is_already_automated & ~frame.can_be_automated]
    assert m["manual_only"] == {"avg_hours": round(manual.mttr_hours.mean(), 2), "tickets": len(manual)}
    assert m["automated"]["tickets"] + m["human_handled"]["tickets"] == 48


def test_dashboard_savings_use_shared_rule(kpis, frame):
    months = months_covered(frame.opened.min(), frame.opened.max())
    expected = automation_savings(int(frame.can_be_automated.sum()), months)
    assert kpis["automation_value"]["annual_savings_inr"] == expected["annual_savings_inr"]


def test_ticket_intelligence_savings_match_dashboard(client, seeded, kpis):
    """Regression: this tab used $15 x calendar hours, a different rule from the dashboard."""
    stats = client.get(f"/api/ticket-intelligence/{seeded['upload_a']}/stats", headers=auth("pytest_alice")).json()
    assert stats["estimated_annual_savings"] == kpis["automation_value"]["annual_savings_inr"]


def test_dashboard_mttr_is_the_canonical_mttr(kpis, frame):
    text = str(kpis)
    assert str(round(frame.mttr_hours.mean(), 2)) in text


def test_ticket_intelligence_mttr_matches_dashboard(client, seeded, kpis):
    """Regression: this tab capped MTTR at 720 h and disagreed with the dashboard (20.21 vs 21.99 h)."""
    from models import SessionLocal, Ticket
    db = SessionLocal()
    try:   # one very long ticket, as real dumps have
        t = db.query(Ticket).filter(Ticket.upload_id == seeded["upload_a"]).order_by(Ticket.id).first()
        old, t.mttr_hours = t.mttr_hours, 900.0
        db.commit()
        stats = client.get(f"/api/ticket-intelligence/{seeded['upload_a']}/stats", headers=auth("pytest_alice")).json()
        fresh = client.get(f"/api/dashboard-kpis/{seeded['upload_a']}", headers=auth("pytest_alice")).json()
        assert stats["avg_mttr_hours"] == fresh["operational_efficiency"]["avg_mttr_hours"]
    finally:
        t.mttr_hours = old
        db.commit()
        db.close()
