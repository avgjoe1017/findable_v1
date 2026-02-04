"""Site corpus for validation study.

60 sites across 4 quadrants designed to test score-citation correlation.
"""

from dataclasses import dataclass, field
from enum import Enum


class Quadrant(str, Enum):
    """Study quadrants based on expected score vs citation."""

    A = "high_score_cited"  # True Positives - validates scoring
    B = "high_score_not_cited"  # False Positives - reveals blind spots
    C = "low_score_cited"  # False Negatives - reveals missing factors
    D = "low_score_not_cited"  # True Negatives - validates scoring


@dataclass
class StudySite:
    """A site in the validation study."""

    id: str
    url: str
    name: str
    quadrant: Quadrant
    category: str
    why_selected: str
    expected_queries: list[str] = field(default_factory=list)
    technical_notes: str = ""


# ============================================================================
# QUADRANT A: High Score + Frequently Cited (True Positives)
# Profile: Well-optimized sites that AI systems cite regularly
# ============================================================================

QUADRANT_A_SITES = [
    # A1-A5: Tech/SaaS Leaders
    StudySite(
        id="A1",
        url="https://anthropic.com",
        name="Anthropic",
        quadrant=Quadrant.A,
        category="AI Company",
        why_selected="Known authority, cited for AI safety topics",
        expected_queries=["AI safety", "constitutional AI", "Claude AI"],
    ),
    StudySite(
        id="A2",
        url="https://stripe.com",
        name="Stripe",
        quadrant=Quadrant.A,
        category="Fintech",
        why_selected="Industry leader, excellent docs",
        expected_queries=["payment processing", "Stripe vs PayPal", "online payments API"],
    ),
    StudySite(
        id="A3",
        url="https://linear.app",
        name="Linear",
        quadrant=Quadrant.A,
        category="Project Management",
        why_selected="Modern SaaS, strong brand",
        expected_queries=["best project management tools", "Linear vs Jira"],
    ),
    StudySite(
        id="A4",
        url="https://notion.so",
        name="Notion",
        quadrant=Quadrant.A,
        category="Productivity",
        why_selected="Dominant in space, cited constantly",
        expected_queries=["best note taking apps", "Notion vs Obsidian"],
    ),
    StudySite(
        id="A5",
        url="https://vercel.com",
        name="Vercel",
        quadrant=Quadrant.A,
        category="Developer Tools",
        why_selected="Next.js creators, strong docs",
        expected_queries=["Next.js deployment", "Vercel vs Netlify", "serverless hosting"],
    ),
    # A6-A10: Reference/Authority Sites
    StudySite(
        id="A6",
        url="https://developer.mozilla.org",
        name="MDN Web Docs",
        quadrant=Quadrant.A,
        category="Technical Docs",
        why_selected="Canonical web reference",
        expected_queries=["CSS flexbox", "JavaScript array methods", "HTML semantic elements"],
    ),
    StudySite(
        id="A7",
        url="https://schema.org",
        name="Schema.org",
        quadrant=Quadrant.A,
        category="Standards",
        why_selected="Literal authority on schema",
        expected_queries=["schema markup types", "JSON-LD examples", "structured data"],
    ),
    StudySite(
        id="A8",
        url="https://www.w3.org",
        name="W3C",
        quadrant=Quadrant.A,
        category="Standards",
        why_selected="Web standards body",
        expected_queries=["WCAG guidelines", "accessibility standards", "HTML specification"],
    ),
    StudySite(
        id="A9",
        url="https://docs.python.org",
        name="Python Docs",
        quadrant=Quadrant.A,
        category="Technical Docs",
        why_selected="Official Python docs",
        expected_queries=["Python list comprehension", "Python async await", "Python decorators"],
    ),
    StudySite(
        id="A10",
        url="https://kubernetes.io",
        name="Kubernetes",
        quadrant=Quadrant.A,
        category="Technical Docs",
        why_selected="Canonical K8s reference",
        expected_queries=["Kubernetes pods", "K8s deployment", "container orchestration"],
    ),
    # A11-A15: Content/Media Leaders
    StudySite(
        id="A11",
        url="https://www.hubspot.com",
        name="HubSpot",
        quadrant=Quadrant.A,
        category="Marketing",
        why_selected="Dominant content marketer",
        expected_queries=["inbound marketing", "CRM best practices", "email marketing tips"],
    ),
    StudySite(
        id="A12",
        url="https://moz.com",
        name="Moz",
        quadrant=Quadrant.A,
        category="SEO",
        why_selected="SEO authority, coined terms",
        expected_queries=["domain authority", "link building", "SEO basics"],
    ),
    StudySite(
        id="A13",
        url="https://www.nerdwallet.com",
        name="NerdWallet",
        quadrant=Quadrant.A,
        category="Finance",
        why_selected="E-E-A-T exemplar",
        expected_queries=["best credit cards", "how to invest", "mortgage rates"],
    ),
    StudySite(
        id="A14",
        url="https://www.healthline.com",
        name="Healthline",
        quadrant=Quadrant.A,
        category="Health",
        why_selected="YMYL authority",
        expected_queries=["vitamin D benefits", "symptoms of anxiety", "healthy diet"],
    ),
    StudySite(
        id="A15",
        url="https://www.investopedia.com",
        name="Investopedia",
        quadrant=Quadrant.A,
        category="Finance",
        why_selected="Financial definitions",
        expected_queries=["what is inflation", "stock vs bond", "compound interest"],
    ),
]


