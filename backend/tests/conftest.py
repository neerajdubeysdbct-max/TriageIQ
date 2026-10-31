"""
Test fixtures. Integration tests run against the database in DATABASE_URL (a local
dev database or the CI Postgres service). Everything created here is prefixed
`pytest_` and deleted at the end of the session; existing data is never touched.
"""

import os
import sys
from datetime import datetime, timedelta

import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import create_access_token, get_password_hash  # noqa: E402
from models import SessionLocal, Ticket, Upload, User  # noqa: E402

TEAM_A, TEAM_B = "pytest_team_a", "pytest_team_b"
USERS = {
    "pytest_alice": (TEAM_A, "user"),
    "pytest_bob": (TEAM_B, "user"),
    "pytest_admin": (TEAM_A, "admin"),
}
PASSWORD = "pytest-Password-1"

TEAMS = ["Alpha Ops", "Beta Desk", "Gamma DB"]
PRIORITIES = ["1 - Critical", "2 - High", "3 - Moderate", "4 - Low"]
CHANNELS = ["Email", "Phone", "Self-service"]
STATUSES = ["Already Automated", "Can Be Automated", "Manual Only"]


def ticket_rows():
    """48 tickets with known values; tests compute expected answers from this list with pandas."""
    start = datetime(2025, 1, 1, 9, 0)
    rows = []
    for i in range(48):
        status = STATUSES[i % 3]
        mttr = round(0.5 + (i % 7) * 3.25 + (i % 4) * 1.5, 2)
        opened = start + timedelta(days=i * 2)
        rows.append({
            "ticket_number": f"INC9{i:06d}",
            "assignment_group": TEAMS[i % 3 if i % 5 else 0],
            "priority": PRIORITIES[i % 4],
            "channel": CHANNELS[i % 3],
            "contact_type": CHANNELS[i % 3],
            "aiops_automation_status": status,
            "is_already_automated": status == "Already Automated",
            "can_be_automated": status == "Can Be Automated",
            "resolved_by": "bot.runner" if status == "Already Automated" else f"analyst{i % 4}",
            "short_description": ["Disk space alert on server", "Password reset request", "Order page shows wrong price"][i % 3],
            "close_notes": ["Cleared temp files", "Reset password via portal", "Fixed price rule in catalogue"][i % 3],
            "mttr_hours": mttr,
            "opened": opened,
            "resolved": opened + timedelta(hours=mttr),
        })
    return rows


@pytest.fixture(scope="session")
def frame():
    return pd.DataFrame(ticket_rows())


def _cleanup(db):
    ids = [u.id for u in db.query(Upload).filter(Upload.filename.like("pytest_%")).all()]
    if ids:
        db.query(Ticket).filter(Ticket.upload_id.in_(ids)).delete(synchronize_session=False)
        db.query(Upload).filter(Upload.id.in_(ids)).delete(synchronize_session=False)
    db.query(User).filter(User.username.like("pytest_%")).delete(synchronize_session=False)
    db.commit()


@pytest.fixture(scope="session")
def seeded():
    """Users in two teams, plus one upload with 48 tickets owned by team A and an empty one for team B."""
    db = SessionLocal()
    try:
        _cleanup(db)
        for name, (team, role) in USERS.items():
            db.add(User(username=name, email=f"{name}@example.com", team_id=team, role=role,
                        hashed_password=get_password_hash(PASSWORD)))
        up_a = Upload(filename="pytest_team_a.csv", record_type="incident", status="completed",
                      total_tickets=48, team_id=TEAM_A, user_id="pytest_alice")
        up_b = Upload(filename="pytest_team_b.csv", record_type="incident", status="completed",
                      total_tickets=0, team_id=TEAM_B, user_id="pytest_bob")
        db.add_all([up_a, up_b])
        db.commit()
        for r in ticket_rows():
            db.add(Ticket(upload_id=up_a.id, team_id=TEAM_A, record_type="incident", **r))
        db.commit()
        info = {"upload_a": up_a.id, "upload_b": up_b.id}
    finally:
        db.close()
    yield info
    db = SessionLocal()
    try:
        _cleanup(db)
    finally:
        db.close()


@pytest.fixture(scope="session")
def client():
    from fastapi.testclient import TestClient
    from main import app
    return TestClient(app)   # no context manager: startup hooks (model warm-up) are not needed


def auth(username: str) -> dict:
    team = USERS[username][0]
    return {"Authorization": f"Bearer {create_access_token(username, team)}"}


def token(username: str) -> str:
    return create_access_token(username, USERS[username][0])
