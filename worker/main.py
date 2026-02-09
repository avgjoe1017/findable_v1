"""RQ Worker entrypoint."""

import logging
import os
import platform
import sys

from rq import SimpleWorker, Worker
from rq.job import Job

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.config import get_settings  # noqa: E402
from api.logging import setup_logging  # noqa: E402
from worker.redis import (  # noqa: E402
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

    # Load active calibration config for dynamic weights/thresholds
    if settings.calibration_enabled:
        try:
            import asyncio

            from worker.scoring.calculator_v2 import load_active_calibration_weights

            weights = asyncio.run(load_active_calibration_weights())
            logging.info(
                "Calibration config loaded",
                extra={"weights": weights},
            )
        except Exception as e:
            logging.warning(f"Failed to load calibration config, using defaults: {e}")

    # Initialize calibration schedules (drift detection)
    try:
        from worker.scheduler import ensure_calibration_schedules

        schedule_status = ensure_calibration_schedules()
        logging.info(
            "Calibration schedules initialized",
            extra=schedule_status,
        )
    except Exception as e:
        logging.warning(f"Failed to initialize calibration schedules: {e}")

    queues = [QUEUE_HIGH, QUEUE_DEFAULT, QUEUE_LOW]

    # Use SimpleWorker on Windows (no os.fork() support)
    WorkerClass = SimpleWorker if platform.system() == "Windows" else Worker

    worker = WorkerClass(
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
