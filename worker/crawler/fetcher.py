"""HTTP fetcher with retry logic and rate limiting."""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class FetchResult:
    """Result of fetching a URL."""

    url: str
    final_url: str  # After redirects
    status_code: int
    content_type: str | None
    html: str | None
    error: str | None
    fetch_time_ms: int
    fetched_at: datetime

    @property
    def success(self) -> bool:
        """Check if fetch was successful."""
        return self.status_code == 200 and self.html is not None

    @property
    def is_html(self) -> bool:
        """Check if response is HTML."""
        if not self.content_type:
            return False
        return "text/html" in self.content_type.lower()


class Fetcher:
    """HTTP fetcher with retries and rate limiting."""

    def __init__(
        self,
        user_agent: str,
        timeout: float = 30.0,
        max_retries: int = 2,
        retry_delay: float = 1.0,
        min_delay_between_requests: float = 0.5,
    ):
        self.user_agent = user_agent
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.min_delay = min_delay_between_requests
        self._last_request_time: dict[str, float] = {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for rate limiting."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc.lower()

    async def _rate_limit(self, domain: str, crawl_delay: float | None = None) -> None:
        """Apply rate limiting per domain."""
        delay = crawl_delay or self.min_delay

        if domain in self._last_request_time:
            elapsed = asyncio.get_event_loop().time() - self._last_request_time[domain]
            if elapsed < delay:
                await asyncio.sleep(delay - elapsed)

        self._last_request_time[domain] = asyncio.get_event_loop().time()

    async def fetch(
        self,
        url: str,
        crawl_delay: float | None = None,
    ) -> FetchResult:
        """
        Fetch a URL with retries.

        Args:
            url: The URL to fetch
            crawl_delay: Optional crawl delay from robots.txt

        Returns:
            FetchResult with response data or error
        """
        domain = self._get_domain(url)
        start_time = datetime.now(UTC)

        for attempt in range(self.max_retries + 1):
            try:
                # Apply rate limiting
                await self._rate_limit(domain, crawl_delay)

                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                    max_redirects=5,
                ) as client:
                    response = await client.get(
                        url,
                        headers={
                            "User-Agent": self.user_agent,
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Accept-Encoding": "gzip, deflate",
                            "Connection": "keep-alive",
                        },
                    )

                fetch_time = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
                content_type = response.headers.get("content-type", "")

                # Only store HTML content
                html = None
                if response.status_code == 200 and "text/html" in content_type.lower():
                    html = response.text

                return FetchResult(
                    url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content_type=content_type,
                    html=html,
                    error=None,
                    fetch_time_ms=fetch_time,
                    fetched_at=start_time,
                )

            except httpx.TimeoutException:
                error = "Request timed out"
                if attempt < self.max_retries:
                    logger.warning(
                        "fetch_timeout_retry",
                        url=url,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

            except httpx.HTTPStatusError as e:
                error = f"HTTP error: {e.response.status_code}"
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    return FetchResult(
                        url=url,
                        final_url=str(e.response.url),
                        status_code=e.response.status_code,
                        content_type=None,
                        html=None,
                        error=error,
                        fetch_time_ms=int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                        fetched_at=start_time,
                    )
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

            except Exception as e:
                error = str(e)
                if attempt < self.max_retries:
                    logger.warning(
                        "fetch_error_retry",
                        url=url,
                        error=error,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue

        # All retries exhausted
        fetch_time = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        return FetchResult(
            url=url,
            final_url=url,
            status_code=0,
            content_type=None,
            html=None,
            error=error,
            fetch_time_ms=fetch_time,
            fetched_at=start_time,
        )

    async def fetch_many(
        self,
        urls: list[str],
        concurrency: int = 5,
        crawl_delay: float | None = None,
    ) -> list[FetchResult]:
        """
        Fetch multiple URLs with controlled concurrency.

        Args:
            urls: List of URLs to fetch
            concurrency: Maximum concurrent requests
            crawl_delay: Optional crawl delay

        Returns:
            List of FetchResults in same order as input URLs
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(url: str) -> FetchResult:
            async with semaphore:
                return await self.fetch(url, crawl_delay)

        tasks = [fetch_with_semaphore(url) for url in urls]
        return await asyncio.gather(*tasks)
