"""Tests for alert API schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from api.schemas.alert import (
    AlertAcknowledgeRequest,
    AlertConfigCreate,
    AlertConfigResponse,
    AlertConfigUpdate,
    AlertDismissRequest,
    AlertListResponse,
    AlertResponse,
    AlertStats,
    WebhookTestRequest,
    WebhookTestResponse,
)


class TestAlertConfigCreate:
    """Tests for AlertConfigCreate schema."""

    def test_default_values(self) -> None:
        """Test default values."""
        config = AlertConfigCreate()

        assert config.enabled is True
        assert config.alert_on_score_drop is True
        assert config.alert_on_score_improvement is False
        assert config.alert_on_score_critical is True
        assert config.score_drop_threshold == 5
        assert config.score_critical_threshold == 40
        assert config.email_enabled is True
        assert config.webhook_enabled is False
        assert config.min_hours_between_alerts == 24

    def test_custom_values(self) -> None:
        """Test with custom values."""
        config = AlertConfigCreate(
            enabled=False,
            alert_on_score_drop=False,
            alert_on_score_improvement=True,
            score_drop_threshold=10,
            score_critical_threshold=30,
            webhook_enabled=True,
            webhook_url="https://example.com/webhook",
        )

        assert config.enabled is False
        assert config.alert_on_score_drop is False
        assert config.alert_on_score_improvement is True
        assert config.score_drop_threshold == 10
        assert config.score_critical_threshold == 30
        assert config.webhook_enabled is True
        assert config.webhook_url == "https://example.com/webhook"

    def test_threshold_validation_min(self) -> None:
        """Test threshold minimum validation."""
        with pytest.raises(ValidationError) as exc:
            AlertConfigCreate(score_drop_threshold=0)

        assert "greater than or equal to 1" in str(exc.value)

    def test_threshold_validation_max(self) -> None:
        """Test threshold maximum validation."""
        with pytest.raises(ValidationError) as exc:
            AlertConfigCreate(score_drop_threshold=51)

        assert "less than or equal to 50" in str(exc.value)

    def test_critical_threshold_range(self) -> None:
        """Test critical threshold accepts full range."""
        config_low = AlertConfigCreate(score_critical_threshold=0)
        config_high = AlertConfigCreate(score_critical_threshold=100)

        assert config_low.score_critical_threshold == 0
        assert config_high.score_critical_threshold == 100

    def test_mention_rate_threshold_validation(self) -> None:
        """Test mention rate threshold validation."""
        # Valid range
        config = AlertConfigCreate(mention_rate_threshold=0.5)
        assert config.mention_rate_threshold == 0.5

        # Too low
        with pytest.raises(ValidationError):
            AlertConfigCreate(mention_rate_threshold=0.001)

        # Too high
        with pytest.raises(ValidationError):
            AlertConfigCreate(mention_rate_threshold=1.5)


class TestAlertConfigUpdate:
    """Tests for AlertConfigUpdate schema."""

    def test_partial_update(self) -> None:
        """Test partial update."""
        update = AlertConfigUpdate(enabled=False)

        assert update.enabled is False
        assert update.alert_on_score_drop is None
        assert update.score_drop_threshold is None

    def test_all_fields_optional(self) -> None:
        """Test all fields are optional."""
        update = AlertConfigUpdate()

        assert update.enabled is None
        assert update.score_drop_threshold is None
        assert update.webhook_url is None


class TestAlertConfigResponse:
    """Tests for AlertConfigResponse schema."""

    def test_full_response(self) -> None:
        """Test full config response."""
        now = datetime.now(UTC)
        config = AlertConfigResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            enabled=True,
            alert_on_score_drop=True,
            alert_on_score_improvement=False,
            alert_on_score_critical=True,
            alert_on_mention_rate_change=True,
            alert_on_competitor_overtake=True,
            alert_on_snapshot_failed=True,
            alert_on_snapshot_complete=False,
            score_drop_threshold=5,
            score_improvement_threshold=10,
            score_critical_threshold=40,
            mention_rate_threshold=0.1,
            email_enabled=True,
            webhook_enabled=False,
            webhook_url=None,
            in_app_enabled=True,
            min_hours_between_alerts=24,
            last_alert_at=None,
            created_at=now,
            updated_at=now,
        )

        assert config.enabled is True
        assert config.score_drop_threshold == 5


class TestAlertResponse:
    """Tests for AlertResponse schema."""

    def test_full_alert(self) -> None:
        """Test full alert response."""
        now = datetime.now(UTC)
        alert = AlertResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            alert_type="score_drop",
            severity="warning",
            status="sent",
            title="Score dropped by 7 points",
            message="Your score decreased from 72 to 65.",
            data={"previous_score": 72, "current_score": 65, "delta": -7},
            channels_sent=["email", "in_app"],
            acknowledged_at=None,
            dismissed_at=None,
            created_at=now,
            sent_at=now,
        )

        assert alert.alert_type == "score_drop"
        assert alert.severity == "warning"
        assert alert.data["delta"] == -7

    def test_minimal_alert(self) -> None:
        """Test minimal alert response."""
        now = datetime.now(UTC)
        alert = AlertResponse(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            alert_type="snapshot_complete",
            severity="info",
            status="pending",
            title="Snapshot complete",
            message="Your scheduled snapshot completed.",
            data=None,
            channels_sent=None,
            acknowledged_at=None,
            dismissed_at=None,
            created_at=now,
            sent_at=None,
        )

        assert alert.data is None
        assert alert.channels_sent is None


class TestAlertListResponse:
    """Tests for AlertListResponse schema."""

    def test_paginated_list(self) -> None:
        """Test paginated alert list."""
        response = AlertListResponse(
            items=[],
            total=100,
            limit=50,
            offset=0,
            unread_count=15,
        )

        assert response.total == 100
        assert response.unread_count == 15


class TestAlertAcknowledgeRequest:
    """Tests for AlertAcknowledgeRequest schema."""

    def test_valid_request(self) -> None:
        """Test valid acknowledge request."""
        request = AlertAcknowledgeRequest(alert_ids=[uuid.uuid4(), uuid.uuid4()])

        assert len(request.alert_ids) == 2

    def test_empty_list_invalid(self) -> None:
        """Test empty list is invalid."""
        with pytest.raises(ValidationError) as exc:
            AlertAcknowledgeRequest(alert_ids=[])

        assert "min_length" in str(exc.value).lower() or "too_short" in str(exc.value).lower()


class TestAlertDismissRequest:
    """Tests for AlertDismissRequest schema."""

    def test_valid_request(self) -> None:
        """Test valid dismiss request."""
        request = AlertDismissRequest(alert_ids=[uuid.uuid4()])

        assert len(request.alert_ids) == 1


class TestAlertStats:
    """Tests for AlertStats schema."""

    def test_stats(self) -> None:
        """Test alert stats."""
        stats = AlertStats(
            total_alerts=50,
            unread_count=10,
            critical_count=2,
            warning_count=5,
            info_count=3,
            alerts_today=3,
            alerts_this_week=15,
        )

        assert stats.total_alerts == 50
        assert stats.unread_count == 10
        assert stats.critical_count == 2


class TestWebhookTestRequest:
    """Tests for WebhookTestRequest schema."""

    def test_valid_url(self) -> None:
        """Test valid webhook URL."""
        request = WebhookTestRequest(webhook_url="https://example.com/webhook")

        assert request.webhook_url == "https://example.com/webhook"


class TestWebhookTestResponse:
    """Tests for WebhookTestResponse schema."""

    def test_success_response(self) -> None:
        """Test successful webhook test response."""
        response = WebhookTestResponse(
            success=True,
            status_code=200,
            error=None,
            response_time_ms=150,
        )

        assert response.success is True
        assert response.status_code == 200
        assert response.response_time_ms == 150

    def test_failure_response(self) -> None:
        """Test failed webhook test response."""
        response = WebhookTestResponse(
            success=False,
            status_code=500,
            error="Internal Server Error",
            response_time_ms=2000,
        )

        assert response.success is False
        assert response.error == "Internal Server Error"
