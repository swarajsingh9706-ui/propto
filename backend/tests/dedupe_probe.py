import asyncio, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv; load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))
from db import db
from models import now_iso
import pipeline

N = [0]


async def mk(sid, flat, category, desc, phone):
    N[0] += 1
    doc = {"ticket_number": f"TKT-DUP-{N[0]}", "society_id": sid, "flat": flat, "category": category,
           "description": desc, "raw_message": desc, "reporter_phone": phone,
           "status": "Open", "created_at": now_iso(), "updated_at": now_iso(), "timeline": []}
    await db.tickets.insert_one(doc)


def check(label, got, exp, fails):
    ok = bool(got) == exp
    fails += 0 if ok else 1
    print(f"{'OK  ' if ok else 'FAIL'} {label}: dup={bool(got)} (expect {exp})")
    return fails


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-DUP-"}})
    f = 0
    await mk(sid, "A701", "Electrical", "No electricity in the flat", "910000000001")
    f = check("same flat, same resident, reworded", await pipeline.find_duplicate(sid, "A701", "Electrical", "No light in flat since yesterday", "910000000001"), True, f)
    f = check("same flat, different resident", await pipeline.find_duplicate(sid, "A701", "Electrical", "No electricity in the flat", "910000000002"), True, f)
    f = check("same flat, different issue", await pipeline.find_duplicate(sid, "A701", "Water Supply", "No water in the flat", "910000000001"), False, f)
    f = check("different flat, exact same text", await pipeline.find_duplicate(sid, "B502", "Electrical", "No electricity in the flat", "910000000003"), False, f)

    await mk(sid, "", "Security & Gate", "Security guard sleeping at the gate", "910000000004")
    f = check("flatless, same resident, reworded", await pipeline.find_duplicate(sid, "", "Security & Gate", "Security guard is sleeping at gate since yesterday", "910000000004"), True, f)
    f = check("flatless, different resident, exact same text", await pipeline.find_duplicate(sid, "", "Security & Gate", "Security guard sleeping at the gate", "910000000005"), False, f)
    f = check("flatless, no phone", await pipeline.find_duplicate(sid, "", "Security & Gate", "Security guard sleeping at the gate", None), False, f)

    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-DUP-"}})
    print("FAILURES:", f)

asyncio.run(main())
