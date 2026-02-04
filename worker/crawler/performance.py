"""Performance measurement for AI crawler accessibility.

Measures Time to First Byte (TTFB) which is critical for AI crawlers
that have strict timeout constraints (often 1-5 seconds).
"""

import time
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import structlog

logger = structlog.get_logger(__name__)


# TTFB thresholds based on research
# AI crawlers often limit retrieval to 1-5 seconds
TTFB_THRESHOLDS = {
    "excellent": 200,  # <200ms - Google recommendation
    "good": 500,  # 200-500ms - Acceptable
    "acceptable": 1000,  # 500-1000ms - Problematic
    "poor": 1500,  # 1000-1500ms - Likely skipped
    "critical": 2000,  # >1500ms - Almost certainly skipped
}


@dataclass
class TTFBResult:
    """Result of TTFB measurement."""

    url: str
    ttfb_ms: int
    score: float  # 0-100
    level: str  # excellent, good, acceptable, poor, critical
    dns_time_ms: int | None = None
    connect_time_ms: int | None = None
    tls_time_ms: int | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "ttfb_ms": self.ttfb_ms,
            "score": round(self.score, 2),
            "level": self.level,
            "dns_time_ms": self.dns_time_ms,
            "connect_time_ms": self.connect_time_ms,
            "tls_time_ms": self.tls_time_ms,
            "error": self.error,
            "threshold_excellent": TTFB_THRESHOLDS["excellent"],
            "threshold_good": TTFB_THRESHOLDS["good"],
        }

    @property
    def is_acceptable(self) -> bool:
        """Check if TTFB is acceptable for AI crawlers."""
        return self.ttfb_ms < TTFB_THRESHOLDS["acceptable"]

    @property
    def is_critical(self) -> bool:
        """Check if TTFB is critically slow."""
        return self.ttfb_ms >= TTFB_THRESHOLDS["critical"]


def _calculate_ttfb_score(ttfb_ms: int) -> tuple[float, str]:
    """
    Calculate score and level from TTFB.

    Returns:
        Tuple of (score 0-100, level string)
    """
    if ttfb_ms < TTFB_THRESHOLDS["excellent"]:
        return 100.0, "excellent"
    elif ttfb_ms < TTFB_THRESHOLDS["good"]:
        # Linear interpolation 80-100
        ratio = (ttfb_ms - TTFB_THRESHOLDS["excellent"]) / (
            TTFB_THRESHOLDS["good"] - TTFB_THRESHOLDS["excellent"]
        )
        return 100 - (ratio * 20), "good"
    elif ttfb_ms < TTFB_THRESHOLDS["acceptable"]:
        # Linear interpolation 50-80
        ratio = (ttfb_ms - TTFB_THRESHOLDS["good"]) / (
            TTFB_THRESHOLDS["acceptable"] - TTFB_THRESHOLDS["good"]
        )
        return 80 - (ratio * 30), "acceptable"
    elif ttfb_ms < TTFB_THRESHOLDS["poor"]:
        # Linear interpolation 25-50
        ratio = (ttfb_ms - TTFB_THRESHOLDS["acceptable"]) / (
            TTFB_THRESHOLDS["poor"] - TTFB_THRESHOLDS["acceptable"]
        )
        return 50 - (ratio * 25), "poor"
    else:
        # Below 25
        ratio = min(1.0, (ttfb_ms - TTFB_THRESHOLDS["poor"]) / 1000)
        return max(0, 25 - (ratio * 25)), "critical"


