"""BFS web crawler with configurable limits."""

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlparse

import structlog
from bs4 import BeautifulSoup

from worker.crawler.fetcher import Fetcher
from worker.crawler.robots import RobotsChecker
from worker.crawler.sitemap import fetch_sitemap_urls
from worker.crawler.url import (
    extract_domain,
    is_internal_url,
    normalize_url,
)

logger = structlog.get_logger(__name__)


def classify_surface(url: str) -> str:
    """Classify a URL as 'docs' or 'marketing' based on path patterns.

    Returns: "docs" | "marketing"
    """
    path = urlparse(url).path.lower()
    hostname = urlparse(url).hostname or ""

    # Subdomain detection (docs.example.com, help.example.com)
    if hostname.startswith(
        ("docs.", "help.", "developer.", "developers.", "support.", "guide.", "learn.")
    ):
        return "docs"

    # Path-based detection
    docs_patterns = (
        "/docs",
        "/documentation",
        "/guide",
        "/tutorial",
        "/api-reference",
        "/reference",
        "/sdk",
        "/manual",
        "/getting-started",
        "/quickstart",
        "/how-to",
    )
    for pattern in docs_patterns:
        if path.startswith(pattern):
            return "docs"

    return "marketing"


@dataclass
class CrawlPage:
    """A crawled page with metadata."""

    url: str
    final_url: str
    title: str | None
    html: str
    content_type: str | None
    status_code: int
    depth: int
    fetch_time_ms: int
    fetched_at: datetime
    links_found: int
    surface: str = "marketing"  # "docs" | "marketing"


@dataclass
class CrawlResult:
    """Result of a complete crawl."""

    domain: str
    start_url: str
    pages: list[CrawlPage]
    urls_discovered: int
    urls_crawled: int
    urls_skipped: int
    urls_failed: int
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    robots_respected: bool
    max_depth_reached: int

    # Surface attribution
    docs_pages_crawled: int = 0
    marketing_pages_crawled: int = 0
    docs_surface_detected: bool = False

    @property
    def success_rate(self) -> float:
        """Calculate crawl success rate."""
        if self.urls_crawled == 0:
            return 0.0
        return len(self.pages) / self.urls_crawled


@dataclass
class CrawlConfig:
    """Configuration for a crawl."""

    max_pages: int = 250
    max_depth: int = 3
    timeout: float = 30.0
    user_agent: str = "FindableBot/1.0"
    respect_robots: bool = True
    follow_external_links: bool = False
    concurrency: int = 5
    min_delay: float = 0.5

    # Priority paths to seed the crawl with (improves score coverage)
    # These paths often contain high-value content not linked from homepage
    priority_paths: list[str] | None = None


# Default priority paths for better findability coverage
DEFAULT_PRIORITY_PATHS = [
    "/about",
    "/pricing",
    "/press",  # Founder info, company history
    "/newsroom",  # Alternative to /press
    "/contact",
    "/support",
    "/help",
    "/faq",
    "/features",
    "/products",
    "/services",
    "/solutions",
    "/customers",
    "/case-studies",
    "/testimonials",
    "/blog",
    "/company",
    "/team",
    "/careers",
    "/docs",  # Documentation surface
    "/documentation",
    "/getting-started",
]


