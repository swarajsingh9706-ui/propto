from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta

from db import db
from auth_utils import require_society_admin, user_society_id

router = APIRouter(prefix="/api/society/reports", tags=["reports"])


def _sid(user):
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


@router.get("")
async def reports(society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    q = {"society_id": sid}
    tickets = await db.tickets.find(q).to_list(5000)

    # daily complaints last 14 days
    daily = {}
    for i in range(13, -1, -1):
        d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
        daily[d] = 0
    for t in tickets:
        d = (t.get("created_at") or "")[:10]
        if d in daily:
            daily[d] += 1
    daily_series = [{"date": k[5:], "count": v} for k, v in daily.items()]

    # category
    cats = {}
    for t in tickets:
        cats[t.get("category", "Other")] = cats.get(t.get("category", "Other"), 0) + 1
    category_series = [{"category": k, "count": v} for k, v in sorted(cats.items(), key=lambda x: -x[1])]

    # resolution time (avg hours) per category for resolved
    res_times = {}
    counts = {}
    for t in tickets:
        if t.get("status") == "Resolved" and t.get("created_at") and t.get("updated_at"):
            try:
                c = datetime.fromisoformat(t["created_at"])
                u = datetime.fromisoformat(t["updated_at"])
                hrs = (u - c).total_seconds() / 3600
                res_times[t["category"]] = res_times.get(t["category"], 0) + hrs
                counts[t["category"]] = counts.get(t["category"], 0) + 1
            except Exception:
                pass
    resolution_series = [{"category": k, "hours": round(res_times[k] / counts[k], 1)} for k in res_times]

    # vendor performance
    vp = []
    for v in await db.vendors.find(q).to_list(500):
        vid = str(v["_id"])
        assigned = await db.tickets.count_documents({"vendor_id": vid})
        resolved = await db.tickets.count_documents({"vendor_id": vid, "status": "Resolved"})
        vp.append({"vendor": v["name"], "assigned": assigned, "resolved": resolved,
                   "rate": round(resolved / assigned * 100) if assigned else 0})
    vp.sort(key=lambda x: -x["resolved"])

    total = len(tickets)
    ai_count = sum(1 for t in tickets if t.get("ai_generated"))
    return {
        "daily": daily_series,
        "categories": category_series,
        "resolution": resolution_series,
        "vendor_performance": vp,
        "summary": {
            "total": total,
            "resolved": sum(1 for t in tickets if t.get("status") == "Resolved"),
            "ai_detection_rate": round(ai_count / total * 100) if total else 0,
            "ai_generated": ai_count,
        },
    }
