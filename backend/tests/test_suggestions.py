"""Tests for Resident Suggestions + WhatsApp poll ingestion."""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://complaint-whatsapp.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

SOC = {"email": "admin@greenvalley.com", "password": "Admin@123"}


@pytest.fixture(scope="module")
def soc_h():
    r = requests.post(f"{API}/auth/login", json=SOC, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def created_ids():
    ids = []
    yield ids
    # cleanup
    r = requests.post(f"{API}/auth/login", json=SOC, timeout=20)
    if r.status_code == 200:
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        for sid in ids:
            requests.delete(f"{API}/society/suggestions/{sid}", headers=h, timeout=10)


def _create(soc_h, created_ids, title=None):
    title = title or f"TEST_Sug_{uuid.uuid4().hex[:6]}"
    r = requests.post(f"{API}/society/suggestions",
                      headers=soc_h,
                      json={"title": title, "category": "General", "author_name": "TestBot"},
                      timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "id" in data
    assert data["poll_message_id"], f"poll_message_id must be set (got {data.get('poll_message_id')})"
    created_ids.append(data["id"])
    return data


class TestSuggestionCreate:
    def test_create_returns_poll_message_id(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        assert s["title"].startswith("TEST_Sug_")
        assert s["status"] == "Under Review"
        assert s["yes_votes"] == 0 and s["no_votes"] == 0
        # In env with 402 plan, poll_message_id starts with "local-"
        assert isinstance(s["poll_message_id"], str) and len(s["poll_message_id"]) > 0


class TestPollWebhookIngest:
    def test_poll_webhook_updates_votes(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        pmid = s["poll_message_id"]
        payload = {"messages": [{
            "id": pmid, "type": "poll", "from_me": True, "chat_id": "120363000@g.us",
            "poll": {"title": s["title"], "options": ["Yes", "No"], "total": 1,
                     "results": [{"name": "Yes", "count": 5, "voters": []},
                                 {"name": "No", "count": 3, "voters": []}]},
        }]}
        r = requests.post(f"{API}/whapi/webhook", json=payload, timeout=20)
        assert r.status_code == 200, r.text

        # verify via GET
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        assert g.status_code == 200
        found = next((x for x in g.json()["suggestions"] if x["id"] == s["id"]), None)
        assert found is not None
        assert found["yes_votes"] == 5, found
        assert found["no_votes"] == 3, found

    def test_poll_webhook_is_absolute_not_additive(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        pmid = s["poll_message_id"]

        def _send(y, n):
            payload = {"messages": [{
                "id": pmid, "type": "poll", "from_me": True, "chat_id": "120363000@g.us",
                "poll": {"title": s["title"], "options": ["Yes", "No"], "total": 1,
                         "results": [{"name": "Yes", "count": y}, {"name": "No", "count": n}]},
            }]}
            r = requests.post(f"{API}/whapi/webhook", json=payload, timeout=20)
            assert r.status_code == 200

        _send(5, 3)
        _send(8, 1)
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        found = next(x for x in g.json()["suggestions"] if x["id"] == s["id"])
        assert found["yes_votes"] == 8 and found["no_votes"] == 1, found

    def test_unknown_message_id_safely_ignored(self, soc_h, created_ids):
        # baseline: create + set a known suggestion to yes=2,no=2
        s = _create(soc_h, created_ids)
        pmid = s["poll_message_id"]
        requests.post(f"{API}/whapi/webhook", json={"messages": [{
            "id": pmid, "type": "poll", "from_me": True, "chat_id": "120363000@g.us",
            "poll": {"results": [{"name": "Yes", "count": 2}, {"name": "No", "count": 2}]},
        }]}, timeout=20)

        # now send unknown id
        payload = {"messages": [{
            "id": f"unknown-{uuid.uuid4().hex}", "type": "poll", "from_me": True,
            "chat_id": "120363000@g.us",
            "poll": {"results": [{"name": "Yes", "count": 99}, {"name": "No", "count": 99}]},
        }]}
        r = requests.post(f"{API}/whapi/webhook", json=payload, timeout=20)
        assert r.status_code == 200

        # verify our known suggestion untouched
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        found = next(x for x in g.json()["suggestions"] if x["id"] == s["id"])
        assert found["yes_votes"] == 2 and found["no_votes"] == 2


class TestManualAndStatus:
    def test_manual_vote_increments(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        r = requests.post(f"{API}/society/suggestions/{s['id']}/vote",
                          headers=soc_h, json={"vote": "yes"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["yes_votes"] == 1
        r = requests.post(f"{API}/society/suggestions/{s['id']}/vote",
                          headers=soc_h, json={"vote": "yes"}, timeout=15)
        assert r.json()["yes_votes"] == 2

    def test_status_update(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        r = requests.put(f"{API}/society/suggestions/{s['id']}",
                         headers=soc_h, json={"status": "Approved"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["status"] == "Approved"
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        found = next(x for x in g.json()["suggestions"] if x["id"] == s["id"])
        assert found["status"] == "Approved"


class TestListStats:
    def test_stats_totals(self, soc_h, created_ids):
        # create one and vote via poll so total_votes moves
        s = _create(soc_h, created_ids)
        requests.post(f"{API}/whapi/webhook", json={"messages": [{
            "id": s["poll_message_id"], "type": "poll", "from_me": True,
            "chat_id": "120363000@g.us",
            "poll": {"results": [{"name": "Yes", "count": 4}, {"name": "No", "count": 2}]},
        }]}, timeout=20)
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        assert g.status_code == 200
        data = g.json()
        assert "stats" in data and "suggestions" in data
        st = data["stats"]
        for k in ("total", "under_review", "approved", "pending", "declined", "total_votes"):
            assert k in st, f"missing key {k}"
        computed = sum(x.get("yes_votes", 0) + x.get("no_votes", 0) for x in data["suggestions"])
        assert st["total_votes"] == computed
