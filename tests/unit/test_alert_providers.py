"""Tests for alert notification providers."""

import pytest

from worker.alerts.providers import (
    EmailProvider,
    InAppProvider,
    NotificationResult,
    WebhookProvider,
)


class TestNotificationResult:
    """Tests for NotificationResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful notification result."""
        result = NotificationResult(
            success=True,
            channel="email",
            response_time_ms=150,
        )

        assert result.success is True
        assert result.channel == "email"
        assert result.error is None
        assert result.response_time_ms == 150

    def test_failure_result(self) -> None:
        """Test failed notification result."""
        result = NotificationResult(
            success=False,
            channel="webhook",
            error="Connection timeout",
            response_time_ms=10000,
        )

        assert result.success is False
        assert result.error == "Connection timeout"


class TestEmailProvider:
    """Tests for EmailProvider."""

    def test_channel_name(self) -> None:
        """Test email channel name."""
        provider = EmailProvider()
        assert provider.channel == "email"

    @pytest.mark.asyncio
    async def test_send_logs_email(self) -> None:
        """Test email send logs the email."""
        provider = EmailProvider()
        result = await provider.send(
            recipient="test@example.com",
            title="Test Alert",
            message="This is a test message.",
            data={"test": True},
        )

        # In test/dev mode, email is logged and returns success
        assert result.success is True
        assert result.channel == "email"


class TestWebhookProvider:
    """Tests for WebhookProvider."""

    def test_channel_name(self) -> None:
        """Test webhook channel name."""
        provider = WebhookProvider()
        assert provider.channel == "webhook"

    @pytest.mark.asyncio
    async def test_send_no_url(self) -> None:
        """Test webhook send without URL fails."""
        provider = WebhookProvider()
        result = await provider.send(
            recipient="",
            title="Test Alert",
            message="This is a test message.",
        )

        assert result.success is False
        assert "No webhook URL" in result.error

    @pytest.mark.asyncio
    async def test_send_invalid_url(self) -> None:
        """Test webhook send with invalid URL fails."""
        provider = WebhookProvider(timeout=1.0)
        result = await provider.send(
            recipient="http://invalid.localhost.invalid:9999/webhook",
            title="Test Alert",
            message="This is a test message.",
        )

        assert result.success is False
        assert result.channel == "webhook"
        # Error could be connection error or timeout


class TestInAppProvider:
    """Tests for InAppProvider."""

    def test_channel_name(self) -> None:
        """Test in-app channel name."""
        provider = InAppProvider()
        assert provider.channel == "in_app"

    @pytest.mark.asyncio
    async def test_send_always_succeeds(self) -> None:
        """Test in-app send always succeeds (notification stored in DB)."""
        provider = InAppProvider()
        result = await provider.send(
            recipient="user-uuid",
            title="Test Alert",
            message="This is a test message.",
            data={"test": True},
        )

        assert result.success is True
        assert result.channel == "in_app"
        assert result.response_data["stored"] is True
