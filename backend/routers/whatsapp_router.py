from fastapi import APIRouter, HTTPException, Depends, Request, Query
from fastapi.responses import PlainTextResponse
from bson import ObjectId
import os
import asyncio
import logging
import json
import re
import uuid

from db import db
from models import SimulateMessage, GroupConnect, TestSend, now_iso
from auth_utils import require_society_admin, user_society_id, get_current_user
import whatsapp_client as wa
import pipeline
import audit
import task_queue

router = APIRouter(tags=["whatsapp"])
logger = logging.getLogger("propto.whatsapp_router")

# Webhooks are processed INLINE (awaited within the request) so the DB writes
# complete before we return 200. Passenger/LSAPI kills idle/recycled workers
# right after the response, which would abandon any detached background task
# before it writes to Atlas. Hard timeout caps below keep a worker from hanging.


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
    if task_queue.redis_enabled():
        await task_queue.enqueue({"kind": "meta", "payload": payload})
    else:
        try:
            await asyncio.wait_for(process_meta(payload), timeout=45)
        except asyncio.TimeoutError:
            logger.warning("Meta webhook processing exceeded 45s cap; returning 200")
    return {"status": "ok"}


async def process_meta(payload: dict):
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


async def _group_chat_id(society_id: str):
    soc = await db.societies.find_one({"_id": ObjectId(society_id)})
    return ((soc or {}).get("whatsapp_group") or {}).get("chat_id")


async def _vendor_action(society_id: str, phone: str, tid: str, action: str, otp: str = None):
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
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"status": "Pending", "vendor_accepted": True, "response_due_at": None, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor Accepted", f"{vname} accepted the job")
        await audit.log(society_id, "vendor_accepted", f"{vname} accepted {num} ({cat} · Flat {flat}) via WhatsApp", actor=vname, category="vendor", ticket_number=num)
        soc = await db.societies.find_one({"_id": ObjectId(society_id)})
        soc_name = (soc or {}).get("name") or "the society"
        rname = ticket.get("resident_name") or "Resident"
        rphone = ticket.get("reporter_phone") or ticket.get("resident_phone") or "—"
        # 1) Confirm to the vendor + share the complaint raiser's details
        link = pipeline.vendor_link(ticket.get("vendor_token"))
        await _ack(phone,
                   f"👍 You've *accepted* {num} ({cat}).\n"
                   f"Raised by: {rname}\n"
                   f"Phone: {rphone}\n"
                   f"Flat: {flat}\n"
                   f"Society: {soc_name}\n"
                   f"Issue: {ticket.get('description') or cat}\n\n"
                   f"The resident has received a resolution OTP. Once the work is done, ask them for it and "
                   f"reply *DONE <OTP>*" + (f" or resolve here: {link}" if link else "") + ".")
        otp_code = await pipeline.issue_resolve_otp(ticket)
        # 2) Send the vendor's contact to the customer personally
        vendor = None
        if ticket.get("vendor_id"):
            try:
                vendor = await db.vendors.find_one({"_id": ObjectId(ticket["vendor_id"])})
            except Exception:
                vendor = None
        cust = ticket.get("reporter_phone") or ticket.get("resident_phone")
        if cust:
            await _ack(cust,
                       f"✅ Good news! Your complaint {num} ({cat} · Flat {flat}) has been accepted by *{vname}*.\n"
                       f"Vendor contact: {(vendor or {}).get('phone') or '—'}\n"
                       f"They'll reach out shortly — feel free to coordinate directly.\n\n"
                       + pipeline.otp_text({**ticket, "vendor_name": vname}, otp_code))
        else:
            await pipeline.send_otp({**ticket, "vendor_name": vname}, otp_code)

    elif action == "reject":
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"vendor_id": None, "vendor_name": None, "status": "Open", "vendor_accepted": False, "response_due_at": None, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, "Vendor Rejected", f"{vname} declined the job")
        await audit.log(society_id, "vendor_rejected", f"{vname} declined {num} via WhatsApp", actor=vname, category="vendor", ticket_number=num)
        await _ack(phone, f"No problem — you've *declined* {num}. We'll reassign it.")
        fresh = await db.tickets.find_one({"_id": ticket["_id"]})
        newv = await pipeline.pick_vendor(society_id, ticket.get("routing_category") or cat, exclude_id=str(ticket.get("vendor_id")) if ticket.get("vendor_id") else None)
        gid = await _group_chat_id(society_id)
        quote = ticket.get("source_message_id")
        if newv:
            await pipeline.assign_vendor(fresh, newv)
            if gid:
                await wa.send_text(gid, f"🔄 {num} is being reassigned to {newv['name']}.", reply_to=quote)
        else:
            await pipeline.escalate_to_committee(fresh, after_priority=0, reason="No other vendor available after rejection")

    elif action == "resolve":
        if not ticket.get("vendor_accepted") or ticket.get("status") not in ("Open", "Pending"):
            await _ack(phone, f"{num} can't be resolved right now — please accept the job first.")
            return
        if not ticket.get("resolve_otp_hash"):
            code = await pipeline.issue_resolve_otp(ticket)
            await pipeline.send_otp(ticket, code)
            await _ack(phone, f"An OTP for {num} has been sent to the resident. Ask them for it and reply *DONE <OTP>*.")
            return
        if not otp:
            await _ack(phone, f"To resolve {num}, reply *DONE <OTP>* with the 6-digit OTP the resident received.")
            return
        ok, msg = await pipeline.verify_resolve_otp(ticket, otp)
        if not ok:
            await _ack(phone, f"❌ {msg}")
            return
        await pipeline.resolve_by_vendor(ticket, vname, "WhatsApp")
        await _ack(phone, f"✅ OTP verified. Marked {num} as *resolved*. Thank you!")


