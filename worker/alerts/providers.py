"""Notification providers for alert delivery."""

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
    """Email notification provider using SendGrid or SES."""

    @property
    def channel(self) -> str:
        return "email"

    async def send(
        self,
        recipient: str,
        title: str,
        message: str,
        data: dict | None = None,
    ) -> NotificationResult:
        """Send an email notification."""
        settings = get_settings()

        # In development/test without API key, just log
        if settings.env in ("development", "test") and not settings.sendgrid_api_key:
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

        # Send via configured provider
        if settings.email_provider == "sendgrid":
            return await self._send_sendgrid(recipient, title, message, data, settings)
        else:
            # Fallback: log only
            logger.warning(
                "email_provider_not_configured",
                provider=settings.email_provider,
            )
            return NotificationResult(
                success=False,
                channel=self.channel,
                error=f"Email provider '{settings.email_provider}' not configured",
            )

    async def _send_sendgrid(
        self,
        recipient: str,
        title: str,
        message: str,
        data: dict | None,  # type: ignore[type-arg]
        settings: Any,
    ) -> NotificationResult:
        """Send email via SendGrid API."""
        if not settings.sendgrid_api_key:
            return NotificationResult(
                success=False,
                channel=self.channel,
                error="SendGrid API key not configured",
            )

        # Build HTML email from message
        html_content = self._build_html_email(title, message, data)

        payload = {
            "personalizations": [{"to": [{"email": recipient}]}],
            "from": {
                "email": settings.email_from_address,
                "name": settings.email_from_name,
            },
            "subject": title,
            "content": [
                {"type": "text/plain", "value": message},
                {"type": "text/html", "value": html_content},
            ],
        }

        start_time = datetime.now(UTC)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.sendgrid.com/v3/mail/send",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {settings.sendgrid_api_key}",
                        "Content-Type": "application/json",
                    },
                )

                elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

                # SendGrid returns 202 Accepted for success
                if response.status_code in (200, 202):
                    logger.info(
                        "email_sent_sendgrid",
                        recipient=recipient,
                        title=title,
                        elapsed_ms=elapsed_ms,
                    )
                    return NotificationResult(
                        success=True,
                        channel=self.channel,
                        response_data={"status_code": response.status_code},
                        response_time_ms=elapsed_ms,
                    )
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text[:200]}"
                    logger.error(
                        "email_sendgrid_failed",
                        recipient=recipient,
                        status_code=response.status_code,
                        error=response.text[:200],
                    )
                    return NotificationResult(
                        success=False,
                        channel=self.channel,
                        error=error_msg,
                        response_time_ms=elapsed_ms,
                    )

        except Exception as e:
            logger.error("email_sendgrid_error", error=str(e))
            return NotificationResult(
                success=False,
                channel=self.channel,
                error=str(e),
            )

    def _build_html_email(
        self,
        title: str,
        message: str,
        data: dict | None,
    ) -> str:
        """Build a simple HTML email."""
        # Extract alert details from data if available
        site_name = data.get("site_name", "") if data else ""
        score = data.get("score") if data else None
        _ = data.get("alert_type", "") if data else ""  # reserved for future use

        score_html = ""
        if score is not None:
            score_html = f"""
            <div style="text-align: center; margin: 20px 0;">
                <span style="font-size: 48px; font-weight: bold; color: #0d9488;">{score}</span>
                <span style="font-size: 18px; color: #64748b;">/100</span>
            </div>
            """

        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 0; background-color: #f1f5f9;">
    <div style="max-width: 600px; margin: 0 auto; padding: 40px 20px;">
        <div style="background: white; border-radius: 12px; padding: 32px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #0d9488; margin: 0; font-size: 24px;">Findable</h1>
            </div>

            <!-- Title -->
            <h2 style="color: #1e293b; margin: 0 0 16px 0; font-size: 20px;">{title}</h2>

            {f'<p style="color: #64748b; margin: 0 0 8px 0; font-size: 14px;">Site: {site_name}</p>' if site_name else ''}

            {score_html}

            <!-- Message -->
            <div style="color: #334155; line-height: 1.6; margin: 16px 0;">
                {message.replace(chr(10), '<br>')}
            </div>

            <!-- CTA Button -->
            <div style="text-align: center; margin: 32px 0;">
                <a href="https://app.findable.ai" style="display: inline-block; background: linear-gradient(135deg, #0d9488, #14b8a6); color: white; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: 500;">View Dashboard</a>
            </div>

            <!-- Footer -->
            <div style="border-top: 1px solid #e2e8f0; margin-top: 32px; padding-top: 16px; text-align: center; color: #94a3b8; font-size: 12px;">
                <p style="margin: 0 0 8px 0;">Findable Score Analyzer</p>
                <p style="margin: 0;">
                    <a href="https://app.findable.ai/settings/notifications" style="color: #64748b;">Manage notifications</a>
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


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
