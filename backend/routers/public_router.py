from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from bson import ObjectId
import logging

from db import db
from models import ResidentCreate, PublicReassign, now_iso
import pipeline
import whatsapp_client as wa
import audit

router = APIRouter(prefix="/api/public", tags=["public"])
logger = logging.getLogger("propto.public")


@router.get("/join/{token}")
async def join_info(token: str):
    soc = await db.societies.find_one({"form_token": token})
    if not soc:
        raise HTTPException(status_code=404, detail="This link is invalid or has expired.")
    return {"society_name": soc.get("name"), "city": soc.get("city") or "", "towers": soc.get("towers") or []}


@router.post("/join/{token}")
async def join_submit(token: str, body: ResidentCreate):
    soc = await db.societies.find_one({"form_token": token})
    if not soc:
        raise HTTPException(status_code=404, detail="This link is invalid or has expired.")
    if not body.name.strip() or not body.phone.strip():
        raise HTTPException(status_code=400, detail="Name and phone are required.")
    if await db.residents.find_one({"society_id": str(soc["_id"]), "phone": body.phone.strip()}):
        raise HTTPException(status_code=409, detail="This phone number is already registered for this society.")
    doc = body.model_dump()
    doc.update({
        "society_id": str(soc["_id"]), "created_at": now_iso(),
        "approval": "pending", "source": "form",
    })
    await db.residents.insert_one(doc)
    return {"status": "submitted", "society_name": soc.get("name")}


# ---------- Public ticket view / manage (token-scoped, no login) ----------
async def _ticket_by_token(token: str):
    t = await db.tickets.find_one({"ticket_number": token})
    if not t:
        raise HTTPException(status_code=404, detail="This ticket link is invalid or has expired.")
    return t


async def _notify_group(ticket: dict, text: str):
    """Post an update to the society WhatsApp group, quoting the original complaint."""
    try:
        soc = await db.societies.find_one({"_id": ObjectId(ticket["society_id"])})
        gid = ((soc or {}).get("whatsapp_group") or {}).get("chat_id")
        if gid:
            await wa.send_text(gid, text, reply_to=ticket.get("source_message_id") or ticket.get("ack_message_id"))
        elif ticket.get("resident_phone"):
            await wa.send_text(ticket["resident_phone"], text)
    except Exception as e:
        logger.warning("public group notify failed: %s", e)


@router.get("/ticket/{token}")
async def ticket_view(token: str):
    t = await _ticket_by_token(token)
    soc = await db.societies.find_one({"_id": ObjectId(t["society_id"])})
    status = t.get("status")
    return {
        "ticket_number": t.get("ticket_number"),
        "society_name": (soc or {}).get("name") or "",
        "description": t.get("description") or "",
        "category": t.get("category") or "",
        "sub_category": t.get("sub_category") or "",
        "flat": t.get("flat") or "",
        "tower": t.get("tower") or "",
        "priority": t.get("priority") or "",
        "status": status,
        "resident_name": t.get("resident_name") or "",
        "assigned_to": t.get("vendor_name") or t.get("assigned_to") or "",
        "vendor_name": t.get("vendor_name") or "",
        "created_at": t.get("created_at"),
        "can_act": status not in ("Cancelled", "Resolved"),
    }


@router.get("/ticket/{token}/categories")
async def ticket_categories(token: str):
    t = await _ticket_by_token(token)
    cursor = db.vendors.find({"society_id": t["society_id"], "active": True})
    cats = set()
    async for v in cursor:
        for c in (v.get("categories") or []):
            if c:
                cats.add(c)
    return {"categories": sorted(cats)}


@router.post("/ticket/{token}/cancel")
async def ticket_cancel(token: str):
    t = await _ticket_by_token(token)
    tnum = t.get("ticket_number")
    if t.get("status") == "Cancelled":
        raise HTTPException(status_code=400, detail=f"Ticket {tnum} is already cancelled.")
    if t.get("status") == "Resolved":
        raise HTTPException(status_code=400, detail=f"Ticket {tnum} is already resolved and can't be cancelled.")
    sid = t["society_id"]
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"status": "Cancelled", "cancelled_by": "web", "updated_at": now_iso()}})
    await pipeline.add_timeline(str(t["_id"]), "Ticket Cancelled", "Cancelled via ticket details page")
    await audit.log(sid, "ticket_cancelled", f"{tnum} cancelled via ticket details page", actor="Ticket page", category="ticket", ticket_number=tnum)
    await _notify_group(t, f"❌ Ticket {tnum} has been *cancelled* as requested. No further action will be taken.")
    vid = t.get("vendor_id")
    if vid:
        try:
            v = await db.vendors.find_one({"_id": ObjectId(vid)})
            if v and v.get("phone"):
                await wa.send_text(v["phone"], f"⚠️ Ticket {tnum} ({t.get('category') or 'Issue'} · Flat {t.get('flat') or '—'}) has been CANCELLED. No action is required — please disregard this job.")
        except Exception as e:
            logger.warning("vendor cancel notice failed: %s", e)
    return {"status": "Cancelled"}


