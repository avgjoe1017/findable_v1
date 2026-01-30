"""Notification providers for alert delivery."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import structlog

from api.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass
class NotificationResult:
    """Result of a notification delivery attempt."""

    success: bool
    channel: str
    error: str | None = None
    response_data: dict | None = None
    response_time_ms: int | None = None


class NotificationProvider(ABC):
    """Base class for notification providers."""

    @property
    @abstractmethod
    def channel(self) -> str:
        """Return the channel name."""
        pass

    @abstractmethod
    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> NotificationResult:
        """Send a notification."""
        pass


class EmailProvider(NotificationProvider):
    """Email notification provider.

    In production, this would integrate with SendGrid, SES, etc.
    For now, it logs the email (development mode).
    """

    @property
    def channel(self) -> str:
        return "email"

    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        data: dict | None = None,  # noqa: ARG002
    ) -> NotificationResult:
        """Send an email notification."""
        settings = get_settings()

        # In development, just log the email
        if settings.env == "development":
            logger.info(
                "email_notification_dev",
                recipient=recipient,
                title=title,
                message=message[:100] + "..." if len(message) > 100 else message,
            )
            return NotificationResult(
                success=True,
                channel=self.channel,
                response_data={"mode": "development", "logged": True},
            )

        # In production, send via email service
        # TODO: Implement actual email sending (SendGrid, SES, etc.)
        try:
            # Placeholder for actual email sending
            logger.info(
                "email_notification_sent",
                recipient=recipient,
                title=title,
            )
            return NotificationResult(
                success=True,
                channel=self.channel,
            )
        except Exception as e:
            logger.error(
                "email_notification_failed",
                recipient=recipient,
                error=str(e),
            )
            return NotificationResult(
                success=False,
                channel=self.channel,
                error=str(e),
            )


class WebhookProvider(NotificationProvider):
    """Webhook notification provider."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    @property
    def channel(self) -> str:
        return "webhook"

    async def send(
        self,
        recipient: str,  # This is the webhook URL
        title: str,
        message: str,
        data: dict | None = None,
    ) -> NotificationResult:
        """Send a webhook notification."""
        if not recipient:
            return NotificationResult(
                success=False,
                channel=self.channel,
                error="No webhook URL configured",
            )

        payload = {
            "event": "findable.alert",
            "timestamp": datetime.now(UTC).isoformat(),
            "alert": {
                "title": title,
                "message": message,
                "data": data or {},
            },
        }

        start_time = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    recipient,
                    json=payload,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "Findable-Alerts/1.0",
                    },
                )

                elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                if response.is_success:
                    logger.info(
                        "webhook_notification_sent",
                        url=recipient[:50] + "..." if len(recipient) > 50 else recipient,
                        status_code=response.status_code,
                        elapsed_ms=elapsed_ms,
                    )
                    return NotificationResult(
                        success=True,
                        channel=self.channel,
                        response_data={
                            "status_code": response.status_code,
                        },
                        response_time_ms=elapsed_ms,
                    )
                else:
                    logger.warning(
                        "webhook_notification_failed",
                        url=recipient[:50] + "..." if len(recipient) > 50 else recipient,
                        status_code=response.status_code,
                    )
                    return NotificationResult(
                        success=False,
                        channel=self.channel,
                        error=f"HTTP {response.status_code}",
                        response_time_ms=elapsed_ms,
                    )

        except httpx.TimeoutException:
            elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            logger.error("webhook_timeout", url=recipient[:50])
            return NotificationResult(
                success=False,
                channel=self.channel,
                error="Request timeout",
                response_time_ms=elapsed_ms,
            )
        except Exception as e:
            logger.error("webhook_error", url=recipient[:50], error=str(e))
            return NotificationResult(
                success=False,
                channel=self.channel,
                error=str(e),
            )


class InAppProvider(NotificationProvider):
    """In-app notification provider.

    Stores notifications in the database for display in the UI.
    The Alert model itself serves as the in-app notification.
    """

    @property
    def channel(self) -> str:
        return "in_app"

    async def send(
        self,
        recipient: str,  # noqa: ARG002 - User ID, kept for interface consistency
        title: str,  # noqa: ARG002 - Kept for interface consistency
        message: str,  # noqa: ARG002 - Kept for interface consistency
        data: dict | None = None,  # noqa: ARG002 - Kept for interface consistency
    ) -> NotificationResult:
        """In-app notifications are already stored as Alerts."""
        # The alert is already created in the database
        # This just marks it as "delivered" for in-app
        return NotificationResult(
            success=True,
            channel=self.channel,
            response_data={"stored": True},
        )


async def send_alert_notifications(
    alert_id: uuid.UUID,
    user_email: str,
    title: str,
    message: str,
    data: dict | None,
    email_enabled: bool,
    webhook_enabled: bool,
    webhook_url: str | None,
    in_app_enabled: bool,
) -> dict[str, NotificationResult]:
    """Send alert notifications through all enabled channels.

    Returns a dict of channel -> NotificationResult.
    """
    results: dict[str, NotificationResult] = {}

    # Email
    if email_enabled:
        provider = EmailProvider()
        results["email"] = await provider.send(
            recipient=user_email,
            title=title,
            message=message,
            data=data,
        )

    # Webhook
    if webhook_enabled and webhook_url:
        webhook_provider = WebhookProvider()
        results["webhook"] = await webhook_provider.send(
            recipient=webhook_url,
            title=title,
            message=message,
            data=data,
        )

    # In-app
    if in_app_enabled:
        in_app_provider = InAppProvider()
        results["in_app"] = await in_app_provider.send(
            recipient=str(alert_id),
            title=title,
            message=message,
            data=data,
        )

    return results


async def test_webhook(url: str, timeout: float = 10.0) -> NotificationResult:
    """Test a webhook URL with a test payload."""
    provider = WebhookProvider(timeout=timeout)
    return await provider.send(
        recipient=url,
        title="Findable Webhook Test",
        message="This is a test notification from Findable to verify your webhook configuration.",
        data={"test": True, "timestamp": datetime.now(UTC).isoformat()},
    )
