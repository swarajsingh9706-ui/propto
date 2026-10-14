from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId

from db import db
from models import ReviewDecision, now_iso
from auth_utils import require_society_admin, user_society_id
import pipeline

router = APIRouter(prefix="/api/society/ai", tags=["ai"])


def _clean(doc):
    doc["id"] = str(doc.pop("_id"))
    return doc


def _sid(user):
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


@router.get("/review-queue")
async def review_queue(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    return [_clean(r) for r in await db.review_queue.find({"society_id": sid, "status": "pending"}).sort("created_at", -1).to_list(200)]


@router.post("/review-queue/{review_id}")
async def decide(review_id: str, body: ReviewDecision, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    review = await db.review_queue.find_one({"_id": ObjectId(review_id)})
    if not review:
        raise HTTPException(status_code=404, detail="Review item not found")

    if body.action == "reject":
        await db.review_queue.update_one({"_id": ObjectId(review_id)},
                                         {"$set": {"status": "rejected", "reviewed_at": now_iso()}})
        return {"status": "rejected"}

    ai = dict(review.get("ai_result") or {})
    if body.category: ai["category"] = body.category
    if body.flat: ai["flat"] = body.flat
    if body.tower: ai["tower"] = body.tower
    if body.priority: ai["priority"] = body.priority
    if body.description: ai["description"] = body.description
    ai["intent"] = "Complaint"

    resident = await pipeline.find_resident(sid, phone=review.get("phone"), flat=ai.get("flat"))
    ticket = await pipeline.create_ticket(sid, ai, resident, "hitl_review", review.get("text", ""), ai_generated=True)
    await db.review_queue.update_one({"_id": ObjectId(review_id)},
                                     {"$set": {"status": "approved", "reviewed_at": now_iso(),
                                               "ticket_number": ticket["ticket_number"]}})
    await pipeline.log_activity(sid, review.get("phone"), review.get("text", ""), "ticket_created",
                                ai=ai, reason="HITL approved", ticket_number=ticket["ticket_number"])
    return {"status": "approved", "ticket_number": ticket["ticket_number"]}
