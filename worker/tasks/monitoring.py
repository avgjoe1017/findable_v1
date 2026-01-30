"""Monitoring snapshot background tasks."""

import uuid
from datetime import UTC, datetime

import structlog
from rq import get_current_job
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from api.database import async_session_maker
from api.models import (
    MonitoringSchedule,
    Report,
    Run,
    RunStatus,
    RunType,
    Site,
    Snapshot,
    SnapshotTrigger,
)
from worker.scheduler import (
    calculate_next_run,
    get_frequency_for_plan,
    monitoring_scheduler,
)

logger = structlog.get_logger(__name__)


def run_snapshot_sync(
    site_id: str,
    trigger: str = SnapshotTrigger.SCHEDULED_WEEKLY.value,
    include_observation: bool = True,
    include_benchmark: bool = True,
) -> dict:
    """
    Synchronous wrapper for snapshot task.

    This is the entry point for RQ which requires sync functions.
    """
    import asyncio

    return asyncio.run(
        run_snapshot(
            uuid.UUID(site_id),
            trigger,
            include_observation,
            include_benchmark,
        )
    )


async def run_snapshot(
    site_id: uuid.UUID,
    trigger: str = SnapshotTrigger.SCHEDULED_WEEKLY.value,
    include_observation: bool = True,
    include_benchmark: bool = True,
) -> dict:
    """
    Run a monitoring snapshot for a site.

    This creates a new Run, executes the audit, creates a Snapshot record,
    and schedules the next snapshot.

    Args:
        site_id: The site to snapshot
        trigger: How the snapshot was triggered
        include_observation: Run real AI observation
        include_benchmark: Include competitor benchmark

    Returns:
        Dict with snapshot results
    """
    job = get_current_job()

    logger.info(
        "snapshot_started",
        site_id=str(site_id),
        trigger=trigger,
        job_id=job.id if job else None,
    )

    try:
        async with async_session_maker() as db:
            # Load site with user
            result = await db.execute(
                select(Site)
                .options(selectinload(Site.user))
                .where(Site.id == site_id)
            )
            site = result.scalar_one_or_none()

            if not site:
                raise ValueError(f"Site {site_id} not found")

            if not site.monitoring_enabled:
                logger.info("monitoring_disabled", site_id=str(site_id))
                return {"status": "skipped", "reason": "monitoring_disabled"}

            # Get previous snapshot for comparison
            prev_snapshot_result = await db.execute(
                select(Snapshot)
                .where(Snapshot.site_id == site_id)
                .order_by(Snapshot.snapshot_at.desc())
                .limit(1)
            )
            prev_snapshot = prev_snapshot_result.scalar_one_or_none()

            # Create a new run for this snapshot
            run = Run(
                site_id=site_id,
                run_type=RunType.SNAPSHOT.value,
                status=RunStatus.QUEUED.value,
                config={
                    "include_observation": include_observation,
                    "include_benchmark": include_benchmark,
                    "trigger": trigger,
                },
            )
            db.add(run)
            await db.commit()
            await db.refresh(run)
            run_id = run.id

        # Execute the audit
        # Import here to avoid circular imports
        from worker.tasks.audit import run_audit

        result = await run_audit(run_id, site_id)

        if result["status"] != "complete":
            raise RuntimeError(f"Audit failed: {result.get('error', 'Unknown error')}")

        report_id = uuid.UUID(result["report_id"])

        # Create snapshot record
        async with async_session_maker() as db:
            # Get the report
            report_result = await db.execute(
                select(Report).where(Report.id == report_id)
            )
            report = report_result.scalar_one()

            # Calculate deltas from previous snapshot
            score_delta = None
            mention_rate_delta = None
            changes = None

            if prev_snapshot and prev_snapshot.score_typical is not None:
                if report.score_typical is not None:
                    score_delta = report.score_typical - prev_snapshot.score_typical

                if (
                    report.mention_rate is not None
                    and prev_snapshot.mention_rate is not None
                ):
                    mention_rate_delta = (
                        report.mention_rate - prev_snapshot.mention_rate
                    )

                # Build changes summary
                changes = {
                    "score_improved": (score_delta or 0) > 0,
                    "score_delta": score_delta,
                    "mention_rate_improved": (mention_rate_delta or 0) > 0,
                    "mention_rate_delta": mention_rate_delta,
                }

            # Extract category scores from report data
            category_scores = None
            if report.data and "categories" in report.data:
                category_scores = {
                    cat["name"]: cat.get("score")
                    for cat in report.data["categories"]
                    if "name" in cat and "score" in cat
                }

            # Extract benchmark data
            benchmark_data = None
            if report.data and "benchmark" in report.data:
                benchmark_data = report.data["benchmark"]

            # Create snapshot
            snapshot = Snapshot(
                site_id=site_id,
                run_id=run_id,
                report_id=report_id,
                trigger=trigger,
                score_conservative=report.score_conservative,
                score_typical=report.score_typical,
                score_generous=report.score_generous,
                mention_rate=report.mention_rate,
                score_delta=score_delta,
                mention_rate_delta=mention_rate_delta,
                category_scores=category_scores,
                benchmark_data=benchmark_data,
                changes=changes,
            )
            db.add(snapshot)

            # Update monitoring schedule
            schedule_result = await db.execute(
                select(MonitoringSchedule).where(
                    MonitoringSchedule.site_id == site_id
                )
            )
            schedule = schedule_result.scalar_one_or_none()

            if schedule:
                schedule.last_run_at = datetime.now(UTC)
                schedule.last_run_status = "complete"

                # Calculate and set next run
                site_result = await db.execute(
                    select(Site)
                    .options(selectinload(Site.user))
                    .where(Site.id == site_id)
                )
                site = site_result.scalar_one()
                frequency = get_frequency_for_plan(site.user.plan)

                schedule.next_run_at = calculate_next_run(
                    frequency,
                    schedule.day_of_week,
                    schedule.hour,
                )

            # Update site's next_snapshot_at
            site_result = await db.execute(
                select(Site).where(Site.id == site_id)
            )
            site = site_result.scalar_one()
            if schedule:
                site.next_snapshot_at = schedule.next_run_at

            await db.commit()
            snapshot_id = snapshot.id

        # Schedule next snapshot
        async with async_session_maker() as db:
            site_result = await db.execute(
                select(Site)
                .options(selectinload(Site.user))
                .where(Site.id == site_id)
            )
            site = site_result.scalar_one()

            schedule_result = await db.execute(
                select(MonitoringSchedule).where(
                    MonitoringSchedule.site_id == site_id
                )
            )
            schedule = schedule_result.scalar_one_or_none()

            if site.monitoring_enabled and schedule:
                new_job = monitoring_scheduler.schedule_snapshot(
                    site_id=site_id,
                    user_plan=site.user.plan,
                    run_at=schedule.next_run_at,
                    day_of_week=schedule.day_of_week,
                    hour=schedule.hour,
                    include_observation=schedule.include_observation,
                    include_benchmark=schedule.include_benchmark,
                )
                schedule.scheduler_job_id = new_job.id
                await db.commit()

        # Check for alerts
        try:
            from api.services.alert_service import AlertService

            async with async_session_maker() as alert_db:
                alert_service = AlertService(alert_db)
                alerts_created = await alert_service.check_snapshot_alerts(
                    snapshot=snapshot,
                    previous_snapshot=prev_snapshot,
                )
                await alert_db.commit()

                if alerts_created:
                    logger.info(
                        "alerts_created",
                        site_id=str(site_id),
                        alert_count=len(alerts_created),
                        alert_types=[a.alert_type for a in alerts_created],
                    )
        except Exception as alert_error:
            logger.warning(
                "alert_check_failed",
                site_id=str(site_id),
                error=str(alert_error),
            )

        logger.info(
            "snapshot_completed",
            site_id=str(site_id),
            snapshot_id=str(snapshot_id),
            run_id=str(run_id),
            report_id=str(report_id),
            score_delta=score_delta,
        )

        return {
            "status": "complete",
            "snapshot_id": str(snapshot_id),
            "run_id": str(run_id),
            "report_id": str(report_id),
            "score_typical": report.score_typical,
            "score_delta": score_delta,
        }

    except Exception as e:
        logger.exception(
            "snapshot_failed",
            site_id=str(site_id),
            error=str(e),
        )

        # Update schedule with failure status
        try:
            async with async_session_maker() as db:
                schedule_result = await db.execute(
                    select(MonitoringSchedule).where(
                        MonitoringSchedule.site_id == site_id
                    )
                )
                schedule = schedule_result.scalar_one_or_none()

                if schedule:
                    schedule.last_run_at = datetime.now(UTC)
                    schedule.last_run_status = "failed"
                    await db.commit()

                # Create failed snapshot alert
                from api.services.alert_service import AlertService

                alert_service = AlertService(db)
                await alert_service.create_snapshot_failed_alert(
                    site_id=site_id,
                    error_message=str(e),
                )
                await db.commit()
        except Exception:
            pass  # Don't fail the job just because we couldn't update status

        raise


