"""Source primacy detection — is this site THE authoritative source for its content?

The strongest predictor of AI citation is whether a site is the *primary* source
for the information it contains. AI models strongly prefer citing canonical/original
sources over sites that aggregate, restate, or comment on information available
elsewhere.

Source primacy levels:
- PRIMARY: Site IS the canonical source (docs.python.org for Python, stripe.com/docs for Stripe API)
- AUTHORITATIVE: Not the original source, but recognized authority (MDN for web standards, Ahrefs for SEO)
- DERIVATIVE: Content is available from many equivalent sources (generic blog posts, news rewrites)

Signals analyzed:
1. Content uniqueness markers (proprietary data, original research, product docs)
2. Domain-content alignment (does the domain own the topic?)
3. Citation patterns from URL structure
4. Entity-topic ownership (is this the entity's own website?)
"""

from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

import structlog

from worker.extraction.page_type import PageType, PageTypeResult
from worker.extraction.site_type import SiteType

logger = structlog.get_logger(__name__)


class PrimacyLevel(StrEnum):
    """How strongly this site owns its content."""

    PRIMARY = "primary"  # THE canonical source (>80% citation rate)
    AUTHORITATIVE = "authoritative"  # Recognized authority (50-80% citation rate)
    DERIVATIVE = "derivative"  # One of many equivalent sources (<50% citation rate)


# Expected citation rates per primacy level
PRIMACY_CITATION_RATES = {
    PrimacyLevel.PRIMARY: 0.90,
    PrimacyLevel.AUTHORITATIVE: 0.65,
    PrimacyLevel.DERIVATIVE: 0.25,
}


@dataclass
class PrimacySignal:
    """Individual signal contributing to primacy score."""

    name: str
    score: float  # -1.0 to 1.0 (negative = derivative, positive = primary)
    reason: str


@dataclass
class SourcePrimacyResult:
    """Result of source primacy analysis."""

    primacy_level: PrimacyLevel
    primacy_score: float  # 0-1 (0=derivative, 1=primary)
    signals: list[PrimacySignal] = field(default_factory=list)
    expected_citation_rate: float = 0.5

    def to_dict(self) -> dict:
        return {
            "primacy_level": self.primacy_level.value,
            "primacy_score": round(self.primacy_score, 2),
            "expected_citation_rate": round(self.expected_citation_rate, 2),
            "signals": [
                {"name": s.name, "score": round(s.score, 2), "reason": s.reason}
                for s in self.signals
            ],
        }


# Content types that indicate primary source status
_PRIMARY_CONTENT_INDICATORS = {
    PageType.DOCUMENTATION: 0.8,  # Product docs = primary source
    PageType.PRICING: 0.7,  # Pricing is from the source
    PageType.FAQ: 0.3,  # FAQ can be original or derivative
    PageType.BLOG_POST: 0.0,  # Blogs can be either
    PageType.BLOG_INDEX: 0.0,
    PageType.HOMEPAGE: 0.1,
    PageType.ABOUT: 0.2,
    PageType.CONTACT: 0.4,  # Contact info is inherently primary
    PageType.PRODUCT: 0.5,  # Product pages are usually primary
    PageType.SERVICE: 0.4,
    PageType.LEGAL: 0.3,
    PageType.UNKNOWN: 0.1,
}

# URL path patterns that indicate primary source content
_PRIMARY_URL_PATTERNS = [
    "/docs",
    "/documentation",
    "/api",
    "/reference",
    "/sdk",
    "/changelog",
    "/release-notes",
    "/specifications",
    "/spec",
    "/rfc",
    "/status",
]

# URL path patterns that indicate derivative content
_DERIVATIVE_URL_PATTERNS = [
    "/blog",
    "/news",
    "/press",
    "/articles",
    "/posts",
    "/reviews",
    "/comparison",
    "/vs",
    "/alternatives",
    "/best-",
    "/top-",
    "/guide-to",
    "/what-is",
    "/how-to",
]


