import asyncio, json, urllib.request
from dotenv import load_dotenv; load_dotenv()
from db import db
from models import now_iso
from bson import ObjectId


def api_url():
    return "http://localhost:8001"


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    vendor = await db.vendors.find_one({"society_id": sid, "categories": "Plumbing", "active": True})
    doc = {
        "ticket_number": "TKT-HTTP-1", "society_id": sid, "resident_name": "Res",
        "resident_phone": "919111111111", "reporter_phone": "919111111111",
        "category": "Plumbing", "description": "Leak", "flat": "B505", "priority": "High",
        "status": "Pending", "vendor_id": str(vendor["_id"]), "vendor_name": vendor["name"],
        "vendor_accepted": False, "created_at": now_iso(), "updated_at": now_iso(), "timeline": [],
    }
    await db.tickets.delete_many({"ticket_number": "TKT-HTTP-1"})
    r = await db.tickets.insert_one(doc); tid = str(r.inserted_id)
    await db.wa_processed.delete_many({"_id": "HTTPMSG-ACCEPT"})
    print("ticket:", tid, "vendor:", vendor["name"], "phone:", vendor["phone"])

    # Simulate a Whapi interactive button reply (vendor taps Accept) hitting the SEND webhook
    payload = {"messages": [{
        "chat_id": vendor["phone"], "from": vendor["phone"], "id": "HTTPMSG-ACCEPT",
        "type": "reply", "reply": {"buttons_reply": {"id": f"vendor_accept_{tid}", "title": "Accept"}},
    }]}
    url = api_url() + "/api/whapi/webhook/send"
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        print("webhook HTTP status:", resp.status)
    except Exception as e:
        print("webhook POST error:", e)

    await asyncio.sleep(2)
    t2 = await db.tickets.find_one({"_id": ObjectId(tid)})
    print("AFTER ACCEPT via HTTP -> vendor_accepted=", t2.get("vendor_accepted"), "status=", t2.get("status"), "response_due_at=", t2.get("response_due_at"))

    await db.tickets.delete_many({"ticket_number": "TKT-HTTP-1"})
    await db.wa_processed.delete_many({"_id": "HTTPMSG-ACCEPT"})
    print("cleanup done")

asyncio.run(main())
