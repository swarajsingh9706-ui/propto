import asyncio
from dotenv import load_dotenv; load_dotenv()
from bson import ObjectId
from db import db
from models import now_iso
import routers.whatsapp_router as wr


async def mk_ticket(sid, vendor, num):
    doc = {
        "ticket_number": num, "society_id": sid, "resident_name": "Res",
        "resident_phone": "919111111111", "reporter_phone": "919111111111",
        "category": "Plumbing", "description": "Leak", "flat": "B505", "priority": "High",
        "status": "Pending", "vendor_id": str(vendor["_id"]), "vendor_name": vendor["name"],
        "vendor_accepted": False, "source_message_id": None,
        "created_at": now_iso(), "updated_at": now_iso(), "timeline": [],
    }
    r = await db.tickets.insert_one(doc); doc["_id"] = r.inserted_id
    return doc


def dm_payload(from_phone, text, mid):
    return {"messages": [{"chat_id": from_phone, "from": from_phone, "id": mid,
                          "type": "text", "text": {"body": text}}]}


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    # ensure two plumbing vendors so reject reassigns to the OTHER one
    vs = await db.vendors.find({"society_id": sid, "categories": "Plumbing", "active": True}).to_list(10)
    print("plumbing vendors:", [v["name"] for v in vs])
    v1 = vs[0]
    t = await mk_ticket(sid, v1, "TKT-RJ-1")
    await db.wa_processed.delete_many({"_id": {"$regex": "^RJMSG"}})

    # Vendor replies "Reject" as a DM that arrives on the READER webhook
    await wr.process_whapi(dm_payload(v1["phone"], "Reject", "RJMSG1"), role="read")
    t2 = await db.tickets.find_one({"_id": t["_id"]})
    print("after READER reject -> status=", t2.get("status"), "vendor=", t2.get("vendor_name"), "assigned_to=", t2.get("assigned_to"), "committee_role=", t2.get("committee_assignee_role"))

    # Same message id again (simulating sender webhook duplicate) -> should be skipped
    await wr.process_whapi(dm_payload(v1["phone"], "Reject", "RJMSG1"), role="send")
    t3 = await db.tickets.find_one({"_id": t["_id"]})
    print("after DUPLICATE -> status=", t3.get("status"), "vendor=", t3.get("vendor_name"), "(should match previous)")

    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-RJ-"}})
    await db.wa_processed.delete_many({"_id": {"$regex": "^RJMSG"}})
    print("cleanup done")

asyncio.run(main())
