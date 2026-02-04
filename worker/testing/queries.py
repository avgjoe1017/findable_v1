"""Test query bank for real-world validation.

Defines queries across categories:
- Informational: "What is X" style queries
- Tool Comparison: "Best X tools" style queries
- How-To: "How to X" style queries
- Technical: Technical implementation queries
- Brand: Brand-specific queries
"""

from dataclasses import dataclass, field
from enum import Enum


class QueryCategory(str, Enum):
    """Categories for test queries."""

    INFORMATIONAL = "informational"  # What is X
    TOOL_COMPARISON = "tool_comparison"  # Best X tools
    HOW_TO = "how_to"  # How to X
    TECHNICAL = "technical"  # Technical implementation
    BRAND = "brand"  # Brand-specific queries


@dataclass
class TestQuery:
    """A query for testing AI citation behavior."""

    query: str
    category: QueryCategory
    expected_sources: list[str] = field(default_factory=list)  # Domains expected to be cited
    difficulty: str = "medium"  # "easy", "medium", "hard" for AI to answer
    notes: str = ""

    def __hash__(self):
        return hash(self.query)

    def __eq__(self, other):
        if isinstance(other, TestQuery):
            return self.query == other.query
        return False


# ============================================================================
# Informational Queries - "What is X" style
# ============================================================================

INFORMATIONAL_QUERIES = [
    # GEO/AEO Specific
    TestQuery(
        query="what is generative engine optimization",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["amsive.com", "searchengineland.com"],
        difficulty="medium",
        notes="Core GEO concept - should cite authoritative sources",
    ),
    TestQuery(
        query="what is AI search optimization",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["searchengineland.com", "searchenginejournal.com"],
        difficulty="medium",
        notes="Broader AI SEO concept",
    ),
    TestQuery(
        query="what is answer engine optimization",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=[],
        difficulty="medium",
        notes="AEO term - may cite various SEO sources",
    ),
    TestQuery(
        query="how do AI search engines find content",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["openai.com", "anthropic.com"],
        difficulty="hard",
        notes="Technical AI retrieval question",
    ),
    TestQuery(
        query="what is AI sourceability",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=[],
        difficulty="hard",
        notes="Emerging term - may not have established sources",
    ),
    # Traditional SEO
    TestQuery(
        query="what is domain authority",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["moz.com"],
        difficulty="easy",
        notes="Moz invented DA - should always cite Moz",
    ),
    TestQuery(
        query="what is E-E-A-T in SEO",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["developers.google.com", "searchengineland.com"],
        difficulty="easy",
        notes="Google concept - should cite Google or SEO news",
    ),
    TestQuery(
        query="what are Core Web Vitals",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["developers.google.com", "web.dev"],
        difficulty="easy",
        notes="Google metric - should cite Google documentation",
    ),
    # Schema & Structured Data
    TestQuery(
        query="what is schema markup",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["schema.org", "developers.google.com"],
        difficulty="easy",
        notes="Should cite schema.org as authoritative source",
    ),
    TestQuery(
        query="what is JSON-LD",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["schema.org", "json-ld.org", "developer.mozilla.org"],
        difficulty="medium",
        notes="Technical standard - may cite various sources",
    ),
    # Marketing
    TestQuery(
        query="what is inbound marketing",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["hubspot.com"],
        difficulty="easy",
        notes="HubSpot coined the term - should cite HubSpot",
    ),
    TestQuery(
        query="what is content marketing",
        category=QueryCategory.INFORMATIONAL,
        expected_sources=["hubspot.com", "contentmarketinginstitute.com"],
        difficulty="easy",
        notes="Established marketing concept",
    ),
]


# ============================================================================
# Tool Comparison Queries - "Best X tools" style
# ============================================================================

