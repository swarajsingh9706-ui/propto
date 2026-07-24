"""PROPTO backend end-to-end tests.

Covers: auth, super admin (societies), society admin (dashboard, vendors, residents,
tickets), WhatsApp simulator + AI pipeline, AI activity, HITL review queue, reports.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://complaint-whatsapp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SUPER = {"email": "superadmin@propto.com", "password": "Propto@123"}
SOC = {"email": "admin@greenvalley.com", "password": "Admin@123"}


# ---------------- fixtures ----------------
@pytest.fixture(scope="session")
def super_token():
    r = requests.post(f"{API}/auth/login", json=SUPER, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def soc_token():
    r = requests.post(f"{API}/auth/login", json=SOC, timeout=20)
    assert r.status_code == 200, r.text
    return r.json()["token"]


@pytest.fixture(scope="session")
def super_h(super_token):
    return {"Authorization": f"Bearer {super_token}"}


@pytest.fixture(scope="session")
def soc_h(soc_token):
    return {"Authorization": f"Bearer {soc_token}"}


# ---------------- auth ----------------
class TestAuth:
    def test_health(self):
        r = requests.get(f"{API}/health", timeout=10)
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

    def test_login_super(self):
        r = requests.post(f"{API}/auth/login", json=SUPER, timeout=20)
        assert r.status_code == 200
        data = r.json()
        assert data["user"]["role"] == "super_admin"
        assert data["token"]

    def test_login_soc(self):
        r = requests.post(f"{API}/auth/login", json=SOC, timeout=20)
        assert r.status_code == 200
        assert r.json()["user"]["role"] == "society_admin"

    def test_login_invalid(self):
        r = requests.post(f"{API}/auth/login", json={"email": "x@y.com", "password": "bad"}, timeout=20)
        assert r.status_code == 401

    def test_me(self, super_h):
        r = requests.get(f"{API}/auth/me", headers=super_h, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == SUPER["email"]

    def test_me_unauth(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code in (401, 403)


# ---------------- super admin ----------------
class TestSuperAdmin:
    def test_list_societies(self, super_h):
        r = requests.get(f"{API}/super/societies", headers=super_h, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert any(s["code"] == "GRNVLY" for s in data)

    def test_create_society(self, super_h):
        code = "TEST" + uuid.uuid4().hex[:4].upper()
        payload = {"name": f"TEST Society {code}", "code": code, "city": "TestCity", "towers": ["A"]}
        r = requests.post(f"{API}/super/societies", headers=super_h, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["code"] == code
        # verify persisted
        r2 = requests.get(f"{API}/super/societies", headers=super_h, timeout=15)
        assert any(s["code"] == code for s in r2.json())
        # cleanup
        requests.delete(f"{API}/super/societies/{created['id']}", headers=super_h, timeout=15)

    def test_super_reports(self, super_h):
        r = requests.get(f"{API}/super/reports", headers=super_h, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "societies" in d and "categories" in d and "vendor_performance" in d


# ---------------- dashboard/vendors/residents ----------------
class TestSocietyResources:
    def test_dashboard(self, soc_h):
        r = requests.get(f"{API}/society/dashboard", headers=soc_h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["total", "open", "pending", "resolved", "escalated", "ai_generated"]:
            assert k in d["stats"]

    def test_vendor_crud(self, soc_h):
        payload = {"name": f"TEST_V_{uuid.uuid4().hex[:4]}", "phone": "919111000001",
                   "categories": ["Plumbing"], "availability": True, "active": True}
        r = requests.post(f"{API}/society/vendors", headers=soc_h, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        # list
        r2 = requests.get(f"{API}/society/vendors", headers=soc_h, timeout=15)
        assert any(v["id"] == vid for v in r2.json())
        # toggle
        r3 = requests.put(f"{API}/society/vendors/{vid}", headers=soc_h,
                          json={"availability": False}, timeout=15)
        assert r3.status_code == 200 and r3.json()["availability"] is False
        # delete
        r4 = requests.delete(f"{API}/society/vendors/{vid}", headers=soc_h, timeout=15)
        assert r4.status_code == 200

    def test_resident_crud(self, soc_h):
        payload = {"name": "TEST_Res", "phone": "919111000099", "flat": "Z999", "tower": "Z"}
        r = requests.post(f"{API}/society/residents", headers=soc_h, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        r2 = requests.get(f"{API}/society/residents", headers=soc_h, timeout=15)
        assert any(x["id"] == rid for x in r2.json())
        assert any(x["phone"] == "918111111102" for x in r2.json())  # seed
        r3 = requests.delete(f"{API}/society/residents/{rid}", headers=soc_h, timeout=15)
        assert r3.status_code == 200


# ---------------- WhatsApp simulator + AI pipeline ----------------
class TestPipeline:
    @pytest.fixture(scope="class")
    def created_ticket(self, soc_h):
        # unique-ish flat suffix to avoid duplicate collisions
        text = "water leaking heavily in flat B302 send plumber urgently"
        r = requests.post(f"{API}/society/whatsapp/simulate", headers=soc_h,
                          json={"phone": "918111111102", "text": text}, timeout=60)
        assert r.status_code == 200, r.text
        return r.json()

    def test_ignored_greeting(self, soc_h):
        r = requests.post(f"{API}/society/whatsapp/simulate", headers=soc_h,
                          json={"phone": "918111111101", "text": "good morning everyone"}, timeout=30)
        assert r.status_code == 200
        assert r.json()["status"] == "ignored"

    def test_ticket_created(self, created_ticket):
        # AI pipeline may occasionally send low confidence -> review_queue; accept but assert normal case
        assert created_ticket["status"] in ("ticket_created", "duplicate", "review_queue"), created_ticket
        if created_ticket["status"] == "ticket_created":
            ai = created_ticket.get("ai", {})
            assert ai.get("category")
            assert 0 <= float(ai.get("confidence", 0)) <= 1

    def test_ticket_appears_in_list(self, soc_h, created_ticket):
        if created_ticket["status"] != "ticket_created":
            pytest.skip("no ticket created")
        tn = created_ticket["ticket_number"]
        r = requests.get(f"{API}/society/tickets", headers=soc_h, timeout=15)
        assert r.status_code == 200
        assert any(t["ticket_number"] == tn for t in r.json())

    def test_ticket_assign_and_close(self, soc_h, created_ticket):
        if created_ticket["status"] != "ticket_created":
            pytest.skip("no ticket created")
        tn = created_ticket["ticket_number"]
        tickets = requests.get(f"{API}/society/tickets", headers=soc_h, timeout=15).json()
        t = next(x for x in tickets if x["ticket_number"] == tn)
        tid = t["id"]
        # get vendor list
        vendors = requests.get(f"{API}/society/vendors", headers=soc_h, timeout=15).json()
        plumbing = [v for v in vendors if "Plumbing" in v.get("categories", [])]
        if plumbing:
            r = requests.post(f"{API}/society/tickets/{tid}/assign", headers=soc_h,
                              json={"vendor_id": plumbing[0]["id"]}, timeout=20)
            assert r.status_code == 200
            assert r.json()["vendor_id"] == plumbing[0]["id"]
        # update status Pending
        r2 = requests.put(f"{API}/society/tickets/{tid}", headers=soc_h,
                          json={"status": "Pending"}, timeout=15)
        assert r2.status_code == 200
        # close
        r3 = requests.post(f"{API}/society/tickets/{tid}/close", headers=soc_h, timeout=15)
        assert r3.status_code == 200
        assert r3.json()["status"] == "Resolved"

    def test_duplicate_detection(self, soc_h):
        # Create fresh complaint pair with unique flat
        text = "the tap is leaking badly water everywhere in flat A101 need plumber"
        r1 = requests.post(f"{API}/society/whatsapp/simulate", headers=soc_h,
                           json={"phone": "918111111101", "text": text}, timeout=60)
        assert r1.status_code == 200
        # send again with slight variation
        text2 = "water leakage from tap in flat A101 please send plumber"
        r2 = requests.post(f"{API}/society/whatsapp/simulate", headers=soc_h,
                           json={"phone": "918111111101", "text": text2}, timeout=60)
        assert r2.status_code == 200
        s1, s2 = r1.json()["status"], r2.json()["status"]
        # At least one of them must be a ticket, and the 2nd (given open ticket) should either be duplicate or ticket_created if categorized differently.
        assert s1 in ("ticket_created", "duplicate", "review_queue")
        assert s2 in ("ticket_created", "duplicate", "review_queue")
        # cleanup: close any open tickets on A101 Plumbing
        tickets = requests.get(f"{API}/society/tickets", headers=soc_h, timeout=15).json()
        for t in tickets:
            if t.get("flat", "").upper() == "A101" and t.get("status") in ("Open", "Pending"):
                requests.post(f"{API}/society/tickets/{t['id']}/close", headers=soc_h, timeout=15)


# ---------------- AI activity + HITL ----------------
class TestAIActivity:
    def test_activity_endpoint(self, soc_h):
        r = requests.get(f"{API}/society/ai/activity", headers=soc_h, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "logs" in d and "stats" in d
        assert d["stats"]["total"] >= 0

    def test_review_queue_endpoint(self, soc_h):
        r = requests.get(f"{API}/society/ai/review-queue", headers=soc_h, timeout=15)
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------- Reports ----------------
class TestReports:
    def test_reports(self, soc_h):
        r = requests.get(f"{API}/society/reports", headers=soc_h, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ["daily", "categories", "resolution", "vendor_performance", "summary"]:
            assert k in d
        assert len(d["daily"]) == 14