async def _apply_poll_results(m: dict, create_if_missing: bool = False):
    poll = m.get("poll") or {}
    pu = m.get("poll_update") or {}
    match_ids = [x for x in [m.get("id"), pu.get("poll_id")] if x]
    gid = m.get("group_chat_id")
    soc = await db.societies.find_one({"whatsapp_group.chat_id": gid}) if gid else None
    title = (poll.get("title") or "").split(" — Do you support")[0].strip()
    s = None
    for mid in match_ids:
        s = await db.suggestions.find_one({"poll_message_id": mid})
        if s:
            break
    if not s and title:
        q = {"title": title}
        if soc:
            q["society_id"] = str(soc["_id"])
        s = await db.suggestions.find_one(q, sort=[("created_at", -1)])
        if s and match_ids:
            await db.suggestions.update_one({"_id": s["_id"]}, {"$set": {"poll_message_id": match_ids[0]}})
    # A poll created by a resident inside the WhatsApp group -> capture as a new suggestion.
    if not s and create_if_missing and soc and title:
        doc = {
            "society_id": str(soc["_id"]), "title": title, "category": "General",
            "author_name": "WhatsApp Group", "flat": "", "status": "Under Review",
            "voters": {}, "yes_votes": 0, "no_votes": 0, "poll_posted": True,
            "poll_message_id": match_ids[0] if match_ids else f"grp-{uuid.uuid4().hex}",
            "source": "group_poll", "created_at": now_iso(), "updated_at": now_iso(),
        }
        res = await db.suggestions.insert_one(doc)
        s = await db.suggestions.find_one({"_id": res.inserted_id})
        await audit.log(str(soc["_id"]), "suggestion_created", f"Group poll captured: {title}", actor="WhatsApp Group", category="suggestion")
        logger.info("group poll captured as suggestion: %s", title)
    if not s:
        logger.info("poll update ignored — no suggestion for ids %s title %s", match_ids, poll.get("title"))
        return
    results = poll.get("results") or []
    options = []
    yes = no = None
    for r in results:
        name = (r.get("name") or "").strip()
        cnt = r.get("count")
        if cnt is None:
            cnt = len(r.get("voters") or [])
        cnt = cnt or 0
        options.append({"name": name, "count": cnt})
        low = name.lower()
        if "yes" in low:
            yes = cnt
        elif "no" in low:
            no = cnt
    upd = {"updated_at": now_iso()}
    if options:
        upd["options"] = options
    if yes is not None or no is not None:
        by = yes or 0
        bn = no or 0
        av = s.get("admin_vote") or (s.get("voters") or {}).get("admin_panel")
        if av == "yes":
            by += 1
        elif av == "no":
            bn += 1
        upd["yes_votes"] = by
        upd["no_votes"] = bn
    elif len(options) >= 2 and not s.get("source") == "group_poll":
        upd["yes_votes"] = options[0]["count"]
        upd["no_votes"] = options[1]["count"]
    await db.suggestions.update_one({"_id": s["_id"]}, {"$set": upd})
    logger.info("poll %s updated -> yes=%s no=%s options=%s", s.get("poll_message_id"), yes, no, options)


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


