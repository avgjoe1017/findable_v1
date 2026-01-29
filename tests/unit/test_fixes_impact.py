"""Tests for fix impact estimator module."""

from uuid import uuid4

from worker.fixes.generator import Fix, FixPlan
from worker.fixes.impact import (
    CATEGORY_WEIGHT_FACTORS,
    QUESTION_COUNT_MULTIPLIERS,
    REASON_CODE_BASE_IMPACT,
    ConfidenceLevel,
    FixImpactEstimate,
    FixPlanImpact,
    ImpactRange,
    ImpactTier,
    TierCEstimator,
    estimate_fix_impact,
    estimate_plan_impact,
)
from worker.fixes.reason_codes import ReasonCode, get_reason_info
from worker.fixes.templates import get_template
from worker.questions.universal import QuestionCategory


def make_fix(
    reason_code: ReasonCode = ReasonCode.MISSING_DEFINITION,
    affected_question_ids: list[str] | None = None,
    affected_categories: list[QuestionCategory] | None = None,
) -> Fix:
    """Create a test fix."""
    return Fix(
        id=uuid4(),
        reason_code=reason_code,
        reason_info=get_reason_info(reason_code),
        template=get_template(reason_code),
        affected_question_ids=affected_question_ids or ["q1"],
        affected_categories=affected_categories or [QuestionCategory.IDENTITY],
        scaffold="Test scaffold",
        extracted_content=[],
        priority=1,
        estimated_impact=0.2,
        effort_level="low",
        target_url="/about",
    )


def make_fix_plan(fixes: list[Fix] | None = None) -> FixPlan:
    """Create a test fix plan."""
    if fixes is None:
        fixes = [make_fix()]

    return FixPlan(
        id=uuid4(),
        site_id=uuid4(),
        run_id=uuid4(),
        company_name="Test Company",
        fixes=fixes,
        total_fixes=len(fixes),
        critical_fixes=1,
        high_priority_fixes=0,
        estimated_total_impact=0.2,
        categories_addressed=[QuestionCategory.IDENTITY],
        questions_addressed=1,
    )


class TestImpactTier:
    """Tests for ImpactTier enum."""

    def test_all_tiers_exist(self) -> None:
        """All tiers exist."""
        assert ImpactTier.TIER_C == "tier_c"
        assert ImpactTier.TIER_B == "tier_b"
        assert ImpactTier.TIER_A == "tier_a"


class TestConfidenceLevel:
    """Tests for ConfidenceLevel enum."""

    def test_all_levels_exist(self) -> None:
        """All levels exist."""
        assert ConfidenceLevel.HIGH == "high"
        assert ConfidenceLevel.MEDIUM == "medium"
        assert ConfidenceLevel.LOW == "low"


class TestImpactRange:
    """Tests for ImpactRange dataclass."""

    def test_create_range(self) -> None:
        """Can create an impact range."""
        impact = ImpactRange(
            min_points=2.0,
            max_points=6.0,
            expected_points=4.0,
            confidence=ConfidenceLevel.MEDIUM,
            tier=ImpactTier.TIER_C,
        )

        assert impact.min_points == 2.0
        assert impact.max_points == 6.0
        assert impact.expected_points == 4.0

    def test_to_dict(self) -> None:
        """Converts to dict."""
        impact = ImpactRange(
            min_points=1.5,
            max_points=4.5,
            expected_points=3.0,
            confidence=ConfidenceLevel.HIGH,
            tier=ImpactTier.TIER_C,
        )

        d = impact.to_dict()
        assert d["min_points"] == 1.5
        assert d["max_points"] == 4.5
        assert d["confidence"] == "high"
        assert d["tier"] == "tier_c"


