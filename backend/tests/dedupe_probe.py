import asyncio
from dotenv import load_dotenv; load_dotenv()
from db import db
from models import now_iso
import pipeline


async def mk(sid, flat, category, desc, raw):
    doc = {"ticket_number": "TKT-DUP-" + category[:3], "society_id": sid, "flat": flat,
           "category": category, "description": desc, "raw_message": raw,
           "status": "Open", "created_at": now_iso(), "updated_at": now_iso(), "timeline": []}
    r = await db.tickets.insert_one(doc); doc["_id"] = r.inserted_id
    return doc


async def main():
    soc = await db.societies.find_one({"name": "Green Valley Residency"})
    sid = str(soc["_id"])
    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-DUP-"}})

    # Existing ticket (first message) — Electrical category
    await mk(sid, "A701", "Power Supply & Backup", "No electricity/light in the flat.", "No light in my flat")

    # Case 1: near-identical second message, DIFFERENT category -> should be DUPLICATE
    d1 = await pipeline.find_duplicate(sid, "A701", "Common Area Lighting", "No electricity in the flat since yesterday")
    print("CASE1 (light since yesterday, diff category) -> duplicate?", bool(d1))

    # Case 2: genuinely different issue, same flat -> should NOT be duplicate
    d2 = await pipeline.find_duplicate(sid, "A701", "Water Supply", "No water in the flat")
    print("CASE2 (no water) -> duplicate?", bool(d2), "(expected False)")

    # Case 3: different flat -> not duplicate
    d3 = await pipeline.find_duplicate(sid, "B202", "Power Supply & Backup", "No electricity/light in the flat.")
    print("CASE3 (other flat) -> duplicate?", bool(d3), "(expected False)")

    await db.tickets.delete_many({"ticket_number": {"$regex": "^TKT-DUP-"}})
    print("cleanup done")

asyncio.run(main())
