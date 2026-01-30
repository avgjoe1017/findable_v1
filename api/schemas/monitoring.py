"""Monitoring API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MonitoringEnableRequest(BaseModel):
    """Request to enable monitoring for a site."""

    day_of_week: int = Field(
        default=0,
        ge=0,
        le=6,
        description="Day of week for snapshots (0=Monday, 6=Sunday)",
    )
    hour: int = Field(
        default=6,
        ge=0,
        le=23,
        description="Hour of day (UTC) for snapshots",
    )
    include_observation: bool = Field(
        default=True,
        description="Run real AI observation in snapshots",
    )
    include_benchmark: bool = Field(
        default=True,
        description="Include competitor benchmark in snapshots",
    )


class MonitoringScheduleResponse(BaseModel):
    """Monitoring schedule information."""

    id: UUID
    site_id: UUID
    frequency: str = Field(description="weekly or monthly")
    day_of_week: int = Field(description="0=Monday, 6=Sunday")
    hour: int = Field(description="Hour of day (UTC)")
    include_observation: bool
    include_benchmark: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_run_status: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class MonitoringStatusResponse(BaseModel):
    """Response with monitoring status."""

    enabled: bool
    frequency: str | None = None
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    schedule: MonitoringScheduleResponse | None = None


class SnapshotResponse(BaseModel):
    """Snapshot summary for API responses."""

    id: UUID
    site_id: UUID
    run_id: UUID | None
    report_id: UUID | None
    trigger: str
    score_conservative: int | None
    score_typical: int | None
    score_generous: int | None
    mention_rate: float | None
    score_delta: int | None
    mention_rate_delta: float | None
    category_scores: dict | None
    benchmark_data: dict | None
    changes: dict | None
    snapshot_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class SnapshotListResponse(BaseModel):
    """Paginated list of snapshots."""

    items: list[SnapshotResponse]
    total: int
    limit: int
    offset: int


class ScoreTrendPoint(BaseModel):
    """A single point in a score trend."""

    date: datetime
    score_typical: int | None
    score_delta: int | None
    mention_rate: float | None


class ScoreTrendResponse(BaseModel):
    """Score trend data for charting."""

    site_id: UUID
    points: list[ScoreTrendPoint]
    period_start: datetime
    period_end: datetime
    overall_delta: int | None


class ScheduledJobResponse(BaseModel):
    """Information about a scheduled monitoring job."""

    job_id: str
    site_id: str | None
    run_at: str | None
    scheduled_at: str | None
    frequency: str | None


class SchedulerStatsResponse(BaseModel):
    """Scheduler statistics."""

    jobs_count: int
    jobs: list[ScheduledJobResponse]