def analyze_source_primacy(
    domain: str,
    site_type: SiteType,
    page_urls: list[str],
    page_type_results: list[PageTypeResult] | None = None,
    brand_name: str | None = None,
    pages_content: list[str] | None = None,
) -> SourcePrimacyResult:
    """
    Analyze whether a site is a primary, authoritative, or derivative source.

    Args:
        domain: Site domain (e.g., "docs.python.org")
        site_type: Previously detected site type
        page_urls: List of crawled page URLs
        page_type_results: Optional pre-computed page type results
        brand_name: Optional brand name for entity-topic alignment
        pages_content: Optional extracted text content per page (for content uniqueness)

    Returns:
        SourcePrimacyResult with primacy level, score, and signals
    """
    signals: list[PrimacySignal] = []
    raw_score = 0.0

    # 1. Site type as baseline
    type_signal = _score_from_site_type(site_type)
    signals.append(type_signal)
    raw_score += type_signal.score

    # 2. Content type distribution from page types
    if page_type_results:
        content_signal = _score_from_page_types(page_type_results)
        signals.append(content_signal)
        raw_score += content_signal.score

    # 3. URL patterns
    url_signal = _score_from_urls(page_urls)
    signals.append(url_signal)
    raw_score += url_signal.score

    # 4. Domain-topic alignment
    domain_signal = _score_from_domain_alignment(domain, site_type, brand_name)
    signals.append(domain_signal)
    raw_score += domain_signal.score

    # 5. Self-referential content (does the site talk about its own product?)
    self_ref_signal = _score_from_self_reference(domain, page_urls)
    signals.append(self_ref_signal)
    raw_score += self_ref_signal.score

    # 6. Content uniqueness (proprietary data, first-party markers, generic phrasing)
    if pages_content:
        try:
            from worker.extraction.content_uniqueness import analyze_content_uniqueness

            uniqueness_result = analyze_content_uniqueness(
                pages_content=pages_content,
                page_urls=page_urls,
                domain=domain,
            )
            # Convert 0-100 score to -1 to +1 range for consistency with other signals
            # 50 = neutral, 100 = strongly primary, 0 = strongly derivative
            uniqueness_normalized = (uniqueness_result.score - 50.0) / 50.0
            uniqueness_signal = PrimacySignal(
                name="content_uniqueness",
                score=max(-1.0, min(1.0, uniqueness_normalized)),
                reason=f"Content uniqueness score: {uniqueness_result.score:.0f}/100 "
                f"(proprietary={uniqueness_result.proprietary_data_score:.0f}, "
                f"first_party={uniqueness_result.first_party_score:.0f}, "
                f"non_generic={uniqueness_result.generic_phrasing_score:.0f})",
            )
            signals.append(uniqueness_signal)
            raw_score += uniqueness_signal.score
        except Exception as e:
            logger.warning("content_uniqueness_signal_failed", error=str(e))

    # Normalize to 0-1 range (max possible from N signals each +-1.0)
    max_possible = len(signals)
    primacy_score = max(0.0, min(1.0, (raw_score + max_possible) / (2 * max_possible)))

    # Determine level
    if primacy_score >= 0.65:
        level = PrimacyLevel.PRIMARY
    elif primacy_score >= 0.40:
        level = PrimacyLevel.AUTHORITATIVE
    else:
        level = PrimacyLevel.DERIVATIVE

    expected_rate = PRIMACY_CITATION_RATES[level]

    result = SourcePrimacyResult(
        primacy_level=level,
        primacy_score=primacy_score,
        signals=signals,
        expected_citation_rate=expected_rate,
    )

    logger.info(
        "source_primacy_analyzed",
        domain=domain,
        primacy_level=level.value,
        primacy_score=round(primacy_score, 2),
        expected_citation_rate=expected_rate,
    )

    return result


def _score_from_site_type(site_type: SiteType) -> PrimacySignal:
    """Score based on site type — documentation and reference are inherently primary."""
    type_scores = {
        SiteType.DOCUMENTATION: 0.8,
        SiteType.REFERENCE: 0.7,
        SiteType.DEVELOPER_TOOLS: 0.5,
        SiteType.SAAS_MARKETING: -0.2,
        SiteType.NEWS_MEDIA: -0.6,
        SiteType.UGC_PLATFORM: -0.3,
        SiteType.ECOMMERCE: 0.1,
        SiteType.BLOG: -0.1,
        SiteType.MIXED: 0.0,
    }
    score = type_scores.get(site_type, 0.0)

    reasons = {
        SiteType.DOCUMENTATION: "Documentation sites are canonical sources for their topics.",
        SiteType.REFERENCE: "Reference sites own their authoritative data.",
        SiteType.DEVELOPER_TOOLS: "Developer tools own their technical documentation.",
        SiteType.SAAS_MARKETING: "Marketing content competes with many equivalent sources.",
        SiteType.NEWS_MEDIA: "News sites report on others' content; they're rarely the primary source.",
        SiteType.UGC_PLATFORM: "UGC aggregates others' content; individual posts may be primary.",
        SiteType.ECOMMERCE: "E-commerce sites own their product data but not general category info.",
        SiteType.BLOG: "Blog primacy depends entirely on content originality.",
        SiteType.MIXED: "Mixed content type; primacy varies by section.",
    }

    return PrimacySignal(
        name="site_type",
        score=score,
        reason=reasons.get(site_type, "Unknown site type."),
    )


def _score_from_page_types(page_type_results: list[PageTypeResult]) -> PrimacySignal:
    """Score based on what types of pages the site contains."""
    if not page_type_results:
        return PrimacySignal(name="content_types", score=0.0, reason="No page data available.")

    total = len(page_type_results)
    weighted_score = 0.0

    for pt_result in page_type_results:
        indicator_score = _PRIMARY_CONTENT_INDICATORS.get(pt_result.page_type, 0.0)
        weighted_score += indicator_score

    avg_score = weighted_score / total if total > 0 else 0.0

    # Map from 0-1 to -0.5 to 1.0
    score = (avg_score - 0.3) * 2.0
    score = max(-1.0, min(1.0, score))

    primary_count = sum(
        1 for pt in page_type_results if _PRIMARY_CONTENT_INDICATORS.get(pt.page_type, 0.0) >= 0.5
    )
    pct = primary_count / total * 100 if total > 0 else 0

    return PrimacySignal(
        name="content_types",
        score=score,
        reason=f"{pct:.0f}% of pages are primary-source content types "
        f"(docs, API, product, changelog).",
    )


