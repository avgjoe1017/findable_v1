"""V2 Competitor benchmark for comparing pillar scores across companies.

This module compares the 6-pillar Findable Score v2 between a site and its
competitors, providing side-by-side analysis of strengths and weaknesses.
"""

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from worker.scoring.calculator_v2 import FindableScoreV2, PillarScore


@dataclass
class PillarComparison:
    """Comparison of a single pillar between you and a competitor."""

    pillar_name: str
    pillar_display_name: str
    your_score: float  # 0-100
    your_points: float
    your_level: str
    competitor_score: float  # 0-100
    competitor_points: float
    competitor_level: str
    advantage: float  # positive = you're ahead
    max_points: float

    @property
    def winner(self) -> str:
        """Returns 'you', 'competitor', or 'tie'."""
        if abs(self.advantage) < 5:
            return "tie"
        return "you" if self.advantage > 0 else "competitor"

    def to_dict(self) -> dict:
        return {
            "pillar_name": self.pillar_name,
            "display_name": self.pillar_display_name,
            "your_score": round(self.your_score, 1),
            "your_points": round(self.your_points, 1),
            "your_level": self.your_level,
            "competitor_score": round(self.competitor_score, 1),
            "competitor_points": round(self.competitor_points, 1),
            "competitor_level": self.competitor_level,
            "advantage": round(self.advantage, 1),
            "max_points": self.max_points,
            "winner": self.winner,
        }


@dataclass
class CompetitorV2Score:
    """V2 score for a single competitor."""

    name: str
    domain: str
    total_score: float
    grade: str
    grade_description: str
    pillars: list[PillarScore] = field(default_factory=list)
    pillars_good: int = 0
    pillars_warning: int = 0
    pillars_critical: int = 0
    is_partial: bool = False

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "domain": self.domain,
            "total_score": round(self.total_score, 1),
            "grade": self.grade,
            "grade_description": self.grade_description,
            "pillars": [p.to_dict() for p in self.pillars],
            "pillars_good": self.pillars_good,
            "pillars_warning": self.pillars_warning,
            "pillars_critical": self.pillars_critical,
            "is_partial": self.is_partial,
        }


@dataclass
class HeadToHeadV2:
    """Head-to-head v2 comparison with a single competitor."""

    competitor_name: str
    competitor_domain: str

    # Overall comparison
    your_total: float
    competitor_total: float
    score_advantage: float

    your_grade: str
    competitor_grade: str

    # Per-pillar comparison
    pillar_comparisons: list[PillarComparison] = field(default_factory=list)

    # Summary
    pillars_winning: int = 0
    pillars_losing: int = 0
    pillars_tied: int = 0

    # Strengths and weaknesses relative to this competitor
    your_strengths: list[str] = field(default_factory=list)  # Pillar names
    your_weaknesses: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "competitor_name": self.competitor_name,
            "competitor_domain": self.competitor_domain,
            "your_total": round(self.your_total, 1),
            "competitor_total": round(self.competitor_total, 1),
            "score_advantage": round(self.score_advantage, 1),
            "your_grade": self.your_grade,
            "competitor_grade": self.competitor_grade,
            "pillar_comparisons": [p.to_dict() for p in self.pillar_comparisons],
            "pillars_winning": self.pillars_winning,
            "pillars_losing": self.pillars_losing,
            "pillars_tied": self.pillars_tied,
            "your_strengths": self.your_strengths,
            "your_weaknesses": self.your_weaknesses,
        }


