"""Pool complaints -> Pool AMC Vendor; no vendor for a category -> Society Manager / committee chain."""
import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from bson import ObjectId
from db import db
import pipeline, taxonomy_v3

pipeline.wa.send_text = lambda *a, **k: asyncio.sleep(0)
pipeline.wa.send_buttons = lambda *a, **k: asyncio.sleep(0)


def ai_for(text):
    tx = taxonomy_v3.match(text)
    return {"intent": "Complaint", "confidence": 0.9, "description": text, "flat": "TEST-P1",
            "category": tx["category"], "sub_category": tx["label"], "priority": tx["severity"],
            "routing_category": tx["vendor_category"], "handled_by": tx["handled_by"], "vendor_required": tx["vendor_required"]}


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    prev = soc.get("manager_only_routing", True)
    await db.societies.update_one({"_id": soc["_id"]}, {"$set": {"manager_only_routing": False}})
    fails, made = 0, []
    try:
        text = "swimming pool water is dirty"
        ai = ai_for(text)
        print("routing_category:", ai["routing_category"], "| handled_by:", ai["handled_by"])
        fails += ai["routing_category"] != "Pool AMC Vendor"

        t1 = await pipeline.create_ticket(sid, ai, None, "whatsapp", text, True)
        made.append(t1["_id"]); d1 = await db.tickets.find_one({"_id": ObjectId(str(t1["_id"]))})
        ok = not d1.get("vendor_id") and d1.get("committee_assignee_id")
        fails += not ok
        print(f"{'OK  ' if ok else 'FAIL'} no pool vendor -> committee: {d1.get('assigned_to')}")

        v = await db.vendors.insert_one({"society_id": sid, "name": "TEST_Pool AMC", "phone": "919999000111",
                                         "categories": ["Pool AMC Vendor"], "priorities": {"Pool AMC Vendor": 1},
                                         "availability": True, "active": True, "response_time_hours": 2})
        t2 = await pipeline.create_ticket(sid, ai_for("pool filter not working"), None, "whatsapp", "pool filter not working", True)
        made.append(t2["_id"]); d2 = await db.tickets.find_one({"_id": ObjectId(str(t2["_id"]))})
        ok = d2.get("vendor_name") == "TEST_Pool AMC"
        fails += not ok
        print(f"{'OK  ' if ok else 'FAIL'} pool vendor present -> {d2.get('vendor_name')}")
        await db.vendors.delete_one({"_id": v.inserted_id})

        t3 = await pipeline.create_ticket(sid, {**ai_for("tap leaking in kitchen"), "routing_category": "TEST_NoVendorCat"},
                                          None, "whatsapp", "tap leaking in kitchen", True)
        made.append(t3["_id"]); d3 = await db.tickets.find_one({"_id": ObjectId(str(t3["_id"]))})
        ok = not d3.get("vendor_id") and d3.get("committee_assignee_id")
        fails += not ok
        print(f"{'OK  ' if ok else 'FAIL'} any category without vendor -> committee: {d3.get('assigned_to')}")
    finally:
        await db.societies.update_one({"_id": soc["_id"]}, {"$set": {"manager_only_routing": prev}})
        await db.tickets.delete_many({"_id": {"$in": [ObjectId(str(i)) for i in made]}})
        await db.vendors.delete_many({"name": "TEST_Pool AMC"})
    print("FAILURES:", fails)

asyncio.run(main())