async def enable_monitoring(
    site_id: uuid.UUID,
    day_of_week: int = 0,
    hour: int = 6,
    include_observation: bool = True,
    include_benchmark: bool = True,
) -> dict:
    """
    Enable monitoring for a site.

    Creates a MonitoringSchedule and schedules the first snapshot.

    Args:
        site_id: The site to enable monitoring for
        day_of_week: Preferred day (0=Monday)
        hour: Preferred hour (UTC)
        include_observation: Include AI observation in snapshots
        include_benchmark: Include competitor benchmark

    Returns:
        Dict with schedule info
    """
    async with async_session_maker() as db:
        # Load site with user
        result = await db.execute(
            select(Site)
            .options(selectinload(Site.user))
            .where(Site.id == site_id)
        )
        site = result.scalar_one_or_none()

        if not site:
            raise ValueError(f"Site {site_id} not found")

        # Get frequency based on plan
        frequency = get_frequency_for_plan(site.user.plan)
        next_run = calculate_next_run(
            frequency,
            day_of_week,
            hour,
        )

        # Create or update schedule
        schedule_result = await db.execute(
            select(MonitoringSchedule).where(MonitoringSchedule.site_id == site_id)
        )
        schedule = schedule_result.scalar_one_or_none()

        if schedule:
            # Update existing
            schedule.frequency = frequency.value
            schedule.day_of_week = day_of_week
            schedule.hour = hour
            schedule.include_observation = include_observation
            schedule.include_benchmark = include_benchmark
            schedule.next_run_at = next_run
        else:
            # Create new
            schedule = MonitoringSchedule(
                site_id=site_id,
                frequency=frequency.value,
                day_of_week=day_of_week,
                hour=hour,
                include_observation=include_observation,
                include_benchmark=include_benchmark,
                next_run_at=next_run,
            )
            db.add(schedule)

        # Enable on site
        site.monitoring_enabled = True
        site.next_snapshot_at = next_run

        await db.commit()
        await db.refresh(schedule)

        # Schedule the job
        job = monitoring_scheduler.schedule_snapshot(
            site_id=site_id,
            user_plan=site.user.plan,
            run_at=next_run,
            day_of_week=day_of_week,
            hour=hour,
            include_observation=include_observation,
            include_benchmark=include_benchmark,
        )

        # Save job ID
        schedule.scheduler_job_id = job.id
        await db.commit()

        logger.info(
            "monitoring_enabled",
            site_id=str(site_id),
            frequency=frequency.value,
            next_run=next_run.isoformat(),
            job_id=job.id,
        )

        return {
            "schedule_id": str(schedule.id),
            "frequency": frequency.value,
            "next_run_at": next_run.isoformat(),
            "job_id": job.id,
        }