class PerformanceChecker:
    """Measures site performance metrics for AI crawlers."""

    def __init__(
        self,
        timeout: float = 10.0,
        user_agent: str = "FindableBot/1.0 (Performance Check)",
    ):
        self.timeout = timeout
        self.user_agent = user_agent

    async def measure_ttfb(self, url: str) -> TTFBResult:
        """
        Measure Time to First Byte for a URL.

        Uses streaming to capture the exact moment the first byte arrives.

        Args:
            url: The URL to measure

        Returns:
            TTFBResult with timing breakdown and score
        """
        result = TTFBResult(
            url=url,
            ttfb_ms=0,
            score=0,
            level="critical",
        )

        try:
            start = time.perf_counter()

            async with (
                httpx.AsyncClient(timeout=self.timeout) as client,
                client.stream(
                    "GET",
                    url,
                    headers={
                        "User-Agent": self.user_agent,
                        "Accept": "text/html,application/xhtml+xml",
                    },
                    follow_redirects=True,
                ) as response,
            ):
                # Time to first byte is when headers are received
                first_byte_time = time.perf_counter()
                ttfb_ms = int((first_byte_time - start) * 1000)

                # Read a small chunk to ensure connection is established
                _ = await response.aread()

            result.ttfb_ms = ttfb_ms
            result.score, result.level = _calculate_ttfb_score(ttfb_ms)

            logger.info(
                "ttfb_measured",
                url=url,
                ttfb_ms=ttfb_ms,
                score=result.score,
                level=result.level,
            )

        except httpx.TimeoutException:
            result.ttfb_ms = int(self.timeout * 1000)
            result.score = 0
            result.level = "critical"
            result.error = f"Request timed out after {self.timeout}s"
            logger.warning("ttfb_timeout", url=url, timeout=self.timeout)

        except httpx.ConnectError as e:
            result.error = f"Connection failed: {e}"
            result.level = "critical"
            logger.warning("ttfb_connect_error", url=url, error=str(e))

        except Exception as e:
            result.error = str(e)
            result.level = "critical"
            logger.warning("ttfb_error", url=url, error=str(e))

        return result

    async def measure_multiple(
        self,
        urls: list[str],
        sample_size: int = 5,
    ) -> dict[str, TTFBResult]:
        """
        Measure TTFB for multiple URLs.

        Args:
            urls: List of URLs to measure
            sample_size: Max number of URLs to sample

        Returns:
            Dict mapping URL to TTFBResult
        """
        # Sample if too many URLs
        sampled = urls[:sample_size] if len(urls) > sample_size else urls

        results = {}
        for url in sampled:
            results[url] = await self.measure_ttfb(url)

        return results


@dataclass
class SitePerformanceResult:
    """Aggregated performance result for a site."""

    domain: str
    avg_ttfb_ms: int
    min_ttfb_ms: int
    max_ttfb_ms: int
    score: float
    level: str
    pages_measured: int
    page_results: list[TTFBResult]

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "avg_ttfb_ms": self.avg_ttfb_ms,
            "min_ttfb_ms": self.min_ttfb_ms,
            "max_ttfb_ms": self.max_ttfb_ms,
            "score": round(self.score, 2),
            "level": self.level,
            "pages_measured": self.pages_measured,
            "page_results": [r.to_dict() for r in self.page_results],
        }


async def measure_site_ttfb(
    urls: list[str],
    timeout: float = 10.0,
    sample_size: int = 5,
) -> SitePerformanceResult:
    """
    Measure TTFB for a site (samples multiple pages).

    Args:
        urls: List of URLs on the site
        timeout: Request timeout
        sample_size: Number of pages to sample

    Returns:
        SitePerformanceResult with aggregated metrics
    """
    if not urls:
        return SitePerformanceResult(
            domain="unknown",
            avg_ttfb_ms=0,
            min_ttfb_ms=0,
            max_ttfb_ms=0,
            score=0,
            level="critical",
            pages_measured=0,
            page_results=[],
        )

    domain = urlparse(urls[0]).netloc

    checker = PerformanceChecker(timeout=timeout)
    url_results = await checker.measure_multiple(urls, sample_size)

    results = list(url_results.values())
    valid_results = [r for r in results if r.error is None]

    if not valid_results:
        return SitePerformanceResult(
            domain=domain,
            avg_ttfb_ms=int(timeout * 1000),
            min_ttfb_ms=int(timeout * 1000),
            max_ttfb_ms=int(timeout * 1000),
            score=0,
            level="critical",
            pages_measured=len(results),
            page_results=results,
        )

    ttfb_values = [r.ttfb_ms for r in valid_results]
    avg_ttfb = int(sum(ttfb_values) / len(ttfb_values))
    score, level = _calculate_ttfb_score(avg_ttfb)

    return SitePerformanceResult(
        domain=domain,
        avg_ttfb_ms=avg_ttfb,
        min_ttfb_ms=min(ttfb_values),
        max_ttfb_ms=max(ttfb_values),
        score=score,
        level=level,
        pages_measured=len(results),
        page_results=results,
    )


async def measure_ttfb(url: str, timeout: float = 10.0) -> TTFBResult:
    """
    Convenience function to measure TTFB for a single URL.

    Args:
        url: The URL to measure
        timeout: Request timeout in seconds

    Returns:
        TTFBResult with TTFB and score
    """
    checker = PerformanceChecker(timeout=timeout)
    return await checker.measure_ttfb(url)
