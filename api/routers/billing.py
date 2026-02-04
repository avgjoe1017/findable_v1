"""Billing and subscription management endpoints."""

from __future__ import annotations

import hashlib
import hmac
from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.config import get_settings

if TYPE_CHECKING:
    from api.config import Settings
from datetime import UTC

from api.database import get_db
from api.models import User
from api.models.billing import BillingEventType
from api.schemas.billing import (
    PLAN_LIMITS,
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
    UsageResponse,
)
from api.services.billing_service import BillingService

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


# Dependencies
async def get_billing_service(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BillingService:
    """Get billing service instance."""
    return BillingService(db)


# Subscription endpoints


@router.get("/subscription", response_model=SubscriptionResponse)
async def get_subscription(
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> SubscriptionResponse:
    """Get current user's subscription details."""
    subscription = await billing_service.get_or_create_subscription(current_user.id)

    return SubscriptionResponse(
        id=subscription.id,
        plan=subscription.plan,
        status=subscription.status,
        billing_cycle=subscription.billing_cycle,
        stripe_customer_id=subscription.stripe_customer_id,
        stripe_subscription_id=subscription.stripe_subscription_id,
        current_period_start=subscription.current_period_start,
        current_period_end=subscription.current_period_end,
        cancel_at=subscription.cancel_at,
        canceled_at=subscription.canceled_at,
        trial_end=subscription.trial_end,
        created_at=subscription.created_at,
    )


# Usage endpoints


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> UsageResponse:
    """Get current period usage statistics."""
    return await billing_service.get_current_usage(current_user.id)


# Plan endpoints


@router.get("/plans", response_model=PlanComparisonResponse)
async def get_plans(
    current_user: Annotated[User, Depends(current_active_user)],
) -> PlanComparisonResponse:
    """Get comparison of all available plans."""
    return PlanComparisonResponse(
        starter=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.STARTER]),  # type: ignore[arg-type]
        professional=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.PROFESSIONAL]),  # type: ignore[arg-type]
        agency=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.AGENCY]),  # type: ignore[arg-type]
        current_plan=current_user.plan,
    )


@router.get("/plans/{plan}", response_model=PlanLimitsResponse)
async def get_plan_limits(
    plan: PlanTier,
) -> PlanLimitsResponse:
    """Get limits for a specific plan."""
    return PlanLimitsResponse(**PLAN_LIMITS[plan])  # type: ignore[arg-type]


# Limit check endpoints


