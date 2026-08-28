"""Whapi webhook robustness tests (bug: webhook returned HTTP 500 on self-host)
plus regression tests for the AI complaint pipeline and Meta webhook."""
import os
import time

import pytest
import requests
from dotenv import dotenv_values

_env = dotenv_values("/app/frontend/.env")
BASE = (os.environ.get("REACT_APP_BACKEND_URL") or _env.get("REACT_APP_BACKEND_URL", "")).rstrip("/")
if not BASE:
    raise RuntimeError("REACT_APP_BACKEND_URL missing")

WHAPI = f"{BASE}/api/whapi/webhook"
GROUP_ID = "999999999999999999@g.us"  # intentionally unmapped group


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    return s


# ---------- Whapi webhook: must never 500 ----------
class TestWhapiWebhook:
    def test_empty_body_post(self, session):
        r = session.post(WHAPI, data=b"", headers={"Content-Type": "application/json"}, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json() == {"status": "ok"}

    def test_no_content_type_no_body(self, session):
        r = session.post(WHAPI, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json().get("status") == "ok"

    def test_malformed_body(self, session):
        r = session.post(WHAPI, data="this is not json <<>>", headers={"Content-Type": "application/json"}, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json().get("status") == "ok"

    def test_form_encoded_body(self, session):
        r = session.post(WHAPI, data={"foo": "bar"}, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json().get("status") == "ok"

    def test_empty_json_object(self, session):
        r = session.post(WHAPI, json={}, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json() == {"status": "ok"}

    def test_json_array_body(self, session):
        r = session.post(WHAPI, json=[1, 2, 3], timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json().get("status") == "ok"

    def test_json_null_body(self, session):
        r = session.post(WHAPI, data="null", headers={"Content-Type": "application/json"}, timeout=60)
        assert r.status_code == 200, r.text[:500]
        assert r.json().get("status") == "ok"

    def test_realistic_group_message_unmapped_group(self, session):
        payload = {
            "messages": [{
                "id": "TESTMSG_unmapped_1",
                "from_me": False,
                "type": "text",
                "chat_id": GROUP_ID,
                "timestamp": int(time.time()),
                "from": "918111111101",
                "chat_name": "TEST_Unmapped Group",
                "text": {"body": "TEST_ Booster pump not working in Tower A"},
            }],
            "event": {"type": "messages", "event": "post"},
            "channel_id": "TESTCH",
        }
        r = session.post(WHAPI, json=payload, timeout=90)
        assert r.status_code == 200, r.text[:500]
        assert r.json() == {"status": "ok"}

    def test_direct_message_payload(self, session):
        payload = {
            "messages": [{
                "id": "TESTMSG_dm_1",
                "from_me": False,
                "type": "text",
                "chat_id": "918111111101@s.whatsapp.net",
                "from": "918111111101",
                "text": {"body": "TEST_ hello there"},
            }]
        }
        r = session.post(WHAPI, json=payload, timeout=90)
        assert r.status_code == 200, r.text[:500]

    def test_put_poll_update(self, session):
        payload = {
            "messages": [{
                "id": "TESTMSG_poll_1",
                "type": "poll",
                "chat_id": GROUP_ID,
                "from": "918111111101",
                "poll": {
                    "title": "TEST_Nonexistent suggestion — Do you support this?",
                    "results": [
                        {"id": "0", "name": "Yes 👍", "count": 3, "voters": []},
                        {"id": "1", "name": "No 👎", "count": 1, "voters": []},
                    ],
                },
                "poll_update": {"poll_id": "TESTMSG_poll_1"},
            }]
        }
        r = session.put(WHAPI, json=payload, timeout=90)
        assert r.status_code == 200, r.text[:500]
        assert r.json() == {"status": "ok"}

    def test_patch_method_allowed(self, session):
        r = session.patch(WHAPI, json={}, timeout=60)
        assert r.status_code == 200, r.text[:500]

    def test_get_method_behaviour(self, session):
        """Browser/Whapi probe: GET must return 200 with a 'webhook is live' JSON body."""
        r = session.get(WHAPI, timeout=60)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data.get("status") == "ok", data
        assert "live" in (data.get("detail") or "").lower(), data

    def test_button_payload_unknown_ticket(self, session):
        payload = {
            "messages": [{
                "id": "TESTMSG_btn_1",
                "type": "reply",
                "chat_id": "918111111102@s.whatsapp.net",
                "from": "918111111102",
                "reply": {"type": "buttons_reply", "buttons_reply": {"id": "vendor_accept_000000000000000000000000", "title": "Accept"}},
            }]
        }
        r = session.post(WHAPI, json=payload, timeout=90)
        assert r.status_code == 200, r.text[:500]


# ---------- Meta webhook regression ----------
class TestMetaWebhook:
    def test_get_verification_wrong_token(self, session):
        r = session.get(f"{BASE}/api/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "12345"}, timeout=60)
        assert r.status_code == 403, r.text[:300]

    def test_get_verification_correct_token(self, session):
        token = os.environ.get("WHATSAPP_VERIFY_TOKEN") or dotenv_values("/app/backend/.env").get("WHATSAPP_VERIFY_TOKEN")
        if not token:
            pytest.skip("WHATSAPP_VERIFY_TOKEN not configured")
        r = session.get(f"{BASE}/api/webhook", params={"hub.mode": "subscribe", "hub.verify_token": token, "hub.challenge": "12345"}, timeout=60)
        assert r.status_code == 200
        assert r.text.strip() == "12345"

    def test_post_without_signature_not_500(self, session):
        r = session.post(f"{BASE}/api/webhook", json={"object": "whatsapp_business_account", "entry": []}, timeout=60)
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (200, 401, 403), r.status_code

    def test_post_empty_body_not_500(self, session):
        r = session.post(f"{BASE}/api/webhook", data=b"", headers={"Content-Type": "application/json"}, timeout=60)
        assert r.status_code != 500, r.text[:300]


# ---------- AI pipeline regression ----------
@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@greenvalley.com", "password": "Admin@123"}, timeout=60)
    if r.status_code != 200:
        pytest.fail(f"society admin login failed {r.status_code}: {r.text[:300]}")
    tok = r.json().get("token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_client(admin_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"})
    return s


class TestPipelineRegression:
    created = []

    def test_simulate_excel_taxonomy_match(self, admin_client):
        r = admin_client.post(f"{BASE}/api/society/whatsapp/simulate",
                              json={"phone": "918111111101", "text": "Booster pump not working"}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        print("EXCEL RESULT:", data)
        assert data.get("status") == "ticket_created", data
        assert data.get("ticket_number"), data
        TestPipelineRegression.created.append(data["ticket_number"])
        ai = data.get("ai") or {}
        assert ai.get("source_of_truth") == "excel", ai
        assert ai.get("category"), ai
        assert ai.get("intent") == "Complaint", ai

    def test_simulate_freeform_ai_classification(self, admin_client):
        """Free-form text unlikely to be in the Excel taxonomy -> must go through AI without error."""
        text = ("Since yesterday evening a strong sewage smell is coming from the basement near the "
                "clubhouse entrance and residents at C204 are unable to use the corridor")
        r = admin_client.post(f"{BASE}/api/society/whatsapp/simulate",
                              json={"phone": "918111111103", "text": text}, timeout=180)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        print("AI RESULT:", data)
        assert data.get("status") in ("ticket_created", "review_queued", "duplicate"), f"classification failed: {data}"
        if data.get("ticket_number"):
            TestPipelineRegression.created.append(data["ticket_number"])
        ai = data.get("ai") or {}
        assert ai.get("category"), f"no category returned: {data}"

    def test_simulate_non_complaint_ignored(self, admin_client):
        r = admin_client.post(f"{BASE}/api/society/whatsapp/simulate",
                              json={"phone": "918111111103", "text": "Good morning everyone"}, timeout=120)
        assert r.status_code == 200, r.text[:500]
        data = r.json()
        assert data.get("status") == "ignored", data

    def test_tickets_list_no_objectid_leak(self, admin_client):
        r = admin_client.get(f"{BASE}/api/society/tickets", timeout=60)
        assert r.status_code == 200, r.text[:300]
        items = r.json()
        assert isinstance(items, list)
        for it in items[:10]:
            assert "_id" not in it, it
            assert "id" in it, it

    def test_created_tickets_persisted(self, admin_client):
        if not TestPipelineRegression.created:
            pytest.skip("no tickets created")
        r = admin_client.get(f"{BASE}/api/society/tickets", timeout=60)
        assert r.status_code == 200
        numbers = {t.get("ticket_number") for t in r.json()}
        for num in TestPipelineRegression.created:
            assert num in numbers, f"{num} not persisted in ticket list"


# ---------- End-to-end: mapped group message -> ticket via Whapi webhook ----------
class TestWhapiMappedGroupE2E:
    TEST_GROUP = "120363999000111222@g.us"

    @pytest.fixture(scope="class")
    def mapped_group(self, admin_client):
        st = admin_client.get(f"{BASE}/api/society/whatsapp/status", timeout=60)
        assert st.status_code == 200, st.text[:300]
        original = st.json().get("group")
        r = admin_client.post(f"{BASE}/api/society/whatsapp/connect",
                              json={"group_name": "TEST_QA Group", "group_id": self.TEST_GROUP}, timeout=60)
        assert r.status_code == 200, r.text[:300]
        yield self.TEST_GROUP
        if original:
            admin_client.post(f"{BASE}/api/society/whatsapp/connect",
                              json={"group_name": original.get("group_name"), "group_id": original.get("group_id")}, timeout=60)

    def test_group_complaint_creates_ticket(self, admin_client, mapped_group):
        before = {t["ticket_number"] for t in admin_client.get(f"{BASE}/api/society/tickets", timeout=60).json()}
        payload = {
            "messages": [{
                "id": f"TESTMSG_e2e_{int(time.time())}",
                "from_me": False,
                "type": "text",
                "chat_id": mapped_group,
                "from": "918111111101",
                "chat_name": "TEST_QA Group",
                "text": {"body": f"Cockroach and mosquito infestation in the B302 kitchen, needs pest control urgently (ref {int(time.time())})"},
            }],
            "event": {"type": "messages", "event": "post"},
        }
        r = requests.post(WHAPI, json=payload, timeout=120)
        assert r.status_code == 200, r.text[:300]
        assert r.json() == {"status": "ok"}
        new_num = None
        for _ in range(15):
            after = admin_client.get(f"{BASE}/api/society/tickets", timeout=60).json()
            diff = [t for t in after if t["ticket_number"] not in before]
            if diff:
                new_num = diff[0]
                break
            time.sleep(2)
        assert new_num, "webhook returned 200 but no ticket was created for mapped group message"
        print("E2E TICKET:", new_num.get("ticket_number"), new_num.get("category"), new_num.get("source_of_truth"))
        assert new_num.get("category")
        assert "_id" not in new_num
