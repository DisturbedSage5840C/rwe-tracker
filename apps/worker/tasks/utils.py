"""Shared worker task utilities for DB sessions, retries, and progress updates."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

import redis.asyncio as redis
from tenacity import retry, stop_after_attempt, wait_exponential

from apps.api.config import get_settings
from apps.api.db import SessionLocal

settings = get_settings()
_worker_loop: asyncio.AbstractEventLoop | None = None


@asynccontextmanager
async def db_session():
    """Yield async DB session for worker tasks."""
    async with SessionLocal() as session:
        yield session


async def set_job_progress(task_id: str, progress: int) -> None:
    """Persist task progress in Redis for polling endpoints."""
    client = redis.from_url(settings.redis_url, decode_responses=True)
    await client.set(f"job:{task_id}:progress", str(progress))
    await client.close()


async def set_job_result(task_id: str, payload: dict, ttl_seconds: int = 86400) -> None:
    """Persist final job result payload with expiration TTL."""
    client = redis.from_url(settings.redis_url, decode_responses=True)
    await client.set(f"job:{task_id}:result", str(payload), ex=ttl_seconds)
    await client.close()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), reraise=True)
async def with_retry(func, *args, **kwargs):
    """Execute async call with bounded retry/backoff policy."""
    return await func(*args, **kwargs)


def run_async(coro):
    """Run coroutine in Celery sync context using a process-local loop."""
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()

    asyncio.set_event_loop(_worker_loop)
    return _worker_loop.run_until_complete(coro)
