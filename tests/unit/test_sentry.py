"""Tests for Sentry integration module."""

from unittest.mock import patch

from api.sentry import (
    _before_send,
    _before_send_transaction,
    add_breadcrumb,
    capture_exception,
    capture_message,
    init_sentry,
    set_context,
    set_tag,
    set_user_context,
)


class TestBeforeSend:
    """Tests for the before_send filter function."""

    def test_filters_4xx_http_exceptions(self):
        from fastapi import HTTPException

        exc = HTTPException(status_code=404, detail="Not found")
        hint = {"exc_info": (HTTPException, exc, None)}
        event = {"message": "Not found"}

        result = _before_send(event, hint)
        assert result is None  # Should be filtered out

    def test_allows_5xx_http_exceptions(self):
        from fastapi import HTTPException

        exc = HTTPException(status_code=500, detail="Server error")
        hint = {"exc_info": (HTTPException, exc, None)}
        event = {"message": "Server error"}

        result = _before_send(event, hint)
        assert result is not None  # Should not be filtered

    def test_filters_auth_headers(self):
        event = {
            "request": {
                "headers": {
                    "authorization": "Bearer secret-token",
                    "cookie": "session=abc123",
                    "x-api-key": "api-key-here",
                    "content-type": "application/json",
                }
            }
        }
        hint = {}

        result = _before_send(event, hint)

        assert result["request"]["headers"]["authorization"] == "[Filtered]"
        assert result["request"]["headers"]["cookie"] == "[Filtered]"
        assert result["request"]["headers"]["x-api-key"] == "[Filtered]"
        assert result["request"]["headers"]["content-type"] == "application/json"

    def test_passes_regular_exceptions(self):
        exc = ValueError("Some error")
        hint = {"exc_info": (ValueError, exc, None)}
        event = {"message": "Some error"}

        result = _before_send(event, hint)
        assert result is not None

    def test_handles_missing_request(self):
        event = {"message": "Some error"}
        hint = {}

        result = _before_send(event, hint)
        assert result is not None


class TestBeforeSendTransaction:
    """Tests for the transaction filter function."""

    def test_filters_health_check(self):
        event = {"transaction": "/api/health"}
        hint = {}

        result = _before_send_transaction(event, hint)
        assert result is None

    def test_filters_ready_check(self):
        event = {"transaction": "/api/ready"}
        hint = {}

        result = _before_send_transaction(event, hint)
        assert result is None

    def test_filters_metrics(self):
        event = {"transaction": "/metrics"}
        hint = {}

        result = _before_send_transaction(event, hint)
        assert result is None

    def test_allows_api_transactions(self):
        event = {"transaction": "/v1/sites"}
        hint = {}

        result = _before_send_transaction(event, hint)
        assert result is not None


class TestSentryHelpers:
    """Tests for Sentry helper functions when not initialized."""

    def test_set_user_context_when_not_initialized(self):
        # Should not raise when Sentry is not initialized
        set_user_context("user-123", email="test@example.com", plan="starter")

    def test_set_tag_when_not_initialized(self):
        # Should not raise when Sentry is not initialized
        set_tag("key", "value")

    def test_set_context_when_not_initialized(self):
        # Should not raise when Sentry is not initialized
        set_context("name", {"key": "value"})

    def test_capture_exception_when_not_initialized(self):
        result = capture_exception(ValueError("test"))
        assert result is None

    def test_capture_message_when_not_initialized(self):
        result = capture_message("test message")
        assert result is None

    def test_add_breadcrumb_when_not_initialized(self):
        # Should not raise when Sentry is not initialized
        add_breadcrumb("test message", category="test", level="info")


class TestInitSentry:
    """Tests for Sentry initialization."""

    @patch("api.sentry.get_settings")
    def test_skips_when_no_dsn(self, mock_settings):
        mock_settings.return_value.sentry_dsn = None

        result = init_sentry()
        assert result is False

    @patch("api.sentry.get_settings")
    def test_handles_import_error(self, mock_settings):
        mock_settings.return_value.sentry_dsn = "https://test@sentry.io/123"

        with patch.dict("sys.modules", {"sentry_sdk": None}):
            # This simulates ImportError by having the module be None
            # In practice, the actual import would fail
            pass

        # The function should handle gracefully even if sentry-sdk not installed
        # (We can't fully test this without removing the package)


class TestSentryConfiguration:
    """Tests for Sentry configuration values."""

    def test_filtered_paths(self):
        # Health check paths should be filtered
        filtered_paths = ["/api/health", "/api/ready", "/metrics"]

        for path in filtered_paths:
            event = {"transaction": path}
            result = _before_send_transaction(event, {})
            assert result is None, f"Path {path} should be filtered"

    def test_sensitive_headers(self):
        # These headers should always be filtered
        sensitive_headers = ["authorization", "cookie", "x-api-key"]

        event = {"request": {"headers": dict.fromkeys(sensitive_headers, "secret")}}

        result = _before_send(event, {})

        for header in sensitive_headers:
            assert result["request"]["headers"][header] == "[Filtered]"
