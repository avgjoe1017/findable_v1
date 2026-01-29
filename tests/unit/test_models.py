"""Tests for database models."""

from api.models import (
    BusinessModel,
    PlanTier,
    RunStatus,
    RunType,
)


def test_plan_tier_enum() -> None:
    """Test PlanTier enum values."""
    assert PlanTier.STARTER.value == "starter"
    assert PlanTier.PROFESSIONAL.value == "professional"
    assert PlanTier.AGENCY.value == "agency"


def test_business_model_enum() -> None:
    """Test BusinessModel enum values."""
    assert BusinessModel.LOCAL_SERVICE.value == "local_service"
    assert BusinessModel.ECOMMERCE.value == "ecommerce"
    assert BusinessModel.SAAS.value == "saas"
    assert BusinessModel.UNKNOWN.value == "unknown"


def test_run_status_enum() -> None:
    """Test RunStatus enum values."""
    assert RunStatus.QUEUED.value == "queued"
    assert RunStatus.CRAWLING.value == "crawling"
    assert RunStatus.COMPLETE.value == "complete"
    assert RunStatus.FAILED.value == "failed"


def test_run_type_enum() -> None:
    """Test RunType enum values."""
    assert RunType.STARTER_AUDIT.value == "starter_audit"
    assert RunType.SNAPSHOT.value == "snapshot"
    assert RunType.RESCORE.value == "rescore"
