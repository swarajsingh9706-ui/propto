# Vendor job link (/v/<token>) + resolution OTP: public API (HTTP) and pipeline/WhatsApp logic (direct python).
import os
import sys
import asyncio
import hashlib
import pytest
import requests
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)
load_dotenv(os.path.join(BACKEND_DIR, ".env"))

# Preview URL (frontend/.env REACT_APP_BACKEND_URL points to production api.propto.app which lacks these routes)
BASE_URL = os.environ.get("PREVIEW_URL", "https://complaint-whatsapp.preview.emergentagent.com").rstrip("/")
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
SOC = mdb.societies.find_one({"name": "Green Valley Residency"})
SID = str(SOC["_id"])
OTP = "123456"


def h(tid, otp):
    return hashlib.sha256(f"{tid}:{otp}".encode()).hexdigest()


@pytest.fixture(scope="module")
def vendor():
    v = {"society_id": SID, "name": "TEST_Vendor Plumb", "phone": "919999900001", "category": "Plumbing",
         "active": True, "response_time_hours": 2}
    v["_id"] = mdb.vendors.insert_one(v).inserted_id
    yield v
    mdb.vendors.delete_many({"name": {"$regex": "^TEST_"}})
    mdb.tickets.delete_many({"ticket_number": {"$regex": "^TEST_"}})


def mk_ticket(vendor, num, accepted=True, status="Pending", with_hash=True, attempts=0, vendor_id=True):
    oid = ObjectId()
    doc = {"_id": oid, "ticket_number": num, "society_id": SID, "resident_name": "TEST Resident",
           "resident_phone": "919999900099", "reporter_phone": "919999900099", "category": "Plumbing",
           "sub_category": "Tap leak", "matched_situation": "Leaking tap", "priority": "High", "sla_target": "4h",
           "description": "Tap leaking", "raw_message": "TEST bathroom tap leaking badly since morning",
           "flat": "A101", "tower": "T1", "location": "Flat", "status": status,
           "vendor_id": str(vendor["_id"]) if vendor_id else None, "vendor_name": vendor["name"],
           "vendor_accepted": accepted, "vendor_token": f"testtok_{oid}", "otp_attempts": attempts,
           "resolve_otp_hash": h(str(oid), OTP) if with_hash else None,
           "created_at": "2026-01-10T10:00:00+00:00", "updated_at": "2026-01-10T10:00:00+00:00", "timeline": []}
    mdb.tickets.insert_one(doc)
    return doc


