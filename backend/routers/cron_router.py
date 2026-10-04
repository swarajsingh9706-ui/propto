import os
import hmac
import asyncio
import logging
from fastapi import APIRouter, Header, HTTPException

import asset_alerts
import pipeline

logger = logging.getLogger("propto.cron")
router = APIRouter(prefix="/api/cron", tags=["cron"])


def _authorized(authorization: str) -> bool:
    secret = os.environ.get("WEBHOOK_CRON_SECRET") or ""
    token = (authorization or "").replace("Bearer ", "").strip()
    return bool(secret) and hmac.compare_digest(token, secret)


@router.post("/asset-alerts")
async def asset_alerts_cron(authorization: str = Header(None)):
    # Cron endpoints must ack 2xx immediately; enqueue/background the actual work.
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="unauthorized")
    asyncio.create_task(asset_alerts.run_asset_alerts())
    return {"status": "accepted"}


@router.post("/vendor-timeouts")
async def vendor_timeouts_cron(authorization: str = Header(None)):
    # Reassign un-accepted tickets to the Society Manager past the vendor response window.
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="unauthorized")
    asyncio.create_task(pipeline.check_vendor_timeouts())
    return {"status": "accepted"}
