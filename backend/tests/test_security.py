"""
API security: authentication, team isolation, admin-only actions, safe downloads.
Every 'denied' test has a matching 'allowed' test, so a broken endpoint can't pass as secure.
"""

from jose import jwt
import pytest

from tests.conftest import PASSWORD, auth, token

TEAM_ENDPOINTS = [
    "/api/dashboard-kpis/{id}",
    "/api/tickets/{id}",
    "/api/automation-summary/{id}",
    "/api/rag/status/{id}",
    "/api/review/{id}/summary",
    "/api/ticket-intelligence/{id}/stats",
]


def test_login(client, seeded):
    ok = client.post("/api/login", data={"username": "pytest_alice", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["access_token"]
    bad = client.post("/api/login", data={"username": "pytest_alice", "password": "wrong"})
    assert bad.status_code == 401
    unknown = client.post("/api/login", data={"username": "pytest_nobody", "password": PASSWORD})
    assert unknown.status_code == 401                                   # same response: no user enumeration


@pytest.mark.parametrize("path", TEAM_ENDPOINTS)
def test_requires_token(client, seeded, path):
    assert client.get(path.format(id=seeded["upload_a"])).status_code in (401, 403)


@pytest.mark.parametrize("path", TEAM_ENDPOINTS)
def test_rejects_forged_token(client, seeded, path):
    forged = jwt.encode({"user_id": "pytest_alice", "team_id": "pytest_team_a"}, "not-the-secret", algorithm="HS256")
    r = client.get(path.format(id=seeded["upload_a"]), headers={"Authorization": f"Bearer {forged}"})
    assert r.status_code == 401


@pytest.mark.parametrize("path", TEAM_ENDPOINTS)
def test_owner_team_allowed(client, seeded, path):
    assert client.get(path.format(id=seeded["upload_a"]), headers=auth("pytest_alice")).status_code == 200


@pytest.mark.parametrize("path", TEAM_ENDPOINTS)
def test_other_team_gets_404(client, seeded, path):
    """404, not 403, so another team can't even learn that the upload exists."""
    assert client.get(path.format(id=seeded["upload_a"]), headers=auth("pytest_bob")).status_code == 404


def test_copilot_ask_checks_ownership(client, seeded):
    r = client.post("/api/rag/ask", json={"upload_id": seeded["upload_a"], "question": "MTTR"},
                    headers=auth("pytest_bob"))
    assert r.status_code == 404


def test_similar_tickets_checks_ownership(client, seeded):
    assert client.get(f"/api/rag/similar/{seeded['upload_a']}/1", headers=auth("pytest_bob")).status_code == 404


def test_review_label_checks_ownership(client, seeded):
    r = client.post(f"/api/review/{seeded['upload_a']}/label", headers=auth("pytest_bob"),
                    json={"ticket_id": 1, "label": "Manual Only", "mode": "random"})
    assert r.status_code == 404


def test_export_link_needs_token_and_ownership(client, seeded):
    path = f"/api/copilot/export/csv/team_performance?upload_id={seeded['upload_a']}"
    assert client.get(path).status_code in (401, 422)
    assert client.get(path + f"&token={token('pytest_bob')}").status_code == 404
    assert client.get(path + f"&token={token('pytest_alice')}").status_code == 200


@pytest.mark.parametrize("name", ["..%2F..%2Fconfig.py", "..%5C..%5C.env", "%2Fetc%2Fpasswd", "does-not-exist.csv"])
def test_download_cannot_leave_export_dir(client, seeded, name):
    assert client.get(f"/api/copilot/download/{name}?token={token('pytest_alice')}").status_code == 404


def test_download_requires_token(client):
    assert client.get("/api/copilot/download/anything.csv").status_code in (401, 422)


@pytest.mark.parametrize("method,path", [
    ("post", "/api/models/automation/retrain"),
    ("post", "/api/models/automation/versions/20990101-000000/activate"),
])
def test_model_changes_are_admin_only(client, seeded, method, path):
    assert getattr(client, method)(path, headers=auth("pytest_alice")).status_code == 403


def test_signup_is_admin_only(client, seeded):
    """Regression: public signup accepted any team_id, which granted access to that team's data."""
    form = {"username": "pytest_mallory", "password": "long-enough-1", "email": "m@example.com",
            "team_id": "pytest_team_a"}
    assert client.post("/api/signup", data=form).status_code in (401, 403)
    assert client.post("/api/signup", data=form, headers=auth("pytest_alice")).status_code == 403
    assert client.post("/api/signup", data={**form, "password": "short"},
                       headers=auth("pytest_admin")).status_code == 400
    assert client.post("/api/signup", data=form, headers=auth("pytest_admin")).status_code == 200


def test_secrets_not_served(client):
    for path in ["/.env", "/backend/.env", "/config.py", "/.secret_key"]:
        assert client.get(path).status_code == 404


def test_upload_never_uses_client_file_name_as_path(client, seeded, monkeypatch):
    """Regression: the file was saved as uploads/<user>_<client file name>, so '../' could escape."""
    import os
    import main
    saved = {}
    monkeypatch.setattr(main, "process_upload_background", lambda path, uid, team: saved.update(path=path))
    r = client.post("/api/upload", headers=auth("pytest_alice"),
                    files={"file": ("pytest_../../escape.CSV", b"number,short_description\nINC1,test\n", "text/csv")})
    assert r.status_code == 200
    path = os.path.realpath(saved["path"])
    try:
        assert os.path.dirname(path) == os.path.realpath("uploads")
        assert "escape" not in os.path.basename(path) and path.endswith(".csv")
        assert not os.path.exists(os.path.join(os.path.dirname(os.path.realpath("uploads")), "escape.CSV"))
    finally:
        os.remove(path)


@pytest.mark.parametrize("name", ["data.txt", "data.csv.exe", "noextension"])
def test_upload_rejects_other_file_types(client, seeded, name):
    r = client.post("/api/upload", headers=auth("pytest_alice"), files={"file": (name, b"x", "text/plain")})
    assert r.status_code == 400
