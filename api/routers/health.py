"""Health check endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    timestamp: str
    version: str


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
    )


@router.get("/")
async def root() -> dict[str, str]:
    """Root endpoint with API info."""
    return {
        "name": "Findable Score Analyzer API",
        "version": "0.1.0",
        "docs": "/docs",
    }
