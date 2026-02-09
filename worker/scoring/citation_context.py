"""Citation Context  - predicts whether AI will actually cite a URL.

The Findable Score (7 pillars) measures sourceability: "Can AI find and use
your content?" Citation Context answers the follow-up: "Will AI actually
cite your URL?"

Key insight: A site can score 95/100 on all pillars and still get 0% citation
rate. Pillar scores measure what the site owner controls; citation depends on
whether the AI has better alternatives.

This module generates citation predictions and recommendations based on:
1. Site content type (strongest predictor)
2. Per-question-category citation rates
3. Actionable recommendations for improving citation likelihood
"""

from dataclasses import dataclass, field

import structlog

from worker.extraction.site_type import (
    CATEGORY_CITATION_RATES,
    CITATION_BASELINES,
    SiteType,
    SiteTypeResult,
)

logger = structlog.get_logger(__name__)


class CitationLikelihood:
    """Citation likelihood levels with thresholds."""

    HIGH = "high"  # >= 0.70
    MODERATE = "moderate"  # 0.40-0.69
    LOW = "low"  # < 0.40

    @staticmethod
    def from_rate(rate: float) -> str:
        if rate >= 0.70:
            return CitationLikelihood.HIGH
        elif rate >= 0.40:
            return CitationLikelihood.MODERATE
        return CitationLikelihood.LOW


@dataclass
class CategoryPrediction:
    """Citation prediction for a question category."""

    category: str
    likelihood: str  # high, moderate, low
    predicted_rate: float
    reason: str

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "likelihood": self.likelihood,
            "predicted_rate": round(self.predicted_rate, 2),
            "reason": self.reason,
        }


@dataclass
class CitationContext:
    """Citation context for a site  - predicts real-world citation behavior."""

    # Site classification
    site_type: str
    site_type_confidence: float

    # Overall citation prediction
    citation_baseline: float
    citation_range: tuple[float, float]
    citation_description: str
    overall_likelihood: str  # high, moderate, low

    # Per-category predictions
    category_predictions: list[CategoryPrediction] = field(default_factory=list)

    # Actionable recommendations
    recommendations: list[str] = field(default_factory=list)

    # Best category for citation (where to focus)
    best_category: str = ""
    worst_category: str = ""

    def to_dict(self) -> dict:
        return {
            "site_type": self.site_type,
            "site_type_confidence": round(self.site_type_confidence, 2),
            "citation_baseline": round(self.citation_baseline, 2),
            "citation_range": [round(r, 2) for r in self.citation_range],
            "citation_description": self.citation_description,
            "overall_likelihood": self.overall_likelihood,
            "category_predictions": [p.to_dict() for p in self.category_predictions],
            "recommendations": self.recommendations,
            "best_category": self.best_category,
            "worst_category": self.worst_category,
        }

    def show_citation_context(self) -> str:
        """Generate human-readable citation context."""
        lines = [
            "=" * 60,
            "CITATION CONTEXT",
            "=" * 60,
            "",
            f"Site Type: {self.site_type.replace('_', ' ').title()}",
            f"Citation Baseline: ~{self.citation_baseline * 100:.0f}% "
            f"(range: {self.citation_range[0] * 100:.0f}-{self.citation_range[1] * 100:.0f}%)",
            f"Overall Likelihood: {self.overall_likelihood.upper()}",
            "",
            self.citation_description,
            "",
            "-" * 60,
            "PER-CATEGORY PREDICTIONS",
            "-" * 60,
        ]

        for pred in self.category_predictions:
            icon = (
                "+" if pred.likelihood == "high" else "!" if pred.likelihood == "moderate" else "-"
            )
            lines.append(
                f"  [{icon}] {pred.category.title():<20} "
                f"{pred.likelihood.upper():<10} "
                f"({pred.predicted_rate * 100:.0f}%)"
            )
            lines.append(f"      {pred.reason}")

        if self.recommendations:
            lines.extend(
                [
                    "",
                    "-" * 60,
                    "HOW TO IMPROVE CITATION RATE",
                    "-" * 60,
                ]
            )
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"  {i}. {rec}")

        lines.extend(["", "=" * 60])
        return "\n".join(lines)


