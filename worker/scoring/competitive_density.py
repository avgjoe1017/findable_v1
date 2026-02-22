"""Competitive density estimation — how many equivalent sources compete for the same content?

The key insight: "What is CRM?" has 1000 competing answers (low citation chance
for any single site), while "How to configure Stripe webhook retries" has essentially
just stripe.com/docs (high citation chance).

Competitive density is the inverse of source uniqueness. High density means many
equivalent sources exist, making citation of any specific one unlikely. Low density
means the site is one of very few (or the only) credible source, making citation
far more likely.

This module combines two factors:
1. Question category density — some question types are inherently more competitive
   (e.g., comparison queries attract many listicle sites, while identity queries
   about a specific brand have few competitors)
2. Site type competition — some site types exist in crowded markets (SaaS marketing,
   news) while others occupy unique niches (documentation, reference)

Usage:
    from worker.scoring.competitive_density import analyze_competitive_density
    from worker.extraction.site_type import SiteType

    result = analyze_competitive_density(
        site_type=SiteType.DOCUMENTATION,
        question_categories=["identity", "expertise", "comparison"],
        is_own_brand_query=[True, True, False],
        domain="docs.python.org",
    )
    print(result.density_score)    # 0-100 (low = less competition)
    print(result.inverse_score)    # 0-100 (high = better for citation)
"""

from __future__ import annotations

from dataclasses import dataclass, field

import structlog

from worker.extraction.site_type import SiteType

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Question category density mapping
# ---------------------------------------------------------------------------
# Each value represents the estimated number of equivalent credible sources
# that compete for that question type, normalised to a 0-100 density scale.
#
# "own_site" = the question is specifically about the site's own brand/product
#   (e.g. "What does Stripe do?" asked about stripe.com)
# "other_site" = the question is about a generic category the site happens
#   to cover (e.g. "What is a payment gateway?" when the site is stripe.com)
#
# Categories without own/other distinction have a single float value — they
# are equally competitive regardless of brand focus.
# ---------------------------------------------------------------------------
CATEGORY_DENSITY: dict[str, dict[str, float] | float] = {
    "identity": {
        "own_site": 5.0,  # "What is [Brand]?" — very few competitors for YOUR brand
        "other_site": 85.0,  # "What is [Category]?" — many competitors
    },
    "differentiation": {
        "own_site": 30.0,  # "Why choose [Brand]?" — some competitors (comparison sites)
        "other_site": 70.0,  # "What differentiates X?" — moderate competition
    },
    "expertise": {
        "own_site": 40.0,  # "How to do X with [Brand]?" — moderate (docs + tutorials)
        "other_site": 60.0,  # "How to do X?" — many generic guides
    },
    "comparison": 80.0,  # "X vs Y?" — always high competition (many comparison sites)
    "offerings": {
        "own_site": 15.0,  # "What does [Brand] offer?" — only the brand itself + review sites
        "other_site": 75.0,  # "What are the best X tools?" — very competitive listicles
    },
    # Additional categories that may appear in generated questions
    "contact": {
        "own_site": 5.0,  # "How to contact [Brand]?" — essentially only the brand itself
        "other_site": 50.0,  # "How to contact X support?" — moderate
    },
    "trust": {
        "own_site": 20.0,  # "Is [Brand] trustworthy?" — brand + review sites
        "other_site": 65.0,  # "Best reviewed X?" — many review aggregators
    },
}

# Default density for unknown question categories
DEFAULT_CATEGORY_DENSITY = 50.0


