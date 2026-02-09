"""Custom middleware for the API."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

# Type alias for call_next function
CallNext = Callable[[Request], Awaitable[Response]]

logger = structlog.get_logger()


# Rate limiting configuration
@dataclass
class RateLimitConfig:
    """Rate limit configuration."""

    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_size: int = 10  # Allow burst above limit


@dataclass
class RateLimitBucket:
    """Token bucket for rate limiting."""

    tokens: float = 0.0
    last_update: float = field(default_factory=time.time)


# Default rate limits by plan tier
PLAN_RATE_LIMITS = {
    "starter": RateLimitConfig(requests_per_minute=30, requests_per_hour=500),
    "professional": RateLimitConfig(requests_per_minute=120, requests_per_hour=5000),
    "agency": RateLimitConfig(requests_per_minute=300, requests_per_hour=20000),
}

# Stricter limits for auth endpoints (per IP)
AUTH_RATE_LIMITS = RateLimitConfig(
    requests_per_minute=10,
    requests_per_hour=50,
    burst_size=5,
)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add unique request ID to each request for tracing."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))

        # Bind request ID to structlog context
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Add to request state for access in handlers
        request.state.request_id = request_id

        response = await call_next(request)  # type: ignore[return-value]

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log request/response details."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        start_time = time.perf_counter()

        # Log request
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
        )

        response = await call_next(request)  # type: ignore[return-value]

        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Log response
        logger.info(
            "Request completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using token bucket algorithm."""

    # Paths excluded from rate limiting
    EXCLUDE_PATHS = {"/api/health", "/api/ready", "/metrics", "/docs", "/openapi.json"}

    # Auth paths with stricter limits
    AUTH_PATHS = {"/v1/auth/login", "/v1/auth/register", "/v1/auth/forgot-password"}

    def __init__(self, app: Any, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled
        # In-memory buckets (use Redis in production for multi-instance)
        self._user_buckets: dict[str, RateLimitBucket] = defaultdict(RateLimitBucket)
        self._ip_buckets: dict[str, RateLimitBucket] = defaultdict(RateLimitBucket)

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        if not self.enabled:
            return await call_next(request)  # type: ignore[return-value]

        # Skip excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)  # type: ignore[return-value]

        # Get client identifier
        client_ip = self._get_client_ip(request)

        # Check auth endpoint rate limits (by IP)
        if request.url.path in self.AUTH_PATHS:
            allowed, retry_after = self._check_rate_limit(
                f"ip:{client_ip}",
                AUTH_RATE_LIMITS,
                self._ip_buckets,
            )
            if not allowed:
                return self._rate_limit_response(retry_after)

        # Check user rate limits (by user ID or IP)
        user_id = self._get_user_id(request)
        plan = self._get_user_plan(request)
        limits = PLAN_RATE_LIMITS.get(plan, PLAN_RATE_LIMITS["starter"])

        identifier = f"user:{user_id}" if user_id else f"ip:{client_ip}"
        allowed, retry_after = self._check_rate_limit(identifier, limits, self._user_buckets)

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                identifier=identifier,
                path=request.url.path,
            )
            return self._rate_limit_response(retry_after)

        response = await call_next(request)  # type: ignore[return-value]

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(limits.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(
            max(0, int(self._user_buckets[identifier].tokens))
        )

        return response

    def _check_rate_limit(
        self,
        identifier: str,
        config: RateLimitConfig,
        buckets: dict[str, RateLimitBucket],
    ) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, retry_after_seconds)."""
        now = time.time()
        bucket = buckets[identifier]

        # Refill tokens based on time elapsed
        elapsed = now - bucket.last_update
        refill_rate = config.requests_per_minute / 60.0  # tokens per second
        bucket.tokens = min(
            config.burst_size + config.requests_per_minute,
            bucket.tokens + elapsed * refill_rate,
        )
        bucket.last_update = now

        # Check if we have tokens
        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0

        # Calculate retry after
        retry_after = int((1.0 - bucket.tokens) / refill_rate) + 1
        return False, retry_after

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP, handling proxies."""
        # Check X-Forwarded-For header (from reverse proxy)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # First IP is the original client
            ip: str = forwarded.split(",")[0].strip()
            return ip
        # Fall back to direct connection
        return request.client.host if request.client else "unknown"

    def _get_user_id(self, request: Request) -> str | None:
        """Get user ID from request state if authenticated."""
        return getattr(request.state, "user_id", None)

    def _get_user_plan(self, request: Request) -> str:
        """Get user plan from request state."""
        return getattr(request.state, "user_plan", "starter")

    def _rate_limit_response(self, retry_after: int) -> JSONResponse:
        """Create rate limit exceeded response."""
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "code": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                }
            },
            headers={"Retry-After": str(retry_after)},
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses."""

    async def dispatch(self, request: Request, call_next: CallNext) -> Response:
        response = await call_next(request)  # type: ignore[return-value]

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # XSS protection (legacy, but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer policy
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions policy (disable unnecessary features)
        response.headers["Permissions-Policy"] = (
            "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
            "magnetometer=(), microphone=(), payment=(), usb=()"
        )

        # Content Security Policy for API responses
        # More permissive for HTML pages, stricter for API
        if request.url.path.startswith("/v1/") or request.url.path.startswith("/api/"):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )

        # HSTS (only in production with HTTPS)
        # Uncomment when deployed with HTTPS:
        # response.headers["Strict-Transport-Security"] = (
        #     "max-age=31536000; includeSubDomains; preload"
        # )

        return response