# Reasons for each category by site type
_CATEGORY_REASONS = {
    SiteType.DOCUMENTATION: {
        "identity": "Documentation sites are well-known; AI rarely needs to cite the About page.",
        "differentiation": "Your docs ARE the differentiation  - AI cites them as the authoritative source.",
        "expertise": "Technical documentation is the strongest content type for AI citation.",
        "comparison": "Comparison content is sometimes cited, but AI may synthesize from multiple docs.",
        "offerings": "Feature documentation gets cited when users ask about specific capabilities.",
    },
    SiteType.SAAS_MARKETING: {
        "identity": "AI knows your brand from training data and rarely cites your About page.",
        "differentiation": "Unique positioning content has citation potential if sufficiently specific.",
        "expertise": "How-to content with specific implementation details can get cited.",
        "comparison": "AI synthesizes comparisons from multiple sources; your comparison page is one of many.",
        "offerings": "Product pages compete with review sites and aggregators for citation.",
    },
    SiteType.NEWS_MEDIA: {
        "identity": "AI models are trained on news content and don't need to cite your homepage.",
        "differentiation": "News brands are well-known; AI cites original sources, not news coverage.",
        "expertise": "Investigative or analytical content occasionally gets cited.",
        "comparison": "AI rarely cites news sites for comparison queries.",
        "offerings": "Not applicable for most news sites.",
    },
    SiteType.UGC_PLATFORM: {
        "identity": "AI knows UGC platforms well; no need to cite their About pages.",
        "differentiation": "Specific threads/posts get cited, not the platform itself.",
        "expertise": "Individual expert answers on the platform may get cited.",
        "comparison": "Review aggregation data sometimes gets cited.",
        "offerings": "Platform features are rarely the subject of AI queries.",
    },
    SiteType.REFERENCE: {
        "identity": "Well-known reference sites are recognized but rarely cited for identity queries.",
        "differentiation": "Reference content is the gold standard  - AI cites it heavily.",
        "expertise": "Unique, authoritative answers drive most citations.",
        "comparison": "Side-by-side reference data gets cited when available.",
        "offerings": "Feature documentation of reference tools gets good citation rates.",
    },
    SiteType.DEVELOPER_TOOLS: {
        "identity": "Developer tool brands are recognized; About pages rarely cited.",
        "differentiation": "Technical docs and unique features drive citation.",
        "expertise": "Implementation guides and tutorials are strong citation drivers.",
        "comparison": "Integration docs and compatibility info can get cited.",
        "offerings": "API and SDK documentation drives most citations.",
    },
    SiteType.ECOMMERCE: {
        "identity": "E-commerce brands may or may not be well-known to AI.",
        "differentiation": "Product uniqueness and reviews can drive citation.",
        "expertise": "Buying guides and product education content can get cited.",
        "comparison": "Price comparison data occasionally gets cited.",
        "offerings": "Product detail pages with rich data can get cited for purchase queries.",
    },
    SiteType.BLOG: {
        "identity": "Blog identity depends on the author's reputation and expertise.",
        "differentiation": "Unique perspectives and original research drive citation.",
        "expertise": "Deep technical or domain expertise content gets cited.",
        "comparison": "Original benchmark data and hands-on comparisons can get cited.",
        "offerings": "Not typically applicable for blogs.",
    },
    SiteType.MIXED: {
        "identity": "Citation likelihood depends on your specific content and brand recognition.",
        "differentiation": "Unique positioning content has moderate citation potential.",
        "expertise": "Expert content with specific implementation details can get cited.",
        "comparison": "Original data and hands-on comparisons improve citation chances.",
        "offerings": "Product/service pages may be cited depending on content uniqueness.",
    },
}

