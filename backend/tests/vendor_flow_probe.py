import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv; load_dotenv()
from bson import ObjectId
from db import db
from models import now_iso
import pipeline
import routers.whatsapp_router as wr


async def mk_ticket(sid, vendor, num):
    doc = {
        "ticket_number": num, "society_id": sid, "resident_name": "Test Resident",
        "resident_phone": "919111111111", "reporter_phone": "919111111111",
        "category": "Plumbing", "description": "Leak in bathroom", "flat": "B505",
        "priority": "High", "status": "Pending", "vendor_id": str(vendor["_id"]),
        "vendor_name": vendor["name"], "vendor_accepted": False,
        "source_message_id": None, "created_at": now_iso(), "updated_at": now_iso(),
        "timeline": [],
    }
    r = await db.tickets.insert_one(doc)
    doc["_id"] = r.inserted_id
    return doc


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    v1 = await db.vendors.find_one({"society_id": sid, "name": "RespTest Vendor"})
    # ensure a second plumbing vendor exists for reassignment test
    v2 = await db.vendors.find_one({"society_id": sid, "name": "AquaFix Plumbing"})
    print("v1=", v1 and v1["name"], "v2=", v2 and v2["name"])

    # ---- ACCEPT ----
    t = await mk_ticket(sid, v1, "TKT-TEST-ACC")
    await wr._vendor_action(sid, v1["phone"], str(t["_id"]), "accept")
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("ACCEPT -> vendor_accepted=", t2.get("vendor_accepted"), "response_due_at=", t2.get("response_due_at"), "status=", t2.get("status"))

    # ---- REJECT with another vendor available ----
    t = await mk_ticket(sid, v1, "TKT-TEST-REJ1")
    await wr._vendor_action(sid, v1["phone"], str(t["_id"]), "reject")
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("REJECT(w/ alt) -> status=", t2.get("status"), "assigned vendor=", t2.get("vendor_name"), "assigned_to=", t2.get("assigned_to"))

    # ---- REJECT with NO other vendor (use a unique category vendor) ----
    vuniq = await db.vendors.find_one({"society_id": sid, "name": "DefaultRT Vendor"})  # Electrical, sole
    t = await mk_ticket(sid, vuniq, "TKT-TEST-REJ2")
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"category": "Electrical"}})
    t = await db.tickets.find_one({"_id": t["_id"]})
    await wr._vendor_action(sid, vuniq["phone"], str(t["_id"]), "reject")
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("REJECT(no alt) -> status=", t2.get("status"), "assigned_to=", t2.get("assigned_to"), "vendor_name=", t2.get("vendor_name"))

    # ---- RESOLVE ----
    t = await mk_ticket(sid, v1, "TKT-TEST-RES")
    await wr._vendor_action(sid, v1["phone"], str(t["_id"]), "resolve")
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("RESOLVE -> status=", t2.get("status"))

    # ---- TIMEOUT ----
    t = await mk_ticket(sid, v1, "TKT-TEST-TMO")
    past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"response_due_at": past}})
    res = await pipeline.check_vendor_timeouts()
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("TIMEOUT -> reassigned=", res["reassigned"], "assigned_to=", t2.get("assigned_to"), "status=", t2.get("status"), "vendor_id=", t2.get("vendor_id"))

    # cleanup test tickets
    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-TEST-"}})
    print("cleanup done")

asyncio.run(main())
