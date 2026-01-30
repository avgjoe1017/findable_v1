"""Tests for middleware components."""

import time
from unittest.mock import MagicMock

import pytest

from api.middleware import (
    AUTH_RATE_LIMITS,
    PLAN_RATE_LIMITS,
    RateLimitBucket,
    RateLimitConfig,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
)


class TestRateLimitConfig:
    """Tests for rate limit configuration."""

    def test_default_config(self):
        config = RateLimitConfig()
        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 1000
        assert config.burst_size == 10

    def test_custom_config(self):
        config = RateLimitConfig(
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_size=20,
        )
        assert config.requests_per_minute == 100
        assert config.requests_per_hour == 2000
        assert config.burst_size == 20


class TestRateLimitBucket:
    """Tests for rate limit bucket."""

    def test_default_bucket(self):
        bucket = RateLimitBucket()
        assert bucket.tokens == 0.0
        assert bucket.last_update > 0

    def test_bucket_with_tokens(self):
        bucket = RateLimitBucket(tokens=5.0)
        assert bucket.tokens == 5.0


class TestPlanRateLimits:
    """Tests for plan-based rate limits."""

    def test_starter_limits(self):
        limits = PLAN_RATE_LIMITS["starter"]
        assert limits.requests_per_minute == 30
        assert limits.requests_per_hour == 500

    def test_professional_limits(self):
        limits = PLAN_RATE_LIMITS["professional"]
        assert limits.requests_per_minute == 120
        assert limits.requests_per_hour == 5000

    def test_agency_limits(self):
        limits = PLAN_RATE_LIMITS["agency"]
        assert limits.requests_per_minute == 300
        assert limits.requests_per_hour == 20000

    def test_agency_higher_than_professional(self):
        agency = PLAN_RATE_LIMITS["agency"]
        pro = PLAN_RATE_LIMITS["professional"]
        assert agency.requests_per_minute > pro.requests_per_minute

    def test_professional_higher_than_starter(self):
        pro = PLAN_RATE_LIMITS["professional"]
        starter = PLAN_RATE_LIMITS["starter"]
        assert pro.requests_per_minute > starter.requests_per_minute


class TestAuthRateLimits:
    """Tests for auth endpoint rate limits."""

    def test_auth_limits_stricter(self):
        # Auth limits should be stricter than starter
        starter = PLAN_RATE_LIMITS["starter"]
        assert AUTH_RATE_LIMITS.requests_per_minute < starter.requests_per_minute

    def test_auth_limits_values(self):
        assert AUTH_RATE_LIMITS.requests_per_minute == 10
        assert AUTH_RATE_LIMITS.requests_per_hour == 50
        assert AUTH_RATE_LIMITS.burst_size == 5


