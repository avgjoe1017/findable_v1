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


class PillarScoreSummary(BaseModel):
    """Summary of a single pillar score."""

    name: str
    display_name: str
    raw_score: float = Field(description="Score 0-100 for this pillar")
    points_earned: float = Field(description="Points contributed to total")
    max_points: float = Field(description="Maximum points for this pillar")
    level: str = Field(description="good, warning, or critical")


class ScoreV2Summary(BaseModel):
    """Summary of Findable Score v2."""

    total_score: float = Field(description="Total score 0-100")
    # Findability level (replaces letter grades)
    level: str = Field(
        default="not_yet_findable",
        description="Findability level: not_yet_findable, partially_findable, findable, highly_findable, optimized",
    )
    level_label: str = Field(default="Not Yet Findable", description="Human-readable level label")
    level_summary: str = Field(default="", description="Action-oriented summary for this level")
    level_focus: str = Field(default="", description="What to focus on at this level")
    # Milestone tracking
    next_milestone: str | None = Field(default=None, description="Next findability level to reach")
    points_to_milestone: float = Field(
        default=0.0, description="Points needed to reach next milestone"
    )
    # Pillar breakdown
    pillars: list[PillarScoreSummary] = Field(default_factory=list)
    pillars_good: int = 0
    pillars_warning: int = 0
    pillars_critical: int = 0
    # Strengths (positive findings)
    strengths: list[str] = Field(default_factory=list, description="Positive findings to celebrate")


class ActionItemSummary(BaseModel):
    """Summary of a fix action item."""

    id: str
    category: str
    title: str
    priority: int
    impact_level: str
    effort_level: str
    estimated_points: float = Field(description="Estimated total score improvement")
    impact_points: float = Field(
        default=0.0, description="Points improvement within affected pillar (0-100 scale)"
    )
    affected_pillar: str = Field(default="", description="Which pillar this fix impacts")


class ActionCenterSummary(BaseModel):
    """Summary of the Action Center."""

    total_fixes: int = 0
    quick_wins_count: int = 0
    critical_count: int = 0
    estimated_total_points: float = 0.0
    top_fixes: list[ActionItemSummary] = Field(default_factory=list)


class ReportSummary(BaseModel):
    """Summary of a report for quick display."""

    id: uuid.UUID
    report_version: str
    score_conservative: int | None
    score_typical: int | None
    score_generous: int | None
    mention_rate: float | None
    # v2 fields
    score_v2: ScoreV2Summary | None = None
    action_center: ActionCenterSummary | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class RunWithReport(RunRead):
    """Run with embedded report summary."""

    report: ReportSummary | None = None

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
