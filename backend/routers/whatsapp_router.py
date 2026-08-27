from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import PlainTextResponse
from bson import ObjectId
import os
import logging
import json

from db import db
from models import SimulateMessage, GroupConnect, TestSend, now_iso
from auth_utils import require_society_admin, user_society_id, get_current_user
import whatsapp_client as wa
import pipeline
import audit

router = APIRouter(tags=["whatsapp"])
logger = logging.getLogger("propto.whatsapp_router")


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
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}
    try:
        messages = wa.parse_meta_inbound(payload)
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
    except Exception as e:
        logger.exception("Meta webhook processing failed: %s", e)
    return {"status": "ok"}


async def _ack(phone: str, text: str):
    try:
        await wa.send_text(phone, text)
    except Exception as e:
        logger.warning("ack send failed: %s", e)


async def _notify_followers(ticket: dict, text: str):
    """Post an update to the origin group (quoting the complaint) or DM the resident."""
    gid = ticket.get("group_chat_id")
    try:
        if gid:
            await wa.send_text(gid, text, reply_to=ticket.get("origin_message_id"))
        elif ticket.get("resident_phone"):
            await wa.send_text(ticket["resident_phone"], text)
    except Exception as e:
        logger.warning("follower notify failed: %s", e)


async def _vendor_action(society_id: str, phone: str, tid: str, action: str):
    try:
        ticket = await db.tickets.find_one({"_id": ObjectId(tid)})
    except Exception:
        ticket = None
    if not ticket:
        logger.info("vendor_action: ticket %s not found", tid)
        return
    vname = ticket.get("vendor_name") or "The vendor"
    flat = ticket.get("flat") or "—"
    num = ticket.get("ticket_number")
    cat = ticket.get("category")

    if action == "accept":
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"status": "Pending", "vendor_accepted": True, "awaiting_vendor_time": False, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor Accepted", f"{vname} accepted the job")
        await _ack(phone, f"👍 Thanks! You've *accepted* {num} ({cat} · Flat {flat}). Please visit and reply *DONE* once resolved.")
        await _notify_followers(ticket, f"👷 {vname} accepted {num} and will attend to the {cat} issue at Flat {flat} shortly.")
        await audit.log(society_id, "vendor_accepted", f"{vname} accepted {num} ({cat} · Flat {flat}) via WhatsApp", actor=vname, category="vendor", ticket_number=num)

    elif action == "reject":
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"vendor_id": None, "vendor_name": None, "status": "Open", "awaiting_vendor_time": False, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor Rejected", f"{vname} declined the job")
        await audit.log(society_id, "vendor_rejected", f"{vname} declined {num} via WhatsApp", actor=vname, category="vendor", ticket_number=num)
        await _ack(phone, f"No problem — you've *declined* {num}. We'll reassign it.")
        fresh = await db.tickets.find_one({"_id": ticket["_id"]})
        newv = await pipeline.pick_vendor(society_id, cat, exclude_id=str(ticket.get("vendor_id")) if ticket.get("vendor_id") else None)
        if newv:
            await pipeline.assign_vendor(fresh, newv)
            await _notify_followers(ticket, f"🔄 {num} is being reassigned to {newv['name']}.")
        else:
            await _notify_followers(ticket, f"⏳ {num} needs reassignment — our team will assign another vendor shortly.")

    elif action == "resolve":
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"status": "Resolved", "awaiting_vendor_time": False, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Marked Resolved", f"Resolved by {vname}")
        await audit.log(society_id, "ticket_resolved", f"{num} ({cat} · Flat {flat}) marked resolved by {vname} via WhatsApp", actor=vname, category="ticket", ticket_number=num)
        await _ack(phone, f"✅ Marked {num} as *resolved*. Thank you!")
        await _notify_followers(ticket, f"✅ {num} ({cat} · Flat {flat}) has been resolved by {vname}. We'd love your feedback!")

    elif action == "time":
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"awaiting_vendor_time": True, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor: Suggesting Time", f"{vname} will propose a visit time")
        await _ack(phone, f"🕒 Sure — please reply with your preferred visit time for {num} (e.g. \"Tomorrow 4 PM\").")


