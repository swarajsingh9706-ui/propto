from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
import uuid

from db import db
from models import SuggestionCreate, SuggestionStatusUpdate, SuggestionVote, now_iso
from auth_utils import require_society_admin, user_society_id
import whatsapp_client as wa
import audit

router = APIRouter(prefix="/api/society/suggestions", tags=["suggestions"])


def _clean(d):
    d["id"] = str(d.pop("_id"))
    d.pop("voters", None)
    return d


def _sid(user):
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


def _recompute(voters: dict):
    yes = sum(1 for v in voters.values() if v == "yes")
    no = sum(1 for v in voters.values() if v == "no")
    return yes, no


@router.get("")
async def list_suggestions(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    raw = await db.suggestions.find({"society_id": sid}).sort("created_at", -1).to_list(500)
    total_votes = sum((s.get("yes_votes", 0) + s.get("no_votes", 0)) for s in raw)
    stats = {
        "total": len(raw),
        "under_review": sum(1 for s in raw if s.get("status") == "Under Review"),
        "approved": sum(1 for s in raw if s.get("status") == "Approved"),
        "pending": sum(1 for s in raw if s.get("status") == "Pending"),
        "declined": sum(1 for s in raw if s.get("status") == "Declined"),
        "total_votes": total_votes,
    }
    return {"suggestions": [_clean(s) for s in raw], "stats": stats}


@router.post("")
async def create_suggestion(body: SuggestionCreate, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    society = await db.societies.find_one({"_id": ObjectId(sid)})
    doc = {
        "society_id": sid, "title": body.title, "category": body.category or "General",
        "author_name": body.author_name or "Admin", "flat": body.flat or "",
        "status": "Under Review", "voters": {}, "yes_votes": 0, "no_votes": 0,
        "poll_posted": False, "poll_message_id": None, "created_at": now_iso(), "updated_at": now_iso(),
    }
    res = await db.suggestions.insert_one(doc)
    gid = ((society or {}).get("whatsapp_group") or {}).get("chat_id")
    poll_msg_id = None
    posted = False
    if gid:
        r = await wa.send_poll(gid, f"{body.title} — Do you support this?", ["Yes", "No"], 1)
        poll_msg_id = wa.poll_message_id_from(r)
        posted = poll_msg_id is not None
    if not poll_msg_id:
        poll_msg_id = f"local-{uuid.uuid4().hex}"
    await db.suggestions.update_one({"_id": res.inserted_id}, {"$set": {"poll_posted": posted, "poll_message_id": poll_msg_id}})
    doc["_id"] = res.inserted_id
    out = _clean(doc)
    out["poll_posted"] = posted
    out["poll_message_id"] = poll_msg_id
    await audit.log(sid, "suggestion_created", f"Suggestion posted: {body.title}", actor=body.author_name or "Admin", category="suggestion")
    return out


@router.put("/{sug_id}")
async def update_status(sug_id: str, body: SuggestionStatusUpdate, user: dict = Depends(require_society_admin)):
    await db.suggestions.update_one({"_id": ObjectId(sug_id)}, {"$set": {"status": body.status, "updated_at": now_iso()}})
    s = await db.suggestions.find_one({"_id": ObjectId(sug_id)})
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    actor = user.get("name") or user.get("email") or "Admin"
    await audit.log(s.get("society_id"), "suggestion_status_changed", f"Suggestion '{s.get('title')}' marked {body.status}", actor=actor, category="suggestion")
    return _clean(s)


@router.post("/{sug_id}/vote")
async def vote(sug_id: str, body: SuggestionVote, user: dict = Depends(require_society_admin)):
    s = await db.suggestions.find_one({"_id": ObjectId(sug_id)})
    if not s:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    voters = s.get("voters", {}) or {}
    voters[f"manual_{uuid.uuid4().hex[:8]}"] = "yes" if body.vote == "yes" else "no"
    yes, no = _recompute(voters)
    await db.suggestions.update_one({"_id": s["_id"]}, {"$set": {"voters": voters, "yes_votes": yes, "no_votes": no, "updated_at": now_iso()}})
    return {"yes_votes": yes, "no_votes": no}


@router.delete("/{sug_id}")
async def delete_suggestion(sug_id: str, user: dict = Depends(require_society_admin)):
    await db.suggestions.delete_one({"_id": ObjectId(sug_id)})
    return {"status": "deleted"}
