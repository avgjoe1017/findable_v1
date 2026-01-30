"""Alert API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AlertConfigCreate(BaseModel):
    """Request to create or update alert configuration."""

    enabled: bool = True

    # Alert type toggles
    alert_on_score_drop: bool = True
    alert_on_score_improvement: bool = False
    alert_on_score_critical: bool = True
    alert_on_mention_rate_change: bool = True
    alert_on_competitor_overtake: bool = True
    alert_on_snapshot_failed: bool = True
    alert_on_snapshot_complete: bool = False

    # Thresholds
    score_drop_threshold: int = Field(default=5, ge=1, le=50)
    score_improvement_threshold: int = Field(default=10, ge=1, le=50)
    score_critical_threshold: int = Field(default=40, ge=0, le=100)
    mention_rate_threshold: float = Field(default=0.1, ge=0.01, le=1.0)

    # Notification channels
    email_enabled: bool = True
    webhook_enabled: bool = False
    webhook_url: str | None = None
    in_app_enabled: bool = True

    # Rate limiting
    min_hours_between_alerts: int = Field(default=24, ge=1, le=168)  # Max 1 week


class AlertConfigUpdate(BaseModel):
    """Partial update for alert configuration."""

    enabled: bool | None = None

    # Alert type toggles
    alert_on_score_drop: bool | None = None
    alert_on_score_improvement: bool | None = None
    alert_on_score_critical: bool | None = None
    alert_on_mention_rate_change: bool | None = None
    alert_on_competitor_overtake: bool | None = None
    alert_on_snapshot_failed: bool | None = None
    alert_on_snapshot_complete: bool | None = None

    # Thresholds
    score_drop_threshold: int | None = Field(default=None, ge=1, le=50)
    score_improvement_threshold: int | None = Field(default=None, ge=1, le=50)
    score_critical_threshold: int | None = Field(default=None, ge=0, le=100)
    mention_rate_threshold: float | None = Field(default=None, ge=0.01, le=1.0)

    # Notification channels
    email_enabled: bool | None = None
    webhook_enabled: bool | None = None
    webhook_url: str | None = None
    in_app_enabled: bool | None = None

    # Rate limiting
    min_hours_between_alerts: int | None = Field(default=None, ge=1, le=168)


class AlertConfigResponse(BaseModel):
    """Alert configuration response."""

    id: UUID
    user_id: UUID
    site_id: UUID
    enabled: bool

    # Alert type toggles
    alert_on_score_drop: bool
    alert_on_score_improvement: bool
    alert_on_score_critical: bool
    alert_on_mention_rate_change: bool
    alert_on_competitor_overtake: bool
    alert_on_snapshot_failed: bool
    alert_on_snapshot_complete: bool

    # Thresholds
    score_drop_threshold: int
    score_improvement_threshold: int
    score_critical_threshold: int
    mention_rate_threshold: float

    # Notification channels
    email_enabled: bool
    webhook_enabled: bool
    webhook_url: str | None
    in_app_enabled: bool

    # Rate limiting
    min_hours_between_alerts: int
    last_alert_at: datetime | None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AlertResponse(BaseModel):
    """Individual alert response."""

    id: UUID
    user_id: UUID
    site_id: UUID
    alert_type: str
    severity: str
    status: str
    title: str
    message: str
    data: dict | None
    channels_sent: list[str] | None
    acknowledged_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime
    sent_at: datetime | None

    model_config = {"from_attributes": True}


class AlertListResponse(BaseModel):
    """Paginated list of alerts."""

    items: list[AlertResponse]
    total: int
    limit: int
    offset: int
    unread_count: int


class AlertAcknowledgeRequest(BaseModel):
    """Request to acknowledge alerts."""

    alert_ids: list[UUID] = Field(min_length=1, max_length=100)


class AlertDismissRequest(BaseModel):
    """Request to dismiss alerts."""

    alert_ids: list[UUID] = Field(min_length=1, max_length=100)


class AlertStats(BaseModel):
    """Alert statistics for a user."""

    total_alerts: int
    unread_count: int
    critical_count: int
    warning_count: int
    info_count: int
    alerts_today: int
    alerts_this_week: int


class WebhookTestRequest(BaseModel):
    """Request to test webhook configuration."""

    webhook_url: str


class WebhookTestResponse(BaseModel):
    """Response from webhook test."""

    success: bool
    status_code: int | None
    error: str | None
    response_time_ms: int | None
