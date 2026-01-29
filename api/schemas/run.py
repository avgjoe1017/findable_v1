"""Run and Report schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunConfig(BaseModel):
    """Run configuration schema."""

    include_observation: bool = True
    include_benchmark: bool = True
    bands: list[str] = Field(
        default=["conservative", "typical", "generous"],
        description="Budget bands to simulate",
    )
    provider: dict[str, str] = Field(
        default={"preferred": "router", "model": "auto"},
        description="Observation provider settings",
    )
    question_set_id: uuid.UUID | None = None


class RunCreate(BaseModel):
    """Schema for creating a run."""

    run_type: str = Field(default="starter_audit")
    config: RunConfig = Field(default_factory=RunConfig)


class RunProgress(BaseModel):
    """Run progress information."""

    pages_crawled: int = 0
    pages_total: int = 0
    chunks_created: int = 0
    questions_processed: int = 0
    questions_total: int = 0
    current_step: str = "queued"


class RunRead(BaseModel):
    """Schema for reading a run."""

    id: uuid.UUID
    site_id: uuid.UUID
    run_type: str
    status: str
    job_id: str | None
    config: dict | None
    progress: RunProgress | None
    report_id: uuid.UUID | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RunList(BaseModel):
    """Schema for listing runs."""

    id: uuid.UUID
    site_id: uuid.UUID
    run_type: str
    status: str
    report_id: uuid.UUID | None
    created_at: datetime
    completed_at: datetime | None

    class Config:
        from_attributes = True


class ReportSummary(BaseModel):
    """Summary of a report for quick display."""

    id: uuid.UUID
    report_version: str
    score_conservative: int | None
    score_typical: int | None
    score_generous: int | None
    mention_rate: float | None
    created_at: datetime

    class Config:
        from_attributes = True


class ReportRead(BaseModel):
    """Full report response."""

    id: uuid.UUID
    report_version: str
    data: dict[str, Any]
    score_conservative: int | None
    score_typical: int | None
    score_generous: int | None
    mention_rate: float | None
    created_at: datetime

    class Config:
        from_attributes = True
