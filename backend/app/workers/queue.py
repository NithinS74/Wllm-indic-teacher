"""Redis / RQ queue helpers.

When INLINE_JOBS=true (tests, or demos without Redis) tasks run
synchronously in the caller process — the API contract stays identical.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from app.core.config import settings

logger = logging.getLogger("lecturelens.queue")

_queue = None


def get_queue():
    global _queue
    if _queue is None:
        from redis import Redis
        from rq import Queue
        redis_conn = Redis.from_url(settings.redis_url)
        _queue = Queue(settings.rq_queue_name, connection=redis_conn)
    return _queue


def reset_queue() -> None:
    global _queue
    _queue = None


def enqueue(func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
    """Enqueue a background task; returns 'inline' id when running inline."""
    if settings.inline_jobs:
        logger.info("INLINE_JOBS=true — running %s synchronously",
                    getattr(func, "__name__", func))
        func(*args, **kwargs)
        return "inline"
    job = get_queue().enqueue(
        func, *args, **kwargs,
        job_timeout=settings.job_timeout_seconds,
        failure_ttl=7 * 24 * 3600,
        result_ttl=7 * 24 * 3600,
    )
    logger.info("Enqueued %s as rq-job %s",
                getattr(func, "__name__", func), job.id)
    return job.id
