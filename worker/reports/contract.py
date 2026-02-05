"""Report JSON contract and data structures.

Defines the stable report format for the Findable Score Analyzer.
All reports follow this contract for API responses and persistence.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import UUID

from api.config import SCORE_BAND_CONSERVATIVE, SCORE_BAND_GENEROUS


class ReportVersion(str, Enum):
    """Report schema versions."""

    V1_0 = "1.0"
    V1_1 = "1.1"  # Surface attribution, citable index, coverage buckets


# Current version
CURRENT_VERSION = ReportVersion.V1_1


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


@dataclass
class CrawledPageInfo:
    """Summary of a crawled page for the report."""

    url: str
    title: str | None
    status_code: int
    depth: int
    word_count: int
    chunk_count: int
    surface: str = "marketing"  # "docs" | "marketing"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "status_code": self.status_code,
            "depth": self.depth,
            "word_count": self.word_count,
            "chunk_count": self.chunk_count,
            "surface": self.surface,
        }


@dataclass
class CrawlSection:
    """Crawl results section of the report."""

    total_pages: int
    total_words: int
    total_chunks: int
    urls_discovered: int
    urls_failed: int
    max_depth_reached: int
    duration_seconds: float
    pages: list[CrawledPageInfo]

    # Surface attribution (v1.1)
    docs_pages_crawled: int = 0
    marketing_pages_crawled: int = 0
    docs_surface_detected: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_pages": self.total_pages,
            "total_words": self.total_words,
            "total_chunks": self.total_chunks,
            "urls_discovered": self.urls_discovered,
            "urls_failed": self.urls_failed,
            "max_depth_reached": self.max_depth_reached,
            "duration_seconds": round(self.duration_seconds, 2),
            "pages": [p.to_dict() for p in self.pages],
            "surface_coverage": {
                "docs_pages": self.docs_pages_crawled,
                "marketing_pages": self.marketing_pages_crawled,
                "docs_surface_detected": self.docs_surface_detected,
            },
        }


@dataclass
class TechnicalComponent:
    """A single technical readiness component."""

    name: str
    score: float
    weight: float
    level: str  # good, warning, critical
    explanation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "level": self.level,
            "explanation": self.explanation,
        }


@dataclass
class TechnicalSection:
    """Technical Readiness section of the report (v2 pillar)."""

    total_score: float  # 0-100
    level: str  # good, warning, critical
    max_points: float = 15.0  # Points this contributes to v2 score

    # Component breakdown
    components: list[TechnicalComponent] = field(default_factory=list)

    # AI crawler access details
    robots_txt_exists: bool = False
    crawlers_allowed: dict[str, bool] = field(default_factory=dict)
    critical_crawlers_blocked: list[str] = field(default_factory=list)

    # Performance
    ttfb_ms: int | None = None
    ttfb_level: str | None = None

    # llms.txt
    llms_txt_exists: bool = False
    llms_txt_quality: float = 0.0

    # JS dependency
    js_dependent: bool = False
    js_framework: str | None = None

    # HTTPS
    is_https: bool = True

    # Issues
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)

    # Show the math
    show_the_math: str = ""

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "robots_txt_exists": self.robots_txt_exists,
            "crawlers_allowed": self.crawlers_allowed,
            "critical_crawlers_blocked": self.critical_crawlers_blocked,
            "ttfb_ms": self.ttfb_ms,
            "ttfb_level": self.ttfb_level,
            "llms_txt_exists": self.llms_txt_exists,
            "llms_txt_quality": round(self.llms_txt_quality, 2),
            "js_dependent": self.js_dependent,
            "js_framework": self.js_framework,
            "is_https": self.is_https,
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "show_the_math": self.show_the_math,
        }


@dataclass
class StructureComponent:
    """A single structure quality component."""

    name: str
    score: float
    weight: float
    level: str  # good, warning, critical
    explanation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "level": self.level,
            "explanation": self.explanation,
        }


@dataclass
class StructureSection:
    """Semantic Structure section of the report (v2 pillar)."""

    total_score: float  # 0-100
    level: str  # good, warning, critical
    max_points: float = 20.0  # Points this contributes to v2 score

    # Component breakdown
    components: list[StructureComponent] = field(default_factory=list)

    # Heading analysis
    h1_count: int = 0
    heading_hierarchy_valid: bool = True
    heading_issues: list[str] = field(default_factory=list)

    # Answer-first analysis
    answer_in_first_paragraph: bool = False
    has_definition: bool = False

    # FAQ analysis
    has_faq_section: bool = False
    faq_count: int = 0
    has_faq_schema: bool = False

    # Link analysis
    internal_links: int = 0
    link_density_level: str = "unknown"

    # Extractable formats
    table_count: int = 0
    list_item_count: int = 0

    # Issues
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Show the math
    show_the_math: str = ""

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "headings": {
                "h1_count": self.h1_count,
                "hierarchy_valid": self.heading_hierarchy_valid,
                "issues": self.heading_issues,
            },
            "answer_first": {
                "in_first_paragraph": self.answer_in_first_paragraph,
                "has_definition": self.has_definition,
            },
            "faq": {
                "has_section": self.has_faq_section,
                "count": self.faq_count,
                "has_schema": self.has_faq_schema,
            },
            "links": {
                "internal_count": self.internal_links,
                "density_level": self.link_density_level,
            },
            "formats": {
                "tables": self.table_count,
                "list_items": self.list_item_count,
            },
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "recommendations": self.recommendations,
            "show_the_math": self.show_the_math,
        }


@dataclass
class SchemaComponent:
    """A single schema richness component."""

    name: str
    score: float
    weight: float
    level: str  # good, warning, critical
    explanation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "level": self.level,
            "explanation": self.explanation,
        }


@dataclass
class SchemaSection:
    """Schema Richness section of the report (v2 pillar)."""

    total_score: float  # 0-100
    level: str  # good, warning, critical
    max_points: float = 15.0  # Points this contributes to v2 score

    # Component breakdown
    components: list[SchemaComponent] = field(default_factory=list)

    # Schema detection
    has_json_ld: bool = False
    has_microdata: bool = False
    total_schemas: int = 0
    schema_types: list[str] = field(default_factory=list)

    # Key schema types
    has_faq_page: bool = False
    has_article: bool = False
    has_how_to: bool = False
    has_organization: bool = False

    # FAQ details
    faq_count: int = 0

    # Author/Authority
    has_author: bool = False
    author_name: str | None = None

    # Freshness
    has_date_modified: bool = False
    date_modified: str | None = None
    days_since_modified: int | None = None
    freshness_level: str = "unknown"

    # Validation
    validation_errors: int = 0

    # Issues
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Show the math
    show_the_math: str = ""

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "detection": {
                "has_json_ld": self.has_json_ld,
                "has_microdata": self.has_microdata,
                "total_schemas": self.total_schemas,
                "types": self.schema_types,
            },
            "types": {
                "has_faq_page": self.has_faq_page,
                "has_article": self.has_article,
                "has_how_to": self.has_how_to,
                "has_organization": self.has_organization,
            },
            "faq_count": self.faq_count,
            "author": {
                "has_author": self.has_author,
                "name": self.author_name,
            },
            "freshness": {
                "has_date_modified": self.has_date_modified,
                "date_modified": self.date_modified,
                "days_since_modified": self.days_since_modified,
                "level": self.freshness_level,
            },
            "validation_errors": self.validation_errors,
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "recommendations": self.recommendations,
            "show_the_math": self.show_the_math,
        }


@dataclass
class AuthorityComponent:
    """A single authority signals component."""

    name: str
    score: float
    weight: float
    level: str  # good, warning, critical
    explanation: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": round(self.score, 2),
            "weight": self.weight,
            "level": self.level,
            "explanation": self.explanation,
        }


@dataclass
class AuthoritySection:
    """Authority Signals section of the report (v2 pillar)."""

    total_score: float  # 0-100
    level: str  # good, warning, critical
    max_points: float = 15.0  # Points this contributes to v2 score

    # Component breakdown
    components: list[AuthorityComponent] = field(default_factory=list)

    # Author attribution
    has_author: bool = False
    author_name: str | None = None
    author_is_linked: bool = False
    has_author_photo: bool = False

    # Credentials
    has_credentials: bool = False
    has_author_bio: bool = False
    credentials_found: list[str] = field(default_factory=list)

    # Citations
    total_citations: int = 0
    authoritative_citations: int = 0

    # Original data
    has_original_data: bool = False
    original_data_count: int = 0

    # Freshness (visible dates)
    has_visible_date: bool = False
    days_since_published: int | None = None
    freshness_level: str = "unknown"

    # Issues
    critical_issues: list[str] = field(default_factory=list)
    all_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    # Show the math
    show_the_math: str = ""

    def to_dict(self) -> dict:
        return {
            "total_score": round(self.total_score, 2),
            "level": self.level,
            "max_points": self.max_points,
            "points_earned": round(self.total_score / 100 * self.max_points, 2),
            "components": [c.to_dict() for c in self.components],
            "author": {
                "has_author": self.has_author,
                "name": self.author_name,
                "is_linked": self.author_is_linked,
                "has_photo": self.has_author_photo,
            },
            "credentials": {
                "has_credentials": self.has_credentials,
                "has_bio": self.has_author_bio,
                "found": self.credentials_found,
            },
            "citations": {
                "total": self.total_citations,
                "authoritative": self.authoritative_citations,
            },
            "original_data": {
                "has_original_data": self.has_original_data,
                "count": self.original_data_count,
            },
            "freshness": {
                "has_visible_date": self.has_visible_date,
                "days_since_published": self.days_since_published,
                "level": self.freshness_level,
            },
            "critical_issues": self.critical_issues,
            "all_issues": self.all_issues,
            "recommendations": self.recommendations,
            "show_the_math": self.show_the_math,
        }


@dataclass
class PillarSummary:
    """Summary of a single scoring pillar for v2."""

    name: str
    display_name: str
    raw_score: float
    max_points: float
    points_earned: float
    level: str

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "raw_score": round(self.raw_score, 2),
            "max_points": self.max_points,
            "points_earned": round(self.points_earned, 2),
            "level": self.level,
        }


@dataclass
class ScoreSectionV2:
    """V2 Score section with 6-pillar breakdown and findability levels."""

    # Overall
    total_score: float  # 0-100
    version: str = "2.1"

    # Findability Level (replaces letter grades)
    level: str = "not_yet_findable"  # e.g., "partially_findable"
    level_label: str = "Not Yet Findable"  # e.g., "Partially Findable"
    level_summary: str = ""  # e.g., "Foundation in place..."
    level_focus: str = ""  # e.g., "Add structured data..."

    # Next milestone
    next_milestone: dict | None = None  # {score, name, description, points_needed}
    points_to_milestone: float = 0.0

    # Path forward (top actions to reach milestone)
    path_forward: list[dict] = field(default_factory=list)

    # Pillar summaries
    pillars: list[PillarSummary] = field(default_factory=list)

    # Summary counts
    pillars_good: int = 0
    pillars_warning: int = 0
    pillars_critical: int = 0

    # Issues, recommendations, and strengths
    critical_issues: list[str] = field(default_factory=list)
    top_recommendations: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)

    # Show the math
    calculation_summary: list[str] = field(default_factory=list)
    show_the_math: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "total_score": round(self.total_score, 2),
            # Findability Level
            "level": self.level,
            "level_label": self.level_label,
            "level_summary": self.level_summary,
            "level_focus": self.level_focus,
            # Milestone
            "next_milestone": self.next_milestone,
            "points_to_milestone": round(self.points_to_milestone, 1),
            # Path forward
            "path_forward": self.path_forward,
            # Pillars
            "pillars": [p.to_dict() for p in self.pillars],
            "pillars_good": self.pillars_good,
            "pillars_warning": self.pillars_warning,
            "pillars_critical": self.pillars_critical,
            # Issues, recommendations, strengths
            "critical_issues": self.critical_issues,
            "top_recommendations": self.top_recommendations,
            "strengths": self.strengths,
            "calculation_summary": self.calculation_summary,
            "show_the_math": self.show_the_math,
        }


@dataclass
class ActionItemSummary:
    """Summary of a single action item."""

    id: str
    category: str
    title: str
    description: str
    priority: int
    impact_level: str
    effort_level: str
    estimated_points: float
    affected_pillar: str
    scaffold: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "impact_level": self.impact_level,
            "effort_level": self.effort_level,
            "estimated_points": round(self.estimated_points, 2),
            "affected_pillar": self.affected_pillar,
            "scaffold": self.scaffold,
        }


@dataclass
class ActionCenterSection:
    """Action Center section for prioritized fixes."""

    # Quick wins
    quick_wins: list[ActionItemSummary] = field(default_factory=list)

    # High priority
    high_priority: list[ActionItemSummary] = field(default_factory=list)

    # All fixes
    all_fixes: list[ActionItemSummary] = field(default_factory=list)

    # Summary stats
    total_fixes: int = 0
    estimated_total_points: float = 0.0
    critical_count: int = 0
    high_count: int = 0
    medium_count: int = 0
    low_count: int = 0

    def to_dict(self) -> dict:
        return {
            "quick_wins": [a.to_dict() for a in self.quick_wins],
            "high_priority": [a.to_dict() for a in self.high_priority],
            "all_fixes": [a.to_dict() for a in self.all_fixes],
            "summary": {
                "total_fixes": self.total_fixes,
                "estimated_total_points": round(self.estimated_total_points, 2),
                "critical_count": self.critical_count,
                "high_count": self.high_count,
                "medium_count": self.medium_count,
                "low_count": self.low_count,
            },
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
class CitableIndexSection:
    """Citable Index section — how deeply AI relies on this source.

    Keyed off citation depth >= 3 (the "citable" threshold).
    """

    # Headline metric
    avg_depth: float  # 0-5 scale
    pct_citable: float  # % questions at depth >= 3
    pct_strongly_sourced: float  # % questions at depth >= 4

    # Depth distribution histogram
    depth_histogram: dict[int, int]  # {0: N, 1: N, ..., 5: N}

    # Confidence in the scores
    confidence: str  # "high" | "medium" | "low"
    depth_divergence: float  # avg |ai - heuristic|

    # Free-signal aggregates
    avg_competitors: float
    framing_distribution: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "avg_depth": round(self.avg_depth, 2),
            "pct_citable": round(self.pct_citable, 1),
            "pct_strongly_sourced": round(self.pct_strongly_sourced, 1),
            "depth_histogram": self.depth_histogram,
            "confidence": self.confidence,
            "depth_divergence": round(self.depth_divergence, 2),
            "avg_competitors": round(self.avg_competitors, 2),
            "framing_distribution": self.framing_distribution,
        }


@dataclass
class FullReport:
    """Complete report combining all analysis sections."""

    metadata: ReportMetadata
    score: ScoreSection
    fixes: FixSection
    crawl: CrawlSection | None = None
    technical: TechnicalSection | None = None  # v2: Technical Readiness
    structure: StructureSection | None = None  # v2: Semantic Structure
    schema: SchemaSection | None = None  # v2: Schema Richness
    authority: AuthoritySection | None = None  # v2: Authority Signals
    score_v2: ScoreSectionV2 | None = None  # v2: Unified 6-pillar score
    action_center: ActionCenterSection | None = None  # v2: Prioritized fixes
    observation: ObservationSection | None = None
    benchmark: BenchmarkSection | None = None
    divergence: DivergenceSection | None = None
    citable_index: CitableIndexSection | None = None  # v1.1: Citation depth metrics

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "metadata": self.metadata.to_dict(),
            "score": self.score.to_dict(),
            "fixes": self.fixes.to_dict(),
        }

        if self.crawl:
            result["crawl"] = self.crawl.to_dict()

        if self.technical:
            result["technical"] = self.technical.to_dict()

        if self.structure:
            result["structure"] = self.structure.to_dict()

        if self.schema:
            result["schema"] = self.schema.to_dict()

        if self.authority:
            result["authority"] = self.authority.to_dict()

        if self.score_v2:
            result["score_v2"] = self.score_v2.to_dict()

        if self.action_center:
            result["action_center"] = self.action_center.to_dict()

        if self.observation:
            result["observation"] = self.observation.to_dict()

        if self.benchmark:
            result["benchmark"] = self.benchmark.to_dict()

        if self.divergence:
            result["divergence"] = self.divergence.to_dict()

        if self.citable_index:
            result["citable_index"] = self.citable_index.to_dict()

        return result

    def get_quick_access_fields(self) -> dict:
        """Get denormalized fields for database quick access."""
        return {
            "score_conservative": int(self.score.total_score * SCORE_BAND_CONSERVATIVE),
            "score_typical": int(self.score.total_score),
            "score_generous": int(min(100, self.score.total_score * SCORE_BAND_GENEROUS)),
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
