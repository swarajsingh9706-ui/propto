"""Redis-backed job queue (the Python equivalent of Redis+BullMQ).

The webhook LPUSHes a job and returns 200 instantly; a separate long-running
worker (worker.py) consumes jobs with a reliable BRPOPLPUSH pattern and runs the
OpenAI -> taxonomy -> ticket pipeline. If REDIS_URL is not set, callers fall back
to inline processing so the app still works without Redis.
"""
import os
import json
import logging

logger = logging.getLogger("propto.queue")

QUEUE_KEY = "propto:webhooks"
PROCESSING_KEY = "propto:webhooks:processing"
_redis = None


def redis_url():
    return os.environ.get("REDIS_URL")


def redis_enabled():
    return bool(redis_url())


async def get_redis():
    global _redis
    if _redis is None:
        import redis.asyncio as aioredis
        # socket_timeout=None so blocking BRPOPLPUSH (server-side timeout) doesn't trip
        # the client read timeout; health check keeps the connection alive.
        _redis = aioredis.from_url(
            redis_url(), encoding="utf-8", decode_responses=True,
            socket_timeout=None, socket_connect_timeout=10, health_check_interval=30,
        )
    return _redis


async def enqueue(job: dict):
    r = await get_redis()
    await r.lpush(QUEUE_KEY, json.dumps(job))
