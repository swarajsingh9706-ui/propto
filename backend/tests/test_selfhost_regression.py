"""Iteration 6: verify the cPanel/self-host defensive changes did not regress anything.

Covers: /api/health, passenger_wsgi importability (a2wsgi + ASGIMiddleware wrap),
startup seeding guard (seeded data still present), society admin login + dashboard,
super admin login + dashboard, and whapi webhook GET/POST/PUT contract.
"""
import os
import subprocess
import sys

import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
if not BASE:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

WHAPI = f"{BASE}/api/whapi/webhook"


@pytest.fixture(scope="module")
def session():
    return requests.Session()


# ---------- health ----------
def test_health(session):
    r = session.get(f"{BASE}/api/health", timeout=60)
    assert r.status_code == 200, r.text[:300]
    assert r.json().get("status") == "healthy", r.json()


# ---------- passenger_wsgi (cPanel serving path) ----------
class TestPassengerWsgi:
    def test_a2wsgi_installed(self):
        import importlib
        assert importlib.util.find_spec("a2wsgi") is not None, "a2wsgi missing from requirements/venv"

    def test_passenger_wsgi_imports_and_exposes_application(self):
        code = (
            "import sys; sys.path.insert(0, '/app/backend');"
            "import passenger_wsgi as p;"
            "from a2wsgi import ASGIMiddleware;"
            "assert isinstance(p.application, ASGIMiddleware), type(p.application);"
            "print('WSGI_OK')"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
        assert "WSGI_OK" in proc.stdout, f"stdout={proc.stdout[-1500:]} stderr={proc.stderr[-2500:]}"

    def test_missing_a2wsgi_gives_clear_message(self):
        """Simulate a venv without a2wsgi -> must print the actionable FATAL hint and raise ImportError."""
        code = (
            "import sys, builtins;"
            "sys.path.insert(0, '/app/backend');"
            "_ri = builtins.__import__\n"
            "def fake(name, *a, **k):\n"
            "    if name == 'a2wsgi' or name.startswith('a2wsgi.'):\n"
            "        raise ImportError('No module named a2wsgi')\n"
            "    return _ri(name, *a, **k)\n"
            "builtins.__import__ = fake\n"
            "try:\n"
            "    import passenger_wsgi\n"
            "except ImportError:\n"
            "    print('RAISED_IMPORT_ERROR')\n"
        )
        proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=180)
        assert "RAISED_IMPORT_ERROR" in proc.stdout, f"stdout={proc.stdout[-800:]} stderr={proc.stderr[-800:]}"
        assert "a2wsgi" in proc.stderr and "pip install" in proc.stderr, proc.stderr[-1500:]


# ---------- whapi webhook contract ----------
class TestWebhookContract:
    def test_get_live(self, session):
        r = session.get(WHAPI, timeout=60)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("status") == "ok"
        assert "live" in body.get("detail", "").lower(), body

    @pytest.mark.parametrize("kwargs", [
        {"data": b""},
        {"data": "{}"},
        {"data": "<<not json>>"},
        {"json": {"messages": [{"id": "TESTMSG_x", "type": "text", "chat_id": "1@g.us",
                                "from": "918111111101", "text": {"body": "TEST_ leak in lobby"}}]}},
    ])
    def test_post_never_500(self, session, kwargs):
        r = session.post(WHAPI, headers={"Content-Type": "application/json"}, timeout=120, **kwargs)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("status") == "ok"

    def test_put_poll(self, session):
        payload = {"messages": [{"id": "TESTMSG_p6", "type": "poll", "chat_id": "1@g.us",
                                 "from": "918111111101",
                                 "poll": {"title": "TEST_x", "results": [{"id": "0", "name": "Yes", "count": 1, "voters": []}]},
                                 "poll_update": {"poll_id": "TESTMSG_p6"}}]}
        r = session.put(WHAPI, json=payload, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("status") == "ok"


# ---------- auth + dashboards (seeding guard regression) ----------
def _login(email, password):
    r = requests.post(f"{BASE}/api/auth/login", json={"email": email, "password": password}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"login failed for {email}: {r.status_code} {r.text[:300]}")
    body = r.json()
    assert body.get("token"), body
    assert body.get("user", {}).get("email") == email, body
    return body


def _assert_no_objectid_leak(obj):
    """Recursively assert no raw Mongo '_id' key is serialized."""
    if isinstance(obj, dict):
        assert "_id" not in obj, f"raw _id leaked: {list(obj.keys())}"
        for v in obj.values():
            _assert_no_objectid_leak(v)
    elif isinstance(obj, list):
        for v in obj:
            _assert_no_objectid_leak(v)


class TestDashboards:
    def test_society_admin_login_and_dashboard(self):
        body = _login("admin@greenvalley.com", "Admin@123")
        assert body["user"]["role"] == "society_admin", body["user"]
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {body['token']}"})
        r = s.get(f"{BASE}/api/society/dashboard", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        print("SOCIETY DASHBOARD:", data)
        assert isinstance(data, dict) and data, data
        _assert_no_objectid_leak(data)
        me = s.get(f"{BASE}/api/auth/me", timeout=60)
        assert me.status_code == 200 and me.json().get("email") == "admin@greenvalley.com"

    def test_super_admin_login_and_dashboard(self):
        body = _login("superadmin@propto.com", "Propto@123")
        assert body["user"]["role"] == "super_admin", body["user"]
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {body['token']}"})
        r = s.get(f"{BASE}/api/super/dashboard", timeout=60)
        assert r.status_code == 200, r.text[:300]
        data = r.json()
        print("SUPER DASHBOARD:", data)
        assert isinstance(data, dict) and data, data
        _assert_no_objectid_leak(data)

    def test_society_dashboard_requires_auth(self):
        r = requests.get(f"{BASE}/api/society/dashboard", timeout=60)
        assert r.status_code in (401, 403), r.status_code


# ---------- simulate pipeline (excel taxonomy) ----------
class TestSimulate:
    created = []

    def test_excel_taxonomy_ticket(self):
        body = _login("admin@greenvalley.com", "Admin@123")
        s = requests.Session()
        s.headers.update({"Authorization": f"Bearer {body['token']}", "Content-Type": "application/json"})
        r = s.post(f"{BASE}/api/society/whatsapp/simulate",
                   json={"phone": "918111111101", "text": "Booster pump not working"}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        print("SIMULATE:", data)
        assert data.get("status") in ("ticket_created", "duplicate"), data
        ai = data.get("ai") or {}
        assert ai.get("source_of_truth") == "excel", ai
        assert ai.get("category"), ai
        assert ai.get("intent") == "Complaint", ai
        if data.get("ticket_number"):
            TestSimulate.created.append(data["ticket_number"])
            print("CREATED_TICKET", data["ticket_number"])
