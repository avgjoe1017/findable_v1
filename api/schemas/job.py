"""Job-related Pydantic schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class JobStatusResponse(BaseModel):
    """Response schema for job status."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    created_at: datetime | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    result: Any | None = None
    error: str | None = None
    meta: dict[str, Any] = {}


class QueueStats(BaseModel):
    """Statistics for a single queue."""

    name: str
    count: int
    started_jobs: int
    finished_jobs: int
    failed_jobs: int
    deferred_jobs: int
    scheduled_jobs: int


class QueueStatsResponse(BaseModel):
    """Response schema for queue statistics."""

    high: QueueStats
    default: QueueStats
    low: QueueStats
