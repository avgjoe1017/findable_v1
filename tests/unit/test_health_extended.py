"""Extended tests for health check endpoints."""

import pytest
from pydantic import ValidationError

from api.routers.health import (
    ApiInfoResponse,
    DependencyCheck,
    HealthResponse,
    ReadyResponse,
)


class TestHealthResponse:
    """Tests for HealthResponse schema."""

    def test_valid_response(self):
        response = HealthResponse(
            status="healthy",
            timestamp="2026-01-29T12:00:00Z",
            version="0.1.0",
            uptime_seconds=3600,
        )
        assert response.status == "healthy"
        assert response.uptime_seconds == 3600

    def test_requires_status(self):
        with pytest.raises(ValidationError):
            HealthResponse(
                timestamp="2026-01-29T12:00:00Z",
                version="0.1.0",
                uptime_seconds=3600,
            )

    def test_requires_uptime(self):
        with pytest.raises(ValidationError):
            HealthResponse(
                status="healthy",
                timestamp="2026-01-29T12:00:00Z",
                version="0.1.0",
            )


class TestDependencyCheck:
    """Tests for DependencyCheck schema."""

    def test_healthy_check(self):
        check = DependencyCheck(
            status="healthy",
            latency_ms=5.2,
        )
        assert check.status == "healthy"
        assert check.latency_ms == 5.2
        assert check.error is None

    def test_unhealthy_check(self):
        check = DependencyCheck(
            status="unhealthy",
            error="Connection refused",
        )
        assert check.status == "unhealthy"
        assert check.error == "Connection refused"
        assert check.latency_ms is None

    def test_optional_latency(self):
        check = DependencyCheck(status="healthy")
        assert check.latency_ms is None


class TestReadyResponse:
    """Tests for ReadyResponse schema."""

    def test_valid_response(self):
        response = ReadyResponse(
            status="healthy",
            timestamp="2026-01-29T12:00:00Z",
            version="0.1.0",
            uptime_seconds=7200,
            checks={
                "database": DependencyCheck(status="healthy", latency_ms=2.5),
                "redis": DependencyCheck(status="healthy", latency_ms=1.2),
            },
        )
        assert response.status == "healthy"
        assert len(response.checks) == 2
        assert response.checks["database"].status == "healthy"

    def test_degraded_status(self):
        response = ReadyResponse(
            status="degraded",
            timestamp="2026-01-29T12:00:00Z",
            version="0.1.0",
            uptime_seconds=7200,
            checks={
                "database": DependencyCheck(status="healthy", latency_ms=2.5),
                "redis": DependencyCheck(status="unhealthy", error="Timeout"),
            },
        )
        assert response.status == "degraded"
        assert response.checks["redis"].status == "unhealthy"

    def test_unhealthy_status(self):
        response = ReadyResponse(
            status="unhealthy",
            timestamp="2026-01-29T12:00:00Z",
            version="0.1.0",
            uptime_seconds=7200,
            checks={
                "database": DependencyCheck(status="unhealthy", error="Connection refused"),
                "redis": DependencyCheck(status="unhealthy", error="Timeout"),
            },
        )
        assert response.status == "unhealthy"


class TestApiInfoResponse:
    """Tests for ApiInfoResponse schema."""

    def test_valid_response(self):
        response = ApiInfoResponse(
            name="Findable Score Analyzer API",
            version="0.1.0",
            env="development",
            docs="/docs",
        )
        assert response.name == "Findable Score Analyzer API"
        assert response.docs == "/docs"

    def test_production_no_docs(self):
        response = ApiInfoResponse(
            name="Findable Score Analyzer API",
            version="0.1.0",
            env="production",
            docs=None,
        )
        assert response.docs is None


class TestHealthStatusValues:
    """Tests for health status value conventions."""

    def test_valid_health_statuses(self):
        # All valid status values
        valid_statuses = ["healthy", "degraded", "unhealthy"]

        for status in valid_statuses:
            response = HealthResponse(
                status=status,
                timestamp="2026-01-29T12:00:00Z",
                version="0.1.0",
                uptime_seconds=0,
            )
            assert response.status == status

    def test_valid_dependency_statuses(self):
        # All valid dependency status values
        valid_statuses = ["healthy", "unhealthy"]

        for status in valid_statuses:
            check = DependencyCheck(status=status)
            assert check.status == status


class TestUptimeTracking:
    """Tests for uptime tracking."""

    def test_uptime_is_positive(self):
        response = HealthResponse(
            status="healthy",
            timestamp="2026-01-29T12:00:00Z",
            version="0.1.0",
            uptime_seconds=0,
        )
        assert response.uptime_seconds >= 0

    def test_uptime_can_be_large(self):
        # 30 days in seconds
        uptime = 30 * 24 * 60 * 60
        response = HealthResponse(
            status="healthy",
            timestamp="2026-01-29T12:00:00Z",
            version="0.1.0",
            uptime_seconds=uptime,
        )
        assert response.uptime_seconds == uptime


class TestLatencyTracking:
    """Tests for latency tracking in health checks."""

    def test_latency_precision(self):
        check = DependencyCheck(
            status="healthy",
            latency_ms=1.234567,
        )
        assert check.latency_ms == 1.234567

    def test_zero_latency(self):
        check = DependencyCheck(
            status="healthy",
            latency_ms=0.0,
        )
        assert check.latency_ms == 0.0

    def test_high_latency(self):
        # 5 seconds in ms
        check = DependencyCheck(
            status="healthy",
            latency_ms=5000.0,
        )
        assert check.latency_ms == 5000.0
