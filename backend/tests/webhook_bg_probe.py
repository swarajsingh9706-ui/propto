import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import db
from models import now_iso

GID = "TESTGROUP999@g.us"


async def setup():
    soc = await db.societies.find_one({"code": "GRNVLY"})
    sid = str(soc["_id"])
    await db.societies.update_one({"_id": soc["_id"]}, {"$set": {"whatsapp_group.chat_id": GID, "monitoring": True}})
    await db.ai_activity.delete_many({"society_id": sid})
    await db.residents.update_one({"society_id": sid, "flat": "B302"}, {"$set": {"phone": "919601703609"}}, upsert=False)
    print("SETUP sid=%s chat_id=%s cleared ai_activity" % (sid, GID))


async def check():
    soc = await db.societies.find_one({"code": "GRNVLY"})
    sid = str(soc["_id"])
    n = await db.ai_activity.count_documents({"society_id": sid})
    logs = await db.ai_activity.find({"society_id": sid}).sort("created_at", -1).to_list(5)
    print("ai_activity count=%d" % n)
    for l in logs:
        print("  ->", l.get("decision"), "|", (l.get("text") or "")[:40], "|", l.get("ticket_number"))


mode = sys.argv[1] if len(sys.argv) > 1 else "check"
asyncio.run(setup() if mode == "setup" else check())
