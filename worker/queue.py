"""Job queue service for managing background jobs."""

import uuid
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from rq import Queue
from rq.job import Job

from worker.redis import (
    JOB_RESULT_TTL,
    QUEUE_DEFAULT,
    QUEUE_HIGH,
    QUEUE_LOW,
    get_redis_connection_bytes,
)


class JobStatus(str, Enum):
    """RQ job status values."""

    QUEUED = "queued"
    STARTED = "started"
    DEFERRED = "deferred"
    FINISHED = "finished"
    STOPPED = "stopped"
    SCHEDULED = "scheduled"
    FAILED = "failed"
    CANCELED = "canceled"


class QueuePriority(str, Enum):
    """Queue priority levels."""

    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"


@dataclass
class JobInfo:
    """Job information wrapper."""

    id: str
    status: JobStatus
    created_at: datetime | None
    started_at: datetime | None
    ended_at: datetime | None
    result: Any | None
    error: str | None
    meta: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "result": self.result,
            "error": self.error,
            "meta": self.meta,
        }


class JobQueue:
    """Service for managing RQ job queues."""

    def __init__(self) -> None:
        self._conn = get_redis_connection_bytes()
        self._queues = {
            QueuePriority.HIGH: Queue(QUEUE_HIGH, connection=self._conn),
            QueuePriority.DEFAULT: Queue(QUEUE_DEFAULT, connection=self._conn),
            QueuePriority.LOW: Queue(QUEUE_LOW, connection=self._conn),
        }

    def get_queue(self, priority: QueuePriority = QueuePriority.DEFAULT) -> Queue:
        """Get a queue by priority."""
        return self._queues[priority]

    def enqueue(
        self,
        func: Any,
        *args: Any,
        priority: QueuePriority = QueuePriority.DEFAULT,
        job_id: str | None = None,
        job_timeout: int = 3600,  # 1 hour default
        result_ttl: int = JOB_RESULT_TTL,
        meta: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> Job:
        """
        Enqueue a job for background processing.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            priority: Queue priority (high, default, low)
            job_id: Optional custom job ID
            job_timeout: Job timeout in seconds
            result_ttl: How long to keep results
            meta: Additional metadata to store with job
            **kwargs: Keyword arguments for the function

        Returns:
            The enqueued RQ Job
        """
        queue = self.get_queue(priority)

        job = queue.enqueue(
            func,
            *args,
            job_id=job_id or str(uuid.uuid4()),
            job_timeout=job_timeout,
            result_ttl=result_ttl,
            meta=meta or {},
            **kwargs,
        )

        return job

    def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        try:
            job = Job.fetch(job_id, connection=self._conn)
            return job
        except Exception:
            return None

    def get_job_info(self, job_id: str) -> JobInfo | None:
        """Get job information by ID."""
        job = self.get_job(job_id)
        if not job:
            return None

        status = JobStatus(job.get_status() or "queued")
        error = None

        if status == JobStatus.FAILED and job.exc_info:
            error = str(job.exc_info)

        return JobInfo(
            id=job.id,
            status=status,
            created_at=job.created_at,
            started_at=job.started_at,
            ended_at=job.ended_at,
            result=job.result if status == JobStatus.FINISHED else None,
            error=error,
            meta=job.meta or {},
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job."""
        job = self.get_job(job_id)
        if not job:
            return False

        status = job.get_status()
        if status in ("queued", "deferred", "scheduled"):
            job.cancel()
            return True
        return False

    def get_queue_stats(self) -> dict[str, Any]:
        """Get statistics for all queues."""
        stats = {}
        for priority, queue in self._queues.items():
            stats[priority.value] = {
                "name": queue.name,
                "count": len(queue),
                "started_jobs": queue.started_job_registry.count,
                "finished_jobs": queue.finished_job_registry.count,
                "failed_jobs": queue.failed_job_registry.count,
                "deferred_jobs": queue.deferred_job_registry.count,
                "scheduled_jobs": queue.scheduled_job_registry.count,
            }
        return stats


# Singleton instance
job_queue = JobQueue()