async def _committee_action(society_id: str, phone: str, tid: str, action: str):
    try:
        ticket = await db.tickets.find_one({"_id": ObjectId(tid)})
    except Exception:
        ticket = None
    if not ticket:
        return
    num = ticket.get("ticket_number"); cat = ticket.get("category"); flat = ticket.get("flat") or "—"
    role = ticket.get("committee_assignee_role") or "Committee member"
    mname = ticket.get("committee_assignee_name") or role
    if action == "accept":
        await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"committee_accepted": True, "response_due_at": None, "updated_at": now_iso()}})
        await pipeline.add_timeline(tid, f"{role} Accepted", f"{mname} accepted the escalation")
        await audit.log(society_id, "committee_accepted", f"{mname} ({role}) accepted {num}", actor=mname, category="ticket", ticket_number=num)
        soc = await db.societies.find_one({"_id": ObjectId(society_id)})
        soc_name = (soc or {}).get("name") or "the society"
        rname = ticket.get("resident_name") or "Resident"
        rphone = ticket.get("reporter_phone") or ticket.get("resident_phone") or "—"
        await _ack(phone,
                   f"👍 You've *accepted* {num} ({cat}).\n"
                   f"Raised by: {rname}\nPhone: {rphone}\nFlat: {flat}\nSociety: {soc_name}\n"
                   f"Issue: {ticket.get('description') or cat}\n\nReply *DONE* once resolved.")
        gid = await _group_chat_id(society_id)
        if gid:
            await wa.send_text(gid, f"👍 {num} is now being handled by {mname} ({role}).", reply_to=ticket.get("source_message_id"))
    elif action == "reject":
        await pipeline.add_timeline(tid, f"{role} Declined", f"{mname} declined the escalation")
        await audit.log(society_id, "committee_rejected", f"{mname} ({role}) declined {num}", actor=mname, category="ticket", ticket_number=num)
        await _ack(phone, f"No problem — you've *declined* {num}. Escalating further.")
        fresh = await db.tickets.find_one({"_id": ticket["_id"]})
        await pipeline.escalate_to_committee(fresh, after_priority=(ticket.get("committee_priority") or 0), reason=f"{role} declined")


async def _handle_button(society_id: str, phone: str, button_id: str):
    logger.info("button click phone=%s id=%s", phone, button_id)
    # Whapi prefixes interactive button ids (e.g. "ButtonsV3:vendor_accept_<tid>").
    # Strip any "prefix:" so our startswith() matching works.
    if ":" in button_id:
        button_id = button_id.split(":", 1)[1]
    if button_id.startswith("vendor_accept_"):
        await _vendor_action(society_id, phone, button_id.replace("vendor_accept_", ""), "accept")
    elif button_id.startswith("vendor_reject_"):
        await _vendor_action(society_id, phone, button_id.replace("vendor_reject_", ""), "reject")
    elif button_id.startswith("committee_accept_"):
        await _committee_action(society_id, phone, button_id.replace("committee_accept_", ""), "accept")
    elif button_id.startswith("committee_reject_"):
        await _committee_action(society_id, phone, button_id.replace("committee_reject_", ""), "reject")
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
# -------- Whapi Webhook (public) --------
@router.get("/api/whapi/webhook")
@router.get("/api/whapi/webhook/read")
@router.get("/api/whapi/webhook/send")
async def whapi_webhook_check():
    # Lets you confirm the route is live by opening the URL in a browser.
    return {"status": "ok", "detail": "PROPTO Whapi webhook is live. Whapi will POST here."}


