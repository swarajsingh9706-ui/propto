"""PROPTO background worker (Redis queue consumer).

Run this as a persistent process on your VPS (systemd service — see DEPLOYMENT.md):
    python worker.py

It BRPOPLPUSHes jobs from the Redis queue and runs the full pipeline
(pre-filter -> Gemini complaint check -> 10k taxonomy -> Gemini ticket content
-> ticket creation). One process = one asyncio loop = one Motor client, so there
is no event-loop/DB conflict.
"""
import asyncio
import json
import logging

import redis.exceptions

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import task_queue
from routers.whatsapp_router import process_whapi, process_meta

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("propto.worker")


async def handle(job: dict):
    kind = job.get("kind")
    if kind == "whapi":
        await process_whapi(job.get("payload") or {}, job.get("method", "POST"))
    elif kind == "meta":
        await process_meta(job.get("payload") or {})
    else:
        logger.warning("unknown job kind: %s", kind)


async def main():
    r = await task_queue.get_redis()
    logger.info("PROPTO worker started; waiting for jobs on '%s'", task_queue.QUEUE_KEY)
    while True:
        try:
            item = await r.brpoplpush(task_queue.QUEUE_KEY, task_queue.PROCESSING_KEY, timeout=5)
        except (redis.exceptions.TimeoutError, redis.exceptions.ConnectionError) as e:
            logger.warning("redis read hiccup (%s); retrying", e)
            await asyncio.sleep(1)
            continue
        if item is None:
            continue
        try:
            await handle(json.loads(item))
        except Exception as e:
            logger.exception("job failed: %s", e)
        finally:
            await r.lrem(task_queue.PROCESSING_KEY, 1, item)


if __name__ == "__main__":
    asyncio.run(main())
