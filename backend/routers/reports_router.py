from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
import io
import base64
import logging
from bson import ObjectId

from db import db
from auth_utils import require_society_admin, user_society_id
import whatsapp_client as wa

logger = logging.getLogger("propto.reports")

router = APIRouter(prefix="/api/society/reports", tags=["reports"])


def _sid(user):
    return user_society_id(user) if user["role"] == "society_admin" else user.get("society_id")


@router.get("")
async def reports(society_id: str = None, start: str = None, end: str = None,
                  user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    tickets = await db.tickets.find({"society_id": sid}).to_list(5000)

    def _in_range(t):
        d = (t.get("created_at") or "")[:10]
        if start and d < start:
            return False
        if end and d > end:
            return False
        return True

    tickets = [t for t in tickets if _in_range(t)]

    # daily complaints — across selected range, else last 14 days
    daily = {}
    if start and end:
        s = datetime.fromisoformat(start)
        e = datetime.fromisoformat(end)
        span = min((e - s).days, 365)
        for i in range(span, -1, -1):
            d = (e - timedelta(days=i)).strftime("%Y-%m-%d")
            daily[d] = 0
    else:
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

    # vendor performance (range-aware, from filtered tickets)
    vp_map = {}
    for t in tickets:
        vid = t.get("vendor_id")
        if not vid:
            continue
        name = t.get("vendor_name") or "Vendor"
        rec = vp_map.setdefault(vid, {"vendor": name, "assigned": 0, "resolved": 0})
        rec["assigned"] += 1
        if t.get("status") == "Resolved":
            rec["resolved"] += 1
    vp = []
    for rec in vp_map.values():
        rec["rate"] = round(rec["resolved"] / rec["assigned"] * 100) if rec["assigned"] else 0
        vp.append(rec)
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


def _build_pdf(soc: dict, data: dict, sections: list, start: str, end: str) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=18 * mm, bottomMargin=16 * mm)
    ss = getSampleStyleSheet()
    brand = colors.HexColor("#1e40af")
    h = ParagraphStyle("h", parent=ss["Title"], textColor=brand, fontSize=22, spaceAfter=2)
    sub = ParagraphStyle("sub", parent=ss["Normal"], textColor=colors.HexColor("#64748b"), fontSize=9)
    sec = ParagraphStyle("sec", parent=ss["Heading2"], textColor=brand, fontSize=13, spaceBefore=14, spaceAfter=6)
    el = [Paragraph("PROPTO", h), Paragraph(f"{soc.get('name','Society')} — Reports", sub)]
    rng = f"{start or 'All time'} to {end or 'now'}"
    el.append(Paragraph(f"Period: {rng} &nbsp;|&nbsp; Generated: {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}", sub))
    el.append(Spacer(1, 8))

    def tbl(rows, widths=None):
        t = Table(rows, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), brand), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef2f7")]),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("PADDING", (0, 0), (-1, -1), 5)]))
        return t

    s = data["summary"]
    if "summary" in sections:
        el.append(Paragraph("Summary", sec))
        el.append(tbl([["Metric", "Value"], ["Total Complaints", str(s["total"])], ["Resolved", str(s["resolved"])],
                       ["AI Detection Rate", f"{s['ai_detection_rate']}%"], ["AI Generated", str(s["ai_generated"])]], [260, 200]))
    if "categories" in sections and data["categories"]:
        el.append(Paragraph("Top Issue Categories", sec))
        el.append(tbl([["Category", "Count"]] + [[c["category"], str(c["count"])] for c in data["categories"][:12]], [320, 140]))
    if "resolution" in sections and data["resolution"]:
        el.append(Paragraph("Avg Resolution Time (hours)", sec))
        el.append(tbl([["Category", "Hours"]] + [[r["category"], str(r["hours"])] for r in data["resolution"]], [320, 140]))
    if "vendors" in sections and data["vendor_performance"]:
        el.append(Paragraph("Vendor Performance", sec))
        el.append(tbl([["Vendor", "Assigned", "Resolved", "Rate"]] +
                      [[v["vendor"], str(v["assigned"]), str(v["resolved"]), f"{v['rate']}%"] for v in data["vendor_performance"][:15]]))
    if "daily" in sections and data["daily"]:
        el.append(Paragraph("Daily Complaints", sec))
        el.append(tbl([["Date", "Count"]] + [[d["date"], str(d["count"])] for d in data["daily"]], [320, 140]))
    doc.build(el)
    return buf.getvalue()


@router.post("/share-pdf")
async def share_pdf(body: dict, society_id: str = None, user: dict = Depends(require_society_admin)):
    sid = society_id or _sid(user)
    sections = body.get("sections") or ["summary", "categories", "resolution", "vendors"]
    start, end = body.get("start"), body.get("end")
    data = await reports(society_id=sid, start=start, end=end, user=user)
    soc = await db.societies.find_one({"_id": ObjectId(sid)})
    pdf = _build_pdf(soc, data, sections, start, end)
    gid = (soc.get("whatsapp_group") or {}).get("chat_id")
    if not gid:
        return {"status": "no_group", "group_configured": False, "sent_to_group": False}
    res = await wa.send_document(gid, base64.b64encode(pdf).decode(),
                                 f"Propto_Report_{datetime.now(timezone.utc).strftime('%Y%m%d')}.pdf",
                                 f"📊 {soc.get('name','Society')} report")
    return {"status": "ok", "group_configured": True, "sent_to_group": not res.get("error")}
