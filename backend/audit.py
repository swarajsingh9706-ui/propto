import logging
from db import db
from models import now_iso

logger = logging.getLogger("propto.audit")


async def log(society_id, action, summary, actor="System", category="general",
              ticket_number=None, meta=None):
    """Best-effort audit trail. Never raises so it can't break core flows."""
    if not society_id:
        return
    try:
        await db.audit_logs.insert_one({
            "society_id": str(society_id),
            "category": category,
            "action": action,
            "summary": summary,
            "actor": actor,
            "ticket_number": ticket_number,
            "meta": meta or {},
            "created_at": now_iso(),
        })
    except Exception as e:
        logger.warning("audit log failed: %s", e)