async def _whapi_ingest(request: Request, role: str):
    # Return 200 fast. With Redis set -> enqueue for the worker; else process inline.
    try:
        payload = await request.json()
    except Exception:
        return {"status": "ok"}
    if task_queue.redis_enabled():
        await task_queue.enqueue({"kind": "whapi", "payload": payload, "method": request.method, "role": role})
    else:
        try:
            await asyncio.wait_for(process_whapi(payload, request.method, role), timeout=45)
        except asyncio.TimeoutError:
            logger.warning("Whapi webhook processing exceeded 45s cap; returning 200")
    return {"status": "ok"}


@router.api_route("/api/whapi/webhook", methods=["POST", "PUT", "PATCH"])
@router.api_route("/api/whapi/webhook/read", methods=["POST", "PUT", "PATCH"])
async def whapi_webhook_read(request: Request):
    # READER account: incoming GROUP messages -> AI/ticket pipeline.
    # Group->society assignment is matched against this reader number.
    return await _whapi_ingest(request, "read")


@router.api_route("/api/whapi/webhook/send", methods=["POST", "PUT", "PATCH"])
async def whapi_webhook_send(request: Request):
    # SENDER account: poll votes + 1:1 vendor/resident replies (those chats were
    # started by the sender, so replies come back to the sending number).
    return await _whapi_ingest(request, "send")


# Signatures of messages PROPTO itself posts into the group. The reader account
# sees these as normal group messages (they are not from_me on the reader), so we
# must skip them — otherwise our own acknowledgement gets re-classified as a new
# complaint and triggers a duplicate "already tracked" reply (feedback loop).
_BOT_MARKERS = (
    "we've logged your complaint",
    "this is already tracked under ticket",
    "will be assigned to concern vendor",
    "has been resolved",
    "propto is connected",
    "assigned to: society manager",
    "as *resolved*",
    "we'd love your feedback",
    "please share feedback",
    "has been *cancelled*",
    "can cancel it",
    "already cancelled",
    "can't be cancelled",
    "reassigned",
)


def _is_bot_echo(text: str) -> bool:
    t = (text or "").lower()
    return any(mk in t for mk in _BOT_MARKERS)


