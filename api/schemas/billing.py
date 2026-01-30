"""Billing and subscription schemas."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, HttpUrl


class PlanTier(str, Enum):
    """Available plan tiers."""

    STARTER = "starter"
    PROFESSIONAL = "professional"
    AGENCY = "agency"


class SubscriptionStatus(str, Enum):
    """Stripe subscription status."""

    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    TRIALING = "trialing"
    UNPAID = "unpaid"
    PAUSED = "paused"


class BillingCycle(str, Enum):
    """Billing cycle options."""

    MONTHLY = "monthly"
    YEARLY = "yearly"


# Plan limits configuration
PLAN_LIMITS = {
    PlanTier.STARTER: {
        "sites": 1,
        "runs_per_month": 10,
        "snapshots_per_month": 30,
        "monitoring_interval_hours": 168,  # Weekly only
        "competitors_per_site": 3,
        "api_access": False,
        "webhook_alerts": False,
        "priority_support": False,
    },
    PlanTier.PROFESSIONAL: {
        "sites": 5,
        "runs_per_month": 50,
        "snapshots_per_month": 150,
        "monitoring_interval_hours": 24,  # Daily
        "competitors_per_site": 10,
        "api_access": True,
        "webhook_alerts": True,
        "priority_support": False,
    },
    PlanTier.AGENCY: {
        "sites": 25,
        "runs_per_month": 250,
        "snapshots_per_month": 750,
        "monitoring_interval_hours": 6,  # 4x daily
        "competitors_per_site": 25,
        "api_access": True,
        "webhook_alerts": True,
        "priority_support": True,
    },
}


# Request schemas
class CreateCheckoutSessionRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    plan: PlanTier
    billing_cycle: BillingCycle = BillingCycle.MONTHLY
    success_url: HttpUrl
    cancel_url: HttpUrl


class CreatePortalSessionRequest(BaseModel):
    """Request to create a Stripe customer portal session."""

    return_url: HttpUrl


class ChangePlanRequest(BaseModel):
    """Request to change subscription plan."""

    new_plan: PlanTier
    billing_cycle: BillingCycle | None = None


# Response schemas
class PlanLimitsResponse(BaseModel):
    """Plan limits for a tier."""

    sites: int
    runs_per_month: int
    snapshots_per_month: int
    monitoring_interval_hours: int
    competitors_per_site: int
    api_access: bool
    webhook_alerts: bool
    priority_support: bool


class SubscriptionResponse(BaseModel):
    """Subscription details response."""

    id: uuid.UUID
    plan: str
    status: str
    billing_cycle: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at: datetime | None
    canceled_at: datetime | None
    trial_end: datetime | None
    created_at: datetime

    class Config:
        from_attributes = True


class UsageResponse(BaseModel):
    """Current usage statistics."""

    sites_count: int
    sites_limit: int
    sites_remaining: int
    runs_count: int
    runs_limit: int
    runs_remaining: int
    snapshots_count: int
    snapshots_limit: int
    snapshots_remaining: int
    period_start: datetime
    period_end: datetime


class UsageSummaryResponse(BaseModel):
    """Usage summary for a period."""

    id: uuid.UUID
    period_start: datetime
    period_end: datetime
    sites_count: int
    runs_count: int
    snapshots_count: int
    observations_count: int
    benchmarks_count: int
    api_calls_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class CheckoutSessionResponse(BaseModel):
    """Checkout session response."""

    session_id: str
    url: str


class PortalSessionResponse(BaseModel):
    """Customer portal session response."""

    url: str


class PlanComparisonResponse(BaseModel):
    """Compare all available plans."""

    starter: PlanLimitsResponse
    professional: PlanLimitsResponse
    agency: PlanLimitsResponse
    current_plan: str


class BillingEventResponse(BaseModel):
    """Billing event record."""

    id: uuid.UUID
    event_type: str
    stripe_event_id: str | None
    data: dict | None
    processed: bool
    error: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class BillingHistoryResponse(BaseModel):
    """Billing history with pagination."""

    events: list[BillingEventResponse]
    total: int
    page: int
    per_page: int


# Limit check responses
class LimitCheckResponse(BaseModel):
    """Result of checking a usage limit."""

    allowed: bool
    current: int
    limit: int
    remaining: int
    message: str | None = None


class FeatureCheckResponse(BaseModel):
    """Result of checking a feature access."""

    allowed: bool
    required_plan: str | None = None
    message: str | None = None


# Webhook schemas
class StripeWebhookEvent(BaseModel):
    """Stripe webhook event wrapper."""

    id: str
    type: str
    data: dict
    created: int
    livemode: bool