# ---------------------------------------------------------------------------
# Site type competition factor
# ---------------------------------------------------------------------------
# How competitive the landscape is for this type of site, on a 0-1 scale.
# 0.0 = essentially no competition (unique source)
# 1.0 = maximum competition (identical content from many sites)
# ---------------------------------------------------------------------------
SITE_TYPE_COMPETITION: dict[SiteType, float] = {
    SiteType.DOCUMENTATION: 0.15,  # Docs are unique by definition
    SiteType.REFERENCE: 0.25,  # References are relatively unique
    SiteType.DEVELOPER_TOOLS: 0.30,  # Some competition but specialised
    SiteType.BLOG: 0.65,  # Blogs compete with many similar blogs
    SiteType.SAAS_MARKETING: 0.75,  # SaaS marketing is extremely competitive
    SiteType.NEWS_MEDIA: 0.85,  # News is rehashed by many outlets
    SiteType.UGC_PLATFORM: 0.70,  # UGC competes with many platforms
    SiteType.ECOMMERCE: 0.80,  # E-commerce is very competitive
    SiteType.MIXED: 0.55,  # Default middle ground
}

# Fallback for any SiteType not in the mapping
DEFAULT_SITE_TYPE_COMPETITION = 0.55


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class CompetitiveDensityResult:
    """Result of competitive density analysis.

    Attributes:
        density_score: Overall competitive density, 0-100.
            0 = no competition (unique source), 100 = extremely competitive.
        category_scores: Per-question-category density breakdown.
        site_type_factor: The competition factor applied from the site type
            (0.0-1.0; higher = more competitive landscape).
        explanation: Human-readable summary of the analysis.
    """

    density_score: float  # 0-100 (0 = no competition, 100 = extremely competitive)
    category_scores: dict[str, float] = field(default_factory=dict)
    site_type_factor: float = 0.5
    explanation: str = ""

    @property
    def inverse_score(self) -> float:
        """Inverse density (high = less competition = better for citation).

        Returns:
            Float 0-100 where 100 means the site faces almost no competition.
        """
        return 100.0 - self.density_score

    def to_dict(self) -> dict:
        """Serialise to a plain dict for JSON storage / API responses."""
        return {
            "density_score": round(self.density_score, 2),
            "inverse_score": round(self.inverse_score, 2),
            "category_scores": {k: round(v, 2) for k, v in self.category_scores.items()},
            "site_type_factor": round(self.site_type_factor, 2),
            "explanation": self.explanation,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _get_category_density(category: str, is_own_brand: bool) -> float:
    """Look up the density value for a single question category.

    Args:
        category: Question category string (e.g. "identity", "expertise").
        is_own_brand: Whether the question is about the site's own brand.

    Returns:
        Density value 0-100.
    """
    entry = CATEGORY_DENSITY.get(category.lower())

    if entry is None:
        return DEFAULT_CATEGORY_DENSITY

    # Single float value — no own/other distinction
    if isinstance(entry, int | float):
        return float(entry)

    # Dict with own_site / other_site keys
    key = "own_site" if is_own_brand else "other_site"
    return float(entry.get(key, DEFAULT_CATEGORY_DENSITY))


def _blend_density(
    category_density: float,
    site_competition: float,
    *,
    category_weight: float = 0.6,
    site_weight: float = 0.4,
) -> float:
    """Blend question-category density with site-type competition factor.

    The blending weights determine how much each factor contributes to the
    final density estimate.  The default 60/40 split favours the question-level
    signal because it is more specific, while the site-level factor provides
    a useful prior.

    Args:
        category_density: Raw density for the question category (0-100).
        site_competition: Site type competition factor (0-1).
        category_weight: Weight for the category signal.
        site_weight: Weight for the site-type signal.

    Returns:
        Blended density score (0-100).
    """
    # Convert site_competition (0-1) to the same 0-100 scale
    site_density = site_competition * 100.0
    blended = category_weight * category_density + site_weight * site_density
    return max(0.0, min(100.0, blended))


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------
def analyze_competitive_density(
    site_type: SiteType,
    question_categories: list[str],
    is_own_brand_query: list[bool],
    domain: str | None = None,
) -> CompetitiveDensityResult:
    """Estimate competitive density for a site's content.

    For each generated question the function looks up the inherent competitive
    density of that question category (adjusted for whether the question is
    about the site's own brand), then blends it with the site-type competition
    factor.  The overall density is the average across all questions.

    Args:
        site_type: Detected site type (from ``SiteTypeDetector``).
        question_categories: List of question category strings
            (e.g. ``["identity", "expertise", "comparison"]``).
        is_own_brand_query: Parallel list indicating whether each question
            is about the site's own brand (``True``) or a generic category
            query (``False``).
        domain: Optional domain string, used only for logging context.

    Returns:
        ``CompetitiveDensityResult`` with overall density and per-category
        breakdown.
    """
    # --- Defensive: empty input -------------------------------------------
    if not question_categories:
        logger.warning(
            "competitive_density_empty_questions",
            domain=domain,
        )
        site_factor = SITE_TYPE_COMPETITION.get(site_type, DEFAULT_SITE_TYPE_COMPETITION)
        return CompetitiveDensityResult(
            density_score=site_factor * 100.0,
            site_type_factor=site_factor,
            explanation=(
                f"No questions provided. "
                f"Density estimated from site type ({site_type.value}) alone."
            ),
        )

    # Ensure is_own_brand_query aligns with question_categories.  If shorter,
    # pad with False (assume generic query).  If longer, truncate silently.
    brand_flags = list(is_own_brand_query)
    while len(brand_flags) < len(question_categories):
        brand_flags.append(False)
    brand_flags = brand_flags[: len(question_categories)]

    site_factor = SITE_TYPE_COMPETITION.get(site_type, DEFAULT_SITE_TYPE_COMPETITION)

    # --- Per-question density ---------------------------------------------
    per_question_densities: list[float] = []
    category_accum: dict[str, list[float]] = {}

    for category, is_own in zip(question_categories, brand_flags, strict=False):
        cat_density = _get_category_density(category, is_own)
        blended = _blend_density(cat_density, site_factor)
        per_question_densities.append(blended)

        cat_key = category.lower()
        if cat_key not in category_accum:
            category_accum[cat_key] = []
        category_accum[cat_key].append(blended)

    # --- Aggregate --------------------------------------------------------
    overall_density = (
        sum(per_question_densities) / len(per_question_densities)
        if per_question_densities
        else site_factor * 100.0
    )
    overall_density = max(0.0, min(100.0, overall_density))

    category_scores: dict[str, float] = {
        cat: sum(vals) / len(vals) for cat, vals in category_accum.items() if vals
    }

    # --- Build explanation ------------------------------------------------
    inverse = 100.0 - overall_density
    if overall_density < 25:
        density_label = "very low competition"
    elif overall_density < 45:
        density_label = "low competition"
    elif overall_density < 60:
        density_label = "moderate competition"
    elif overall_density < 80:
        density_label = "high competition"
    else:
        density_label = "very high competition"

    own_count = sum(1 for b in brand_flags if b)
    generic_count = len(brand_flags) - own_count
    explanation = (
        f"Competitive density is {overall_density:.0f}/100 ({density_label}). "
        f"Analyzed {len(question_categories)} question(s) "
        f"({own_count} brand-specific, {generic_count} generic) "
        f"for a {site_type.value} site. "
        f"Site-type competition factor: {site_factor:.2f}. "
        f"Inverse score (uniqueness advantage): {inverse:.0f}/100."
    )

    result = CompetitiveDensityResult(
        density_score=overall_density,
        category_scores=category_scores,
        site_type_factor=site_factor,
        explanation=explanation,
    )

    logger.info(
        "competitive_density_analyzed",
        domain=domain,
        site_type=site_type.value,
        density_score=round(overall_density, 2),
        inverse_score=round(inverse, 2),
        num_questions=len(question_categories),
        own_brand_count=own_count,
        category_scores={k: round(v, 2) for k, v in category_scores.items()},
    )

    return result
