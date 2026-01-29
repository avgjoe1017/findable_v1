"""Job service for managing background jobs from the API."""

import uuid

from api.models import Run, Site
from worker.queue import JobInfo, JobQueue, QueuePriority, job_queue
from worker.tasks import run_audit_sync


class JobService:
    """Service for managing background jobs."""

    def __init__(self, queue: JobQueue | None = None):
        self._queue = queue or job_queue

    def enqueue_audit(
        self,
        run: Run,
        site: Site,
        priority: QueuePriority = QueuePriority.DEFAULT,
    ) -> str:
        """
        Enqueue an audit run job.

        Args:
            run: The Run record
            site: The Site record
            priority: Queue priority

        Returns:
            The job ID
        """
        job = self._queue.enqueue(
            run_audit_sync,
            str(run.id),
            str(site.id),
            priority=priority,
            job_id=f"audit-{run.id}",
            job_timeout=7200,  # 2 hours for full audit
            meta={
                "run_id": str(run.id),
                "site_id": str(site.id),
                "domain": site.domain,
                "run_type": run.run_type,
            },
        )

        return job.id  # type: ignore[no-any-return]

    def get_job_status(self, job_id: str) -> JobInfo | None:
        """Get status of a job by ID."""
        return self._queue.get_job_info(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a queued job."""
        return self._queue.cancel_job(job_id)

    def get_audit_job_id(self, run_id: uuid.UUID) -> str:
        """Get the job ID for an audit run."""
        return f"audit-{run_id}"

    def get_queue_stats(self) -> dict:
        """Get queue statistics."""
        return self._queue.get_queue_stats()


# Singleton instance
job_service = JobService()
