"""Sitemap parser for discovering URLs from sitemap.xml files."""

import contextlib
import gzip
from dataclasses import dataclass
from xml.etree import ElementTree as ET

import httpx
import structlog

logger = structlog.get_logger(__name__)

# XML namespaces for sitemap
SITEMAP_NS = {
    "sm": "http://www.sitemaps.org/schemas/sitemap/0.9",
}


@dataclass
class SitemapURL:
    """A URL extracted from a sitemap."""

    loc: str
    lastmod: str | None = None
    changefreq: str | None = None
    priority: float | None = None


@dataclass
class SitemapResult:
    """Result of parsing sitemaps."""

    urls: list[SitemapURL]
    sitemap_count: int
    errors: list[str]


class SitemapParser:
    """Parser for sitemap.xml and sitemap index files."""

    def __init__(
        self,
        user_agent: str = "FindableBot/1.0",
        timeout: float = 30.0,
        max_urls: int = 1000,
        max_sitemaps: int = 10,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_urls = max_urls
        self.max_sitemaps = max_sitemaps

    async def fetch_and_parse(self, sitemap_urls: list[str]) -> SitemapResult:
        """
        Fetch and parse multiple sitemap URLs.

        Handles both sitemap index files and regular sitemaps.
        Supports gzipped sitemaps (.gz extension).

        Args:
            sitemap_urls: List of sitemap URLs to fetch

        Returns:
            SitemapResult with extracted URLs
        """
        all_urls: list[SitemapURL] = []
        errors: list[str] = []
        sitemaps_processed = 0

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for sitemap_url in sitemap_urls[: self.max_sitemaps]:
                try:
                    urls, nested_sitemaps = await self._fetch_sitemap(client, sitemap_url)
                    all_urls.extend(urls)
                    sitemaps_processed += 1

                    # Process nested sitemaps (from sitemap index)
                    for nested_url in nested_sitemaps[: self.max_sitemaps - sitemaps_processed]:
                        if sitemaps_processed >= self.max_sitemaps:
                            break
                        try:
                            nested_urls, _ = await self._fetch_sitemap(client, nested_url)
                            all_urls.extend(nested_urls)
                            sitemaps_processed += 1
                        except Exception as e:
                            errors.append(f"{nested_url}: {str(e)}")

                    # Stop if we have enough URLs
                    if len(all_urls) >= self.max_urls:
                        all_urls = all_urls[: self.max_urls]
                        break

                except Exception as e:
                    errors.append(f"{sitemap_url}: {str(e)}")

        logger.info(
            "sitemap_parsing_complete",
            urls_found=len(all_urls),
            sitemaps_processed=sitemaps_processed,
            errors=len(errors),
        )

        return SitemapResult(
            urls=all_urls,
            sitemap_count=sitemaps_processed,
            errors=errors,
        )

    async def _fetch_sitemap(
        self, client: httpx.AsyncClient, url: str
    ) -> tuple[list[SitemapURL], list[str]]:
        """
        Fetch and parse a single sitemap.

        Returns:
            Tuple of (urls, nested_sitemap_urls)
        """
        response = await client.get(
            url,
            headers={"User-Agent": self.user_agent},
            follow_redirects=True,
        )

        if response.status_code != 200:
            raise ValueError(f"HTTP {response.status_code}")

        # Handle gzipped content
        content = response.content
        if url.endswith(".gz") or response.headers.get("content-encoding") == "gzip":
            with contextlib.suppress(Exception):
                content = gzip.decompress(content)

        return self._parse_sitemap_xml(content)

    def _parse_sitemap_xml(self, content: bytes) -> tuple[list[SitemapURL], list[str]]:
        """
        Parse sitemap XML content.

        Returns:
            Tuple of (urls, nested_sitemap_urls)
        """
        urls: list[SitemapURL] = []
        nested_sitemaps: list[str] = []

        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid XML: {e}") from e

        # Check if this is a sitemap index
        # <sitemapindex> contains <sitemap> elements with <loc>
        if root.tag.endswith("sitemapindex"):
            for sitemap in root.findall(".//sm:sitemap/sm:loc", SITEMAP_NS):
                if sitemap.text:
                    nested_sitemaps.append(sitemap.text.strip())
            # Also try without namespace (some sitemaps don't use it)
            for sitemap in root.findall(".//sitemap/loc"):
                if sitemap.text and sitemap.text.strip() not in nested_sitemaps:
                    nested_sitemaps.append(sitemap.text.strip())

        # Parse regular sitemap URLs
        # <urlset> contains <url> elements
        for url_elem in root.findall(".//sm:url", SITEMAP_NS):
            url_data = self._extract_url_data(url_elem, SITEMAP_NS)
            if url_data:
                urls.append(url_data)

        # Also try without namespace
        for url_elem in root.findall(".//url"):
            url_data = self._extract_url_data(url_elem, {})
            if url_data and url_data.loc not in [u.loc for u in urls]:
                urls.append(url_data)

        return urls, nested_sitemaps

    def _extract_url_data(self, url_elem: ET.Element, ns: dict[str, str]) -> SitemapURL | None:
        """Extract URL data from a <url> element."""
        prefix = "sm:" if ns else ""

        loc_elem = url_elem.find(f"{prefix}loc", ns) if ns else url_elem.find("loc")
        if loc_elem is None or not loc_elem.text:
            return None

        loc = loc_elem.text.strip()

        # Extract optional fields
        lastmod = None
        lastmod_elem = url_elem.find(f"{prefix}lastmod", ns) if ns else url_elem.find("lastmod")
        if lastmod_elem is not None and lastmod_elem.text:
            lastmod = lastmod_elem.text.strip()

        changefreq = None
        changefreq_elem = (
            url_elem.find(f"{prefix}changefreq", ns) if ns else url_elem.find("changefreq")
        )
        if changefreq_elem is not None and changefreq_elem.text:
            changefreq = changefreq_elem.text.strip()

        priority = None
        priority_elem = url_elem.find(f"{prefix}priority", ns) if ns else url_elem.find("priority")
        if priority_elem is not None and priority_elem.text:
            with contextlib.suppress(ValueError):
                priority = float(priority_elem.text.strip())

        return SitemapURL(
            loc=loc,
            lastmod=lastmod,
            changefreq=changefreq,
            priority=priority,
        )


async def fetch_sitemap_urls(
    sitemap_urls: list[str],
    user_agent: str = "FindableBot/1.0",
    max_urls: int = 500,
) -> list[str]:
    """
    Convenience function to fetch URLs from sitemaps.

    Args:
        sitemap_urls: List of sitemap URLs (usually from robots.txt)
        user_agent: User agent string
        max_urls: Maximum URLs to return

    Returns:
        List of URL strings from the sitemaps
    """
    if not sitemap_urls:
        return []

    parser = SitemapParser(user_agent=user_agent, max_urls=max_urls)
    result = await parser.fetch_and_parse(sitemap_urls)

    # Sort by priority if available, highest first
    sorted_urls = sorted(
        result.urls,
        key=lambda u: u.priority if u.priority is not None else 0.5,
        reverse=True,
    )

    return [u.loc for u in sorted_urls]
