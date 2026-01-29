"""Tests for user schemas."""

from api.schemas.user import PlanInfo, get_plan_limits


def test_get_plan_limits_starter() -> None:
    """Test starter plan limits."""
    limits = get_plan_limits("starter")
    assert limits["competitors"] == 1
    assert limits["custom_questions"] == 5
    assert limits["weekly_snapshots"] == 4


def test_get_plan_limits_professional() -> None:
    """Test professional plan limits."""
    limits = get_plan_limits("professional")
    assert limits["competitors"] == 2
    assert limits["weekly_snapshots"] == -1  # unlimited


def test_get_plan_limits_agency() -> None:
    """Test agency plan limits."""
    limits = get_plan_limits("agency")
    assert limits["competitors"] == 2
    assert limits["client_sites"] == 10


def test_get_plan_limits_unknown_defaults_to_starter() -> None:
    """Test unknown plan defaults to starter limits."""
    limits = get_plan_limits("unknown")
    assert limits == get_plan_limits("starter")


def test_plan_info_model() -> None:
    """Test PlanInfo model."""
    plan_info = PlanInfo(
        plan="professional",
        limits={"competitors": 2, "custom_questions": 5},
    )
    assert plan_info.plan == "professional"
    assert plan_info.limits["competitors"] == 2
