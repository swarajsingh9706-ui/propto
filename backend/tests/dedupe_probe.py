import asyncio
from dotenv import load_dotenv; load_dotenv()
from db import db
from models import now_iso
import pipeline


async def mk(sid, flat, category, desc, raw):
    doc = {"ticket_number": "TKT-DUP-" + (flat or "NF") + category[:3], "society_id": sid, "flat": flat,
           "category": category, "description": desc, "raw_message": raw,
           "status": "Open", "created_at": now_iso(), "updated_at": now_iso(), "timeline": []}
    r = await db.tickets.insert_one(doc); doc["_id"] = r.inserted_id
    return doc


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-DUP-"}})

    # WITH flat
    await mk(sid, "A701", "Power Supply & Backup", "No electricity/light in the flat.", "No light in my flat")
    d1 = await pipeline.find_duplicate(sid, "A701", "Common Area Lighting", "No electricity in the flat since yesterday")
    print("CASE1 same-flat reworded diff-category -> dup?", bool(d1), "(expect True)")
    d2 = await pipeline.find_duplicate(sid, "A701", "Water Supply", "No water in the flat")
    print("CASE2 same-flat different issue -> dup?", bool(d2), "(expect False)")

    # FLATLESS (the real live scenario: Flat: —)
    await mk(sid, "", "Security & Access", "Security guard is sleeping at the gate.", "Security guard sleeping at gate")
    d3 = await pipeline.find_duplicate(sid, "", "Society Manager", "Security guard sleeping at the gate since yesterday")
    print("CASE3 flatless reworded -> dup?", bool(d3), "(expect True)")
    d4 = await pipeline.find_duplicate(sid, "", "Housekeeping", "Lift is not working in B wing")
    print("CASE4 flatless different issue -> dup?", bool(d4), "(expect False)")

    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-DUP-"}})
    print("cleanup done")

asyncio.run(main())