# ============================================================================
# QUADRANT B: High Score + Rarely Cited (False Positives)
# Profile: Well-optimized sites that SHOULD get cited but don't
# ============================================================================

QUADRANT_B_SITES = [
    # B1-B5: Well-Optimized Unknown SaaS
    StudySite(
        id="B1",
        url="https://www.commandbar.com",
        name="CommandBar",
        quadrant=Quadrant.B,
        category="Dev Tools",
        why_selected="Great docs, good schema, but low brand awareness",
        expected_queries=["product tours", "in-app help", "user onboarding tools"],
        technical_notes="Schema ✓, Structure ✓",
    ),
    StudySite(
        id="B2",
        url="https://pika.style",
        name="Pika",
        quadrant=Quadrant.B,
        category="Design Tools",
        why_selected="Modern, well-built, but new and niche",
        expected_queries=["screenshot beautifier", "image mockups"],
        technical_notes="Fast, Schema ✓",
    ),
    StudySite(
        id="B3",
        url="https://www.airplane.dev",
        name="Airplane",
        quadrant=Quadrant.B,
        category="Internal Tools",
        why_selected="Excellent technical docs, enterprise niche",
        expected_queries=["internal tools platform", "admin panels"],
        technical_notes="Docs ✓, Schema ✓",
    ),
    StudySite(
        id="B4",
        url="https://www.radix-ui.com",
        name="Radix UI",
        quadrant=Quadrant.B,
        category="Design Systems",
        why_selected="Clean implementation, overshadowed by larger players",
        expected_queries=["headless UI components", "React primitives"],
        technical_notes="Structure ✓, Schema ✓",
    ),
    StudySite(
        id="B5",
        url="https://www.raycast.com",
        name="Raycast",
        quadrant=Quadrant.B,
        category="Productivity",
        why_selected="Well-optimized site, Mac-only niche",
        expected_queries=["Mac launcher app", "Alfred alternative"],
        technical_notes="Fast, Schema ✓",
    ),
    # B6-B10: Optimized Content Sites in Crowded Niches
    StudySite(
        id="B6",
        url="https://backlinko.com",
        name="Backlinko",
        quadrant=Quadrant.B,
        category="SEO Blog",
        why_selected="Well-structured content, overshadowed by Moz/Ahrefs",
        expected_queries=["backlink strategies", "SEO case studies"],
        technical_notes="Schema ✓, Structure ✓",
    ),
    StudySite(
        id="B7",
        url="https://growthhackers.com",
        name="GrowthHackers",
        quadrant=Quadrant.B,
        category="Marketing",
        why_selected="Good technical setup, lost mindshare",
        expected_queries=["growth hacking tactics", "startup marketing"],
        technical_notes="Schema ✓, Clean",
    ),
    StudySite(
        id="B8",
        url="https://copyblogger.com",
        name="Copyblogger",
        quadrant=Quadrant.B,
        category="Content Marketing",
        why_selected="Pioneer, good structure, dated perception",
        expected_queries=["copywriting tips", "content writing"],
        technical_notes="Schema ✓, E-E-A-T ✓",
    ),
    StudySite(
        id="B9",
        url="https://www.convinceandconvert.com",
        name="Convince & Convert",
        quadrant=Quadrant.B,
        category="Marketing",
        why_selected="Proper implementation, niche lower volume",
        expected_queries=["social media strategy", "content strategy"],
        technical_notes="Schema ✓, Authority ✓",
    ),
    StudySite(
        id="B10",
        url="https://contentmarketinginstitute.com",
        name="Content Marketing Institute",
        quadrant=Quadrant.B,
        category="Content",
        why_selected="Industry body, institutional and dry",
        expected_queries=["content marketing trends", "B2B content"],
        technical_notes="Schema ✓, Authority ✓",
    ),
    # B11-B15: Technical Excellence, Brand Obscurity
    StudySite(
        id="B11",
        url="https://questdb.io",
        name="QuestDB",
        quadrant=Quadrant.B,
        category="Database",
        why_selected="Excellent docs, niche time-series DB",
        expected_queries=["time series database", "SQL for time series"],
        technical_notes="Docs ✓, Schema ✓",
    ),
    StudySite(
        id="B12",
        url="https://temporal.io",
        name="Temporal",
        quadrant=Quadrant.B,
        category="Dev Tools",
        why_selected="Great technical content, workflow orchestration niche",
        expected_queries=["workflow orchestration", "durable execution"],
        technical_notes="Schema ✓, Structure ✓",
    ),
    StudySite(
        id="B13",
        url="https://buf.build",
        name="Buf",
        quadrant=Quadrant.B,
        category="Dev Tools",
        why_selected="Well-built, good docs, Protobuf niche",
        expected_queries=["protobuf tools", "gRPC development"],
        technical_notes="Fast, Schema ✓",
    ),
    StudySite(
        id="B14",
        url="https://www.tinybird.co",
        name="Tinybird",
        quadrant=Quadrant.B,
        category="Data Tools",
        why_selected="Modern, optimized, analytics niche",
        expected_queries=["real-time analytics", "ClickHouse managed"],
        technical_notes="Schema ✓, Fast",
    ),
    StudySite(
        id="B15",
        url="https://planetscale.com",
        name="PlanetScale",
        quadrant=Quadrant.B,
        category="Database",
        why_selected="Excellent content, MySQL niche, overshadowed by Supabase",
        expected_queries=["serverless MySQL", "database branching"],
        technical_notes="Schema ✓, Structure ✓",
    ),
]


