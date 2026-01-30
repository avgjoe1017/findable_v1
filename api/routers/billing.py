"""Billing and subscription management endpoints."""

from __future__ import annotations

import hashlib
import hmac
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import current_active_user
from api.config import get_settings
from api.database import get_db
from api.models import User
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
        starter=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.STARTER]),
        professional=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.PROFESSIONAL]),
        agency=PlanLimitsResponse(**PLAN_LIMITS[PlanTier.AGENCY]),
        current_plan=current_user.plan,
    )


@router.get("/plans/{plan}", response_model=PlanLimitsResponse)
async def get_plan_limits(
    plan: PlanTier,
) -> PlanLimitsResponse:
    """Get limits for a specific plan."""
    return PlanLimitsResponse(**PLAN_LIMITS[plan])


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

    events, total = await billing_service.get_billing_history(
        current_user.id, page, per_page
    )

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
    billing_service: Annotated[BillingService, Depends(get_billing_service)],  # noqa: ARG001
    db: Annotated[AsyncSession, Depends(get_db)],  # noqa: ARG001
) -> CheckoutSessionResponse:
    """Create a Stripe checkout session for plan upgrade.

    Note: This is a stub. In production, this would integrate with Stripe.
    """
    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    # In production, create Stripe checkout session here
    # For now, return a placeholder
    logger.info(
        "checkout_session_requested",
        user_id=str(current_user.id),
        plan=request.plan.value,
        billing_cycle=request.billing_cycle.value,
    )

    # Placeholder response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Stripe checkout not yet implemented. Contact support for plan changes.",
    )


@router.post("/portal", response_model=PortalSessionResponse)
async def create_portal_session(
    request: CreatePortalSessionRequest,  # noqa: ARG001
    current_user: Annotated[User, Depends(current_active_user)],
    billing_service: Annotated[BillingService, Depends(get_billing_service)],
) -> PortalSessionResponse:
    """Create a Stripe customer portal session.

    Note: This is a stub. In production, this would integrate with Stripe.
    """
    settings = get_settings()

    if not settings.stripe_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    subscription = await billing_service.get_user_subscription(current_user.id)

    if not subscription or not subscription.stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No billing account found. Please contact support.",
        )

    # Placeholder response
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Stripe portal not yet implemented. Contact support for billing changes.",
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

    success, message = await billing_service.change_plan(
        current_user.id, request.new_plan
    )

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
    stripe_signature: Annotated[str | None, Header(alias="stripe-signature")] = None,
    db: Annotated[AsyncSession, Depends(get_db)] = None,
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
        _verify_stripe_signature(
            body, stripe_signature, settings.stripe_webhook_secret
        )
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


def _verify_stripe_signature(
    payload: bytes, signature: str, secret: str
) -> None:
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
    _billing_service: BillingService,
    _db: AsyncSession,
) -> None:
    """Handle subscription created event."""
    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")

    # Look up user by customer ID
    # In production, you'd have a mapping of Stripe customer IDs to users
    logger.info(
        "stripe_subscription_created",
        customer_id=customer_id,
        subscription_id=data.get("id"),
    )


async def _handle_subscription_updated(
    event: dict,
    _billing_service: BillingService,
    _db: AsyncSession,
) -> None:
    """Handle subscription updated event."""
    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    sub_status = data.get("status")

    logger.info(
        "stripe_subscription_updated",
        customer_id=customer_id,
        status=sub_status,
    )


async def _handle_subscription_deleted(
    event: dict,
    _billing_service: BillingService,
    _db: AsyncSession,
) -> None:
    """Handle subscription deleted event."""
    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")

    logger.info(
        "stripe_subscription_deleted",
        customer_id=customer_id,
    )


async def _handle_invoice_paid(
    event: dict,
    _billing_service: BillingService,
    _db: AsyncSession,
) -> None:
    """Handle invoice paid event."""
    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")
    amount = data.get("amount_paid")

    logger.info(
        "stripe_invoice_paid",
        customer_id=customer_id,
        amount=amount,
    )


async def _handle_invoice_payment_failed(
    event: dict,
    _billing_service: BillingService,
    _db: AsyncSession,
) -> None:
    """Handle invoice payment failed event."""
    data = event.get("data", {}).get("object", {})
    customer_id = data.get("customer")

    logger.warning(
        "stripe_invoice_payment_failed",
        customer_id=customer_id,
    )
