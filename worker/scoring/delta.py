"""Delta comparison between Findable Score runs.

Tracks score changes between audit runs, showing improvement/regression
per pillar and generating actionable insights about progress.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from worker.scoring.calculator_v2 import FindableScoreV2, PillarScore


class ChangeDirection(StrEnum):
    """Direction of score change."""

    IMPROVED = "improved"
    DECLINED = "declined"
    UNCHANGED = "unchanged"


class ChangeSignificance(StrEnum):
    """Significance level of a score change."""

    MAJOR = "major"  # >= 10 points
    MODERATE = "moderate"  # 5-9 points
    MINOR = "minor"  # 1-4 points
    NEGLIGIBLE = "negligible"  # < 1 point


@dataclass
class PillarDelta:
    """Change in a single pillar between runs."""

    pillar_name: str
    display_name: str

    # Previous run values
    previous_score: float
    previous_points: float
    previous_level: str

    # Current run values
    current_score: float
    current_points: float
    current_level: str

    # Calculated deltas
    score_delta: float  # Change in raw score (0-100)
    points_delta: float  # Change in weighted points
    direction: ChangeDirection
    significance: ChangeSignificance

    # Level change
    level_improved: bool
    level_declined: bool
    max_points: float

    def to_dict(self) -> dict:
        return {
            "pillar_name": self.pillar_name,
            "display_name": self.display_name,
            "previous_score": round(self.previous_score, 1),
            "previous_points": round(self.previous_points, 1),
            "previous_level": self.previous_level,
            "current_score": round(self.current_score, 1),
            "current_points": round(self.current_points, 1),
            "current_level": self.current_level,
            "score_delta": round(self.score_delta, 1),
            "points_delta": round(self.points_delta, 1),
            "direction": self.direction.value,
            "significance": self.significance.value,
            "level_improved": self.level_improved,
            "level_declined": self.level_declined,
            "max_points": self.max_points,
        }

    @property
    def delta_display(self) -> str:
        """Human-readable delta string."""
        if abs(self.score_delta) < 0.5:
            return "—"
        sign = "+" if self.score_delta > 0 else ""
        return f"{sign}{self.score_delta:.0f}"


@dataclass
class ScoreDelta:
    """Complete delta comparison between two runs."""

    # Run identifiers
    previous_run_id: UUID | None = None
    current_run_id: UUID | None = None
    previous_run_date: datetime | None = None
    current_run_date: datetime | None = None

    # Overall score changes
    previous_total: float = 0.0
    current_total: float = 0.0
    total_delta: float = 0.0
    total_direction: ChangeDirection = ChangeDirection.UNCHANGED
    total_significance: ChangeSignificance = ChangeSignificance.NEGLIGIBLE

    # Findability level changes (kept as grade_* for backward compatibility in API)
    previous_grade: str = ""  # Now stores findability level
    current_grade: str = ""  # Now stores findability level
    grade_improved: bool = False  # True if level improved
    grade_declined: bool = False  # True if level declined

    # Per-pillar deltas
    pillar_deltas: list[PillarDelta] = field(default_factory=list)

    # Summary metrics
    pillars_improved: int = 0
    pillars_declined: int = 0
    pillars_unchanged: int = 0

    # Notable changes
    biggest_gain: PillarDelta | None = None
    biggest_loss: PillarDelta | None = None

    # Insights
    insights: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    # Metadata
    days_between_runs: int = 0
    is_valid_comparison: bool = True
    comparison_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "previous_run_id": str(self.previous_run_id) if self.previous_run_id else None,
            "current_run_id": str(self.current_run_id) if self.current_run_id else None,
            "previous_run_date": (
                self.previous_run_date.isoformat() if self.previous_run_date else None
            ),
            "current_run_date": (
                self.current_run_date.isoformat() if self.current_run_date else None
            ),
            "previous_total": round(self.previous_total, 1),
            "current_total": round(self.current_total, 1),
            "total_delta": round(self.total_delta, 1),
            "total_direction": self.total_direction.value,
            "total_significance": self.total_significance.value,
            "previous_grade": self.previous_grade,
            "current_grade": self.current_grade,
            "grade_improved": self.grade_improved,
            "grade_declined": self.grade_declined,
            "pillar_deltas": [p.to_dict() for p in self.pillar_deltas],
            "pillars_improved": self.pillars_improved,
            "pillars_declined": self.pillars_declined,
            "pillars_unchanged": self.pillars_unchanged,
            "biggest_gain": self.biggest_gain.to_dict() if self.biggest_gain else None,
            "biggest_loss": self.biggest_loss.to_dict() if self.biggest_loss else None,
            "insights": self.insights,
            "warnings": self.warnings,
            "days_between_runs": self.days_between_runs,
            "is_valid_comparison": self.is_valid_comparison,
            "comparison_notes": self.comparison_notes,
        }

    def show_the_delta(self) -> str:
        """Generate human-readable delta summary."""
        lines = [
            "=" * 60,
            "SCORE COMPARISON",
            "=" * 60,
            "",
        ]

        # Overall change
        sign = "+" if self.total_delta > 0 else ""
        lines.append(
            f"Overall: {self.previous_total:.0f} → {self.current_total:.0f} ({sign}{self.total_delta:.0f})"
        )
        lines.append(f"Level: {self.previous_grade} → {self.current_grade}")

        if self.days_between_runs > 0:
            lines.append(f"Time between runs: {self.days_between_runs} days")

        lines.extend(
            [
                "",
                "-" * 60,
                "PILLAR CHANGES",
                "-" * 60,
            ]
        )

        for delta in self.pillar_deltas:
            icon = (
                "↑"
                if delta.direction == ChangeDirection.IMPROVED
                else "↓" if delta.direction == ChangeDirection.DECLINED else "="
            )
            sign = "+" if delta.score_delta > 0 else ""
            lines.append(
                f"[{icon}] {delta.display_name}: "
                f"{delta.previous_score:.0f} → {delta.current_score:.0f} ({sign}{delta.score_delta:.0f})"
            )

        lines.extend(
            [
                "",
                f"Improved: {self.pillars_improved} | Declined: {self.pillars_declined} | Unchanged: {self.pillars_unchanged}",
            ]
        )

        if self.biggest_gain:
            lines.append(
                f"Biggest gain: {self.biggest_gain.display_name} (+{self.biggest_gain.score_delta:.0f})"
            )

        if self.biggest_loss:
            lines.append(
                f"Biggest loss: {self.biggest_loss.display_name} ({self.biggest_loss.score_delta:.0f})"
            )

        if self.insights:
            lines.extend(
                [
                    "",
                    "-" * 60,
                    "INSIGHTS",
                    "-" * 60,
                ]
            )
            for insight in self.insights:
                lines.append(f"  • {insight}")

        if self.warnings:
            lines.extend(
                [
                    "",
                    "-" * 60,
                    "WARNINGS",
                    "-" * 60,
                ]
            )
            for warning in self.warnings:
                lines.append(f"  ⚠ {warning}")

        lines.extend(["", "=" * 60])
        return "\n".join(lines)


class ScoreDeltaCalculator:
    """Calculates delta between two Findable Score v2 results."""

    # Level ordering for comparison (pillar levels)
    # Progress-based: limited → partial → full
    LEVEL_ORDER = {"limited": 0, "partial": 1, "full": 2}

    # Findability level ordering for comparison (overall score levels)
    FINDABILITY_LEVEL_ORDER = {
        "not_yet_findable": 0,
        "partially_findable": 1,
        "findable": 2,
        "highly_findable": 3,
        "optimized": 4,
    }

    def calculate(
        self,
        previous_score: FindableScoreV2,
        current_score: FindableScoreV2,
        previous_run_id: UUID | None = None,
        current_run_id: UUID | None = None,
        previous_run_date: datetime | None = None,
        current_run_date: datetime | None = None,
    ) -> ScoreDelta:
        """
        Calculate delta between two Findable Score v2 results.

        Args:
            previous_score: Score from previous run
            current_score: Score from current run
            previous_run_id: Optional ID of previous run
            current_run_id: Optional ID of current run
            previous_run_date: Optional timestamp of previous run
            current_run_date: Optional timestamp of current run

        Returns:
            ScoreDelta with complete comparison
        """
        result = ScoreDelta(
            previous_run_id=previous_run_id,
            current_run_id=current_run_id,
            previous_run_date=previous_run_date,
            current_run_date=current_run_date,
        )

        # Calculate days between runs
        if previous_run_date and current_run_date:
            result.days_between_runs = (current_run_date - previous_run_date).days

        # Overall score comparison
        result.previous_total = previous_score.total_score
        result.current_total = current_score.total_score
        result.total_delta = current_score.total_score - previous_score.total_score
        result.total_direction = self._get_direction(result.total_delta)
        result.total_significance = self._get_significance(result.total_delta)

        # Findability level comparison (stored in grade fields for backward compatibility)
        prev_level = (
            previous_score.level if hasattr(previous_score, "level") else "not_yet_findable"
        )
        curr_level = current_score.level if hasattr(current_score, "level") else "not_yet_findable"
        result.previous_grade = prev_level  # Now stores findability level
        result.current_grade = curr_level  # Now stores findability level
        result.grade_improved = self._level_improved(prev_level, curr_level)
        result.grade_declined = self._level_declined(prev_level, curr_level)

        # Build pillar-by-pillar comparison
        prev_pillars = {p.name: p for p in previous_score.pillars}
        curr_pillars = {p.name: p for p in current_score.pillars}

        pillar_order = ["technical", "structure", "schema", "authority", "retrieval", "coverage"]

        for pillar_name in pillar_order:
            prev = prev_pillars.get(pillar_name)
            curr = curr_pillars.get(pillar_name)

            if prev and curr:
                delta = self._build_pillar_delta(prev, curr)
                result.pillar_deltas.append(delta)

                # Track summary metrics
                if delta.direction == ChangeDirection.IMPROVED:
                    result.pillars_improved += 1
                elif delta.direction == ChangeDirection.DECLINED:
                    result.pillars_declined += 1
                else:
                    result.pillars_unchanged += 1

        # Find biggest changes
        gains = [d for d in result.pillar_deltas if d.score_delta > 0]
        losses = [d for d in result.pillar_deltas if d.score_delta < 0]

        if gains:
            result.biggest_gain = max(gains, key=lambda d: d.score_delta)
        if losses:
            result.biggest_loss = min(losses, key=lambda d: d.score_delta)

        # Check for partial analysis issues
        if previous_score.is_partial or current_score.is_partial:
            result.comparison_notes.append(
                "Comparison includes partial analysis - some pillars may not be directly comparable."
            )

        # Generate insights
        result.insights = self._generate_insights(result)
        result.warnings = self._generate_warnings(result, previous_score, current_score)

        return result

    def _build_pillar_delta(self, previous: PillarScore, current: PillarScore) -> PillarDelta:
        """Build delta for a single pillar."""
        score_delta = current.raw_score - previous.raw_score
        points_delta = current.points_earned - previous.points_earned
        direction = self._get_direction(score_delta)
        significance = self._get_significance(score_delta)

        # Level change tracking
        prev_level_ord = self.LEVEL_ORDER.get(previous.level, 0)
        curr_level_ord = self.LEVEL_ORDER.get(current.level, 0)
        level_improved = curr_level_ord > prev_level_ord
        level_declined = curr_level_ord < prev_level_ord

        return PillarDelta(
            pillar_name=current.name,
            display_name=current.display_name,
            previous_score=previous.raw_score,
            previous_points=previous.points_earned,
            previous_level=previous.level,
            current_score=current.raw_score,
            current_points=current.points_earned,
            current_level=current.level,
            score_delta=score_delta,
            points_delta=points_delta,
            direction=direction,
            significance=significance,
            level_improved=level_improved,
            level_declined=level_declined,
            max_points=current.max_points,
        )

    def _get_direction(self, delta: float) -> ChangeDirection:
        """Determine direction of change."""
        if delta > 0.5:
            return ChangeDirection.IMPROVED
        elif delta < -0.5:
            return ChangeDirection.DECLINED
        return ChangeDirection.UNCHANGED

    def _get_significance(self, delta: float) -> ChangeSignificance:
        """Determine significance of change."""
        abs_delta = abs(delta)
        if abs_delta >= 10:
            return ChangeSignificance.MAJOR
        elif abs_delta >= 5:
            return ChangeSignificance.MODERATE
        elif abs_delta >= 1:
            return ChangeSignificance.MINOR
        return ChangeSignificance.NEGLIGIBLE

    def _level_improved(self, prev: str, curr: str) -> bool:
        """Check if findability level improved."""
        return self.FINDABILITY_LEVEL_ORDER.get(curr, 0) > self.FINDABILITY_LEVEL_ORDER.get(prev, 0)

    def _level_declined(self, prev: str, curr: str) -> bool:
        """Check if findability level declined."""
        return self.FINDABILITY_LEVEL_ORDER.get(curr, 0) < self.FINDABILITY_LEVEL_ORDER.get(prev, 0)

    def _generate_insights(self, delta: ScoreDelta) -> list[str]:
        """Generate insights from delta comparison."""
        insights = []

        # Overall trend
        if delta.total_direction == ChangeDirection.IMPROVED:
            if delta.total_significance == ChangeSignificance.MAJOR:
                insights.append(
                    f"Major improvement: +{delta.total_delta:.0f} points since last audit."
                )
            elif delta.total_significance == ChangeSignificance.MODERATE:
                insights.append(f"Solid progress: +{delta.total_delta:.0f} points improvement.")
            else:
                insights.append(f"Incremental improvement: +{delta.total_delta:.0f} points.")
        elif delta.total_direction == ChangeDirection.DECLINED:
            if delta.total_significance == ChangeSignificance.MAJOR:
                insights.append(
                    f"Significant regression: {delta.total_delta:.0f} points lost. Investigate root cause."
                )
            else:
                insights.append(f"Score declined by {abs(delta.total_delta):.0f} points.")
        else:
            insights.append("Score stable since last audit.")

        # Findability level change
        if delta.grade_improved:
            insights.append(f"Level improved from {delta.previous_grade} to {delta.current_grade}!")
        elif delta.grade_declined:
            insights.append(f"Level dropped from {delta.previous_grade} to {delta.current_grade}.")

        # Biggest improvements
        if delta.biggest_gain and delta.biggest_gain.score_delta >= 5:
            insights.append(
                f"Best improvement in {delta.biggest_gain.display_name}: "
                f"+{delta.biggest_gain.score_delta:.0f} points."
            )

        # Level changes
        level_improvements = [d for d in delta.pillar_deltas if d.level_improved]
        if level_improvements:
            names = [d.display_name for d in level_improvements[:3]]
            insights.append(f"Level upgrades in: {', '.join(names)}.")

        # Momentum
        if delta.pillars_improved >= 4:
            insights.append(f"Strong momentum: {delta.pillars_improved}/6 pillars improved.")

        return insights[:6]

    def _generate_warnings(
        self,
        delta: ScoreDelta,
        previous: FindableScoreV2,
        current: FindableScoreV2,
    ) -> list[str]:
        """Generate warnings about concerning changes."""
        warnings = []

        # Major regression
        if delta.biggest_loss and delta.biggest_loss.score_delta <= -10:
            warnings.append(
                f"Major regression in {delta.biggest_loss.display_name}: "
                f"{delta.biggest_loss.score_delta:.0f} points. Review recent changes."
            )

        # Level downgrades
        level_declines = [d for d in delta.pillar_deltas if d.level_declined]
        if level_declines:
            names = [d.display_name for d in level_declines[:3]]
            warnings.append(f"Level downgrades in: {', '.join(names)}.")

        # Level drop
        if delta.grade_declined and delta.total_delta <= -5:
            warnings.append(
                f"Level dropped from {delta.previous_grade} to {delta.current_grade}. "
                "Prioritize recovery."
            )

        # Multiple declines
        if delta.pillars_declined >= 3:
            warnings.append(
                f"{delta.pillars_declined}/6 pillars declined. Review site-wide changes."
            )

        # Partial comparison warning
        if previous.is_partial != current.is_partial:
            warnings.append(
                "Analysis scope changed between runs. Comparison may not be fully accurate."
            )

        return warnings[:4]


@dataclass
class ScoreTrend:
    """Trend data for visualizing score over time."""

    run_id: UUID | None
    run_date: datetime
    total_score: float
    grade: str  # Now stores findability level (kept as 'grade' for backward compatibility)
    pillar_scores: dict[str, float]  # pillar_name -> raw_score

    def to_dict(self) -> dict:
        return {
            "run_id": str(self.run_id) if self.run_id else None,
            "run_date": self.run_date.isoformat(),
            "total_score": round(self.total_score, 1),
            "level": self.grade,  # Expose as 'level' in API
            "pillar_scores": {k: round(v, 1) for k, v in self.pillar_scores.items()},
        }


@dataclass
class ScoreTrendSummary:
    """Summary of score trends over multiple runs."""

    site_domain: str
    data_points: list[ScoreTrend] = field(default_factory=list)
    total_runs: int = 0

    # Calculated trends
    score_trend: str = "stable"  # improving, declining, stable
    avg_score: float = 0.0
    min_score: float = 0.0
    max_score: float = 0.0
    latest_score: float = 0.0

    # Per-pillar trends
    pillar_trends: dict[str, str] = field(default_factory=dict)  # pillar -> trend

    # Time range
    first_run_date: datetime | None = None
    last_run_date: datetime | None = None
    days_tracked: int = 0

    def to_dict(self) -> dict:
        return {
            "site_domain": self.site_domain,
            "data_points": [d.to_dict() for d in self.data_points],
            "total_runs": self.total_runs,
            "score_trend": self.score_trend,
            "avg_score": round(self.avg_score, 1),
            "min_score": round(self.min_score, 1),
            "max_score": round(self.max_score, 1),
            "latest_score": round(self.latest_score, 1),
            "pillar_trends": self.pillar_trends,
            "first_run_date": self.first_run_date.isoformat() if self.first_run_date else None,
            "last_run_date": self.last_run_date.isoformat() if self.last_run_date else None,
            "days_tracked": self.days_tracked,
        }


def build_trend_data(
    scores: list[tuple[FindableScoreV2, UUID | None, datetime]],
) -> ScoreTrendSummary:
    """
    Build trend summary from a list of scores over time.

    Args:
        scores: List of (score, run_id, run_date) tuples, ordered by date

    Returns:
        ScoreTrendSummary with trend analysis
    """
    if not scores:
        return ScoreTrendSummary(site_domain="unknown")

    data_points = []
    all_scores = []

    for score, run_id, run_date in scores:
        level = score.level if hasattr(score, "level") else "not_yet_findable"
        pillar_scores = {p.name: p.raw_score for p in score.pillars}

        data_points.append(
            ScoreTrend(
                run_id=run_id,
                run_date=run_date,
                total_score=score.total_score,
                grade=level,  # Stored as 'grade' for backward compatibility
                pillar_scores=pillar_scores,
            )
        )
        all_scores.append(score.total_score)

    summary = ScoreTrendSummary(
        site_domain="",  # Caller should set this
        data_points=data_points,
        total_runs=len(scores),
        avg_score=sum(all_scores) / len(all_scores),
        min_score=min(all_scores),
        max_score=max(all_scores),
        latest_score=all_scores[-1],
    )

    if len(scores) >= 2:
        summary.first_run_date = scores[0][2]
        summary.last_run_date = scores[-1][2]
        summary.days_tracked = (summary.last_run_date - summary.first_run_date).days

        # Calculate overall trend
        first_score = all_scores[0]
        last_score = all_scores[-1]
        delta = last_score - first_score

        if delta >= 5:
            summary.score_trend = "improving"
        elif delta <= -5:
            summary.score_trend = "declining"
        else:
            summary.score_trend = "stable"

        # Calculate per-pillar trends
        pillar_names = ["technical", "structure", "schema", "authority", "retrieval", "coverage"]
        for pillar in pillar_names:
            first_pillar = data_points[0].pillar_scores.get(pillar, 0)
            last_pillar = data_points[-1].pillar_scores.get(pillar, 0)
            pillar_delta = last_pillar - first_pillar

            if pillar_delta >= 5:
                summary.pillar_trends[pillar] = "improving"
            elif pillar_delta <= -5:
                summary.pillar_trends[pillar] = "declining"
            else:
                summary.pillar_trends[pillar] = "stable"

    return summary


def compare_scores(
    previous_score: FindableScoreV2,
    current_score: FindableScoreV2,
    previous_run_id: UUID | None = None,
    current_run_id: UUID | None = None,
    previous_run_date: datetime | None = None,
    current_run_date: datetime | None = None,
) -> ScoreDelta:
    """
    Convenience function to compare two Findable Score v2 results.

    Args:
        previous_score: Score from previous run
        current_score: Score from current run
        previous_run_id: Optional ID of previous run
        current_run_id: Optional ID of current run
        previous_run_date: Optional timestamp of previous run
        current_run_date: Optional timestamp of current run

    Returns:
        ScoreDelta with complete comparison
    """
    calculator = ScoreDeltaCalculator()
    return calculator.calculate(
        previous_score=previous_score,
        current_score=current_score,
        previous_run_id=previous_run_id,
        current_run_id=current_run_id,
        previous_run_date=previous_run_date,
        current_run_date=current_run_date,
    )