class TestFixImpactEstimate:
    """Tests for FixImpactEstimate dataclass."""

    def test_create_estimate(self) -> None:
        """Can create an estimate."""
        estimate = FixImpactEstimate(
            fix_id="fix-123",
            reason_code=ReasonCode.MISSING_PRICING,
            impact_range=ImpactRange(
                min_points=2.0,
                max_points=5.0,
                expected_points=3.5,
                confidence=ConfidenceLevel.MEDIUM,
                tier=ImpactTier.TIER_C,
            ),
            affected_questions=2,
            affected_categories=[QuestionCategory.OFFERINGS],
            base_impact=3.0,
            question_multiplier=1.5,
            category_multiplier=1.2,
            explanation="Test explanation",
            assumptions=["Assumption 1"],
        )

        assert estimate.fix_id == "fix-123"
        assert estimate.affected_questions == 2

    def test_to_dict(self) -> None:
        """Converts to dict."""
        estimate = FixImpactEstimate(
            fix_id="fix-456",
            reason_code=ReasonCode.MISSING_CONTACT,
            impact_range=ImpactRange(
                min_points=1.0,
                max_points=3.0,
                expected_points=2.0,
                confidence=ConfidenceLevel.HIGH,
                tier=ImpactTier.TIER_C,
            ),
            affected_questions=1,
            affected_categories=[QuestionCategory.CONTACT],
            base_impact=2.0,
            question_multiplier=1.0,
            category_multiplier=1.1,
            explanation="Test",
            assumptions=[],
        )

        d = estimate.to_dict()
        assert d["fix_id"] == "fix-456"
        assert d["reason_code"] == "missing_contact"
        assert "impact_range" in d


class TestFixPlanImpact:
    """Tests for FixPlanImpact dataclass."""

    def test_create_plan_impact(self) -> None:
        """Can create a plan impact."""
        plan_impact = FixPlanImpact(
            plan_id="plan-123",
            estimates=[],
            total_min_points=5.0,
            total_max_points=15.0,
            total_expected_points=10.0,
            top_impact_fixes=["fix-1", "fix-2"],
            categories_impacted=[QuestionCategory.IDENTITY],
            overall_confidence=ConfidenceLevel.MEDIUM,
            tier=ImpactTier.TIER_C,
        )

        assert plan_impact.total_expected_points == 10.0

    def test_to_dict(self) -> None:
        """Converts to dict."""
        plan_impact = FixPlanImpact(
            plan_id="plan-456",
            estimates=[],
            total_min_points=3.0,
            total_max_points=8.0,
            total_expected_points=5.5,
            top_impact_fixes=[],
            categories_impacted=[],
            overall_confidence=ConfidenceLevel.LOW,
            tier=ImpactTier.TIER_C,
            notes=["Note 1"],
        )

        d = plan_impact.to_dict()
        assert d["plan_id"] == "plan-456"
        assert d["total_expected_points"] == 5.5
        assert d["notes"] == ["Note 1"]


class TestLookupTables:
    """Tests for lookup tables."""

    def test_all_reason_codes_have_base_impact(self) -> None:
        """All reason codes have base impact defined."""
        for code in ReasonCode:
            assert code in REASON_CODE_BASE_IMPACT

    def test_base_impacts_are_valid(self) -> None:
        """Base impacts have valid ranges."""
        for code, (min_val, expected, max_val) in REASON_CODE_BASE_IMPACT.items():
            assert min_val > 0, f"{code} min must be positive"
            assert min_val <= expected, f"{code} min must be <= expected"
            assert expected <= max_val, f"{code} expected must be <= max"
            assert max_val <= 15, f"{code} max seems too high"

    def test_question_multipliers_exist(self) -> None:
        """Question count multipliers exist for common counts."""
        assert 1 in QUESTION_COUNT_MULTIPLIERS
        assert 2 in QUESTION_COUNT_MULTIPLIERS
        assert 5 in QUESTION_COUNT_MULTIPLIERS

    def test_question_multipliers_increase(self) -> None:
        """Multipliers increase with question count."""
        prev = 0.0
        for count in sorted(QUESTION_COUNT_MULTIPLIERS.keys()):
            mult = QUESTION_COUNT_MULTIPLIERS[count]
            assert mult > prev
            prev = mult

    def test_category_weights_exist(self) -> None:
        """All categories have weight factors."""
        for category in QuestionCategory:
            assert category in CATEGORY_WEIGHT_FACTORS