# Recommendations by site type
_SITE_TYPE_RECOMMENDATIONS = {
    SiteType.DOCUMENTATION: [
        "Maintain comprehensive, up-to-date documentation  - this is your strongest citation driver.",
        "Add code examples and practical tutorials that AI can reference.",
        "Ensure API reference pages are well-structured with clear parameter descriptions.",
    ],
    SiteType.SAAS_MARKETING: [
        "Create documentation-style content (reference pages, tutorials, implementation guides). "
        "Documentation gets cited 3x more than marketing copy.",
        "Publish original research with unique data, benchmarks, or case studies. "
        "AI cites unique data sources it can't find elsewhere.",
        "Build detailed how-to guides specific to YOUR product  - generic best practices "
        "content gets outcompeted by docs sites.",
        "Add a /docs section with technical reference material that becomes the canonical "
        "source for your product's use cases.",
    ],
    SiteType.NEWS_MEDIA: [
        "Focus on original investigative content with unique data or analysis.",
        "Create reference pages for ongoing topics (timelines, fact sheets, data trackers).",
        "Build topic authority through comprehensive coverage that becomes a canonical source.",
    ],
    SiteType.UGC_PLATFORM: [
        "Ensure high-quality answers and content are well-structured and accessible.",
        "Create curated collections and topic hubs from community content.",
        "Add structured data to highlight expert-verified or highly-rated content.",
    ],
    SiteType.REFERENCE: [
        "Keep reference content comprehensive and up-to-date.",
        "Add structured data for easy AI extraction (definitions, code examples, tables).",
        "Ensure content hierarchy is clear so AI can find specific answers quickly.",
    ],
    SiteType.DEVELOPER_TOOLS: [
        "Invest in comprehensive API documentation and SDK guides.",
        "Create tutorials and integration guides for common use cases.",
        "Publish performance benchmarks and technical deep-dives with unique data.",
    ],
    SiteType.ECOMMERCE: [
        "Add rich product descriptions with specifications, not just marketing copy.",
        "Create buying guides and comparison content for your product categories.",
        "Implement Product schema with detailed attributes (price, availability, reviews).",
    ],
    SiteType.BLOG: [
        "Focus on original research, unique data, and expert analysis.",
        "Build topic clusters around your areas of deep expertise.",
        "Add author credentials and expertise signals to boost trust.",
    ],
    SiteType.MIXED: [
        "Identify your highest-value content type and double down on it.",
        "Create a clear content structure so AI can find authoritative pages quickly.",
        "Focus on content where you're the primary/canonical source, not one of many.",
    ],
}


def generate_citation_context(
    site_type_result: SiteTypeResult,
) -> CitationContext:
    """
    Generate citation context from a site type classification.

    Args:
        site_type_result: Result from SiteTypeDetector

    Returns:
        CitationContext with predictions and recommendations
    """
    st = site_type_result.site_type

    # Build per-category predictions
    category_rates = CATEGORY_CITATION_RATES.get(st, {})
    reasons = _CATEGORY_REASONS.get(st, _CATEGORY_REASONS[SiteType.MIXED])
    categories = ["identity", "differentiation", "expertise", "comparison", "offerings"]

    predictions = []
    best_cat = ""
    best_rate = 0.0
    worst_cat = ""
    worst_rate = 1.0

    for cat in categories:
        rate = category_rates.get(cat, 0.5)
        reason = reasons.get(cat, "")
        likelihood = CitationLikelihood.from_rate(rate)

        predictions.append(
            CategoryPrediction(
                category=cat,
                likelihood=likelihood,
                predicted_rate=rate,
                reason=reason,
            )
        )

        if rate > best_rate:
            best_rate = rate
            best_cat = cat
        if rate < worst_rate:
            worst_rate = rate
            worst_cat = cat

    # Get recommendations
    recommendations = _SITE_TYPE_RECOMMENDATIONS.get(st, _SITE_TYPE_RECOMMENDATIONS[SiteType.MIXED])

    # Overall likelihood
    overall = CitationLikelihood.from_rate(site_type_result.citation_baseline)

    baseline = CITATION_BASELINES[st]

    context = CitationContext(
        site_type=st.value,
        site_type_confidence=site_type_result.confidence,
        citation_baseline=site_type_result.citation_baseline,
        citation_range=baseline["range"],  # type: ignore[arg-type]
        citation_description=baseline["description"],  # type: ignore[arg-type]
        overall_likelihood=overall,
        category_predictions=predictions,
        recommendations=recommendations,
        best_category=best_cat,
        worst_category=worst_cat,
    )

    logger.info(
        "citation_context_generated",
        site_type=st.value,
        overall_likelihood=overall,
        best_category=best_cat,
        worst_category=worst_cat,
    )

    return context
