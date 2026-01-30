"""Tests for alert model enums."""

from api.models import (
    AlertChannel,
    AlertSeverity,
    AlertStatus,
    AlertType,
)


def test_alert_type_enum() -> None:
    """Test AlertType enum values."""
    assert AlertType.SCORE_DROP.value == "score_drop"
    assert AlertType.SCORE_IMPROVEMENT.value == "score_improvement"
    assert AlertType.SCORE_CRITICAL.value == "score_critical"
    assert AlertType.MENTION_RATE_DROP.value == "mention_rate_drop"
    assert AlertType.MENTION_RATE_IMPROVEMENT.value == "mention_rate_improvement"
    assert AlertType.COMPETITOR_OVERTAKE.value == "competitor_overtake"
    assert AlertType.SNAPSHOT_FAILED.value == "snapshot_failed"
    assert AlertType.SNAPSHOT_COMPLETE.value == "snapshot_complete"


def test_alert_severity_enum() -> None:
    """Test AlertSeverity enum values."""
    assert AlertSeverity.CRITICAL.value == "critical"
    assert AlertSeverity.WARNING.value == "warning"
    assert AlertSeverity.INFO.value == "info"


def test_alert_channel_enum() -> None:
    """Test AlertChannel enum values."""
    assert AlertChannel.EMAIL.value == "email"
    assert AlertChannel.WEBHOOK.value == "webhook"
    assert AlertChannel.IN_APP.value == "in_app"


def test_alert_status_enum() -> None:
    """Test AlertStatus enum values."""
    assert AlertStatus.PENDING.value == "pending"
    assert AlertStatus.SENT.value == "sent"
    assert AlertStatus.FAILED.value == "failed"
    assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
    assert AlertStatus.DISMISSED.value == "dismissed"