# ============================================================================
# QUADRANT C: Low Score + Frequently Cited (False Negatives)
# Profile: Poorly-optimized sites that AI cites anyway
# ============================================================================

QUADRANT_C_SITES = [
    # C1-C5: User-Generated Content Platforms
    StudySite(
        id="C1",
        url="https://www.reddit.com",
        name="Reddit",
        quadrant=Quadrant.C,
        category="Forum",
        why_selected="Training data dominance, authentic opinions",
        expected_queries=["best laptop reddit", "is X worth it", "advice subreddit"],
        technical_notes="Inconsistent structure, no article schema, chaotic markup",
    ),
    StudySite(
        id="C2",
        url="https://www.quora.com",
        name="Quora",
        quadrant=Quadrant.C,
        category="Q&A",
        why_selected="Training data, question-answer format",
        expected_queries=["why questions", "how does X work", "explain like I'm 5"],
        technical_notes="Heavy JS, inconsistent schema, slow",
    ),
    StudySite(
        id="C3",
        url="https://stackexchange.com",
        name="Stack Exchange",
        quadrant=Quadrant.C,
        category="Q&A",
        why_selected="Canonical technical answers, massive backlinks",
        expected_queries=["how to fix error", "programming questions"],
        technical_notes="Dated markup, minimal schema",
    ),
    StudySite(
        id="C4",
        url="https://news.ycombinator.com",
        name="Hacker News",
        quadrant=Quadrant.C,
        category="Forum",
        why_selected="Tech authority, startup ecosystem coverage",
        expected_queries=["startup advice", "tech trends", "Show HN"],
        technical_notes="Zero schema, minimal HTML",
    ),
    StudySite(
        id="C5",
        url="https://medium.com",
        name="Medium",
        quadrant=Quadrant.C,
        category="Blog Platform",
        why_selected="Volume, covers every topic, some authoritative authors",
        expected_queries=["how to articles", "personal essays", "tech tutorials"],
        technical_notes="Inconsistent (user-dependent), paywall issues",
    ),
    # C6-C10: Legacy Authority Sites
    StudySite(
        id="C6",
        url="https://www.irs.gov",
        name="IRS",
        quadrant=Quadrant.C,
        category="Government",
        why_selected="Only authoritative source for US tax info",
        expected_queries=["tax filing deadline", "W-4 form", "tax brackets"],
        technical_notes="Dated design, poor UX, limited schema",
    ),
    StudySite(
        id="C7",
        url="https://www.cdc.gov",
        name="CDC",
        quadrant=Quadrant.C,
        category="Government",
        why_selected="Health authority, YMYL requirements",
        expected_queries=["vaccine information", "disease symptoms", "health guidelines"],
        technical_notes="Slow, cluttered, inconsistent structure",
    ),
    StudySite(
        id="C8",
        url="https://www.sec.gov",
        name="SEC",
        quadrant=Quadrant.C,
        category="Government",
        why_selected="Only source for SEC filings",
        expected_queries=["SEC filings", "10-K reports", "company financials"],
        technical_notes="PDF-heavy, poor navigation, no schema",
    ),
    StudySite(
        id="C9",
        url="https://www.nytimes.com",
        name="New York Times",
        quadrant=Quadrant.C,
        category="News",
        why_selected="Brand dominance, journalistic authority",
        expected_queries=["news analysis", "investigative journalism"],
        technical_notes="Paywall, heavy JS, inconsistent schema",
    ),
    StudySite(
        id="C10",
        url="https://www.bbc.com",
        name="BBC",
        quadrant=Quadrant.C,
        category="News",
        why_selected="Global brand, training data prevalence",
        expected_queries=["world news", "UK news", "BBC analysis"],
        technical_notes="Complex structure, dated areas",
    ),
    # C11-C15: Wikipedia and Reference
    StudySite(
        id="C11",
        url="https://www.wikipedia.org",
        name="Wikipedia",
        quadrant=Quadrant.C,
        category="Encyclopedia",
        why_selected="Training data dominance, neutral POV, covers everything",
        expected_queries=["what is X", "history of", "biography of"],
        technical_notes="Dated CSS, no JSON-LD schema, MediaWiki quirks",
    ),
    StudySite(
        id="C12",
        url="https://www.britannica.com",
        name="Britannica",
        quadrant=Quadrant.C,
        category="Encyclopedia",
        why_selected="Legacy authority, editorial quality",
        expected_queries=["encyclopedia entries", "academic definitions"],
        technical_notes="Subscription barriers, slower, older",
    ),
    StudySite(
        id="C13",
        url="https://www.webmd.com",
        name="WebMD",
        quadrant=Quadrant.C,
        category="Health",
        why_selected="Health authority, brand recognition",
        expected_queries=["symptoms of", "treatment for", "is X safe"],
        technical_notes="Ad-heavy, cluttered, older design",
    ),
    StudySite(
        id="C14",
        url="https://www.mayoclinic.org",
        name="Mayo Clinic",
        quadrant=Quadrant.C,
        category="Health",
        why_selected="Medical authority, E-E-A-T",
        expected_queries=["medical conditions", "treatment options", "health advice"],
        technical_notes="Dated UX, slow in areas",
    ),
    StudySite(
        id="C15",
        url="https://www.imdb.com",
        name="IMDb",
        quadrant=Quadrant.C,
        category="Entertainment",
        why_selected="Only comprehensive film database",
        expected_queries=["movie cast", "film ratings", "actor filmography"],
        technical_notes="Heavy JS, complex structure",
    ),
]