@router.get("/limits/sites", response_model=LimitCheckResponse)
async def check_site_limit(
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> LimitCheckResponse:
    """Check if user can create a new site."""
    return await billing_service.check_site_limit(current_user.id)


@router.get("/limits/runs", response_model=LimitCheckResponse)
async def check_run_limit(
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> LimitCheckResponse:
    """Check if user can start a new run."""
    return await billing_service.check_run_limit(current_user.id)


@router.get("/limits/snapshots", response_model=LimitCheckResponse)
async def check_snapshot_limit(
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> LimitCheckResponse:
    """Check if user can take a snapshot."""
    return await billing_service.check_snapshot_limit(current_user.id)


# Feature check endpoints


@router.get("/features/{feature}", response_model=FeatureCheckResponse)
async def check_feature_access(
    feature: str,
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> FeatureCheckResponse:
    """Check if user has access to a specific feature."""
    return await billing_service.check_feature_access(current_user.id, feature)


# Billing history


@router.get("/history", response_model=BillingHistoryResponse)
async def get_billing_history(
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
    page: int = 1,
    per_page: int = 20,
) -> BillingHistoryResponse:
    """Get billing event history."""
    if page < 1:
        page = 1
    if per_page < 1 or per_page > 100:
        per_page = 20

    events, total = await billing_service.get_billing_history(current_user.id, page, per_page)

    return BillingHistoryResponse(
        events=[
            BillingEventResponse(
                id=e.id,
                event_type=e.event_type,
                stripe_event_id=e.stripe_event_id,
                data=e.data,
                processed=e.processed,
                error=e.error,
                created_at=e.created_at,
            )
            for e in events
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


# Stripe integration endpoints (stubs for future implementation)


@router.post("/checkout", response_model=CheckoutSessionResponse)
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for plan upgrade."""
    import stripe

    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    stripe.api_key = settings.stripe_secret_key

    # Get or create subscription to get/create Stripe customer
    subscription = await billing_service.get_or_create_subscription(current_user.id)

    # Create Stripe customer if needed
    if not subscription.stripe_customer_id:
        try:
            customer = stripe.Customer.create(
                email=current_user.email,
                metadata={"user_id": str(current_user.id)},
            )
            subscription.stripe_customer_id = customer.id
            await db.commit()
        except stripe.StripeError as e:
            logger.error("stripe_customer_creation_failed", error=str(e))
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to create billing account",
            )

    # Get the price ID for the requested plan/cycle
    price_id = _get_price_id(request.plan, request.billing_cycle, settings)
    if not price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No price configured for {request.plan.value} {request.billing_cycle.value}",
        )

    try:
        checkout_session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=(
                str(request.success_url)
                if request.success_url
                else f"{settings.api_host}/billing/success"
            ),
            cancel_url=(
                str(request.cancel_url)
                if request.cancel_url
                else f"{settings.api_host}/billing/cancel"
            ),
            metadata={"user_id": str(current_user.id)},
            subscription_data={"metadata": {"user_id": str(current_user.id)}},
        )

        logger.info(
            "checkout_session_created",
            user_id=str(current_user.id),
            plan=request.plan.value,
            billing_cycle=request.billing_cycle.value,
            session_id=checkout_session.id,
        )

        return CheckoutSessionResponse(
            session_id=checkout_session.id,
            url=checkout_session.url or "",
        )

    except stripe.StripeError as e:
        logger.error("stripe_checkout_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create checkout session",
        )


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal_session(
    request: CreatePortalSessionRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> PortalSessionResponse:
    """Create a Stripe customer portal session for managing subscription."""
    import stripe

    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    stripe.api_key = settings.stripe_secret_key

    subscription = await billing_service.get_user_subscription(current_user.id)

    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please contact support.",
        )

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=str(request.return_url) if request.return_url else f"{settings.api_host}/",
        )

        logger.info(
            "portal_session_created",
            user_id=str(current_user.id),
            customer_id=subscription.stripe_customer_id,
        )

        return PortalSessionResponse(url=portal_session.url)

    except stripe.StripeError as e:
        logger.error("stripe_portal_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create portal session",
        )


@router.post("/change-plan")
async def change_plan(
    request: ChangePlanRequest,
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Change user's plan (admin/dev endpoint).

    Note: In production, plan changes should go through Stripe checkout.
    This endpoint is for development/testing purposes.
    """
    settings = get_settings()

    # Only allow direct plan changes in development
    if settings.env != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Direct plan changes not allowed. Use checkout flow.",
        )

    success, message = await billing_service.change_plan(current_user.id, request.new_plan)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=message,
        )

    await db.commit()

    return {"success": True, "message": message}


# Stripe webhook endpoint


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
) -> dict:
    """Handle Stripe webhook events.

    Verifies the webhook signature and processes billing events.
    """
    settings = get_settings()

    if not settings.stripe_webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )

    if not stripe_signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing stripe-signature header",
        )

    # Get raw body for signature verification
    body = await request.body()

    # Verify signature
    try:
        _verify_stripe_signature(body, stripe_signature, settings.stripe_webhook_secret)
    except ValueError as e:
        logger.warning("stripe_webhook_invalid_signature", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        )

    # Parse event
    import json

    try:
        event = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        )

    event_type = event.get("type", "")
    event_id = event.get("id", "")

    logger.info(
        "stripe_webhook_received",
        event_type=event_type,
        event_id=event_id,
    )

    # Process event based on type
    billing_service = BillingService(db)

    try:
        if event_type == "customer.subscription.created":
            await _handle_subscription_created(event, billing_service, db)
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(event, billing_service, db)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(event, billing_service, db)
        elif event_type == "invoice.paid":
            await _handle_invoice_paid(event, billing_service, db)
        elif event_type == "invoice.payment_failed":
            await _handle_invoice_payment_failed(event, billing_service, db)
        else:
            logger.debug("stripe_webhook_unhandled_type", event_type=event_type)

        await db.commit()

    except Exception as e:
        logger.error(
            "stripe_webhook_processing_error",
            event_type=event_type,
            event_id=event_id,
            error=str(e),
        )
        # Don't raise - return 200 to acknowledge receipt
        # The event can be retried or handled manually

    return {"received": True}