async def disable_monitoring(site_id: uuid.UUID) -> dict:
    """
    Disable monitoring for a site.

    Cancels scheduled jobs and removes the schedule.

    Args:
        site_id: The site to disable monitoring for

    Returns:
        Dict with result info
    """
    async with async_session_maker() as db:
        # Get schedule
        schedule_result = await db.execute(
            select(MonitoringSchedule).where(MonitoringSchedule.site_id == site_id)
        )
        schedule = schedule_result.scalar_one_or_none()

        # Cancel scheduled job
        if schedule and schedule.scheduler_job_id:
            monitoring_scheduler.cancel_scheduled_snapshot(schedule.scheduler_job_id)

        # Delete schedule
        if schedule:
            await db.delete(schedule)

        # Disable on site
        site_result = await db.execute(select(Site).where(Site.id == site_id))
        site = site_result.scalar_one_or_none()

        if site:
            site.monitoring_enabled = False
            site.next_snapshot_at = None

        await db.commit()

        logger.info("monitoring_disabled", site_id=str(site_id))

        return {"status": "disabled", "site_id": str(site_id)}


async def get_snapshots(
    site_id: uuid.UUID,
    limit: int = 12,
    offset: int = 0,
) -> list[Snapshot]:
    """
    Get snapshots for a site.

    Args:
        site_id: The site to get snapshots for
        limit: Maximum number to return
        offset: Pagination offset

    Returns:
        List of Snapshot records
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(Snapshot)
            .where(Snapshot.site_id == site_id)
            .order_by(Snapshot.snapshot_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
