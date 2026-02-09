"""Alert models for monitoring notifications."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.site import Site
    from api.models.user import User


class AlertType(StrEnum):
    """Types of alerts that can be triggered."""

    SCORE_DROP = "score_drop"  # Score decreased by threshold
    SCORE_IMPROVEMENT = "score_improvement"  # Score increased by threshold
    SCORE_CRITICAL = "score_critical"  # Score fell below critical threshold
    MENTION_RATE_DROP = "mention_rate_drop"  # Mention rate decreased
    MENTION_RATE_IMPROVEMENT = "mention_rate_improvement"  # Mention rate increased
    COMPETITOR_OVERTAKE = "competitor_overtake"  # Competitor now ranks higher
    SNAPSHOT_FAILED = "snapshot_failed"  # Scheduled snapshot failed
    SNAPSHOT_COMPLETE = "snapshot_complete"  # Snapshot completed (optional)


class AlertSeverity(StrEnum):
    """Severity levels for alerts."""

    CRITICAL = "critical"  # Immediate attention needed
    WARNING = "warning"  # Important but not urgent
    INFO = "info"  # Informational only


class AlertChannel(StrEnum):
    """Notification delivery channels."""

    EMAIL = "email"
    WEBHOOK = "webhook"
    IN_APP = "in_app"


class AlertStatus(StrEnum):
    """Status of an alert."""

    PENDING = "pending"  # Not yet sent
    SENT = "sent"  # Successfully delivered
    FAILED = "failed"  # Delivery failed
    ACKNOWLEDGED = "acknowledged"  # User acknowledged
    DISMISSED = "dismissed"  # User dismissed


class AlertConfig(Base):
    """User alert configuration for a site."""

    __tablename__ = "alert_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Enable/disable alerts
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Alert type toggles
    alert_on_score_drop: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_score_improvement: Mapped[bool] = mapped_column(Boolean, default=False)
    alert_on_score_critical: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_mention_rate_change: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_competitor_overtake: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_snapshot_failed: Mapped[bool] = mapped_column(Boolean, default=True)
    alert_on_snapshot_complete: Mapped[bool] = mapped_column(Boolean, default=False)

    # Thresholds
    score_drop_threshold: Mapped[int] = mapped_column(Integer, default=5, nullable=False)  # Points
    score_improvement_threshold: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    score_critical_threshold: Mapped[int] = mapped_column(
        Integer, default=40, nullable=False
    )  # Score below this
    mention_rate_threshold: Mapped[float] = mapped_column(default=0.1, nullable=False)  # 10% change

    # Notification channels
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    webhook_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Rate limiting
    min_hours_between_alerts: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    last_alert_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    user: Mapped[User] = relationship("User")
    site: Mapped[Site] = relationship("Site")


class Alert(Base):
    """Individual alert instance."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Alert details
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(
        String(20), default=AlertSeverity.WARNING.value, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), default=AlertStatus.PENDING.value, nullable=False, index=True
    )

    # Content
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)

    # Context data
    data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example:
    # {
    #   "previous_score": 72,
    #   "current_score": 65,
    #   "delta": -7,
    #   "snapshot_id": "uuid",
    #   "competitor": "competitor.com"
    # }

    # Delivery tracking
    channels_sent: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    # ["email", "webhook", "in_app"]

    delivery_errors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # {"email": "SMTP error", "webhook": null}

    # User interaction
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    user: Mapped[User] = relationship("User")
    site: Mapped[Site] = relationship("Site")
