"""Sentry error tracking integration."""

from __future__ import annotations

import structlog
from fastapi import Request

from api.config import get_settings

logger = structlog.get_logger(__name__)

# Flag to track if Sentry is initialized
_sentry_initialized = False


def init_sentry() -> bool:
    """Initialize Sentry SDK if configured.

    Returns True if Sentry was initialized, False otherwise.
    """
    global _sentry_initialized

    settings = get_settings()

    if not settings.sentry_dsn:
        logger.info("Sentry DSN not configured, skipping initialization")
        return False

    if _sentry_initialized:
        return True

    try:
        import sentry_sdk
        from sentry_sdk.integrations.asyncio import AsyncioIntegration
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.httpx import HttpxIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.starlette import StarletteIntegration

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.env,
            release="findable@0.1.0",
            # Capture 100% of errors
            sample_rate=1.0,
            # Capture 10% of transactions for performance monitoring
            traces_sample_rate=0.1 if settings.is_production else 1.0,
            # Enable profiling (10% of transactions)
            profiles_sample_rate=0.1 if settings.is_production else 0.0,
            # Send PII (user info) - disable in strict privacy environments
            send_default_pii=False,
            # Integrations
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                StarletteIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                HttpxIntegration(),
                AsyncioIntegration(),
                LoggingIntegration(
                    level=None,  # Capture all logs as breadcrumbs
                    event_level=None,  # Don't create events for logs
                ),
            ],
            # Filter sensitive data
            before_send=_before_send,
            before_send_transaction=_before_send_transaction,
        )

        _sentry_initialized = True
        logger.info("Sentry initialized", environment=settings.env)
        return True

    except ImportError:
        logger.warning("sentry-sdk not installed, skipping Sentry initialization")
        return False
    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e))
        return False


def _before_send(event: dict, hint: dict) -> dict | None:
    """Filter or modify events before sending to Sentry."""
    # Filter out certain exceptions
    if "exc_info" in hint:
        exc_type, exc_value, _ = hint["exc_info"]

        # Don't report 4xx errors as they're usually user errors
        from fastapi import HTTPException

        if isinstance(exc_value, HTTPException) and 400 <= exc_value.status_code < 500:
            return None

    # Remove sensitive data from event
    if "request" in event:
        request_data = event["request"]
        # Remove auth headers
        if "headers" in request_data:
            headers = request_data["headers"]
            sensitive_headers = ["authorization", "cookie", "x-api-key"]
            for header in sensitive_headers:
                if header in headers:
                    headers[header] = "[Filtered]"

    return event


def _before_send_transaction(event: dict, hint: dict) -> dict | None:  # noqa: ARG001
    """Filter transactions before sending."""
    # Filter out health check transactions
    if "transaction" in event:
        transaction_name = event["transaction"]
        if transaction_name in ["/api/health", "/api/ready", "/metrics"]:
            return None

    return event


def set_user_context(user_id: str, email: str | None = None, plan: str | None = None) -> None:
    """Set user context for Sentry events."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_user(
            {
                "id": user_id,
                "email": email,
                "plan": plan,
            }
        )
    except Exception:
        pass


def set_tag(key: str, value: str) -> None:
    """Set a tag on the current Sentry scope."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_tag(key, value)
    except Exception:
        pass


def set_context(name: str, data: dict) -> None:
    """Set additional context for Sentry events."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.set_context(name, data)
    except Exception:
        pass


def capture_exception(exception: Exception) -> str | None:
    """Capture an exception and send to Sentry.

    Returns the event ID if captured, None otherwise.
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        event_id: str | None = sentry_sdk.capture_exception(exception)
        return event_id
    except Exception:
        return None


def capture_message(message: str, level: str = "info") -> str | None:
    """Capture a message and send to Sentry.

    Returns the event ID if captured, None otherwise.
    """
    if not _sentry_initialized:
        return None

    try:
        import sentry_sdk

        event_id: str | None = sentry_sdk.capture_message(message, level=level)
        return event_id
    except Exception:
        return None


def add_breadcrumb(
    message: str,
    category: str = "default",
    level: str = "info",
    data: dict | None = None,
) -> None:
    """Add a breadcrumb for debugging."""
    if not _sentry_initialized:
        return

    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            message=message,
            category=category,
            level=level,
            data=data,
        )
    except Exception:
        pass


async def sentry_request_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Middleware to add request context to Sentry."""
    if not _sentry_initialized:
        return await call_next(request)

    try:
        import sentry_sdk

        with sentry_sdk.configure_scope() as scope:
            # Add request ID
            request_id = getattr(request.state, "request_id", None)
            if request_id:
                scope.set_tag("request_id", request_id)

            # Add user context if available
            user_id = getattr(request.state, "user_id", None)
            if user_id:
                scope.set_user({"id": user_id})

            return await call_next(request)

    except Exception:
        return await call_next(request)
