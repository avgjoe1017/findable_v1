"""Site-level content type classification.

Aggregates per-page PageType results and domain signals into a site-level
content type classification. This is used to predict citation likelihood
and provide context-aware recommendations.

Key insight from calibration analysis (Feb 2026):
- Documentation sites get cited ~100% of the time
- Reference/developer tool sites get cited ~80-95%
- SaaS marketing sites get cited 0-60%
- News/media sites get cited 0-20%
- UGC platforms get cited 10-30%

The site type is the strongest single predictor of whether AI will cite
a URL (stronger than any of the 7 pillar scores).
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlparse

import structlog

from worker.extraction.page_type import PageType, PageTypeResult, detect_page_type

logger = structlog.get_logger(__name__)


class SiteType(StrEnum):
    """Site-level content type classifications."""

    DOCUMENTATION = "documentation"  # docs.python.org, tailwindcss.com
    REFERENCE = "reference"  # stackoverflow.com, httpbin.org
    DEVELOPER_TOOLS = "developer_tools"  # github.com, vercel.com
    SAAS_MARKETING = "saas_marketing"  # datadog.com, lemlist.com
    NEWS_MEDIA = "news_media"  # bbc.com, wsj.com
    UGC_PLATFORM = "ugc_platform"  # reddit.com, yelp.com, g2.com
    ECOMMERCE = "ecommerce"  # etsy.com, shopify stores
    BLOG = "blog"  # Personal/company blogs
    MIXED = "mixed"  # No dominant type


# Citation baselines derived from calibration corpus (Feb 2026)
# These are expected citation rates for each site type
CITATION_BASELINES = {
    SiteType.DOCUMENTATION: {
        "citation_rate": 0.95,
        "range": (0.85, 1.0),
        "description": "Documentation sites are nearly always cited because they are THE canonical source.",
    },
    SiteType.REFERENCE: {
        "citation_rate": 0.85,
        "range": (0.75, 0.95),
        "description": "Reference sites provide unique answers not available elsewhere.",
    },
    SiteType.DEVELOPER_TOOLS: {
        "citation_rate": 0.80,
        "range": (0.65, 0.95),
        "description": "Developer tools with unique technical content get cited frequently.",
    },
    SiteType.SAAS_MARKETING: {
        "citation_rate": 0.45,
        "range": (0.0, 0.70),
        "description": "SaaS marketing sites compete with many similar sources. "
        "Citation depends on content uniqueness.",
    },
    SiteType.NEWS_MEDIA: {
        "citation_rate": 0.10,
        "range": (0.0, 0.25),
        "description": "AI models are trained on news content and rarely cite news URLs. "
        "They cite original sources instead.",
    },
    SiteType.UGC_PLATFORM: {
        "citation_rate": 0.20,
        "range": (0.05, 0.35),
        "description": "UGC platforms get cited for specific threads/reviews, not broadly.",
    },
    SiteType.ECOMMERCE: {
        "citation_rate": 0.35,
        "range": (0.15, 0.55),
        "description": "E-commerce sites sometimes get cited for product details and pricing.",
    },
    SiteType.BLOG: {
        "citation_rate": 0.50,
        "range": (0.20, 0.80),
        "description": "Blog citation rates vary widely based on content uniqueness and expertise.",
    },
    SiteType.MIXED: {
        "citation_rate": 0.50,
        "range": (0.20, 0.80),
        "description": "Mixed content type. Citation rate depends on content quality and uniqueness.",
    },
}

# Per-question-category citation rates by site type (from calibration analysis)
CATEGORY_CITATION_RATES = {
    SiteType.DOCUMENTATION: {
        "identity": 0.80,
        "differentiation": 0.95,
        "expertise": 0.95,
        "comparison": 0.70,
        "offerings": 0.90,
    },
    SiteType.REFERENCE: {
        "identity": 0.75,
        "differentiation": 0.90,
        "expertise": 0.90,
        "comparison": 0.65,
        "offerings": 0.80,
    },
    SiteType.DEVELOPER_TOOLS: {
        "identity": 0.70,
        "differentiation": 0.85,
        "expertise": 0.85,
        "comparison": 0.60,
        "offerings": 0.75,
    },
    SiteType.SAAS_MARKETING: {
        "identity": 0.30,
        "differentiation": 0.50,
        "expertise": 0.55,
        "comparison": 0.25,
        "offerings": 0.45,
    },
    SiteType.NEWS_MEDIA: {
        "identity": 0.05,
        "differentiation": 0.10,
        "expertise": 0.15,
        "comparison": 0.05,
        "offerings": 0.05,
    },
    SiteType.UGC_PLATFORM: {
        "identity": 0.10,
        "differentiation": 0.15,
        "expertise": 0.25,
        "comparison": 0.10,
        "offerings": 0.15,
    },
    SiteType.ECOMMERCE: {
        "identity": 0.20,
        "differentiation": 0.30,
        "expertise": 0.35,
        "comparison": 0.20,
        "offerings": 0.40,
    },
    SiteType.BLOG: {
        "identity": 0.40,
        "differentiation": 0.55,
        "expertise": 0.60,
        "comparison": 0.35,
        "offerings": 0.45,
    },
    SiteType.MIXED: {
        "identity": 0.40,
        "differentiation": 0.50,
        "expertise": 0.55,
        "comparison": 0.35,
        "offerings": 0.45,
    },
}

# Domain patterns that strongly indicate site type
DOMAIN_PATTERNS = {
    SiteType.DOCUMENTATION: [
        r"^docs\.",
        r"\.readthedocs\.",
        r"^developers?\.",  # developer. and developers.
        r"^devdocs\.",
        r"^api\.",
        r"^reference\.",
        r"^wiki\.",
    ],
    SiteType.REFERENCE: [
        r"stackoverflow\.com",
        r"stackexchange\.com",
        r"wikipedia\.org",
        r"mdn\.mozilla\.org",
        r"w3schools\.com",
        r"^schema\.org$",
        r"httpbin\.org",
        r"^w3\.org$",
        r"^ietf\.org$",
        r"^docs\.python\.org$",
    ],
    SiteType.UGC_PLATFORM: [
        r"reddit\.com",
        r"quora\.com",
        r"yelp\.com",
        r"trustpilot\.com",
        r"g2\.com",
        r"capterra\.com",
        r"producthunt\.com",
    ],
    SiteType.NEWS_MEDIA: [
        r"bbc\.com",
        r"bbc\.co\.uk",
        r"cnn\.com",
        r"wsj\.com",
        r"nytimes\.com",
        r"reuters\.com",
        r"theguardian\.com",
        r"techcrunch\.com",
        r"searchengineland\.com",
        r"searchenginejournal\.com",
        r"theverge\.com",
        r"arstechnica\.com",
        r"wired\.com",
    ],
    SiteType.ECOMMERCE: [
        r"etsy\.com",
        r"amazon\.com",
        r"ebay\.com",
        r"\.myshopify\.com",
    ],
    SiteType.SAAS_MARKETING: [
        r"hubspot\.com",
        r"salesforce\.com",
        r"datadog\.com",
        r"lemlist\.com",
        r"hunter\.io",
        r"buffer\.com",
        r"mailchimp\.com",
        r"intercom\.com",
        r"zendesk\.com",
    ],
    SiteType.DEVELOPER_TOOLS: [
        r"github\.com",
        r"gitlab\.com",
        r"vercel\.com",
        r"netlify\.com",
        r"heroku\.com",
        r"npmjs\.com",
        r"pypi\.org",
    ],
}


@dataclass
class SiteTypeResult:
    """Result of site-level content type classification."""

    site_type: SiteType
    confidence: float  # 0-1
    signals: list[str]  # What indicated this classification

    # Page type distribution
    page_type_counts: dict[str, int] = field(default_factory=dict)
    total_pages_analyzed: int = 0

    # Citation context
    citation_baseline: float = 0.5
    citation_range: tuple[float, float] = (0.2, 0.8)
    citation_description: str = ""

    # Per-category predictions
    category_predictions: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "site_type": self.site_type.value,
            "confidence": round(self.confidence, 2),
            "signals": self.signals[:5],
            "page_type_counts": self.page_type_counts,
            "total_pages_analyzed": self.total_pages_analyzed,
            "citation_baseline": round(self.citation_baseline, 2),
            "citation_range": [round(r, 2) for r in self.citation_range],
            "citation_description": self.citation_description,
            "category_predictions": {k: round(v, 2) for k, v in self.category_predictions.items()},
        }


class SiteTypeDetector:
    """Classifies a site's content type from crawled pages and domain signals."""

    def detect(
        self,
        domain: str,
        page_urls: list[str],
        page_htmls: list[str | None] | None = None,
        page_type_results: list[PageTypeResult] | None = None,
    ) -> SiteTypeResult:
        """
        Classify a site's content type.

        Args:
            domain: Site domain (e.g., "docs.python.org")
            page_urls: List of crawled page URLs
            page_htmls: Optional list of HTML content per page
            page_type_results: Optional pre-computed PageTypeResults

        Returns:
            SiteTypeResult with classification and citation context
        """
        signals: list[str] = []
        scores: dict[SiteType, float] = dict.fromkeys(SiteType, 0.0)

        # 1. Check domain patterns (strongest signal)
        domain_type = self._check_domain_patterns(domain)
        if domain_type:
            scores[domain_type] += 3.0
            signals.append(f"Domain pattern matches {domain_type.value}")

        # 2. Analyze page types
        if page_type_results:
            pt_results = page_type_results
        else:
            pt_results = [
                detect_page_type(url, html)
                for url, html in zip(
                    page_urls,
                    page_htmls or [None] * len(page_urls),
                    strict=False,
                )
            ]

        page_type_counts = Counter(r.page_type.value for r in pt_results)
        total_pages = len(pt_results)

        if total_pages > 0:
            page_scores = self._score_from_page_types(page_type_counts, total_pages)
            for st, score in page_scores.items():
                scores[st] += score

            # Add signal about dominant page type
            most_common = page_type_counts.most_common(1)
            if most_common:
                dominant_type, dominant_count = most_common[0]
                pct = dominant_count / total_pages * 100
                signals.append(
                    f"{pct:.0f}% pages are {dominant_type} ({dominant_count}/{total_pages})"
                )

        # 3. Check URL patterns
        url_scores = self._score_from_urls(page_urls)
        for st, score in url_scores.items():
            scores[st] += score
            if score > 0.5:
                signals.append(f"URL patterns suggest {st.value}")

        # 4. Determine winner
        best_type = max(scores, key=scores.get)  # type: ignore[arg-type]
        best_score = scores[best_type]

        # Calculate confidence
        total_score = sum(s for s in scores.values() if s > 0)
        if total_score > 0 and best_score > 0:
            confidence = min(0.95, best_score / total_score)
        else:
            confidence = 0.3

        # If nothing scored well, it's mixed
        if best_score < 0.5:
            best_type = SiteType.MIXED
            confidence = 0.4
            signals.append("No dominant content type detected")

        # Get citation context
        baseline = CITATION_BASELINES[best_type]
        category_preds = CATEGORY_CITATION_RATES.get(best_type, {})

        result = SiteTypeResult(
            site_type=best_type,
            confidence=confidence,
            signals=signals,
            page_type_counts=dict(page_type_counts),
            total_pages_analyzed=total_pages,
            citation_baseline=baseline["citation_rate"],
            citation_range=baseline["range"],
            citation_description=baseline["description"],
            category_predictions=category_preds,
        )

        logger.info(
            "site_type_detected",
            domain=domain,
            site_type=best_type.value,
            confidence=confidence,
            page_types=dict(page_type_counts),
        )

        return result

    def _check_domain_patterns(self, domain: str) -> SiteType | None:
        """Check if domain matches any known pattern."""
        for site_type, patterns in DOMAIN_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, domain, re.IGNORECASE):
                    return site_type
        return None

    def _score_from_page_types(self, counts: Counter, total: int) -> dict[SiteType, float]:
        """Score site types based on page type distribution."""
        scores: dict[SiteType, float] = dict.fromkeys(SiteType, 0.0)

        doc_pages = counts.get(PageType.DOCUMENTATION, 0)
        blog_pages = counts.get(PageType.BLOG_POST, 0) + counts.get(PageType.BLOG_INDEX, 0)
        product_pages = counts.get(PageType.PRODUCT, 0) + counts.get(PageType.SERVICE, 0)
        faq_pages = counts.get(PageType.FAQ, 0)
        pricing_pages = counts.get(PageType.PRICING, 0)

        if total == 0:
            return scores

        # Documentation: majority docs pages
        if doc_pages / total >= 0.5:
            scores[SiteType.DOCUMENTATION] += 2.0
        elif doc_pages / total >= 0.3:
            scores[SiteType.DOCUMENTATION] += 1.0

        # Blog: majority blog pages
        if blog_pages / total >= 0.5:
            scores[SiteType.BLOG] += 2.0
        elif blog_pages / total >= 0.3:
            scores[SiteType.BLOG] += 1.0

        # SaaS Marketing: mix of product, pricing, about, homepage
        if product_pages > 0 and pricing_pages > 0:
            scores[SiteType.SAAS_MARKETING] += 1.5
        elif product_pages > 0 or (pricing_pages > 0 and faq_pages > 0):
            scores[SiteType.SAAS_MARKETING] += 1.0

        # E-commerce: many product pages, no docs
        if product_pages / total >= 0.4 and doc_pages == 0:
            scores[SiteType.ECOMMERCE] += 1.5

        return scores

    def _score_from_urls(self, urls: list[str]) -> dict[SiteType, float]:
        """Score site types based on URL path patterns."""
        scores: dict[SiteType, float] = dict.fromkeys(SiteType, 0.0)

        doc_urls = 0
        api_urls = 0
        blog_urls = 0
        product_urls = 0
        news_urls = 0

        for url in urls:
            path = urlparse(url).path.lower()

            if re.search(r"/docs?/|/guide/|/tutorial/|/reference/|/api/", path):
                doc_urls += 1
            if re.search(r"/api/|/sdk/|/cli/", path):
                api_urls += 1
            if re.search(r"/blog/|/posts?/|/articles?/", path):
                blog_urls += 1
            if re.search(r"/products?/|/solutions?/|/features?/", path):
                product_urls += 1
            if re.search(r"/news/|/press/|/media/", path):
                news_urls += 1

        total = len(urls) if urls else 1

        if doc_urls / total >= 0.3:
            scores[SiteType.DOCUMENTATION] += 1.0
        if api_urls / total >= 0.2:
            scores[SiteType.DEVELOPER_TOOLS] += 0.5
        if blog_urls / total >= 0.3:
            scores[SiteType.BLOG] += 0.5
        if product_urls / total >= 0.2:
            scores[SiteType.SAAS_MARKETING] += 0.5
        if news_urls / total >= 0.3:
            scores[SiteType.NEWS_MEDIA] += 0.5

        return scores


def detect_site_type(
    domain: str,
    page_urls: list[str],
    page_htmls: list[str | None] | None = None,
    page_type_results: list[PageTypeResult] | None = None,
) -> SiteTypeResult:
    """
    Convenience function to detect site content type.

    Args:
        domain: Site domain
        page_urls: List of crawled page URLs
        page_htmls: Optional HTML content per page
        page_type_results: Optional pre-computed page type results

    Returns:
        SiteTypeResult with classification and citation context
    """
    detector = SiteTypeDetector()
    return detector.detect(domain, page_urls, page_htmls, page_type_results)
