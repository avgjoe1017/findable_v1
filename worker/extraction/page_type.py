"""Page type detection for context-aware scoring and reporting.

Detects the type of page (homepage, blog, product, etc.) to provide
context-appropriate expectations and recommendations.
"""

import re
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlparse

from bs4 import BeautifulSoup


class PageType(StrEnum):
    """Types of web pages with different scoring expectations."""

    HOMEPAGE = "homepage"
    ABOUT = "about"
    BLOG_POST = "blog_post"
    BLOG_INDEX = "blog_index"
    PRODUCT = "product"
    SERVICE = "service"
    PRICING = "pricing"
    CONTACT = "contact"
    FAQ = "faq"
    DOCUMENTATION = "documentation"
    LEGAL = "legal"  # Privacy, terms, etc.
    UNKNOWN = "unknown"


@dataclass
class PageTypeResult:
    """Result of page type detection."""

    page_type: PageType
    confidence: float  # 0-1
    signals: list[str]  # What indicated this type

    # Context notes for the report
    scoring_context: str  # E.g., "Homepages typically score lower on Authority"
    expected_gaps: list[str]  # E.g., ["No author byline expected on homepage"]

    def to_dict(self) -> dict:
        return {
            "page_type": self.page_type.value,
            "confidence": round(self.confidence, 2),
            "signals": self.signals,
            "scoring_context": self.scoring_context,
            "expected_gaps": self.expected_gaps,
        }


# URL patterns for page type detection
URL_PATTERNS = {
    PageType.ABOUT: [r"/about", r"/company", r"/team", r"/who-we-are"],
    PageType.BLOG_POST: [r"/blog/[^/]+", r"/posts?/[^/]+", r"/articles?/[^/]+", r"/news/[^/]+"],
    PageType.BLOG_INDEX: [r"/blog/?$", r"/posts/?$", r"/articles/?$", r"/news/?$"],
    PageType.PRODUCT: [r"/products?/", r"/solutions?/", r"/features?/"],
    PageType.SERVICE: [r"/services?/"],
    PageType.PRICING: [r"/pricing", r"/plans?"],
    PageType.CONTACT: [r"/contact", r"/support", r"/help"],
    PageType.FAQ: [r"/faq", r"/frequently-asked", r"/questions"],
    PageType.DOCUMENTATION: [r"/docs?/", r"/documentation", r"/guide", r"/tutorial"],
    PageType.LEGAL: [r"/privacy", r"/terms", r"/legal", r"/cookie"],
}

# Page type context and expectations
PAGE_TYPE_CONTEXT = {
    PageType.HOMEPAGE: {
        "scoring_context": (
            "Homepages typically score lower on Authority signals (no author byline) "
            "and may have less structured content. Full site audit recommended."
        ),
        "expected_gaps": [
            "No author attribution expected",
            "Less detailed content than interior pages",
            "May lack FAQ sections",
        ],
    },
    PageType.ABOUT: {
        "scoring_context": (
            "About pages should have strong company identity signals. "
            "Team/founder information improves Authority score."
        ),
        "expected_gaps": [
            "May lack technical content",
            "Focus on narrative over structured data",
        ],
    },
    PageType.BLOG_POST: {
        "scoring_context": (
            "Blog posts are ideal for Authority signals. "
            "Author bylines, dates, and citations significantly impact score."
        ),
        "expected_gaps": [],  # Blog posts should have everything
    },
    PageType.BLOG_INDEX: {
        "scoring_context": (
            "Blog index pages aggregate content. Individual post quality matters more."
        ),
        "expected_gaps": [
            "No single author expected",
            "Content may be summaries only",
        ],
    },
    PageType.PRODUCT: {
        "scoring_context": (
            "Product pages benefit from Product schema markup and detailed feature lists."
        ),
        "expected_gaps": [
            "Author attribution not typical",
            "Focus on features over narrative",
        ],
    },
    PageType.SERVICE: {
        "scoring_context": (
            "Service pages should clearly explain offerings with structured information."
        ),
        "expected_gaps": [
            "Author attribution not typical",
        ],
    },
    PageType.PRICING: {
        "scoring_context": (
            "Pricing pages are high-value for AI queries about cost. Clear structure is key."
        ),
        "expected_gaps": [
            "Author attribution not expected",
            "Limited narrative content",
        ],
    },
    PageType.CONTACT: {
        "scoring_context": (
            "Contact pages should have LocalBusiness schema and clear contact information."
        ),
        "expected_gaps": [
            "Minimal content expected",
            "Focus on structured data over narrative",
        ],
    },
    PageType.FAQ: {
        "scoring_context": (
            "FAQ pages are ideal for AI extraction. FAQPage schema provides significant boost."
        ),
        "expected_gaps": [],  # FAQs should be well-structured
    },
    PageType.DOCUMENTATION: {
        "scoring_context": (
            "Documentation pages benefit from clear headings, code examples, and HowTo schema."
        ),
        "expected_gaps": [
            "Author byline may not be present",
            "Technical focus over authority signals",
        ],
    },
    PageType.LEGAL: {
        "scoring_context": (
            "Legal pages are not typically indexed by AI. Low priority for optimization."
        ),
        "expected_gaps": [
            "Not designed for AI extraction",
            "Focus on compliance, not engagement",
        ],
    },
    PageType.UNKNOWN: {
        "scoring_context": (
            "Page type unclear. Review content structure and add appropriate signals."
        ),
        "expected_gaps": [],
    },
}