TOOL_COMPARISON_QUERIES = [
    # GEO/AI Tools
    TestQuery(
        query="best GEO optimization tools",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["otterly.ai", "rankscale.ai"],
        difficulty="hard",
        notes="Emerging category - few established sources",
    ),
    TestQuery(
        query="AI SEO monitoring tools",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["otterly.ai"],
        difficulty="hard",
        notes="Niche category",
    ),
    TestQuery(
        query="how to check if AI cites my website",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["otterly.ai"],
        difficulty="hard",
        notes="Very specific use case",
    ),
    TestQuery(
        query="tools to track AI search visibility",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=[],
        difficulty="hard",
        notes="Emerging category",
    ),
    # Traditional SEO Tools
    TestQuery(
        query="best SEO tools 2024",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["ahrefs.com", "moz.com", "semrush.com"],
        difficulty="easy",
        notes="Well-established category with known players",
    ),
    TestQuery(
        query="best keyword research tools",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["ahrefs.com", "moz.com", "semrush.com"],
        difficulty="easy",
        notes="Should cite major SEO tool providers",
    ),
    TestQuery(
        query="best backlink analysis tools",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["ahrefs.com", "moz.com"],
        difficulty="easy",
        notes="Ahrefs and Moz are known for backlink analysis",
    ),
    # Marketing Tools
    TestQuery(
        query="best CRM software",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["hubspot.com", "salesforce.com"],
        difficulty="easy",
        notes="Established category",
    ),
    TestQuery(
        query="best email marketing tools",
        category=QueryCategory.TOOL_COMPARISON,
        expected_sources=["hubspot.com", "mailchimp.com"],
        difficulty="easy",
        notes="Well-known marketing category",
    ),
]


# ============================================================================
# How-To Queries - "How to X" style
# ============================================================================

HOW_TO_QUERIES = [
    # GEO/AI Optimization
    TestQuery(
        query="how to optimize website for ChatGPT",
        category=QueryCategory.HOW_TO,
        expected_sources=["searchengineland.com"],
        difficulty="hard",
        notes="Emerging optimization practice",
    ),
    TestQuery(
        query="how to get cited by Perplexity",
        category=QueryCategory.HOW_TO,
        expected_sources=[],
        difficulty="hard",
        notes="Very specific - few authoritative sources",
    ),
    TestQuery(
        query="how to improve AI visibility",
        category=QueryCategory.HOW_TO,
        expected_sources=["searchengineland.com", "searchenginejournal.com"],
        difficulty="hard",
        notes="Emerging topic",
    ),
    TestQuery(
        query="how to make website findable by AI",
        category=QueryCategory.HOW_TO,
        expected_sources=[],
        difficulty="hard",
        notes="Key Findable use case query",
    ),
    # Traditional SEO
    TestQuery(
        query="how to do keyword research",
        category=QueryCategory.HOW_TO,
        expected_sources=["moz.com", "ahrefs.com", "backlinko.com"],
        difficulty="easy",
        notes="Well-documented SEO practice",
    ),
    TestQuery(
        query="how to build backlinks",
        category=QueryCategory.HOW_TO,
        expected_sources=["moz.com", "ahrefs.com", "backlinko.com"],
        difficulty="easy",
        notes="Common SEO question",
    ),
    TestQuery(
        query="how to improve page speed",
        category=QueryCategory.HOW_TO,
        expected_sources=["developers.google.com", "web.dev"],
        difficulty="easy",
        notes="Should cite Google documentation",
    ),
    TestQuery(
        query="how to create a sitemap",
        category=QueryCategory.HOW_TO,
        expected_sources=["developers.google.com", "sitemaps.org"],
        difficulty="easy",
        notes="Technical SEO question",
    ),
    # Content Creation
    TestQuery(
        query="how to write content for AI search",
        category=QueryCategory.HOW_TO,
        expected_sources=["searchengineland.com"],
        difficulty="hard",
        notes="Emerging content strategy",
    ),
    TestQuery(
        query="how to structure content for AI extraction",
        category=QueryCategory.HOW_TO,
        expected_sources=[],
        difficulty="hard",
        notes="Technical content question",
    ),
]


# ============================================================================
# Technical Queries - Implementation-focused
# ============================================================================