class Crawler:
    """BFS web crawler."""

    def __init__(self, config: CrawlConfig):
        self.config = config
        self.fetcher = Fetcher(
            user_agent=config.user_agent,
            timeout=config.timeout,
            min_delay_between_requests=config.min_delay,
        )
        self.robots = RobotsChecker(
            user_agent=config.user_agent,
            respect_robots=config.respect_robots,
        )

    def _extract_links(self, html: str, base_url: str) -> list[str]:
        """Extract and normalize links from HTML."""
        links = []
        try:
            soup = BeautifulSoup(html, "html.parser")

            for a_tag in soup.find_all("a", href=True):
                href = a_tag["href"]

                # Skip javascript, mailto, tel links
                if href.startswith(("javascript:", "mailto:", "tel:", "#")):
                    continue

                # Normalize the URL
                normalized = normalize_url(href, base_url)
                if normalized:
                    links.append(normalized)

        except Exception as e:
            logger.warning("link_extraction_error", error=str(e), url=base_url)

        return links

    def _extract_title(self, html: str) -> str | None:
        """Extract page title from HTML."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.find("title")
            if title_tag and title_tag.string:  # type: ignore[union-attr]
                return title_tag.string.strip()[:500]  # type: ignore[union-attr, no-any-return]
        except Exception:
            pass
        return None

    async def crawl(
        self,
        start_url: str,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> CrawlResult:
        """
        Perform a BFS crawl starting from the given URL.

        Args:
            start_url: The URL to start crawling from
            progress_callback: Optional callback(pages_crawled, total_discovered)

        Returns:
            CrawlResult with all crawled pages and statistics
        """
        started_at = datetime.now(UTC)

        # Normalize start URL
        normalized_start = normalize_url(start_url)
        if not normalized_start:
            raise ValueError(f"Invalid start URL: {start_url}")

        base_domain = extract_domain(normalized_start)
        if not base_domain:
            raise ValueError(f"Could not extract domain from: {start_url}")

        logger.info(
            "crawl_started",
            url=normalized_start,
            domain=base_domain,
            max_pages=self.config.max_pages,
            max_depth=self.config.max_depth,
        )

        # Initialize crawl state
        pages: list[CrawlPage] = []
        queue: deque[tuple[str, int]] = deque()  # (url, depth)
        seen: set[str] = set()
        failed: set[str] = set()
        skipped: set[str] = set()
        max_depth_reached = 0

        # Add start URL to queue
        queue.append((normalized_start, 0))
        seen.add(normalized_start)

        # Seed queue with priority paths (depth 0 so they're crawled early)
        # These paths often contain high-value content for AI findability
        priority_paths = self.config.priority_paths or DEFAULT_PRIORITY_PATHS
        base_url = normalized_start.rstrip("/")
        priority_count = 0
        for path in priority_paths:
            priority_url = normalize_url(path, base_url)
            if (
                priority_url
                and priority_url not in seen
                and is_internal_url(priority_url, base_domain)
            ):
                queue.append((priority_url, 0))
                seen.add(priority_url)
                priority_count += 1

        if priority_count > 0:
            logger.info(
                "priority_paths_seeded",
                count=priority_count,
                paths=priority_paths[:5],  # Log first 5 for debugging
            )

        # Seed queue with URLs from sitemap.xml (if available)
        # Sitemaps are discovered from robots.txt
        try:
            # First, trigger robots.txt fetch to populate the cache
            await self.robots.is_allowed(normalized_start)
            sitemap_urls = self.robots.get_sitemaps(normalized_start)

            if sitemap_urls:
                logger.info(
                    "sitemaps_found_in_robots",
                    count=len(sitemap_urls),
                    sitemaps=sitemap_urls[:3],
                )

                # Fetch URLs from sitemaps (limit to avoid overwhelming the queue)
                sitemap_page_urls = await fetch_sitemap_urls(
                    sitemap_urls=sitemap_urls,
                    user_agent=self.config.user_agent,
                    max_urls=min(100, self.config.max_pages * 2),
                )

                sitemap_count = 0
                for sitemap_url in sitemap_page_urls:
                    normalized = normalize_url(sitemap_url)
                    if (
                        normalized
                        and normalized not in seen
                        and is_internal_url(normalized, base_domain)
                    ):
                        queue.append((normalized, 0))  # Depth 0 for priority
                        seen.add(normalized)
                        sitemap_count += 1

                if sitemap_count > 0:
                    logger.info(
                        "sitemap_urls_seeded",
                        count=sitemap_count,
                        sample=list(sitemap_page_urls)[:5],
                    )
        except Exception as e:
            logger.warning(
                "sitemap_seeding_failed",
                error=str(e),
                url=normalized_start,
            )

        while queue and len(pages) < self.config.max_pages:
            url, depth = queue.popleft()

            # Check depth limit
            if depth > self.config.max_depth:
                skipped.add(url)
                continue

            # Check robots.txt
            if not await self.robots.is_allowed(url):
                logger.debug("robots_disallowed", url=url)
                skipped.add(url)
                continue

            # Get crawl delay from robots.txt
            crawl_delay = self.robots.get_crawl_delay(url)

            # Fetch the page
            result = await self.fetcher.fetch(url, crawl_delay)

            if not result.success:
                logger.debug(
                    "fetch_failed",
                    url=url,
                    status=result.status_code,
                    error=result.error,
                )
                failed.add(url)
                continue

            # Skip non-HTML responses
            if not result.is_html or not result.html:
                skipped.add(url)
                continue

            # Extract page info
            title = self._extract_title(result.html)
            links = self._extract_links(result.html, result.final_url)

            # Create page record with surface classification
            page = CrawlPage(
                url=url,
                final_url=result.final_url,
                title=title,
                html=result.html,
                content_type=result.content_type,
                status_code=result.status_code,
                depth=depth,
                fetch_time_ms=result.fetch_time_ms,
                fetched_at=result.fetched_at,
                links_found=len(links),
                surface=classify_surface(result.final_url),
            )
            pages.append(page)

            # Track max depth
            if depth > max_depth_reached:
                max_depth_reached = depth

            # Report progress
            if progress_callback:
                progress_callback(len(pages), len(seen))

            logger.debug(
                "page_crawled",
                url=url,
                title=title[:50] if title else None,
                depth=depth,
                links=len(links),
            )

            # Add new links to queue
            for link in links:
                if link in seen:
                    continue

                # Check if internal
                if not self.config.follow_external_links and not is_internal_url(link, base_domain):
                    continue

                # Check depth of new URL
                link_depth = depth + 1
                if link_depth > self.config.max_depth:
                    continue

                seen.add(link)
                queue.append((link, link_depth))

        completed_at = datetime.now(UTC)
        duration = (completed_at - started_at).total_seconds()

        # Compute surface attribution
        docs_count = sum(1 for p in pages if p.surface == "docs")
        marketing_count = len(pages) - docs_count

        logger.info(
            "crawl_completed",
            domain=base_domain,
            pages_crawled=len(pages),
            urls_discovered=len(seen),
            urls_failed=len(failed),
            duration_seconds=round(duration, 2),
            docs_pages=docs_count,
            marketing_pages=marketing_count,
        )

        return CrawlResult(
            domain=base_domain,
            start_url=normalized_start,
            pages=pages,
            urls_discovered=len(seen),
            urls_crawled=len(pages) + len(failed),
            urls_skipped=len(skipped),
            urls_failed=len(failed),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            robots_respected=self.config.respect_robots,
            max_depth_reached=max_depth_reached,
            docs_pages_crawled=docs_count,
            marketing_pages_crawled=marketing_count,
            docs_surface_detected=docs_count > 0,
        )


async def crawl_site(
    url: str,
    max_pages: int = 250,
    max_depth: int = 3,
    user_agent: str = "FindableBot/1.0",
    progress_callback: Callable[[int, int], None] | None = None,
) -> CrawlResult:
    """
    Convenience function to crawl a site.

    Args:
        url: The URL to start crawling
        max_pages: Maximum pages to crawl
        max_depth: Maximum link depth
        user_agent: User agent string
        progress_callback: Optional progress callback

    Returns:
        CrawlResult with crawled pages
    """
    config = CrawlConfig(
        max_pages=max_pages,
        max_depth=max_depth,
        user_agent=user_agent,
    )
    crawler = Crawler(config)
    return await crawler.crawl(url, progress_callback)
