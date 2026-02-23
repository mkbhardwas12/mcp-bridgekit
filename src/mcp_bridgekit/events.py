"""SSE push notifications for background job completion.

Uses Redis Pub/Sub so the RQ worker (separate process) can signal connected
SSE clients held open in the FastAPI process — no shared in-process state needed.
"""
import json
from typing import AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from .config import settings

logger = structlog.get_logger()
router = APIRouter()


@router.get("/events/{job_id}", summary="SSE stream — fires once when job completes")
async def sse_job_events(job_id: str):
    """
    Server-Sent Events endpoint.  Connect before (or just after) submitting a long
    job; receives a single ``data:`` event when the background worker finishes, then
    closes the stream automatically.

    No auth required (job_id acts as a capability token).
    """
    return EventSourceResponse(_job_event_generator(job_id))


async def _job_event_generator(job_id: str) -> AsyncGenerator[dict, None]:
    channel = f"bridgekit:events:{job_id}"
    redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    logger.info("SSE client subscribed", job_id=job_id, channel=channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                yield {"data": message["data"]}
                break  # one-shot: close after the first (completion) event
    finally:
        await pubsub.unsubscribe(channel)
        await redis.aclose()
        logger.info("SSE client disconnected", job_id=job_id)
