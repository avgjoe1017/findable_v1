"""Monitoring endpoints for scheduled snapshots and trends."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from api.auth import CurrentUser
from api.database import DbSession
from api.models import MonitoringSchedule, Snapshot
from api.schemas.monitoring import (
    MonitoringEnableRequest,
    MonitoringScheduleResponse,
    MonitoringStatusResponse,
    ScheduledJobResponse,
    SchedulerStatsResponse,
    ScoreTrendPoint,
    ScoreTrendResponse,
    SnapshotListResponse,
    SnapshotResponse,
)
from api.schemas.responses import SuccessResponse
from api.services import site_service
from worker.scheduler import monitoring_scheduler
from worker.tasks.monitoring import (
    disable_monitoring,
    enable_monitoring,
    run_snapshot,
)

router = APIRouter(prefix="/sites/{site_id}/monitoring", tags=["monitoring"])


@router.post(
    "",
    response_model=SuccessResponse[MonitoringScheduleResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Enable monitoring for a site",
)
async def enable_site_monitoring(
    site_id: uuid.UUID,
    request: MonitoringEnableRequest,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[MonitoringScheduleResponse]:
    """
    Enable periodic monitoring for a site.

    - Creates a monitoring schedule
    - Schedules the first snapshot based on user's plan
    - Starter plans get monthly snapshots
    - Professional and Agency plans get weekly snapshots
    """
    # Verify site ownership
    try:
        site = await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Check if already enabled
    if site.monitoring_enabled:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Monitoring is already enabled for this site",
        )

    # Enable monitoring
    await enable_monitoring(
        site_id=site_id,
        day_of_week=request.day_of_week,
        hour=request.hour,
        include_observation=request.include_observation,
        include_benchmark=request.include_benchmark,
    )

    # Get the created schedule
    schedule_result = await db.execute(
        select(MonitoringSchedule).where(MonitoringSchedule.site_id == site_id)
    )
    schedule = schedule_result.scalar_one()

    return SuccessResponse(data=MonitoringScheduleResponse.model_validate(schedule))


@router.delete(
    "",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disable monitoring for a site",
)
async def disable_site_monitoring(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> None:
    """
    Disable periodic monitoring for a site.

    - Cancels any scheduled snapshot jobs
    - Removes the monitoring schedule
    - Historical snapshots are preserved
    """
    # Verify site ownership
    try:
        site = await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    if not site.monitoring_enabled:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Monitoring is not enabled for this site",
        )

    await disable_monitoring(site_id)


@router.get(
    "",
    response_model=SuccessResponse[MonitoringStatusResponse],
    summary="Get monitoring status",
)
async def get_monitoring_status(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[MonitoringStatusResponse]:
    """
    Get the current monitoring status for a site.

    Returns:
    - Whether monitoring is enabled
    - Schedule configuration if enabled
    - Next and last run times
    """
    # Verify site ownership
    try:
        site = await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Get schedule if exists
    schedule_result = await db.execute(
        select(MonitoringSchedule).where(MonitoringSchedule.site_id == site_id)
    )
    schedule = schedule_result.scalar_one_or_none()

    if not site.monitoring_enabled or not schedule:
        return SuccessResponse(
            data=MonitoringStatusResponse(
                enabled=False,
            )
        )

    return SuccessResponse(
        data=MonitoringStatusResponse(
            enabled=True,
            frequency=schedule.frequency,
            next_run_at=schedule.next_run_at,
            last_run_at=schedule.last_run_at,
            last_run_status=schedule.last_run_status,
            schedule=MonitoringScheduleResponse.model_validate(schedule),
        )
    )


@router.post(
    "/snapshot",
    response_model=SuccessResponse[SnapshotResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Trigger a manual snapshot",
)
async def trigger_snapshot(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[SnapshotResponse]:
    """
    Trigger an immediate snapshot for a site.

    This runs a full audit and creates a snapshot record,
    regardless of the monitoring schedule.
    """
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Run the snapshot
    from api.models import SnapshotTrigger

    result = await run_snapshot(
        site_id=site_id,
        trigger=SnapshotTrigger.MANUAL.value,
        include_observation=True,
        include_benchmark=True,
    )

    if result.get("status") != "complete":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("reason", "Snapshot failed"),
        )

    # Get the created snapshot
    snapshot_result = await db.execute(
        select(Snapshot).where(Snapshot.id == uuid.UUID(result["snapshot_id"]))
    )
    snapshot = snapshot_result.scalar_one()

    return SuccessResponse(data=SnapshotResponse.model_validate(snapshot))


# Snapshots router (nested under sites)
snapshots_router = APIRouter(prefix="/sites/{site_id}/snapshots", tags=["snapshots"])


@snapshots_router.get(
    "",
    response_model=SuccessResponse[SnapshotListResponse],
    summary="List snapshots for a site",
)
async def list_snapshots(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=12, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> SuccessResponse[SnapshotListResponse]:
    """
    List all snapshots for a site.

    Returns paginated results ordered by snapshot date (newest first).
    """
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Get total count
    count_result = await db.execute(
        select(func.count()).select_from(Snapshot).where(Snapshot.site_id == site_id)
    )
    total = count_result.scalar_one()

    # Get snapshots
    result = await db.execute(
        select(Snapshot)
        .where(Snapshot.site_id == site_id)
        .order_by(Snapshot.snapshot_at.desc())
        .limit(limit)
        .offset(offset)
    )
    snapshots = list(result.scalars().all())

    return SuccessResponse(
        data=SnapshotListResponse(
            items=[SnapshotResponse.model_validate(s) for s in snapshots],
            total=total,
            limit=limit,
            offset=offset,
        )
    )


@snapshots_router.get(
    "/{snapshot_id}",
    response_model=SuccessResponse[SnapshotResponse],
    summary="Get a specific snapshot",
)
async def get_snapshot(
    site_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
) -> SuccessResponse[SnapshotResponse]:
    """
    Get details of a specific snapshot.
    """
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    # Get snapshot
    result = await db.execute(
        select(Snapshot).where(
            Snapshot.id == snapshot_id,
            Snapshot.site_id == site_id,
        )
    )
    snapshot = result.scalar_one_or_none()

    if not snapshot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Snapshot {snapshot_id} not found",
        )

    return SuccessResponse(data=SnapshotResponse.model_validate(snapshot))


@snapshots_router.get(
    "/trend",
    response_model=SuccessResponse[ScoreTrendResponse],
    summary="Get score trend data",
)
async def get_score_trend(
    site_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    days: int = Query(default=90, ge=7, le=365),
) -> SuccessResponse[ScoreTrendResponse]:
    """
    Get score trend data for charting.

    Returns score data points over the specified period.
    """
    # Verify site ownership
    try:
        await site_service.get_site(db, site_id, user.id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site {site_id} not found",
        )

    period_end = datetime.now(UTC)
    period_start = period_end - timedelta(days=days)

    # Get snapshots in the period
    result = await db.execute(
        select(Snapshot)
        .where(
            Snapshot.site_id == site_id,
            Snapshot.snapshot_at >= period_start,
        )
        .order_by(Snapshot.snapshot_at.asc())
    )
    snapshots = list(result.scalars().all())

    # Build trend points
    points = [
        ScoreTrendPoint(
            date=s.snapshot_at,
            score_typical=s.score_typical,
            score_delta=s.score_delta,
            mention_rate=s.mention_rate,
        )
        for s in snapshots
    ]

    # Calculate overall delta
    overall_delta = None
    if len(snapshots) >= 2:
        first = snapshots[0]
        last = snapshots[-1]
        if first.score_typical is not None and last.score_typical is not None:
            overall_delta = last.score_typical - first.score_typical

    return SuccessResponse(
        data=ScoreTrendResponse(
            site_id=site_id,
            points=points,
            period_start=period_start,
            period_end=period_end,
            overall_delta=overall_delta,
        )
    )


# Admin router for scheduler stats
admin_router = APIRouter(prefix="/admin/scheduler", tags=["admin"])


@admin_router.get(
    "/stats",
    response_model=SuccessResponse[SchedulerStatsResponse],
    summary="Get scheduler statistics",
)
async def get_scheduler_stats(
    _user: CurrentUser,  # Required for auth, not used in logic
) -> SuccessResponse[SchedulerStatsResponse]:
    """
    Get scheduler statistics and job list.

    Admin endpoint for monitoring the scheduler.
    """
    jobs = monitoring_scheduler.get_scheduled_jobs()

    return SuccessResponse(
        data=SchedulerStatsResponse(
            jobs_count=len(jobs),
            jobs=[
                ScheduledJobResponse(
                    job_id=j["job_id"],
                    site_id=j.get("site_id"),
                    run_at=j.get("run_at"),
                    scheduled_at=j.get("scheduled_at"),
                    frequency=j.get("frequency"),
                )
                for j in jobs
            ],
        )
    )
