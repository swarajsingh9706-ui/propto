from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from bson import ObjectId
from datetime import datetime, timezone
import io

from db import db, COMPLAINT_CATEGORIES
from models import (VendorCreate, VendorUpdate, ResidentCreate, ResidentUpdate,
                    TicketAssign, TicketUpdate, now_iso)
from auth_utils import require_society_admin, user_society_id
import pipeline

router = APIRouter(prefix="/api/society", tags=["society_admin"])


def _clean(doc):
    doc["id"] = str(doc.pop("_id"))
    return doc


def _sid(user):
    # super_admin may pass ?society_id filter via society scoping; society_admin uses own
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


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
    return _clean(doc)


@router.put("/vendors/{vendor_id}")
async def update_vendor(vendor_id: str, body: VendorUpdate, user: dict = Depends(require_society_admin)):
    updates = body.model_dump(exclude_none=True)
    await db.vendors.update_one({"_id": ObjectId(vendor_id)}, {"$set": updates})
    v = await db.vendors.find_one({"_id": ObjectId(vendor_id)})
    return _clean(v)


@router.delete("/vendors/{vendor_id}")
async def delete_vendor(vendor_id: str, user: dict = Depends(require_society_admin)):
    await db.vendors.delete_one({"_id": ObjectId(vendor_id)})
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
    return _clean(doc)


@router.put("/residents/{resident_id}")
async def update_resident(resident_id: str, body: ResidentUpdate, user: dict = Depends(require_society_admin)):
    await db.residents.update_one({"_id": ObjectId(resident_id)}, {"$set": body.model_dump(exclude_none=True)})
    r = await db.residents.find_one({"_id": ObjectId(resident_id)})
    return _clean(r)


@router.delete("/residents/{resident_id}")
async def delete_resident(resident_id: str, user: dict = Depends(require_society_admin)):
    await db.residents.delete_one({"_id": ObjectId(resident_id)})
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
@router.get("/tickets")
async def list_tickets(society_id: str = None, status: str = None, category: str = None,
                       search: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    q = {"society_id": sid}
    if status and status != "all":
        q["status"] = status
    if category and category != "all":
        q["category"] = category
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
    await pipeline.assign_vendor(t, v)
    return _clean(await db.tickets.find_one({"_id": ObjectId(ticket_id)}))


@router.put("/tickets/{ticket_id}")
async def update_ticket(ticket_id: str, body: TicketUpdate, user: dict = Depends(require_society_admin)):
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields")
    updates["updated_at"] = now_iso()
    await db.tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": updates})
    if "status" in updates:
        await pipeline.add_timeline(ticket_id, f"Status: {updates['status']}", "Updated by admin")
    return _clean(await db.tickets.find_one({"_id": ObjectId(ticket_id)}))


@router.post("/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, user: dict = Depends(require_society_admin)):
    await db.tickets.update_one({"_id": ObjectId(ticket_id)}, {"$set": {"status": "Resolved", "updated_at": now_iso()}})
    await pipeline.add_timeline(ticket_id, "Ticket Closed", "Marked resolved by admin")
    t = await db.tickets.find_one({"_id": ObjectId(ticket_id)})
    if t.get("resident_phone"):
        import whatsapp_client as wa
        await wa.send_text(t["resident_phone"], f"Your ticket {t['ticket_number']} has been resolved. Please share feedback!")
    return _clean(t)


@router.get("/categories")
async def categories(user: dict = Depends(require_society_admin)):
    return COMPLAINT_CATEGORIES
