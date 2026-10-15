# Seed TEST_ tickets for the vendor page UI test (run with `python tests/seed_vendor_ui.py [clean]`)
import os, sys, hashlib
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
mdb = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
if len(sys.argv) > 1 and sys.argv[1] == "clean":
    print(mdb.tickets.delete_many({"ticket_number": {"$regex": "^TEST_"}}).deleted_count,
          mdb.vendors.delete_many({"name": {"$regex": "^TEST_"}}).deleted_count)
    sys.exit()
sid = str(mdb.societies.find_one({"name": "Green Valley Residency"})["_id"])
vid = mdb.vendors.insert_one({"society_id": sid, "name": "TEST_UI Vendor", "phone": "919999900002", "category": "Plumbing", "active": True}).inserted_id
for key, accepted, status, attempts in [("acc", True, "Pending", 0), ("na", False, "Pending", 0), ("lock", True, "Pending", 5), ("res", True, "Resolved", 0)]:
    oid = ObjectId()
    mdb.tickets.insert_one({"_id": oid, "ticket_number": f"TEST_UI_{key.upper()}", "society_id": sid, "resident_name": "TEST UI Resident",
        "reporter_phone": "919999900098", "category": "Plumbing", "sub_category": "Tap leak", "priority": "High", "sla_target": "4h",
        "description": "Tap leaking", "raw_message": "TEST UI kitchen tap leaking", "flat": "B302", "tower": "T2", "status": status,
        "vendor_id": str(vid), "vendor_name": "TEST_UI Vendor", "vendor_accepted": accepted, "vendor_token": f"testtok_ui_{key}",
        "otp_attempts": attempts, "resolve_otp_hash": hashlib.sha256(f"{oid}:123456".encode()).hexdigest(),
        "created_at": "2026-01-10T10:00:00+00:00", "updated_at": "2026-01-10T10:00:00+00:00",
        "response_due_at": "2026-01-10T12:00:00+00:00", "timeline": []})
print("seeded")
