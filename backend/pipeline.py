import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from bson import ObjectId

from db import db
from models import now_iso
import ai_engine
import whatsapp_client as wa
import audit

logger = logging.getLogger("propto.pipeline")

SLA_HOURS = {"Critical": 2, "High": 4, "Medium": 24, "Low": 72}


def threshold() -> float:
    try:
        return float(os.environ.get("AI_CONFIDENCE_THRESHOLD", "0.75"))
    except Exception:
        return 0.75


def gen_ticket_number() -> str:
    return "TKT-" + datetime.now(timezone.utc).strftime("%y%m%d") + "-" + uuid.uuid4().hex[:5].upper()


async def find_resident(society_id: str, phone: str = None, flat: str = None):
    query = {"society_id": society_id}
    if phone:
        r = await db.residents.find_one({"society_id": society_id, "phone": phone})
        if r:
            return r
    if flat:
        r = await db.residents.find_one({"society_id": society_id, "flat": {"$regex": f"^{flat}$", "$options": "i"}})
        if r:
            return r
    return None


async def find_duplicate(society_id: str, flat: str, category: str):
    if not flat:
        return None
    return await db.tickets.find_one({
        "society_id": society_id,
        "flat": {"$regex": f"^{flat}$", "$options": "i"},
        "category": category,
        "status": {"$in": ["Open", "Pending"]},
    })


async def pick_vendor(society_id: str, category: str, exclude_id: str = None):
    cursor = db.vendors.find({
        "society_id": society_id, "active": True, "availability": True,
        "categories": category,
    })
    vendors = await cursor.to_list(100)
    if exclude_id:
        vendors = [v for v in vendors if str(v["_id"]) != exclude_id]
    if not vendors:
        return None
    # Order by admin-set priority for this category (1 = first), then least current load.
    scored = []
    for v in vendors:
        load = await db.tickets.count_documents({
            "vendor_id": str(v["_id"]), "status": {"$in": ["Open", "Pending"]},
        })
        p = (v.get("priorities") or {}).get(category)
        try:
            p = int(p)
            if p <= 0:
                p = 999
        except (TypeError, ValueError):
            p = 999
        scored.append((p, load, v))
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[0][2]


async def add_timeline(ticket_id: str, event: str, detail: str = ""):
    await db.tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$push": {"timeline": {"event": event, "detail": detail, "at": now_iso()}},
         "$set": {"updated_at": now_iso()}},
    )


async def assign_vendor(ticket: dict, vendor: dict, actor: str = "AI (auto-route)"):
    tid = str(ticket["_id"])
    await db.tickets.update_one(
        {"_id": ObjectId(tid)},
        {"$set": {"vendor_id": str(vendor["_id"]), "vendor_name": vendor["name"],
                  "status": "Pending", "updated_at": now_iso()}},
    )
    await add_timeline(tid, "Vendor Assigned", f"{vendor['name']} assigned")
    await audit.log(ticket.get("society_id"), "vendor_assigned",
                    f"{vendor['name']} assigned to {ticket.get('ticket_number')} ({ticket.get('category')})",
                    actor=actor, category="vendor", ticket_number=ticket.get("ticket_number"))
    await wa.send_buttons(
        vendor["phone"],
        f"New job: {ticket['category']} at Flat {ticket.get('flat','?')} ({ticket['priority']} priority). {ticket['description']}",
        [{"id": f"vendor_accept_{tid}", "title": "Accept"},
         {"id": f"vendor_reject_{tid}", "title": "Reject"},
         {"id": f"vendor_time_{tid}", "title": "Suggest Time"}],
    )


