"""Content uniqueness analysis — how proprietary/original is a site's content?

The key missing signal that explains the Citation Paradox: generic SaaS marketing
sites score high on all 7 technical pillars (structure, schema, authority, etc.) but
get 0% actual AI citations. Meanwhile, documentation sites with mediocre technical
scores get cited nearly 100% of the time.

The difference is content uniqueness. AI models cite sources that provide information
*not available elsewhere*. Documentation sites are the only source for their API
specs; SaaS marketing sites say the same generic phrases as every competitor.

Three signals measured:
1. Proprietary Data Density — pricing, specs, original research, code examples
2. First-Party Content Markers — author bylines, dates, original images, case studies
3. Generic Phrasing Density (inverted) — marketing boilerplate that signals replaceability

Combined into a single 0-100 ContentUniqueness score weighted:
  proprietary_data=40%, first_party=25%, generic_phrasing=35%
"""

import re
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Generic marketing phrases (60+ patterns)
# High density of these phrases => content is replaceable => AI won't cite it
# ---------------------------------------------------------------------------
GENERIC_MARKETING_PHRASES: list[str] = [
    # Superlatives and buzzwords
    "leading solution",
    "best-in-class",
    "world-class",
    "cutting-edge",
    "state-of-the-art",
    "next-generation",
    "industry-leading",
    "market-leading",
    "top-rated",
    "award-winning",
    "game-changing",
    "revolutionary",
    "groundbreaking",
    "innovative solution",
    "disruptive",
    # Trust / social proof boilerplate
    "trusted by thousands",
    "trusted by millions",
    "trusted by leading",
    "trusted by companies",
    "join thousands of",
    "join millions of",
    "loved by teams",
    "preferred by",
    # Feature fluff
    "seamless integration",
    "seamlessly integrates",
    "powerful features",
    "robust solution",
    "robust platform",
    "scalable platform",
    "scalable solution",
    "flexible solution",
    "comprehensive solution",
    "all-in-one solution",
    "all-in-one platform",
    "one-stop solution",
    "one-stop shop",
    "end-to-end solution",
    "end-to-end platform",
    "turnkey solution",
    "out-of-the-box",
    "plug-and-play",
    # Outcome promises
    "drive results",
    "deliver results",
    "unlock potential",
    "unlock the power",
    "unleash the power",
    "transform your business",
    "grow your business",
    "take your business to the next level",
    "take it to the next level",
    "to the next level",
    "supercharge your",
    "turbocharge your",
    "accelerate your",
    "boost your productivity",
    "maximize your",
    "optimize your workflow",
    "streamline your",
    "empower your team",
    "empower your business",
    "everything you need",
    "all you need",
    # CTA boilerplate
    "schedule a demo",
    "book a demo",
    "request a demo",
    "book a call",
    "get started today",
    "start your free trial",
    "try it free",
    "sign up for free",
    "get started for free",
    "no credit card required",
    "start free trial",
    "see it in action",
    "learn more",
    # Enterprise / trust signals (generic)
    "enterprise-grade",
    "enterprise-ready",
    "mission-critical",
    "future-proof",
    "battle-tested",
    "production-ready",
    "military-grade",
    "bank-level security",
    "soc 2 compliant",
    # Vague differentiation
    "unlike other",
    "better than",
    "the only platform",
    "the only solution",
    "purpose-built",
    "built for teams",
    "designed for teams",
    "built for scale",
    "built for the modern",
    "from day one",
    # Process / methodology fluff
    "data-driven",
    "ai-powered",
    "machine learning powered",
    "cloud-native",
    "developer-friendly",
    "user-friendly",
    "easy to use",
    "intuitive interface",
    "beautiful interface",
    "simple and intuitive",
    "works out of the box",
    # ROI / value
    "reduce costs",
    "save time and money",
    "increase efficiency",
    "improve productivity",
    "roi",
    "return on investment",
    "time to value",
    "total cost of ownership",
]

