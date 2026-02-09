"""Authority signal extraction and analysis.

Extracts E-E-A-T (Experience, Expertise, Authoritativeness, Trustworthiness)
signals that help AI systems trust and cite content.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from urllib.parse import urlparse

import structlog
from bs4 import BeautifulSoup, Tag

logger = structlog.get_logger(__name__)


# Patterns that indicate original research/data
ORIGINAL_DATA_PATTERNS = [
    r"\bour\s+(?:research|study|data|survey|analysis|findings|report)\b",
    r"\bwe\s+(?:found|discovered|analyzed|surveyed|studied|measured|tested)\b",
    r"\bour\s+(?:team|experts?|researchers?|analysts?)\b",
    r"\baccording\s+to\s+our\b",
    r"\bbased\s+on\s+our\s+(?:research|data|analysis)\b",
    r"\b(?:in|from)\s+our\s+(?:2\d{3}|latest)\s+(?:study|survey|report)\b",
    r"\bproprietary\s+(?:data|research|methodology)\b",
    r"\boriginal\s+(?:research|data|findings)\b",
]

# Patterns for author byline detection
AUTHOR_BYLINE_PATTERNS = [
    r"\bby\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",  # "By John Smith"
    r"\bwritten\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    r"\bauthor[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
    r"\breviewed\s+by\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
]

# Job titles/credentials that indicate expertise
CREDENTIAL_PATTERNS = [
    r"\b(?:Ph\.?D\.?|M\.?D\.?|J\.?D\.?|MBA|CPA|CFA)\b",
    r"\b(?:Dr\.|Professor|Prof\.)\s+",
    r"\b(?:CEO|CTO|CFO|COO|President|Director|Manager|Lead|Head|Chief)\b",
    r"\b(?:Senior|Principal|Expert|Specialist|Consultant)\b",
    r"\b(?:years?\s+of\s+experience|industry\s+expert)\b",
    r"\b(?:certified|licensed|registered)\s+\w+",
    r"\b(?:author\s+of|published\s+in|featured\s+in)\b",
]

# Domains that indicate authoritative citations
AUTHORITATIVE_DOMAINS = {
    # Academic (.edu matches stanford.edu, mit.edu, etc.)
    "edu",
    "ac.uk",
    # Government (.gov matches cdc.gov, nih.gov, etc.)
    "gov",
    "gov.uk",
    "europa.eu",
    # Academic publishers & research
    "nature.com",
    "science.org",
    "sciencedirect.com",
    "springer.com",
    "wiley.com",
    "pubmed.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",
    "nih.gov",
    "scholar.google.com",
    "arxiv.org",
    "researchgate.net",
    "jstor.org",
    "ssrn.com",
    "acm.org",
    "ieee.org",
    "plos.org",
    "frontiersin.org",
    # AI/Tech research labs
    "openai.com",
    "deepmind.com",
    "research.google",
    "ai.meta.com",
    "research.microsoft.com",
    "ai.google",
    "anthropic.com",
    # Major news
    "nytimes.com",
    "wsj.com",
    "washingtonpost.com",
    "bbc.com",
    "bbc.co.uk",
    "reuters.com",
    "apnews.com",
    "economist.com",
    "ft.com",
    "theguardian.com",
    # Business/research firms
    "bloomberg.com",
    "hbr.org",
    "mckinsey.com",
    "forrester.com",
    "gartner.com",
    "deloitte.com",
    "pwc.com",
    "bcg.com",
    "bain.com",
    # Tech documentation & standards
    "github.com",
    "stackoverflow.com",
    "developer.mozilla.org",
    "docs.python.org",
    "w3.org",
    "ietf.org",
    "iso.org",
    "rfc-editor.org",
    # Wikipedia (often used as reference)
    "wikipedia.org",
    "wikimedia.org",
    # Security & compliance certification bodies
    "aicpa.org",
    "aicpa-cima.com",  # SOC 2 (AICPA)
    "bsigroup.com",  # ISO certification body
    "tuv.com",
    "tuvsud.com",
    "tuvnord.com",  # TÜV certification
    "dnv.com",
    "dnvgl.com",  # DNV certification
    "sgs.com",  # SGS certification
    "bureau-veritas.com",  # Bureau Veritas
    "intertek.com",  # Intertek
    "ul.com",  # UL certification
    "a2la.org",  # A2LA accreditation
    "schellman.com",  # SOC 2 auditor
    "coalfire.com",  # SOC 2 auditor
    "kpmg.com",
    "ey.com",  # Big 4 audit firms
    "gdpr.eu",
    "ico.org.uk",  # Privacy/data protection
    "csagroup.org",  # CSA certification
    "hitrust.net",  # HITRUST
    "fedramp.gov",  # FedRAMP
}

# Date patterns for visible content
DATE_PATTERNS = [
    r"(?:published|posted|updated|modified|written|reviewed)\s*(?:on|:)?\s*(\w+\s+\d{1,2},?\s+\d{4})",
    r"(?:published|posted|updated|modified|written|reviewed)\s*(?:on|:)?\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
    r"(?:published|posted|updated|modified|written|reviewed)\s*(?:on|:)?\s*(\d{4}[/-]\d{1,2}[/-]\d{1,2})",
    # Capture the full date string including month name
    r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
]


@dataclass
class AuthorInfo:
    """Information about a content author."""

    name: str
    credentials: list[str] = field(default_factory=list)
    bio: str | None = None
    has_photo: bool = False
    has_social_links: bool = False
    is_linked: bool = False  # Links to author page
    source: str = "byline"  # byline, schema, meta

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "credentials": self.credentials,
            "bio": self.bio[:200] if self.bio else None,
            "has_photo": self.has_photo,
            "has_social_links": self.has_social_links,
            "is_linked": self.is_linked,
            "source": self.source,
        }


@dataclass
class Citation:
    """A citation or reference to external source."""

    url: str
    anchor_text: str
    domain: str
    is_authoritative: bool = False
    citation_type: str = "general"  # research, news, government, academic

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "anchor_text": self.anchor_text[:100],
            "domain": self.domain,
            "is_authoritative": self.is_authoritative,
            "type": self.citation_type,
        }


@dataclass
class OriginalDataMarker:
    """Marker indicating original research or data."""

    text: str
    pattern_matched: str
    context: str  # Surrounding text

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "pattern": self.pattern_matched,
            "context": self.context[:200],
        }


@dataclass
class ContentDate:
    """A date found in visible content."""

    date_str: str
    date_type: str  # published, updated, modified
    parsed_date: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "date_str": self.date_str,
            "date_type": self.date_type,
            "parsed_date": self.parsed_date.isoformat() if self.parsed_date else None,
        }


@dataclass
class AuthorSchemaAnalysis:
    """Analysis of author-related structured data (GEO/AEO requirement).

    Per GEO/AEO spec: Author pages, Person schema, and linked author
    profiles increase citation likelihood.
    """

    has_person_schema: bool = False  # Standalone Person schema
    has_author_in_article: bool = False  # Author nested in Article schema
    has_author_page_link: bool = False  # Link to dedicated author page
    author_page_url: str | None = None

    # Person schema details
    person_name: str | None = None
    person_job_title: str | None = None
    person_same_as: list[str] = field(default_factory=list)  # External profile links
    person_knows_about: list[str] = field(default_factory=list)  # Expertise topics

    # Score
    score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "has_person_schema": self.has_person_schema,
            "has_author_in_article": self.has_author_in_article,
            "has_author_page_link": self.has_author_page_link,
            "author_page_url": self.author_page_url,
            "person_details": {
                "name": self.person_name,
                "job_title": self.person_job_title,
                "same_as": self.person_same_as[:5],
                "knows_about": self.person_knows_about[:5],
            },
            "score": round(self.score, 2),
        }


@dataclass
class AuthorityAnalysis:
    """Complete authority signal analysis result."""

    url: str

    # Author attribution
    has_author: bool = False
    authors: list[AuthorInfo] = field(default_factory=list)
    primary_author: AuthorInfo | None = None

    # Author schema (GEO/AEO addition)
    author_schema: AuthorSchemaAnalysis = field(default_factory=AuthorSchemaAnalysis)

    # Author credentials
    has_credentials: bool = False
    has_author_bio: bool = False
    has_author_photo: bool = False
    credentials_found: list[str] = field(default_factory=list)

    # Citations
    total_citations: int = 0
    authoritative_citations: int = 0
    citations: list[Citation] = field(default_factory=list)

    # Original data markers
    has_original_data: bool = False
    original_data_markers: list[OriginalDataMarker] = field(default_factory=list)
    original_data_count: int = 0

    # Content freshness (visible dates)
    has_visible_date: bool = False
    content_dates: list[ContentDate] = field(default_factory=list)
    days_since_published: int | None = None
    freshness_level: str = "unknown"  # fresh, recent, stale, very_stale, unknown

    # Overall metrics
    authority_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "author": {
                "has_author": self.has_author,
                "primary_author": self.primary_author.to_dict() if self.primary_author else None,
                "all_authors": [a.to_dict() for a in self.authors[:5]],
            },
            "author_schema": self.author_schema.to_dict(),
            "credentials": {
                "has_credentials": self.has_credentials,
                "has_bio": self.has_author_bio,
                "has_photo": self.has_author_photo,
                "found": self.credentials_found[:10],
            },
            "citations": {
                "total": self.total_citations,
                "authoritative": self.authoritative_citations,
                "examples": [c.to_dict() for c in self.citations[:10]],
            },
            "original_data": {
                "has_original_data": self.has_original_data,
                "count": self.original_data_count,
                "markers": [m.to_dict() for m in self.original_data_markers[:5]],
            },
            "freshness": {
                "has_visible_date": self.has_visible_date,
                "dates": [d.to_dict() for d in self.content_dates[:3]],
                "days_since_published": self.days_since_published,
                "level": self.freshness_level,
            },
            "authority_score": round(self.authority_score, 2),
        }


class AuthorityAnalyzer:
    """Analyzes E-E-A-T authority signals for AI trust assessment."""

    def __init__(
        self,
        freshness_thresholds: dict | None = None,
    ):
        self.freshness_thresholds = freshness_thresholds or {
            "fresh": 30,
            "recent": 90,
            "stale": 180,
        }

    def analyze(self, html: str, url: str, main_content: str = "") -> AuthorityAnalysis:
        """
        Analyze authority signals in HTML content.

        Args:
            html: Full HTML content
            url: Page URL
            main_content: Extracted main content text (optional)

        Returns:
            AuthorityAnalysis with complete authority evaluation
        """
        soup = BeautifulSoup(html, "html.parser")
        result = AuthorityAnalysis(url=url)

        # Use main_content if provided, otherwise extract text
        text_content = main_content or soup.get_text(separator=" ", strip=True)

        # Analyze author attribution
        self._analyze_authors(soup, text_content, result)

        # Analyze author schema (GEO/AEO)
        result.author_schema = self._analyze_author_schema(soup, html)

        # Analyze credentials
        self._analyze_credentials(soup, text_content, result)

        # Analyze citations
        self._analyze_citations(soup, url, result)

        # Analyze original data markers
        self._analyze_original_data(text_content, result)

        # Analyze content freshness
        self._analyze_freshness(soup, text_content, result)

        # Calculate overall score
        result.authority_score = self._calculate_score(result)

        logger.debug(
            "authority_analysis_complete",
            url=url,
            has_author=result.has_author,
            authoritative_citations=result.authoritative_citations,
            has_original_data=result.has_original_data,
            score=result.authority_score,
        )

        return result

    def _analyze_authors(
        self, soup: BeautifulSoup, text_content: str, result: AuthorityAnalysis
    ) -> None:
        """Extract author information."""
        authors = []

        # Look for author elements in HTML
        author_selectors = [
            '[class*="author"]',
            '[rel="author"]',
            '[itemprop="author"]',
            ".byline",
            ".writer",
            ".post-author",
            ".article-author",
        ]

        for selector in author_selectors:
            elements = soup.select(selector)
            for elem in elements:
                author = self._extract_author_from_element(elem)
                if author:
                    authors.append(author)

        # Also look for byline patterns in text
        for pattern in AUTHOR_BYLINE_PATTERNS:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                name = match.group(1).strip()
                if name and len(name) < 50 and name not in [a.name for a in authors]:
                    authors.append(AuthorInfo(name=name, source="byline"))

        # Deduplicate authors
        seen_names = set()
        unique_authors = []
        for author in authors:
            if author.name.lower() not in seen_names:
                seen_names.add(author.name.lower())
                unique_authors.append(author)

        result.authors = unique_authors[:5]
        result.has_author = len(unique_authors) > 0
        if unique_authors:
            result.primary_author = unique_authors[0]

    def _extract_author_from_element(self, elem: Tag) -> AuthorInfo | None:
        """Extract author info from an HTML element."""
        # Get author name
        name_elem = elem.select_one('a, [itemprop="name"], .name, strong, span')
        name = name_elem.get_text(strip=True) if name_elem else elem.get_text(strip=True)

        # Clean up name - remove common prefixes
        name = re.sub(r"^(?:by|written by|author:)\s*", "", name, flags=re.IGNORECASE)
        # Remove credentials from the end (keep only the name part)
        name = re.sub(r",?\s*(?:Ph\.?D\.?|M\.?D\.?|MBA|CPA).*$", "", name)
        name = name.strip()

        if not name or len(name) < 2 or len(name) > 100:
            return None

        # Check if name looks like a real name
        # Allow "Dr. Name" or "Name" or "Name Name" patterns
        name_pattern = r"^(?:Dr\.?\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*$"
        if not re.match(name_pattern, name):
            # Try to extract a name from the beginning
            match = re.match(r"^(?:Dr\.?\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", name)
            if match:
                name = match.group(0)
            else:
                return None

        author = AuthorInfo(name=name, source="html")

        # Check for author photo
        img = elem.find("img")
        if img:
            author.has_photo = True

        # Check for author link
        link = elem.find("a")
        if link and link.get("href"):  # type: ignore[union-attr]
            author.is_linked = True

        # Check for social links
        social_patterns = ["twitter", "linkedin", "facebook", "instagram"]
        for a in elem.find_all("a"):
            href = (a.get("href") or "").lower()
            if any(p in href for p in social_patterns):
                author.has_social_links = True
                break

        # Look for bio text
        bio_elem = elem.select_one(".bio, .description, [itemprop='description']")
        if bio_elem:
            author.bio = bio_elem.get_text(strip=True)[:500]

        return author

    def _analyze_author_schema(self, soup: BeautifulSoup, _html: str) -> AuthorSchemaAnalysis:
        """Analyze author-related structured data (GEO/AEO requirement).

        Checks for:
        - Person schema (standalone or in Article.author)
        - Author page links
        - sameAs links to external profiles
        """
        import json

        result = AuthorSchemaAnalysis()

        # Look for JSON-LD schema
        schemas = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    schemas.extend(data)
                else:
                    schemas.append(data)
            except (json.JSONDecodeError, TypeError):
                continue

        # Check for Person schema
        for schema in schemas:
            schema_type = schema.get("@type", "")

            # Handle arrays of types
            types = schema_type if isinstance(schema_type, list) else [schema_type]

            # Standalone Person schema
            if "Person" in types:
                result.has_person_schema = True
                result.person_name = schema.get("name")
                result.person_job_title = schema.get("jobTitle")

                # sameAs links (external profiles)
                same_as = schema.get("sameAs", [])
                if isinstance(same_as, str):
                    same_as = [same_as]
                result.person_same_as = same_as[:10]

                # knowsAbout (expertise)
                knows = schema.get("knowsAbout", [])
                if isinstance(knows, str):
                    knows = [knows]
                result.person_knows_about = knows[:10]

            # Article with author
            if "Article" in types or "NewsArticle" in types or "BlogPosting" in types:
                author = schema.get("author")
                if author:
                    result.has_author_in_article = True

                    # Author can be nested Person
                    if isinstance(author, dict):
                        author_type = author.get("@type", "")
                        if author_type == "Person" or "Person" in (
                            author_type if isinstance(author_type, list) else [author_type]
                        ):
                            result.has_person_schema = True
                            if not result.person_name:
                                result.person_name = author.get("name")
                            if not result.person_job_title:
                                result.person_job_title = author.get("jobTitle")

                            same_as = author.get("sameAs", [])
                            if isinstance(same_as, str):
                                same_as = [same_as]
                            if not result.person_same_as:
                                result.person_same_as = same_as[:10]

                        # Check for author URL (author page link)
                        author_url = author.get("url")
                        if author_url:
                            result.has_author_page_link = True
                            result.author_page_url = author_url

        # Also check for author page links in HTML
        if not result.has_author_page_link:
            author_links = soup.select('a[href*="/author/"], a[href*="/team/"], a[href*="/about/"]')
            for link in author_links:
                text = link.get_text(strip=True).lower()
                # Skip generic "about" or "team" links
                if text and len(text) > 2 and text not in ["about", "team", "about us"]:
                    result.has_author_page_link = True
                    result.author_page_url = link.get("href")  # type: ignore[assignment]
                    break

        # Calculate score
        score = 0.0
        if result.has_person_schema:
            score += 40
        if result.has_author_in_article:
            score += 20
        if result.has_author_page_link:
            score += 15
        if result.person_same_as:
            score += min(15, len(result.person_same_as) * 5)  # Up to 15 for external links
        if result.person_job_title:
            score += 5
        if result.person_knows_about:
            score += 5

        result.score = min(100, score)
        return result

    def _analyze_credentials(
        self, soup: BeautifulSoup, text_content: str, result: AuthorityAnalysis
    ) -> None:
        """Analyze author credentials and expertise markers."""
        credentials = []

        # Look for credentials in author areas
        author_areas = soup.select('[class*="author"], .byline, .bio, [class*="expert"]')
        author_text = " ".join(elem.get_text(" ", strip=True) for elem in author_areas)

        # Check full text if author areas are sparse
        text_to_check = author_text if len(author_text) > 50 else text_content[:2000]

        for pattern in CREDENTIAL_PATTERNS:
            matches = re.findall(pattern, text_to_check, re.IGNORECASE)
            credentials.extend(matches)

        # Deduplicate
        result.credentials_found = list(set(credentials))[:10]
        result.has_credentials = len(result.credentials_found) > 0

        # Check for author bio
        bio_elems = soup.select('.author-bio, .bio, [class*="about-author"]')
        if bio_elems:
            result.has_author_bio = True
            # Update author with bio if found
            if result.primary_author:
                bio_text = bio_elems[0].get_text(strip=True)
                if bio_text:
                    result.primary_author.bio = bio_text[:500]

        # Check for author photo
        author_imgs = soup.select('[class*="author"] img, .byline img, .avatar')
        if author_imgs:
            result.has_author_photo = True
            if result.primary_author:
                result.primary_author.has_photo = True

    def _analyze_citations(
        self, soup: BeautifulSoup, page_url: str, result: AuthorityAnalysis
    ) -> None:
        """Analyze external citations and references."""
        page_domain = urlparse(page_url).netloc.lower()
        citations = []

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            if not href.startswith(("http://", "https://")):
                continue

            try:
                parsed = urlparse(href)
                domain = parsed.netloc.lower()

                # Skip same domain (internal links)
                if domain == page_domain or domain.endswith("." + page_domain):
                    continue

                # Skip common non-citation links
                skip_domains = ["facebook.com", "twitter.com", "instagram.com", "pinterest.com"]
                if any(d in domain for d in skip_domains):
                    continue

                anchor = link.get_text(strip=True)
                if not anchor or len(anchor) < 3:
                    continue

                # Determine if authoritative
                is_authoritative = False
                citation_type = "general"

                for auth_domain in AUTHORITATIVE_DOMAINS:
                    if auth_domain in domain or domain.endswith("." + auth_domain):
                        is_authoritative = True
                        if "edu" in domain or "ac." in domain:
                            citation_type = "academic"
                        elif "gov" in domain:
                            citation_type = "government"
                        elif any(n in domain for n in ["news", "times", "post"]):
                            citation_type = "news"
                        else:
                            citation_type = "research"
                        break

                citations.append(
                    Citation(
                        url=href,
                        anchor_text=anchor,
                        domain=domain,
                        is_authoritative=is_authoritative,
                        citation_type=citation_type,
                    )
                )

            except Exception:
                continue

        result.citations = citations[:50]
        result.total_citations = len(citations)
        result.authoritative_citations = sum(1 for c in citations if c.is_authoritative)

    def _analyze_original_data(self, text_content: str, result: AuthorityAnalysis) -> None:
        """Analyze markers indicating original research or data."""
        markers = []

        for pattern in ORIGINAL_DATA_PATTERNS:
            matches = re.finditer(pattern, text_content, re.IGNORECASE)
            for match in matches:
                # Get surrounding context
                start = max(0, match.start() - 50)
                end = min(len(text_content), match.end() + 50)
                context = text_content[start:end]

                markers.append(
                    OriginalDataMarker(
                        text=match.group(0),
                        pattern_matched=pattern,
                        context=context,
                    )
                )

        # Deduplicate similar markers
        unique_markers = []
        seen_texts = set()
        for marker in markers:
            text_lower = marker.text.lower()
            if text_lower not in seen_texts:
                seen_texts.add(text_lower)
                unique_markers.append(marker)

        result.original_data_markers = unique_markers[:10]
        result.original_data_count = len(unique_markers)
        result.has_original_data = len(unique_markers) > 0

    def _analyze_freshness(
        self, soup: BeautifulSoup, text_content: str, result: AuthorityAnalysis
    ) -> None:
        """Analyze visible content dates."""
        dates = []

        # Look for date elements in HTML
        date_selectors = [
            "time[datetime]",
            '[class*="date"]',
            '[class*="time"]',
            '[itemprop="datePublished"]',
            '[itemprop="dateModified"]',
            ".published",
            ".updated",
            ".posted",
        ]

        for selector in date_selectors:
            for elem in soup.select(selector):
                # Try datetime attribute first
                datetime_attr = elem.get("datetime")
                if datetime_attr:
                    date_type = "published"
                    if "modified" in selector or "updated" in elem.get("class", []):
                        date_type = "modified"
                    dates.append(
                        ContentDate(
                            date_str=datetime_attr,  # type: ignore[arg-type]
                            date_type=date_type,
                            parsed_date=self._parse_date(datetime_attr),  # type: ignore[arg-type]
                        )
                    )
                else:
                    # Try text content
                    text = elem.get_text(strip=True)
                    if text and len(text) < 50:
                        parsed = self._parse_date(text)
                        if parsed:
                            dates.append(
                                ContentDate(
                                    date_str=text,
                                    date_type="published",
                                    parsed_date=parsed,
                                )
                            )

        # Also look for date patterns in text
        for pattern in DATE_PATTERNS:
            matches = re.finditer(pattern, text_content[:2000], re.IGNORECASE)
            for match in matches:
                date_str = match.group(1) if match.groups() else match.group(0)
                parsed = self._parse_date(date_str)
                if parsed:
                    # Determine type from pattern
                    full_match = match.group(0).lower()
                    if "updated" in full_match or "modified" in full_match:
                        date_type = "modified"
                    else:
                        date_type = "published"

                    dates.append(
                        ContentDate(
                            date_str=date_str,
                            date_type=date_type,
                            parsed_date=parsed,
                        )
                    )

        # Deduplicate and sort by date
        unique_dates = []
        seen = set()
        for d in dates:
            key = (d.date_str, d.date_type)
            if key not in seen:
                seen.add(key)
                unique_dates.append(d)

        result.content_dates = sorted(
            unique_dates,
            key=lambda x: x.parsed_date or datetime.min,
            reverse=True,
        )[:5]

        result.has_visible_date = len(result.content_dates) > 0

        # Calculate freshness
        if result.content_dates:
            # Use most recent date
            for d in result.content_dates:
                if d.parsed_date:
                    delta = datetime.now() - d.parsed_date
                    result.days_since_published = max(0, delta.days)

                    if delta.days < self.freshness_thresholds["fresh"]:
                        result.freshness_level = "fresh"
                    elif delta.days < self.freshness_thresholds["recent"]:
                        result.freshness_level = "recent"
                    elif delta.days < self.freshness_thresholds["stale"]:
                        result.freshness_level = "stale"
                    else:
                        result.freshness_level = "very_stale"
                    break

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse various date formats."""
        # Clean the date string - remove timezone and milliseconds
        clean = date_str.strip()
        clean = clean.split("+")[0].split("Z")[0]
        # Remove milliseconds (e.g., .123456)
        clean = re.sub(r"\.\d+$", "", clean)

        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d",
            "%B %d, %Y",
            "%B %d %Y",
            "%b %d, %Y",
            "%b %d %Y",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%m-%d-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(clean, fmt)
            except ValueError:
                continue

        return None

    def _calculate_score(self, result: AuthorityAnalysis) -> float:
        """Calculate overall authority score."""
        score = 0.0

        # Author attribution (up to 20 points - reduced from 25)
        if result.has_author:
            score += 12
            if result.primary_author:
                if result.primary_author.is_linked:
                    score += 4
                if result.primary_author.has_photo:
                    score += 4

        # Author schema - GEO/AEO addition (up to 15 points)
        if result.author_schema.has_person_schema:
            score += 8
        if result.author_schema.has_author_in_article:
            score += 4
        if result.author_schema.person_same_as:
            score += 3  # External profile links

        # Credentials (up to 15 points - reduced from 20)
        if result.has_credentials:
            score += 8
            if result.has_author_bio:
                score += 4
            if len(result.credentials_found) >= 2:
                score += 3

        # Citations (up to 20 points)
        if result.authoritative_citations >= 3:
            score += 20
        elif result.authoritative_citations >= 1:
            score += 10 + min(10, result.authoritative_citations * 3)
        elif result.total_citations >= 5:
            score += 5

        # Original data (up to 15 points)
        if result.has_original_data:
            score += 10
            if result.original_data_count >= 3:
                score += 5

        # Freshness (up to 15 points - reduced from 20)
        if result.has_visible_date:
            if result.freshness_level == "fresh":
                score += 15
            elif result.freshness_level == "recent":
                score += 10
            elif result.freshness_level == "stale":
                score += 3
            # very_stale gets 0

        return min(100, score)


def analyze_authority(html: str, url: str, main_content: str = "") -> AuthorityAnalysis:
    """
    Convenience function to analyze authority signals.

    Args:
        html: Full HTML content
        url: Page URL
        main_content: Extracted main content text (optional)

    Returns:
        AuthorityAnalysis with complete authority evaluation
    """
    analyzer = AuthorityAnalyzer()
    return analyzer.analyze(html, url, main_content)
