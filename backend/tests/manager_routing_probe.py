import asyncio
from dotenv import load_dotenv; load_dotenv()
from bson import ObjectId
from db import db
from models import now_iso
import pipeline


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    await db.societies.update_one({"_id": soc["_id"]}, {"$set": {"manager_only_routing": True}})

    # ensure a Society Manager committee member exists
    await db.committee.delete_many({"society_id": sid, "name": {"$regex": "^ZZ "}})
    await db.committee.insert_one({"society_id": sid, "name": "ZZ Manager", "role": "Society Manager", "phone": "919000000011", "acceptance_time_hours": 2, "priority": None, "created_at": now_iso()})

    ai = {"category": "Security", "description": "Guard sleeping at gate", "priority": "Low", "handled_by": "Society Manager"}
    doc = await pipeline.create_ticket(sid, ai, None, "test", "guard sleeping", True, notify_to=None)
    t = await db.tickets.find_one({"_id": doc["_id"]})
    print("NEW manager ticket:")
    print("  status=", t.get("status"), "| committee_role=", t.get("committee_assignee_role"), "| committee_accepted=", t.get("committee_accepted"), "| response_due_at set=", bool(t.get("response_due_at")))
    print("  assigned_to=", t.get("assigned_to"))

    await db.tickets.delete_many({"_id": doc["_id"]})
    await db.committee.delete_many({"society_id": sid, "name": {"$regex": "^ZZ "}})
    print("cleanup done")

asyncio.run(main())