class TestTierCEstimator:
    """Tests for TierCEstimator class."""

    def test_create_estimator(self) -> None:
        """Can create an estimator."""
        estimator = TierCEstimator()
        assert estimator.max_total_impact == 30.0

    def test_create_with_custom_cap(self) -> None:
        """Can use custom cap."""
        estimator = TierCEstimator(max_total_impact=20.0)
        assert estimator.max_total_impact == 20.0

    def test_estimate_fix_returns_estimate(self) -> None:
        """estimate_fix returns FixImpactEstimate."""
        estimator = TierCEstimator()
        fix = make_fix()

        estimate = estimator.estimate_fix(fix)

        assert isinstance(estimate, FixImpactEstimate)
        assert estimate.impact_range.tier == ImpactTier.TIER_C

    def test_estimate_uses_reason_code_base(self) -> None:
        """Uses reason code base impact."""
        estimator = TierCEstimator()

        # MISSING_DEFINITION has higher base than POOR_HEADINGS
        fix_high = make_fix(reason_code=ReasonCode.MISSING_DEFINITION)
        fix_low = make_fix(reason_code=ReasonCode.POOR_HEADINGS)

        est_high = estimator.estimate_fix(fix_high)
        est_low = estimator.estimate_fix(fix_low)

        assert est_high.impact_range.expected_points > est_low.impact_range.expected_points

    def test_estimate_scales_with_questions(self) -> None:
        """Impact scales with affected questions."""
        estimator = TierCEstimator()

        fix_one = make_fix(affected_question_ids=["q1"])
        fix_three = make_fix(affected_question_ids=["q1", "q2", "q3"])

        est_one = estimator.estimate_fix(fix_one)
        est_three = estimator.estimate_fix(fix_three)

        assert est_three.impact_range.expected_points > est_one.impact_range.expected_points
        assert est_three.question_multiplier > est_one.question_multiplier

    def test_estimate_considers_category(self) -> None:
        """Impact considers category weight."""
        estimator = TierCEstimator()

        # OFFERINGS has higher weight than DIFFERENTIATION
        fix_offerings = make_fix(affected_categories=[QuestionCategory.OFFERINGS])
        fix_diff = make_fix(affected_categories=[QuestionCategory.DIFFERENTIATION])

        est_offerings = estimator.estimate_fix(fix_offerings)
        est_diff = estimator.estimate_fix(fix_diff)

        assert est_offerings.category_multiplier > est_diff.category_multiplier

    def test_estimate_has_explanation(self) -> None:
        """Estimate includes explanation."""
        estimator = TierCEstimator()
        fix = make_fix()

        estimate = estimator.estimate_fix(fix)

        assert len(estimate.explanation) > 0
        assert "points" in estimate.explanation.lower()

    def test_estimate_has_assumptions(self) -> None:
        """Estimate includes assumptions."""
        estimator = TierCEstimator()
        fix = make_fix()

        estimate = estimator.estimate_fix(fix)

        assert len(estimate.assumptions) > 0
        assert any("Tier C" in a for a in estimate.assumptions)

    def test_estimate_plan_returns_plan_impact(self) -> None:
        """estimate_plan returns FixPlanImpact."""
        estimator = TierCEstimator()
        plan = make_fix_plan()

        impact = estimator.estimate_plan(plan)

        assert isinstance(impact, FixPlanImpact)
        assert impact.tier == ImpactTier.TIER_C

    def test_plan_calculates_totals(self) -> None:
        """Plan calculates total impact."""
        estimator = TierCEstimator()

        fixes = [
            make_fix(reason_code=ReasonCode.MISSING_DEFINITION),
            make_fix(reason_code=ReasonCode.MISSING_PRICING),
        ]
        plan = make_fix_plan(fixes=fixes)

        impact = estimator.estimate_plan(plan)

        assert impact.total_expected_points > 0
        assert impact.total_min_points <= impact.total_expected_points
        assert impact.total_expected_points <= impact.total_max_points

    def test_plan_respects_cap(self) -> None:
        """Plan respects max total impact cap."""
        estimator = TierCEstimator(max_total_impact=10.0)

        # Create many high-impact fixes
        fixes = [
            make_fix(
                reason_code=ReasonCode.BLOCKED_BY_ROBOTS,
                affected_question_ids=["q1", "q2", "q3", "q4", "q5"],
            )
            for _ in range(5)
        ]
        plan = make_fix_plan(fixes=fixes)

        impact = estimator.estimate_plan(plan)

        assert impact.total_expected_points <= 10.0
        assert impact.total_max_points <= 10.0

    def test_plan_identifies_top_fixes(self) -> None:
        """Plan identifies top impact fixes."""
        estimator = TierCEstimator()

        fixes = [
            make_fix(reason_code=ReasonCode.POOR_HEADINGS),  # Low impact
            make_fix(reason_code=ReasonCode.BLOCKED_BY_ROBOTS),  # High impact
            make_fix(reason_code=ReasonCode.MISSING_DEFINITION),  # Medium impact
        ]
        plan = make_fix_plan(fixes=fixes)

        impact = estimator.estimate_plan(plan, top_n=2)

        assert len(impact.top_impact_fixes) == 2
        # BLOCKED_BY_ROBOTS should be first
        first_fix_id = impact.top_impact_fixes[0]
        first_estimate = next(e for e in impact.estimates if e.fix_id == first_fix_id)
        assert first_estimate.reason_code == ReasonCode.BLOCKED_BY_ROBOTS

    def test_plan_collects_categories(self) -> None:
        """Plan collects all impacted categories."""
        estimator = TierCEstimator()

        fixes = [
            make_fix(affected_categories=[QuestionCategory.IDENTITY]),
            make_fix(affected_categories=[QuestionCategory.OFFERINGS]),
        ]
        plan = make_fix_plan(fixes=fixes)

        impact = estimator.estimate_plan(plan)

        assert QuestionCategory.IDENTITY in impact.categories_impacted
        assert QuestionCategory.OFFERINGS in impact.categories_impacted

    def test_plan_has_notes(self) -> None:
        """Plan includes notes."""
        estimator = TierCEstimator()
        plan = make_fix_plan()

        impact = estimator.estimate_plan(plan)

        assert len(impact.notes) > 0

    def test_empty_plan_handled(self) -> None:
        """Handles plan with no fixes."""
        estimator = TierCEstimator()
        plan = make_fix_plan(fixes=[])

        impact = estimator.estimate_plan(plan)

        assert impact.total_expected_points == 0
        assert len(impact.estimates) == 0


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_estimate_fix_impact(self) -> None:
        """estimate_fix_impact returns estimate."""
        fix = make_fix()

        estimate = estimate_fix_impact(fix)

        assert isinstance(estimate, FixImpactEstimate)

    def test_estimate_plan_impact(self) -> None:
        """estimate_plan_impact returns plan impact."""
        plan = make_fix_plan()

        impact = estimate_plan_impact(plan)

        assert isinstance(impact, FixPlanImpact)

    def test_estimate_plan_impact_with_top_n(self) -> None:
        """estimate_plan_impact accepts top_n."""
        fixes = [make_fix() for _ in range(5)]
        plan = make_fix_plan(fixes=fixes)

        impact = estimate_plan_impact(plan, top_n=3)

        assert len(impact.top_impact_fixes) == 3