async def _apply_poll_results(m: dict):
    poll = m.get("poll") or {}
    pu = m.get("poll_update") or {}
    match_ids = [x for x in [m.get("id"), pu.get("poll_id")] if x]
    s = None
    for mid in match_ids:
        s = await db.suggestions.find_one({"poll_message_id": mid})
        if s:
            break
    if not s and poll.get("title"):
        title = poll["title"].split(" — Do you support")[0].strip()
        q = {"title": title}
        gid = m.get("group_chat_id")
        if gid:
            soc = await db.societies.find_one({"whatsapp_group.chat_id": gid})
            if soc:
                q["society_id"] = str(soc["_id"])
        s = await db.suggestions.find_one(q, sort=[("created_at", -1)])
        if s and match_ids:
            await db.suggestions.update_one({"_id": s["_id"]}, {"$set": {"poll_message_id": match_ids[0]}})
    if not s:
        logger.info("poll update ignored — no suggestion for ids %s title %s", match_ids, poll.get("title"))
        return
    results = poll.get("results") or []
    yes = no = None
    for i, r in enumerate(results):
        name = (r.get("name") or "").strip().lower()
        cnt = r.get("count")
        if cnt is None:
            cnt = len(r.get("voters") or [])
        if "yes" in name:
            yes = cnt
        elif "no" in name:
            no = cnt
    if yes is None and no is None and len(results) >= 2:
        yes = results[0].get("count") or 0
        no = results[1].get("count") or 0
    if yes is None and no is None:
        return
    await db.suggestions.update_one({"_id": s["_id"]}, {"$set": {"yes_votes": yes or 0, "no_votes": no or 0, "updated_at": now_iso()}})
    logger.info("poll %s updated -> yes=%s no=%s", s.get("poll_message_id"), yes, no)


async def _vote_suggestion(sug_id: str, phone: str, vote: str):
    try:
        s = await db.suggestions.find_one({"_id": ObjectId(sug_id)})
    except Exception:
        s = None
    if not s:
        return
    voters = s.get("voters", {}) or {}
    voters[phone] = vote
    yes = sum(1 for v in voters.values() if v == "yes")
    no = sum(1 for v in voters.values() if v == "no")
    await db.suggestions.update_one({"_id": s["_id"]}, {"$set": {"voters": voters, "yes_votes": yes, "no_votes": no, "updated_at": now_iso()}})


async def _handle_button(society_id: str, phone: str, button_id: str):
    logger.info("button click phone=%s id=%s", phone, button_id)
    if button_id.startswith("vendor_accept_"):
        await _vendor_action(society_id, phone, button_id.replace("vendor_accept_", ""), "accept")
    elif button_id.startswith("vendor_reject_"):
        await _vendor_action(society_id, phone, button_id.replace("vendor_reject_", ""), "reject")
    elif button_id.startswith("vendor_time_"):
        await _vendor_action(society_id, phone, button_id.replace("vendor_time_", ""), "time")
    elif button_id.startswith("vendor_resolved_"):
        await _vendor_action(society_id, phone, button_id.replace("vendor_resolved_", ""), "resolve")
    elif button_id == "resident_confirm":
        item = await db.review_queue.find_one({"society_id": society_id, "phone": phone, "status": "pending"}, sort=[("created_at", -1)])
        if item:
            ai = dict(item.get("ai_result") or {})
            ai["intent"] = "Complaint"
            resident = await pipeline.find_resident(society_id, phone=phone, flat=ai.get("flat"))
            ticket = await pipeline.create_ticket(society_id, ai, resident, "resident_confirm", item.get("text", ""), ai_generated=True, notify_to=phone)
            await db.review_queue.update_one({"_id": item["_id"]}, {"$set": {"status": "approved", "ticket_number": ticket["ticket_number"], "reviewed_at": now_iso()}})
    elif button_id == "resident_cancel":
        await db.review_queue.update_many({"society_id": society_id, "phone": phone, "status": "pending"}, {"$set": {"status": "rejected", "reviewed_at": now_iso()}})
        await _ack(phone, "No problem — we won't create a ticket. Message us again anytime you need help.")
    elif button_id.startswith("sugg_yes_"):
        await _vote_suggestion(button_id.replace("sugg_yes_", ""), phone, "yes")
    elif button_id.startswith("sugg_no_"):
        await _vote_suggestion(button_id.replace("sugg_no_", ""), phone, "no")


# -------- Whapi Webhook (public) — reads real WhatsApp GROUP chats --------
@router.api_route("/api/whapi/webhook", methods=["POST", "PUT", "PATCH"])
async def whapi_webhook(request: Request):
    # Webhooks must always return 200 quickly; never surface a 500 to the provider.
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}
    try:
        logger.info("Whapi RAW [%s]: %s", request.method, json.dumps(payload)[:2500])
        messages = wa.parse_whapi_inbound(payload)
        logger.info("Whapi parsed %d msg(s): %s", len(messages), [{"from": m.get("from"), "type": m.get("type"), "btn": m.get("button_id"), "poll": bool(m.get("poll")), "id": m.get("id")} for m in messages])
        for m in messages:
            if m.get("type") == "poll" or m.get("poll"):
                await _apply_poll_results(m)
                continue
            group_chat_id = m.get("group_chat_id")
            society = None
            if group_chat_id:
                society = await db.societies.find_one({"whatsapp_group.chat_id": group_chat_id})
                if not society:
                    continue  # message from an unmapped group -> ignore
            else:
                society = await db.societies.find_one({"monitoring": True})
            if not society:
                continue
            sid = str(society["_id"])
            if m.get("button_id"):
                await _handle_button(sid, m["from"], m["button_id"])
            elif group_chat_id and m.get("text"):
                # group message -> AI complaint pipeline; replies go back into the group, quoting the original
                await pipeline.process_message(sid, m["from"], m["text"], group_chat_id=group_chat_id, reply_to=m.get("id"))
            elif m.get("text"):
                # 1:1 reply (vendor/resident) -> lightweight keyword handling
                await _handle_direct_reply(sid, m["from"], m["text"])
    except Exception as e:
        logger.exception("Whapi webhook processing failed: %s", e)
    return {"status": "ok"}


