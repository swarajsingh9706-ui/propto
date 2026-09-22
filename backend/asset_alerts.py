import logging
from datetime import datetime, timezone, date
from bson import ObjectId

from db import db
import whatsapp_client as wa

logger = logging.getLogger("propto.asset_alerts")

MANAGER_ROLES = ["Secretary", "Manager", "Chairman"]


def _parse(s):
    try:
        return date.fromisoformat(str(s)[:10])
    except Exception:
        return None


async def _manager_phone(sid: str):
    m = await db.committee.find_one({"society_id": sid, "role": {"$in": MANAGER_ROLES}})
    return (m or {}).get("phone")


async def run_asset_alerts():
    """Daily: WhatsApp reminders for assets whose service is due/overdue.
    Recipients = assigned vendor + escalation matrix contacts; if no matrix, vendor + society manager.
    Fires once per service cycle (deduped via last_alert_date == next_service)."""
    today = datetime.now(timezone.utc).date()
    societies = await db.societies.find({}).to_list(1000)
    sent = 0
    for soc in societies:
        sid = str(soc["_id"])
        matrix = soc.get("escalation_matrix") or []
        manager = None
        assets = await db.assets.find({"society_id": sid}).to_list(1000)
        for a in assets:
            ns = _parse(a.get("next_service"))
            if not ns or ns > today:
                continue
            if a.get("last_alert_date") == a.get("next_service"):
                continue  # already alerted for this cycle

            phones = []
            if a.get("vendor_id"):
                try:
                    v = await db.vendors.find_one({"_id": ObjectId(a["vendor_id"])})
                    if v and v.get("phone"):
                        phones.append(v["phone"])
                except Exception:
                    pass
            if matrix:
                phones += [m["phone"] for m in matrix if m.get("phone")]
            else:
                if manager is None:
                    manager = await _manager_phone(sid)
                if manager:
                    phones.append(manager)
            phones = list(dict.fromkeys([p for p in phones if p]))  # unique, preserve order
            if not phones:
                logger.info("asset %s due but no recipients (society %s)", a.get("name"), sid)
                await db.assets.update_one({"_id": a["_id"]}, {"$set": {"last_alert_date": a.get("next_service")}})
                continue

            overdue = ns < today
            state = "is OVERDUE" if overdue else "is due today"
            msg = (
                f"🔧 *Asset Service Reminder*\n"
                f"{a.get('name')} ({a.get('type') or 'Asset'}) service {state} ({a.get('next_service')}).\n"
                f"Location: {a.get('location') or '—'}\n"
                f"Please schedule/complete the service and update the Propto dashboard."
            )
            for p in phones:
                try:
                    await wa.send_text(p, msg)
                    sent += 1
                except Exception as e:
                    logger.warning("asset alert send failed to %s: %s", p, e)
            await db.assets.update_one({"_id": a["_id"]}, {"$set": {"last_alert_date": a.get("next_service")}})
    logger.info("asset alerts run complete: %d messages", sent)
    return {"messages_sent": sent}
