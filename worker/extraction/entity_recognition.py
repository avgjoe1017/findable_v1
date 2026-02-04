"""
Entity Recognition Module

Measures brand/entity recognition signals to capture why some technically
poor sites get cited (training data prevalence, brand recognition) while
some technically good sites don't (unknown brands).

This addresses the 23% pessimism bias in the Findable Score model.

Signals measured:
- Wikipedia presence and quality
- Wikidata entity existence
- Domain age and establishment
- Web presence (search result volume)
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import httpx

logger = logging.getLogger(__name__)


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class WikipediaSignals:
    """Signals from Wikipedia presence."""

    has_page: bool = False
    page_url: str | None = None
    page_title: str | None = None
    page_length_chars: int = 0
    page_sections: int = 0
    citation_count: int = 0
    infobox_present: bool = False
    last_edited: datetime | None = None

    # Derived scores
    score: int = 0
    max_score: int = 30

    def calculate_score(self) -> int:
        """Calculate Wikipedia presence score (0-30)."""
        score = 0

        if self.has_page:
            score += 15  # Base points for having a page

            # Page quality signals
            if self.page_length_chars > 10000:
                score += 5
            elif self.page_length_chars > 5000:
                score += 3
            elif self.page_length_chars > 2000:
                score += 1

            # Citation quality
            if self.citation_count > 50:
                score += 5
            elif self.citation_count > 20:
                score += 3
            elif self.citation_count > 5:
                score += 1

            # Structure signals
            if self.infobox_present:
                score += 2

            if self.page_sections > 10:
                score += 2
            elif self.page_sections > 5:
                score += 1

            # Freshness (edited in last year)
            if self.last_edited:
                now = datetime.now(UTC) if self.last_edited.tzinfo else datetime.now()
                if now - self.last_edited < timedelta(days=365):
                    score += 1

        self.score = min(score, self.max_score)
        return self.score


@dataclass
class WikidataSignals:
    """Signals from Wikidata entity presence."""

    has_entity: bool = False
    entity_id: str | None = None  # e.g., "Q312"
    entity_url: str | None = None
    label: str | None = None
    description: str | None = None
    property_count: int = 0
    sitelink_count: int = 0  # Number of Wikipedia pages in different languages
    instance_of: list[str] = field(default_factory=list)  # e.g., ["company", "website"]

    # Derived scores
    score: int = 0
    max_score: int = 20

    def calculate_score(self) -> int:
        """Calculate Wikidata presence score (0-20)."""
        score = 0

        if self.has_entity:
            score += 10  # Base points for having an entity

            # Property richness
            if self.property_count > 50:
                score += 4
            elif self.property_count > 20:
                score += 2
            elif self.property_count > 10:
                score += 1

            # International presence (sitelinks)
            if self.sitelink_count > 50:
                score += 4
            elif self.sitelink_count > 20:
                score += 3
            elif self.sitelink_count > 5:
                score += 2
            elif self.sitelink_count > 1:
                score += 1

            # Entity type classification
            notable_types = ["company", "organization", "software", "website", "brand"]
            if any(t in " ".join(self.instance_of).lower() for t in notable_types):
                score += 2

        self.score = min(score, self.max_score)
        return self.score


@dataclass
class DomainSignals:
    """Signals from domain registration and history."""

    domain: str = ""
    creation_date: datetime | None = None
    domain_age_years: float = 0.0
    registrar: str | None = None
    is_registered: bool = False

    # TLD signals
    tld: str = ""
    is_premium_tld: bool = False  # .com, .org, .net
    is_country_tld: bool = False  # .uk, .de, etc.

    # Derived scores
    score: int = 0
    max_score: int = 20

    def calculate_score(self) -> int:
        """Calculate domain age/establishment score (0-20)."""
        score = 0

        if self.is_registered:
            # Domain age (biggest signal)
            if self.domain_age_years >= 20:
                score += 10
            elif self.domain_age_years >= 10:
                score += 8
            elif self.domain_age_years >= 5:
                score += 5
            elif self.domain_age_years >= 2:
                score += 3
            elif self.domain_age_years >= 1:
                score += 1

            # TLD quality
            if self.is_premium_tld:
                score += 5
            elif self.is_country_tld:
                score += 3

            # Short domain bonus (brandable)
            domain_name = self.domain.split(".")[0] if self.domain else ""
            if len(domain_name) <= 6:
                score += 3
            elif len(domain_name) <= 10:
                score += 1

        self.score = min(score, self.max_score)
        return self.score


@dataclass
class WebPresenceSignals:
    """Signals from general web presence."""

    brand_name: str = ""

    # Search presence
    google_results_estimate: int = 0
    bing_results_estimate: int = 0

    # Social signals (optional, rate-limited)
    twitter_followers: int | None = None
    linkedin_followers: int | None = None
    github_stars: int | None = None

    # News presence
    news_mentions_30d: int = 0
    news_sources: list[str] = field(default_factory=list)

    # Derived scores
    score: int = 0
    max_score: int = 30

    def calculate_score(self) -> int:
        """Calculate web presence score (0-30)."""
        score = 0

        # Search result volume (biggest signal)
        total_results = max(self.google_results_estimate, self.bing_results_estimate)

        if total_results > 100_000_000:
            score += 15
        elif total_results > 10_000_000:
            score += 12
        elif total_results > 1_000_000:
            score += 9
        elif total_results > 100_000:
            score += 6
        elif total_results > 10_000:
            score += 3
        elif total_results > 1_000:
            score += 1

        # News presence
        if self.news_mentions_30d > 100:
            score += 8
        elif self.news_mentions_30d > 20:
            score += 5
        elif self.news_mentions_30d > 5:
            score += 3
        elif self.news_mentions_30d > 0:
            score += 1

        # Prestigious news sources
        prestigious = ["nytimes", "wsj", "bbc", "reuters", "techcrunch", "forbes"]
        prestigious_count = sum(
            1 for s in self.news_sources if any(p in s.lower() for p in prestigious)
        )
        if prestigious_count >= 3:
            score += 5
        elif prestigious_count >= 1:
            score += 2

        # Social signals (bonus, not required)
        if self.twitter_followers and self.twitter_followers > 100_000:
            score += 2
        if self.github_stars and self.github_stars > 10_000:
            score += 2

        self.score = min(score, self.max_score)
        return self.score


@dataclass
class EntityReinforcementSignals:
    """Signals measuring how well the brand is reinforced in page content.

    Per GEO/AEO spec: "Core entities to reinforce on this page
    (copy should echo these verbatim)"

    Measures:
    - Brand mention frequency and placement
    - Entity consistency across page
    - Presence in key locations (headings, first paragraph)
    """

    brand_name: str = ""

    # Mention analysis
    total_mentions: int = 0
    mentions_in_headings: int = 0
    mentions_in_first_para: int = 0
    mentions_per_500_words: float = 0.0

    # Placement quality
    in_h1: bool = False
    in_h2: bool = False
    in_first_100_words: bool = False
    in_meta_title: bool = False
    in_meta_description: bool = False

    # Consistency (brand name variations)
    consistent_casing: bool = True
    name_variations_found: list[str] = field(default_factory=list)

    # Related entities mentioned
    related_entities: list[str] = field(default_factory=list)

    # Derived scores
    score: int = 0
    max_score: int = 20

    def calculate_score(self) -> int:
        """Calculate entity reinforcement score (0-20)."""
        score = 0

        # Brand mention frequency
        if self.mentions_per_500_words >= 2.0:
            score += 5
        elif self.mentions_per_500_words >= 1.0:
            score += 3
        elif self.mentions_per_500_words >= 0.5:
            score += 1

        # Key placement
        if self.in_h1:
            score += 3
        if self.mentions_in_headings >= 2:
            score += 2
        elif self.mentions_in_headings >= 1:
            score += 1

        if self.in_first_100_words:
            score += 2

        # Meta presence
        if self.in_meta_title:
            score += 2
        if self.in_meta_description:
            score += 1

        # Consistency
        if self.consistent_casing:
            score += 2
        else:
            score -= 1  # Penalty for inconsistent casing

        # Related entities add context
        if len(self.related_entities) >= 3:
            score += 2
        elif len(self.related_entities) >= 1:
            score += 1

        self.score = min(max(0, score), self.max_score)
        return self.score


@dataclass
class EntityRecognitionResult:
    """Complete entity recognition analysis result."""

    domain: str
    brand_name: str

    # Component signals
    wikipedia: WikipediaSignals = field(default_factory=WikipediaSignals)
    wikidata: WikidataSignals = field(default_factory=WikidataSignals)
    domain_signals: DomainSignals = field(default_factory=DomainSignals)
    web_presence: WebPresenceSignals = field(default_factory=WebPresenceSignals)
    # GEO/AEO addition
    reinforcement: EntityReinforcementSignals = field(default_factory=EntityReinforcementSignals)

    # Aggregate score
    total_score: int = 0
    max_score: int = 120  # Updated to include reinforcement (20 pts)
    normalized_score: float = 0.0  # 0-100 scale

    # Metadata
    analysis_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    errors: list[str] = field(default_factory=list)

    def calculate_total_score(self) -> int:
        """Calculate total entity recognition score."""
        self.wikipedia.calculate_score()
        self.wikidata.calculate_score()
        self.domain_signals.calculate_score()
        self.web_presence.calculate_score()
        self.reinforcement.calculate_score()

        self.total_score = (
            self.wikipedia.score
            + self.wikidata.score
            + self.domain_signals.score
            + self.web_presence.score
            + self.reinforcement.score
        )

        self.normalized_score = (self.total_score / self.max_score) * 100
        return self.total_score

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "domain": self.domain,
            "brand_name": self.brand_name,
            "total_score": self.total_score,
            "normalized_score": round(self.normalized_score, 1),
            "max_score": self.max_score,
            "components": {
                "wikipedia": {
                    "score": self.wikipedia.score,
                    "max_score": self.wikipedia.max_score,
                    "has_page": self.wikipedia.has_page,
                    "page_url": self.wikipedia.page_url,
                    "page_length_chars": self.wikipedia.page_length_chars,
                    "citation_count": self.wikipedia.citation_count,
                },
                "wikidata": {
                    "score": self.wikidata.score,
                    "max_score": self.wikidata.max_score,
                    "has_entity": self.wikidata.has_entity,
                    "entity_id": self.wikidata.entity_id,
                    "property_count": self.wikidata.property_count,
                    "sitelink_count": self.wikidata.sitelink_count,
                },
                "domain": {
                    "score": self.domain_signals.score,
                    "max_score": self.domain_signals.max_score,
                    "domain_age_years": round(self.domain_signals.domain_age_years, 1),
                    "is_premium_tld": self.domain_signals.is_premium_tld,
                },
                "web_presence": {
                    "score": self.web_presence.score,
                    "max_score": self.web_presence.max_score,
                    "search_results_estimate": self.web_presence.google_results_estimate,
                    "news_mentions_30d": self.web_presence.news_mentions_30d,
                },
                "reinforcement": {
                    "score": self.reinforcement.score,
                    "max_score": self.reinforcement.max_score,
                    "total_mentions": self.reinforcement.total_mentions,
                    "mentions_per_500_words": round(self.reinforcement.mentions_per_500_words, 2),
                    "in_h1": self.reinforcement.in_h1,
                    "in_first_100_words": self.reinforcement.in_first_100_words,
                    "in_meta_title": self.reinforcement.in_meta_title,
                    "consistent_casing": self.reinforcement.consistent_casing,
                },
            },
            "errors": self.errors,
            "timestamp": self.analysis_timestamp.isoformat(),
        }


# =============================================================================
# API Clients
# =============================================================================


class WikipediaClient:
    """Client for Wikipedia API queries."""

    BASE_URL = "https://en.wikipedia.org/w/api.php"
    USER_AGENT = "FindableScore/1.0 (https://findablescore.com; contact@findablescore.com)"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {"User-Agent": self.USER_AGENT}

    async def search_entity(self, brand_name: str) -> str | None:
        """Search for a Wikipedia page by brand name. Returns page title if found."""
        params = {
            "action": "query",
            "list": "search",
            "srsearch": brand_name,
            "srlimit": 5,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("query", {}).get("search", [])
            if results:
                # Return first result that looks like a match
                for result in results:
                    title = result.get("title", "")
                    # Basic matching - title contains brand or vice versa
                    if brand_name.lower() in title.lower() or title.lower() in brand_name.lower():
                        return title
                # Fallback to first result
                return results[0].get("title")

        return None

    async def get_page_info(self, title: str) -> WikipediaSignals:
        """Get detailed information about a Wikipedia page."""
        signals = WikipediaSignals()

        params = {
            "action": "query",
            "titles": title,
            "prop": "info|revisions|categories|templates",
            "rvprop": "size|timestamp",
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            pages = data.get("query", {}).get("pages", {})
            for page_id, page in pages.items():
                if page_id == "-1":  # Page doesn't exist
                    return signals

                signals.has_page = True
                signals.page_title = page.get("title")
                signals.page_url = f"https://en.wikipedia.org/wiki/{quote(signals.page_title)}"

                # Get page size from revisions
                revisions = page.get("revisions", [])
                if revisions:
                    signals.page_length_chars = revisions[0].get("size", 0)
                    timestamp = revisions[0].get("timestamp")
                    if timestamp:
                        signals.last_edited = datetime.fromisoformat(
                            timestamp.replace("Z", "+00:00")
                        )

                # Count categories as proxy for sections
                categories = page.get("categories", [])
                signals.page_sections = len(categories)

                # Check for infobox
                templates = page.get("templates", [])
                signals.infobox_present = any(
                    "infobox" in t.get("title", "").lower() for t in templates
                )

        # Get citation count with separate query
        signals.citation_count = await self._get_citation_count(title)

        return signals

    async def _get_citation_count(self, title: str) -> int:
        """Count references/citations on a Wikipedia page."""
        params = {
            "action": "parse",
            "page": title,
            "prop": "wikitext",
            "format": "json",
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
                response = await client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

                wikitext = data.get("parse", {}).get("wikitext", {}).get("*", "")
                # Count <ref> tags as proxy for citations
                return len(re.findall(r"<ref", wikitext, re.IGNORECASE))
        except Exception:
            return 0


class WikidataClient:
    """Client for Wikidata API queries."""

    BASE_URL = "https://www.wikidata.org/w/api.php"
    USER_AGENT = "FindableScore/1.0 (https://findablescore.com; contact@findablescore.com)"

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {"User-Agent": self.USER_AGENT}

    async def search_entity(self, brand_name: str) -> str | None:
        """Search for a Wikidata entity by brand name. Returns entity ID if found."""
        params = {
            "action": "wbsearchentities",
            "search": brand_name,
            "language": "en",
            "limit": 5,
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            results = data.get("search", [])
            if results:
                return results[0].get("id")

        return None

    async def get_entity_info(self, entity_id: str) -> WikidataSignals:
        """Get detailed information about a Wikidata entity."""
        signals = WikidataSignals()

        params = {
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "labels|descriptions|claims|sitelinks",
            "languages": "en",
            "format": "json",
        }

        async with httpx.AsyncClient(timeout=self.timeout, headers=self.headers) as client:
            response = await client.get(self.BASE_URL, params=params)
            response.raise_for_status()
            data = response.json()

            entities = data.get("entities", {})
            entity = entities.get(entity_id, {})

            if not entity or "missing" in entity:
                return signals

            signals.has_entity = True
            signals.entity_id = entity_id
            signals.entity_url = f"https://www.wikidata.org/wiki/{entity_id}"

            # Get label and description
            labels = entity.get("labels", {})
            if "en" in labels:
                signals.label = labels["en"].get("value")

            descriptions = entity.get("descriptions", {})
            if "en" in descriptions:
                signals.description = descriptions["en"].get("value")

            # Count properties (claims)
            claims = entity.get("claims", {})
            signals.property_count = len(claims)

            # Get instance_of (P31)
            if "P31" in claims:
                for claim in claims["P31"]:
                    mainsnak = claim.get("mainsnak", {})
                    datavalue = mainsnak.get("datavalue", {})
                    if datavalue.get("type") == "wikibase-entityid":
                        entity_ref = datavalue.get("value", {}).get("id")
                        if entity_ref:
                            signals.instance_of.append(entity_ref)

            # Count sitelinks
            sitelinks = entity.get("sitelinks", {})
            signals.sitelink_count = len(sitelinks)

        return signals


class DomainAgeClient:
    """Client for domain WHOIS queries via RDAP."""

    RDAP_SERVERS = {
        "com": "https://rdap.verisign.com/com/v1/domain/",
        "net": "https://rdap.verisign.com/net/v1/domain/",
        "org": "https://rdap.publicinterestregistry.org/rdap/domain/",
        "io": "https://rdap.nic.io/domain/",
        "ai": "https://rdap.nic.ai/domain/",
        "co": "https://rdap.nic.co/domain/",
    }

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def get_domain_info(self, domain: str) -> DomainSignals:
        """Get domain registration information."""
        signals = DomainSignals()
        signals.domain = domain

        # Parse TLD
        parts = domain.split(".")
        if len(parts) >= 2:
            signals.tld = parts[-1].lower()
            signals.is_premium_tld = signals.tld in ["com", "org", "net"]
            signals.is_country_tld = len(signals.tld) == 2 and signals.tld not in ["ai", "io", "co"]

        # Try RDAP lookup
        rdap_url = self.RDAP_SERVERS.get(signals.tld)
        if rdap_url:
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.get(f"{rdap_url}{domain}")
                    if response.status_code == 200:
                        data = response.json()
                        signals.is_registered = True

                        # Find registration date
                        events = data.get("events", [])
                        for event in events:
                            if event.get("eventAction") == "registration":
                                date_str = event.get("eventDate")
                                if date_str:
                                    signals.creation_date = datetime.fromisoformat(
                                        date_str.replace("Z", "+00:00")
                                    )
                                    now = datetime.now(UTC)
                                    age = now - signals.creation_date
                                    signals.domain_age_years = age.days / 365.25
                                break

                        # Get registrar
                        entities = data.get("entities", [])
                        for entity in entities:
                            if "registrar" in entity.get("roles", []):
                                vcard = entity.get("vcardArray", [])
                                if len(vcard) > 1:
                                    for item in vcard[1]:
                                        if item[0] == "fn":
                                            signals.registrar = item[3]
                                            break
            except Exception as e:
                logger.warning(f"RDAP lookup failed for {domain}: {e}")

        # Fallback: assume registered if we can resolve DNS
        if not signals.is_registered:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.head(f"https://{domain}", follow_redirects=True)
                    signals.is_registered = response.status_code < 500
            except Exception:
                pass

        return signals


class WebPresenceClient:
    """Client for measuring web presence signals."""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    async def estimate_search_results(self, brand_name: str) -> int:
        """Estimate number of search results for a brand."""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                # Use DuckDuckGo instant answer API as a free proxy
                response = await client.get(
                    "https://api.duckduckgo.com/",
                    params={"q": brand_name, "format": "json", "no_html": 1},
                )

                if response.status_code == 200:
                    data = response.json()
                    # If DDG has an abstract, brand is known
                    if data.get("Abstract"):
                        return 1_000_000  # Placeholder - known brand
                    elif data.get("RelatedTopics"):
                        return 100_000  # Some presence
        except Exception as e:
            logger.warning(f"Search estimate failed for {brand_name}: {e}")

        return 0

    async def check_news_presence(self, _brand_name: str) -> tuple[int, list[str]]:
        """Check for recent news mentions. Returns (mention_count, source_domains)."""
        # Placeholder - would need a real news API in production
        return 0, []


# =============================================================================
# Main Analyzer
# =============================================================================


class EntityRecognitionAnalyzer:
    """
    Main analyzer that orchestrates entity recognition scoring.

    Usage:
        analyzer = EntityRecognitionAnalyzer()
        result = await analyzer.analyze("stripe.com", "Stripe")
        print(result.normalized_score)  # 0-100
    """

    def __init__(
        self,
        timeout: float = 10.0,
        skip_web_presence: bool = False,
    ):
        self.wikipedia = WikipediaClient(timeout=timeout)
        self.wikidata = WikidataClient(timeout=timeout)
        self.domain_client = DomainAgeClient(timeout=timeout)
        self.web_presence = WebPresenceClient(timeout=timeout)
        self.skip_web_presence = skip_web_presence

    async def analyze(
        self,
        domain: str,
        brand_name: str | None = None,
        html_content: str | None = None,
        main_text: str | None = None,
        word_count: int = 0,
    ) -> EntityRecognitionResult:
        """
        Analyze entity recognition signals for a domain/brand.

        Args:
            domain: The domain to analyze (e.g., "stripe.com")
            brand_name: The brand name to search for. If not provided,
                        will be extracted from domain.
            html_content: Optional HTML for entity reinforcement analysis
            main_text: Optional extracted text content
            word_count: Word count of content (for mention density)

        Returns:
            EntityRecognitionResult with all signals and scores.
        """
        # Extract brand name from domain if not provided
        if not brand_name:
            brand_name = self._extract_brand_name(domain)

        result = EntityRecognitionResult(
            domain=domain,
            brand_name=brand_name,
        )

        # Run all checks concurrently
        tasks = [
            self._check_wikipedia(brand_name, result),
            self._check_wikidata(brand_name, result),
            self._check_domain(domain, result),
        ]

        if not self.skip_web_presence:
            tasks.append(self._check_web_presence(brand_name, result))

        await asyncio.gather(*tasks, return_exceptions=True)

        # Analyze entity reinforcement if content provided (GEO/AEO)
        if html_content or main_text:
            self._analyze_reinforcement(brand_name, result, html_content, main_text, word_count)

        # Calculate total score
        result.calculate_total_score()

        return result

    def _extract_brand_name(self, domain: str) -> str:
        """Extract likely brand name from domain."""
        # Remove TLD
        name = domain.split(".")[0]

        # Handle common patterns
        name = re.sub(r"^(www|app|api|docs|blog)\.", "", name)

        # Convert to title case for search
        return name.title()

    def _analyze_reinforcement(
        self,
        brand_name: str,
        result: EntityRecognitionResult,
        html_content: str | None,
        main_text: str | None,
        word_count: int,
    ) -> None:
        """Analyze entity reinforcement in page content (GEO/AEO).

        Measures how consistently the brand is echoed in the content.
        """
        from bs4 import BeautifulSoup

        reinforcement = EntityReinforcementSignals(brand_name=brand_name)

        # Parse HTML if provided
        soup = None
        if html_content:
            soup = BeautifulSoup(html_content, "html.parser")

        # Get text content
        text = main_text or ""
        if not text and soup:
            main_el = soup.find("main") or soup.find("article") or soup.body
            if main_el:
                text = main_el.get_text(separator=" ", strip=True)

        if not text:
            result.reinforcement = reinforcement
            return

        # Count brand mentions (case-insensitive)
        brand_pattern = re.compile(re.escape(brand_name), re.IGNORECASE)
        mentions = brand_pattern.findall(text)
        reinforcement.total_mentions = len(mentions)

        # Calculate mention density
        wc = word_count if word_count > 0 else len(text.split())
        if wc > 0:
            reinforcement.mentions_per_500_words = (reinforcement.total_mentions / wc) * 500

        # Check first 100 words
        first_100_words = " ".join(text.split()[:100])
        if brand_pattern.search(first_100_words):
            reinforcement.in_first_100_words = True

        # Analyze HTML elements if available
        if soup:
            # Check H1
            h1 = soup.find("h1")
            if h1 and brand_pattern.search(h1.get_text()):
                reinforcement.in_h1 = True

            # Check all headings
            for h in soup.find_all(["h1", "h2", "h3", "h4"]):
                if brand_pattern.search(h.get_text()):
                    reinforcement.mentions_in_headings += 1

            # Check meta title
            title_tag = soup.find("title")
            if title_tag and brand_pattern.search(title_tag.get_text()):
                reinforcement.in_meta_title = True

            # Check meta description
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                desc_content = meta_desc.get("content", "")
                if brand_pattern.search(desc_content):
                    reinforcement.in_meta_description = True

            # Check first paragraph
            first_p = soup.find("p")
            if first_p and brand_pattern.search(first_p.get_text()):
                reinforcement.mentions_in_first_para = 1

        # Check casing consistency
        if mentions:
            unique_casings = set(mentions)
            # If more than 2 variations, inconsistent (allow "Brand" and "brand")
            if len(unique_casings) > 2:
                reinforcement.consistent_casing = False
            reinforcement.name_variations_found = list(unique_casings)[:5]

        # Look for related entities (common co-occurring terms)
        # This is a simple heuristic - look for other capitalized words near brand
        related = []
        sentences_with_brand = re.findall(
            r"[^.!?]*" + re.escape(brand_name) + r"[^.!?]*[.!?]", text, re.IGNORECASE
        )
        for sentence in sentences_with_brand[:10]:
            # Find other proper nouns
            words = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b", sentence)
            for word in words:
                if word.lower() != brand_name.lower() and word not in related:
                    related.append(word)

        reinforcement.related_entities = related[:10]

        result.reinforcement = reinforcement

    async def _check_wikipedia(self, brand_name: str, result: EntityRecognitionResult) -> None:
        """Check Wikipedia presence."""
        try:
            title = await self.wikipedia.search_entity(brand_name)
            if title:
                result.wikipedia = await self.wikipedia.get_page_info(title)
            else:
                result.wikipedia = WikipediaSignals()
        except Exception as e:
            logger.error(f"Wikipedia check failed for {brand_name}: {e}")
            result.errors.append(f"Wikipedia: {str(e)}")
            result.wikipedia = WikipediaSignals()

    async def _check_wikidata(self, brand_name: str, result: EntityRecognitionResult) -> None:
        """Check Wikidata entity presence."""
        try:
            entity_id = await self.wikidata.search_entity(brand_name)
            if entity_id:
                result.wikidata = await self.wikidata.get_entity_info(entity_id)
            else:
                result.wikidata = WikidataSignals()
        except Exception as e:
            logger.error(f"Wikidata check failed for {brand_name}: {e}")
            result.errors.append(f"Wikidata: {str(e)}")
            result.wikidata = WikidataSignals()

    async def _check_domain(self, domain: str, result: EntityRecognitionResult) -> None:
        """Check domain registration signals."""
        try:
            result.domain_signals = await self.domain_client.get_domain_info(domain)
        except Exception as e:
            logger.error(f"Domain check failed for {domain}: {e}")
            result.errors.append(f"Domain: {str(e)}")
            result.domain_signals = DomainSignals(domain=domain)

    async def _check_web_presence(self, brand_name: str, result: EntityRecognitionResult) -> None:
        """Check web presence signals."""
        try:
            result.web_presence.brand_name = brand_name
            result.web_presence.google_results_estimate = (
                await self.web_presence.estimate_search_results(brand_name)
            )
            mentions, sources = await self.web_presence.check_news_presence(brand_name)
            result.web_presence.news_mentions_30d = mentions
            result.web_presence.news_sources = sources
        except Exception as e:
            logger.error(f"Web presence check failed for {brand_name}: {e}")
            result.errors.append(f"Web presence: {str(e)}")
            result.web_presence = WebPresenceSignals(brand_name=brand_name)


# =============================================================================
# Convenience Functions
# =============================================================================


async def get_entity_recognition_score(
    domain: str,
    brand_name: str | None = None,
    fast_mode: bool = False,
) -> tuple[float, dict]:
    """
    Convenience function to get entity recognition score for Findable Score integration.

    Args:
        domain: The domain to analyze
        brand_name: Optional brand name override
        fast_mode: Skip slow checks (web presence)

    Returns:
        Tuple of (normalized_score, details_dict)
    """
    analyzer = EntityRecognitionAnalyzer(skip_web_presence=fast_mode)
    result = await analyzer.analyze(domain, brand_name)
    return result.normalized_score, result.to_dict()
