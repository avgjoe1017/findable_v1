"""Findable Score Analyzer - Worker Package."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when these are needed:
# from worker.queue import JobQueue, job_queue, JobInfo, JobStatus, QueuePriority
# from worker.redis import get_redis_connection, QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW
# from worker.crawler import Crawler, CrawlConfig, crawl_site

__all__ = [
    "JobQueue",
    "JobInfo",
    "JobStatus",
    "QueuePriority",
    "job_queue",
    "get_redis_connection",
    "get_redis_connection_bytes",
    "QUEUE_HIGH",
    "QUEUE_DEFAULT",
    "QUEUE_LOW",
]


from typing import Any


def __getattr__(name: str) -> Any:
    """Lazy import for worker submodules."""
    if name in ("JobQueue", "JobInfo", "JobStatus", "QueuePriority", "job_queue"):
        from worker.queue import JobInfo, JobQueue, JobStatus, QueuePriority, job_queue

        return locals()[name]
    elif name in (
        "get_redis_connection",
        "get_redis_connection_bytes",
        "QUEUE_HIGH",
        "QUEUE_DEFAULT",
        "QUEUE_LOW",
    ):
        from worker.redis import (
            QUEUE_DEFAULT,
            QUEUE_HIGH,
            QUEUE_LOW,
            get_redis_connection,
            get_redis_connection_bytes,
        )

        return locals()[name]
    raise AttributeError(f"module 'worker' has no attribute '{name}'")
