"""Fix impact estimator with tiered estimation approaches.

Tier C: Precomputed lookup tables (conservative, fast)
Tier B: Synthetic patch re-scoring (accurate, moderate cost)
Tier A: Full re-crawl and simulation (most accurate, expensive)

This module implements Tier C estimation.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from worker.fixes.generator import Fix, FixPlan
from worker.fixes.reason_codes import ReasonCode, get_reason_info
from worker.questions.universal import QuestionCategory


class ImpactTier(StrEnum):
    """Impact estimation tier."""

    TIER_C = "tier_c"  # Precomputed lookup (fast, conservative)
    TIER_B = "tier_b"  # Synthetic patch (moderate, accurate)
    TIER_A = "tier_a"  # Full re-simulation (slow, most accurate)


class ConfidenceLevel(StrEnum):
    """Confidence in the impact estimate."""

    HIGH = "high"  # Based on strong patterns
    MEDIUM = "medium"  # Based on reasonable assumptions
    LOW = "low"  # Conservative estimate with high uncertainty


@dataclass
class ImpactRange:
    """Estimated impact range for a fix."""

    min_points: float  # Minimum expected score improvement
    max_points: float  # Maximum expected score improvement
    expected_points: float  # Most likely improvement
    confidence: ConfidenceLevel
    tier: ImpactTier

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "min_points": round(self.min_points, 2),
            "max_points": round(self.max_points, 2),
            "expected_points": round(self.expected_points, 2),
            "confidence": self.confidence.value,
            "tier": self.tier.value,
        }


@dataclass
class FixImpactEstimate:
    """Impact estimate for a single fix."""

    fix_id: str
    reason_code: ReasonCode
    impact_range: ImpactRange

    # Breakdown
    affected_questions: int
    affected_categories: list[QuestionCategory]
    base_impact: float  # From reason code
    question_multiplier: float  # From affected question count
    category_multiplier: float  # From category weights

    # Explanation
    explanation: str
    assumptions: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "fix_id": self.fix_id,
            "reason_code": self.reason_code.value,
            "impact_range": self.impact_range.to_dict(),
            "affected_questions": self.affected_questions,
            "affected_categories": [c.value for c in self.affected_categories],
            "base_impact": round(self.base_impact, 3),
            "question_multiplier": round(self.question_multiplier, 2),
            "category_multiplier": round(self.category_multiplier, 2),
            "explanation": self.explanation,
            "assumptions": self.assumptions,
        }


@dataclass
class FixPlanImpact:
    """Impact estimates for an entire fix plan."""

    plan_id: str
    estimates: list[FixImpactEstimate]

    # Aggregate ranges
    total_min_points: float
    total_max_points: float
    total_expected_points: float

    # Summary
    top_impact_fixes: list[str]  # Fix IDs sorted by impact
    categories_impacted: list[QuestionCategory]
    overall_confidence: ConfidenceLevel

    # Metadata
    tier: ImpactTier
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "plan_id": self.plan_id,
            "estimates": [e.to_dict() for e in self.estimates],
            "total_min_points": round(self.total_min_points, 2),
            "total_max_points": round(self.total_max_points, 2),
            "total_expected_points": round(self.total_expected_points, 2),
            "top_impact_fixes": self.top_impact_fixes,
            "categories_impacted": [c.value for c in self.categories_impacted],
            "overall_confidence": self.overall_confidence.value,
            "tier": self.tier.value,
            "notes": self.notes,
        }


# Tier C Lookup Tables
# These are conservative estimates based on typical patterns

# Base impact per reason code (points out of 100)
REASON_CODE_BASE_IMPACT: dict[ReasonCode, tuple[float, float, float]] = {
    # (min, expected, max) points improvement
    # Content gaps - high impact
    ReasonCode.MISSING_DEFINITION: (3.0, 5.0, 8.0),
    ReasonCode.MISSING_PRICING: (2.5, 4.5, 7.0),
    ReasonCode.MISSING_CONTACT: (2.0, 3.5, 5.0),
    ReasonCode.MISSING_LOCATION: (1.0, 2.0, 3.5),
    ReasonCode.MISSING_FEATURES: (2.0, 4.0, 6.0),
    ReasonCode.MISSING_SOCIAL_PROOF: (1.5, 3.0, 5.0),
    # Structure issues - medium impact
    ReasonCode.BURIED_ANSWER: (1.0, 2.5, 4.0),
    ReasonCode.FRAGMENTED_INFO: (0.5, 1.5, 3.0),
    ReasonCode.NO_DEDICATED_PAGE: (1.5, 3.0, 5.0),
    ReasonCode.POOR_HEADINGS: (0.5, 1.0, 2.0),
    # Quality issues - variable impact
    ReasonCode.NOT_CITABLE: (0.5, 1.5, 2.5),
    ReasonCode.VAGUE_LANGUAGE: (0.5, 1.5, 3.0),
    ReasonCode.OUTDATED_INFO: (1.0, 2.5, 4.0),
    ReasonCode.INCONSISTENT: (2.0, 4.0, 6.0),
    # Trust gaps - medium impact
    ReasonCode.TRUST_GAP: (1.0, 2.5, 4.0),
    ReasonCode.NO_AUTHORITY: (0.5, 1.5, 3.0),
    ReasonCode.UNVERIFIED_CLAIMS: (0.5, 1.5, 2.5),
    # Technical - high impact when fixed
    ReasonCode.RENDER_REQUIRED: (3.0, 6.0, 10.0),
    ReasonCode.BLOCKED_BY_ROBOTS: (4.0, 8.0, 12.0),
}

# Question count multipliers
# More affected questions = higher total impact (with diminishing returns)
QUESTION_COUNT_MULTIPLIERS: dict[int, float] = {
    1: 1.0,
    2: 1.5,
    3: 1.8,
    4: 2.0,
    5: 2.2,
}

# Category weight factors (how important the category is)
CATEGORY_WEIGHT_FACTORS: dict[QuestionCategory, float] = {
    QuestionCategory.IDENTITY: 1.0,
    QuestionCategory.OFFERINGS: 1.2,  # Most important for conversions
    QuestionCategory.CONTACT: 1.1,
    QuestionCategory.TRUST: 1.0,
    QuestionCategory.DIFFERENTIATION: 0.9,
}


class TierCEstimator:
    """Tier C impact estimator using precomputed lookup tables."""

    def __init__(self, max_total_impact: float = 30.0):
        """
        Initialize estimator.

        Args:
            max_total_impact: Maximum total impact cap (prevents unrealistic estimates)
        """
        self.max_total_impact = max_total_impact

    def estimate_fix(self, fix: Fix) -> FixImpactEstimate:
        """
        Estimate impact for a single fix.

        Args:
            fix: The fix to estimate

        Returns:
            FixImpactEstimate with impact range
        """
        # Get base impact from lookup table
        base_min, base_expected, base_max = REASON_CODE_BASE_IMPACT.get(
            fix.reason_code, (0.5, 1.0, 2.0)
        )

        # Calculate question multiplier
        question_count = len(fix.affected_question_ids)
        question_mult = self._get_question_multiplier(question_count)

        # Calculate category multiplier
        category_mult = self._get_category_multiplier(fix.affected_categories)

        # Calculate final impact range
        min_points = base_min * question_mult * category_mult
        expected_points = base_expected * question_mult * category_mult
        max_points = base_max * question_mult * category_mult

        # Determine confidence based on reason code info
        reason_info = get_reason_info(fix.reason_code)
        confidence = self._determine_confidence(reason_info.severity, question_count)

        # Build explanation
        explanation = self._build_explanation(
            fix.reason_code,
            question_count,
            fix.affected_categories,
            expected_points,
        )

        # Build assumptions list
        assumptions = self._build_assumptions(fix.reason_code, question_count)

        return FixImpactEstimate(
            fix_id=str(fix.id),
            reason_code=fix.reason_code,
            impact_range=ImpactRange(
                min_points=min_points,
                max_points=max_points,
                expected_points=expected_points,
                confidence=confidence,
                tier=ImpactTier.TIER_C,
            ),
            affected_questions=question_count,
            affected_categories=fix.affected_categories,
            base_impact=base_expected,
            question_multiplier=question_mult,
            category_multiplier=category_mult,
            explanation=explanation,
            assumptions=assumptions,
        )

    def estimate_plan(self, plan: FixPlan, top_n: int = 5) -> FixPlanImpact:
        """
        Estimate impact for an entire fix plan.

        Args:
            plan: The fix plan to estimate
            top_n: Number of top fixes to highlight

        Returns:
            FixPlanImpact with all estimates
        """
        estimates: list[FixImpactEstimate] = []

        for fix in plan.fixes:
            estimate = self.estimate_fix(fix)
            estimates.append(estimate)

        # Sort by expected impact
        estimates.sort(key=lambda e: -e.impact_range.expected_points)

        # Calculate totals (with overlap adjustment)
        total_min, total_expected, total_max = self._calculate_totals(estimates)

        # Apply cap
        total_min = min(total_min, self.max_total_impact)
        total_expected = min(total_expected, self.max_total_impact)
        total_max = min(total_max, self.max_total_impact)

        # Get top fix IDs
        top_fix_ids = [e.fix_id for e in estimates[:top_n]]

        # Get all impacted categories
        all_categories: set[QuestionCategory] = set()
        for e in estimates:
            all_categories.update(e.affected_categories)

        # Determine overall confidence
        overall_confidence = self._determine_overall_confidence(estimates)

        # Build notes
        notes = self._build_plan_notes(estimates, total_expected)

        return FixPlanImpact(
            plan_id=str(plan.id),
            estimates=estimates,
            total_min_points=total_min,
            total_max_points=total_max,
            total_expected_points=total_expected,
            top_impact_fixes=top_fix_ids,
            categories_impacted=list(all_categories),
            overall_confidence=overall_confidence,
            tier=ImpactTier.TIER_C,
            notes=notes,
        )

    def _get_question_multiplier(self, count: int) -> float:
        """Get multiplier based on affected question count."""
        if count in QUESTION_COUNT_MULTIPLIERS:
            return QUESTION_COUNT_MULTIPLIERS[count]
        # Diminishing returns for many questions
        return min(2.5, 2.2 + (count - 5) * 0.05)

    def _get_category_multiplier(self, categories: list[QuestionCategory]) -> float:
        """Get multiplier based on affected categories."""
        if not categories:
            return 1.0

        # Use highest category weight
        weights = [CATEGORY_WEIGHT_FACTORS.get(cat, 1.0) for cat in categories]
        return max(weights)

    def _determine_confidence(self, severity: str, question_count: int) -> ConfidenceLevel:
        """Determine confidence level for estimate."""
        # High confidence for critical issues with few questions
        if severity == "critical" and question_count <= 2:
            return ConfidenceLevel.HIGH

        # Medium confidence for most cases
        if severity in ("critical", "high") or question_count <= 3:
            return ConfidenceLevel.MEDIUM

        # Low confidence for complex cases
        return ConfidenceLevel.LOW

    def _build_explanation(
        self,
        reason_code: ReasonCode,
        question_count: int,
        categories: list[QuestionCategory],
        expected_points: float,
    ) -> str:
        """Build human-readable explanation."""
        reason_info = get_reason_info(reason_code)
        cat_str = ", ".join(c.value for c in categories) if categories else "general"

        return (
            f"Fixing '{reason_info.name}' is expected to improve your score by "
            f"~{expected_points:.1f} points. This fix affects {question_count} "
            f"question(s) in the {cat_str} category/categories."
        )

    def _build_assumptions(self, reason_code: ReasonCode, question_count: int) -> list[str]:
        """Build list of assumptions for this estimate."""
        assumptions = [
            "Based on Tier C precomputed lookup tables",
            "Assumes fix is fully implemented as suggested",
            "Does not account for content quality variations",
        ]

        if question_count > 3:
            assumptions.append("Multiple questions may have overlapping improvements")

        reason_info = get_reason_info(reason_code)
        if reason_info.category == "technical":
            assumptions.append("Technical fixes may have broader impact than estimated")

        return assumptions

    def _calculate_totals(self, estimates: list[FixImpactEstimate]) -> tuple[float, float, float]:
        """Calculate total impact with overlap adjustment."""
        if not estimates:
            return 0.0, 0.0, 0.0

        # Simple sum (with diminishing returns for overlap)
        total_min = 0.0
        total_expected = 0.0
        total_max = 0.0

        # Apply 80% efficiency for each additional fix (overlap adjustment)
        efficiency = 1.0
        for i, estimate in enumerate(estimates):
            if i > 0:
                efficiency *= 0.8  # Diminishing returns

            total_min += estimate.impact_range.min_points * efficiency
            total_expected += estimate.impact_range.expected_points * efficiency
            total_max += estimate.impact_range.max_points * efficiency

        return total_min, total_expected, total_max

    def _determine_overall_confidence(self, estimates: list[FixImpactEstimate]) -> ConfidenceLevel:
        """Determine overall confidence for the plan."""
        if not estimates:
            return ConfidenceLevel.LOW

        # Count confidence levels
        high_count = sum(1 for e in estimates if e.impact_range.confidence == ConfidenceLevel.HIGH)
        low_count = sum(1 for e in estimates if e.impact_range.confidence == ConfidenceLevel.LOW)

        if high_count > len(estimates) / 2:
            return ConfidenceLevel.HIGH
        elif low_count > len(estimates) / 2:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.MEDIUM

    def _build_plan_notes(
        self, estimates: list[FixImpactEstimate], total_expected: float
    ) -> list[str]:
        """Build notes for the plan impact."""
        notes = []

        if total_expected >= 15:
            notes.append("Significant improvement potential - prioritize these fixes")
        elif total_expected >= 8:
            notes.append("Good improvement potential with the recommended fixes")
        else:
            notes.append("Moderate improvement expected - consider additional optimizations")

        # Check for technical fixes
        tech_fixes = [
            e for e in estimates if get_reason_info(e.reason_code).category == "technical"
        ]
        if tech_fixes:
            notes.append(
                "Technical fixes should be addressed first as they may block " "other improvements"
            )

        # Note about Tier C limitations
        notes.append(
            "Tier C estimates are conservative. Use Tier B for more accurate "
            "projections on specific fixes."
        )

        return notes


def estimate_fix_impact(fix: Fix) -> FixImpactEstimate:
    """
    Convenience function to estimate impact for a single fix.

    Args:
        fix: The fix to estimate

    Returns:
        FixImpactEstimate
    """
    estimator = TierCEstimator()
    return estimator.estimate_fix(fix)


def estimate_plan_impact(plan: FixPlan, top_n: int = 5) -> FixPlanImpact:
    """
    Convenience function to estimate impact for a fix plan.

    Args:
        plan: The fix plan
        top_n: Number of top fixes to highlight

    Returns:
        FixPlanImpact
    """
    estimator = TierCEstimator()
    return estimator.estimate_plan(plan, top_n)
