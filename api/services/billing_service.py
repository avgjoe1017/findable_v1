"""Billing service for plan enforcement and usage tracking."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import (
    BillingEvent,
    BillingEventType,
    Run,
    Site,
    Snapshot,
    Subscription,
    SubscriptionStatus,
    UsageRecord,
    UsageSummary,
    UsageType,
    User,
)
from api.models.user import PlanTier
from api.schemas.billing import (
    PLAN_LIMITS,
    FeatureCheckResponse,
    LimitCheckResponse,
    PlanLimitsResponse,
    UsageResponse,
)

logger = structlog.get_logger(__name__)


class BillingService:
    """Service for billing, plan enforcement, and usage tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Plan and subscription methods

    async def get_user_subscription(self, user_id: uuid.UUID) -> Subscription | None:
        """Get user's subscription."""
        result = await self.db.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_subscription(self, user_id: uuid.UUID) -> Subscription:
        """Get or create a subscription for a user."""
        subscription = await self.get_user_subscription(user_id)

        if not subscription:
            # Create starter subscription
            subscription = Subscription(
                user_id=user_id,
                plan=PlanTier.STARTER.value,
                status=SubscriptionStatus.ACTIVE.value,
                billing_cycle="monthly",
                current_period_start=datetime.now(UTC),
                current_period_end=datetime.now(UTC) + timedelta(days=30),
            )
            self.db.add(subscription)
            await self.db.flush()
            await self.db.refresh(subscription)

            logger.info(
                "subscription_created",
                user_id=str(user_id),
                plan=PlanTier.STARTER.value,
            )

        return subscription

    async def get_user_plan(self, user_id: uuid.UUID) -> PlanTier:
        """Get user's current plan tier."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if user and user.plan:
            try:
                return PlanTier(user.plan)
            except ValueError:
                pass

        return PlanTier.STARTER

    async def get_plan_limits(self, plan: PlanTier) -> PlanLimitsResponse:
        """Get limits for a specific plan."""
        limits = PLAN_LIMITS[plan]
        return PlanLimitsResponse(**limits)

    # Usage tracking methods

    async def record_usage(
        self,
        user_id: uuid.UUID,
        usage_type: UsageType,
        quantity: int = 1,
        site_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
        metadata: dict | None = None,
    ) -> UsageRecord:
        """Record a usage event."""
        # Get current billing period
        subscription = await self.get_or_create_subscription(user_id)

        period_start = subscription.current_period_start or datetime.now(UTC)
        period_end = subscription.current_period_end or (
            datetime.now(UTC) + timedelta(days=30)
        )

        usage = UsageRecord(
            user_id=user_id,
            usage_type=usage_type.value,
            quantity=quantity,
            site_id=site_id,
            run_id=run_id,
            metadata=metadata,
            period_start=period_start,
            period_end=period_end,
        )
        self.db.add(usage)
        await self.db.flush()

        logger.debug(
            "usage_recorded",
            user_id=str(user_id),
            usage_type=usage_type.value,
            quantity=quantity,
        )

        return usage

    async def get_current_usage(self, user_id: uuid.UUID) -> UsageResponse:
        """Get current period usage for a user."""
        subscription = await self.get_or_create_subscription(user_id)
        plan = await self.get_user_plan(user_id)
        limits = PLAN_LIMITS[plan]

        period_start = subscription.current_period_start or datetime.now(UTC)
        period_end = subscription.current_period_end or (
            datetime.now(UTC) + timedelta(days=30)
        )

        # Count sites (current total, not period-based)
        sites_result = await self.db.execute(
            select(func.count()).where(Site.user_id == user_id)
        )
        sites_count = sites_result.scalar_one()

        # Count runs in current period
        runs_result = await self.db.execute(
            select(func.count()).where(
                Run.site_id.in_(select(Site.id).where(Site.user_id == user_id)),
                Run.created_at >= period_start,
                Run.created_at < period_end,
            )
        )
        runs_count = runs_result.scalar_one()

        # Count snapshots in current period
        snapshots_result = await self.db.execute(
            select(func.count()).where(
                Snapshot.site_id.in_(select(Site.id).where(Site.user_id == user_id)),
                Snapshot.created_at >= period_start,
                Snapshot.created_at < period_end,
            )
        )
        snapshots_count = snapshots_result.scalar_one()

        return UsageResponse(
            sites_count=sites_count,
            sites_limit=limits["sites"],
            sites_remaining=max(0, limits["sites"] - sites_count),
            runs_count=runs_count,
            runs_limit=limits["runs_per_month"],
            runs_remaining=max(0, limits["runs_per_month"] - runs_count),
            snapshots_count=snapshots_count,
            snapshots_limit=limits["snapshots_per_month"],
            snapshots_remaining=max(0, limits["snapshots_per_month"] - snapshots_count),
            period_start=period_start,
            period_end=period_end,
        )

    # Limit checking methods

    async def check_site_limit(self, user_id: uuid.UUID) -> LimitCheckResponse:
        """Check if user can create a new site."""
        usage = await self.get_current_usage(user_id)

        allowed = usage.sites_count < usage.sites_limit
        message = None if allowed else f"Site limit reached ({usage.sites_limit} sites)"

        return LimitCheckResponse(
            allowed=allowed,
            current=usage.sites_count,
            limit=usage.sites_limit,
            remaining=usage.sites_remaining,
            message=message,
        )

    async def check_run_limit(self, user_id: uuid.UUID) -> LimitCheckResponse:
        """Check if user can start a new run."""
        usage = await self.get_current_usage(user_id)

        allowed = usage.runs_count < usage.runs_limit
        message = (
            None
            if allowed
            else f"Monthly run limit reached ({usage.runs_limit} runs)"
        )

        return LimitCheckResponse(
            allowed=allowed,
            current=usage.runs_count,
            limit=usage.runs_limit,
            remaining=usage.runs_remaining,
            message=message,
        )

    async def check_snapshot_limit(self, user_id: uuid.UUID) -> LimitCheckResponse:
        """Check if user can take a snapshot."""
        usage = await self.get_current_usage(user_id)

        allowed = usage.snapshots_count < usage.snapshots_limit
        message = (
            None
            if allowed
            else f"Monthly snapshot limit reached ({usage.snapshots_limit} snapshots)"
        )

        return LimitCheckResponse(
            allowed=allowed,
            current=usage.snapshots_count,
            limit=usage.snapshots_limit,
            remaining=usage.snapshots_remaining,
            message=message,
        )

    async def check_competitors_limit(
        self, user_id: uuid.UUID, current_count: int
    ) -> LimitCheckResponse:
        """Check if user can add another competitor."""
        plan = await self.get_user_plan(user_id)
        limits = PLAN_LIMITS[plan]
        limit = limits["competitors_per_site"]

        allowed = current_count < limit
        message = (
            None if allowed else f"Competitor limit reached ({limit} competitors)"
        )

        return LimitCheckResponse(
            allowed=allowed,
            current=current_count,
            limit=limit,
            remaining=max(0, limit - current_count),
            message=message,
        )

    async def check_monitoring_interval(
        self, user_id: uuid.UUID, requested_hours: int
    ) -> LimitCheckResponse:
        """Check if user can use the requested monitoring interval."""
        plan = await self.get_user_plan(user_id)
        limits = PLAN_LIMITS[plan]
        min_interval = limits["monitoring_interval_hours"]

        allowed = requested_hours >= min_interval
        message = (
            None
            if allowed
            else f"Minimum monitoring interval for your plan is {min_interval} hours"
        )

        return LimitCheckResponse(
            allowed=allowed,
            current=requested_hours,
            limit=min_interval,
            remaining=0,  # Not applicable
            message=message,
        )

    # Feature access methods

    async def check_feature_access(
        self, user_id: uuid.UUID, feature: str
    ) -> FeatureCheckResponse:
        """Check if user has access to a feature."""
        plan = await self.get_user_plan(user_id)
        limits = PLAN_LIMITS[plan]

        feature_map = {
            "api_access": ("api_access", PlanTier.PROFESSIONAL),
            "webhook_alerts": ("webhook_alerts", PlanTier.PROFESSIONAL),
            "priority_support": ("priority_support", PlanTier.AGENCY),
        }

        if feature not in feature_map:
            return FeatureCheckResponse(
                allowed=True,
                message="Unknown feature, allowing by default",
            )

        feature_key, required_plan = feature_map[feature]
        allowed = limits.get(feature_key, False)

        return FeatureCheckResponse(
            allowed=allowed,
            required_plan=required_plan.value if not allowed else None,
            message=None if allowed else f"Requires {required_plan.value} plan or higher",
        )

    # Billing event methods

    async def log_billing_event(
        self,
        user_id: uuid.UUID,
        event_type: BillingEventType,
        stripe_event_id: str | None = None,
        data: dict | None = None,
        processed: bool = True,
        error: str | None = None,
    ) -> BillingEvent:
        """Log a billing event."""
        event = BillingEvent(
            user_id=user_id,
            event_type=event_type.value,
            stripe_event_id=stripe_event_id,
            data=data,
            processed=processed,
            error=error,
        )
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)

        logger.info(
            "billing_event_logged",
            user_id=str(user_id),
            event_type=event_type.value,
            stripe_event_id=stripe_event_id,
        )

        return event

    async def get_billing_history(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[BillingEvent], int]:
        """Get billing event history for a user."""
        # Get total count
        count_result = await self.db.execute(
            select(func.count()).where(BillingEvent.user_id == user_id)
        )
        total = count_result.scalar_one()

        # Get paginated events
        offset = (page - 1) * per_page
        result = await self.db.execute(
            select(BillingEvent)
            .where(BillingEvent.user_id == user_id)
            .order_by(BillingEvent.created_at.desc())
            .limit(per_page)
            .offset(offset)
        )
        events = list(result.scalars().all())

        return events, total

    # Usage summary methods

    async def get_or_create_usage_summary(
        self, user_id: uuid.UUID, period_start: datetime, period_end: datetime
    ) -> UsageSummary:
        """Get or create usage summary for a period."""
        result = await self.db.execute(
            select(UsageSummary).where(
                UsageSummary.user_id == user_id,
                UsageSummary.period_start == period_start,
                UsageSummary.period_end == period_end,
            )
        )
        summary = result.scalar_one_or_none()

        if not summary:
            summary = UsageSummary(
                user_id=user_id,
                period_start=period_start,
                period_end=period_end,
            )
            self.db.add(summary)
            await self.db.flush()
            await self.db.refresh(summary)

        return summary

    async def update_usage_summary(self, user_id: uuid.UUID) -> UsageSummary:
        """Update usage summary with current counts."""
        subscription = await self.get_or_create_subscription(user_id)
        usage = await self.get_current_usage(user_id)

        period_start = subscription.current_period_start or datetime.now(UTC)
        period_end = subscription.current_period_end or (
            datetime.now(UTC) + timedelta(days=30)
        )

        summary = await self.get_or_create_usage_summary(
            user_id, period_start, period_end
        )

        summary.sites_count = usage.sites_count
        summary.runs_count = usage.runs_count
        summary.snapshots_count = usage.snapshots_count

        await self.db.flush()
        await self.db.refresh(summary)

        return summary

    # Plan change methods

    async def change_plan(
        self, user_id: uuid.UUID, new_plan: PlanTier
    ) -> tuple[bool, str]:
        """
        Change user's plan. Returns (success, message).

        Note: In production, this would be triggered by Stripe webhook
        after successful payment. This method handles the database updates.
        """
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()

        if not user:
            return False, "User not found"

        old_plan = user.plan
        user.plan = new_plan.value

        subscription = await self.get_or_create_subscription(user_id)
        subscription.plan = new_plan.value

        # Log the event
        event_type = (
            BillingEventType.PLAN_UPGRADED
            if _plan_rank(new_plan) > _plan_rank(PlanTier(old_plan))
            else BillingEventType.PLAN_DOWNGRADED
        )
        await self.log_billing_event(
            user_id=user_id,
            event_type=event_type,
            data={"old_plan": old_plan, "new_plan": new_plan.value},
        )

        await self.db.flush()

        logger.info(
            "plan_changed",
            user_id=str(user_id),
            old_plan=old_plan,
            new_plan=new_plan.value,
        )

        return True, f"Plan changed from {old_plan} to {new_plan.value}"


def _plan_rank(plan: PlanTier) -> int:
    """Get numeric rank for plan comparison."""
    ranks = {
        PlanTier.STARTER: 1,
        PlanTier.PROFESSIONAL: 2,
        PlanTier.AGENCY: 3,
    }
    return ranks.get(plan, 0)