class PageTypeDetector:
    """Detects the type of a web page."""

    def detect(self, url: str, html: str | None = None) -> PageTypeResult:
        """
        Detect the type of a page from URL and optionally HTML content.

        Args:
            url: Page URL
            html: Optional HTML content for deeper analysis

        Returns:
            PageTypeResult with type, confidence, and context
        """
        signals = []
        page_type = PageType.UNKNOWN
        confidence = 0.0

        parsed = urlparse(url)
        path = parsed.path.lower()

        # Check if homepage
        if path in ("", "/", "/index.html", "/index.php"):
            page_type = PageType.HOMEPAGE
            confidence = 0.9
            signals.append("Root URL path")
        else:
            # Check URL patterns
            for ptype, patterns in URL_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, path, re.IGNORECASE):
                        page_type = ptype
                        confidence = 0.7
                        signals.append(f"URL matches {pattern}")
                        break
                if page_type != PageType.UNKNOWN:
                    break

        # Boost confidence with HTML analysis
        if html and page_type == PageType.UNKNOWN:
            html_type, html_signals = self._analyze_html(html)
            if html_type != PageType.UNKNOWN:
                page_type = html_type
                confidence = 0.6
                signals.extend(html_signals)
        elif html:
            # Verify URL-based detection with HTML
            html_type, html_signals = self._analyze_html(html)
            if html_type == page_type:
                confidence = min(0.95, confidence + 0.2)
                signals.extend(html_signals)

        # Get context for this page type
        context = PAGE_TYPE_CONTEXT.get(page_type, PAGE_TYPE_CONTEXT[PageType.UNKNOWN])

        return PageTypeResult(
            page_type=page_type,
            confidence=confidence,
            signals=signals[:5],  # Limit signals
            scoring_context=context["scoring_context"],  # type: ignore[arg-type]
            expected_gaps=context["expected_gaps"],  # type: ignore[arg-type]
        )

    def _analyze_html(self, html: str) -> tuple[PageType, list[str]]:
        """Analyze HTML content to detect page type."""
        signals = []
        soup = BeautifulSoup(html, "html.parser")

        # Check for FAQ indicators
        faq_indicators = soup.find_all(class_=re.compile(r"faq|question|accordion", re.I))
        if len(faq_indicators) >= 3:
            signals.append(f"Found {len(faq_indicators)} FAQ-like elements")
            return PageType.FAQ, signals

        # Check for blog post indicators
        article = soup.find("article")
        author = soup.find(class_=re.compile(r"author|byline", re.I))
        published_date = soup.find(attrs={"itemprop": "datePublished"}) or soup.find(
            class_=re.compile(r"date|published", re.I)
        )
        if article and (author or published_date):
            signals.append("Found article element with author/date")
            return PageType.BLOG_POST, signals

        # Check for product indicators
        price = soup.find(class_=re.compile(r"price", re.I)) or soup.find(
            attrs={"itemprop": "price"}
        )
        add_to_cart = soup.find(attrs={"class": re.compile(r"cart|buy|purchase", re.I)})
        if price and add_to_cart:
            signals.append("Found price and cart elements")
            return PageType.PRODUCT, signals

        # Check for pricing page
        pricing_tables = soup.find_all(class_=re.compile(r"pricing|plan", re.I))
        if len(pricing_tables) >= 2:
            signals.append("Found pricing table elements")
            return PageType.PRICING, signals

        # Check for documentation
        code_blocks = soup.find_all(["pre", "code"])
        if len(code_blocks) >= 3:
            signals.append(f"Found {len(code_blocks)} code blocks")
            return PageType.DOCUMENTATION, signals

        return PageType.UNKNOWN, signals


def detect_page_type(url: str, html: str | None = None) -> PageTypeResult:
    """
    Convenience function to detect page type.

    Args:
        url: Page URL
        html: Optional HTML content

    Returns:
        PageTypeResult with type and context
    """
    detector = PageTypeDetector()
    return detector.detect(url, html)


def get_page_type_context(page_type: PageType) -> dict:
    """Get the scoring context for a page type."""
    return PAGE_TYPE_CONTEXT.get(page_type, PAGE_TYPE_CONTEXT[PageType.UNKNOWN])
