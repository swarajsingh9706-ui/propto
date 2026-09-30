from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId
from datetime import datetime, timezone

from db import db, COMPLAINT_CATEGORIES
from models import SocietyCreate, SocietyUpdate, now_iso
from auth_utils import require_super_admin, hash_password
import audit

router = APIRouter(prefix="/api/super", tags=["super_admin"])


def _clean(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


@router.get("/societies")
async def list_societies(user: dict = Depends(require_super_admin)):
    out = []
    for s in await db.societies.find().sort("created_at", -1).to_list(500):
        sid = str(s["_id"])
        s = _clean(s)
        s["ticket_count"] = await db.tickets.count_documents({"society_id": sid})
        s["vendor_count"] = await db.vendors.count_documents({"society_id": sid})
        s["resident_count"] = await db.residents.count_documents({"society_id": sid})
        out.append(s)
    return out


@router.post("/societies")
async def create_society(body: SocietyCreate, user: dict = Depends(require_super_admin)):
    if await db.societies.find_one({"code": body.code.upper()}):
        raise HTTPException(status_code=400, detail="Society code already exists")
    doc = {
        "name": body.name, "code": body.code.upper(), "address": body.address or "",
        "city": body.city or "", "towers": body.towers or [], "active": True,
        "whatsapp_group": None, "monitoring": False, "manager_only_routing": True, "created_at": now_iso(),
    }
    res = await db.societies.insert_one(doc)
    sid = str(res.inserted_id)

    if body.admin_email and body.admin_password:
        email = body.admin_email.lower().strip()
        if await db.users.find_one({"email": email}):
            raise HTTPException(status_code=400, detail="Admin email already in use")
        await db.users.insert_one({
            "email": email, "password_hash": hash_password(body.admin_password),
            "name": body.admin_name or "Society Admin", "role": "society_admin",
            "society_id": sid, "created_at": now_iso(),
        })
    doc["_id"] = res.inserted_id
    actor = user.get("name") or user.get("email") or "Super Admin"
    await audit.log(sid, "society_created", f"Society '{body.name}' ({body.code.upper()}) created", actor=actor, category="society")
    return _clean(doc)


@router.put("/societies/{society_id}")
async def update_society(society_id: str, body: SocietyUpdate, user: dict = Depends(require_super_admin)):
    updates = {k: v for k, v in body.model_dump(exclude_none=True).items()}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.societies.update_one({"_id": ObjectId(society_id)}, {"$set": updates})
    s = await db.societies.find_one({"_id": ObjectId(society_id)})
    if not s:
        raise HTTPException(status_code=404, detail="Society not found")
    return _clean(s)


@router.delete("/societies/{society_id}")
async def delete_society(society_id: str, user: dict = Depends(require_super_admin)):
    await db.societies.delete_one({"_id": ObjectId(society_id)})
    return {"status": "deleted"}


@router.get("/dashboard")
async def super_dashboard(user: dict = Depends(require_super_admin)):
    now_str = datetime.now(timezone.utc).isoformat()
    societies = await db.societies.find().sort("created_at", -1).to_list(500)
    rows = []
    for s in societies:
        sid = str(s["_id"])
        rows.append({
            "id": sid, "name": s["name"], "code": s["code"], "city": s.get("city", ""),
            "active": s.get("active", True),
            "total": await db.tickets.count_documents({"society_id": sid}),
            "open": await db.tickets.count_documents({"society_id": sid, "status": {"$in": ["Open", "Pending"]}}),
            "escalated": await db.tickets.count_documents({"society_id": sid, "status": "Escalated"}),
            "resolved": await db.tickets.count_documents({"society_id": sid, "status": "Resolved"}),
        })
    stats = {
        "societies": len(societies),
        "active_societies": sum(1 for s in societies if s.get("active", True)),
        "total_tickets": await db.tickets.count_documents({}),
        "open": await db.tickets.count_documents({"status": {"$in": ["Open", "Pending"]}}),
        "escalated": await db.tickets.count_documents({"status": "Escalated"}),
        "overdue": await db.tickets.count_documents({"status": {"$in": ["Open", "Pending", "Escalated"]}, "sla_due": {"$lt": now_str}}),
        "resolved": await db.tickets.count_documents({"status": "Resolved"}),
        "vendors": await db.vendors.count_documents({}),
    }
    cat_pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 6}]
    categories = [{"category": c["_id"], "count": c["count"]} async for c in db.tickets.aggregate(cat_pipeline)]
    recent = []
    for t in await db.tickets.find().sort("created_at", -1).limit(6).to_list(6):
        recent.append(_clean(t))
    return {"stats": stats, "societies": rows, "categories": categories, "recent": recent}


@router.get("/categories")
async def get_categories(user: dict = Depends(require_super_admin)):
    return COMPLAINT_CATEGORIES


@router.get("/reports")
async def super_reports(user: dict = Depends(require_super_admin)):
    societies = await db.societies.find().to_list(500)
    society_reports = []
    for s in societies:
        sid = str(s["_id"])
        total = await db.tickets.count_documents({"society_id": sid})
        resolved = await db.tickets.count_documents({"society_id": sid, "status": "Resolved"})
        open_t = await db.tickets.count_documents({"society_id": sid, "status": {"$in": ["Open", "Pending"]}})
        society_reports.append({
            "society": s["name"], "code": s["code"], "active": s.get("active", True),
            "total": total, "resolved": resolved, "open": open_t,
        })
    # category analytics across all
    pipeline = [{"$group": {"_id": "$category", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    cat = [{"category": c["_id"], "count": c["count"]} async for c in db.tickets.aggregate(pipeline)]
    # vendor performance
    vp = []
    for v in await db.vendors.find().to_list(500):
        vid = str(v["_id"])
        assigned = await db.tickets.count_documents({"vendor_id": vid})
        resolved = await db.tickets.count_documents({"vendor_id": vid, "status": "Resolved"})
        vp.append({"vendor": v["name"], "assigned": assigned, "resolved": resolved,
                   "rate": round(resolved / assigned * 100) if assigned else 0})
    vp.sort(key=lambda x: x["resolved"], reverse=True)
    return {"societies": society_reports, "categories": cat, "vendor_performance": vp[:10],
            "totals": {"societies": len(societies),
                       "tickets": await db.tickets.count_documents({}),
                       "vendors": await db.vendors.count_documents({}),
                       "residents": await db.residents.count_documents({})}}