async def _handle_direct_reply(society_id: str, phone: str, text: str):
    t = text.strip().lower()
    vendor = await db.vendors.find_one({"society_id": society_id, "phone": {"$regex": phone[-10:] + "$"}})
    if vendor:
        job = await db.tickets.find_one({"vendor_id": str(vendor["_id"]), "status": {"$in": ["Open", "Pending"]}}, sort=[("updated_at", -1)])
        if job:
            tid = str(job["_id"])
            if "accept" in t:
                await _vendor_action(society_id, phone, tid, "accept"); return
            if "reject" in t or "decline" in t:
                await _vendor_action(society_id, phone, tid, "reject"); return
            if "resolve" in t or t == "done" or "complete" in t or "finished" in t:
                await _vendor_action(society_id, phone, tid, "resolve"); return
            if job.get("awaiting_vendor_time"):
                await db.tickets.update_one({"_id": job["_id"]}, {"$set": {"preferred_time": text.strip(), "awaiting_vendor_time": False, "updated_at": now_iso()}})
                await pipeline.add_timeline(tid, "Vendor Suggested Time", f"{vendor['name']}: {text.strip()}")
                await _ack(phone, f"🕒 Noted — visit time for {job.get('ticket_number')} set to \"{text.strip()}\".")
                await _notify_followers(job, f"🕒 {vendor['name']} proposed a visit time for {job.get('ticket_number')}: {text.strip()}.")
                return
    if "confirm" in t or t == "yes":
        await _handle_button(society_id, phone, "resident_confirm")
    elif "cancel" in t or t == "no":
        await _handle_button(society_id, phone, "resident_cancel")


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
        "provider": "whapi" if wa.whapi_configured() else ("meta" if wa.meta_configured() else None),
        "whapi_configured": wa.whapi_configured(),
        "meta_configured": wa.meta_configured(),
    }


@router.post("/api/society/whatsapp/connect")
async def wa_connect(body: GroupConnect, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    await db.societies.update_one(
        {"_id": ObjectId(sid)},
        {"$set": {"whatsapp_group": {"group_name": body.group_name, "group_id": body.group_id,
                                     "chat_id": body.group_id,
                                     "phone_number_id": os.environ.get("WHATSAPP_PHONE_ID", "")},
                  "monitoring": True}},
    )
    actor = user.get("name") or user.get("email") or "Admin"
    await audit.log(sid, "whatsapp_group_connected", f"WhatsApp group '{body.group_name}' connected", actor=actor, category="whatsapp")
    return {"status": "connected"}


@router.post("/api/society/whatsapp/toggle-monitoring")
async def toggle_monitoring(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    s = await db.societies.find_one({"_id": ObjectId(sid)})
    new_val = not s.get("monitoring", False)
    await db.societies.update_one({"_id": ObjectId(sid)}, {"$set": {"monitoring": new_val}})
    actor = user.get("name") or user.get("email") or "Admin"
    await audit.log(sid, "whatsapp_monitoring_toggled", f"Group monitoring {'enabled' if new_val else 'disabled'}", actor=actor, category="whatsapp")
    return {"monitoring": new_val}


@router.get("/api/society/whatsapp/check")
async def wa_check(user: dict = Depends(require_society_admin)):
    return await wa.check_connection()


@router.post("/api/society/whatsapp/test-send")
async def wa_test_send(body: TestSend, user: dict = Depends(require_society_admin)):
    if not wa.is_configured():
        raise HTTPException(status_code=400, detail="No WhatsApp transport configured")
    try:
        res = await wa.send_text(body.phone, "✅ PROPTO is connected. Live complaint monitoring is active.")
        return {"ok": True, "response": res}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------- Simulator (test the full flow without live WhatsApp) --------
@router.post("/api/society/whatsapp/simulate")
async def simulate(body: SimulateMessage, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    result = await pipeline.process_message(sid, body.phone, body.text)
    return result
