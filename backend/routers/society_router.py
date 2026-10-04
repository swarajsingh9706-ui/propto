from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from bson import ObjectId
from datetime import datetime, timezone, timedelta, date
import calendar
import io

from db import db, COMPLAINT_CATEGORIES
from models import (VendorCreate, VendorUpdate, ResidentCreate, ResidentUpdate,
                    TicketAssign, TicketUpdate, now_iso)
from auth_utils import require_society_admin, user_society_id
import pipeline
import audit
import whatsapp_client as wa

router = APIRouter(prefix="/api/society", tags=["society_admin"])


def _clean(doc):
    doc["id"] = str(doc.pop("_id"))
    return doc


def _sid(user):
    # super_admin may pass ?society_id filter via society scoping; society_admin uses own
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


def _actor(user):
    return user.get("name") or user.get("email") or user.get("role", "admin")


# ---------------- Asset scheduling helpers ----------------
FREQ_MONTHS = {"Monthly": 1, "Two Months": 2, "Three Months": 3, "Six Months": 6, "Yearly": 12}


def _parse_date(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


def _add_months(d: date, months: int) -> date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return date(y, m, day)


def _asset_status(a: dict) -> str:
    ns = _parse_date(a.get("next_service"))
    if not ns:
        return "Unscheduled"
    today = datetime.now(timezone.utc).date()
    if ns < today:
        return "Overdue"
    if (ns - today).days <= 7:
        return "Due Soon"
    return "Scheduled"


def _asset_clean(a: dict) -> dict:
    a["status"] = _asset_status(a)
    return _clean(a)


async def _cascade_priorities(sid: str, priorities: dict, exclude_id: str = None):
    # For each category, "insert at N": shift OTHER vendors with priority >= N down by +1.
    # Guarantees no two vendors share the same priority within a society/category.
    for cat, desired in (priorities or {}).items():
        try:
            desired = int(desired)
        except (TypeError, ValueError):
            continue
        if desired <= 0:
            continue
        q = {"society_id": sid, "categories": cat, f"priorities.{cat}": {"$gte": desired}}
        if exclude_id:
            q["_id"] = {"$ne": ObjectId(exclude_id)}
        await db.vendors.update_many(q, {"$inc": {f"priorities.{cat}": 1}})


@router.get("/audit")
async def audit_log(society_id: str = None, category: str = None, start: str = None, end: str = None,
                    limit: int = 500, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    q = {"society_id": sid}
    if category and category != "all":
        q["category"] = category
    if start or end:
        rng = {}
        if start:
            rng["$gte"] = f"{start}T00:00:00"
        if end:
            rng["$lte"] = f"{end}T23:59:59.999999"
        q["created_at"] = rng
    return [_clean(d) for d in await db.audit_logs.find(q).sort("created_at", -1).to_list(limit)]


# ---------------- Dashboard ----------------
@router.get("/dashboard")
async def dashboard(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    q = {"society_id": sid}
    now_str = datetime.now(timezone.utc).isoformat()
    today_str = datetime.now(timezone.utc).date().isoformat()
    stats = {
        "total": await db.tickets.count_documents(q),
        "open": await db.tickets.count_documents({**q, "status": "Open"}),
        "pending": await db.tickets.count_documents({**q, "status": "Pending"}),
        "resolved": await db.tickets.count_documents({**q, "status": "Resolved"}),
        "escalated": await db.tickets.count_documents({**q, "$or": [{"status": "Escalated"}, {"status": {"$in": ["Open", "Pending"]}, "sla_due": {"$lt": now_str}}]}),
        "ai_generated": await db.tickets.count_documents({**q, "ai_generated": True}),
        "vendors": await db.vendors.count_documents(q),
        "residents": await db.residents.count_documents(q),
        "overdue": await db.tickets.count_documents({**q, "status": {"$in": ["Open", "Pending", "Escalated"]}, "sla_due": {"$lt": now_str}}),
        "assigned": await db.tickets.count_documents({**q, "vendor_id": {"$ne": None}, "status": {"$in": ["Pending"]}}),
        "resolved_today": await db.tickets.count_documents({**q, "status": "Resolved", "updated_at": {"$gte": today_str}}),
    }
    recent = [_clean(t) for t in await db.tickets.find(q).sort("created_at", -1).limit(6).to_list(6)]
    escalated = [_clean(t) for t in await db.tickets.find({**q, "$or": [{"status": "Escalated"}, {"status": {"$in": ["Open", "Pending"]}, "sla_due": {"$lt": now_str}}]}).sort("created_at", -1).limit(5).to_list(5)]
    cat_pipeline = [{"$match": q}, {"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    by_category = [{"category": c["_id"], "count": c["count"]} async for c in db.tickets.aggregate(cat_pipeline)]
    status_dist = [
        {"status": s, "count": stats[k]} for s, k in
        [("Open", "open"), ("Pending", "pending"), ("Resolved", "resolved"), ("Escalated", "escalated")]
    ]
    assets_all = await db.assets.find(q).to_list(500)
    stats["assets"] = len(assets_all)
    maintenance = sorted([a for a in assets_all if a.get("next_service")], key=lambda x: x.get("next_service") or "")[:5]
    maintenance = [_asset_clean(a) for a in maintenance]
    return {"stats": stats, "recent": recent, "escalated": escalated,
            "maintenance": maintenance,
            "by_category": by_category, "status_dist": status_dist}


# ---------------- Vendors ----------------
@router.get("/vendors")
async def list_vendors(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    out = []
    for v in await db.vendors.find({"society_id": sid}).sort("created_at", -1).to_list(500):
        vid = str(v["_id"])
        v = _clean(v)
        v["assigned"] = await db.tickets.count_documents({"vendor_id": vid})
        v["resolved"] = await db.tickets.count_documents({"vendor_id": vid, "status": "Resolved"})
        out.append(v)
    return out


@router.post("/vendors")
async def create_vendor(body: VendorCreate, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    doc = body.model_dump()
    priorities = dict(doc.get("priorities") or {})
    for cat in (doc.get("categories") or []):
        desired = priorities.get(cat)
        try:
            desired = int(desired)
            if desired <= 0:
                desired = None
        except (TypeError, ValueError):
            desired = None
        if desired is None:
            # No explicit priority -> append at the end of this category (max + 1).
            existing = await db.vendors.find({"society_id": sid, "categories": cat}).to_list(1000)
            mx = 0
            for e in existing:
                p = (e.get("priorities") or {}).get(cat)
                if isinstance(p, int) and p > mx:
                    mx = p
            desired = mx + 1
        else:
            # Explicit priority -> push existing vendors at/after this slot down by 1.
            await _cascade_priorities(sid, {cat: desired})
        priorities[cat] = desired
    doc["priorities"] = priorities
    doc.update({"society_id": sid, "created_at": now_iso()})
    res = await db.vendors.insert_one(doc)
    doc["_id"] = res.inserted_id
    await audit.log(sid, "vendor_added", f"Vendor {doc.get('name')} added ({', '.join(doc.get('categories') or []) or 'general'})", actor=_actor(user), category="vendor")
    return _clean(doc)


@router.put("/vendors/{vendor_id}")
async def update_vendor(vendor_id: str, body: VendorUpdate, user: dict = Depends(require_society_admin)):
    updates = body.model_dump(exclude_none=True)
    current = await db.vendors.find_one({"_id": ObjectId(vendor_id)})
    if not current:
        raise HTTPException(status_code=404, detail="Vendor not found")
    new_pr = updates.get("priorities")
    if new_pr:
        cur_pr = current.get("priorities") or {}
        # Only cascade the categories whose priority actually changed -> avoids
        # duplicate priorities when an admin edits a vendor's rank inline.
        changed = {cat: n for cat, n in new_pr.items()
                   if isinstance(n, int) and n > 0 and cur_pr.get(cat) != n}
        await _cascade_priorities(current.get("society_id"), changed, exclude_id=vendor_id)
    await db.vendors.update_one({"_id": ObjectId(vendor_id)}, {"$set": updates})
    v = await db.vendors.find_one({"_id": ObjectId(vendor_id)})
    await audit.log(v.get("society_id"), "vendor_updated", f"Vendor {v.get('name')} details updated", actor=_actor(user), category="vendor")
    return _clean(v)


@router.delete("/vendors/{vendor_id}")
async def delete_vendor(vendor_id: str, user: dict = Depends(require_society_admin)):
    v = await db.vendors.find_one({"_id": ObjectId(vendor_id)})
    await db.vendors.delete_one({"_id": ObjectId(vendor_id)})
    if v:
        await audit.log(v.get("society_id"), "vendor_removed", f"Vendor {v.get('name')} removed", actor=_actor(user), category="vendor")
    return {"status": "deleted"}


# ---------------- Residents ----------------
@router.get("/residents")
async def list_residents(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    return [_clean(r) for r in await db.residents.find({"society_id": sid}).sort("created_at", -1).to_list(1000)]


@router.post("/residents")
async def create_resident(body: ResidentCreate, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    doc = body.model_dump()
    doc.update({"society_id": sid, "created_at": now_iso(), "approval": "active", "source": "manual"})
    res = await db.residents.insert_one(doc)
    doc["_id"] = res.inserted_id
    await audit.log(sid, "resident_added", f"Resident {doc.get('name')} ({doc.get('flat') or '—'}) added as {doc.get('status') or 'Owner'}", actor=_actor(user), category="resident")
    return _clean(doc)


@router.put("/residents/{resident_id}")
async def update_resident(resident_id: str, body: ResidentUpdate, user: dict = Depends(require_society_admin)):
    await db.residents.update_one({"_id": ObjectId(resident_id)}, {"$set": body.model_dump(exclude_none=True)})
    r = await db.residents.find_one({"_id": ObjectId(resident_id)})
    await audit.log(r.get("society_id"), "resident_updated", f"Resident {r.get('name')} ({r.get('flat') or '—'}) updated", actor=_actor(user), category="resident")
    return _clean(r)


@router.delete("/residents/{resident_id}")
async def delete_resident(resident_id: str, user: dict = Depends(require_society_admin)):
    r = await db.residents.find_one({"_id": ObjectId(resident_id)})
    await db.residents.delete_one({"_id": ObjectId(resident_id)})
    if r:
        await audit.log(r.get("society_id"), "resident_removed", f"Resident {r.get('name')} ({r.get('flat') or '—'}) removed", actor=_actor(user), category="resident")
    return {"status": "deleted"}


@router.post("/residents/import")
async def import_residents(file: UploadFile = File(...), society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    import pandas as pd
    content = await file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content))
        else:
            df = pd.read_excel(io.BytesIO(content))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse file: {e}")
    df.columns = [str(c).strip().lower() for c in df.columns]
    inserted = 0
    for _, row in df.iterrows():
        name = str(row.get("name", "")).strip()
        phone = str(row.get("phone", "")).strip().replace(".0", "")
        if not name or not phone or name == "nan":
            continue
        await db.residents.insert_one({
            "name": name, "phone": phone,
            "flat": str(row.get("flat", "")).strip().replace(".0", ""),
            "tower": str(row.get("tower", "")).strip(),
            "status": (str(row.get("status", "")).strip().title() or "Owner") if str(row.get("status", "")).strip().lower() in ("owner", "tenant") else "Owner",
            "society_id": sid, "created_at": now_iso(), "approval": "active", "source": "import",
        })
        inserted += 1
    return {"inserted": inserted}


@router.get("/form-link")
async def resident_form_link(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    soc = await db.societies.find_one({"_id": ObjectId(sid)})
    if not soc:
        raise HTTPException(status_code=404, detail="Society not found")
    token = soc.get("form_token")
    if not token:
        import secrets
        token = secrets.token_urlsafe(9)
        await db.societies.update_one({"_id": ObjectId(sid)}, {"$set": {"form_token": token}})
    return {"token": token, "path": f"/join/{token}"}


@router.post("/residents/{resident_id}/approve")
async def approve_resident(resident_id: str, user: dict = Depends(require_society_admin)):
    r = await db.residents.find_one({"_id": ObjectId(resident_id)})
    if not r:
        raise HTTPException(status_code=404, detail="Resident not found")
    await db.residents.update_one({"_id": ObjectId(resident_id)}, {"$set": {"approval": "active"}})
    sid = r.get("society_id")
    invite = {"sent": False, "link": ""}
    try:
        soc = await db.societies.find_one({"_id": ObjectId(sid)}) if sid else None
        grp = (soc or {}).get("whatsapp_group") or {}
        gid = grp.get("group_id") or grp.get("chat_id")
        link = await wa.get_group_invite_link(gid) if gid else ""
        if link and r.get("phone"):
            msg = (f"Hi {r.get('name') or 'Resident'}, your request to join "
                   f"{(soc or {}).get('name') or 'the society'} has been approved! "
                   f"Tap to join our WhatsApp group: {link}")
            resp = await wa.send_text(r["phone"], msg)
            invite = {"sent": not (isinstance(resp, dict) and resp.get("error")), "link": link}
    except Exception as e:
        import logging
        logging.getLogger("propto").warning("approve invite send failed: %s", e)
    await audit.log(sid, "resident_approved",
                    f"Resident {r.get('name')} ({r.get('flat') or '—'}) approved"
                    + (" & group invite sent" if invite["sent"] else ""),
                    actor=_actor(user), category="resident")
    r["approval"] = "active"
    return {"status": "approved", "invite": invite, "resident": _clean(r)}


# ---------------- Tickets ----------------
# ---------------- Assets ----------------
@router.get("/assets")
async def list_assets(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    return [_asset_clean(d) for d in await db.assets.find({"society_id": sid}).sort("created_at", -1).to_list(500)]


@router.get("/assets/tickets")
async def list_asset_tickets(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    return [_clean(t) for t in await db.tickets.find({"society_id": sid, "asset_id": {"$ne": None}}).sort("created_at", -1).to_list(500)]


_ASSET_FIELDS = ["name", "type", "location", "next_service", "last_service",
                 "service_frequency", "vendor_id", "vendor_name", "notes"]


@router.post("/assets")
async def create_asset(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    doc = {"society_id": sid, "created_at": now_iso()}
    for f in _ASSET_FIELDS:
        doc[f] = (body.get(f) or "").strip() if isinstance(body.get(f), str) else body.get(f) or ""
    if not doc["name"]:
        raise HTTPException(status_code=400, detail="Asset name required")
    r = await db.assets.insert_one(doc)
    await audit.log(sid, "asset_added", f"Asset {doc['name']} ({doc['type'] or '—'}) added", actor=_actor(user), category="asset")
    return _asset_clean({**doc, "_id": r.inserted_id})


@router.put("/assets/{aid}")
async def update_asset(aid: str, body: dict, user: dict = Depends(require_society_admin)):
    updates = {f: body[f] for f in _ASSET_FIELDS if f in body}
    if not updates:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await db.assets.update_one({"_id": ObjectId(aid)}, {"$set": updates})
    a = await db.assets.find_one({"_id": ObjectId(aid)})
    await audit.log(a.get("society_id"), "asset_updated", f"Asset {a.get('name')} updated", actor=_actor(user), category="asset")
    return _asset_clean(a)


@router.post("/assets/{aid}/service-done")
async def asset_service_done(aid: str, body: dict, user: dict = Depends(require_society_admin)):
    a = await db.assets.find_one({"_id": ObjectId(aid)})
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    done = body.get("service_date") or datetime.now(timezone.utc).date().isoformat()
    freq = body.get("service_frequency") or a.get("service_frequency")
    upd = {"last_service": done, "last_alert_date": None}
    if freq in FREQ_MONTHS:
        base = _parse_date(done) or datetime.now(timezone.utc).date()
        upd["next_service"] = _add_months(base, FREQ_MONTHS[freq]).isoformat()
        upd["service_frequency"] = freq
    elif body.get("next_service"):
        upd["next_service"] = body["next_service"]
    await db.assets.update_one({"_id": ObjectId(aid)}, {"$set": upd})
    a = await db.assets.find_one({"_id": ObjectId(aid)})
    await audit.log(a.get("society_id"), "asset_serviced",
                    f"Service marked done for {a.get('name')} (next: {upd.get('next_service') or '—'})",
                    actor=_actor(user), category="asset")
    return _asset_clean(a)


@router.post("/assets/{aid}/schedule")
async def asset_schedule(aid: str, body: dict, user: dict = Depends(require_society_admin)):
    upd = {"last_alert_date": None}
    for f in ["next_service", "service_frequency", "vendor_id", "vendor_name"]:
        if f in body:
            upd[f] = body[f]
    if upd.get("vendor_id") and not upd.get("vendor_name"):
        v = await db.vendors.find_one({"_id": ObjectId(upd["vendor_id"])})
        if v:
            upd["vendor_name"] = v.get("name")
    await db.assets.update_one({"_id": ObjectId(aid)}, {"$set": upd})
    a = await db.assets.find_one({"_id": ObjectId(aid)})
    await audit.log(a.get("society_id"), "asset_scheduled",
                    f"Service scheduled for {a.get('name')} on {upd.get('next_service') or '—'}",
                    actor=_actor(user), category="asset")
    return _asset_clean(a)


@router.post("/assets/{aid}/raise-ticket")
async def asset_raise_ticket(aid: str, body: dict, user: dict = Depends(require_society_admin)):
    a = await db.assets.find_one({"_id": ObjectId(aid)})
    if not a:
        raise HTTPException(status_code=404, detail="Asset not found")
    prio = body.get("priority") or "Medium"
    hrs = pipeline.SLA_HOURS.get(prio, 24)
    now = datetime.now(timezone.utc)
    doc = {
        "ticket_number": pipeline.gen_ticket_number(),
        "society_id": a.get("society_id"),
        "category": body.get("category") or a.get("type") or "Maintenance",
        "sub_category": a.get("name"),
        "description": body.get("description") or f"Service/maintenance required for {a.get('name')}",
        "status": "Open", "priority": prio,
        "flat": "", "tower": a.get("location") or "",
        "resident_name": "Society (Asset)", "resident_phone": None,
        "asset_id": aid, "asset_name": a.get("name"),
        "source": "asset", "ai_generated": False,
        "vendor_id": None, "vendor_name": None,
        "sla_hours": hrs, "sla_due": (now + timedelta(hours=hrs)).isoformat(),
        "timeline": [{"event": "Ticket Raised", "detail": f"Asset ticket for {a.get('name')}", "at": now_iso()}],
        "created_at": now_iso(), "updated_at": now_iso(),
    }
    r = await db.tickets.insert_one(doc)
    await audit.log(a.get("society_id"), "asset_ticket_raised",
                    f"Ticket {doc['ticket_number']} raised for asset {a.get('name')}",
                    actor=_actor(user), category="ticket", ticket_number=doc["ticket_number"])
    return _clean({**doc, "_id": r.inserted_id})


@router.delete("/assets/{aid}")
async def delete_asset(aid: str, user: dict = Depends(require_society_admin)):
    await db.assets.delete_one({"_id": ObjectId(aid)})
    return {"status": "deleted"}


# ---------------- Escalation Matrix (society-level, used for asset service alerts) ----------------
@router.get("/escalation-matrix")
async def get_escalation_matrix(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    soc = await db.societies.find_one({"_id": ObjectId(sid)})
    return {"matrix": (soc or {}).get("escalation_matrix") or []}


@router.put("/escalation-matrix")
async def put_escalation_matrix(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    matrix = []
    for m in (body.get("matrix") or []):
        try:
            wait = int(m.get("wait_minutes") or 0)
        except (TypeError, ValueError):
            wait = 0
        matrix.append({"name": (m.get("name") or "").strip(), "phone": (m.get("phone") or "").strip(),
                       "role": (m.get("role") or "").strip(), "wait_minutes": wait})
    await db.societies.update_one({"_id": ObjectId(sid)}, {"$set": {"escalation_matrix": matrix}})
    await audit.log(sid, "escalation_matrix_updated", f"Escalation matrix updated ({len(matrix)} levels)", actor=_actor(user), category="asset")
    return {"matrix": matrix}


# ---------------- Escalation Timeline (notification rules for asset service alerts) ----------------
DEFAULT_TIMELINE = [
    {"key": "pre", "offset_days": 7, "direction": "before", "timing": "7 days before due date",
     "title": "Pre-service reminder", "description": "WhatsApp reminder sent to vendor and secretary to prepare for upcoming service.",
     "notify": ["Secretary", "Vendor"], "channel": "WhatsApp", "color": "blue"},
    {"key": "final", "offset_days": 1, "direction": "before", "timing": "1 day before due date",
     "title": "Final reminder", "description": "Last-minute alert to confirm vendor availability and secretary preparedness.",
     "notify": ["Secretary", "Vendor"], "channel": "WhatsApp", "color": "amber"},
    {"key": "overdue", "offset_days": 2, "direction": "after", "timing": "2 days after due date (if not updated)",
     "title": "Overdue escalation", "description": "If secretary has not marked service as done, chairman is looped in for oversight.",
     "notify": ["Secretary", "Chairman"], "channel": "WhatsApp", "color": "red"},
    {"key": "critical", "offset_days": 7, "direction": "after", "timing": "7 days after due date (if not updated)",
     "title": "Critical escalation", "description": "Full escalation to management. All committee members notified via WhatsApp.",
     "notify": ["Secretary", "Chairman", "Manager"], "channel": "WhatsApp", "color": "purple"},
]
_VALID_ROLES = ["Secretary", "Vendor", "Chairman", "Manager"]


@router.get("/escalation-timeline")
async def get_escalation_timeline(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    soc = await db.societies.find_one({"_id": ObjectId(sid)})
    return {"timeline": (soc or {}).get("escalation_timeline") or DEFAULT_TIMELINE}


@router.put("/escalation-timeline")
async def put_escalation_timeline(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    timeline = []
    for r in (body.get("timeline") or []):
        try:
            off = int(r.get("offset_days") or 0)
        except (TypeError, ValueError):
            off = 0
        direction = "after" if (r.get("direction") == "after") else "before"
        notify = [n for n in (r.get("notify") or []) if n in _VALID_ROLES]
        timeline.append({
            "key": (r.get("key") or "").strip(),
            "offset_days": off,
            "direction": direction,
            "timing": (r.get("timing") or "").strip(),
            "title": (r.get("title") or "").strip(),
            "description": (r.get("description") or "").strip(),
            "notify": notify,
            "channel": "WhatsApp",
            "color": (r.get("color") or "blue").strip(),
        })
    await db.societies.update_one({"_id": ObjectId(sid)}, {"$set": {"escalation_timeline": timeline}})
    await audit.log(sid, "escalation_timeline_updated", f"Escalation timeline updated ({len(timeline)} rules)", actor=_actor(user), category="asset")
    return {"timeline": timeline}


# ---------------- Routing mode (all complaints -> Society Manager) ----------------
@router.get("/routing-mode")
async def get_routing_mode(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    s = await db.societies.find_one({"_id": ObjectId(sid)})
    return {"manager_only_routing": (s or {}).get("manager_only_routing", True)}


@router.put("/routing-mode")
async def set_routing_mode(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    val = bool(body.get("manager_only_routing"))
    await db.societies.update_one({"_id": ObjectId(sid)}, {"$set": {"manager_only_routing": val}})
    await audit.log(sid, "routing_mode_changed",
                    f"Vendor routing {'DISABLED — all complaints go to Society Manager' if val else 'ENABLED — complaints auto-route to vendors'}",
                    actor=_actor(user), category="society")
    return {"manager_only_routing": val}


# ---------------- Society Committee ----------------
@router.get("/committee")
async def list_committee(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    return [_clean(d) for d in await db.committee.find({"society_id": sid}).sort("created_at", -1).to_list(200)]


@router.post("/committee")
async def create_committee(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    doc = {"society_id": sid, "name": (body.get("name") or "").strip(),
           "role": (body.get("role") or "Member").strip(), "tower": (body.get("tower") or "").strip(),
           "phone": (body.get("phone") or "").strip(), "email": (body.get("email") or "").strip(),
           "created_at": now_iso()}
    if not doc["name"]:
        raise HTTPException(status_code=400, detail="Member name required")
    r = await db.committee.insert_one(doc)
    await audit.log(sid, "committee_added", f"{doc['name']} added to committee as {doc['role']}", actor=_actor(user), category="committee")
    return _clean({**doc, "_id": r.inserted_id})


@router.put("/committee/{cid}")
async def update_committee(cid: str, body: dict, user: dict = Depends(require_society_admin)):
    upd = {k: (body.get(k) or "").strip() for k in ("name", "role", "tower", "phone", "email") if k in body}
    if "name" in upd and not upd["name"]:
        raise HTTPException(status_code=400, detail="Member name required")
    await db.committee.update_one({"_id": ObjectId(cid)}, {"$set": upd})
    doc = await db.committee.find_one({"_id": ObjectId(cid)})
    if not doc:
        raise HTTPException(status_code=404, detail="Member not found")
    await audit.log(doc.get("society_id"), "committee_updated", f"{doc.get('name')} ({doc.get('role')}) updated", actor=_actor(user), category="committee")
    return _clean(doc)


@router.delete("/committee/{cid}")
async def delete_committee(cid: str, user: dict = Depends(require_society_admin)):
    await db.committee.delete_one({"_id": ObjectId(cid)})
    return {"status": "deleted"}


# ---------------- Escalated tickets ----------------
@router.get("/tickets/escalated")
async def escalated_tickets(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    now_str = datetime.now(timezone.utc).isoformat()
    q = {"society_id": sid, "$or": [
        {"status": "Escalated"},
        {"status": {"$in": ["Open", "Pending"]}, "sla_due": {"$lt": now_str}},
    ]}
    return [_clean(t) for t in await db.tickets.find(q).sort("created_at", -1).to_list(100)]


# ---------------- Ticket assignment logic (config view) ----------------
@router.get("/assignment-config")
async def assignment_config(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    vendors = await db.vendors.find({"society_id": sid, "active": True}).to_list(500)
    cats = {}
    for v in vendors:
        for c in v.get("categories", []):
            cats[c] = cats.get(c, 0) + 1
    coverage = [{"category": c, "vendors": n} for c, n in sorted(cats.items())]
    return {
        "sla": [
            {"severity": "Critical", "hours": 2, "color": "#dc2626"},
            {"severity": "High", "hours": 4, "color": "#ef4444"},
            {"severity": "Medium", "hours": 24, "color": "#d97706"},
            {"severity": "Low", "hours": 72, "color": "#16a34a"},
        ],
        "coverage": coverage,
        "vendor_count": len(vendors),
    }


@router.get("/tickets")
async def list_tickets(society_id: str = None, status: str = None, category: str = None,
                       priority: str = None, search: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    q = {"society_id": sid}
    if status and status != "all":
        q["status"] = status
    if category and category != "all":
        q["category"] = category
    if priority and priority != "all":
        q["priority"] = priority
    if search:
        q["$or"] = [
            {"ticket_number": {"$regex": search, "$options": "i"}},
            {"flat": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}},
            {"resident_name": {"$regex": search, "$options": "i"}},
        ]
    return [_clean(t) for t in await db.tickets.find(q).sort("created_at", -1).to_list(1000)]


@router.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, user: dict = Depends(require_society_admin)):
    t = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return _clean(t)


@router.post("/tickets/{ticket_id}/assign")
async def assign(ticket_id: str, body: TicketAssign, user: dict = Depends(require_society_admin)):
    t = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if not t:
        raise HTTPException(status_code=404, detail="Ticket not found")
    v = await db.vendors.find_one({"_id": ObjectId(body.vendor_id)})
    if not v:
        raise HTTPException(status_code=404, detail="Vendor not found")
    await pipeline.assign_vendor(t, v, actor=_actor(user))
    return _clean(await db.tickets.find_one({"_id": ObjectId(ticket_id)}))


@router.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: TicketUpdate, user: dict = Depends(require_society_admin)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields")
    updates["updated_at"] = now_iso()
    await db.tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": updates})
    t2 = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if "status" in updates:
        await pipeline.add_timeline(ticket_id, f"Status: {updates['status']}", "Updated by admin")
        await audit.log(t2.get("society_id"), "ticket_status_changed", f"{t2.get('ticket_number')} status changed to {updates['status']}", actor=_actor(user), category="ticket", ticket_number=t2.get("ticket_number"))
    return _clean(t2)


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, user: dict = Depends(require_society_admin)):
    await db.tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": {"status": "Resolved", "updated_at": now_iso()}})
    await pipeline.add_timeline(ticket_id, "Ticket Closed", "Marked resolved by admin")
    t = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    await audit.log(t.get("society_id"), "ticket_resolved", f"{t.get('ticket_number')} marked resolved by admin", actor=_actor(user), category="ticket", ticket_number=t.get("ticket_number"))
    if t.get("resident_phone"):
        import whatsapp_client as wa
        await wa.send_text(t["resident_phone"], f"Your ticket {t['ticket_number']} has been resolved. Please share feedback!")
    return _clean(t)


@router.get("/categories")
async def categories(user: dict = Depends(require_society_admin)):
    return COMPLAINT_CATEGORIES
