"""Prometheus metrics for monitoring and observability."""

from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware

# Request metrics
REQUEST_COUNT = Counter(
    "findable_http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

REQUEST_LATENCY = Histogram(
    "findable_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0],
)

REQUEST_IN_PROGRESS = Gauge(
    "findable_http_requests_in_progress",
    "HTTP requests currently being processed",
    ["method", "endpoint"],
)

# Error metrics
ERROR_COUNT = Counter(
    "findable_errors_total",
    "Total application errors",
    ["error_type", "endpoint"],
)

# Business metrics
SITES_TOTAL = Gauge(
    "findable_sites_total",
    "Total number of sites",
)

RUNS_TOTAL = Counter(
    "findable_runs_total",
    "Total audit runs started",
    ["status"],
)

RUNS_IN_PROGRESS = Gauge(
    "findable_runs_in_progress",
    "Audit runs currently in progress",
)

SNAPSHOTS_TOTAL = Counter(
    "findable_snapshots_total",
    "Total monitoring snapshots taken",
    ["trigger"],
)

ALERTS_TOTAL = Counter(
    "findable_alerts_total",
    "Total alerts created",
    ["type", "severity"],
)

OBSERVATIONS_TOTAL = Counter(
    "findable_observations_total",
    "Total LLM observations made",
    ["provider", "status"],
)

# Usage metrics
API_CALLS_TOTAL = Counter(
    "findable_api_calls_total",
    "Total API calls by endpoint",
    ["endpoint", "plan"],
)

# Job metrics
JOB_QUEUE_SIZE = Gauge(
    "findable_job_queue_size",
    "Number of jobs in queue",
    ["queue"],
)

JOB_PROCESSING_TIME = Histogram(
    "findable_job_processing_seconds",
    "Job processing time in seconds",
    ["job_type"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0],
)

# Public audit adoption metrics
PUBLIC_AUDITS_TOTAL = Counter("findable_public_audits_total", "Total public audits started")
EMAIL_CAPTURES_TOTAL = Counter("findable_email_captures_total", "Email capture conversions")
SHARES_TOTAL = Counter("findable_shares_total", "Social shares", ["platform"])
RETURN_AUDITS_TOTAL = Counter("findable_return_audits_total", "Return audits from same IP")


def get_metrics() -> bytes:
    """Generate Prometheus metrics output."""
    metrics: bytes = generate_latest()
    return metrics


def get_metrics_content_type() -> str:
    """Get the content type for Prometheus metrics."""
    content_type: str = CONTENT_TYPE_LATEST
    return content_type


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""

    # Paths to exclude from metrics
    EXCLUDE_PATHS = {"/metrics", "/api/health", "/api/ready", "/favicon.ico"}

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Skip metrics for excluded paths
        if request.url.path in self.EXCLUDE_PATHS:
            return await call_next(request)  # type: ignore[return-value]

        method = request.method
        # Normalize endpoint path (remove IDs)
        endpoint = self._normalize_path(request.url.path)

        # Track in-progress requests
        REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()

        start_time = time.perf_counter()

        try:
            response = await call_next(request)  # type: ignore[return-value]
            status_code = str(response.status_code)

            # Record metrics
            REQUEST_COUNT.labels(
                method=method,
                endpoint=endpoint,
                status_code=status_code,
            ).inc()

            duration = time.perf_counter() - start_time
            REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

            return response

        except Exception as e:
            # Record error
            ERROR_COUNT.labels(
                error_type=type(e).__name__,
                endpoint=endpoint,
            ).inc()
            raise

        finally:
            REQUEST_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()

    def _normalize_path(self, path: str) -> str:
        """Normalize path by replacing UUIDs and IDs with placeholders."""
        import re

        # Replace UUIDs
        path = re.sub(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "{id}",
            path,
            flags=re.IGNORECASE,
        )
        # Replace numeric IDs
        path = re.sub(r"/\d+(/|$)", r"/{id}\1", path)
        return path


# Helper functions for recording business metrics


def record_site_created() -> None:
    """Record a site creation."""
    SITES_TOTAL.inc()


def record_site_deleted() -> None:
    """Record a site deletion."""
    SITES_TOTAL.dec()


def record_run_started() -> None:
    """Record a run started."""
    RUNS_TOTAL.labels(status="started").inc()
    RUNS_IN_PROGRESS.inc()


def record_run_completed(success: bool = True) -> None:
    """Record a run completed."""
    RUNS_TOTAL.labels(status="completed" if success else "failed").inc()
    RUNS_IN_PROGRESS.dec()


def record_snapshot_taken(trigger: str) -> None:
    """Record a snapshot taken."""
    SNAPSHOTS_TOTAL.labels(trigger=trigger).inc()


def record_alert_created(alert_type: str, severity: str) -> None:
    """Record an alert created."""
    ALERTS_TOTAL.labels(type=alert_type, severity=severity).inc()


def record_observation(provider: str, success: bool = True) -> None:
    """Record an LLM observation."""
    OBSERVATIONS_TOTAL.labels(
        provider=provider,
        status="success" if success else "failed",
    ).inc()


def record_api_call(endpoint: str, plan: str) -> None:
    """Record an API call."""
    API_CALLS_TOTAL.labels(endpoint=endpoint, plan=plan).inc()


def update_queue_size(queue: str, size: int) -> None:
    """Update job queue size."""
    JOB_QUEUE_SIZE.labels(queue=queue).set(size)


def record_job_duration(job_type: str, duration: float) -> None:
    """Record job processing duration."""
    JOB_PROCESSING_TIME.labels(job_type=job_type).observe(duration)


def record_public_audit() -> None:
    """Record a public audit started."""
    PUBLIC_AUDITS_TOTAL.inc()


def record_email_capture() -> None:
    """Record an email capture conversion."""
    EMAIL_CAPTURES_TOTAL.inc()


def record_share(platform: str) -> None:
    """Record a social share."""
    SHARES_TOTAL.labels(platform=platform).inc()


def record_return_audit() -> None:
    """Record a return audit from same IP."""
    RETURN_AUDITS_TOTAL.inc()