async def create_ticket(society_id: str, ai: dict, resident: dict, source: str, raw_text: str, ai_generated: bool,
                        notify_to: str = None, notify_reply_to: str = None):
    doc = {
        "ticket_number": gen_ticket_number(),
        "society_id": society_id,
        "resident_id": str(resident["_id"]) if resident else None,
        "resident_name": resident["name"] if resident else "Unknown",
        "resident_phone": resident["phone"] if resident else None,
        "category": ai.get("category") or "Civil",
        "sub_category": ai.get("sub_category") or "",
        "kb_category": ai.get("kb_category") or "",
        "matched_situation": ai.get("matched_situation") or "",
        "description": ai.get("description") or raw_text[:150],
        "flat": ai.get("flat") or (resident.get("flat") if resident else ""),
        "tower": ai.get("tower") or (resident.get("tower") if resident else ""),
        "priority": ai.get("priority") or "Medium",
        "preferred_time": ai.get("preferred_time") or "",
        "status": "Open",
        "source": source,
        "ai_generated": ai_generated,
        "ai_confidence": ai.get("confidence", 0),
        "vendor_id": None,
        "vendor_name": None,
        "assigned_to": None,
        "handled_by": ai.get("handled_by") or "",
        "vendor_required": ai.get("vendor_required") or "",
        "raw_message": raw_text,
        "sla_hours": SLA_HOURS.get(ai.get("priority") or "Medium", 24),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "timeline": [{"event": "Ticket Created", "detail": f"via {source}", "at": now_iso()}],
    }
    doc["sla_due"] = (datetime.now(timezone.utc) + timedelta(hours=doc["sla_hours"])).isoformat()
    res = await db.tickets.insert_one(doc)
    doc["_id"] = res.inserted_id
    await audit.log(society_id, "ticket_created",
                    f"Ticket {doc['ticket_number']} raised: {doc['category']} · Flat {doc['flat'] or '—'} ({doc['priority']})",
                    actor=(resident["name"] if resident else "WhatsApp user"),
                    category="ticket", ticket_number=doc["ticket_number"])
    # Route based on the taxonomy "Handled By". Society Manager issues stay in-house;
    # everything else auto-routes to a matching vendor.
    tid = str(doc["_id"])
    handled_by = doc["handled_by"]
    vendor = None
    if handled_by == "Society Manager":
        await db.tickets.update_one({"_id": doc["_id"]}, {"$set": {"status": "Pending", "assigned_to": "Society Manager", "updated_at": now_iso()}})
        doc["status"] = "Pending"
        doc["assigned_to"] = "Society Manager"
        await add_timeline(tid, "Assigned to Society Manager", "Handled in-house by the society manager")
        await audit.log(society_id, "ticket_assigned_manager",
                        f"{doc['ticket_number']} routed to the Society Manager (in-house)",
                        actor="AI (taxonomy)", category="ticket", ticket_number=doc["ticket_number"])
        assigned_line = "Assigned to: Society Manager (handled in-house)."
    else:
        routing_cat = ai.get("routing_category") or doc["category"]
        vendor = await pick_vendor(society_id, routing_cat)
        if vendor:
            await assign_vendor(doc, vendor)
            assigned_line = f"Assigned to: {vendor['name']}. They'll reach out shortly."
        else:
            assigned_line = "A vendor will be assigned shortly."
    who = (resident["name"] + ", " if resident else "")
    confirm_msg = (
        f"✅ {who}we've logged your {doc['category']} complaint.\n"
        f"Ticket: {doc['ticket_number']}\n"
        f"Flat: {doc['flat'] or '—'}  |  Priority: {doc['priority']}\n"
        + assigned_line
    )
    # Prefer replying in the group (quoting the original message); else private 1:1 to resident.
    try:
        if notify_to:
            await wa.send_text(notify_to, confirm_msg, reply_to=notify_reply_to)
        elif resident and resident.get("phone"):
            await wa.send_text(resident["phone"], confirm_msg)
    except Exception as e:
        logger.warning("confirmation send failed: %s", e)
    return doc


async def log_activity(society_id: str, phone: str, text: str, decision: str, ai: dict = None, reason: str = "", ticket_number: str = None):
    doc = {
        "society_id": society_id,
        "phone": phone,
        "text": text,
        "decision": decision,  # ignored | ai_analyzed | ticket_created | duplicate | review_queue
        "reason": reason,
        "ai_result": ai,
        "confidence": (ai or {}).get("confidence", 0) if ai else 0,
        "ticket_number": ticket_number,
        "created_at": now_iso(),
    }
    await db.ai_activity.insert_one(doc)


