"""RQ Worker entrypoint."""

import logging
import os
import sys

from rq import Worker
from rq.job import Job

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import get_settings
from api.logging import setup_logging
from worker.redis import (
    QUEUE_DEFAULT,
    QUEUE_HIGH,
    QUEUE_LOW,
    get_redis_connection_bytes,
)


def on_job_start(job: Job) -> None:
    """Called when a job starts."""
    logging.info(
        f"Job started: {job.id} ({job.func_name})",
        extra={"job_id": job.id, "func": job.func_name},
    )


def on_job_success(job: Job, _connection: object, result: object) -> None:
    """Called when a job succeeds."""
    logging.info(
        f"Job completed: {job.id}",
        extra={"job_id": job.id, "result": str(result)[:100]},
    )


def on_job_failure(
    job: Job,
    _connection: object,
    _exc_type: type,
    exc_value: Exception,
    _traceback: object,
) -> None:
    """Called when a job fails."""
    logging.error(
        f"Job failed: {job.id} - {exc_value}",
        extra={"job_id": job.id, "error": str(exc_value)},
    )


def run_worker() -> None:
    """Start the RQ worker."""
    settings = get_settings()
    setup_logging()

    logging.info(
        "Starting worker",
        extra={
            "env": settings.env,
            "queues": [QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW],
        },
    )

    redis_conn = get_redis_connection_bytes()

    queues = [QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW]

    worker = Worker(
        queues,
        connection=redis_conn,
        name=f"findable-worker-{os.getpid()}",
    )

    worker.work(
        with_scheduler=True,
        logging_level=settings.log_level,
    )


if __name__ == "__main__":
    run_worker()