class TestRateLimitMiddleware:
    """Tests for rate limit middleware."""

    @pytest.fixture
    def middleware(self):
        app = MagicMock()
        return RateLimitMiddleware(app, enabled=True)

    @pytest.fixture
    def disabled_middleware(self):
        app = MagicMock()
        return RateLimitMiddleware(app, enabled=False)

    def test_exclude_paths(self, middleware):
        assert "/api/health" in middleware.EXCLUDE_PATHS
        assert "/api/ready" in middleware.EXCLUDE_PATHS
        assert "/metrics" in middleware.EXCLUDE_PATHS

    def test_auth_paths(self, middleware):
        assert "/v1/auth/login" in middleware.AUTH_PATHS
        assert "/v1/auth/register" in middleware.AUTH_PATHS
        assert "/v1/auth/forgot-password" in middleware.AUTH_PATHS

    def test_check_rate_limit_allowed(self, middleware):
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        buckets = {"test": RateLimitBucket(tokens=5.0, last_update=time.time())}

        allowed, retry_after = middleware._check_rate_limit("test", config, buckets)
        assert allowed is True
        assert retry_after == 0

    def test_check_rate_limit_denied(self, middleware):
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        buckets = {"test": RateLimitBucket(tokens=0.0, last_update=time.time())}

        allowed, retry_after = middleware._check_rate_limit("test", config, buckets)
        assert allowed is False
        assert retry_after > 0

    def test_check_rate_limit_refills(self, middleware):
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        # Set last update to 2 seconds ago
        past_time = time.time() - 2.0
        buckets = {"test": RateLimitBucket(tokens=0.0, last_update=past_time)}

        allowed, retry_after = middleware._check_rate_limit("test", config, buckets)
        # Should have refilled some tokens (2 seconds * 1 token/second)
        assert allowed is True

    def test_get_client_ip_direct(self, middleware):
        request = MagicMock()
        request.headers.get.return_value = None
        request.client.host = "192.168.1.1"

        ip = middleware._get_client_ip(request)
        assert ip == "192.168.1.1"

    def test_get_client_ip_forwarded(self, middleware):
        request = MagicMock()
        request.headers.get.return_value = "10.0.0.1, 192.168.1.1"

        ip = middleware._get_client_ip(request)
        assert ip == "10.0.0.1"

    def test_get_user_id_none(self, middleware):
        request = MagicMock()
        request.state = MagicMock(spec=[])  # No user_id attribute

        user_id = middleware._get_user_id(request)
        assert user_id is None

    def test_get_user_id_present(self, middleware):
        request = MagicMock()
        request.state.user_id = "user-123"

        user_id = middleware._get_user_id(request)
        assert user_id == "user-123"

    def test_get_user_plan_default(self, middleware):
        request = MagicMock()
        request.state = MagicMock(spec=[])  # No user_plan attribute

        plan = middleware._get_user_plan(request)
        assert plan == "starter"

    def test_get_user_plan_present(self, middleware):
        request = MagicMock()
        request.state.user_plan = "professional"

        plan = middleware._get_user_plan(request)
        assert plan == "professional"

    def test_rate_limit_response(self, middleware):
        response = middleware._rate_limit_response(retry_after=30)
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "30"


class TestSecurityHeadersMiddleware:
    """Tests for security headers middleware."""

    @pytest.fixture
    def middleware(self):
        app = MagicMock()
        return SecurityHeadersMiddleware(app)

    @pytest.mark.asyncio
    async def test_adds_content_type_options(self, middleware):
        request = MagicMock()
        request.url.path = "/v1/sites"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert result.headers["X-Content-Type-Options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_adds_frame_options(self, middleware):
        request = MagicMock()
        request.url.path = "/v1/sites"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert result.headers["X-Frame-Options"] == "DENY"

    @pytest.mark.asyncio
    async def test_adds_xss_protection(self, middleware):
        request = MagicMock()
        request.url.path = "/v1/sites"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert "X-XSS-Protection" in result.headers

    @pytest.mark.asyncio
    async def test_adds_referrer_policy(self, middleware):
        request = MagicMock()
        request.url.path = "/v1/sites"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert "strict-origin" in result.headers["Referrer-Policy"]

    @pytest.mark.asyncio
    async def test_adds_permissions_policy(self, middleware):
        request = MagicMock()
        request.url.path = "/v1/sites"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert "Permissions-Policy" in result.headers
        assert "camera=()" in result.headers["Permissions-Policy"]

    @pytest.mark.asyncio
    async def test_adds_csp_for_api(self, middleware):
        request = MagicMock()
        request.url.path = "/v1/sites"

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        assert "Content-Security-Policy" in result.headers

    @pytest.mark.asyncio
    async def test_no_csp_for_web_pages(self, middleware):
        request = MagicMock()
        request.url.path = "/sites/new"  # Web page, not API

        response = MagicMock()
        response.headers = {}

        async def call_next(req):
            return response

        result = await middleware.dispatch(request, call_next)
        # CSP should not be added for non-API paths
        assert "Content-Security-Policy" not in result.headers