def _score_from_urls(page_urls: list[str]) -> PrimacySignal:
    """Score based on URL path patterns."""
    if not page_urls:
        return PrimacySignal(name="url_patterns", score=0.0, reason="No URLs to analyze.")

    primary_count = 0
    derivative_count = 0

    for url in page_urls:
        path = urlparse(url).path.lower()
        if any(p in path for p in _PRIMARY_URL_PATTERNS):
            primary_count += 1
        if any(p in path for p in _DERIVATIVE_URL_PATTERNS):
            derivative_count += 1

    total = len(page_urls)
    primary_ratio = primary_count / total if total > 0 else 0
    derivative_ratio = derivative_count / total if total > 0 else 0

    # Net score: primary signals minus derivative signals
    score = (primary_ratio - derivative_ratio) * 2.0
    score = max(-1.0, min(1.0, score))

    return PrimacySignal(
        name="url_patterns",
        score=score,
        reason=f"{primary_count} primary-source URLs (docs, API, reference) vs "
        f"{derivative_count} derivative URLs (blog, news, comparisons).",
    )


def _score_from_domain_alignment(
    domain: str,
    site_type: SiteType,
    brand_name: str | None = None,
) -> PrimacySignal:
    """Score based on whether the domain inherently owns its topic.

    A site about its own product (stripe.com about Stripe) is a primary source.
    A site about others' products (review site about Stripe) is derivative.
    """
    score = 0.0
    reasons = []

    # Subdomain signals
    subdomain = domain.split(".")[0] if "." in domain else domain
    primary_subdomains = {"docs", "api", "developer", "developers", "reference", "wiki", "dev"}
    if subdomain in primary_subdomains:
        score += 0.5
        reasons.append(f"Subdomain '{subdomain}' indicates primary source content.")

    # Self-owned domain pattern (the brand's own site)
    # If site type is documentation or developer_tools, it's likely the product's own docs
    if site_type in (SiteType.DOCUMENTATION, SiteType.DEVELOPER_TOOLS):
        score += 0.3
        reasons.append("Site type indicates self-owned product content.")

    # If brand name matches domain, strong primary signal
    if brand_name:
        brand_lower = brand_name.lower().replace(" ", "")
        domain_base = domain.split(".")[0] if "." in domain else domain
        if brand_lower in domain_base or domain_base in brand_lower:
            score += 0.3
            reasons.append(f"Domain matches brand '{brand_name}' — content is about own product.")

    # News/UGC domains are inherently covering others' content
    if site_type in (SiteType.NEWS_MEDIA, SiteType.UGC_PLATFORM):
        score -= 0.4
        reasons.append("News/UGC sites primarily cover others' content.")

    score = max(-1.0, min(1.0, score))
    reason = " ".join(reasons) if reasons else "No strong domain alignment signals."

    return PrimacySignal(name="domain_alignment", score=score, reason=reason)


def _score_from_self_reference(_domain: str, page_urls: list[str]) -> PrimacySignal:
    """Score based on whether the site's URLs reference its own domain/brand.

    Sites that primarily link to their own docs/API/product pages are primary sources.
    Sites with lots of external-topic URLs (/best-X, /alternatives-to, /vs) are derivative.
    """
    if not page_urls:
        return PrimacySignal(name="self_reference", score=0.0, reason="No URLs to analyze.")

    own_topic_count = 0
    external_topic_count = 0

    for url in page_urls:
        path = urlparse(url).path.lower()

        # Self-referential patterns (site talking about its own stuff)
        if any(
            p in path
            for p in [
                "/docs",
                "/api",
                "/pricing",
                "/features",
                "/changelog",
                "/getting-started",
                "/quickstart",
                "/integrations",
                "/download",
                "/install",
            ]
        ):
            own_topic_count += 1

        # External-topic patterns (site talking about others' stuff)
        if any(
            p in path
            for p in [
                "/alternatives",
                "/vs-",
                "/vs/",
                "-vs-",
                "/best-",
                "/top-",
                "/review",
                "/comparison",
                "/compare",
            ]
        ):
            external_topic_count += 1

    total = len(page_urls)
    own_ratio = own_topic_count / total if total > 0 else 0
    ext_ratio = external_topic_count / total if total > 0 else 0

    score = (own_ratio - ext_ratio) * 2.0
    score = max(-1.0, min(1.0, score))

    return PrimacySignal(
        name="self_reference",
        score=score,
        reason=f"{own_topic_count} self-referential URLs (own docs/product) vs "
        f"{external_topic_count} external-topic URLs (reviews, comparisons).",
    )