TECHNICAL_QUERIES = [
    # Schema/Structured Data
    TestQuery(
        query="what schema markup helps AI understand content",
        category=QueryCategory.TECHNICAL,
        expected_sources=["schema.org", "developers.google.com"],
        difficulty="medium",
        notes="Schema implementation question",
    ),
    TestQuery(
        query="how to add JSON-LD to website",
        category=QueryCategory.TECHNICAL,
        expected_sources=["schema.org", "developers.google.com"],
        difficulty="easy",
        notes="Technical implementation",
    ),
    TestQuery(
        query="Organization schema markup example",
        category=QueryCategory.TECHNICAL,
        expected_sources=["schema.org"],
        difficulty="easy",
        notes="Specific schema type",
    ),
    TestQuery(
        query="FAQ schema markup for SEO",
        category=QueryCategory.TECHNICAL,
        expected_sources=["schema.org", "developers.google.com"],
        difficulty="easy",
        notes="Popular schema type",
    ),
    # Robots & Crawling
    TestQuery(
        query="robots.txt for AI crawlers",
        category=QueryCategory.TECHNICAL,
        expected_sources=["developers.google.com"],
        difficulty="medium",
        notes="Emerging technical topic",
    ),
    TestQuery(
        query="how to block GPTBot in robots.txt",
        category=QueryCategory.TECHNICAL,
        expected_sources=["openai.com"],
        difficulty="medium",
        notes="OpenAI publishes GPTBot documentation",
    ),
    TestQuery(
        query="what is llms.txt",
        category=QueryCategory.TECHNICAL,
        expected_sources=[],
        difficulty="hard",
        notes="Very new standard - may not have citations",
    ),
    # Web Development
    TestQuery(
        query="how to implement lazy loading images",
        category=QueryCategory.TECHNICAL,
        expected_sources=["developer.mozilla.org", "web.dev"],
        difficulty="easy",
        notes="Standard web dev question",
    ),
    TestQuery(
        query="meta tags for SEO",
        category=QueryCategory.TECHNICAL,
        expected_sources=["developer.mozilla.org", "moz.com"],
        difficulty="easy",
        notes="Common technical SEO question",
    ),
]


# ============================================================================
# Brand Queries - Brand-specific
# ============================================================================

BRAND_QUERIES = [
    # AI Companies
    TestQuery(
        query="what is ChatGPT",
        category=QueryCategory.BRAND,
        expected_sources=["openai.com"],
        difficulty="easy",
        notes="Should cite OpenAI",
    ),
    TestQuery(
        query="what is Claude AI",
        category=QueryCategory.BRAND,
        expected_sources=["anthropic.com"],
        difficulty="easy",
        notes="Should cite Anthropic",
    ),
    TestQuery(
        query="what is Perplexity AI",
        category=QueryCategory.BRAND,
        expected_sources=["perplexity.ai"],
        difficulty="easy",
        notes="Should cite Perplexity",
    ),
    # SEO Tools
    TestQuery(
        query="what is Moz Pro",
        category=QueryCategory.BRAND,
        expected_sources=["moz.com"],
        difficulty="easy",
        notes="Brand query - should cite Moz",
    ),
    TestQuery(
        query="Ahrefs vs SEMrush",
        category=QueryCategory.BRAND,
        expected_sources=["ahrefs.com", "semrush.com"],
        difficulty="medium",
        notes="Comparison query between brands",
    ),
]


# ============================================================================
# Combined Query Sets
# ============================================================================

TEST_QUERIES = (
    INFORMATIONAL_QUERIES
    + TOOL_COMPARISON_QUERIES
    + HOW_TO_QUERIES
    + TECHNICAL_QUERIES
    + BRAND_QUERIES
)


def get_queries_by_category(category: QueryCategory) -> list[TestQuery]:
    """Get queries filtered by category."""
    return [q for q in TEST_QUERIES if q.category == category]


def get_queries_for_domain(domain: str) -> list[TestQuery]:
    """Get queries where a domain is expected to be cited."""
    domain = domain.replace("www.", "").lower()
    return [q for q in TEST_QUERIES if any(domain in src.lower() for src in q.expected_sources)]


def get_informational_queries() -> list[TestQuery]:
    """Get informational queries."""
    return INFORMATIONAL_QUERIES


def get_tool_comparison_queries() -> list[TestQuery]:
    """Get tool comparison queries."""
    return TOOL_COMPARISON_QUERIES


def get_how_to_queries() -> list[TestQuery]:
    """Get how-to queries."""
    return HOW_TO_QUERIES


def get_technical_queries() -> list[TestQuery]:
    """Get technical queries."""
    return TECHNICAL_QUERIES


def get_brand_queries() -> list[TestQuery]:
    """Get brand queries."""
    return BRAND_QUERIES


def get_geo_queries() -> list[TestQuery]:
    """Get queries specifically related to GEO/AEO."""
    geo_terms = ["geo", "generative engine", "ai search", "ai visibility", "ai cite", "ai source"]
    return [q for q in TEST_QUERIES if any(term in q.query.lower() for term in geo_terms)]