async def process_message(society_id: str, phone: str, text: str, group_chat_id: str = None, reply_to: str = None):
    """Main pipeline: rule filter -> AI -> confidence workflow. Returns result dict.
    Acknowledgements/confirmations for group messages are sent to the complainant's
    PERSONAL chat (not the group) to keep the group clean."""
    in_group = bool(group_chat_id)
    # All resident-facing acknowledgements go to the person's personal chat (their phone).
    ack_target = phone

    rule = ai_engine.prefilter(text)
    if not rule["forward"]:
        await log_activity(society_id, phone, text, "ignored", reason=rule["reason"])
        return {"status": "ignored", "reason": rule["reason"]}

    try:
        ai = await ai_engine.analyze_message(text)
    except Exception as e:
        logger.warning("AI analysis failed, routing to review queue: %s", e)
        review = {"society_id": society_id, "phone": phone, "text": text,
                  "ai_result": None, "confidence": 0, "resident_id": None,
                  "status": "pending", "created_at": now_iso()}
        await db.review_queue.insert_one(review)
        await log_activity(society_id, phone, text, "review_queue", reason="AI unavailable")
        return {"status": "review_queue", "confidence": 0, "reason": "AI temporarily unavailable"}
    if ai.get("intent") != "Complaint":
        await log_activity(society_id, phone, text, "ignored", ai=ai, reason="AI: not a complaint")
        return {"status": "ignored", "reason": "AI classified as not a complaint", "ai": ai}

    resident = await find_resident(society_id, phone=phone, flat=ai.get("flat"))
    conf = ai.get("confidence", 0)

    if conf >= threshold():
        dup = await find_duplicate(society_id, ai.get("flat"), ai.get("category"))
        if dup:
            await db.tickets.update_one(
                {"_id": dup["_id"]},
                {"$addToSet": {"linked_reporters": phone}, "$set": {"updated_at": now_iso()}},
            )
            await add_timeline(str(dup["_id"]), "Duplicate Linked", f"Another report from {phone}")
            await log_activity(society_id, phone, text, "duplicate", ai=ai, reason="Open ticket exists", ticket_number=dup["ticket_number"])
            if ack_target:
                await wa.send_text(ack_target, f"This is already tracked under ticket {dup['ticket_number']}. We'll keep you posted.")
            return {"status": "duplicate", "ticket_number": dup["ticket_number"], "ai": ai}

        ticket = await create_ticket(society_id, ai, resident, "whatsapp", text, ai_generated=True,
                                     notify_to=ack_target, notify_reply_to=None)
        await log_activity(society_id, phone, text, "ticket_created", ai=ai, ticket_number=ticket["ticket_number"])
        return {"status": "ticket_created", "ticket_number": ticket["ticket_number"], "ai": ai}

    # Below threshold -> HITL review queue
    review = {
        "society_id": society_id,
        "phone": phone,
        "text": text,
        "ai_result": ai,
        "confidence": conf,
        "resident_id": str(resident["_id"]) if resident else None,
        "status": "pending",
        "created_at": now_iso(),
    }
    await db.review_queue.insert_one(review)
    await log_activity(society_id, phone, text, "review_queue", ai=ai, reason=f"Low confidence {conf:.2f}")
    if in_group:
        if phone:
            await wa.send_text(
                phone,
                f"Thanks — this looks like it may be a {ai.get('category') or 'maintenance'} complaint"
                + (f" at Flat {ai.get('flat')}" if ai.get('flat') else "") + ". Our team will review and confirm shortly.",
            )
    elif phone:
        await wa.send_buttons(
            phone,
            f"We detected a possible {ai.get('category') or 'maintenance'} complaint at Flat {ai.get('flat') or 'your unit'}. Create a ticket?",
            [{"id": "resident_confirm", "title": "Confirm"}, {"id": "resident_cancel", "title": "Cancel"}],
        )
    return {"status": "review_queue", "confidence": conf, "ai": ai}