def _get_price_id(plan: PlanTier, billing_cycle: str, settings: Settings) -> str | None:
    """Get Stripe price ID for a plan and billing cycle."""
    price_map = {
        (PlanTier.STARTER, "monthly"): settings.stripe_price_starter_monthly,
        (PlanTier.STARTER, "yearly"): settings.stripe_price_starter_yearly,
        (PlanTier.PROFESSIONAL, "monthly"): settings.stripe_price_professional_monthly,
        (PlanTier.PROFESSIONAL, "yearly"): settings.stripe_price_professional_yearly,
        (PlanTier.AGENCY, "monthly"): settings.stripe_price_agency_monthly,
        (PlanTier.AGENCY, "yearly"): settings.stripe_price_agency_yearly,
    }
    return price_map.get((plan, billing_cycle))


def _plan_from_price_id(price_id: str, settings: Settings) -> PlanTier | None:
    """Get plan tier from Stripe price ID."""
    if price_id in (settings.stripe_price_starter_monthly, settings.stripe_price_starter_yearly):
        return PlanTier.STARTER
    if price_id in (
        settings.stripe_price_professional_monthly,
        settings.stripe_price_professional_yearly,
    ):
        return PlanTier.PROFESSIONAL
    if price_id in (settings.stripe_price_agency_monthly, settings.stripe_price_agency_yearly):
        return PlanTier.AGENCY
    return None