# Pre-compile generic phrase patterns for efficiency.
# Each pattern is lowered at compile time; matching is done against lowered text.
_GENERIC_PHRASE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b" + re.escape(phrase) + r"\b", re.IGNORECASE)
    for phrase in GENERIC_MARKETING_PHRASES
]

# ---------------------------------------------------------------------------
# Proprietary data detection patterns
# ---------------------------------------------------------------------------

# Pricing patterns — dollar amounts in pricing context
_PRICING_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\$\s?\d[\d,]*(?:\.\d{2})?\s*(?:/\s*(?:mo(?:nth)?|yr|year|user|seat|license|unit))",
        re.IGNORECASE,
    ),
    re.compile(r"starting\s+at\s+\$\s?\d[\d,]*", re.IGNORECASE),
    re.compile(r"(?:per|/)\s*(?:month|year|user|seat|license)\s*", re.IGNORECASE),
    re.compile(r"(?:free|basic|starter|pro|premium|enterprise)\s+plan", re.IGNORECASE),
    re.compile(r"pricing\s+(?:table|tier|plan)", re.IGNORECASE),
    re.compile(r"\bprice[sd]?\s+at\s+\$\s?\d", re.IGNORECASE),
]

# Product-specific specification patterns
_SPEC_PATTERNS: list[re.Pattern[str]] = [
    # Version numbers: v1.2.3, version 2.0, SDK 4.x
    re.compile(r"\bv(?:ersion)?\s?\d+\.\d+(?:\.\d+)?(?:-\w+)?\b", re.IGNORECASE),
    # API parameters: --flag, -f, param_name=value
    re.compile(r"\b(?:--\w[\w-]+|(?:param|option|flag|arg)\s*[:=]\s*\S+)", re.IGNORECASE),
    # Configuration options: key: value in YAML/config style
    re.compile(r"^\s*\w[\w_-]+\s*:\s*(?:true|false|\d+|\"[^\"]+\")", re.IGNORECASE | re.MULTILINE),
    # Feature specs: "supports up to X", "max N", "limit of N"
    re.compile(
        r"(?:supports?\s+up\s+to|max(?:imum)?\s+of?|limit\s+of)\s+[\d,]+",
        re.IGNORECASE,
    ),
    # Rate limits / quotas
    re.compile(
        r"\d[\d,]*\s*(?:requests?|calls?|events?|messages?)\s*/\s*(?:sec|min|hour|day|month)",
        re.IGNORECASE,
    ),
]

# Original research indicators
_RESEARCH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\bour\s+(?:data|research|study|survey|analysis|findings|report)\s+shows?\b", re.IGNORECASE
    ),
    re.compile(
        r"\bwe\s+(?:found|discovered|analyzed|surveyed|studied|measured|tested|examined|observed)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bour\s+survey\s+(?:of|found|shows?|reveals?)\b", re.IGNORECASE),
    re.compile(r"\bbased\s+on\s+(?:\d[\d,]*\s+)?responses?\b", re.IGNORECASE),
    re.compile(
        r"\bour\s+(?:2\d{3}|latest|annual|quarterly)\s+(?:study|survey|report|analysis)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bwe\s+(?:polled|interviewed|benchmarked|sampled)\s+\d", re.IGNORECASE),
    re.compile(r"\bproprietary\s+(?:data|research|methodology|algorithm|model)\b", re.IGNORECASE),
    re.compile(r"\boriginal\s+(?:research|data|findings|analysis)\b", re.IGNORECASE),
    re.compile(
        r"\bour\s+(?:team|engineers?|researchers?|analysts?)\s+(?:found|built|developed|created|designed)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bin-house\s+(?:research|data|testing|benchmark)\b", re.IGNORECASE),
]

