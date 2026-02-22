"""Snapshot model for monitoring score changes over time."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.run import Report, Run
    from api.models.site import Site


class SnapshotTrigger(StrEnum):
    """How the snapshot was triggered."""

    SCHEDULED_WEEKLY = "scheduled_weekly"
    SCHEDULED_MONTHLY = "scheduled_monthly"
    MANUAL = "manual"
    ON_DEMAND = "on_demand"


class Snapshot(Base):
    """Snapshot model - stores score snapshots for monitoring trends."""

    __tablename__ = "snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Associated run/report
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Trigger type
    trigger: Mapped[str] = mapped_column(
        String(50),
        default=SnapshotTrigger.SCHEDULED_WEEKLY.value,
        nullable=False,
    )

    # Score snapshot (denormalized for quick access)
    score_conservative: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_typical: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_generous: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mention_rate: Mapped[float | None] = mapped_column(nullable=True)

    # Score changes from previous snapshot
    score_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mention_rate_delta: Mapped[float | None] = mapped_column(nullable=True)

    # Category scores snapshot
    category_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #   "identity": 78,
    #   "offerings": 54,
    #   "contact": 82,
    #   "trust": 45,
    #   "differentiation": 61
    # }

    # Benchmark snapshot (if competitors analyzed)
    benchmark_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #   "win_rate": 0.65,
    #   "competitors": [
    #     {"domain": "competitor.com", "score": 72, "win_rate": 0.45}
    #   ]
    # }

    # Comparison to previous snapshot
    changes: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #   "score_improved": true,
    #   "categories_improved": ["identity", "trust"],
    #   "categories_declined": [],
    #   "new_issues": [],
    #   "resolved_issues": []
    # }

    # Timestamps
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    site: Mapped[Site] = relationship("Site")
    run: Mapped[Run | None] = relationship("Run")
    report: Mapped[Report | None] = relationship("Report")


class MonitoringSchedule(Base):
    """Stores the monitoring schedule configuration for a site."""

    __tablename__ = "monitoring_schedules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Schedule configuration
    frequency: Mapped[str] = mapped_column(
        String(20),
        default="weekly",
        nullable=False,
    )  # weekly, monthly

    # Day of week for weekly (0=Monday, 6=Sunday)
    day_of_week: Mapped[int] = mapped_column(
        Integer,
        default=0,  # Monday
        nullable=False,
    )

    # Hour of day (UTC)
    hour: Mapped[int] = mapped_column(
        Integer,
        default=6,  # 6 AM UTC
        nullable=False,
    )

    # Include options
    include_observation: Mapped[bool] = mapped_column(default=True, nullable=False)
    include_benchmark: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Scheduling state
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Scheduler job ID (for cancellation)
    scheduler_job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    site: Mapped[Site] = relationship("Site")
