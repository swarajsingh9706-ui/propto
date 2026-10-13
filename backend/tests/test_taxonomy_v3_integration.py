"""Integration tests for Propto Taxonomy v3.2 pipeline + ticket listing + vendor routing."""
import os, time, uuid, pytest, requests
TAG = f"TEST-{uuid.uuid4().hex[:6]}"
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE = "https://complaint-whatsapp.preview.emergentagent.com"
try:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE = line.split("=", 1)[1].strip().rstrip("/")
except Exception:
    pass

ADMIN = {"email": "admin@greenvalley.com", "password": "Admin@123"}
RESIDENT_PHONE = "918111111101"


@pytest.fixture(scope="module")
def headers():
    r = requests.post(f"{BASE}/api/auth/login", json=ADMIN, timeout=30)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def created_ticket_numbers():
    nums = []
    yield nums
    try:
        from pymongo import MongoClient
        cli = MongoClient(os.environ["MONGO_URL"])
        db = cli[os.environ["DB_NAME"]]
        if nums:
            db.tickets.delete_many({"ticket_number": {"$in": nums}})
    except Exception as e:
        print("cleanup failed:", e)


def _simulate(headers, text):
    r = requests.post(f"{BASE}/api/society/whatsapp/simulate",
                      json={"phone": RESIDENT_PHONE, "text": text},
                      headers=headers, timeout=90)
    assert r.status_code == 200, f"{text} -> {r.status_code} {r.text}"
    return r.json()


def _get_ticket_by_number(headers, number):
    r = requests.get(f"{BASE}/api/society/tickets",
                     params={"search": number}, headers=headers, timeout=30)
    assert r.status_code == 200
    for t in r.json():
        if t.get("ticket_number") == number:
            return t
    return None


# ---------- Positive complaints ----------

def test_plumbing_tap_leak_creates_ticket(headers, created_ticket_numbers):
    res = _simulate(headers, f"{TAG} tap leaking in kitchen")
    assert res.get("status") == "ticket_created", res
    assert res["ai"]["category"] == "Plumbing & Leakage"
    assert res["ai"]["sub_category"].lower().startswith("tap")
    assert res["ai"]["routing_category"] == "Plumbing"
    assert res["ai"].get("issue_id")
    assert res["ai"].get("location") == "Flat"
    created_ticket_numbers.append(res["ticket_number"])
    t = _get_ticket_by_number(headers, res["ticket_number"])
    assert t is not None
    assert t["category"] == "Plumbing & Leakage"
    assert t["routing_category"] == "Plumbing"
    assert t.get("issue_id")
    assert t.get("location") == "Flat"


def test_no_power_electrical_critical(headers, created_ticket_numbers):
    res = _simulate(headers, f"{TAG} no power in flat")
    assert res.get("status") == "ticket_created", res
    assert res["ai"]["routing_category"] == "Electrical"
    assert res["ai"]["priority"] == "Critical"
    created_ticket_numbers.append(res["ticket_number"])


def test_water_supply_routing(headers, created_ticket_numbers):
    # LLM may occasionally mis-classify; retry up to 3 times
    res = None
    for _ in range(3):
        res = _simulate(headers, f"{TAG} water issue in my flat not coming")
        if res.get("status") == "ticket_created":
            break
    assert res.get("status") == "ticket_created", f"after retries: {res}"
    assert res["ai"].get("routing_category") == "Water Supply", res["ai"]
    created_ticket_numbers.append(res["ticket_number"])
    t = _get_ticket_by_number(headers, res["ticket_number"])
    assert t is not None
    # vendor must be Water Supply or fall back to Plumbing (if assigned)
    if t.get("vendor_id"):
        from pymongo import MongoClient
        from bson import ObjectId
        cli = MongoClient(os.environ["MONGO_URL"]); db = cli[os.environ["DB_NAME"]]
        v = db.vendors.find_one({"_id": ObjectId(t["vendor_id"])})
        cats = v.get("categories") or [v.get("category")]
        assert any(c in ("Water Supply", "Plumbing") for c in cats), cats


# ---------- Non-complaint ----------

@pytest.mark.parametrize("text", [
    "working on it rn",
    "on my way",
    "swimming pool issue is resolved",
])
def test_status_messages_do_not_create_tickets(headers, text):
    res = _simulate(headers, text)
    assert res.get("status") != "ticket_created", f"unexpected ticket for {text!r}: {res}"


# ---------- Listing with v3 categories ----------

def test_list_tickets_category_plumbing_includes_v3(headers, created_ticket_numbers):
    # ensure the plumbing ticket exists
    if not created_ticket_numbers:
        res = _simulate(headers, f"{TAG} tap leak listing check")
        if res.get("status") == "ticket_created":
            created_ticket_numbers.append(res["ticket_number"])
    r = requests.get(f"{BASE}/api/society/tickets?category=Plumbing", headers=headers, timeout=30)
    assert r.status_code == 200
    tickets = r.json()
    assert isinstance(tickets, list)
    nums = {t.get("ticket_number") for t in tickets}
    plumb_found = [n for n in created_ticket_numbers if n in nums]
    assert plumb_found, f"created={created_ticket_numbers}, listed={len(tickets)}"
    for t in tickets:
        assert t.get("category") == "Plumbing" or t.get("routing_category") == "Plumbing", t


def test_list_tickets_category_plus_search(headers):
    r = requests.get(f"{BASE}/api/society/tickets",
                     params={"category": "Plumbing", "search": "TEST"},
                     headers=headers, timeout=30)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


# ---------- Vendors still carry the 11 old categories ----------

def test_vendors_list_contains_old_categories(headers):
    r = requests.get(f"{BASE}/api/society/vendors", headers=headers, timeout=30)
    assert r.status_code == 200
    data = r.json()
    cats = set()
    for v in data:
        for c in (v.get("categories") or []):
            cats.add(c)
        if v.get("category"):
            cats.add(v["category"])
    OLD = {"Plumbing","Electrical","Lift","Security","Housekeeping","Civil",
           "Parking","Gardening","Water Supply","DG Set","Pest Control"}
    assert cats & OLD, f"no old vendor categories found: {cats}"
