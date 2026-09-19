from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta

from db import db
from models import now_iso
from auth_utils import require_society_admin, user_society_id

router = APIRouter(prefix="/api/society/notifications", tags=["notifications"])


def _sid(user):
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


def _parse_date(v):
    if not v:
        return None
    v = str(v).strip()
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d %B %Y", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(v[:len(fmt) + 4], fmt).replace(tzinfo=timezone.utc)
        except Exception:
            continue
    try:
        return datetime.fromisoformat(v).astimezone(timezone.utc)
    except Exception:
        return None


async def _derive(sid: str):
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    items = []

    # Overdue tickets (past SLA, still active)
    overdue = await db.tickets.find({
        "society_id": sid,
        "status": {"$in": ["Open", "Pending", "Escalated"]},
        "sla_due": {"$lt": now_str},
    }).sort("sla_due", 1).to_list(50)
    for t in overdue:
        items.append({
            "id": f"overdue_{t['_id']}", "type": "overdue", "severity": "high",
            "title": f"Ticket {t.get('ticket_number', '')} is overdue",
            "detail": f"{t.get('category', 'Issue')} in {t.get('flat') or t.get('tower') or 'society'}",
            "time": t.get("sla_due") or t.get("created_at"), "link": "/escalated",
        })

    # Escalated tickets (needs manual action)
    escalated = await db.tickets.find({"society_id": sid, "status": "Escalated"}).sort("created_at", -1).to_list(50)
    for t in escalated:
        items.append({
            "id": f"escalated_{t['_id']}", "type": "escalated", "severity": "high",
            "title": f"Ticket {t.get('ticket_number', '')} escalated",
            "detail": t.get("escalation_reason") or "Requires manual vendor assignment",
            "time": t.get("updated_at") or t.get("created_at"), "link": "/escalated",
        })

    # Assets — due soon / overdue
    assets = await db.assets.find({"society_id": sid}).to_list(200)
    soon = now + timedelta(days=7)
    for a in assets:
        due = _parse_date(a.get("next_service"))
        if not due:
            continue
        if due < now:
            items.append({
                "id": f"asset_overdue_{a['_id']}", "type": "asset_overdue", "severity": "high",
                "title": "Asset service overdue",
                "detail": f"{a.get('name', 'Asset')} service was due on {a.get('next_service')}",
                "time": due.isoformat(), "link": "/assets",
            })
        elif due <= soon:
            items.append({
                "id": f"asset_due_{a['_id']}", "type": "asset_due", "severity": "medium",
                "title": "Asset service due soon",
                "detail": f"{a.get('name', 'Asset')} service is due on {a.get('next_service')}",
                "time": due.isoformat(), "link": "/assets",
            })

    # New suggestions (last 14 days)
    since = (now - timedelta(days=14)).isoformat()
    suggestions = await db.suggestions.find({"society_id": sid, "created_at": {"$gte": since}}).sort("created_at", -1).to_list(50)
    for s in suggestions:
        via = " (via WhatsApp group)" if s.get("source") == "group_poll" else ""
        items.append({
            "id": f"suggestion_{s['_id']}", "type": "suggestion", "severity": "low",
            "title": f"New resident suggestion{via}",
            "detail": s.get("title", ""),
            "time": s.get("created_at"), "link": "/suggestions",
        })

    # Pending resident approvals
    pending = await db.residents.find({"society_id": sid, "approval": "pending"}).sort("created_at", -1).to_list(50)
    for r in pending:
        items.append({
            "id": f"resident_{r['_id']}", "type": "resident", "severity": "medium",
            "title": "New resident registration",
            "detail": f"{r.get('name', 'A resident')} ({r.get('flat') or '—'}) is awaiting approval",
            "time": r.get("created_at"), "link": "/residents",
        })

    items.sort(key=lambda x: x.get("time") or "", reverse=True)
    return items


@router.get("")
async def list_notifications(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        return {"items": [], "unread": 0}
    items = await _derive(sid)
    read_ids = {d["notif_id"] for d in await db.notification_reads.find({"society_id": sid}).to_list(2000)}
    unread = 0
    for it in items:
        it["read"] = it["id"] in read_ids
        if not it["read"]:
            unread += 1
    return {"items": items, "unread": unread}


@router.get("/unread-count")
async def unread_count(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    if not sid:
        return {"unread": 0}
    items = await _derive(sid)
    read_ids = {d["notif_id"] for d in await db.notification_reads.find({"society_id": sid}).to_list(2000)}
    return {"unread": sum(1 for it in items if it["id"] not in read_ids)}


@router.post("/read")
async def mark_read(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    ids = body.get("ids") or []
    if body.get("all"):
        items = await _derive(sid)
        ids = [it["id"] for it in items]
    for nid in ids:
        await db.notification_reads.update_one(
            {"society_id": sid, "notif_id": nid},
            {"$set": {"society_id": sid, "notif_id": nid, "read_at": now_iso()}},
            upsert=True,
        )
    return {"status": "ok", "marked": len(ids)}
