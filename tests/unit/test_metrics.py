"""Tests for metrics module."""

import re
from unittest.mock import MagicMock, patch

import pytest

from api.metrics import (
    ERROR_COUNT,
    REQUEST_COUNT,
    REQUEST_IN_PROGRESS,
    REQUEST_LATENCY,
    MetricsMiddleware,
    get_metrics,
    get_metrics_content_type,
    record_alert_created,
    record_api_call,
    record_job_duration,
    record_observation,
    record_run_completed,
    record_run_started,
    record_site_created,
    record_site_deleted,
    record_snapshot_taken,
    update_queue_size,
)


class TestMetricsOutput:
    """Tests for metrics output generation."""

    def test_get_metrics_returns_bytes(self):
        output = get_metrics()
        assert isinstance(output, bytes)

    def test_get_metrics_content_type(self):
        content_type = get_metrics_content_type()
        assert "text/plain" in content_type or "openmetrics" in content_type

    def test_get_metrics_contains_custom_metrics(self):
        output = get_metrics().decode("utf-8")
        assert "findable_http_requests_total" in output
        assert "findable_http_request_duration_seconds" in output


class TestMetricsMiddleware:
    """Tests for metrics middleware."""

    @pytest.fixture
    def middleware(self):
        app = MagicMock()
        return MetricsMiddleware(app)

    def test_normalize_path_uuid(self, middleware):
        path = "/v1/sites/550e8400-e29b-41d4-a716-446655440000/runs"
        normalized = middleware._normalize_path(path)
        assert normalized == "/v1/sites/{id}/runs"

    def test_normalize_path_numeric_id(self, middleware):
        path = "/v1/reports/12345"
        normalized = middleware._normalize_path(path)
        assert normalized == "/v1/reports/{id}"

    def test_normalize_path_no_id(self, middleware):
        path = "/v1/sites"
        normalized = middleware._normalize_path(path)
        assert normalized == "/v1/sites"

    def test_normalize_path_multiple_uuids(self, middleware):
        path = "/v1/sites/550e8400-e29b-41d4-a716-446655440000/runs/660e8400-e29b-41d4-a716-446655440001"
        normalized = middleware._normalize_path(path)
        assert normalized == "/v1/sites/{id}/runs/{id}"

    def test_exclude_paths(self, middleware):
        assert "/metrics" in middleware.EXCLUDE_PATHS
        assert "/api/health" in middleware.EXCLUDE_PATHS
        assert "/api/ready" in middleware.EXCLUDE_PATHS


class TestBusinessMetrics:
    """Tests for business metric recording functions."""

    def test_record_site_created(self):
        # Should not raise
        record_site_created()

    def test_record_site_deleted(self):
        # Should not raise
        record_site_deleted()

    def test_record_run_started(self):
        # Should not raise
        record_run_started()

    def test_record_run_completed_success(self):
        # Should not raise
        record_run_completed(success=True)

    def test_record_run_completed_failure(self):
        # Should not raise
        record_run_completed(success=False)

    def test_record_snapshot_taken(self):
        # Should not raise
        record_snapshot_taken(trigger="scheduled_weekly")

    def test_record_alert_created(self):
        # Should not raise
        record_alert_created(alert_type="score_drop", severity="warning")

    def test_record_observation_success(self):
        # Should not raise
        record_observation(provider="openrouter", success=True)

    def test_record_observation_failure(self):
        # Should not raise
        record_observation(provider="openrouter", success=False)

    def test_record_api_call(self):
        # Should not raise
        record_api_call(endpoint="/v1/sites", plan="professional")

    def test_update_queue_size(self):
        # Should not raise
        update_queue_size(queue="findable-default", size=10)

    def test_record_job_duration(self):
        # Should not raise
        record_job_duration(job_type="audit", duration=15.5)


class TestMetricLabels:
    """Tests for metric label validation."""

    def test_request_count_labels(self):
        # Verify labels are correctly defined
        assert REQUEST_COUNT._labelnames == ("method", "endpoint", "status_code")

    def test_request_latency_labels(self):
        assert REQUEST_LATENCY._labelnames == ("method", "endpoint")

    def test_request_in_progress_labels(self):
        assert REQUEST_IN_PROGRESS._labelnames == ("method", "endpoint")

    def test_error_count_labels(self):
        assert ERROR_COUNT._labelnames == ("error_type", "endpoint")


class TestHistogramBuckets:
    """Tests for histogram bucket configuration."""

    def test_request_latency_buckets(self):
        # Verify buckets are appropriate for HTTP requests
        buckets = REQUEST_LATENCY._upper_bounds
        assert 0.005 in buckets  # 5ms
        assert 0.1 in buckets  # 100ms
        assert 1.0 in buckets  # 1s
        assert 10.0 in buckets  # 10s