@router.post("/ticket/{token}/reassign")
async def ticket_reassign(token: str, body: PublicReassign):
    t = await _ticket_by_token(token)
    tnum = t.get("ticket_number")
    if t.get("status") in ("Cancelled", "Resolved"):
        raise HTTPException(status_code=400, detail=f"Ticket {tnum} is {t.get('status').lower()} and can't be reassigned.")
    sid = t["society_id"]
    prev_vid = t.get("vendor_id")

    if body.target == "manager":
        await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"vendor_id": None, "vendor_name": None, "assigned_to": "Society Manager", "status": "Pending", "updated_at": now_iso()}})
        await pipeline.add_timeline(str(t["_id"]), "Reassigned to Society Manager", "Handled in-house via ticket details page")
        await audit.log(sid, "ticket_reassigned_manager", f"{tnum} reassigned to Society Manager via ticket page", actor="Ticket page", category="ticket", ticket_number=tnum)
        await _notify_group(t, f"🔄 Ticket {tnum} has been reassigned to the Society Manager (handled in-house).")
        await _notify_prev_vendor(prev_vid, tnum, t)
        return {"status": "Pending", "assigned_to": "Society Manager"}

    category = (body.category or "").strip()
    if not category:
        raise HTTPException(status_code=400, detail="Please select a category to reassign.")
    vendor = await pipeline.pick_vendor(sid, category, exclude_id=str(prev_vid) if prev_vid else None)
    if not vendor:
        raise HTTPException(status_code=400, detail=f"No available vendor found for {category}.")
    ticket_for_assign = dict(t)
    ticket_for_assign["category"] = category
    await pipeline.assign_vendor(ticket_for_assign, vendor, actor="Ticket page")
    await db.tickets.update_one({"_id": t["_id"]}, {"$set": {"assigned_to": vendor["name"], "updated_at": now_iso()}})
    await _notify_group(t, f"🔄 Ticket {tnum} has been reassigned to {vendor['name']} ({category}). They'll reach out shortly.")
    if prev_vid and str(prev_vid) != str(vendor["_id"]):
        await _notify_prev_vendor(prev_vid, tnum, t)
    return {"status": "Pending", "assigned_to": vendor["name"]}


async def _notify_prev_vendor(prev_vid, tnum, ticket):
    if not prev_vid:
        return
    try:
        v = await db.vendors.find_one({"_id": ObjectId(prev_vid)})
        if v and v.get("phone"):
            await wa.send_text(v["phone"], f"ℹ️ Ticket {tnum} ({ticket.get('category') or 'Issue'} · Flat {ticket.get('flat') or '—'}) has been reassigned. No action is required from you.")
    except Exception as e:
        logger.warning("prev vendor notice failed: %s", e)



# ---------- Vendor job page (secret per-assignment token) ----------
class VendorResolve(BaseModel):
    otp: str


async def _ticket_by_vendor_token(vtoken: str):
    t = await db.tickets.find_one({"vendor_token": vtoken}) if vtoken else None
    if not t or not t.get("vendor_id"):
        raise HTTPException(status_code=404, detail="This job link is invalid or no longer assigned to you.")
    return t


@router.get("/vendor/{vtoken}")
async def vendor_ticket_view(vtoken: str):
    t = await _ticket_by_vendor_token(vtoken)
    soc = await db.societies.find_one({"_id": ObjectId(t["society_id"])})
    status = t.get("status")
    active = status in ("Open", "Pending")
    return {
        "ticket_number": t.get("ticket_number"), "society_name": (soc or {}).get("name") or "",
        "description": t.get("description") or "", "raw_message": t.get("raw_message") or "",
        "category": t.get("category") or "", "sub_category": t.get("sub_category") or "",
        "issue_line": t.get("matched_situation") or "", "priority": t.get("priority") or "",
        "sla_target": t.get("sla_target") or "", "flat": t.get("flat") or "", "tower": t.get("tower") or "",
        "location": t.get("location") or "", "resident_name": t.get("resident_name") or "",
        "resident_phone": t.get("reporter_phone") or t.get("resident_phone") or "",
        "status": status, "vendor_name": t.get("vendor_name") or "", "vendor_accepted": bool(t.get("vendor_accepted")),
        "created_at": t.get("created_at"), "response_due_at": t.get("response_due_at"),
        "can_resolve": active and bool(t.get("vendor_accepted")),
        "otp_locked": (t.get("otp_attempts") or 0) >= 5,
    }


@router.post("/vendor/{vtoken}/resolve")
async def vendor_ticket_resolve(vtoken: str, body: VendorResolve):
    t = await _ticket_by_vendor_token(vtoken)
    if t.get("status") not in ("Open", "Pending") or not t.get("vendor_accepted"):
        raise HTTPException(status_code=400, detail="This job can only be resolved after you accept it.")
    if not t.get("resolve_otp_hash"):
        code = await pipeline.issue_resolve_otp(t)
        await pipeline.send_otp(t, code)
        raise HTTPException(status_code=400, detail="A new OTP has been sent to the resident. Please enter it.")
    ok, msg = await pipeline.verify_resolve_otp(t, body.otp)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    await pipeline.resolve_by_vendor(t, t.get("vendor_name") or "Vendor", "vendor link")
    return {"status": "Resolved"}
