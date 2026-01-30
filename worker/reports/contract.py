"""Report JSON contract and data structures.

Defines the stable report format for the Findable Score Analyzer.
All reports follow this contract for API responses and persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID


class ReportVersion(str, Enum):
    """Report schema versions."""

    V1_0 = "1.0"
    V1_1 = "1.1"  # Reserved for future


# Current version
CURRENT_VERSION = ReportVersion.V1_0


@dataclass
class ReportMetadata:
    """Report metadata and context."""

    report_id: UUID
    site_id: UUID
    run_id: UUID
    version: ReportVersion

    # Site info
    company_name: str
    domain: str

    # Timing
    created_at: datetime
    run_started_at: datetime | None = None
    run_completed_at: datetime | None = None
    run_duration_seconds: float | None = None

    # Configuration
    include_observation: bool = True
    include_benchmark: bool = True

    # Limitations and notes
    limitations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "report_id": str(self.report_id),
            "site_id": str(self.site_id),
            "run_id": str(self.run_id),
            "version": self.version.value,
            "company_name": self.company_name,
            "domain": self.domain,
            "created_at": self.created_at.isoformat(),
            "run_started_at": (self.run_started_at.isoformat() if self.run_started_at else None),
            "run_completed_at": (
                self.run_completed_at.isoformat() if self.run_completed_at else None
            ),
            "run_duration_seconds": self.run_duration_seconds,
            "include_observation": self.include_observation,
            "include_benchmark": self.include_benchmark,
            "limitations": self.limitations,
            "notes": self.notes,
        }


@dataclass
class ScoreSection:
    """Score breakdown section of the report."""

    # Overall scores
    total_score: float
    grade: str
    grade_description: str

    # Category breakdown (from ScoreCalculator)
    category_scores: dict[str, float]  # category -> score
    category_breakdown: dict  # Full breakdown from ScoreBreakdown.to_dict()

    # Criterion breakdown
    criterion_scores: list[dict]

    # Question-level
    total_questions: int
    questions_answered: int
    questions_partial: int
    questions_unanswered: int
    coverage_percentage: float

    # Calculation transparency
    calculation_summary: list[str]
    formula_used: str
    rubric_version: str

    # Show the math text
    show_the_math: str

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_score": round(self.total_score, 2),
            "grade": self.grade,
            "grade_description": self.grade_description,
            "category_scores": {k: round(v, 2) for k, v in self.category_scores.items()},
            "category_breakdown": self.category_breakdown,
            "criterion_scores": self.criterion_scores,
            "total_questions": self.total_questions,
            "questions_answered": self.questions_answered,
            "questions_partial": self.questions_partial,
            "questions_unanswered": self.questions_unanswered,
            "coverage_percentage": round(self.coverage_percentage, 2),
            "calculation_summary": self.calculation_summary,
            "formula_used": self.formula_used,
            "rubric_version": self.rubric_version,
            "show_the_math": self.show_the_math,
        }


@dataclass
class FixItem:
    """Individual fix recommendation."""

    id: str
    reason_code: str
    title: str
    description: str
    scaffold: str
    priority: int
    estimated_impact_min: float
    estimated_impact_max: float
    estimated_impact_expected: float
    effort_level: str
    target_url: str | None
    affected_questions: list[str]
    affected_categories: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "reason_code": self.reason_code,
            "title": self.title,
            "description": self.description,
            "scaffold": self.scaffold,
            "priority": self.priority,
            "estimated_impact": {
                "min": round(self.estimated_impact_min, 2),
                "max": round(self.estimated_impact_max, 2),
                "expected": round(self.estimated_impact_expected, 2),
            },
            "effort_level": self.effort_level,
            "target_url": self.target_url,
            "affected_questions": self.affected_questions,
            "affected_categories": self.affected_categories,
        }


@dataclass
class FixSection:
    """Fix recommendations section of the report."""

    total_fixes: int
    critical_fixes: int
    high_priority_fixes: int
    estimated_total_impact: float

    # Individual fixes
    fixes: list[FixItem]

    # Coverage
    categories_addressed: list[str]
    questions_addressed: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_fixes": self.total_fixes,
            "critical_fixes": self.critical_fixes,
            "high_priority_fixes": self.high_priority_fixes,
            "estimated_total_impact": round(self.estimated_total_impact, 2),
            "fixes": [f.to_dict() for f in self.fixes],
            "categories_addressed": self.categories_addressed,
            "questions_addressed": self.questions_addressed,
        }


@dataclass
class ObservationSection:
    """Observation results section of the report."""

    # Overall rates
    company_mention_rate: float
    domain_mention_rate: float
    citation_rate: float

    # Counts
    total_questions: int
    questions_with_mention: int
    questions_with_citation: int

    # Provider info
    provider: str
    model: str

    # Per-question results
    question_results: list[dict]  # Simplified results

    # Comparison with simulation
    prediction_accuracy: float
    optimistic_predictions: int
    pessimistic_predictions: int
    correct_predictions: int

    # Insights
    insights: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "company_mention_rate": round(self.company_mention_rate, 3),
            "domain_mention_rate": round(self.domain_mention_rate, 3),
            "citation_rate": round(self.citation_rate, 3),
            "total_questions": self.total_questions,
            "questions_with_mention": self.questions_with_mention,
            "questions_with_citation": self.questions_with_citation,
            "provider": self.provider,
            "model": self.model,
            "question_results": self.question_results,
            "prediction_accuracy": round(self.prediction_accuracy, 3),
            "optimistic_predictions": self.optimistic_predictions,
            "pessimistic_predictions": self.pessimistic_predictions,
            "correct_predictions": self.correct_predictions,
            "insights": self.insights,
            "recommendations": self.recommendations,
        }


@dataclass
class CompetitorSummary:
    """Summary of competitor performance."""

    name: str
    domain: str
    mention_rate: float
    citation_rate: float
    wins_against_you: int
    losses_against_you: int
    ties: int

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "domain": self.domain,
            "mention_rate": round(self.mention_rate, 3),
            "citation_rate": round(self.citation_rate, 3),
            "wins_against_you": self.wins_against_you,
            "losses_against_you": self.losses_against_you,
            "ties": self.ties,
        }


@dataclass
class BenchmarkSection:
    """Competitor benchmark section of the report."""

    total_competitors: int
    total_questions: int

    # Your rates
    your_mention_rate: float
    your_citation_rate: float

    # Competitor averages
    avg_competitor_mention_rate: float
    avg_competitor_citation_rate: float

    # Win/loss summary
    overall_wins: int
    overall_losses: int
    overall_ties: int
    overall_win_rate: float

    # Unique outcomes
    unique_wins: list[str]  # question_ids where you win vs all
    unique_losses: list[str]  # question_ids where you lose vs all

    # Per-competitor summaries
    competitors: list[CompetitorSummary]

    # Per-question breakdown
    question_benchmarks: list[dict]

    # Insights
    insights: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_competitors": self.total_competitors,
            "total_questions": self.total_questions,
            "your_mention_rate": round(self.your_mention_rate, 3),
            "your_citation_rate": round(self.your_citation_rate, 3),
            "avg_competitor_mention_rate": round(self.avg_competitor_mention_rate, 3),
            "avg_competitor_citation_rate": round(self.avg_competitor_citation_rate, 3),
            "overall_wins": self.overall_wins,
            "overall_losses": self.overall_losses,
            "overall_ties": self.overall_ties,
            "overall_win_rate": round(self.overall_win_rate, 3),
            "unique_wins": self.unique_wins,
            "unique_losses": self.unique_losses,
            "competitors": [c.to_dict() for c in self.competitors],
            "question_benchmarks": self.question_benchmarks,
            "insights": self.insights,
            "recommendations": self.recommendations,
        }


class DivergenceLevel(str, Enum):
    """Level of divergence between simulation and observation."""

    NONE = "none"  # < 10% difference
    LOW = "low"  # 10-20% difference
    MEDIUM = "medium"  # 20-35% difference
    HIGH = "high"  # > 35% difference


@dataclass
class DivergenceSection:
    """Divergence analysis between simulation and observation."""

    level: DivergenceLevel
    mention_rate_delta: float  # Observation - Simulation
    prediction_accuracy: float

    # Triggers for re-run
    should_refresh: bool
    refresh_reasons: list[str]

    # Analysis
    optimism_bias: float  # Positive = simulation was optimistic
    pessimism_bias: float  # Positive = simulation was pessimistic

    # Recommendations
    calibration_notes: list[str]

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "level": self.level.value,
            "mention_rate_delta": round(self.mention_rate_delta, 3),
            "prediction_accuracy": round(self.prediction_accuracy, 3),
            "should_refresh": self.should_refresh,
            "refresh_reasons": self.refresh_reasons,
            "optimism_bias": round(self.optimism_bias, 3),
            "pessimism_bias": round(self.pessimism_bias, 3),
            "calibration_notes": self.calibration_notes,
        }


@dataclass
class FullReport:
    """Complete report combining all analysis sections."""

    metadata: ReportMetadata
    score: ScoreSection
    fixes: FixSection
    observation: ObservationSection | None = None
    benchmark: BenchmarkSection | None = None
    divergence: DivergenceSection | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "metadata": self.metadata.to_dict(),
            "score": self.score.to_dict(),
            "fixes": self.fixes.to_dict(),
        }

        if self.observation:
            result["observation"] = self.observation.to_dict()

        if self.benchmark:
            result["benchmark"] = self.benchmark.to_dict()

        if self.divergence:
            result["divergence"] = self.divergence.to_dict()

        return result

    def get_quick_access_fields(self) -> dict:
        """Get denormalized fields for database quick access."""
        return {
            "score_conservative": int(self.score.total_score * 0.85),  # Conservative band
            "score_typical": int(self.score.total_score),
            "score_generous": int(min(100, self.score.total_score * 1.1)),
            "mention_rate": (self.observation.company_mention_rate if self.observation else None),
        }

    def get_top_fixes(self, n: int = 5) -> list[FixItem]:
        """Get top N priority fixes."""
        sorted_fixes = sorted(
            self.fixes.fixes,
            key=lambda f: (f.priority, -f.estimated_impact_expected),
        )
        return sorted_fixes[:n]

    def get_summary(self) -> dict:
        """Get a summary suitable for list views."""
        return {
            "score": round(self.score.total_score, 1),
            "grade": self.score.grade,
            "mention_rate": (
                round(self.observation.company_mention_rate, 2) if self.observation else None
            ),
            "total_fixes": self.fixes.total_fixes,
            "critical_fixes": self.fixes.critical_fixes,
            "win_rate": (round(self.benchmark.overall_win_rate, 2) if self.benchmark else None),
        }
