from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import PlainTextResponse
from bson import ObjectId
import os

from db import db
from models import SimulateMessage, GroupConnect, TestSend, now_iso
from auth_utils import require_society_admin, user_society_id, get_current_user
import whatsapp_client as wa
import pipeline

router = APIRouter(tags=["whatsapp"])


def _sid(user):
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


# -------- Meta Webhook (public) --------
@router.get("/api/webhook")
async def verify_webhook(request: Request):
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")
    if mode == "subscribe" and token == os.environ.get("WHATSAPP_VERIFY_TOKEN"):
        return PlainTextResponse(content=challenge or "")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/api/webhook")
async def receive_webhook(request: Request):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not wa.verify_signature(body, signature):
        raise HTTPException(status_code=401, detail="Invalid signature")
    payload = await request.json()
    messages = wa.parse_inbound(payload)
    for m in messages:
        phone_id = m.get("phone_number_id")
        society = await db.societies.find_one({"whatsapp_group.phone_number_id": phone_id}) if phone_id else None
        if not society:
            society = await db.societies.find_one({"monitoring": True})
        if not society:
            continue
        sid = str(society["_id"])
        if m.get("button_id"):
            await _handle_button(sid, m["from"], m["button_id"])
        elif m.get("text"):
            await pipeline.process_message(sid, m["from"], m["text"])
    return {"status": "ok"}


async def _handle_button(society_id: str, phone: str, button_id: str):
    if button_id.startswith("vendor_accept_"):
        tid = button_id.replace("vendor_accept_", "")
        await db.tickets.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "Pending", "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor Accepted", f"{phone} accepted the job")
    elif button_id.startswith("vendor_reject_"):
        tid = button_id.replace("vendor_reject_", "")
        await db.tickets.update_one({"_id": ObjectId(tid)}, {"$set": {"vendor_id": None, "vendor_name": None, "status": "Open", "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor Rejected", f"{phone} rejected; needs reassignment")
    elif button_id.startswith("vendor_resolved_"):
        tid = button_id.replace("vendor_resolved_", "")
        await db.tickets.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "Resolved", "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Marked Resolved", f"Resolved by vendor {phone}")
    elif button_id == "resident_confirm":
        item = await db.review_queue.find_one({"society_id": society_id, "phone": phone, "status": "pending"}, sort=[("created_at", -1)])
        if item:
            ai = dict(item.get("ai_result") or {})
            ai["intent"] = "Complaint"
            resident = await pipeline.find_resident(society_id, phone=phone, flat=ai.get("flat"))
            ticket = await pipeline.create_ticket(society_id, ai, resident, "resident_confirm", item.get("text", ""), ai_generated=True)
            await db.review_queue.update_one({"_id": item["_id"]}, {"$set": {"status": "approved", "ticket_number": ticket["ticket_number"], "reviewed_at": now_iso()}})
    elif button_id == "resident_cancel":
        await db.review_queue.update_many({"society_id": society_id, "phone": phone, "status": "pending"}, {"$set": {"status": "rejected", "reviewed_at": now_iso()}})


# -------- Group management --------
@router.get("/api/society/whatsapp/status")
async def wa_status(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    s = await db.societies.find_one({"_id": ObjectId(sid)})
    return {
        "connected": bool(s and s.get("whatsapp_group")),
        "group": s.get("whatsapp_group") if s else None,
        "monitoring": s.get("monitoring", False) if s else False,
        "api_configured": wa.is_configured(),
    }


@router.post("/api/society/whatsapp/connect")
async def wa_connect(body: GroupConnect, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    await db.societies.update_one(
        {"_id": ObjectId(sid)},
        {"$set": {"whatsapp_group": {"group_name": body.group_name, "group_id": body.group_id,
                                     "phone_number_id": os.environ.get("WHATSAPP_PHONE_ID", "")},
                  "monitoring": True}},
    )
    return {"status": "connected"}


@router.post("/api/society/whatsapp/toggle-monitoring")
async def toggle_monitoring(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    s = await db.societies.find_one({"_id": ObjectId(sid)})
    new_val = not s.get("monitoring", False)
    await db.societies.update_one({"_id": ObjectId(sid)}, {"$set": {"monitoring": new_val}})
    return {"monitoring": new_val}


@router.get("/api/society/whatsapp/check")
async def wa_check(user: dict = Depends(require_society_admin)):
    return await wa.check_connection()


@router.post("/api/society/whatsapp/test-send")
async def wa_test_send(body: TestSend, user: dict = Depends(require_society_admin)):
    if not wa.is_configured():
        raise HTTPException(status_code=400, detail="WhatsApp API not configured")
    try:
        res = await wa.send_text(body.phone, "✅ PROPTO is connected to this WhatsApp Business number. Live complaint monitoring is active.")
        return {"ok": True, "response": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Simulator (test the full flow without live WhatsApp) --------
@router.post("/api/society/whatsapp/simulate")
async def simulate(body: SimulateMessage, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    result = await pipeline.process_message(sid, body.phone, body.text)
    return result
