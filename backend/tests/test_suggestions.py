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


class TestPollWebhookMethods:
    """Verify /api/whapi/webhook accepts POST, PUT, PATCH with absolute counts."""

    def _payload(self, s, y, n):
        return {"messages": [{
            "id": s["poll_message_id"], "type": "poll", "from_me": True,
            "chat_id": "120363000@g.us",
            "poll": {"title": f"{s['title']} — Do you support this?",
                     "options": ["Yes", "No"],
                     "results": [{"name": "Yes", "count": y},
                                 {"name": "No", "count": n}]},
        }]}

    def _get(self, soc_h, sid):
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        assert g.status_code == 200
        return next(x for x in g.json()["suggestions"] if x["id"] == sid)

    def test_post_exact_id_match(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        r = requests.post(f"{API}/whapi/webhook", json=self._payload(s, 5, 3), timeout=20)
        assert r.status_code == 200, r.text
        found = self._get(soc_h, s["id"])
        assert found["yes_votes"] == 5 and found["no_votes"] == 3, found

    def test_put_method_accepted(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        # baseline POST
        requests.post(f"{API}/whapi/webhook", json=self._payload(s, 5, 3), timeout=20)
        # now PUT with 9,1 (absolute)
        r = requests.put(f"{API}/whapi/webhook", json=self._payload(s, 9, 1), timeout=20)
        assert r.status_code == 200, f"PUT should be accepted, got {r.status_code}: {r.text}"
        found = self._get(soc_h, s["id"])
        assert found["yes_votes"] == 9 and found["no_votes"] == 1, found

    def test_patch_method_accepted(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        requests.put(f"{API}/whapi/webhook", json=self._payload(s, 9, 1), timeout=20)
        r = requests.patch(f"{API}/whapi/webhook", json=self._payload(s, 2, 2), timeout=20)
        assert r.status_code == 200, f"PATCH should be accepted, got {r.status_code}: {r.text}"
        found = self._get(soc_h, s["id"])
        assert found["yes_votes"] == 2 and found["no_votes"] == 2, found


class TestTitleFallbackAndBackfill:
    def test_title_fallback_updates_and_backfills_id(self, soc_h, created_ids):
        s = _create(soc_h, created_ids)
        original_pmid = s["poll_message_id"]
        new_id = f"remote-{uuid.uuid4().hex}"
        payload = {"messages": [{
            "id": new_id, "type": "poll", "from_me": True,
            "chat_id": "120363999@g.us",  # unbound group -> society scoping skipped
            "poll": {"title": f"{s['title']} — Do you support this?",
                     "options": ["Yes", "No"],
                     "results": [{"name": "Yes", "count": 7},
                                 {"name": "No", "count": 4}]},
        }]}
        r = requests.post(f"{API}/whapi/webhook", json=payload, timeout=20)
        assert r.status_code == 200, r.text

        # Verify votes updated
        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        found = next(x for x in g.json()["suggestions"] if x["id"] == s["id"])
        assert found["yes_votes"] == 7 and found["no_votes"] == 4, found
        # Verify poll_message_id was backfilled to the new id
        assert found["poll_message_id"] == new_id, (
            f"expected poll_message_id backfilled to {new_id}, got {found.get('poll_message_id')} "
            f"(was {original_pmid})")

        # And subsequent updates by the new id still work (exact-id match)
        payload2 = {"messages": [{
            "id": new_id, "type": "poll", "from_me": True,
            "chat_id": "120363999@g.us",
            "poll": {"results": [{"name": "Yes", "count": 1},
                                 {"name": "No", "count": 0}]},
        }]}
        r2 = requests.put(f"{API}/whapi/webhook", json=payload2, timeout=20)
        assert r2.status_code == 200
        g2 = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        found2 = next(x for x in g2.json()["suggestions"] if x["id"] == s["id"])
        assert found2["yes_votes"] == 1 and found2["no_votes"] == 0

    def test_unknown_id_and_unknown_title_ignored(self, soc_h, created_ids):
        # baseline: create a suggestion + set to known 3,2 via exact-id
        s = _create(soc_h, created_ids)
        requests.post(f"{API}/whapi/webhook", json={"messages": [{
            "id": s["poll_message_id"], "type": "poll", "from_me": True,
            "chat_id": "120363000@g.us",
            "poll": {"results": [{"name": "Yes", "count": 3}, {"name": "No", "count": 2}]},
        }]}, timeout=20)

        # send poll with unknown id AND unknown title
        payload = {"messages": [{
            "id": f"nope-{uuid.uuid4().hex}", "type": "poll", "from_me": True,
            "chat_id": "120363000@g.us",
            "poll": {"title": f"NONEXISTENT_{uuid.uuid4().hex} — Do you support this?",
                     "results": [{"name": "Yes", "count": 99}, {"name": "No", "count": 99}]},
        }]}
        r = requests.post(f"{API}/whapi/webhook", json=payload, timeout=20)
        assert r.status_code == 200, r.text
        # PUT/PATCH variants must also 200 (not 405) and not mutate
        r2 = requests.put(f"{API}/whapi/webhook", json=payload, timeout=20)
        assert r2.status_code == 200
        r3 = requests.patch(f"{API}/whapi/webhook", json=payload, timeout=20)
        assert r3.status_code == 200

        g = requests.get(f"{API}/society/suggestions", headers=soc_h, timeout=15)
        found = next(x for x in g.json()["suggestions"] if x["id"] == s["id"])
        assert found["yes_votes"] == 3 and found["no_votes"] == 2, found


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
