"""Monitoring and calibration scheduler using rq-scheduler for periodic jobs.

This module provides:
- Scheduler service for managing periodic monitoring jobs
- Schedule calculation for weekly/monthly snapshots
- Plan-aware scheduling (Starter=monthly, Professional/Agency=weekly)
- Daily calibration drift detection scheduling
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import TYPE_CHECKING

import structlog
from rq_scheduler import Scheduler

from api.config import get_settings
from api.models.user import PlanTier
from worker.redis import QUEUE_LOW, get_redis_connection_bytes

if TYPE_CHECKING:
    from rq.job import Job

logger = structlog.get_logger(__name__)


class ScheduleFrequency(str, Enum):
    """Schedule frequency options."""

    WEEKLY = "weekly"
    MONTHLY = "monthly"


# Plan to frequency mapping
PLAN_FREQUENCIES: dict[str, ScheduleFrequency] = {
    PlanTier.STARTER.value: ScheduleFrequency.MONTHLY,
    PlanTier.PROFESSIONAL.value: ScheduleFrequency.WEEKLY,
    PlanTier.AGENCY.value: ScheduleFrequency.WEEKLY,
}

# Default schedule times (UTC)
DEFAULT_HOUR = 6  # 6 AM UTC
DEFAULT_DAY_OF_WEEK = 0  # Monday


def get_scheduler() -> Scheduler:
    """Get a scheduler instance connected to Redis."""
    conn = get_redis_connection_bytes()
    return Scheduler(queue_name=QUEUE_LOW, connection=conn)


def calculate_next_run(
    frequency: ScheduleFrequency,
    day_of_week: int = DEFAULT_DAY_OF_WEEK,
    hour: int = DEFAULT_HOUR,
    from_time: datetime | None = None,
) -> datetime:
    """
    Calculate the next scheduled run time.

    Args:
        frequency: Weekly or monthly
        day_of_week: Day of week (0=Monday, 6=Sunday) for weekly
        hour: Hour of day (UTC)
        from_time: Calculate from this time (defaults to now)

    Returns:
        The next scheduled run datetime (UTC)
    """
    now = from_time or datetime.now(UTC)

    if frequency == ScheduleFrequency.WEEKLY:
        # Find next occurrence of day_of_week at specified hour
        days_ahead = day_of_week - now.weekday()
        if days_ahead < 0:  # Target day already happened this week
            days_ahead += 7
        elif days_ahead == 0 and now.hour >= hour:  # Today but already passed
            days_ahead = 7

        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0) + timedelta(
            days=days_ahead
        )

    else:  # MONTHLY
        # First occurrence of day_of_week in next month
        if now.month == 12:
            next_month = now.replace(year=now.year + 1, month=1, day=1)
        else:
            next_month = now.replace(month=now.month + 1, day=1)

        # Find first day_of_week in next month
        days_until_target = (day_of_week - next_month.weekday()) % 7
        next_run = next_month + timedelta(days=days_until_target)
        next_run = next_run.replace(hour=hour, minute=0, second=0, microsecond=0)

    return next_run


def get_frequency_for_plan(plan: str) -> ScheduleFrequency:
    """Get the appropriate frequency for a plan tier."""
    return PLAN_FREQUENCIES.get(plan, ScheduleFrequency.MONTHLY)


class MonitoringScheduler:
    """Service for managing monitoring schedules."""

    def __init__(self) -> None:
        self._scheduler = get_scheduler()
        self._settings = get_settings()

    @property
    def scheduler(self) -> Scheduler:
        """Get the underlying rq-scheduler instance."""
        return self._scheduler

    def schedule_snapshot(
        self,
        site_id: uuid.UUID,
        user_plan: str,
        run_at: datetime | None = None,
        day_of_week: int = DEFAULT_DAY_OF_WEEK,
        hour: int = DEFAULT_HOUR,
        include_observation: bool = True,
        include_benchmark: bool = True,
    ) -> Job:
        """
        Schedule a snapshot job for a site.

        Args:
            site_id: The site to snapshot
            user_plan: The user's plan tier
            run_at: When to run (if None, calculates from plan frequency)
            day_of_week: Preferred day (0=Monday)
            hour: Preferred hour (UTC)
            include_observation: Run real AI observation
            include_benchmark: Include competitor benchmark

        Returns:
            The scheduled RQ job
        """
        from worker.tasks.monitoring import run_snapshot_sync

        frequency = get_frequency_for_plan(user_plan)

        if run_at is None:
            run_at = calculate_next_run(frequency, day_of_week, hour)

        job_id = f"snapshot_{site_id}_{run_at.isoformat()}"

        job = self._scheduler.enqueue_at(
            run_at,
            run_snapshot_sync,
            str(site_id),
            frequency.value,
            include_observation,
            include_benchmark,
            job_id=job_id,
            job_timeout=3600,  # 1 hour
            meta={
                "site_id": str(site_id),
                "scheduled_at": datetime.now(UTC).isoformat(),
                "run_at": run_at.isoformat(),
                "frequency": frequency.value,
            },
        )

        logger.info(
            "snapshot_scheduled",
            site_id=str(site_id),
            job_id=job.id,
            run_at=run_at.isoformat(),
            frequency=frequency.value,
        )

        return job

    def cancel_scheduled_snapshot(self, job_id: str) -> bool:
        """
        Cancel a scheduled snapshot job.

        Args:
            job_id: The job ID to cancel

        Returns:
            True if cancelled, False if not found
        """
        try:
            # Get all scheduled jobs and find the one to cancel
            for job in self._scheduler.get_jobs():
                if job.id == job_id:
                    self._scheduler.cancel(job)
                    logger.info("snapshot_cancelled", job_id=job_id)
                    return True
            return False
        except Exception as e:
            logger.error("cancel_failed", job_id=job_id, error=str(e))
            return False

    def get_scheduled_jobs(self, site_id: uuid.UUID | None = None) -> list[dict]:
        """
        Get all scheduled monitoring jobs.

        Args:
            site_id: Filter by site ID (optional)

        Returns:
            List of job info dictionaries
        """
        jobs = []
        for job in self._scheduler.get_jobs():
            meta = job.meta or {}
            job_site_id = meta.get("site_id")

            if site_id and job_site_id != str(site_id):
                continue

            jobs.append(
                {
                    "job_id": job.id,
                    "site_id": job_site_id,
                    "run_at": meta.get("run_at"),
                    "scheduled_at": meta.get("scheduled_at"),
                    "frequency": meta.get("frequency"),
                    "func_name": job.func_name if hasattr(job, "func_name") else None,
                }
            )

        return jobs

    def reschedule_site(
        self,
        site_id: uuid.UUID,
        user_plan: str,
        old_job_id: str | None = None,
        day_of_week: int = DEFAULT_DAY_OF_WEEK,
        hour: int = DEFAULT_HOUR,
        include_observation: bool = True,
        include_benchmark: bool = True,
    ) -> Job:
        """
        Reschedule a site's monitoring (e.g., after plan change).

        Args:
            site_id: The site to reschedule
            user_plan: The user's (possibly new) plan tier
            old_job_id: The old job ID to cancel
            day_of_week: Preferred day of week
            hour: Preferred hour (UTC)
            include_observation: Run real AI observation
            include_benchmark: Include competitor benchmark

        Returns:
            The new scheduled job
        """
        # Cancel old job if exists
        if old_job_id:
            self.cancel_scheduled_snapshot(old_job_id)

        # Schedule new job with appropriate frequency
        return self.schedule_snapshot(
            site_id=site_id,
            user_plan=user_plan,
            day_of_week=day_of_week,
            hour=hour,
            include_observation=include_observation,
            include_benchmark=include_benchmark,
        )


def run_scheduler_tick() -> int:
    """
    Process due jobs in the scheduler.

    This should be called periodically (e.g., every minute) by a cron job
    or the scheduler process.

    Returns:
        Number of jobs enqueued
    """
    scheduler = get_scheduler()
    count = scheduler.run(burst=True)
    if count:
        logger.info("scheduler_tick", jobs_enqueued=count)
    return count or 0


# ============================================================================
# Calibration Drift Detection Scheduling
# ============================================================================


# Default calibration check time (4 AM UTC - off-peak)
DEFAULT_CALIBRATION_HOUR = 4


def run_calibration_drift_check_sync() -> dict:
    """
    Synchronous wrapper for calibration drift check.

    Called by rq-scheduler as a background job.

    Returns:
        Dict with results including alerts created
    """
    import asyncio

    from worker.tasks.calibration import check_calibration_drift

    settings = get_settings()

    # Skip if drift checking is disabled
    if not settings.calibration_drift_check_enabled:
        logger.info("calibration_drift_check_disabled")
        return {"status": "disabled", "alerts_created": 0}

    try:
        # Run the async drift check
        alerts = asyncio.run(
            check_calibration_drift(
                accuracy_threshold=settings.calibration_drift_threshold_accuracy,
                bias_threshold=settings.calibration_drift_threshold_bias,
                min_samples=settings.calibration_min_samples_for_analysis
                // 2,  # Lower bar for drift
            )
        )

        result = {
            "status": "completed",
            "alerts_created": len(alerts),
            "alert_types": [a.drift_type for a in alerts] if alerts else [],
        }

        logger.info("calibration_drift_check_completed", **result)
        return result

    except Exception as e:
        logger.error("calibration_drift_check_failed", error=str(e))
        return {"status": "error", "error": str(e), "alerts_created": 0}


class CalibrationScheduler:
    """Service for managing calibration-related scheduled jobs."""

    DRIFT_CHECK_JOB_ID = "calibration_drift_check_daily"

    def __init__(self) -> None:
        self._scheduler = get_scheduler()
        self._settings = get_settings()

    @property
    def scheduler(self) -> Scheduler:
        """Get the underlying rq-scheduler instance."""
        return self._scheduler

    def schedule_daily_drift_check(
        self,
        hour: int = DEFAULT_CALIBRATION_HOUR,
        minute: int = 0,
    ) -> Job | None:
        """
        Schedule a daily calibration drift check.

        Args:
            hour: Hour of day to run (UTC)
            minute: Minute of hour to run

        Returns:
            The scheduled job, or None if drift checking is disabled
        """
        if not self._settings.calibration_drift_check_enabled:
            logger.info("drift_check_scheduling_skipped_disabled")
            return None

        # Cancel any existing drift check job
        self.cancel_drift_check()

        # Calculate next run time
        now = datetime.now(UTC)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

        # If today's time has passed, schedule for tomorrow
        if next_run <= now:
            next_run += timedelta(days=1)

        job = self._scheduler.schedule(
            scheduled_time=next_run,
            func=run_calibration_drift_check_sync,
            interval=86400,  # 24 hours in seconds
            repeat=None,  # Repeat indefinitely
            id=self.DRIFT_CHECK_JOB_ID,
            job_timeout=1800,  # 30 minutes
            meta={
                "type": "calibration_drift_check",
                "scheduled_at": datetime.now(UTC).isoformat(),
                "interval": "daily",
            },
        )

        logger.info(
            "drift_check_scheduled",
            job_id=job.id,
            next_run=next_run.isoformat(),
            hour=hour,
            minute=minute,
        )

        return job

    def cancel_drift_check(self) -> bool:
        """
        Cancel the scheduled drift check job.

        Returns:
            True if cancelled, False if not found
        """
        try:
            for job in self._scheduler.get_jobs():
                if job.id == self.DRIFT_CHECK_JOB_ID:
                    self._scheduler.cancel(job)
                    logger.info("drift_check_cancelled", job_id=job.id)
                    return True
            return False
        except Exception as e:
            logger.error("drift_check_cancel_failed", error=str(e))
            return False

    def get_drift_check_status(self) -> dict | None:
        """
        Get status of the scheduled drift check job.

        Returns:
            Job info dict or None if not scheduled
        """
        try:
            for job in self._scheduler.get_jobs():
                if job.id == self.DRIFT_CHECK_JOB_ID:
                    meta = job.meta or {}
                    return {
                        "job_id": job.id,
                        "scheduled_at": meta.get("scheduled_at"),
                        "interval": meta.get("interval"),
                        "type": meta.get("type"),
                        "next_run": (
                            job.to_dict().get("scheduled_time") if hasattr(job, "to_dict") else None
                        ),
                    }
            return None
        except Exception as e:
            logger.error("drift_check_status_failed", error=str(e))
            return None

    def run_drift_check_now(self) -> Job:
        """
        Enqueue a drift check to run immediately.

        Returns:
            The enqueued job
        """
        job = self._scheduler.enqueue_at(
            datetime.now(UTC),
            run_calibration_drift_check_sync,
            job_id=f"drift_check_manual_{datetime.now(UTC).isoformat()}",
            job_timeout=1800,
            meta={
                "type": "calibration_drift_check",
                "trigger": "manual",
                "scheduled_at": datetime.now(UTC).isoformat(),
            },
        )

        logger.info("drift_check_enqueued_manually", job_id=job.id)
        return job


def ensure_calibration_schedules() -> dict:
    """
    Ensure all calibration-related schedules are in place.

    Call this at startup to initialize schedules.

    Returns:
        Dict with schedule status
    """
    scheduler = CalibrationScheduler()
    settings = get_settings()

    result = {
        "drift_check_enabled": settings.calibration_drift_check_enabled,
        "drift_check_scheduled": False,
    }

    if settings.calibration_drift_check_enabled:
        # Check if already scheduled
        status = scheduler.get_drift_check_status()
        if status:
            result["drift_check_scheduled"] = True
            result["drift_check_job_id"] = status["job_id"]
        else:
            # Schedule it
            job = scheduler.schedule_daily_drift_check()
            if job:
                result["drift_check_scheduled"] = True
                result["drift_check_job_id"] = job.id

    logger.info("calibration_schedules_ensured", **result)
    return result


# Singleton instances
monitoring_scheduler = MonitoringScheduler()
calibration_scheduler = CalibrationScheduler()