@dataclass
class BenchmarkV2Result:
    """Complete v2 benchmark comparing you vs all competitors."""

    # Your info
    company_name: str
    domain: str
    site_id: UUID | None = None

    # Your v2 score
    your_score: FindableScoreV2 | None = None

    # Competitor scores
    competitor_scores: list[CompetitorV2Score] = field(default_factory=list)

    # Head-to-head comparisons
    head_to_heads: list[HeadToHeadV2] = field(default_factory=list)

    # Aggregate metrics
    total_competitors: int = 0
    your_rank: int = 1  # 1 = best in group

    # Average competitor scores per pillar
    avg_competitor_pillars: dict[str, float] = field(default_factory=dict)

    # Your relative strengths/weaknesses vs average
    relative_strengths: list[str] = field(default_factory=list)
    relative_weaknesses: list[str] = field(default_factory=list)

    # Insights and recommendations
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Timing
    created_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "company_name": self.company_name,
            "domain": self.domain,
            "site_id": str(self.site_id) if self.site_id else None,
            "your_score": self.your_score.to_dict() if self.your_score else None,
            "competitor_scores": [c.to_dict() for c in self.competitor_scores],
            "head_to_heads": [h.to_dict() for h in self.head_to_heads],
            "total_competitors": self.total_competitors,
            "your_rank": self.your_rank,
            "avg_competitor_pillars": {
                k: round(v, 1) for k, v in self.avg_competitor_pillars.items()
            },
            "relative_strengths": self.relative_strengths,
            "relative_weaknesses": self.relative_weaknesses,
            "insights": self.insights,
            "recommendations": self.recommendations,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CompetitorBenchmarkerV2:
    """Benchmarks v2 pillar scores across companies."""

    def benchmark(
        self,
        company_name: str,
        domain: str,
        your_score: FindableScoreV2,
        competitor_scores: list[tuple[str, str, FindableScoreV2]],  # (name, domain, score)
        site_id: UUID | None = None,
    ) -> BenchmarkV2Result:
        """
        Run v2 benchmark comparison.

        Args:
            company_name: Your company name
            domain: Your domain
            your_score: Your FindableScoreV2
            competitor_scores: List of (name, domain, FindableScoreV2) tuples
            site_id: Optional site ID

        Returns:
            BenchmarkV2Result with full comparison
        """
        result = BenchmarkV2Result(
            company_name=company_name,
            domain=domain,
            site_id=site_id,
            your_score=your_score,
            created_at=datetime.utcnow(),
        )

        # Process competitor scores
        for comp_name, comp_domain, comp_score in competitor_scores:
            comp_v2 = CompetitorV2Score(
                name=comp_name,
                domain=comp_domain,
                total_score=comp_score.total_score,
                grade=(
                    comp_score.grade.value  # type: ignore[attr-defined]
                    if hasattr(comp_score.grade, "value")  # type: ignore[attr-defined]
                    else str(comp_score.grade)  # type: ignore[attr-defined]
                ),
                grade_description=comp_score.grade_description,  # type: ignore[attr-defined]
                pillars=comp_score.pillars,
                pillars_good=comp_score.pillars_good,
                pillars_warning=comp_score.pillars_warning,
                pillars_critical=comp_score.pillars_critical,
                is_partial=comp_score.is_partial,
            )
            result.competitor_scores.append(comp_v2)

        result.total_competitors = len(result.competitor_scores)

        # Build head-to-head comparisons
        for comp_v2 in result.competitor_scores:
            h2h = self._build_head_to_head(your_score, comp_v2)
            result.head_to_heads.append(h2h)

        # Calculate aggregate metrics
        self._calculate_aggregates(result)

        # Determine rank
        all_scores = [your_score.total_score] + [c.total_score for c in result.competitor_scores]
        sorted_scores = sorted(all_scores, reverse=True)
        result.your_rank = sorted_scores.index(your_score.total_score) + 1

        # Generate insights and recommendations
        result.insights = self._generate_insights(result)
        result.recommendations = self._generate_recommendations(result)

        return result

    def _build_head_to_head(
        self, your_score: FindableScoreV2, competitor: CompetitorV2Score
    ) -> HeadToHeadV2:
        """Build head-to-head comparison with a single competitor."""
        your_grade = (
            your_score.grade.value if hasattr(your_score.grade, "value") else str(your_score.grade)  # type: ignore[attr-defined]
        )

        h2h = HeadToHeadV2(
            competitor_name=competitor.name,
            competitor_domain=competitor.domain,
            your_total=your_score.total_score,
            competitor_total=competitor.total_score,
            score_advantage=your_score.total_score - competitor.total_score,
            your_grade=your_grade,
            competitor_grade=competitor.grade,
        )

        # Build pillar-by-pillar comparison
        your_pillars_by_name = {p.name: p for p in your_score.pillars}
        comp_pillars_by_name = {p.name: p for p in competitor.pillars}

        for pillar_name in [
            "technical",
            "structure",
            "schema",
            "authority",
            "retrieval",
            "coverage",
        ]:
            your_pillar = your_pillars_by_name.get(pillar_name)
            comp_pillar = comp_pillars_by_name.get(pillar_name)

            if your_pillar and comp_pillar:
                comparison = PillarComparison(
                    pillar_name=pillar_name,
                    pillar_display_name=your_pillar.display_name,
                    your_score=your_pillar.raw_score,
                    your_points=your_pillar.points_earned,
                    your_level=your_pillar.level,
                    competitor_score=comp_pillar.raw_score,
                    competitor_points=comp_pillar.points_earned,
                    competitor_level=comp_pillar.level,
                    advantage=your_pillar.raw_score - comp_pillar.raw_score,
                    max_points=your_pillar.max_points,
                )
                h2h.pillar_comparisons.append(comparison)

                # Track wins/losses/ties
                if comparison.winner == "you":
                    h2h.pillars_winning += 1
                    if comparison.advantage > 15:  # Significant advantage
                        h2h.your_strengths.append(comparison.pillar_display_name)
                elif comparison.winner == "competitor":
                    h2h.pillars_losing += 1
                    if comparison.advantage < -15:  # Significant disadvantage
                        h2h.your_weaknesses.append(comparison.pillar_display_name)
                else:
                    h2h.pillars_tied += 1

        return h2h

    def _calculate_aggregates(self, result: BenchmarkV2Result) -> None:
        """Calculate aggregate metrics across all competitors."""
        if not result.competitor_scores:
            return

        # Calculate average competitor scores per pillar
        pillar_totals: dict[str, list[float]] = {
            "technical": [],
            "structure": [],
            "schema": [],
            "authority": [],
            "retrieval": [],
            "coverage": [],
        }

        for comp in result.competitor_scores:
            for pillar in comp.pillars:
                if pillar.name in pillar_totals:
                    pillar_totals[pillar.name].append(pillar.raw_score)

        for pillar_name, scores in pillar_totals.items():
            if scores:
                result.avg_competitor_pillars[pillar_name] = sum(scores) / len(scores)

        # Determine your relative strengths/weaknesses vs average
        if result.your_score:
            for pillar in result.your_score.pillars:
                avg = result.avg_competitor_pillars.get(pillar.name, 50)
                diff = pillar.raw_score - avg
                if diff > 10:
                    result.relative_strengths.append(pillar.display_name)
                elif diff < -10:
                    result.relative_weaknesses.append(pillar.display_name)

    def _generate_insights(self, result: BenchmarkV2Result) -> list[str]:
        """Generate insights from v2 benchmark results."""
        insights: list[str] = []

        if not result.your_score:
            return insights

        # Rank insight
        if result.your_rank == 1:
            insights.append(
                f"Leading the competitive set with {result.your_score.total_score:.0f}/100 "
                f"({result.total_competitors} competitors analyzed)."
            )
        elif result.your_rank <= 2:
            insights.append(
                f"Strong position: ranked #{result.your_rank} of {result.total_competitors + 1} sites."
            )
        else:
            insights.append(
                f"Competitive gap: ranked #{result.your_rank} of {result.total_competitors + 1}. "
                "See pillar breakdown for improvement areas."
            )

        # Strengths
        if result.relative_strengths:
            insights.append(
                f"Competitive advantage in: {', '.join(result.relative_strengths[:3])}."
            )

        # Weaknesses
        if result.relative_weaknesses:
            insights.append(
                f"Trailing competitors in: {', '.join(result.relative_weaknesses[:3])}."
            )

        # Head-to-head insights
        for h2h in result.head_to_heads:
            if h2h.score_advantage > 15:
                insights.append(
                    f"Significantly outperforming {h2h.competitor_name} "
                    f"(+{h2h.score_advantage:.0f} points)."
                )
            elif h2h.score_advantage < -15:
                insights.append(
                    f"Trailing {h2h.competitor_name} by {-h2h.score_advantage:.0f} points."
                )

        return insights[:6]  # Limit to 6 insights

    def _generate_recommendations(self, result: BenchmarkV2Result) -> list[str]:
        """Generate recommendations from v2 benchmark results."""
        recommendations: list[str] = []

        if not result.your_score:
            return recommendations

        # Focus on weaknesses relative to competitors
        for weakness in result.relative_weaknesses[:2]:
            recommendations.append(f"Priority: Improve {weakness} to match competitor levels.")

        # Specific pillar recommendations based on competitive gaps
        for pillar_name, avg in result.avg_competitor_pillars.items():
            your_pillar = next(
                (p for p in result.your_score.pillars if p.name == pillar_name), None
            )
            if your_pillar and your_pillar.raw_score < avg - 15:
                if pillar_name == "schema":
                    recommendations.append(
                        "Add structured data (FAQPage, Article, Organization) to match competitor schema richness."
                    )
                elif pillar_name == "authority":
                    recommendations.append(
                        "Improve authority signals: add author bylines, credentials, and authoritative citations."
                    )
                elif pillar_name == "structure":
                    recommendations.append(
                        "Improve content structure: add clear headings, FAQs, and answer-first formatting."
                    )

        # Learn from winners
        best_competitor = max(result.competitor_scores, key=lambda c: c.total_score, default=None)
        if best_competitor and best_competitor.total_score > result.your_score.total_score:
            recommendations.append(
                f"Analyze {best_competitor.name}'s content strategy - they lead with "
                f"{best_competitor.total_score:.0f}/100."
            )

        return recommendations[:5]  # Limit to 5 recommendations


def run_benchmark_v2(
    company_name: str,
    domain: str,
    your_score: FindableScoreV2,
    competitor_scores: list[tuple[str, str, FindableScoreV2]],
    site_id: UUID | None = None,
) -> BenchmarkV2Result:
    """
    Convenience function to run v2 competitor benchmark.

    Args:
        company_name: Your company name
        domain: Your domain
        your_score: Your FindableScoreV2
        competitor_scores: List of (name, domain, FindableScoreV2) tuples
        site_id: Optional site ID

    Returns:
        BenchmarkV2Result with full comparison
    """
    benchmarker = CompetitorBenchmarkerV2()
    return benchmarker.benchmark(
        company_name=company_name,
        domain=domain,
        your_score=your_score,
        competitor_scores=competitor_scores,
        site_id=site_id,
    )
