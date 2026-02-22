"""Test corpus definitions for real-world validation.

Defines test sites across categories:
- Known Cited: Sites that ARE cited by AI systems
- Known Uncited: Relevant sites that are NOT cited
- Own Properties: Findable's own sites
- Competitors: Direct competitor tools
"""

from dataclasses import dataclass, field
from enum import StrEnum


class SiteCategory(StrEnum):
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
    # Documentation Sites (HIGH citation — these are THE canonical source)
    TestSite(
        url="https://docs.python.org",
        name="Python Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "python list comprehension",
            "python asyncio documentation",
            "python string methods",
        ],
        industry="Programming",
        authority_level="high",
        notes="Canonical Python documentation, ~100% citation rate",
    ),
    TestSite(
        url="https://react.dev",
        name="React Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "react hooks tutorial",
            "react useEffect documentation",
            "react component lifecycle",
        ],
        industry="Web Development",
        authority_level="high",
        notes="Official React documentation, canonical source",
    ),
    TestSite(
        url="https://docs.stripe.com",
        name="Stripe Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "stripe payment integration",
            "stripe webhook setup",
            "stripe subscription billing",
        ],
        industry="Fintech",
        authority_level="high",
        notes="Official Stripe API documentation, primary source",
    ),
    TestSite(
        url="https://docs.github.com",
        name="GitHub Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "github actions documentation",
            "github pull request workflow",
            "github api reference",
        ],
        industry="Developer Tools",
        authority_level="high",
        notes="Official GitHub documentation",
    ),
    TestSite(
        url="https://kubernetes.io",
        name="Kubernetes Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "kubernetes pod documentation",
            "kubernetes deployment yaml",
            "kubectl commands reference",
        ],
        industry="DevOps",
        authority_level="high",
        notes="Official Kubernetes documentation, canonical source",
    ),
    TestSite(
        url="https://docs.docker.com",
        name="Docker Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "dockerfile reference",
            "docker compose tutorial",
            "docker networking guide",
        ],
        industry="DevOps",
        authority_level="high",
        notes="Official Docker documentation",
    ),
    TestSite(
        url="https://www.terraform.io",
        name="Terraform Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "terraform aws provider",
            "terraform state management",
            "terraform modules guide",
        ],
        industry="DevOps",
        authority_level="high",
        notes="Official Terraform/HashiCorp documentation",
    ),
    TestSite(
        url="https://www.typescriptlang.org",
        name="TypeScript Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "typescript generics tutorial",
            "typescript interface vs type",
            "typescript utility types",
        ],
        industry="Programming",
        authority_level="high",
        notes="Official TypeScript documentation, canonical source",
    ),
    TestSite(
        url="https://tailwindcss.com",
        name="Tailwind CSS",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "tailwind css flexbox classes",
            "tailwind responsive design",
            "tailwind custom configuration",
        ],
        industry="Web Development",
        authority_level="high",
        notes="Official Tailwind CSS documentation",
    ),
    TestSite(
        url="https://nextjs.org",
        name="Next.js Docs",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "next.js app router",
            "next.js server components",
            "next.js api routes",
        ],
        industry="Web Development",
        authority_level="high",
        notes="Official Next.js documentation, Vercel maintained",
    ),
    # Reference Sites (HIGH citation — provide unique authoritative answers)
    TestSite(
        url="https://stackoverflow.com",
        name="Stack Overflow",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "how to parse JSON in python",
            "javascript promise error handling",
            "git merge vs rebase",
        ],
        industry="Developer Q&A",
        authority_level="high",
        notes="Largest developer Q&A site, frequently cited for code solutions",
    ),
    TestSite(
        url="https://en.wikipedia.org",
        name="Wikipedia",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "history of the internet",
            "machine learning definition",
            "what is TCP/IP",
        ],
        industry="Encyclopedia",
        authority_level="high",
        notes="Universal reference, extremely high citation rate for definitions",
    ),
    TestSite(
        url="https://www.investopedia.com",
        name="Investopedia",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "what is a mutual fund",
            "how does compound interest work",
            "stock market basics",
        ],
        industry="Finance",
        authority_level="high",
        notes="Financial reference authority, strong citation for finance queries",
    ),
    TestSite(
        url="https://www.mayoclinic.org",
        name="Mayo Clinic",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "symptoms of diabetes",
            "high blood pressure treatment",
            "vitamin D deficiency",
        ],
        industry="Healthcare",
        authority_level="high",
        notes="Medical reference authority, highly cited for health queries",
    ),
    TestSite(
        url="https://www.law.cornell.edu",
        name="Cornell Law",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "first amendment text",
            "what is habeas corpus",
            "contract law basics",
        ],
        industry="Legal",
        authority_level="high",
        notes="Legal reference, canonical source for US law text",
    ),
    # Developer Tools (HIGH citation — primary source for their own product)
    TestSite(
        url="https://github.com",
        name="GitHub",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "github repository management",
            "git version control",
            "open source projects",
        ],
        industry="Developer Tools",
        authority_level="high",
        notes="Largest code hosting platform, cited for repos and tools",
    ),
    TestSite(
        url="https://vercel.com",
        name="Vercel",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "vercel deployment guide",
            "serverless functions vercel",
            "edge functions documentation",
        ],
        industry="Cloud Platform",
        authority_level="high",
        notes="Major deployment platform, cited for its own product",
    ),
    TestSite(
        url="https://www.cloudflare.com",
        name="Cloudflare",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "cloudflare CDN setup",
            "what is a CDN",
            "DDoS protection",
        ],
        industry="Cloud Infrastructure",
        authority_level="high",
        notes="Major CDN/security provider, cited for infrastructure topics",
    ),
    TestSite(
        url="https://aws.amazon.com",
        name="AWS",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "AWS S3 documentation",
            "AWS Lambda tutorial",
            "cloud computing services",
        ],
        industry="Cloud Infrastructure",
        authority_level="high",
        notes="Largest cloud provider, canonical source for AWS services",
    ),
    # Blogs that ARE cited (high-authority, original content)
    TestSite(
        url="https://www.smashingmagazine.com",
        name="Smashing Magazine",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "web design best practices",
            "CSS grid layout tutorial",
            "responsive design patterns",
        ],
        industry="Web Design",
        authority_level="high",
        notes="Authoritative web development publication, frequently cited",
    ),
    TestSite(
        url="https://css-tricks.com",
        name="CSS-Tricks",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "CSS flexbox guide",
            "CSS grid complete guide",
            "CSS animation examples",
        ],
        industry="Web Development",
        authority_level="high",
        notes="Canonical CSS reference blog, extremely well-cited",
    ),
    # Government / Institutional (primary sources, highly cited)
    TestSite(
        url="https://www.cdc.gov",
        name="CDC",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "vaccine recommendations",
            "disease prevention guidelines",
            "public health data",
        ],
        industry="Government Health",
        authority_level="high",
        notes="Government health authority, primary source, highly cited",
    ),
    TestSite(
        url="https://www.irs.gov",
        name="IRS",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "tax filing deadlines",
            "tax brackets",
            "1099 form instructions",
        ],
        industry="Government",
        authority_level="high",
        notes="Official tax authority, canonical source for US tax info",
    ),
    TestSite(
        url="https://www.nist.gov",
        name="NIST",
        category=SiteCategory.KNOWN_CITED,
        expected_queries=[
            "cybersecurity framework",
            "measurement standards",
        ],
        industry="Government Standards",
        authority_level="high",
        notes="National standards body, primary source for tech standards",
    ),
]


