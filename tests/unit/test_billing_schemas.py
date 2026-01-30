"""Tests for billing schemas."""

import uuid
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from api.schemas.billing import (
    PLAN_LIMITS,
    BillingCycle,
    BillingEventResponse,
    BillingHistoryResponse,
    ChangePlanRequest,
    CheckoutSessionResponse,
    CreateCheckoutSessionRequest,
    CreatePortalSessionRequest,
    FeatureCheckResponse,
    LimitCheckResponse,
    PlanComparisonResponse,
    PlanLimitsResponse,
    PlanTier,
    PortalSessionResponse,
    SubscriptionResponse,
    SubscriptionStatus,
    UsageResponse,
    UsageSummaryResponse,
)


class TestPlanTier:
    """Tests for PlanTier enum."""

    def test_starter_tier(self):
        assert PlanTier.STARTER.value == "starter"

    def test_professional_tier(self):
        assert PlanTier.PROFESSIONAL.value == "professional"

    def test_agency_tier(self):
        assert PlanTier.AGENCY.value == "agency"

    def test_all_tiers_in_limits(self):
        for tier in PlanTier:
            assert tier in PLAN_LIMITS


class TestPlanLimits:
    """Tests for plan limits configuration."""

    def test_starter_limits(self):
        limits = PLAN_LIMITS[PlanTier.STARTER]
        assert limits["sites"] == 1
        assert limits["runs_per_month"] == 10
        assert limits["api_access"] is False
        assert limits["webhook_alerts"] is False

    def test_professional_limits(self):
        limits = PLAN_LIMITS[PlanTier.PROFESSIONAL]
        assert limits["sites"] == 5
        assert limits["runs_per_month"] == 50
        assert limits["api_access"] is True
        assert limits["webhook_alerts"] is True

    def test_agency_limits(self):
        limits = PLAN_LIMITS[PlanTier.AGENCY]
        assert limits["sites"] == 25
        assert limits["runs_per_month"] == 250
        assert limits["priority_support"] is True

    def test_plan_tier_hierarchy(self):
        """Higher tiers should have more resources."""
        starter = PLAN_LIMITS[PlanTier.STARTER]
        pro = PLAN_LIMITS[PlanTier.PROFESSIONAL]
        agency = PLAN_LIMITS[PlanTier.AGENCY]

        assert starter["sites"] < pro["sites"] < agency["sites"]
        assert starter["runs_per_month"] < pro["runs_per_month"] < agency["runs_per_month"]


class TestSubscriptionStatus:
    """Tests for SubscriptionStatus enum."""

    def test_active_status(self):
        assert SubscriptionStatus.ACTIVE.value == "active"

    def test_canceled_status(self):
        assert SubscriptionStatus.CANCELED.value == "canceled"

    def test_past_due_status(self):
        assert SubscriptionStatus.PAST_DUE.value == "past_due"

    def test_trialing_status(self):
        assert SubscriptionStatus.TRIALING.value == "trialing"


class TestBillingCycle:
    """Tests for BillingCycle enum."""

    def test_monthly_cycle(self):
        assert BillingCycle.MONTHLY.value == "monthly"

    def test_yearly_cycle(self):
        assert BillingCycle.YEARLY.value == "yearly"