# Unique statistics — specific numbers with attribution context
_STAT_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b\d{1,3}(?:\.\d)?%\s+of\s+(?:our|the)\s+(?:customers?|users?|respondents?|companies)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:we|our\s+\w+)\s+(?:reduced|increased|improved|saved|achieved)\s+\w+\s+by\s+\d+",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:n\s*=\s*\d+|sample\s+(?:size|of)\s+\d+)", re.IGNORECASE),
    re.compile(r"\baverage\s+(?:of\s+)?\$?[\d,.]+\s+(?:per|in)\b", re.IGNORECASE),
]

# Code / technical content patterns
_CODE_PATTERNS: list[re.Pattern[str]] = [
    # Fenced code blocks (markdown)
    re.compile(r"```[\s\S]*?```"),
    # Inline code
    re.compile(r"`[^`]{3,80}`"),
    # Common code-like patterns: function calls, imports, variable assignments
    re.compile(r"(?:import|from|require|include)\s+[\w.]+", re.IGNORECASE),
    re.compile(r"\w+\s*\([^)]{0,120}\)\s*(?:=>|->|{)", re.MULTILINE),
    re.compile(r"(?:const|let|var|def|func|fn)\s+\w+", re.IGNORECASE),
]

# API documentation patterns
_API_DOC_PATTERNS: list[re.Pattern[str]] = [
    # HTTP methods + paths
    re.compile(r"\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+/[\w/{}?&=.-]+", re.IGNORECASE),
    # curl examples
    re.compile(r"curl\s+(?:-[A-Za-z]+\s+)*https?://", re.IGNORECASE),
    # Request/response format indicators
    re.compile(r"\b(?:request|response)\s+(?:body|header|param|format)\b", re.IGNORECASE),
    # Status codes
    re.compile(
        r"\b(?:returns?\s+)?(?:HTTP\s+)?\d{3}\s+(?:OK|Created|Accepted|Bad Request|Unauthorized|Forbidden|Not Found|Internal Server Error)\b",
        re.IGNORECASE,
    ),
    # Content-Type headers
    re.compile(
        r"\bContent-Type:\s*application/(?:json|xml|x-www-form-urlencoded)\b", re.IGNORECASE
    ),
    # Authentication patterns
    re.compile(r"\b(?:Authorization|Bearer|API[_-]?key|api[_-]?token|X-API-Key)\b"),
]

# ---------------------------------------------------------------------------
# First-party content markers
# ---------------------------------------------------------------------------

# Author byline patterns
_AUTHOR_BYLINE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bby\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b"),
    re.compile(r"\bwritten\s+by\s+[A-Z][a-z]+", re.IGNORECASE),
    re.compile(r"\bauthor\s*:\s*[A-Z][a-z]+", re.IGNORECASE),
    re.compile(r"\breviewed\s+by\s+[A-Z][a-z]+", re.IGNORECASE),
    re.compile(r"\bedited\s+by\s+[A-Z][a-z]+", re.IGNORECASE),
    re.compile(r"\bcontributed\s+by\s+[A-Z][a-z]+", re.IGNORECASE),
]

# Publication date patterns
_PUB_DATE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:published|posted|written|created)\s+(?:on\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:published|posted|written|created)\s+(?:on\s+)?\d{1,2}[/-]\d{1,2}[/-]\d{2,4}",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:published|posted|written|created)\s+(?:on\s+)?\d{4}-\d{2}-\d{2}",
        re.IGNORECASE,
    ),
    # ISO date at start of line (common in blog metadata)
    re.compile(r"^\d{4}-\d{2}-\d{2}", re.MULTILINE),
]

# Original image indicators (img tags with local/asset paths)
_ORIGINAL_IMAGE_PATTERN: re.Pattern[str] = re.compile(
    r"<img\s[^>]*src=[\"'](?:[^\"']*(?:/assets/|/images/|/img/|/static/|/media/|/uploads/|/content/))[^\"']*[\"']",
    re.IGNORECASE,
)


# Domain-local image indicator (matches img src containing the domain)
def _make_domain_image_pattern(domain: str) -> re.Pattern[str]:
    escaped = re.escape(domain)
    return re.compile(
        rf"<img\s[^>]*src=[\"'][^\"']*{escaped}[^\"']*[\"']",
        re.IGNORECASE,
    )


