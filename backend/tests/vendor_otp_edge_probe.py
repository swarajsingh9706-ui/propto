# Probe: re-tapping Accept on WhatsApp resets OTP lock / reopens resolved tickets (edge cases)
import os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
import whatsapp_client as wa
from db import db
from bson import ObjectId
import routers.whatsapp_router as wr


async def nop(*a, **k):
    return None
wa.send_text = nop
wa.send_buttons = nop


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    for status, attempts in [("Pending", 5), ("Resolved", 0)]:
        oid = ObjectId()
        await db.tickets.insert_one({"_id": oid, "ticket_number": f"TEST_EDGE_{status}", "society_id": sid,
                                     "status": status, "vendor_id": "x", "vendor_name": "TEST_V", "vendor_accepted": True,
                                     "otp_attempts": attempts, "resolve_otp_hash": "abc", "timeline": []})
        await wr._vendor_action(sid, "919999900001", str(oid), "accept")
        t = await db.tickets.find_one({"_id": oid})
        print(f"before status={status} attempts={attempts} -> after accept status={t['status']} attempts={t['otp_attempts']} hash_changed={t['resolve_otp_hash']!='abc'}")
    await db.tickets.delete_many({"ticket_number": {"$regex": "^TEST_EDGE_"}})

asyncio.run(main())