class TestCreateCheckoutSessionRequest:
    """Tests for checkout session request schema."""

    def test_valid_request(self):
        request = CreateCheckoutSessionRequest(
            plan=PlanTier.PROFESSIONAL,
            billing_cycle=BillingCycle.MONTHLY,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert request.plan == PlanTier.PROFESSIONAL
        assert request.billing_cycle == BillingCycle.MONTHLY

    def test_defaults_to_monthly(self):
        request = CreateCheckoutSessionRequest(
            plan=PlanTier.AGENCY,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
        )
        assert request.billing_cycle == BillingCycle.MONTHLY

    def test_invalid_url(self):
        with pytest.raises(ValidationError):
            CreateCheckoutSessionRequest(
                plan=PlanTier.PROFESSIONAL,
                success_url="not-a-url",
                cancel_url="https://example.com/cancel",
            )


class TestChangePlanRequest:
    """Tests for change plan request schema."""

    def test_valid_request(self):
        request = ChangePlanRequest(
            new_plan=PlanTier.AGENCY,
            billing_cycle=BillingCycle.YEARLY,
        )
        assert request.new_plan == PlanTier.AGENCY
        assert request.billing_cycle == BillingCycle.YEARLY

    def test_optional_billing_cycle(self):
        request = ChangePlanRequest(new_plan=PlanTier.PROFESSIONAL)
        assert request.billing_cycle is None


class TestSubscriptionResponse:
    """Tests for subscription response schema."""

    def test_valid_response(self):
        now = datetime.utcnow()
        response = SubscriptionResponse(
            id=uuid.uuid4(),
            plan="professional",
            status="active",
            billing_cycle="monthly",
            stripe_customer_id="cus_123",
            stripe_subscription_id="sub_123",
            current_period_start=now,
            current_period_end=now + timedelta(days=30),
            cancel_at=None,
            canceled_at=None,
            trial_end=None,
            created_at=now,
        )
        assert response.plan == "professional"
        assert response.status == "active"

    def test_minimal_response(self):
        now = datetime.utcnow()
        response = SubscriptionResponse(
            id=uuid.uuid4(),
            plan="starter",
            status="active",
            billing_cycle="monthly",
            stripe_customer_id=None,
            stripe_subscription_id=None,
            current_period_start=None,
            current_period_end=None,
            cancel_at=None,
            canceled_at=None,
            trial_end=None,
            created_at=now,
        )
        assert response.stripe_customer_id is None


class TestUsageResponse:
    """Tests for usage response schema."""

    def test_valid_response(self):
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
        assert response.sites_remaining == response.sites_limit - response.sites_count
        assert response.runs_remaining == response.runs_limit - response.runs_count


class TestLimitCheckResponse:
    """Tests for limit check response schema."""

    def test_allowed_response(self):
        response = LimitCheckResponse(
            allowed=True,
            current=2,
            limit=5,
            remaining=3,
            message=None,
        )
        assert response.allowed is True
        assert response.message is None

    def test_denied_response(self):
        response = LimitCheckResponse(
            allowed=False,
            current=5,
            limit=5,
            remaining=0,
            message="Site limit reached",
        )
        assert response.allowed is False
        assert response.message is not None


class TestFeatureCheckResponse:
    """Tests for feature check response schema."""

    def test_allowed_feature(self):
        response = FeatureCheckResponse(
            allowed=True,
            required_plan=None,
            message=None,
        )
        assert response.allowed is True

    def test_denied_feature(self):
        response = FeatureCheckResponse(
            allowed=False,
            required_plan="professional",
            message="Requires professional plan",
        )
        assert response.allowed is False
        assert response.required_plan == "professional"


class TestPlanComparisonResponse:
    """Tests for plan comparison response schema."""

    def test_valid_comparison(self):
        response = PlanComparisonResponse(
            starter=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.STARTER]),
            professional=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.PROFESSIONAL]),
            agency=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.AGENCY]),
            current_plan="starter",
        )
        assert response.current_plan == "starter"
        assert response.starter.sites < response.professional.sites


class TestBillingHistoryResponse:
    """Tests for billing history response schema."""

    def test_valid_history(self):
        now = datetime.utcnow()
        events = [
            BillingEventResponse(
                id=uuid.uuid4(),
                event_type="subscription_created",
                stripe_event_id="evt_123",
                data={"plan": "professional"},
                processed=True,
                error=None,
                created_at=now,
            )
        ]
        response = BillingHistoryResponse(
            events=events,
            total=1,
            page=1,
            per_page=20,
        )
        assert len(response.events) == 1
        assert response.total == 1


class TestUsageSummaryResponse:
    """Tests for usage summary response schema."""

    def test_valid_summary(self):
        now = datetime.utcnow()
        response = UsageSummaryResponse(
            id=uuid.uuid4(),
            period_start=now,
            period_end=now + timedelta(days=30),
            sites_count=3,
            runs_count=25,
            snapshots_count=75,
            observations_count=100,
            benchmarks_count=50,
            api_calls_count=500,
            created_at=now,
        )
        assert response.sites_count == 3
        assert response.runs_count == 25
