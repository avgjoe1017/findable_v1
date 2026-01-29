"""Health check endpoints."""

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field
from redis import Redis
from sqlalchemy import text

from api.config import get_settings
from api.database import async_session_maker

router = APIRouter(tags=["Health"])
logger = structlog.get_logger()


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Health status: healthy, degraded, unhealthy")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")


class ReadyResponse(BaseModel):
    """Readiness check response with dependency status."""

    status: str = Field(..., description="Overall status")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    version: str = Field(..., description="API version")
    checks: dict[str, Any] = Field(..., description="Individual dependency checks")


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
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
    )


@router.get("/ready", response_model=ReadyResponse)
async def readiness_check() -> ReadyResponse:
    """
    Readiness check with dependency verification.

    Checks:
    - Database connectivity
    - Redis connectivity
    """
    settings = get_settings()
    checks: dict[str, Any] = {}
    overall_status = "healthy"

    # Check database
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = {"status": "healthy"}
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"

    # Check Redis
    try:
        redis = Redis.from_url(str(settings.redis_url), socket_timeout=2)
        redis.ping()
        redis.close()
        checks["redis"] = {"status": "healthy"}
    except Exception as e:
        logger.warning("Redis health check failed", error=str(e))
        checks["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_status = "unhealthy"

    return ReadyResponse(
        status=overall_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
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