# Case study / success story patterns
_CASE_STUDY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bcase\s+stud(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\bsuccess\s+stor(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+stor(?:y|ies)\b", re.IGNORECASE),
    re.compile(r"\bcustomer\s+spotlight\b", re.IGNORECASE),
    re.compile(r"\buse\s+case\b", re.IGNORECASE),
    re.compile(r"\btestimonial\b", re.IGNORECASE),
]

# Primary research framing
_PRIMARY_RESEARCH_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bwe\s+tested\b", re.IGNORECASE),
    re.compile(r"\bour\s+team\b", re.IGNORECASE),
    re.compile(r"\bour\s+engineers?\b", re.IGNORECASE),
    re.compile(r"\bour\s+researchers?\b", re.IGNORECASE),
    re.compile(r"\bour\s+analysts?\b", re.IGNORECASE),
    re.compile(r"\bwe\s+built\b", re.IGNORECASE),
    re.compile(r"\bwe\s+developed\b", re.IGNORECASE),
    re.compile(r"\bwe\s+designed\b", re.IGNORECASE),
    re.compile(r"\bwe\s+created\b", re.IGNORECASE),
    re.compile(r"\bour\s+approach\b", re.IGNORECASE),
    re.compile(r"\bour\s+methodology\b", re.IGNORECASE),
    re.compile(r"\bour\s+experience\b", re.IGNORECASE),
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class ContentUniquenessResult:
    """Result of content uniqueness analysis.

    Three sub-scores combine into a single 0-100 score:
    - proprietary_data_score: presence of pricing, specs, research, code, API docs
    - first_party_score: author bylines, dates, original images, case studies
    - generic_phrasing_score: inverted — 100 means NO generic boilerplate detected
    """

    score: float  # 0-100 (0=entirely generic, 100=entirely proprietary)
    proprietary_data_score: float  # 0-100
    first_party_score: float  # 0-100
    generic_phrasing_score: float  # 0-100 (inverted: 100=no generic phrases)
    signals: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "proprietary_data_score": round(self.proprietary_data_score, 1),
            "first_party_score": round(self.first_party_score, 1),
            "generic_phrasing_score": round(self.generic_phrasing_score, 1),
            "signals": self.signals,
        }


# ---------------------------------------------------------------------------
# Helper: split text into paragraphs / sentences
# ---------------------------------------------------------------------------