def _verify_stripe_signature(payload: bytes, signature: str, secret: str) -> None:
    """Verify Stripe webhook signature."""
    # Parse signature header
    parts = dict(item.split("=") for item in signature.split(","))

    timestamp = parts.get("t")
    v1_signature = parts.get("v1")

    if not timestamp or not v1_signature:
        raise ValueError("Invalid signature format")

    # Create expected signature
    signed_payload = f"{timestamp}.{payload.decode()}"
    expected_signature = hmac.new(
        secret.encode(),
        signed_payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    # Compare signatures
    if not hmac.compare_digest(expected_signature, v1_signature):
        raise ValueError("Signature mismatch")


async def _handle_subscription_created(
    event: dict,
    billing_service: BillingService,
    db: AsyncSession,
) -> None:
    """Handle subscription created event."""
    from datetime import datetime

    from sqlalchemy import select

    from api.models.billing import Subscription

    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    sub_status = data.get("status")

    logger.info(
        "stripe_subscription_created",
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=sub_status,
    )

    # Find subscription by customer ID
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        # Update subscription with Stripe data
        subscription.stripe_subscription_id = subscription_id
        subscription.status = sub_status

        # Get plan from price
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            settings = get_settings()
            plan = _plan_from_price_id(price_id, settings)
            if plan:
                subscription.plan = plan.value

        # Period dates
        if data.get("current_period_start"):
            subscription.current_period_start = datetime.fromtimestamp(
                data["current_period_start"], tz=UTC
            )
        if data.get("current_period_end"):
            subscription.current_period_end = datetime.fromtimestamp(
                data["current_period_end"], tz=UTC
            )

        await billing_service.log_billing_event(
            subscription.user_id,
            BillingEventType.SUBSCRIPTION_CREATED,
            event.get("id"),
            data,
        )


async def _handle_subscription_updated(
    event: dict,
    billing_service: BillingService,
    db: AsyncSession,
) -> None:
    """Handle subscription updated event."""
    from datetime import datetime

    from sqlalchemy import select

    from api.models.billing import Subscription

    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    subscription_id = data.get("id")
    sub_status = data.get("status")

    logger.info(
        "stripe_subscription_updated",
        customer_id=customer_id,
        subscription_id=subscription_id,
        status=sub_status,
    )

    # Find subscription
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        old_plan = subscription.plan
        subscription.status = sub_status

        # Update plan if changed
        items = data.get("items", {}).get("data", [])
        if items:
            price_id = items[0].get("price", {}).get("id")
            settings = get_settings()
            plan = _plan_from_price_id(price_id, settings)
            if plan:
                subscription.plan = plan.value

        # Period dates
        if data.get("current_period_start"):
            subscription.current_period_start = datetime.fromtimestamp(
                data["current_period_start"], tz=UTC
            )
        if data.get("current_period_end"):
            subscription.current_period_end = datetime.fromtimestamp(
                data["current_period_end"], tz=UTC
            )

        # Cancellation
        if data.get("cancel_at"):
            subscription.cancel_at = datetime.fromtimestamp(data["cancel_at"], tz=UTC)
        if data.get("canceled_at"):
            subscription.canceled_at = datetime.fromtimestamp(data["canceled_at"], tz=UTC)

        # Determine event type
        event_type = BillingEventType.SUBSCRIPTION_UPDATED
        if subscription.plan != old_plan:
            if _plan_tier_order(subscription.plan) > _plan_tier_order(old_plan):
                event_type = BillingEventType.PLAN_UPGRADED
            else:
                event_type = BillingEventType.PLAN_DOWNGRADED

        await billing_service.log_billing_event(
            subscription.user_id,
            event_type,
            event.get("id"),
            data,
        )


def _plan_tier_order(plan: str) -> int:
    """Get numeric order of plan tier for comparison."""
    order = {"starter": 1, "professional": 2, "agency": 3}
    return order.get(plan, 0)


async def _handle_subscription_deleted(
    event: dict,
    billing_service: BillingService,
    db: AsyncSession,
) -> None:
    """Handle subscription deleted event."""
    from datetime import datetime

    from sqlalchemy import select

    from api.models.billing import Subscription

    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    subscription_id = data.get("id")

    logger.info(
        "stripe_subscription_deleted",
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    # Find subscription
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    )
    subscription = result.scalar_one_or_none()

    if subscription:
        subscription.status = "canceled"
        subscription.canceled_at = datetime.now(UTC)
        # Downgrade to starter plan
        subscription.plan = "starter"

        await billing_service.log_billing_event(
            subscription.user_id,
            BillingEventType.SUBSCRIPTION_CANCELED,
            event.get("id"),
            data,
        )


async def _handle_invoice_paid(
    event: dict,
    billing_service: BillingService,
    db: AsyncSession,
) -> None:
    """Handle invoice paid event."""
    from sqlalchemy import select

    from api.models.billing import Subscription

    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    amount = data.get("amount_paid")
    subscription_id = data.get("subscription")

    logger.info(
        "stripe_invoice_paid",
        customer_id=customer_id,
        amount=amount,
        subscription_id=subscription_id,
    )

    # Find subscription and log payment
    if subscription_id:
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            # Update status to active if it was past_due
            if subscription.status == "past_due":
                subscription.status = "active"

            await billing_service.log_billing_event(
                subscription.user_id,
                BillingEventType.PAYMENT_SUCCEEDED,
                event.get("id"),
                {"amount": amount, "currency": data.get("currency")},
            )


async def _handle_invoice_payment_failed(
    event: dict,
    billing_service: BillingService,
    db: AsyncSession,
) -> None:
    """Handle invoice payment failed event."""
    from sqlalchemy import select

    from api.models.billing import Subscription

    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")

    logger.warning(
        "stripe_invoice_payment_failed",
        customer_id=customer_id,
        subscription_id=subscription_id,
    )

    # Find subscription and update status
    if subscription_id:
        result = await db.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
        )
        subscription = result.scalar_one_or_none()

        if subscription:
            subscription.status = "past_due"

            await billing_service.log_billing_event(
                subscription.user_id,
                BillingEventType.PAYMENT_FAILED,
                event.get("id"),
                {"reason": data.get("billing_reason")},
            )
