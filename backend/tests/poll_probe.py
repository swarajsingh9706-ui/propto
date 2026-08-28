import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import whatsapp_client as wa
from db import db
from routers import whatsapp_router as wr

PATCH_PAYLOAD = {
    "messages_updates": [{
        "id": "POLLMSG123",
        "after_update": {
            "id": "POLLMSG123", "type": "poll", "chat_id": "120363427379658951@g.us",
            "poll": {"title": "Install borewell — Do you support this?", "total": 3,
                     "results": [{"name": "Yes", "count": 2, "voters": ["a", "b"]},
                                 {"name": "No", "count": 1, "voters": ["c"]}]},
        },
        "changes": ["poll"],
    }],
    "event": {"type": "messages", "event": "patch"},
}

VOTE_POST_PAYLOAD = {
    "messages": [{
        "id": "VOTEEVT1", "from_me": True, "type": "action", "chat_id": "120363427379658951@g.us",
        "action": {"target": "POLLMSG123", "type": "vote", "votes": ["optYes"]}, "from": "919601703609",
    }],
    "event": {"type": "messages", "event": "post"},
}


async def main():
    # seed a suggestion with the poll id
    await db.suggestions.delete_many({"title": "Install borewell"})
    await db.suggestions.insert_one({
        "society_id": "TESTSOC", "title": "Install borewell", "status": "Under Review",
        "voters": {}, "yes_votes": 0, "no_votes": 0, "poll_message_id": "POLLMSG123",
    })

    p1 = wa.parse_whapi_inbound(PATCH_PAYLOAD)
    print("PATCH parsed:", [{"type": m.get("type"), "id": m.get("id"), "has_results": bool((m.get('poll') or {}).get('results'))} for m in p1])
    for m in p1:
        await wr._apply_poll_results(m)
    s = await db.suggestions.find_one({"title": "Install borewell"})
    print("After PATCH -> yes=%s no=%s" % (s["yes_votes"], s["no_votes"]))

    p2 = wa.parse_whapi_inbound(VOTE_POST_PAYLOAD)
    print("VOTE-POST parsed:", [{"type": m.get("type"), "fetch_id": m.get("poll_fetch_id"), "from_me": m.get("from_me")} for m in p2])

    await db.suggestions.delete_many({"title": "Install borewell"})
    print("OK")

asyncio.run(main())
