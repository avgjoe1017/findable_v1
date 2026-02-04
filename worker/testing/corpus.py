"""Test corpus definitions for real-world validation.

Defines test sites across categories:
- Known Cited: Sites that ARE cited by AI systems
- Known Uncited: Relevant sites that are NOT cited
- Own Properties: Findable's own sites
- Competitors: Direct competitor tools
"""

from dataclasses import dataclass, field
from enum import Enum


class SiteCategory(str, Enum):
    """Categories for test sites."""

    KNOWN_CITED = "known_cited"  # Sites that ARE cited by AI
    KNOWN_UNCITED = "known_uncited"  # Relevant but NOT cited
    OWN_PROPERTY = "own_property"  # Findable's own sites
    COMPETITOR = "competitor"  # Direct competitors


@dataclass
class TestSite:
    """A site in the test corpus."""

    url: str
    name: str
    category: SiteCategory
    expected_queries: list[str] = field(default_factory=list)  # Queries where site SHOULD appear
    industry: str = ""  # Industry/vertical
    authority_level: str = "medium"  # "high", "medium", "low"
    notes: str = ""

    @property
    def domain(self) -> str:
        """Extract domain from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(self.url)
        return parsed.netloc.replace("www.", "")


# ============================================================================
# Known Cited Sites - Sites that ARE frequently cited by AI
# ============================================================================

KNOWN_CITED_SITES = [
    # SEO & Marketing Authority Sites
    TestSite(
        url="https://moz.com",
        name="Moz",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "what is domain authority",
            "how to do keyword research",
            "SEO best practices",
            "what is link building",
        ],
        industry="SEO",
        authority_level="high",
        notes="Industry authority, strong E-E-A-T, frequently cited for SEO queries",
    ),
    TestSite(
        url="https://ahrefs.com/blog",
        name="Ahrefs Blog",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "how to do backlink analysis",
            "SEO tools comparison",
            "keyword difficulty explained",
        ],
        industry="SEO",
        authority_level="high",
        notes="Major SEO tool, authoritative blog content",
    ),
    TestSite(
        url="https://searchengineland.com",
        name="Search Engine Land",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "Google algorithm updates",
            "search engine news",
            "SEO industry updates",
        ],
        industry="SEO News",
        authority_level="high",
        notes="Industry news authority, cited for current events",
    ),
    TestSite(
        url="https://www.searchenginejournal.com",
        name="Search Engine Journal",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "SEO tips and strategies",
            "content marketing best practices",
        ],
        industry="SEO",
        authority_level="high",
        notes="Long-standing SEO publication",
    ),
    TestSite(
        url="https://hubspot.com",
        name="HubSpot",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "what is inbound marketing",
            "how to create a marketing plan",
            "CRM best practices",
            "email marketing tips",
        ],
        industry="Marketing",
        authority_level="high",
        notes="Marketing authority, comprehensive content library",
    ),
    TestSite(
        url="https://neilpatel.com",
        name="Neil Patel",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "digital marketing strategies",
            "how to increase website traffic",
            "SEO for beginners",
        ],
        industry="Digital Marketing",
        authority_level="high",
        notes="Personal brand authority, extensive content",
    ),
    # Technical Reference Sites
    TestSite(
        url="https://schema.org",
        name="Schema.org",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "what is schema markup",
            "structured data types",
            "JSON-LD examples",
        ],
        industry="Technical Standards",
        authority_level="high",
        notes="Definitive source for schema markup, always cited",
    ),
    TestSite(
        url="https://developer.mozilla.org",
        name="MDN Web Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "JavaScript documentation",
            "HTML elements reference",
            "CSS properties",
            "web API documentation",
        ],
        industry="Web Development",
        authority_level="high",
        notes="Canonical web dev reference, extremely well-cited",
    ),
    TestSite(
        url="https://developers.google.com",
        name="Google Developers",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "Google Search documentation",
            "Core Web Vitals",
            "structured data guidelines",
        ],
        industry="Web Development",
        authority_level="high",
        notes="Official Google documentation, authoritative",
    ),
    TestSite(
        url="https://www.w3.org",
        name="W3C",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "web standards",
            "HTML specification",
            "accessibility guidelines WCAG",
        ],
        industry="Web Standards",
        authority_level="high",
        notes="Web standards body, definitive source",
    ),
    # E-commerce & Business
    TestSite(
        url="https://www.shopify.com/blog",
        name="Shopify Blog",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "how to start an online store",
            "e-commerce best practices",
            "dropshipping guide",
        ],
        industry="E-commerce",
        authority_level="high",
        notes="Major platform, authoritative e-commerce content",
    ),
    # AI & Tech
    TestSite(
        url="https://openai.com",
        name="OpenAI",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "what is GPT",
            "ChatGPT capabilities",
            "AI safety",
        ],
        industry="AI",
        authority_level="high",
        notes="Primary source for OpenAI/ChatGPT information",
    ),
    TestSite(
        url="https://www.anthropic.com",
        name="Anthropic",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "what is Claude AI",
            "constitutional AI",
            "AI alignment",
        ],
        industry="AI",
        authority_level="high",
        notes="Primary source for Claude/Anthropic information",
    ),
]


# ============================================================================
# Known Uncited Sites - Relevant but typically NOT cited
# ============================================================================

KNOWN_UNCITED_SITES = [
    # Small/New Blogs
    TestSite(
        url="https://backlinko.com",
        name="Backlinko",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "link building strategies",
            "SEO case studies",
        ],
        industry="SEO",
        authority_level="medium",
        notes="Good content but less frequently cited than major authorities",
    ),
    # Forums & UGC
    TestSite(
        url="https://www.reddit.com/r/SEO",
        name="Reddit SEO",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "SEO tips from practitioners",
        ],
        industry="SEO",
        authority_level="low",
        notes="UGC content, rarely cited directly",
    ),
    # Paywalled Content
    TestSite(
        url="https://www.wsj.com",
        name="Wall Street Journal",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "business news",
            "market analysis",
        ],
        industry="News",
        authority_level="high",
        notes="High authority but paywalled - AI can't access full content",
    ),
    # Regional/Local Sites
    TestSite(
        url="https://www.bbc.com",
        name="BBC",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "UK news",
            "international news",
        ],
        industry="News",
        authority_level="high",
        notes="Major news source, but AI often prefers tech-specific sources",
    ),
]


# ============================================================================
# Own Properties - Findable's sites
# ============================================================================

OWN_PROPERTY_SITES = [
    TestSite(
        url="https://findable.so",
        name="Findable",
        category=SiteCategory.OWN_PROPERTY,
        expected_queries=[
            "AI SEO tools",
            "findable score",
            "GEO optimization tools",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="Primary product site",
    ),
    # Add additional own properties as they exist
]


# ============================================================================
# Competitor Sites - Direct competitor tools
# ============================================================================

COMPETITOR_SITES = [
    TestSite(
        url="https://otterly.ai",
        name="Otterly.ai",
        category=SiteCategory.COMPETITOR,
        expected_queries=[
            "AI search optimization tools",
            "track AI citations",
        ],
        industry="AI SEO",
        authority_level="medium",
        notes="Direct competitor - AI visibility tracking",
    ),
    TestSite(
        url="https://www.rankscale.ai",
        name="RankScale",
        category=SiteCategory.COMPETITOR,
        expected_queries=[
            "AI search ranking",
            "GEO tools",
        ],
        industry="AI SEO",
        authority_level="medium",
        notes="Direct competitor - AI ranking tool",
    ),
    TestSite(
        url="https://www.amsive.com/insights/seo/generative-engine-optimization-geo/",
        name="Amsive GEO Guide",
        category=SiteCategory.COMPETITOR,
        expected_queries=[
            "what is generative engine optimization",
            "GEO best practices",
        ],
        industry="Marketing Agency",
        authority_level="medium",
        notes="Agency content on GEO - often cited for GEO definitions",
    ),
]


# ============================================================================
# Test Corpus Class
# ============================================================================


@dataclass
class TestCorpus:
    """Collection of test sites for validation."""

    sites: list[TestSite] = field(default_factory=list)
    name: str = "default"
    description: str = ""

    @classmethod
    def full(cls) -> "TestCorpus":
        """Get the full test corpus."""
        return cls(
            sites=(KNOWN_CITED_SITES + KNOWN_UNCITED_SITES + OWN_PROPERTY_SITES + COMPETITOR_SITES),
            name="full",
            description="Complete test corpus with all site categories",
        )

    @classmethod
    def quick(cls) -> "TestCorpus":
        """Get a quick test corpus (subset for fast runs)."""
        return cls(
            sites=[
                KNOWN_CITED_SITES[0],  # Moz
                KNOWN_CITED_SITES[6],  # Schema.org
                KNOWN_UNCITED_SITES[0],  # Backlinko
            ]
            + OWN_PROPERTY_SITES,
            name="quick",
            description="Quick subset for fast validation runs",
        )

    @classmethod
    def own(cls) -> "TestCorpus":
        """Get own property sites only."""
        return cls(
            sites=OWN_PROPERTY_SITES,
            name="own",
            description="Findable's own properties",
        )

    @classmethod
    def competitors(cls) -> "TestCorpus":
        """Get competitor sites only."""
        return cls(
            sites=COMPETITOR_SITES,
            name="competitors",
            description="Direct competitor tools and content",
        )

    @classmethod
    def known_cited(cls) -> "TestCorpus":
        """Get known cited sites only."""
        return cls(
            sites=KNOWN_CITED_SITES,
            name="known_cited",
            description="Sites known to be cited by AI systems",
        )

    @classmethod
    def known_uncited(cls) -> "TestCorpus":
        """Get known uncited sites only."""
        return cls(
            sites=KNOWN_UNCITED_SITES,
            name="known_uncited",
            description="Relevant sites that are typically not cited",
        )

    def filter_by_category(self, category: SiteCategory) -> "TestCorpus":
        """Filter corpus by site category."""
        return TestCorpus(
            sites=[s for s in self.sites if s.category == category],
            name=f"{self.name}_{category.value}",
            description=f"{self.name} filtered to {category.value}",
        )

    def filter_by_industry(self, industry: str) -> "TestCorpus":
        """Filter corpus by industry."""
        return TestCorpus(
            sites=[s for s in self.sites if s.industry.lower() == industry.lower()],
            name=f"{self.name}_{industry}",
            description=f"{self.name} filtered to {industry}",
        )

    @property
    def domains(self) -> list[str]:
        """Get all domains in the corpus."""
        return [site.domain for site in self.sites]

    @property
    def urls(self) -> list[str]:
        """Get all URLs in the corpus."""
        return [site.url for site in self.sites]

    def __len__(self) -> int:
        return len(self.sites)

    def __iter__(self):
        return iter(self.sites)

    def get_by_domain(self, domain: str) -> TestSite | None:
        """Find a site by domain."""
        domain = domain.replace("www.", "").lower()
        for site in self.sites:
            if site.domain.lower() == domain:
                return site
        return None

    def to_dict(self) -> dict:
        """Serialize corpus to dict."""
        return {
            "name": self.name,
            "description": self.description,
            "site_count": len(self.sites),
            "sites": [
                {
                    "url": s.url,
                    "name": s.name,
                    "category": s.category.value,
                    "domain": s.domain,
                    "industry": s.industry,
                    "authority_level": s.authority_level,
                    "expected_queries": s.expected_queries,
                    "notes": s.notes,
                }
                for s in self.sites
            ],
        }