class TestDiminishingReturns:
    """Tests for diminishing returns calculations."""

    def test_second_fix_has_reduced_impact(self) -> None:
        """Second fix contributes less than first."""
        estimator = TierCEstimator()

        # Two identical fixes
        fixes = [
            make_fix(reason_code=ReasonCode.MISSING_DEFINITION),
            make_fix(reason_code=ReasonCode.MISSING_DEFINITION),
        ]
        plan = make_fix_plan(fixes=fixes)

        impact = estimator.estimate_plan(plan)

        # Total should be less than 2x single estimate
        single_estimate = estimator.estimate_fix(fixes[0])
        expected_max = single_estimate.impact_range.expected_points * 2

        assert impact.total_expected_points < expected_max

    def test_many_fixes_converge(self) -> None:
        """Many fixes show convergence (not linear growth)."""
        estimator = TierCEstimator(max_total_impact=100.0)  # High cap

        fixes = [make_fix() for _ in range(10)]
        plan = make_fix_plan(fixes=fixes)

        impact = estimator.estimate_plan(plan)

        # Should be much less than 10x a single fix
        single = estimator.estimate_fix(fixes[0])
        assert impact.total_expected_points < single.impact_range.expected_points * 10


class TestConfidenceDetermination:
    """Tests for confidence level determination."""

    def test_critical_single_question_high_confidence(self) -> None:
        """Critical issue with single question gets high confidence."""
        estimator = TierCEstimator()

        fix = make_fix(
            reason_code=ReasonCode.BLOCKED_BY_ROBOTS,  # Critical
            affected_question_ids=["q1"],
        )

        estimate = estimator.estimate_fix(fix)

        assert estimate.impact_range.confidence == ConfidenceLevel.HIGH

    def test_many_questions_low_confidence(self) -> None:
        """Many affected questions gets lower confidence."""
        estimator = TierCEstimator()

        fix = make_fix(
            reason_code=ReasonCode.POOR_HEADINGS,  # Low severity
            affected_question_ids=["q1", "q2", "q3", "q4", "q5"],
        )

        estimate = estimator.estimate_fix(fix)

        assert estimate.impact_range.confidence == ConfidenceLevel.LOW