# ============================================================================
# Known Uncited Sites - Relevant but typically NOT cited
# ============================================================================

KNOWN_UNCITED_SITES = [
    # NOTE: Backlinko was removed from this list after audit showed it was cited
    # 20/20 times. It's actually a well-known SEO authority site.
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
    # Small SaaS / Niche Products - good content but rarely cited by AI
    TestSite(
        url="https://www.lemlist.com",
        name="Lemlist",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "cold email best practices",
            "email outreach tools",
        ],
        industry="Sales Tech",
        authority_level="low",
        notes="Niche SaaS tool, has blog content but not cited by AI models",
    ),
    TestSite(
        url="https://www.hunter.io",
        name="Hunter.io",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "email finder tools",
            "how to find business email addresses",
        ],
        industry="Sales Tech",
        authority_level="low",
        notes="Email finder tool, rarely cited for general queries",
    ),
    TestSite(
        url="https://buffer.com/resources",
        name="Buffer Blog",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "social media scheduling",
            "best times to post on social media",
        ],
        industry="Social Media",
        authority_level="medium",
        notes="Social media tool blog, competes with larger brands for citations",
    ),
    # Local businesses / service providers
    TestSite(
        url="https://www.yelp.com",
        name="Yelp",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "restaurant reviews near me",
            "best local businesses",
        ],
        industry="Local Business",
        authority_level="medium",
        notes="Large platform but AI doesn't cite specific Yelp listings",
    ),
    # Aggregators / comparison sites
    TestSite(
        url="https://www.g2.com",
        name="G2",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best CRM software reviews",
            "project management tool comparison",
        ],
        industry="Software Reviews",
        authority_level="medium",
        notes="Review aggregator, AI summarizes rather than cites",
    ),
    TestSite(
        url="https://www.capterra.com",
        name="Capterra",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best accounting software for small business",
            "HR software reviews",
        ],
        industry="Software Reviews",
        authority_level="medium",
        notes="Software comparison site, rarely directly cited by AI",
    ),
    # E-commerce / product pages
    TestSite(
        url="https://www.etsy.com",
        name="Etsy",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "handmade gifts",
            "custom jewelry online",
        ],
        industry="E-commerce",
        authority_level="medium",
        notes="Marketplace, AI doesn't cite specific product listings",
    ),
    # Thin content / template sites
    TestSite(
        url="https://www.wix.com/blog",
        name="Wix Blog",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "how to build a website",
            "website builder comparison",
        ],
        industry="Website Builders",
        authority_level="medium",
        notes="Has content but competes with Shopify/WordPress for AI citations",
    ),
    # SaaS marketing pages — good SEO but AI prefers authoritative/docs content
    TestSite(
        url="https://www.freshworks.com",
        name="Freshworks",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "CRM software for small business",
            "customer support tools",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="SaaS marketing site; competes with Salesforce/HubSpot for citations",
    ),
    TestSite(
        url="https://www.pipedrive.com",
        name="Pipedrive",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "sales pipeline management",
            "best CRM for sales teams",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="CRM SaaS marketing; AI cites Salesforce/HubSpot instead",
    ),
    TestSite(
        url="https://www.datadog.com",
        name="Datadog",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "application monitoring tools",
            "cloud observability platform",
        ],
        industry="DevOps",
        authority_level="medium",
        notes="Confirmed 0% citation rate in calibration corpus (Feb 2026)",
    ),
    # Content aggregators / directories
    TestSite(
        url="https://www.crunchbase.com",
        name="Crunchbase",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "startup funding data",
            "company information lookup",
        ],
        industry="Business Data",
        authority_level="medium",
        notes="Database/directory site, AI summarizes rather than cites",
    ),
    TestSite(
        url="https://www.glassdoor.com",
        name="Glassdoor",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "company reviews",
            "salary data by role",
        ],
        industry="Employment",
        authority_level="medium",
        notes="UGC reviews platform, rarely cited as authoritative source",
    ),
    # News/media sites with paywalls or non-technical focus
    TestSite(
        url="https://www.bloomberg.com",
        name="Bloomberg",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "financial markets analysis",
            "economic news",
        ],
        industry="Finance/News",
        authority_level="high",
        notes="Paywalled financial news, AI can't access full content",
    ),
    TestSite(
        url="https://www.nytimes.com",
        name="New York Times",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "current events analysis",
            "investigative journalism",
        ],
        industry="News",
        authority_level="high",
        notes="Major newspaper but heavily paywalled; AI models avoid citing",
    ),
    # Affiliate / comparison content
    TestSite(
        url="https://www.pcmag.com",
        name="PCMag",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best laptops 2024",
            "VPN reviews",
        ],
        industry="Tech Reviews",
        authority_level="medium",
        notes="Review/affiliate site; AI prefers manufacturer docs over reviews",
    ),
    TestSite(
        url="https://www.trustpilot.com",
        name="Trustpilot",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "company reviews and ratings",
            "consumer trust score",
        ],
        industry="Reviews",
        authority_level="medium",
        notes="UGC review aggregator, not an authoritative source for AI",
    ),
    # E-commerce sites — AI doesn't cite product listings
    TestSite(
        url="https://www.amazon.com",
        name="Amazon",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best wireless headphones",
            "laptop deals",
        ],
        industry="E-commerce",
        authority_level="high",
        notes="Largest e-commerce platform but AI doesn't cite product listings",
    ),
    TestSite(
        url="https://www.ebay.com",
        name="eBay",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "buy used electronics",
            "online auction platform",
        ],
        industry="E-commerce",
        authority_level="high",
        notes="Major marketplace, AI prefers authoritative product reviews",
    ),
    TestSite(
        url="https://www.target.com",
        name="Target",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "home decor shopping",
            "best kitchen appliances",
        ],
        industry="Retail",
        authority_level="high",
        notes="Major retailer, product pages not cited by AI",
    ),
    TestSite(
        url="https://www.bestbuy.com",
        name="Best Buy",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best gaming monitors",
            "laptop buying guide",
        ],
        industry="Electronics Retail",
        authority_level="high",
        notes="Electronics retailer, AI cites tech publications instead",
    ),
    TestSite(
        url="https://www.wayfair.com",
        name="Wayfair",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "buy furniture online",
            "home office desk",
        ],
        industry="Furniture E-commerce",
        authority_level="medium",
        notes="Furniture e-commerce, product listings not cited",
    ),
    # SaaS marketing — high pillar scores but low citation rates
    TestSite(
        url="https://www.zendesk.com",
        name="Zendesk",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "customer support software",
            "help desk ticketing system",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="SaaS marketing, AI cites category leaders or docs instead",
    ),
    TestSite(
        url="https://www.asana.com",
        name="Asana",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "project management tools",
            "team collaboration software",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="Project management SaaS, competes with many alternatives",
    ),
    TestSite(
        url="https://www.monday.com",
        name="Monday.com",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "work management platform",
            "project tracking software",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="Work management SaaS, generic marketing content",
    ),
    TestSite(
        url="https://www.notion.so",
        name="Notion",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "note-taking app comparison",
            "productivity tools",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="Productivity SaaS, marketing pages not cited (docs might be)",
    ),
    TestSite(
        url="https://mailchimp.com",
        name="Mailchimp",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "email marketing platform",
            "email automation tools",
        ],
        industry="Marketing Tech",
        authority_level="medium",
        notes="Email marketing SaaS, marketing content generic",
    ),
    TestSite(
        url="https://www.intercom.com",
        name="Intercom",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "customer messaging platform",
            "live chat software",
        ],
        industry="SaaS",
        authority_level="medium",
        notes="Customer messaging SaaS, generic marketing site",
    ),
    # News/media — AI trains on but rarely cites
    TestSite(
        url="https://www.reuters.com",
        name="Reuters",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "breaking news",
            "world news updates",
        ],
        industry="News",
        authority_level="high",
        notes="Major wire service, but AI avoids citing news for factual queries",
    ),
    TestSite(
        url="https://techcrunch.com",
        name="TechCrunch",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "startup funding news",
            "tech industry trends",
        ],
        industry="Tech News",
        authority_level="high",
        notes="Major tech news site, time-sensitive content not cited for evergreen queries",
    ),
    TestSite(
        url="https://www.theverge.com",
        name="The Verge",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "technology news",
            "gadget reviews",
        ],
        industry="Tech News",
        authority_level="high",
        notes="Tech news/reviews, AI prefers manufacturer docs",
    ),
    TestSite(
        url="https://www.wired.com",
        name="Wired",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "technology culture",
            "science and tech reporting",
        ],
        industry="Tech Media",
        authority_level="high",
        notes="Tech media, content is commentary not primary source",
    ),
    TestSite(
        url="https://arstechnica.com",
        name="Ars Technica",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "tech analysis",
            "science news",
        ],
        industry="Tech Media",
        authority_level="high",
        notes="In-depth tech reporting but not primary source material",
    ),
    # UGC / Community platforms
    TestSite(
        url="https://www.quora.com",
        name="Quora",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "expert answers to questions",
            "community knowledge sharing",
        ],
        industry="Q&A Platform",
        authority_level="medium",
        notes="UGC Q&A platform, AI models don't cite crowd-sourced answers",
    ),
    TestSite(
        url="https://www.tripadvisor.com",
        name="TripAdvisor",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best restaurants in Paris",
            "hotel reviews",
        ],
        industry="Travel",
        authority_level="medium",
        notes="Travel UGC platform, AI summarizes rather than cites",
    ),
    TestSite(
        url="https://www.imdb.com",
        name="IMDB",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best movies of all time",
            "movie ratings and reviews",
        ],
        industry="Entertainment",
        authority_level="high",
        notes="Movie database, AI knows the data but rarely cites IMDB URLs",
    ),
    TestSite(
        url="https://www.producthunt.com",
        name="Product Hunt",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "new startup launches",
            "best new apps",
        ],
        industry="Tech Community",
        authority_level="medium",
        notes="Product launch UGC platform, not cited as authoritative",
    ),
    # Mixed / Social platforms
    TestSite(
        url="https://medium.com",
        name="Medium",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "technology blog posts",
            "startup advice articles",
        ],
        industry="Publishing Platform",
        authority_level="medium",
        notes="Publishing platform, individual articles rarely cited (not authoritative)",
    ),
    TestSite(
        url="https://substack.com",
        name="Substack",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "newsletter platforms",
            "independent journalism",
        ],
        industry="Publishing Platform",
        authority_level="medium",
        notes="Newsletter platform, individual writers not canonical sources",
    ),
    # Affiliate / listicle sites
    TestSite(
        url="https://www.tomsguide.com",
        name="Tom's Guide",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "best phones 2025",
            "tech product recommendations",
        ],
        industry="Tech Reviews",
        authority_level="medium",
        notes="Affiliate review site, AI prefers manufacturer sources",
    ),
    TestSite(
        url="https://www.cnet.com",
        name="CNET",
        category=SiteCategory.KNOWN_UNCITED,
        expected_queries=[
            "technology reviews",
            "best streaming services",
        ],
        industry="Tech Reviews",
        authority_level="medium",
        notes="Tech review/affiliate site, derivative content",
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
    TestSite(
        url="https://www.peec.ai",
        name="Peec AI",
        category=SiteCategory.COMPETITOR,
        expected_queries=[
            "AI search optimization",
            "GEO monitoring tool",
        ],
        industry="AI SEO",
        authority_level="medium",
        notes="Direct competitor - AI visibility tool, $29M funded",
    ),
    TestSite(
        url="https://scrunch.ai",
        name="Scrunch AI",
        category=SiteCategory.COMPETITOR,
        expected_queries=[
            "AI content optimization",
            "AI search rankings",
        ],
        industry="AI SEO",
        authority_level="medium",
        notes="Direct competitor - AI optimization tool, $26M funded",
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
        # Pick a representative sample: 1 cited authority, 1 cited docs, 1 uncited SaaS, own properties
        return cls(
            sites=[
                KNOWN_CITED_SITES[0],  # Moz (SEO authority)
                KNOWN_CITED_SITES[6],  # Schema.org (technical reference)
                KNOWN_UNCITED_SITES[0],  # Reddit SEO (UGC)
                KNOWN_UNCITED_SITES[3],  # Lemlist (SaaS marketing)
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