def _split_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs."""
    parts = re.split(r"\n\s*\n|\r\n\s*\r\n", text)
    return [p.strip() for p in parts if p.strip()]


def _count_sentences(text: str) -> int:
    """Rough sentence count using punctuation boundaries."""
    # Split on sentence-ending punctuation followed by whitespace or end-of-string
    sentences = re.split(r"[.!?]+(?:\s|$)", text)
    return max(1, sum(1 for s in sentences if s.strip()))


# ---------------------------------------------------------------------------
# Signal 1: Proprietary Data Density
# ---------------------------------------------------------------------------


def _score_proprietary_data(
    pages_content: list[str],
) -> tuple[float, dict]:
    """Score 0-100 based on density of proprietary data markers across all pages.

    Proprietary data = information that only THIS site would have:
    pricing, product specs, original research, unique stats, code, API docs.

    Returns (score, signals_dict).
    """
    total_paragraphs = 0
    paragraphs_with_markers = 0

    category_counts: dict[str, int] = {
        "pricing": 0,
        "specs": 0,
        "research": 0,
        "statistics": 0,
        "code": 0,
        "api_docs": 0,
    }

    pattern_groups: list[tuple[str, list[re.Pattern[str]]]] = [
        ("pricing", _PRICING_PATTERNS),
        ("specs", _SPEC_PATTERNS),
        ("research", _RESEARCH_PATTERNS),
        ("statistics", _STAT_PATTERNS),
        ("code", _CODE_PATTERNS),
        ("api_docs", _API_DOC_PATTERNS),
    ]

    for content in pages_content:
        if not content:
            continue

        paragraphs = _split_paragraphs(content)
        total_paragraphs += len(paragraphs)

        for para in paragraphs:
            found_any = False
            for category, patterns in pattern_groups:
                for pattern in patterns:
                    if pattern.search(para):
                        category_counts[category] += 1
                        found_any = True
                        break  # one match per category per paragraph is enough

            if found_any:
                paragraphs_with_markers += 1

    # Score = proportion of paragraphs containing at least one proprietary marker
    if total_paragraphs == 0:
        return 0.0, {"total_paragraphs": 0, "categories": category_counts}

    raw_ratio = paragraphs_with_markers / total_paragraphs
    score = min(100.0, raw_ratio * 100.0)

    signals = {
        "total_paragraphs": total_paragraphs,
        "paragraphs_with_markers": paragraphs_with_markers,
        "marker_density": round(raw_ratio, 3),
        "categories": category_counts,
    }

    return score, signals


# ---------------------------------------------------------------------------
# Signal 2: First-Party Content Markers
# ---------------------------------------------------------------------------

_FIRST_PARTY_MAX_MARKERS = 20  # normalization ceiling


def _score_first_party(
    pages_content: list[str],
    page_urls: list[str],
    domain: str,
) -> tuple[float, dict]:
    """Score 0-100 based on first-party content markers across all pages.

    First-party content = markers showing this content was created by the site's
    own team: author bylines, publication dates, original images, case studies,
    primary research framing.

    Returns (score, signals_dict).
    """
    marker_counts: dict[str, int] = {
        "author_bylines": 0,
        "publication_dates": 0,
        "original_images": 0,
        "case_studies": 0,
        "primary_research": 0,
    }

    domain_img_pattern = _make_domain_image_pattern(domain)

    for content in pages_content:
        if not content:
            continue

        # Author bylines
        for pattern in _AUTHOR_BYLINE_PATTERNS:
            if pattern.search(content):
                marker_counts["author_bylines"] += 1
                break  # one per page

        # Publication dates
        for pattern in _PUB_DATE_PATTERNS:
            if pattern.search(content):
                marker_counts["publication_dates"] += 1
                break

        # Original images (check for local asset paths or domain-matching src)
        if _ORIGINAL_IMAGE_PATTERN.search(content) or domain_img_pattern.search(content):
            marker_counts["original_images"] += 1

        # Case studies / success stories
        for pattern in _CASE_STUDY_PATTERNS:
            if pattern.search(content):
                marker_counts["case_studies"] += 1
                break

        # Primary research framing
        for pattern in _PRIMARY_RESEARCH_PATTERNS:
            if pattern.search(content):
                marker_counts["primary_research"] += 1
                break

    # Also check URLs for case study / research indicators
    for url in page_urls:
        url_lower = url.lower()
        if any(kw in url_lower for kw in ["/case-stud", "/customer-stor", "/success-stor"]):
            marker_counts["case_studies"] += 1
        if any(kw in url_lower for kw in ["/research", "/report", "/whitepaper", "/white-paper"]):
            marker_counts["primary_research"] += 1

    total_markers = sum(marker_counts.values())

    # Normalize: 20+ markers => 100
    score = min(100.0, (total_markers / _FIRST_PARTY_MAX_MARKERS) * 100.0)

    signals = {
        "total_markers": total_markers,
        "markers": marker_counts,
    }

    return score, signals


# ---------------------------------------------------------------------------
# Signal 3: Generic Phrasing Density (inverted)
# ---------------------------------------------------------------------------


def _score_generic_phrasing(
    pages_content: list[str],
) -> tuple[float, dict]:
    """Score 0-100 where 100 = NO generic marketing phrases detected.

    High density of boilerplate phrases signals that the content is replaceable
    and AI won't prefer this site over any competitor.

    Returns (score, signals_dict).
    """
    total_sentences = 0
    total_generic_hits = 0
    top_phrases: dict[str, int] = {}

    for content in pages_content:
        if not content:
            continue

        content_lower = content.lower()
        total_sentences += _count_sentences(content)

        for idx, pattern in enumerate(_GENERIC_PHRASE_PATTERNS):
            matches = pattern.findall(content_lower)
            count = len(matches)
            if count > 0:
                total_generic_hits += count
                phrase = GENERIC_MARKETING_PHRASES[idx]
                top_phrases[phrase] = top_phrases.get(phrase, 0) + count

    if total_sentences == 0:
        return 100.0, {"total_sentences": 0, "generic_hits": 0, "top_phrases": {}}

    # Ratio of generic phrase matches to total sentences
    generic_ratio = total_generic_hits / total_sentences

    # Invert: high ratio => low score; clamp to 0-100
    score = max(0.0, min(100.0, (1.0 - generic_ratio) * 100.0))

    # Sort top phrases by frequency, keep top 10
    sorted_phrases = sorted(top_phrases.items(), key=lambda x: x[1], reverse=True)[:10]

    signals = {
        "total_sentences": total_sentences,
        "generic_hits": total_generic_hits,
        "generic_ratio": round(generic_ratio, 4),
        "top_phrases": dict(sorted_phrases),
    }

    return score, signals


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

# Weights for combining sub-scores
_WEIGHT_PROPRIETARY: float = 0.40
_WEIGHT_FIRST_PARTY: float = 0.25
_WEIGHT_GENERIC: float = 0.35


def analyze_content_uniqueness(
    pages_content: list[str],
    page_urls: list[str],
    domain: str,
) -> ContentUniquenessResult:
    """Analyze how unique/proprietary the site's content is across all crawled pages.

    Args:
        pages_content: List of extracted main_content strings, one per page.
        page_urls: Corresponding list of page URLs.
        domain: The site's domain (e.g., "stripe.com").

    Returns:
        ContentUniquenessResult with overall score and per-signal breakdown.
    """
    # Defensive: filter out None / empty entries, keeping alignment
    clean_content: list[str] = []
    clean_urls: list[str] = []
    for content, url in zip(pages_content, page_urls, strict=False):
        if content and content.strip():
            clean_content.append(content)
            clean_urls.append(url)

    if not clean_content:
        logger.warning(
            "content_uniqueness_no_content",
            domain=domain,
            pages_provided=len(pages_content),
        )
        return ContentUniquenessResult(
            score=0.0,
            proprietary_data_score=0.0,
            first_party_score=0.0,
            generic_phrasing_score=0.0,
            signals={"error": "no_content", "pages_provided": len(pages_content)},
        )

    # Score each signal
    proprietary_score, proprietary_signals = _score_proprietary_data(clean_content)
    first_party_score, first_party_signals = _score_first_party(clean_content, clean_urls, domain)
    generic_score, generic_signals = _score_generic_phrasing(clean_content)

    # Weighted combination
    combined = (
        proprietary_score * _WEIGHT_PROPRIETARY
        + first_party_score * _WEIGHT_FIRST_PARTY
        + generic_score * _WEIGHT_GENERIC
    )
    combined = max(0.0, min(100.0, combined))

    result = ContentUniquenessResult(
        score=combined,
        proprietary_data_score=proprietary_score,
        first_party_score=first_party_score,
        generic_phrasing_score=generic_score,
        signals={
            "pages_analyzed": len(clean_content),
            "proprietary_data": proprietary_signals,
            "first_party": first_party_signals,
            "generic_phrasing": generic_signals,
        },
    )

    logger.info(
        "content_uniqueness_analyzed",
        domain=domain,
        pages_analyzed=len(clean_content),
        score=round(combined, 1),
        proprietary_data=round(proprietary_score, 1),
        first_party=round(first_party_score, 1),
        generic_phrasing=round(generic_score, 1),
    )

    return result
