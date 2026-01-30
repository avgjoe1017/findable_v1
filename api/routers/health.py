"""Health check endpoints."""

import time
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import text

from api.config import get_settings
from api.database import async_session_maker

router = APIRouter(tags=["Health"])
logger = structlog.get_logger()

# Track server start time for uptime calculation
_server_start_time = time.time()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    uptime_seconds: int = Field(..., description="Server uptime in seconds")


class DependencyCheck(BaseModel):
    """Individual dependency check result."""

    status: str = Field(..., description="Status: healthy, unhealthy")
    latency_ms: float | None = Field(None, description="Check latency in milliseconds")
    error: str | None = Field(None, description="Error message if unhealthy")


class ReadyResponse(BaseModel):
    """Readiness check response with dependency status."""

    status: str = Field(..., description="Overall status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    uptime_seconds: int = Field(..., description="Server uptime in seconds")
    checks: dict[str, DependencyCheck] = Field(..., description="Individual dependency checks")


class ApiInfoResponse(BaseModel):
    """API information response."""

    name: str
    version: str
    env: str
    docs: str | None


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check endpoint.

    Returns healthy if the API is running. Does not check dependencies.
    Use /ready for full dependency checks.
    """
    uptime = int(time.time() - _server_start_time)
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(UTC).isoformat(),
        version="0.1.0",
        uptime_seconds=uptime,
    )


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check() -> ReadyResponse:
    """
    Readiness check with dependency verification.

    Checks:
    - Database connectivity and latency
    - Redis connectivity and latency
    """
    settings = get_settings()
    checks: dict[str, DependencyCheck] = {}
    overall_status = "healthy"
    uptime = int(time.time() - _server_start_time)

    # Check database
    try:
        start = time.perf_counter()
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = (time.perf_counter() - start) * 1000
        checks["database"] = DependencyCheck(
            status="healthy",
            latency_ms=round(latency_ms, 2),
            error=None,
        )
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        checks["database"] = DependencyCheck(
            status="unhealthy",
            latency_ms=None,
            error=str(e),
        )
        overall_status = "unhealthy"

    # Check Redis
    try:
        start = time.perf_counter()
        redis = Redis.from_url(str(settings.redis_url), socket_timeout=2)
        redis.ping()
        redis.close()
        latency_ms = (time.perf_counter() - start) * 1000
        checks["redis"] = DependencyCheck(
            status="healthy",
            latency_ms=round(latency_ms, 2),
            error=None,
        )
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        checks["redis"] = DependencyCheck(
            status="unhealthy",
            latency_ms=None,
            error=str(e),
        )
        overall_status = "unhealthy"

    # Determine if degraded (one service unhealthy but not all)
    unhealthy_count = sum(1 for c in checks.values() if c.status == "unhealthy")
    if 0 < unhealthy_count < len(checks):
        overall_status = "degraded"

    return ReadyResponse(
        status=overall_status,
        timestamp=datetime.now(UTC).isoformat(),
        version="0.1.0",
        uptime_seconds=uptime,
        checks=checks,
    )


@router.get("/", response_model=ApiInfoResponse)
async def root() -> ApiInfoResponse:
    """Root endpoint with API information."""
    settings = get_settings()
    return ApiInfoResponse(
        name="Findable Score Analyzer API",
        version="0.1.0",
        env=settings.env,
        docs="/docs" if settings.debug else None,
    )
