import asyncio
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv; load_dotenv()
from bson import ObjectId
from db import db
from models import now_iso
import pipeline


async def mk_ticket(sid, vendor, num):
    doc = {
        "ticket_number": num, "society_id": sid, "resident_name": "Test Res",
        "resident_phone": "919111111111", "reporter_phone": "919111111111",
        "category": "Plumbing", "description": "Leak", "flat": "B505", "priority": "High",
        "status": "Pending", "vendor_id": str(vendor["_id"]), "vendor_name": vendor["name"],
        "vendor_accepted": False, "source_message_id": None,
        "created_at": now_iso(), "updated_at": now_iso(), "timeline": [],
    }
    r = await db.tickets.insert_one(doc); doc["_id"] = r.inserted_id
    return doc


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    v1 = await db.vendors.find_one({"society_id": sid})
    print("vendor:", v1["name"])

    # ensure committee: a Society Manager (acc 1h) and a Secretary (acc 2h)
    await db.committee.delete_many({"society_id": sid, "name": {"$regex": "^ZZ "}})
    await db.committee.insert_one({"society_id": sid, "name": "ZZ Manager", "role": "Society Manager", "phone": "919000000011", "acceptance_time_hours": 1, "priority": None, "created_at": now_iso()})
    await db.committee.insert_one({"society_id": sid, "name": "ZZ Secretary", "role": "Secretary", "phone": "919000000012", "acceptance_time_hours": 2, "priority": None, "created_at": now_iso()})

    chain = await pipeline._committee_chain(sid)
    print("CHAIN:", [(p, m["role"], m["name"]) for p, m in chain if m["name"].startswith("ZZ")])

    # vendor timeout -> should go to Society Manager (priority 1)
    t = await mk_ticket(sid, v1, "TKT-ZZ-1")
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"response_due_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
    await pipeline.check_vendor_timeouts()
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("after vendor timeout -> assigned_to=", t2.get("assigned_to"), "role=", t2.get("committee_assignee_role"), "prio=", t2.get("committee_priority"))

    # now manager timeout -> should go to Secretary
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"response_due_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
    await pipeline.check_vendor_timeouts()
    t3 = await db.tickets.find_one({"_id": t["_id"]})
    print("after manager timeout -> assigned_to=", t3.get("assigned_to"), "role=", t3.get("committee_assignee_role"), "prio=", t3.get("committee_priority"))

    # secretary timeout -> chain exhausted
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"response_due_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()}})
    await pipeline.check_vendor_timeouts()
    t4 = await db.tickets.find_one({"_id": t["_id"]})
    print("after secretary timeout -> assigned_to=", t4.get("assigned_to"), "committee_id=", t4.get("committee_assignee_id"))

    # NO MANAGER case: remove manager, secretary should be priority 1
    await db.committee.delete_one({"society_id": sid, "name": "ZZ Manager"})
    chain2 = await pipeline._committee_chain(sid)
    print("CHAIN no-manager:", [(p, m["role"], m["name"]) for p, m in chain2 if m["name"].startswith("ZZ")])

    # cleanup
    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-ZZ-"}})
    await db.committee.delete_many({"society_id": sid, "name": {"$regex": "^ZZ "}})
    print("cleanup done")

asyncio.run(main())