async def process_whapi(payload: dict, method: str = "POST", role: str = "read"):
    try:
        logger.info("Whapi RAW [%s/%s]: %s", method, role, json.dumps(payload)[:2500])
        messages = wa.parse_whapi_inbound(payload)
        logger.info("Whapi[%s] parsed %d msg(s): %s", role, len(messages), [{"from": m.get("from"), "type": m.get("type"), "btn": m.get("button_id"), "poll": bool(m.get("poll")), "id": m.get("id"), "quoted": m.get("quoted_id"), "text": (m.get("text") or "")[:30]} for m in messages])
        for m in messages:
            if m.get("type") == "poll" or m.get("poll"):
                if m.get("poll_fetch_id") and not (m.get("poll") or {}).get("results"):
                    fetched = await wa.get_poll_results(m["poll_fetch_id"])
                    if fetched:
                        m["poll"] = fetched
                        m["id"] = m.get("poll_fetch_id")
                # READER sees group-member polls -> capture them as new suggestions.
                # SENDER owns admin-posted polls -> update tallies of existing suggestions.
                await _apply_poll_results(m, create_if_missing=(role == "read"))
                continue
            group_chat_id = m.get("group_chat_id")
            # The READER drives the group AI pipeline; the SENDER's own group echoes are
            # ignored. DM replies (vendor/committee Accept/Reject/Resolve/Done) can arrive
            # on EITHER Whapi account, so they are handled on both roles and de-duplicated
            # by message id below. (Previously the reader dropped all DMs, so vendor
            # replies landing on the reader account were silently lost.)
            if role == "send" and group_chat_id and m.get("text") and not m.get("button_id"):
                continue
            society = None
            if group_chat_id:
                society = await db.societies.find_one({"whatsapp_group.chat_id": group_chat_id})
                if not society:
                    configured = [(s.get("name"), (s.get("whatsapp_group") or {}).get("chat_id"))
                                  for s in await db.societies.find({}, {"name": 1, "whatsapp_group.chat_id": 1}).to_list(50)]
                    logger.warning("Whapi: NO society mapped to group chat_id=%s -> message DROPPED. Configured societies/chat_ids=%s",
                                   group_chat_id, configured)
                    continue  # message from an unmapped group -> ignore
                logger.info("Whapi: group %s matched society %s (%s)", group_chat_id, str(society["_id"]), society.get("name"))
            else:
                society = await db.societies.find_one({"monitoring": True})
            if not society:
                continue
            sid = str(society["_id"])
            if not group_chat_id and m.get("id"):
                dup = await db.wa_processed.update_one({"_id": str(m["id"])}, {"$setOnInsert": {"at": now_iso()}}, upsert=True)
                if dup.upserted_id is None:
                    logger.info("Whapi[%s]: duplicate DM %s skipped", role, m.get("id"))
                    continue
            if m.get("button_id"):
                logger.info("Whapi[%s]: button '%s' from %s", role, m.get("button_id"), m.get("from"))
                await _handle_button(sid, m["from"], m["button_id"])
            elif group_chat_id and m.get("text"):
                # Reply "cancel" (any case) quoting the ticket -> cancel it (creator or manager only).
                if m["text"].strip().upper() == "CANCEL" and (m.get("quoted_id") or m.get("quoted_body")):
                    await _handle_cancel(sid, m["from"], m.get("quoted_id"), group_chat_id, m.get("id"), m.get("quoted_body"))
                    continue
                if _is_bot_echo(m["text"]):
                    logger.info("Whapi: skipping PROPTO's own group message (echo): %.60s", m["text"])
                    continue
                # group message -> AI complaint pipeline; replies go back into the group, quoting the original
                await pipeline.process_message(sid, m["from"], m["text"], group_chat_id=group_chat_id, reply_to=m.get("id"))
            elif m.get("text"):
                # 1:1 reply (vendor/resident) -> lightweight keyword handling
                await _handle_direct_reply(sid, m["from"], m["text"])
    except Exception as e:
        logger.exception("Whapi webhook processing failed: %s", e)


async def _is_society_manager(society_id: str, phone: str) -> bool:
    p10 = (phone or "")[-10:]
    if not p10:
        return False
    m = await db.committee.find_one({"society_id": society_id, "role": {"$in": ["Secretary", "Manager", "Chairman"]}, "phone": {"$regex": p10 + "$"}})
    return bool(m)


async def _handle_cancel(society_id: str, phone: str, quoted_id: str, group_chat_id: str, reply_to: str, quoted_body: str = ""):
    """Cancel a ticket when the creator or society manager replies 'CANCEL' to it.
    Matches by the quoted message id (source complaint or PROPTO ack) and, as a
    fallback, by a TKT-XXXXXX-XXXXX number found in the quoted acknowledgement text."""
    ticket = None
    if quoted_id:
        ticket = await db.tickets.find_one({"society_id": society_id, "$or": [{"source_message_id": quoted_id}, {"ack_message_id": quoted_id}]})
    if not ticket and quoted_body:
        mnum = re.search(r"TKT-\d{6}-[A-Z0-9]{4,6}", quoted_body.upper())
        if mnum:
            ticket = await db.tickets.find_one({"society_id": society_id, "ticket_number": mnum.group(0)})
    logger.info("CANCEL from=%s quoted_id=%s body=%.50s -> ticket=%s", phone, quoted_id, quoted_body, ticket.get("ticket_number") if ticket else None)
    if not ticket:
        return
    tnum = ticket.get("ticket_number")
    if ticket.get("status") == "Cancelled":
        await wa.send_text(group_chat_id, f"Ticket {tnum} is already cancelled.", reply_to=reply_to); return
    if ticket.get("status") == "Resolved":
        await wa.send_text(group_chat_id, f"Ticket {tnum} is already resolved and can't be cancelled.", reply_to=reply_to); return
    p10 = (phone or "")[-10:]
    rp = ticket.get("reporter_phone") or ""
    is_creator = bool(p10) and rp.endswith(p10)
    is_manager = await _is_society_manager(society_id, phone)
    if not (is_creator or is_manager):
        await wa.send_text(group_chat_id, "Only the resident who raised this ticket or the society manager can cancel it.", reply_to=reply_to)
        return
    by = "Society Manager" if (is_manager and not is_creator) else "resident"
    await db.tickets.update_one({"_id": ticket["_id"]}, {"$set": {"status": "Cancelled", "cancelled_by": by, "updated_at": now_iso()}})
    await pipeline.add_timeline(str(ticket["_id"]), "Ticket Cancelled", f"Cancelled via WhatsApp by {by} ({phone})")
    await audit.log(society_id, "ticket_cancelled", f"{tnum} cancelled by {by} ({phone})", actor=phone, category="ticket", ticket_number=tnum)
    await wa.send_text(group_chat_id, f"❌ Ticket {tnum} has been *cancelled* as requested. No further action will be taken.", reply_to=reply_to)
    # Notify the assigned vendor (if any) that the job is off.
    vid = ticket.get("vendor_id")
    if vid:
        try:
            v = await db.vendors.find_one({"_id": ObjectId(vid)})
            if v and v.get("phone"):
                await wa.send_text(v["phone"], f"⚠️ Ticket {tnum} ({ticket.get('category') or 'Issue'} · Flat {ticket.get('flat') or '—'}) has been CANCELLED. No action is required — please disregard this job.")
        except Exception as e:
            logger.warning("vendor cancel notice failed: %s", e)


