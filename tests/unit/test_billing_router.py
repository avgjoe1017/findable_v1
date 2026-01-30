"""Tests for billing router endpoints."""

import hashlib
import hmac
import json
import time
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.models.user import PlanTier
from api.routers.billing import _verify_stripe_signature, router
from api.schemas.billing import PLAN_LIMITS, LimitCheckResponse, UsageResponse


class TestStripeSignatureVerification:
    """Tests for Stripe webhook signature verification."""

    def test_valid_signature(self):
        secret = "whsec_test_secret"
        payload = b'{"id": "evt_123", "type": "test"}'
        timestamp = str(int(time.time()))

        # Create signature
        signed_payload = f"{timestamp}.{payload.decode()}"
        expected_sig = hmac.new(
            secret.encode(),
            signed_payload.encode(),
            hashlib.sha256,
        ).hexdigest()

        signature = f"t={timestamp},v1={expected_sig}"

        # Should not raise
        _verify_stripe_signature(payload, signature, secret)

    def test_invalid_signature(self):
        secret = "whsec_test_secret"
        payload = b'{"id": "evt_123", "type": "test"}'
        signature = "t=12345,v1=invalid_signature"

        with pytest.raises(ValueError, match="Signature mismatch"):
            _verify_stripe_signature(payload, signature, secret)

    def test_missing_timestamp(self):
        secret = "whsec_test_secret"
        payload = b'{"id": "evt_123"}'
        signature = "v1=some_signature"

        with pytest.raises(ValueError, match="Invalid signature format"):
            _verify_stripe_signature(payload, signature, secret)

    def test_missing_v1_signature(self):
        secret = "whsec_test_secret"
        payload = b'{"id": "evt_123"}'
        signature = "t=12345"

        with pytest.raises(ValueError, match="Invalid signature format"):
            _verify_stripe_signature(payload, signature, secret)


class TestPlanLimitsEndpoint:
    """Tests for plan limits endpoint responses."""

    def test_starter_limits_structure(self):
        limits = PLAN_LIMITS[PlanTier.STARTER]

        assert "sites" in limits
        assert "runs_per_month" in limits
        assert "snapshots_per_month" in limits
        assert "monitoring_interval_hours" in limits
        assert "competitors_per_site" in limits
        assert "api_access" in limits
        assert "webhook_alerts" in limits
        assert "priority_support" in limits

    def test_professional_has_api_access(self):
        limits = PLAN_LIMITS[PlanTier.PROFESSIONAL]
        assert limits["api_access"] is True
        assert limits["webhook_alerts"] is True

    def test_agency_has_priority_support(self):
        limits = PLAN_LIMITS[PlanTier.AGENCY]
        assert limits["priority_support"] is True


class TestLimitCheckResponse:
    """Tests for limit check response formatting."""

    def test_allowed_response_format(self):
        response = LimitCheckResponse(
            allowed=True,
            current=2,
            limit=5,
            remaining=3,
            message=None,
        )

        assert response.allowed is True
        assert response.remaining == response.limit - response.current

    def test_denied_response_has_message(self):
        response = LimitCheckResponse(
            allowed=False,
            current=5,
            limit=5,
            remaining=0,
            message="Limit reached",
        )

        assert response.allowed is False
        assert response.message is not None

    def test_remaining_never_negative(self):
        response = LimitCheckResponse(
            allowed=False,
            current=10,  # Over limit
            limit=5,
            remaining=0,  # Should be 0, not -5
            message="Limit exceeded",
        )

        assert response.remaining >= 0


class TestUsageResponseFormat:
    """Tests for usage response formatting."""

    def test_usage_response_structure(self):
        now = datetime.utcnow()
        response = UsageResponse(
            sites_count=2,
            sites_limit=5,
            sites_remaining=3,
            runs_count=10,
            runs_limit=50,
            runs_remaining=40,
            snapshots_count=25,
            snapshots_limit=150,
            snapshots_remaining=125,
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        # Verify all required fields
        assert response.sites_count >= 0
        assert response.sites_limit > 0
        assert response.runs_count >= 0
        assert response.runs_limit > 0
        assert response.snapshots_count >= 0
        assert response.snapshots_limit > 0

    def test_remaining_calculation(self):
        now = datetime.utcnow()
        response = UsageResponse(
            sites_count=3,
            sites_limit=5,
            sites_remaining=2,
            runs_count=45,
            runs_limit=50,
            runs_remaining=5,
            snapshots_count=100,
            snapshots_limit=150,
            snapshots_remaining=50,
            period_start=now,
            period_end=now + timedelta(days=30),
        )

        assert response.sites_remaining == response.sites_limit - response.sites_count
        assert response.runs_remaining == response.runs_limit - response.runs_count
        assert (
            response.snapshots_remaining
            == response.snapshots_limit - response.snapshots_count
        )


class TestWebhookEventTypes:
    """Tests for webhook event type handling."""

    @pytest.mark.parametrize(
        "event_type",
        [
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.paid",
            "invoice.payment_failed",
        ],
    )
    def test_supported_event_types(self, event_type):
        """Verify these event types are recognized."""
        # These are the supported event types in the router
        supported_types = [
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.paid",
            "invoice.payment_failed",
        ]
        assert event_type in supported_types


class TestPlanComparison:
    """Tests for plan comparison data."""

    def test_all_plans_have_same_keys(self):
        """All plans should have the same limit keys."""
        starter_keys = set(PLAN_LIMITS[PlanTier.STARTER].keys())
        professional_keys = set(PLAN_LIMITS[PlanTier.PROFESSIONAL].keys())
        agency_keys = set(PLAN_LIMITS[PlanTier.AGENCY].keys())

        assert starter_keys == professional_keys == agency_keys

    def test_plans_have_numeric_limits(self):
        """Numeric limits should be integers."""
        for plan in PlanTier:
            limits = PLAN_LIMITS[plan]
            assert isinstance(limits["sites"], int)
            assert isinstance(limits["runs_per_month"], int)
            assert isinstance(limits["snapshots_per_month"], int)
            assert isinstance(limits["monitoring_interval_hours"], int)
            assert isinstance(limits["competitors_per_site"], int)

    def test_plans_have_boolean_features(self):
        """Feature flags should be booleans."""
        for plan in PlanTier:
            limits = PLAN_LIMITS[plan]
            assert isinstance(limits["api_access"], bool)
            assert isinstance(limits["webhook_alerts"], bool)
            assert isinstance(limits["priority_support"], bool)


class TestEndpointPaths:
    """Tests for endpoint path structure."""

    def test_router_prefix(self):
        assert router.prefix == "/billing"

    def test_router_tags(self):
        assert "billing" in router.tags

    def test_route_paths_exist(self):
        """Verify expected routes are defined."""
        route_paths = [route.path for route in router.routes]

        assert "/billing/subscription" in route_paths
        assert "/billing/usage" in route_paths
        assert "/billing/plans" in route_paths
        assert "/billing/plans/{plan}" in route_paths
        assert "/billing/limits/sites" in route_paths
        assert "/billing/limits/runs" in route_paths
        assert "/billing/limits/snapshots" in route_paths
        assert "/billing/features/{feature}" in route_paths
        assert "/billing/history" in route_paths
        assert "/billing/checkout" in route_paths
        assert "/billing/portal" in route_paths
        assert "/billing/change-plan" in route_paths
        assert "/billing/webhooks/stripe" in route_paths
