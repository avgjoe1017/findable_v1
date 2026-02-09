"""Metadata extraction from HTML pages."""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass
class PageMetadata:
    """Metadata extracted from a page."""

    title: str | None = None
    description: str | None = None
    keywords: list[str] = field(default_factory=list)
    author: str | None = None
    published_date: str | None = None
    modified_date: str | None = None
    canonical_url: str | None = None
    language: str | None = None
    og_title: str | None = None
    og_description: str | None = None
    og_image: str | None = None
    og_type: str | None = None
    twitter_title: str | None = None
    twitter_description: str | None = None
    twitter_image: str | None = None
    favicon: str | None = None
    headings: dict[str, list[str]] = field(default_factory=dict)
    links_internal: int = 0
    links_external: int = 0
    images: int = 0
    word_count: int = 0
    schema_types: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "title": self.title,
            "description": self.description,
            "keywords": self.keywords,
            "author": self.author,
            "published_date": self.published_date,
            "modified_date": self.modified_date,
            "canonical_url": self.canonical_url,
            "language": self.language,
            "og": {
                "title": self.og_title,
                "description": self.og_description,
                "image": self.og_image,
                "type": self.og_type,
            },
            "twitter": {
                "title": self.twitter_title,
                "description": self.twitter_description,
                "image": self.twitter_image,
            },
            "favicon": self.favicon,
            "headings": self.headings,
            "counts": {
                "links_internal": self.links_internal,
                "links_external": self.links_external,
                "images": self.images,
                "words": self.word_count,
            },
            "schema_types": self.schema_types,
        }


def _get_meta_content(
    soup: BeautifulSoup, name: str | None = None, property: str | None = None
) -> str | None:
    """Get content from a meta tag by name or property."""
    if name:
        tag = soup.find("meta", attrs={"name": name})
        if not tag:
            tag = soup.find("meta", attrs={"name": name.lower()})
    elif property:
        tag = soup.find("meta", attrs={"property": property})
    else:
        return None

    if tag and tag.get("content"):  # type: ignore[union-attr]
        content = tag["content"]  # type: ignore[index]
        return content.strip() if isinstance(content, str) else str(content).strip()
    return None


def _extract_schema_types(soup: BeautifulSoup) -> list[str]:
    """Extract schema.org types from JSON-LD and microdata."""
    types: set[str] = set()

    # JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if isinstance(data, dict):
                if "@type" in data:
                    t = data["@type"]
                    if isinstance(t, list):
                        types.update(t)
                    else:
                        types.add(t)
                if "@graph" in data and isinstance(data["@graph"], list):
                    for item in data["@graph"]:
                        if isinstance(item, dict) and "@type" in item:
                            t = item["@type"]
                            if isinstance(t, list):
                                types.update(t)
                            else:
                                types.add(t)
        except (json.JSONDecodeError, TypeError):
            pass

    # Microdata itemtype
    for tag in soup.find_all(attrs={"itemtype": True}):
        itemtype = tag.get("itemtype", "")
        if "schema.org" in itemtype:
            # Extract type from URL like "https://schema.org/Article"
            type_match = re.search(r"schema\.org/(\w+)", itemtype)
            if type_match:
                types.add(type_match.group(1))

    return sorted(types)


def _extract_headings(soup: BeautifulSoup) -> dict[str, list[str]]:
    """Extract all headings organized by level."""
    headings: dict[str, list[str]] = {}

    for level in range(1, 7):
        tag_name = f"h{level}"
        found = []
        for tag in soup.find_all(tag_name):
            text = tag.get_text(strip=True)
            if text:
                found.append(text[:200])  # Limit length
        if found:
            headings[tag_name] = found

    return headings


def _count_words(text: str) -> int:
    """Count words in text."""
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def _is_internal_link(href: str, base_domain: str) -> bool:
    """Check if a link is internal."""
    if not href:
        return False
    if href.startswith(("/", "#", "?")):
        return True
    return base_domain.lower() in href.lower()


def extract_metadata(html: str, url: str | None = None) -> PageMetadata:
    """
    Extract metadata from HTML.

    Args:
        html: HTML content
        url: Optional page URL for resolving relative links

    Returns:
        PageMetadata with extracted information
    """
    soup = BeautifulSoup(html, "html.parser")
    metadata = PageMetadata()

    # Extract domain for link classification
    base_domain = ""
    if url:
        from worker.crawler.url import extract_domain

        base_domain = extract_domain(url) or ""

    # Title
    title_tag = soup.find("title")
    if title_tag:
        metadata.title = title_tag.get_text(strip=True)[:500]

    # Meta description
    metadata.description = _get_meta_content(soup, name="description")

    # Keywords
    keywords_str = _get_meta_content(soup, name="keywords")
    if keywords_str:
        metadata.keywords = [k.strip() for k in keywords_str.split(",") if k.strip()][:20]

    # Author
    metadata.author = _get_meta_content(soup, name="author")

    # Dates
    metadata.published_date = (
        _get_meta_content(soup, name="article:published_time")
        or _get_meta_content(soup, property="article:published_time")
        or _get_meta_content(soup, name="date")
        or _get_meta_content(soup, name="pubdate")
    )
    metadata.modified_date = (
        _get_meta_content(soup, name="article:modified_time")
        or _get_meta_content(soup, property="article:modified_time")
        or _get_meta_content(soup, name="last-modified")
    )

    # Canonical URL
    canonical = soup.find("link", rel="canonical")
    if canonical and canonical.get("href"):  # type: ignore[union-attr]
        metadata.canonical_url = canonical["href"]  # type: ignore[assignment, index]

    # Language
    html_tag = soup.find("html")
    if html_tag:
        metadata.language = html_tag.get("lang") or html_tag.get("xml:lang")  # type: ignore[union-attr, assignment]

    # Open Graph
    metadata.og_title = _get_meta_content(soup, property="og:title")
    metadata.og_description = _get_meta_content(soup, property="og:description")
    metadata.og_image = _get_meta_content(soup, property="og:image")
    metadata.og_type = _get_meta_content(soup, property="og:type")

    # Twitter Cards
    metadata.twitter_title = _get_meta_content(soup, name="twitter:title")
    metadata.twitter_description = _get_meta_content(soup, name="twitter:description")
    metadata.twitter_image = _get_meta_content(soup, name="twitter:image")

    # Favicon
    favicon = soup.find("link", rel=lambda x: x and "icon" in x.lower() if x else False)
    if favicon and favicon.get("href"):  # type: ignore[union-attr]
        href = favicon["href"]  # type: ignore[index]
        if url and not href.startswith("http"):  # type: ignore[union-attr]
            href = urljoin(url, href)  # type: ignore[type-var, assignment]
        metadata.favicon = href  # type: ignore[assignment]

    # Headings
    metadata.headings = _extract_headings(soup)

    # Count links
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if _is_internal_link(href, base_domain):
            metadata.links_internal += 1
        else:
            metadata.links_external += 1

    # Count images
    metadata.images = len(soup.find_all("img"))

    # Word count
    text = soup.get_text(separator=" ", strip=True)
    metadata.word_count = _count_words(text)

    # Schema.org types
    metadata.schema_types = _extract_schema_types(soup)

    return metadata