async def _handle_direct_reply(society_id: str, phone: str, text: str):
    t = text.strip().lower()
    vendor = await db.vendors.find_one({"society_id": society_id, "phone": {"$regex": phone[-10:] + "$"}})
    logger.info("direct reply from %s text=%.30s vendor=%s", phone, t, vendor.get("name") if vendor else None)
    if vendor:
        job = await db.tickets.find_one({"vendor_id": str(vendor["_id"]), "status": {"$in": ["Open", "Pending"]}}, sort=[("updated_at", -1)])
        if job:
            tid = str(job["_id"])
            if "accept" in t:
                await _vendor_action(society_id, phone, tid, "accept"); return
            if "reject" in t or "decline" in t:
                await _vendor_action(society_id, phone, tid, "reject"); return
            if "resolve" in t or t.startswith("done") or "complete" in t or "finished" in t:
                m = re.search(r"\b(\d{6})\b", t)
                await _vendor_action(society_id, phone, tid, "resolve", otp=m.group(1) if m else None); return
    member = await db.committee.find_one({"society_id": society_id, "phone": {"$regex": phone[-10:] + "$"}})
    if member:
        job = await db.tickets.find_one({"committee_assignee_id": str(member["_id"]), "status": {"$in": ["Open", "Pending"]}}, sort=[("updated_at", -1)])
        if job:
            tid = str(job["_id"])
            if "accept" in t:
                await _committee_action(society_id, phone, tid, "accept"); return
            if "reject" in t or "decline" in t:
                await _committee_action(society_id, phone, tid, "reject"); return
            if "resolve" in t or t == "done" or "complete" in t or "finished" in t:
                await db.tickets.update_one({"_id": job["_id"]}, {"$set": {"status": "Resolved", "response_due_at": None, "updated_at": now_iso()}})
                await pipeline.add_timeline(tid, "Marked Resolved", f"Resolved by {member.get('name')} ({member.get('role')})")
                await audit.log(society_id, "ticket_resolved", f"{job.get('ticket_number')} resolved by {member.get('name')} via WhatsApp", actor=member.get("name"), category="ticket", ticket_number=job.get("ticket_number"))
                await _ack(phone, f"✅ Marked {job.get('ticket_number')} as *resolved*. Thank you!")
                gid = await _group_chat_id(society_id)
                if gid:
                    await wa.send_text(gid, f"✅ {job.get('ticket_number')} has been resolved by {member.get('name')} ({member.get('role')}). Thank you!", reply_to=job.get("source_message_id"))
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


@router.get("/api/society/whatsapp/groups")
async def wa_groups(user: dict = Depends(require_society_admin)):
    """Live list of the linked Whapi number's groups (id + name) for the picker."""
    try:
        return {"groups": await wa.list_groups()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not load groups: {e}")


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