# ---------- Public vendor API ----------
class TestVendorPublicAPI:
    def test_invalid_token_404(self, vendor):
        r = requests.get(f"{BASE_URL}/api/public/vendor/nope_invalid")
        assert r.status_code == 404

    def test_vendor_id_null_404(self, vendor):
        t = mk_ticket(vendor, "TEST_VNULL", vendor_id=False)
        assert requests.get(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}").status_code == 404
        assert requests.post(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve", json={"otp": OTP}).status_code == 404

    def test_get_details_accepted(self, vendor):
        t = mk_ticket(vendor, "TEST_VGET")
        r = requests.get(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}")
        assert r.status_code == 200
        d = r.json()
        assert d["ticket_number"] == "TEST_VGET"
        assert d["society_name"] == "Green Valley Residency"
        assert d["raw_message"].startswith("TEST bathroom")
        assert d["flat"] == "A101" and d["tower"] == "T1" and d["location"] == "Flat"
        assert d["resident_name"] == "TEST Resident" and d["resident_phone"] == "919999900099"
        assert d["sub_category"] == "Tap leak" and d["priority"] == "High" and d["sla_target"] == "4h"
        assert d["can_resolve"] is True and d["otp_locked"] is False and d["vendor_accepted"] is True
        assert "resolve_otp_hash" not in d and "_id" not in d

    def test_not_accepted_cannot_resolve(self, vendor):
        t = mk_ticket(vendor, "TEST_VNA", accepted=False)
        d = requests.get(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}").json()
        assert d["can_resolve"] is False
        r = requests.post(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve", json={"otp": OTP})
        assert r.status_code == 400
        assert mdb.tickets.find_one({"_id": t["_id"]})["status"] == "Pending"

    def test_resolved_ticket_cannot_resolve(self, vendor):
        t = mk_ticket(vendor, "TEST_VRES", status="Resolved")
        d = requests.get(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}").json()
        assert d["can_resolve"] is False
        assert requests.post(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve", json={"otp": OTP}).status_code == 400

    def test_wrong_otp_then_lock(self, vendor):
        t = mk_ticket(vendor, "TEST_VLOCK")
        url = f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve"
        msgs = []
        for _ in range(5):
            r = requests.post(url, json={"otp": "000000"})
            assert r.status_code == 400
            msgs.append(r.json()["detail"])
        assert msgs[0] == "Incorrect OTP. 4 attempt(s) left."
        assert msgs[3] == "Incorrect OTP. 1 attempt(s) left."
        assert "locked" in msgs[4].lower()
        r = requests.post(url, json={"otp": OTP})
        assert r.status_code == 400 and "locked" in r.json()["detail"].lower()
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["status"] == "Pending" and db_t["otp_attempts"] == 5
        d = requests.get(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}").json()
        assert d["otp_locked"] is True

    def test_correct_otp_resolves(self, vendor):
        t = mk_ticket(vendor, "TEST_VOK")
        url = f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve"
        r1 = requests.post(url, json={"otp": "111111"})
        assert r1.status_code == 400
        r = requests.post(url, json={"otp": OTP})
        assert r.status_code == 200 and r.json()["status"] == "Resolved"
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["status"] == "Resolved" and db_t["resolved_via"] == "vendor link"
        assert db_t["resolve_otp_hash"] is None
        assert any(e["event"] == "Marked Resolved" for e in db_t["timeline"])
        d = requests.get(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}").json()
        assert d["status"] == "Resolved" and d["can_resolve"] is False
        assert requests.post(url, json={"otp": OTP}).status_code == 400

    def test_legacy_no_hash_issues_new_otp(self, vendor):
        t = mk_ticket(vendor, "TEST_VLEG", with_hash=False)
        r = requests.post(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve", json={"otp": OTP})
        assert r.status_code == 400 and "new OTP" in r.json()["detail"]
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["resolve_otp_hash"] and len(db_t["resolve_otp_hash"]) == 64 and db_t["status"] == "Pending"

    def test_missing_otp_field_422(self, vendor):
        t = mk_ticket(vendor, "TEST_V422")
        assert requests.post(f"{BASE_URL}/api/public/vendor/{t['vendor_token']}/resolve", json={}).status_code == 422


# ---------- Direct python: pipeline + WhatsApp vendor actions (wa mocked) ----------
LOOP = asyncio.new_event_loop()


@pytest.fixture
def sent(monkeypatch):
    import whatsapp_client as wa
    out = []

    async def st(to, text, **kw):
        out.append(("text", to, text))

    async def sb(to, body, buttons, **kw):
        out.append(("buttons", to, body, buttons))
    monkeypatch.setattr(wa, "send_text", st)
    monkeypatch.setattr(wa, "send_buttons", sb)
    return out


def run(coro):
    return LOOP.run_until_complete(coro)


class TestPipelineDirect:
    def test_assign_vendor_detailed_message(self, vendor, sent, monkeypatch):
        import pipeline
        t = mk_ticket(vendor, "TEST_VASSIGN", accepted=True, attempts=3)
        old_tok = t["vendor_token"]
        fired = []
        monkeypatch.setattr(pipeline, "_fire", lambda c: fired.append(c))
        run(pipeline.assign_vendor(mdb.tickets.find_one({"_id": t["_id"]}), mdb.vendors.find_one({"_id": vendor["_id"]})))
        for c in fired:
            run(c)
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["vendor_token"] and db_t["vendor_token"] != old_tok
        assert db_t["resolve_otp_hash"] is None and db_t["otp_attempts"] == 0 and db_t["vendor_accepted"] is False
        texts = [s for s in sent if s[0] == "text" and s[1] == vendor["phone"]]
        assert texts, sent
        msg = texts[0][2]
        print(msg)
        for part in ["TEST_VASSIGN", "Green Valley Residency", "Plumbing", "Tap leak", "High", "4h",
                     "TEST bathroom tap leaking", "T1 A101", "Location: Flat", "TEST Resident", "919999900099",
                     "Reported:", "Respond by:", f"/v/{db_t['vendor_token']}"]:
            assert part in msg, part
        btn = [s for s in sent if s[0] == "buttons"]
        assert btn and [b["title"] for b in btn[0][3]] == ["Accept", "Reject"]
        assert sent.index(texts[0]) < sent.index(btn[0])
        # old link should be dead
        assert requests.get(f"{BASE_URL}/api/public/vendor/{old_tok}").status_code == 404

    def test_whatsapp_accept_issues_otp(self, vendor, sent):
        import routers.whatsapp_router as wr
        t = mk_ticket(vendor, "TEST_WACC", accepted=False, with_hash=False)
        run(wr._vendor_action(SID, vendor["phone"], str(t["_id"]), "accept"))
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["vendor_accepted"] is True and db_t["resolve_otp_hash"]
        cust = [s for s in sent if s[0] == "text" and s[1] == "919999900099"]
        assert cust, sent
        import re
        m = re.search(r"\*(\d{6})\*", cust[-1][2])
        assert m, cust[-1][2]
        assert h(str(t["_id"]), m.group(1)) == db_t["resolve_otp_hash"]
        vmsg = [s for s in sent if s[1] == vendor["phone"]][-1][2]
        assert "DONE <OTP>" in vmsg and f"/v/{t['vendor_token']}" in vmsg

    def test_whatsapp_resolve_requires_otp(self, vendor, sent):
        import routers.whatsapp_router as wr
        t = mk_ticket(vendor, "TEST_WRES")
        tid = str(t["_id"])
        run(wr._vendor_action(SID, vendor["phone"], tid, "resolve", otp=None))
        assert mdb.tickets.find_one({"_id": t["_id"]})["status"] == "Pending"
        assert "DONE <OTP>" in sent[-1][2]
        run(wr._vendor_action(SID, vendor["phone"], tid, "resolve", otp="999999"))
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["status"] == "Pending" and db_t["otp_attempts"] == 1
        assert "Incorrect OTP" in sent[-1][2]
        run(wr._vendor_action(SID, vendor["phone"], tid, "resolve", otp=OTP))
        db_t = mdb.tickets.find_one({"_id": t["_id"]})
        assert db_t["status"] == "Resolved" and db_t["resolved_via"] == "WhatsApp"

    def test_direct_reply_done_with_otp(self, vendor, sent):
        import routers.whatsapp_router as wr
        mdb.tickets.update_many({"vendor_id": str(vendor["_id"]), "status": {"$in": ["Open", "Pending"]}},
                                {"$set": {"status": "Cancelled"}})
        t = mk_ticket(vendor, "TEST_WDONE")
        run(wr._handle_direct_reply(SID, vendor["phone"], "DONE 000000"))
        assert mdb.tickets.find_one({"_id": t["_id"]})["status"] == "Pending"
        run(wr._handle_direct_reply(SID, vendor["phone"], "done"))
        assert mdb.tickets.find_one({"_id": t["_id"]})["status"] == "Pending"
        run(wr._handle_direct_reply(SID, vendor["phone"], "Done 123456"))
        assert mdb.tickets.find_one({"_id": t["_id"]})["status"] == "Resolved"


# ---------- Regression: admin close stays OTP-free ----------
class TestAdminResolveRegression:
    def test_admin_close_no_otp(self, vendor):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "admin@greenvalley.com", "password": "Admin@123"})
        assert r.status_code == 200
        tok = r.json()["token"]
        t = mk_ticket(vendor, "TEST_ADMCLOSE")
        r = requests.post(f"{BASE_URL}/api/society/tickets/{t['_id']}/close", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 200
        assert mdb.tickets.find_one({"_id": t["_id"]})["status"] == "Resolved"
