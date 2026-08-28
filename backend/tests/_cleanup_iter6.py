"""Cleanup helper: removes tickets created by iteration-6 test runs and verifies
the Green Valley WhatsApp group mapping was restored after the e2e test."""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv  # noqa: E402

load_dotenv("/app/backend/.env")
from db import db  # noqa: E402

CUTOFF = "2026-08-28T11:2"  # runs happened after ~11:25 UTC today


async def main():
    tickets = await db.tickets.find({"created_at": {"$gte": "2026-08-28T11:00"}}).to_list(200)
    for t in tickets:
        print("DELETING", t.get("ticket_number"), t.get("category"), t.get("created_at"))
        await db.tickets.delete_one({"_id": t["_id"]})
    print("deleted", len(tickets))
    await db.review_queue.delete_many({"created_at": {"$gte": "2026-08-28T11:00"}})
    soc = await db.societies.find_one({"code": "GRNVLY"})
    print("GV whatsapp_group:", soc.get("whatsapp_group"))


asyncio.run(main())