# ============================================================================
# QUADRANT D: Low Score + Rarely Cited (True Negatives)
# Profile: Poorly-optimized sites that don't get cited
# These are real sites with low technical quality and no AI authority
# ============================================================================

QUADRANT_D_SITES = [
    # D1-D5: Small/Niche Sites with Minimal SEO
    StudySite(
        id="D1",
        url="https://httpbin.org",
        name="HTTPBin",
        quadrant=Quadrant.D,
        category="Developer Tool",
        why_selected="Utility site, no content, just HTTP testing endpoints",
        expected_queries=["HTTP testing", "API testing tool"],
        technical_notes="Minimal content, no articles, no schema",
    ),
    StudySite(
        id="D2",
        url="https://example.com",
        name="Example.com",
        quadrant=Quadrant.D,
        category="Placeholder",
        why_selected="IANA reserved domain, minimal content by design",
        expected_queries=["example domain"],
        technical_notes="Intentionally minimal, no real content",
    ),
    StudySite(
        id="D3",
        url="https://www.zombo.com",
        name="Zombo.com",
        quadrant=Quadrant.D,
        category="Internet Curiosity",
        why_selected="Joke site, Flash-era artifact, no useful content",
        expected_queries=["anything is possible"],
        technical_notes="No schema, no real content, novelty only",
    ),
    StudySite(
        id="D4",
        url="https://textfiles.com",
        name="TextFiles.com",
        quadrant=Quadrant.D,
        category="Archive",
        why_selected="BBS-era text file archive, dated design, niche",
        expected_queries=["BBS history", "old text files"],
        technical_notes="1990s design, no schema, historical archive",
    ),
    StudySite(
        id="D5",
        url="https://www.cameronsworld.net",
        name="Cameron's World",
        quadrant=Quadrant.D,
        category="Web Archive",
        why_selected="Geocities tribute, intentionally retro, no useful content",
        expected_queries=["geocities nostalgia"],
        technical_notes="Art project, not informational",
    ),
    # D6-D10: Thin/Dated Content Sites
    StudySite(
        id="D6",
        url="https://www.arngren.net",
        name="Arngren",
        quadrant=Quadrant.D,
        category="E-commerce",
        why_selected="Famously bad UX, chaotic layout, Norwegian electronics",
        expected_queries=["buy electronics Norway"],
        technical_notes="No schema, terrible structure, local market",
    ),
    StudySite(
        id="D7",
        url="https://motherfuckingwebsite.com",
        name="MF Website",
        quadrant=Quadrant.D,
        category="Satire",
        why_selected="Satirical minimalist site, no real content",
        expected_queries=["minimal web design"],
        technical_notes="One-page joke, no schema, no depth",
    ),
    StudySite(
        id="D8",
        url="https://www.lingscars.com",
        name="Ling's Cars",
        quadrant=Quadrant.D,
        category="Car Leasing",
        why_selected="Intentionally chaotic design, UK local business",
        expected_queries=["car leasing UK"],
        technical_notes="Chaotic but functional, limited authority outside UK",
    ),
    StudySite(
        id="D9",
        url="https://www.w3schools.com",
        name="W3Schools",
        quadrant=Quadrant.D,
        category="Tutorial",
        why_selected="Often overshadowed by MDN, criticized for inaccuracies",
        expected_queries=["HTML tutorial", "CSS basics"],
        technical_notes="AI prefers MDN for same queries",
    ),
    StudySite(
        id="D10",
        url="https://www.tutorialspoint.com",
        name="TutorialsPoint",
        quadrant=Quadrant.D,
        category="Tutorial",
        why_selected="Ad-heavy, inconsistent quality, overshadowed by official docs",
        expected_queries=["programming tutorials"],
        technical_notes="Generic content, AI prefers official sources",
    ),
    # D11-D15: Utility/Test Sites with No Content Value
    StudySite(
        id="D11",
        url="https://www.whatismybrowser.com",
        name="What Is My Browser",
        quadrant=Quadrant.D,
        category="Utility",
        why_selected="Single-purpose utility, no informational content",
        expected_queries=["browser detection"],
        technical_notes="Tool-only, no articles",
    ),
    StudySite(
        id="D12",
        url="https://www.speedtest.net",
        name="Speedtest",
        quadrant=Quadrant.D,
        category="Utility",
        why_selected="Single-purpose speed test, minimal informational content",
        expected_queries=["internet speed test"],
        technical_notes="Tool-focused, thin content",
    ),
    StudySite(
        id="D13",
        url="https://www.isitdownrightnow.com",
        name="Is It Down Right Now",
        quadrant=Quadrant.D,
        category="Utility",
        why_selected="Status checker utility, no depth",
        expected_queries=["is website down"],
        technical_notes="Simple utility, no educational content",
    ),
    StudySite(
        id="D14",
        url="https://www.tempail.com",
        name="Tempail",
        quadrant=Quadrant.D,
        category="Utility",
        why_selected="Temporary email service, no content",
        expected_queries=["temporary email"],
        technical_notes="Service-only, no articles or guides",
    ),
    StudySite(
        id="D15",
        url="https://neverssl.com",
        name="NeverSSL",
        quadrant=Quadrant.D,
        category="Utility",
        why_selected="Captive portal bypass utility, single purpose",
        expected_queries=["captive portal bypass"],
        technical_notes="One-page utility, no content",
    ),
]


def get_all_sites() -> list[StudySite]:
    """Get all sites in the study corpus."""
    return QUADRANT_A_SITES + QUADRANT_B_SITES + QUADRANT_C_SITES + QUADRANT_D_SITES


def get_sites_by_quadrant(quadrant: Quadrant) -> list[StudySite]:
    """Get sites for a specific quadrant."""
    mapping = {
        Quadrant.A: QUADRANT_A_SITES,
        Quadrant.B: QUADRANT_B_SITES,
        Quadrant.C: QUADRANT_C_SITES,
        Quadrant.D: QUADRANT_D_SITES,
    }
    return mapping.get(quadrant, [])


def get_real_sites() -> list[StudySite]:
    """Get only sites with real URLs (not placeholders)."""
    all_sites = get_all_sites()
    return [s for s in all_sites if not s.url.startswith("https://example-")]


def get_placeholder_count() -> int:
    """Count how many placeholder sites need real URLs."""
    return len([s for s in get_all_sites() if s.url.startswith("https://example-")])
