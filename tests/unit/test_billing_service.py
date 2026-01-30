"""Tests for billing service."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from api.models import (
    BillingEventType,
    Subscription,
    SubscriptionStatus,
    UsageType,
)
from api.models.user import PlanTier
from api.schemas.billing import PLAN_LIMITS
from api.services.billing_service import BillingService, _plan_rank


class TestPlanRank:
    """Tests for plan ranking function."""

    def test_starter_rank(self):
        assert _plan_rank(PlanTier.STARTER) == 1

    def test_professional_rank(self):
        assert _plan_rank(PlanTier.PROFESSIONAL) == 2

    def test_agency_rank(self):
        assert _plan_rank(PlanTier.AGENCY) == 3

    def test_rank_ordering(self):
        assert (
            _plan_rank(PlanTier.STARTER)
            < _plan_rank(PlanTier.PROFESSIONAL)
            < _plan_rank(PlanTier.AGENCY)
        )


class TestBillingServiceInit:
    """Tests for billing service initialization."""

    def test_init_with_db(self):
        db = MagicMock()
        service = BillingService(db)
        assert service.db == db


class TestGetPlanLimits:
    """Tests for get_plan_limits method."""

    @pytest.mark.asyncio
    async def test_starter_limits(self):
        db = MagicMock()
        service = BillingService(db)
        limits = await service.get_plan_limits(PlanTier.STARTER)

        assert limits.sites == PLAN_LIMITS[PlanTier.STARTER]["sites"]
        assert limits.api_access is False

    @pytest.mark.asyncio
    async def test_professional_limits(self):
        db = MagicMock()
        service = BillingService(db)
        limits = await service.get_plan_limits(PlanTier.PROFESSIONAL)

        assert limits.sites == PLAN_LIMITS[PlanTier.PROFESSIONAL]["sites"]
        assert limits.api_access is True

    @pytest.mark.asyncio
    async def test_agency_limits(self):
        db = MagicMock()
        service = BillingService(db)
        limits = await service.get_plan_limits(PlanTier.AGENCY)

        assert limits.sites == PLAN_LIMITS[PlanTier.AGENCY]["sites"]
        assert limits.priority_support is True


class TestCheckFeatureAccess:
    """Tests for feature access checking."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return BillingService(mock_db)

    @pytest.mark.asyncio
    async def test_api_access_denied_starter(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_feature_access(
                uuid.uuid4(), "api_access"
            )
            assert result.allowed is False
            assert result.required_plan == "professional"

    @pytest.mark.asyncio
    async def test_api_access_allowed_professional(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.PROFESSIONAL
        ):
            result = await service.check_feature_access(
                uuid.uuid4(), "api_access"
            )
            assert result.allowed is True
            assert result.required_plan is None

    @pytest.mark.asyncio
    async def test_webhook_alerts_denied_starter(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_feature_access(
                uuid.uuid4(), "webhook_alerts"
            )
            assert result.allowed is False

    @pytest.mark.asyncio
    async def test_priority_support_denied_professional(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.PROFESSIONAL
        ):
            result = await service.check_feature_access(
                uuid.uuid4(), "priority_support"
            )
            assert result.allowed is False
            assert result.required_plan == "agency"

    @pytest.mark.asyncio
    async def test_priority_support_allowed_agency(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.AGENCY
        ):
            result = await service.check_feature_access(
                uuid.uuid4(), "priority_support"
            )
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_unknown_feature_allowed(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_feature_access(
                uuid.uuid4(), "unknown_feature"
            )
            assert result.allowed is True


class TestCheckMonitoringInterval:
    """Tests for monitoring interval checking."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return BillingService(mock_db)

    @pytest.mark.asyncio
    async def test_starter_weekly_allowed(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_monitoring_interval(uuid.uuid4(), 168)
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_starter_daily_denied(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_monitoring_interval(uuid.uuid4(), 24)
            assert result.allowed is False
            assert "168 hours" in result.message

    @pytest.mark.asyncio
    async def test_professional_daily_allowed(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.PROFESSIONAL
        ):
            result = await service.check_monitoring_interval(uuid.uuid4(), 24)
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_professional_hourly_denied(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.PROFESSIONAL
        ):
            result = await service.check_monitoring_interval(uuid.uuid4(), 6)
            assert result.allowed is False

    @pytest.mark.asyncio
    async def test_agency_frequent_allowed(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.AGENCY
        ):
            result = await service.check_monitoring_interval(uuid.uuid4(), 6)
            assert result.allowed is True


class TestCheckCompetitorsLimit:
    """Tests for competitors limit checking."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        return BillingService(mock_db)

    @pytest.mark.asyncio
    async def test_starter_under_limit(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_competitors_limit(uuid.uuid4(), 2)
            assert result.allowed is True
            assert result.remaining == 1  # 3 - 2

    @pytest.mark.asyncio
    async def test_starter_at_limit(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.STARTER
        ):
            result = await service.check_competitors_limit(uuid.uuid4(), 3)
            assert result.allowed is False
            assert result.remaining == 0

    @pytest.mark.asyncio
    async def test_professional_higher_limit(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.PROFESSIONAL
        ):
            result = await service.check_competitors_limit(uuid.uuid4(), 5)
            assert result.allowed is True
            assert result.remaining == 5  # 10 - 5

    @pytest.mark.asyncio
    async def test_agency_highest_limit(self, service):
        with patch.object(
            service, "get_user_plan", return_value=PlanTier.AGENCY
        ):
            result = await service.check_competitors_limit(uuid.uuid4(), 20)
            assert result.allowed is True
            assert result.remaining == 5  # 25 - 20


class TestUsageTypes:
    """Tests for usage type enum coverage."""

    def test_site_created_type(self):
        assert UsageType.SITE_CREATED.value == "site_created"

    def test_run_started_type(self):
        assert UsageType.RUN_STARTED.value == "run_started"

    def test_snapshot_taken_type(self):
        assert UsageType.SNAPSHOT_TAKEN.value == "snapshot_taken"

    def test_observation_run_type(self):
        assert UsageType.OBSERVATION_RUN.value == "observation_run"

    def test_benchmark_run_type(self):
        assert UsageType.BENCHMARK_RUN.value == "benchmark_run"

    def test_api_call_type(self):
        assert UsageType.API_CALL.value == "api_call"


class TestBillingEventTypes:
    """Tests for billing event type enum coverage."""

    def test_subscription_created(self):
        assert BillingEventType.SUBSCRIPTION_CREATED.value == "subscription_created"

    def test_subscription_updated(self):
        assert BillingEventType.SUBSCRIPTION_UPDATED.value == "subscription_updated"

    def test_subscription_canceled(self):
        assert BillingEventType.SUBSCRIPTION_CANCELED.value == "subscription_canceled"

    def test_payment_succeeded(self):
        assert BillingEventType.PAYMENT_SUCCEEDED.value == "payment_succeeded"

    def test_payment_failed(self):
        assert BillingEventType.PAYMENT_FAILED.value == "payment_failed"

    def test_plan_upgraded(self):
        assert BillingEventType.PLAN_UPGRADED.value == "plan_upgraded"

    def test_plan_downgraded(self):
        assert BillingEventType.PLAN_DOWNGRADED.value == "plan_downgraded"


class TestSubscriptionStatusEnum:
    """Tests for subscription status enum coverage."""

    def test_active(self):
        assert SubscriptionStatus.ACTIVE.value == "active"

    def test_past_due(self):
        assert SubscriptionStatus.PAST_DUE.value == "past_due"

    def test_canceled(self):
        assert SubscriptionStatus.CANCELED.value == "canceled"

    def test_incomplete(self):
        assert SubscriptionStatus.INCOMPLETE.value == "incomplete"

    def test_trialing(self):
        assert SubscriptionStatus.TRIALING.value == "trialing"

    def test_unpaid(self):
        assert SubscriptionStatus.UNPAID.value == "unpaid"

    def test_paused(self):
        assert SubscriptionStatus.PAUSED.value == "paused"
