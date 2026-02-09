"""Run and Report models."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.site import Site


class RunStatus(StrEnum):
    """Run status states."""

    QUEUED = "queued"
    CRAWLING = "crawling"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    SIMULATING = "simulating"
    OBSERVING = "observing"
    ASSEMBLING = "assembling"
    COMPLETE = "complete"
    FAILED = "failed"


class RunType(StrEnum):
    """Type of run."""

    STARTER_AUDIT = "starter_audit"
    SNAPSHOT = "snapshot"
    RESCORE = "rescore"


class Run(Base):
    """Run model - represents an audit run for a site."""

    __tablename__ = "runs"

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

    # Run configuration
    run_type: Mapped[str] = mapped_column(
        String(50),
        default=RunType.STARTER_AUDIT.value,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default=RunStatus.QUEUED.value,
        nullable=False,
        index=True,
    )

    # Job tracking
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Configuration
    config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example config:
    # {
    #   "include_observation": true,
    #   "include_benchmark": true,
    #   "bands": ["conservative", "typical", "generous"],
    #   "provider": {"preferred": "router", "model": "auto"},
    #   "question_set_id": "uuid"
    # }

    # Progress tracking
    progress: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example progress:
    # {
    #   "pages_crawled": 150,
    #   "pages_total": 250,
    #   "chunks_created": 450,
    #   "current_step": "simulating"
    # }

    # Results
    report_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Error handling
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Optimistic locking version
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

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
    site: Mapped[Site] = relationship("Site", back_populates="runs")
    report: Mapped[Report | None] = relationship("Report", back_populates="run")

    __mapper_args__ = {"version_id_col": version}


class Report(Base):
    """Report model - stores the generated report JSON."""

    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # Report version for schema evolution
    report_version: Mapped[str] = mapped_column(
        String(20),
        default="1.0",
        nullable=False,
    )

    # The full report JSON (see spec Section 19)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Quick access fields (denormalized from data)
    score_conservative: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_typical: Mapped[int | None] = mapped_column(Integer, nullable=True)
    score_generous: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mention_rate: Mapped[float | None] = mapped_column(nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # Relationships
    run: Mapped[Run | None] = relationship("Run", back_populates="report")
