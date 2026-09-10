from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from bson import ObjectId
from datetime import datetime, timezone
import io

from db import db, COMPLAINT_CATEGORIES
from models import (VendorCreate, VendorUpdate, ResidentCreate, ResidentUpdate,
                    TicketAssign, TicketUpdate, now_iso)
from auth_utils import require_society_admin, user_society_id
import pipeline
import audit

router = APIRouter(prefix="/api/society", tags=["society_admin"])


def _clean(doc):
    doc["id"] = str(doc.pop("_id"))
    return doc


def _sid(user):
    # super_admin may pass ?society_id filter via society scoping; society_admin uses own
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


def _actor(user):
    return user.get("name") or user.get("email") or user.get("role", "admin")


@router.get("/audit")
async def audit_log(society_id: str = None, category: str = None, limit: int = 300, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    q = {"society_id": sid}
    if category and category != "all":
        q["category"] = category
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
        "escalated": await db.tickets.count_documents({**q, "status": "Escalated"}),
        "ai_generated": await db.tickets.count_documents({**q, "ai_generated": True}),
        "vendors": await db.vendors.count_documents(q),
        "residents": await db.residents.count_documents(q),
        "overdue": await db.tickets.count_documents({**q, "status": {"$in": ["Open", "Pending", "Escalated"]}, "sla_due": {"$lt": now_str}}),
        "assigned": await db.tickets.count_documents({**q, "vendor_id": {"$ne": None}, "status": {"$in": ["Pending"]}}),
        "resolved_today": await db.tickets.count_documents({**q, "status": "Resolved", "updated_at": {"$gte": today_str}}),
    }
    recent = [_clean(t) for t in await db.tickets.find(q).sort("created_at", -1).limit(6).to_list(6)]
    escalated = [_clean(t) for t in await db.tickets.find({**q, "status": "Escalated"}).sort("created_at", -1).limit(5).to_list(5)]
    cat_pipeline = [{"$match": q}, {"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    by_category = [{"category": c["_id"], "count": c["count"]} async for c in db.tickets.aggregate(cat_pipeline)]
    status_dist = [
        {"status": s, "count": stats[k]} for s, k in
        [("Open", "open"), ("Pending", "pending"), ("Resolved", "resolved"), ("Escalated", "escalated")]
    ]
    return {"stats": stats, "recent": recent, "escalated": escalated,
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
    doc.update({"society_id": sid, "created_at": now_iso()})
    res = await db.vendors.insert_one(doc)
    doc["_id"] = res.inserted_id
    await audit.log(sid, "vendor_added", f"Vendor {doc.get('name')} added ({', '.join(doc.get('categories') or []) or 'general'})", actor=_actor(user), category="vendor")
    return _clean(doc)


@router.put("/vendors/{vendor_id}")
async def update_vendor(vendor_id: str, body: VendorUpdate, user: dict = Depends(require_society_admin)):
    updates = body.model_dump(exclude_none=True)
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
    doc.update({"society_id": sid, "created_at": now_iso()})
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
            "society_id": sid, "created_at": now_iso(),
        })
        inserted += 1
    return {"inserted": inserted}


# ---------------- Tickets ----------------
# ---------------- Assets ----------------
@router.get("/assets")
async def list_assets(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    return [_clean(d) for d in await db.assets.find({"society_id": sid}).sort("created_at", -1).to_list(500)]


@router.post("/assets")
async def create_asset(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        raise HTTPException(status_code=400, detail="society_id required")
    doc = {"society_id": sid, "name": (body.get("name") or "").strip(),
           "type": (body.get("type") or "").strip(), "location": (body.get("location") or "").strip(),
           "next_service": body.get("next_service") or "", "status": body.get("status") or "Scheduled",
           "created_at": now_iso()}
    if not doc["name"]:
        raise HTTPException(status_code=400, detail="Asset name required")
    r = await db.assets.insert_one(doc)
    await audit.log(sid, "asset_added", f"Asset {doc['name']} ({doc['type'] or '—'}) added", actor=_actor(user), category="asset")
    return _clean({**doc, "_id": r.inserted_id})


@router.delete("/assets/{aid}")
async def delete_asset(aid: str, user: dict = Depends(require_society_admin)):
    await db.assets.delete_one({"_id": ObjectId(aid)})
    return {"status": "deleted"}


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
