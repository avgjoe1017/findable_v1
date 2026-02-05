"""Findable Score v2 Calculator.

Combines all 7 scoring pillars into a unified Findable Score:
- Technical Readiness (12 points)
- Structure Quality (18 points)
- Schema Richness (13 points)
- Authority Signals (12 points)
- Entity Recognition (13 points) - NEW: External brand/entity awareness signals
- Retrieval Simulation (22 points)
- Answer Coverage (10 points)

Total: 100 points

Uses Findability Levels instead of letter grades for action-oriented feedback.

Weights can be dynamically loaded from the active CalibrationConfig.

Entity Recognition addresses the 23% pessimism bias by capturing signals that
indicate whether AI systems already know about the brand/entity (Wikipedia,
Wikidata, domain age, web presence). Sites with strong entity recognition
get cited even if their technical SEO is imperfect.
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import structlog

from worker.extraction.entity_recognition import EntityRecognitionResult
from worker.scoring.authority import AuthoritySignalsScore
from worker.scoring.calculator import ScoreBreakdown
from worker.scoring.schema import SchemaRichnessScore
from worker.scoring.structure import StructureQualityScore
from worker.scoring.technical import TechnicalReadinessScore

if TYPE_CHECKING:
    from api.models.calibration import CalibrationConfig

logger = structlog.get_logger(__name__)


# Default pillar weights (must sum to 100)
# These are used when no active CalibrationConfig exists
#
# Entity Recognition (13%) added to address 23% pessimism bias:
# - Sites with strong brand recognition get cited even with imperfect technical SEO
# - Captures Wikipedia presence, Wikidata entity, domain age, web presence
# - Redistributed weights from other pillars to maintain 100% total
DEFAULT_PILLAR_WEIGHTS = {
    "technical": 12,
    "structure": 18,
    "schema": 13,
    "authority": 12,
    "entity_recognition": 13,  # NEW: External brand/entity awareness
    "retrieval": 22,
    "coverage": 10,
}

# Backwards compatibility alias
PILLAR_WEIGHTS = DEFAULT_PILLAR_WEIGHTS


def get_pillar_weights(config: "CalibrationConfig | None" = None) -> dict[str, float]:
    """
    Get pillar weights from calibration config or defaults.

    Args:
        config: Optional CalibrationConfig to use. If None, uses cached
                weights or defaults.

    Returns:
        Dict of pillar name -> weight (must sum to 100)
    """
    # If explicit config provided, use it
    if config is not None:
        return config.weights

    # Use cached weights if available
    if _cached_weights is not None:
        return _cached_weights.copy()

    # Fall back to defaults
    return DEFAULT_PILLAR_WEIGHTS.copy()


# Cache for active calibration weights
# Updated via set_active_calibration_weights() when config changes
_cached_weights: dict[str, float] | None = None
_cached_config_name: str | None = None


def set_active_calibration_weights(
    weights: dict[str, float] | None,
    config_name: str | None = None,
) -> None:
    """
    Set the cached active calibration weights.

    Call this when the active CalibrationConfig changes.

    Args:
        weights: New weights to cache, or None to clear cache
        config_name: Name of the config (for logging)
    """
    global _cached_weights, _cached_config_name

    if weights is not None:
        # Validate sum
        total = sum(weights.values())
        if abs(total - 100.0) > 0.01:
            logger.warning(
                "invalid_weights_not_cached",
                total=total,
                config_name=config_name,
            )
            return

        _cached_weights = weights.copy()
        _cached_config_name = config_name
        logger.info(
            "calibration_weights_cached",
            config_name=config_name,
            weights=weights,
        )
    else:
        _cached_weights = None
        _cached_config_name = None
        logger.info("calibration_weights_cache_cleared")


def get_cached_config_name() -> str | None:
    """Get the name of the currently cached calibration config."""
    return _cached_config_name


async def load_active_calibration_weights() -> dict[str, float]:
    """
    Async function to load and cache active calibration weights from DB.

    Call this at startup or when config changes.

    Returns:
        The loaded weights (or defaults if no active config)
    """
    try:
        from sqlalchemy import select

        from api.database import async_session_maker
        from api.models.calibration import CalibrationConfig

        async with async_session_maker() as db:
            result = await db.execute(
                select(CalibrationConfig).where(CalibrationConfig.is_active == True)  # noqa: E712
            )
            active_config = result.scalar_one_or_none()

            if active_config:
                set_active_calibration_weights(
                    weights=active_config.weights,
                    config_name=active_config.name,
                )
                return active_config.weights

    except Exception as e:
        logger.debug("active_calibration_load_failed", error=str(e))

    # No active config - clear cache and return defaults
    set_active_calibration_weights(None)
    return DEFAULT_PILLAR_WEIGHTS.copy()


# Findability Levels - action-oriented, not judgmental
FINDABILITY_LEVELS = {
    "not_yet_findable": {
        "min_score": 0,
        "max_score": 39,
        "label": "Not Yet Findable",
        "summary": "AI crawlers can't effectively access or cite your content yet.",
        "focus": "Fix critical technical barriers first.",
    },
    "partially_findable": {
        "min_score": 40,
        "max_score": 54,
        "label": "Partially Findable",
        "summary": "Foundation in place, but missing key signals that drive citations.",
        "focus": "Add structured data and trust signals.",
    },
    "findable": {
        "min_score": 55,
        "max_score": 69,
        "label": "Findable",
        "summary": "AI can find and cite you. Now optimize to become the preferred source.",
        "focus": "Strengthen authority and content coverage.",
    },
    "highly_findable": {
        "min_score": 70,
        "max_score": 84,
        "label": "Highly Findable",
        "summary": "You're ahead of most competitors. Fine-tune for maximum visibility.",
        "focus": "Address remaining gaps and monitor for changes.",
    },
    "optimized": {
        "min_score": 85,
        "max_score": 100,
        "label": "Optimized",
        "summary": "Your site is well-optimized for AI discovery.",
        "focus": "Maintain current performance and track competitor moves.",
    },
}

# Milestones for path-forward tracking
MILESTONES = [
    {"score": 40, "name": "Partially Findable", "description": "Basic AI accessibility achieved"},
    {"score": 55, "name": "Findable", "description": "AI can reliably find and cite you"},
    {"score": 70, "name": "Highly Findable", "description": "Competitive advantage unlocked"},
    {"score": 85, "name": "Optimized", "description": "Top-tier AI sourceability"},
]


@dataclass
class PillarScore:
    """Score for a single pillar in the v2 system."""

    name: str
    display_name: str
    raw_score: float  # 0-100
    max_points: float  # Points this pillar contributes
    points_earned: float
    weight_pct: float  # Percentage weight (0-100)
    level: str  # full, partial, limited (progress-based)
    description: str
    evaluated: bool = True  # Whether this pillar was actually evaluated
    components: list[dict] = field(default_factory=list)
    critical_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "raw_score": round(self.raw_score, 2),
            "max_points": self.max_points,
            "points_earned": round(self.points_earned, 2),
            "weight_pct": self.weight_pct,
            "level": self.level,
            "description": self.description,
            "evaluated": self.evaluated,
            "components": self.components,
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
        }


@dataclass
class MilestoneInfo:
    """Information about the next milestone."""

    score: int
    name: str
    description: str
    points_needed: float

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "name": self.name,
            "description": self.description,
            "points_needed": round(self.points_needed, 1),
        }


@dataclass
class PathAction:
    """A single action in the path forward."""

    action: str
    impact_points: float
    effort: str
    pillar: str

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "impact_points": round(self.impact_points, 1),
            "effort": self.effort,
            "pillar": self.pillar,
        }


@dataclass
class FindableScoreV2:
    """Complete Findable Score v2 with all pillar breakdowns."""

    # Overall score (always 0-100 scale, rescaled when partial)
    total_score: float  # 0-100 (effective score)
    raw_points_earned: float = 0.0  # Sum of actual points earned

    # Findability Level (replaces letter grades)
    level: str  # e.g., "partially_findable"
    level_label: str  # e.g., "Partially Findable"
    level_summary: str  # e.g., "Foundation in place..."
    level_focus: str  # e.g., "Add structured data..."

    # Next milestone
    next_milestone: MilestoneInfo | None
    points_to_milestone: float

    # Path forward (top actions to reach milestone)
    path_forward: list[PathAction] = field(default_factory=list)

    # Pillar scores
    pillars: list[PillarScore] = field(default_factory=list)
    pillar_breakdown: dict[str, PillarScore] = field(default_factory=dict)

    # Summary metrics
    pillars_good: int = 0
    pillars_warning: int = 0
    pillars_critical: int = 0

    # Aggregated issues
    all_critical_issues: list[str] = field(default_factory=list)
    top_recommendations: list[str] = field(default_factory=list)

    # Strengths (positive findings to celebrate)
    strengths: list[str] = field(default_factory=list)

    # Partial analysis tracking
    pillars_evaluated: int = 6
    pillars_not_evaluated: int = 0
    max_evaluated_points: float = 100.0  # Max points from evaluated pillars
    is_partial: bool = False  # True if some pillars weren't evaluated

    # Metadata
    version: str = "2.2"  # Added Entity Recognition pillar
    calculation_summary: list[str] = field(default_factory=list)

    @property
    def evaluated_score_pct(self) -> float:
        """Score as percentage of evaluated pillars only.

        Note: With the rescaling fix, total_score IS already the effective
        0-100 score, so this returns total_score directly.
        """
        return self.total_score

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "total_score": round(self.total_score, 2),
            "raw_points_earned": round(self.raw_points_earned, 2),
            # Findability Level
            "level": self.level,
            "level_label": self.level_label,
            "level_summary": self.level_summary,
            "level_focus": self.level_focus,
            # Milestone
            "next_milestone": self.next_milestone.to_dict() if self.next_milestone else None,
            "points_to_milestone": round(self.points_to_milestone, 1),
            # Path forward
            "path_forward": [p.to_dict() for p in self.path_forward],
            # Pillars
            "pillars": [p.to_dict() for p in self.pillars],
            "pillar_breakdown": {k: v.to_dict() for k, v in self.pillar_breakdown.items()},
            "pillars_good": self.pillars_good,
            "pillars_warning": self.pillars_warning,
            "pillars_critical": self.pillars_critical,
            # Issues and recommendations
            "all_critical_issues": self.all_critical_issues,
            "top_recommendations": self.top_recommendations,
            "strengths": self.strengths,
            "calculation_summary": self.calculation_summary,
            # Partial analysis tracking
            "pillars_evaluated": self.pillars_evaluated,
            "pillars_not_evaluated": self.pillars_not_evaluated,
            "max_evaluated_points": round(self.max_evaluated_points, 2),
            "is_partial": self.is_partial,
            "evaluated_score_pct": round(self.evaluated_score_pct, 2),
        }

    def show_the_math(self) -> str:
        """Generate human-readable calculation breakdown with path-forward framing."""
        lines = [
            "=" * 60,
            f"FINDABLE SCORE: {self.total_score:.0f}/100",
            f"Level: {self.level_label.upper()}",
            "=" * 60,
            "",
            f'"{self.level_summary}"',
            "",
        ]

        # Show strengths first (positive framing)
        if self.strengths:
            lines.append("WHAT'S WORKING:")
            for strength in self.strengths[:5]:
                lines.append(f"  + {strength}")
            lines.append("")

        # Show limited visibility pillars
        weak_pillars = [p for p in self.pillars if p.evaluated and p.level == "limited"]
        if weak_pillars:
            lines.append("WHAT'S HOLDING YOU BACK:")
            for pillar in weak_pillars:
                lines.append(
                    f"  - {pillar.display_name}: {pillar.raw_score:.0f}/100 - "
                    f"{pillar.description}"
                )
            lines.append("")

        # Path to next milestone
        if self.next_milestone and self.path_forward:
            lines.extend(
                [
                    "-" * 60,
                    f'PATH TO "{self.next_milestone.name.upper()}" ({self.next_milestone.score} pts) '
                    f"- {self.points_to_milestone:.0f} points away",
                    "-" * 60,
                ]
            )

            # Table header
            lines.append(f"{'Action':<40} {'Impact':>8} {'Effort':>10}")
            lines.append("-" * 60)

            total_impact = 0
            for action in self.path_forward:
                lines.append(
                    f"{action.action[:40]:<40} {'+' + str(int(action.impact_points)) + ' pts':>8} "
                    f"{action.effort:>10}"
                )
                total_impact += action.impact_points

            lines.append("-" * 60)
            projected = self.total_score + total_impact
            lines.append(
                f"Complete these -> {projected:.0f}/100 ({self._get_level_for_score(projected)})"
            )
            lines.append("")

        # Pillar breakdown
        lines.extend(
            [
                "-" * 60,
                "PILLAR BREAKDOWN",
                "-" * 60,
            ]
        )

        for pillar in self.pillars:
            if not pillar.evaluated:
                lines.append(f"[-] {pillar.display_name}: NOT RUN")
            else:
                icon = "+" if pillar.level == "full" else "!" if pillar.level == "partial" else "X"
                lines.append(
                    f"[{icon}] {pillar.display_name}: "
                    f"{pillar.raw_score:.0f}/100 -> {pillar.points_earned:.1f}/{pillar.max_points} pts"
                )

        if self.is_partial:
            lines.extend(
                [
                    "",
                    f"NOTE: {self.pillars_not_evaluated} pillar(s) not evaluated - "
                    f"score rescaled from {self.raw_points_earned:.1f}/{self.max_evaluated_points:.0f} pts "
                    f"to {self.total_score:.0f}/100",
                ]
            )

        lines.extend(["", "=" * 60])
        return "\n".join(lines)

    def _get_level_for_score(self, score: float) -> str:
        """Get level label for a given score."""
        if score >= 85:
            return "Optimized"
        elif score >= 70:
            return "Highly Findable"
        elif score >= 55:
            return "Findable"
        elif score >= 40:
            return "Partially Findable"
        else:
            return "Not Yet Findable"


class FindableScoreCalculatorV2:
    """Calculates the unified Findable Score v2 from all pillar scores.

    Supports dynamic weights from CalibrationConfig for continuous learning.
    """

    def __init__(
        self,
        weights: dict[str, float] | None = None,
        config_name: str | None = None,
    ):
        """
        Initialize the calculator.

        Args:
            weights: Optional explicit weights dict. If None, uses cached
                     calibration weights or defaults.
            config_name: Name of config being used (for transparency/logging)
        """
        if weights is not None:
            self._weights = weights.copy()
            self._config_name = config_name or "custom"
        else:
            # Use cached weights or defaults
            self._weights = get_pillar_weights()
            self._config_name = get_cached_config_name() or "default"

        # Validate weights sum to 100
        total = sum(self._weights.values())
        if abs(total - 100.0) > 0.01:
            logger.warning(
                "invalid_pillar_weights",
                total=total,
                config_name=self._config_name,
            )
            self._weights = DEFAULT_PILLAR_WEIGHTS.copy()
            self._config_name = "default (fallback)"

        logger.debug(
            "calculator_initialized",
            config_name=self._config_name,
            weights=self._weights,
        )

    @property
    def config_name(self) -> str:
        """Name of the calibration config being used."""
        return self._config_name

    @property
    def weights(self) -> dict[str, float]:
        """Current pillar weights."""
        return self._weights.copy()

    def calculate(
        self,
        technical_score: TechnicalReadinessScore | None = None,
        structure_score: StructureQualityScore | None = None,
        schema_score: SchemaRichnessScore | None = None,
        authority_score: AuthoritySignalsScore | None = None,
        entity_recognition_result: EntityRecognitionResult | None = None,
        simulation_breakdown: ScoreBreakdown | None = None,
        fixes: list[dict] | None = None,
    ) -> FindableScoreV2:
        """
        Calculate unified Findable Score v2.

        Args:
            technical_score: Technical Readiness pillar score
            structure_score: Structure Quality pillar score
            schema_score: Schema Richness pillar score
            authority_score: Authority Signals pillar score
            entity_recognition_result: Entity Recognition pillar score (brand awareness)
            simulation_breakdown: Existing v1 score breakdown (for retrieval + coverage)
            fixes: Optional list of fixes with impact_points for path_forward

        Returns:
            FindableScoreV2 with complete breakdown
        """
        pillars = []
        pillar_breakdown = {}
        calculation_steps = []
        all_critical = []
        all_recommendations = []

        # 1. Technical Readiness (12 points)
        tech_pillar = self._build_technical_pillar(technical_score)
        pillars.append(tech_pillar)
        pillar_breakdown["technical"] = tech_pillar
        all_critical.extend(tech_pillar.critical_issues)
        all_recommendations.extend(tech_pillar.recommendations)
        calculation_steps.append(
            f"Technical: {tech_pillar.raw_score:.0f}/100 x {tech_pillar.weight_pct}% = "
            f"{tech_pillar.points_earned:.1f} pts"
        )

        # 2. Structure Quality (18 points)
        struct_pillar = self._build_structure_pillar(structure_score)
        pillars.append(struct_pillar)
        pillar_breakdown["structure"] = struct_pillar
        all_critical.extend(struct_pillar.critical_issues)
        all_recommendations.extend(struct_pillar.recommendations)
        calculation_steps.append(
            f"Structure: {struct_pillar.raw_score:.0f}/100 x {struct_pillar.weight_pct}% = "
            f"{struct_pillar.points_earned:.1f} pts"
        )

        # 3. Schema Richness (13 points)
        schema_pillar = self._build_schema_pillar(schema_score)
        pillars.append(schema_pillar)
        pillar_breakdown["schema"] = schema_pillar
        all_critical.extend(schema_pillar.critical_issues)
        all_recommendations.extend(schema_pillar.recommendations)
        calculation_steps.append(
            f"Schema: {schema_pillar.raw_score:.0f}/100 x {schema_pillar.weight_pct}% = "
            f"{schema_pillar.points_earned:.1f} pts"
        )

        # 4. Authority Signals (12 points)
        auth_pillar = self._build_authority_pillar(authority_score)
        pillars.append(auth_pillar)
        pillar_breakdown["authority"] = auth_pillar
        all_critical.extend(auth_pillar.critical_issues)
        all_recommendations.extend(auth_pillar.recommendations)
        calculation_steps.append(
            f"Authority: {auth_pillar.raw_score:.0f}/100 x {auth_pillar.weight_pct}% = "
            f"{auth_pillar.points_earned:.1f} pts"
        )

        # 5. Entity Recognition (13 points) - NEW: Addresses 23% pessimism bias
        entity_pillar = self._build_entity_recognition_pillar(entity_recognition_result)
        pillars.append(entity_pillar)
        pillar_breakdown["entity_recognition"] = entity_pillar
        all_critical.extend(entity_pillar.critical_issues)
        all_recommendations.extend(entity_pillar.recommendations)
        calculation_steps.append(
            f"Entity Recognition: {entity_pillar.raw_score:.0f}/100 x {entity_pillar.weight_pct}% = "
            f"{entity_pillar.points_earned:.1f} pts"
        )

        # 6. Retrieval Simulation (22 points)
        retrieval_pillar = self._build_retrieval_pillar(simulation_breakdown)
        pillars.append(retrieval_pillar)
        pillar_breakdown["retrieval"] = retrieval_pillar
        calculation_steps.append(
            f"Retrieval: {retrieval_pillar.raw_score:.0f}/100 x {retrieval_pillar.weight_pct}% = "
            f"{retrieval_pillar.points_earned:.1f} pts"
        )

        # 7. Answer Coverage (10 points)
        coverage_pillar = self._build_coverage_pillar(simulation_breakdown)
        pillars.append(coverage_pillar)
        pillar_breakdown["coverage"] = coverage_pillar
        calculation_steps.append(
            f"Coverage: {coverage_pillar.raw_score:.0f}/100 x {coverage_pillar.weight_pct}% = "
            f"{coverage_pillar.points_earned:.1f} pts"
        )

        # Calculate total raw points
        raw_points = sum(p.points_earned for p in pillars)

        # Track partial analysis
        total_pillars = len(pillars)  # Now 7 pillars
        pillars_evaluated = sum(1 for p in pillars if p.evaluated)
        pillars_not_evaluated = total_pillars - pillars_evaluated
        max_evaluated_points = sum(p.max_points for p in pillars if p.evaluated)
        is_partial = pillars_not_evaluated > 0

        # total_score is ALWAYS on a 0-100 scale.
        # When partial, rescale so the number and level always agree.
        if is_partial and max_evaluated_points > 0:
            total_score = (raw_points / max_evaluated_points) * 100
        else:
            total_score = raw_points

        calculation_steps.append("")
        if is_partial:
            calculation_steps.append(
                f"Raw points: {raw_points:.1f}/{max_evaluated_points:.0f} evaluated points "
                f"({pillars_not_evaluated} pillar{'s' if pillars_not_evaluated != 1 else ''} not run)"
            )
            calculation_steps.append(f"Effective score: {total_score:.1f}/100 (rescaled to 0-100)")
        else:
            calculation_steps.append(f"Total: {total_score:.1f}/100 points")

        level_info = self.get_findability_level(total_score)

        # Get next milestone
        next_milestone = self.get_next_milestone(total_score)
        points_to_milestone = next_milestone.points_needed if next_milestone else 0

        # Build path forward if fixes are provided
        path_forward = []
        if fixes and next_milestone:
            path_forward = self.get_path_forward(
                score=total_score,
                fixes=fixes,
                milestone_target=next_milestone.score,
            )

        # Count pillar levels (only count evaluated pillars)
        # Using progress-based terminology: full/partial/limited
        evaluated_pillars = [p for p in pillars if p.evaluated]
        pillars_good = sum(1 for p in evaluated_pillars if p.level == "full")
        pillars_warning = sum(1 for p in evaluated_pillars if p.level == "partial")
        pillars_critical = sum(1 for p in evaluated_pillars if p.level == "limited")

        # Deduplicate and limit issues/recommendations
        seen_issues = set()
        unique_critical = []
        for issue in all_critical:
            if issue not in seen_issues:
                seen_issues.add(issue)
                unique_critical.append(issue)

        seen_recs = set()
        unique_recs = []
        for rec in all_recommendations:
            if rec not in seen_recs:
                seen_recs.add(rec)
                unique_recs.append(rec)

        # Detect strengths (positive findings to celebrate)
        strengths = self._detect_strengths(
            technical_score=technical_score,
            structure_score=structure_score,
            schema_score=schema_score,
            authority_score=authority_score,
            entity_recognition_result=entity_recognition_result,
            simulation_breakdown=simulation_breakdown,
        )

        result = FindableScoreV2(
            total_score=total_score,
            raw_points_earned=raw_points,
            # Findability Level
            level=level_info["id"],
            level_label=level_info["label"],
            level_summary=level_info["summary"],
            level_focus=level_info["focus"],
            # Milestone
            next_milestone=next_milestone,
            points_to_milestone=points_to_milestone,
            path_forward=path_forward,
            # Pillars
            pillars=pillars,
            pillar_breakdown=pillar_breakdown,
            pillars_good=pillars_good,
            pillars_warning=pillars_warning,
            pillars_critical=pillars_critical,
            # Issues and recommendations
            all_critical_issues=unique_critical[:10],
            top_recommendations=unique_recs[:10],
            strengths=strengths[:10],
            # Partial analysis tracking
            pillars_evaluated=pillars_evaluated,
            pillars_not_evaluated=pillars_not_evaluated,
            max_evaluated_points=max_evaluated_points,
            is_partial=is_partial,
            calculation_summary=calculation_steps,
        )

        logger.info(
            "findable_score_v2_calculated",
            total_score=total_score,
            level=level_info["id"],
            level_label=level_info["label"],
            pillars_good=pillars_good,
            pillars_warning=pillars_warning,
            pillars_critical=pillars_critical,
            pillars_evaluated=pillars_evaluated,
            is_partial=is_partial,
            max_evaluated_points=max_evaluated_points,
        )

        return result

    def get_findability_level(self, score: float) -> dict:
        """
        Return the findability level dict for a given score.

        Uses threshold-based comparison (>=) to avoid floating-point gaps
        between integer boundaries.

        Args:
            score: Score 0-100

        Returns:
            Dict with id, label, summary, focus, min_score, max_score
        """
        if score >= 85:
            level_id = "optimized"
        elif score >= 70:
            level_id = "highly_findable"
        elif score >= 55:
            level_id = "findable"
        elif score >= 40:
            level_id = "partially_findable"
        else:
            level_id = "not_yet_findable"

        return {"id": level_id, **FINDABILITY_LEVELS[level_id]}

    def get_next_milestone(self, score: float) -> MilestoneInfo | None:
        """
        Return the next milestone above current score, or None if optimized.

        Args:
            score: Current score 0-100

        Returns:
            MilestoneInfo or None if already at highest level
        """
        for milestone in MILESTONES:
            if score < milestone["score"]:
                return MilestoneInfo(
                    score=milestone["score"],
                    name=milestone["name"],
                    description=milestone["description"],
                    points_needed=round(milestone["score"] - score, 1),
                )
        return None  # Already at highest level

    def get_path_forward(
        self,
        score: float,
        fixes: list[dict],
        milestone_target: int,
    ) -> list[PathAction]:
        """
        Return top fixes that would get user to next milestone.

        Prioritize by impact, stop when cumulative points exceed milestone gap.

        Args:
            score: Current score
            fixes: List of fix dicts with impact_points, title, effort, category
            milestone_target: Target milestone score

        Returns:
            List of PathAction items (3-5 items)
        """
        points_needed = milestone_target - score
        path = []
        cumulative = 0

        # Sort fixes by impact (descending)
        sorted_fixes = sorted(
            fixes,
            key=lambda f: f.get("impact_points", 0),
            reverse=True,
        )

        for fix in sorted_fixes:
            impact = fix.get("impact_points", 0)
            if impact <= 0:
                continue

            path.append(
                PathAction(
                    action=fix.get("title", "Unknown fix"),
                    impact_points=impact,
                    effort=fix.get("effort", "Unknown"),
                    pillar=fix.get("category", "general"),
                )
            )
            cumulative += impact

            # Stop when we have enough impact to reach milestone AND at least 3 items
            if cumulative >= points_needed and len(path) >= 3:
                break

            # Max 5 items in path
            if len(path) >= 5:
                break

        return path

    def _build_technical_pillar(self, score: TechnicalReadinessScore | None) -> PillarScore:
        """Build Technical Readiness pillar."""
        max_points = self._weights["technical"]
        weight_pct = max_points

        if not score:
            return PillarScore(
                name="technical",
                display_name="Technical Readiness",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed",
                evaluated=False,
            )

        points = score.total_score / 100 * max_points

        return PillarScore(
            name="technical",
            display_name="Technical Readiness",
            raw_score=score.total_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=score.level,
            description="Can AI access your site?",
            components=[c.to_dict() for c in score.components],
            critical_issues=score.critical_issues[:3],
            recommendations=[],  # Technical fixes are in fix generator
        )

    def _build_structure_pillar(self, score: StructureQualityScore | None) -> PillarScore:
        """Build Structure Quality pillar."""
        max_points = self._weights["structure"]
        weight_pct = max_points

        if not score:
            return PillarScore(
                name="structure",
                display_name="Structure Quality",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed",
                evaluated=False,
            )

        points = score.total_score / 100 * max_points

        return PillarScore(
            name="structure",
            display_name="Structure Quality",
            raw_score=score.total_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=score.level,
            description="Is your content extractable?",
            components=[c.to_dict() for c in score.components],
            critical_issues=score.critical_issues[:3],
            recommendations=score.recommendations[:3],
        )

    def _build_schema_pillar(self, score: SchemaRichnessScore | None) -> PillarScore:
        """Build Schema Richness pillar."""
        max_points = self._weights["schema"]
        weight_pct = max_points

        if not score:
            return PillarScore(
                name="schema",
                display_name="Schema Richness",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed",
                evaluated=False,
            )

        points = score.total_score / 100 * max_points

        return PillarScore(
            name="schema",
            display_name="Schema Richness",
            raw_score=score.total_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=score.level,
            description="Is your content machine-readable?",
            components=[c.to_dict() for c in score.components],
            critical_issues=score.critical_issues[:3],
            recommendations=score.recommendations[:3],
        )

    def _build_authority_pillar(self, score: AuthoritySignalsScore | None) -> PillarScore:
        """Build Authority Signals pillar."""
        max_points = self._weights["authority"]
        weight_pct = max_points

        if not score:
            return PillarScore(
                name="authority",
                display_name="Authority Signals",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed",
                evaluated=False,
            )

        points = score.total_score / 100 * max_points

        return PillarScore(
            name="authority",
            display_name="Authority Signals",
            raw_score=score.total_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=score.level,
            description="Does AI trust your content?",
            components=[c.to_dict() for c in score.components],
            critical_issues=score.critical_issues[:3],
            recommendations=score.recommendations[:3],
        )

    def _build_entity_recognition_pillar(
        self, result: EntityRecognitionResult | None
    ) -> PillarScore:
        """Build Entity Recognition pillar.

        Measures external brand/entity awareness signals to address pessimism bias.
        Sites with strong entity recognition get cited even if technical SEO is imperfect.
        """
        max_points = self._weights.get("entity_recognition", 13)
        weight_pct = max_points

        if not result:
            return PillarScore(
                name="entity_recognition",
                display_name="Entity Recognition",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed",
                evaluated=False,
            )

        # EntityRecognitionResult.normalized_score is 0-100
        raw_score = result.normalized_score
        points = raw_score / 100 * max_points

        level = "full" if raw_score >= 50 else "partial" if raw_score >= 25 else "limited"

        # Build components from signal scores
        components = []
        if result.wikipedia:
            wiki_score = result.wikipedia.calculate_score()
            components.append(
                {
                    "name": "Wikipedia Presence",
                    "raw_score": wiki_score,
                    "max_score": result.wikipedia.max_score,
                    "description": "Wikipedia page existence and quality",
                }
            )
        if result.wikidata:
            wiki_score = result.wikidata.calculate_score()
            components.append(
                {
                    "name": "Wikidata Entity",
                    "raw_score": wiki_score,
                    "max_score": result.wikidata.max_score,
                    "description": "Wikidata knowledge graph presence",
                }
            )
        if result.domain_signals:
            domain_score = result.domain_signals.calculate_score()
            components.append(
                {
                    "name": "Domain Signals",
                    "raw_score": domain_score,
                    "max_score": result.domain_signals.max_score,
                    "description": "Domain age and TLD quality",
                }
            )
        if result.web_presence:
            web_score = result.web_presence.calculate_score()
            components.append(
                {
                    "name": "Web Presence",
                    "raw_score": web_score,
                    "max_score": result.web_presence.max_score,
                    "description": "Search visibility and news mentions",
                }
            )

        # Critical issues
        critical_issues = []
        if raw_score < 25:
            if not result.wikipedia or not result.wikipedia.has_page:
                critical_issues.append("No Wikipedia presence for brand/entity")
            if not result.wikidata or not result.wikidata.has_entity:
                critical_issues.append("No Wikidata entity for brand")

        # Recommendations
        recommendations = []
        if raw_score < 50:
            if not result.wikipedia or not result.wikipedia.has_page:
                recommendations.append("Establish Wikipedia notability for your brand")
            if (
                result.domain_signals
                and result.domain_signals.domain_age_years
                and result.domain_signals.domain_age_years < 2
            ):
                recommendations.append("Domain age is a trust signal - focus on longevity")
            recommendations.append(
                "Build web presence through authoritative mentions and news coverage"
            )

        return PillarScore(
            name="entity_recognition",
            display_name="Entity Recognition",
            raw_score=raw_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=level,
            description="Does AI already know your brand?",
            components=components,
            critical_issues=critical_issues[:3],
            recommendations=recommendations[:3],
        )

    def _build_retrieval_pillar(self, breakdown: ScoreBreakdown | None) -> PillarScore:
        """Build Retrieval Simulation pillar from v1 score."""
        max_points = self._weights["retrieval"]
        weight_pct = max_points

        if not breakdown:
            return PillarScore(
                name="retrieval",
                display_name="Retrieval Quality",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed - requires simulation run",
                evaluated=False,
            )

        # Use the v1 total score as retrieval quality
        raw_score = breakdown.total_score
        points = raw_score / 100 * max_points

        level = "full" if raw_score >= 70 else "partial" if raw_score >= 40 else "limited"

        return PillarScore(
            name="retrieval",
            display_name="Retrieval Quality",
            raw_score=raw_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=level,
            description="Can AI find relevant content?",
            components=[],
            critical_issues=[],
            recommendations=[],
        )

    def _build_coverage_pillar(self, breakdown: ScoreBreakdown | None) -> PillarScore:
        """Build Answer Coverage pillar from v1 score."""
        max_points = self._weights["coverage"]
        weight_pct = max_points

        if not breakdown:
            return PillarScore(
                name="coverage",
                display_name="Answer Coverage",
                raw_score=0.0,
                max_points=max_points,
                points_earned=0.0,
                weight_pct=weight_pct,
                level="limited",
                description="Not analyzed - requires simulation run",
                evaluated=False,
            )

        # Calculate coverage percentage
        raw_score = breakdown.coverage_percentage
        points = raw_score / 100 * max_points

        level = "full" if raw_score >= 70 else "partial" if raw_score >= 40 else "limited"

        return PillarScore(
            name="coverage",
            display_name="Answer Coverage",
            raw_score=raw_score,
            max_points=max_points,
            points_earned=points,
            weight_pct=weight_pct,
            level=level,
            description="How many questions can you answer?",
            components=[],
            critical_issues=[],
            recommendations=[],
        )

    def _detect_strengths(
        self,
        technical_score: TechnicalReadinessScore | None,
        structure_score: StructureQualityScore | None,
        schema_score: SchemaRichnessScore | None,
        authority_score: AuthoritySignalsScore | None,
        entity_recognition_result: EntityRecognitionResult | None,
        simulation_breakdown: ScoreBreakdown | None,
    ) -> list[str]:
        """
        Detect positive findings to celebrate.

        This highlights things the site is doing well, providing
        balanced feedback instead of only showing problems.
        """
        strengths = []

        # Technical strengths
        if technical_score:
            # llms.txt (early adopter win!)
            if technical_score.llms_txt_result and technical_score.llms_txt_result.exists:
                llms = technical_score.llms_txt_result
                if llms.link_count > 0:
                    strengths.append(
                        f"llms.txt with {llms.link_count} links - early adopter of AI discoverability standard"
                    )
                else:
                    strengths.append(
                        "llms.txt file exists - early adopter of AI discoverability standard"
                    )

            # robots.txt allows AI
            if technical_score.robots_result:
                robots = technical_score.robots_result
                if robots.all_allowed:
                    strengths.append("robots.txt allows all AI crawlers")
                elif robots.crawlers:
                    allowed = sum(1 for c in robots.crawlers.values() if c.allowed)
                    if allowed > 0:
                        strengths.append(f"robots.txt allows {allowed} AI crawler(s)")

            # Fast TTFB
            if technical_score.ttfb_result:
                ttfb = technical_score.ttfb_result
                if hasattr(ttfb, "ttfb_ms") and ttfb.ttfb_ms:
                    if ttfb.ttfb_ms < 200:
                        strengths.append(f"Excellent server response time ({ttfb.ttfb_ms}ms TTFB)")
                    elif ttfb.ttfb_ms < 500:
                        strengths.append(f"Good server response time ({ttfb.ttfb_ms}ms TTFB)")

            # HTTPS
            if technical_score.is_https:
                strengths.append("HTTPS enabled (secure connection)")

        # Structure strengths
        if structure_score and structure_score.total_score >= 70:
            strengths.append("Well-structured content with clear hierarchy")

        # Schema strengths
        if schema_score:
            if schema_score.total_score >= 70:
                strengths.append("Rich structured data markup")
            elif schema_score.total_score >= 50:
                # Look for specific schema types
                for comp in schema_score.components:
                    if comp.name == "Schema Types" and comp.raw_score >= 50:
                        strengths.append("Multiple schema types implemented")
                        break

        # Authority strengths
        if authority_score:
            if authority_score.total_score >= 70:
                strengths.append("Strong E-E-A-T signals (author attribution, credentials)")
            else:
                # Check individual components
                auth_analysis = authority_score.authority_analysis
                if auth_analysis:
                    if auth_analysis.has_author and auth_analysis.has_credentials:
                        strengths.append("Author credentials and expertise visible")
                    if auth_analysis.authoritative_citations >= 3:
                        strengths.append(
                            f"{auth_analysis.authoritative_citations} authoritative citations"
                        )
                    if auth_analysis.freshness_level in ["fresh", "recent"]:
                        strengths.append("Content is fresh and regularly updated")

        # Entity Recognition strengths
        if entity_recognition_result:
            if entity_recognition_result.normalized_score >= 60:
                strengths.append("Strong brand recognition across knowledge bases")
            else:
                # Check individual signals
                if (
                    entity_recognition_result.wikipedia
                    and entity_recognition_result.wikipedia.has_page
                ):
                    wiki = entity_recognition_result.wikipedia
                    if wiki.infobox_present:
                        strengths.append("Wikipedia page with infobox (strong brand signal)")
                    elif wiki.page_length_chars and wiki.page_length_chars > 5000:
                        strengths.append("Substantial Wikipedia presence")
                    else:
                        strengths.append("Wikipedia page exists for brand")
                if (
                    entity_recognition_result.wikidata
                    and entity_recognition_result.wikidata.has_entity
                ):
                    wikidata = entity_recognition_result.wikidata
                    if wikidata.sitelink_count and wikidata.sitelink_count >= 20:
                        strengths.append(
                            f"Wikidata entity with {wikidata.sitelink_count} language versions"
                        )
                    else:
                        strengths.append("Wikidata knowledge graph presence")
                if entity_recognition_result.domain_signals:
                    domain = entity_recognition_result.domain_signals
                    if domain.domain_age_years and domain.domain_age_years >= 10:
                        strengths.append(
                            f"Established domain ({int(domain.domain_age_years)}+ years)"
                        )
                    elif domain.is_premium_tld:
                        strengths.append("Premium TLD (.com/.org/.net)")

        # Retrieval/Coverage strengths
        if simulation_breakdown:
            if simulation_breakdown.coverage_percentage >= 80:
                strengths.append(
                    f"Excellent question coverage ({simulation_breakdown.coverage_percentage:.0f}%)"
                )
            elif simulation_breakdown.coverage_percentage >= 60:
                strengths.append(
                    f"Good question coverage ({simulation_breakdown.coverage_percentage:.0f}%)"
                )

            if simulation_breakdown.total_score >= 70:
                strengths.append("High retrieval quality - content is easy to find")

        return strengths


def calculate_findable_score_v2(
    technical_score: TechnicalReadinessScore | None = None,
    structure_score: StructureQualityScore | None = None,
    schema_score: SchemaRichnessScore | None = None,
    authority_score: AuthoritySignalsScore | None = None,
    entity_recognition_result: EntityRecognitionResult | None = None,
    simulation_breakdown: ScoreBreakdown | None = None,
    fixes: list[dict] | None = None,
) -> FindableScoreV2:
    """
    Convenience function to calculate Findable Score v2.

    Args:
        technical_score: Technical Readiness pillar
        structure_score: Structure Quality pillar
        schema_score: Schema Richness pillar
        authority_score: Authority Signals pillar
        entity_recognition_result: Entity Recognition pillar (brand awareness)
        simulation_breakdown: v1 score breakdown for retrieval + coverage
        fixes: Optional list of fixes with impact_points for path_forward

    Returns:
        FindableScoreV2 with complete breakdown
    """
    calculator = FindableScoreCalculatorV2()
    return calculator.calculate(
        technical_score=technical_score,
        structure_score=structure_score,
        schema_score=schema_score,
        authority_score=authority_score,
        entity_recognition_result=entity_recognition_result,
        simulation_breakdown=simulation_breakdown,
        fixes=fixes,
    )
