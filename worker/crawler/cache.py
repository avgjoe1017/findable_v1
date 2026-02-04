"""Crawl result caching using Redis."""

import json
from dataclasses import asdict
from datetime import UTC, datetime

import structlog

from worker.crawler.crawler import CrawlPage, CrawlResult
from worker.redis import get_redis_connection as get_redis

logger = structlog.get_logger(__name__)

# Default cache TTL: 24 hours
DEFAULT_CACHE_TTL_SECONDS = 86400


class CrawlCache:
    """
    Cache for crawl results using Redis.

    Stores complete crawl results by domain, allowing reuse
    across audit runs within the TTL window.
    """

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS):
        """
        Initialize the cache.

        Args:
            ttl_seconds: Time-to-live for cache entries (default: 24 hours)
        """
        self.ttl_seconds = ttl_seconds
        self._prefix = "crawl:cache:"

    def _cache_key(self, domain: str) -> str:
        """Generate cache key for a domain."""
        return f"{self._prefix}{domain.lower()}"

    async def get(self, domain: str) -> CrawlResult | None:
        """
        Get cached crawl result for a domain.

        Args:
            domain: The domain to look up

        Returns:
            CrawlResult if found and valid, None otherwise
        """
        try:
            redis = get_redis()
            key = self._cache_key(domain)
            data = redis.get(key)

            if not data:
                logger.debug("cache_miss", domain=domain)
                return None

            # Parse cached data
            cached = json.loads(data)

            # Reconstruct CrawlResult
            pages = [
                CrawlPage(
                    url=p["url"],
                    final_url=p["final_url"],
                    title=p.get("title"),
                    html=p["html"],
                    content_type=p.get("content_type"),
                    status_code=p["status_code"],
                    depth=p["depth"],
                    fetch_time_ms=p["fetch_time_ms"],
                    fetched_at=datetime.fromisoformat(p["fetched_at"]),
                    links_found=p["links_found"],
                )
                for p in cached["pages"]
            ]

            result = CrawlResult(
                domain=cached["domain"],
                start_url=cached["start_url"],
                pages=pages,
                urls_discovered=cached["urls_discovered"],
                urls_crawled=cached["urls_crawled"],
                urls_skipped=cached["urls_skipped"],
                urls_failed=cached["urls_failed"],
                started_at=datetime.fromisoformat(cached["started_at"]),
                completed_at=datetime.fromisoformat(cached["completed_at"]),
                duration_seconds=cached["duration_seconds"],
                robots_respected=cached["robots_respected"],
                max_depth_reached=cached["max_depth_reached"],
            )

            logger.info(
                "cache_hit",
                domain=domain,
                pages=len(pages),
                age_seconds=int((datetime.now(UTC) - result.completed_at).total_seconds()),
            )
            return result

        except Exception as e:
            logger.warning("cache_get_error", domain=domain, error=str(e))
            return None

    async def set(self, result: CrawlResult) -> bool:
        """
        Store crawl result in cache.

        Args:
            result: The CrawlResult to cache

        Returns:
            True if cached successfully, False otherwise
        """
        try:
            redis = get_redis()
            key = self._cache_key(result.domain)

            # Serialize pages with datetime handling
            pages_data = []
            for page in result.pages:
                page_dict = asdict(page)
                page_dict["fetched_at"] = page.fetched_at.isoformat()
                pages_data.append(page_dict)

            # Build cache data
            cache_data = {
                "domain": result.domain,
                "start_url": result.start_url,
                "pages": pages_data,
                "urls_discovered": result.urls_discovered,
                "urls_crawled": result.urls_crawled,
                "urls_skipped": result.urls_skipped,
                "urls_failed": result.urls_failed,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat(),
                "duration_seconds": result.duration_seconds,
                "robots_respected": result.robots_respected,
                "max_depth_reached": result.max_depth_reached,
                "cached_at": datetime.now(UTC).isoformat(),
            }

            redis.setex(key, self.ttl_seconds, json.dumps(cache_data))

            logger.info(
                "cache_set",
                domain=result.domain,
                pages=len(result.pages),
                ttl_seconds=self.ttl_seconds,
            )
            return True

        except Exception as e:
            logger.warning("cache_set_error", domain=result.domain, error=str(e))
            return False

    async def invalidate(self, domain: str) -> bool:
        """
        Invalidate cache for a domain.

        Args:
            domain: The domain to invalidate

        Returns:
            True if invalidated, False otherwise
        """
        try:
            redis = get_redis()
            key = self._cache_key(domain)
            deleted = redis.delete(key)
            logger.info("cache_invalidated", domain=domain, deleted=bool(deleted))
            return bool(deleted)
        except Exception as e:
            logger.warning("cache_invalidate_error", domain=domain, error=str(e))
            return False

    async def get_cache_info(self, domain: str) -> dict | None:
        """
        Get cache metadata without loading full content.

        Args:
            domain: The domain to check

        Returns:
            Dict with cache info or None if not cached
        """
        try:
            redis = get_redis()
            key = self._cache_key(domain)
            ttl = redis.ttl(key)

            if ttl <= 0:
                return None

            data = redis.get(key)
            if not data:
                return None

            cached = json.loads(data)
            return {
                "domain": cached["domain"],
                "pages_count": len(cached["pages"]),
                "cached_at": cached.get("cached_at"),
                "completed_at": cached["completed_at"],
                "ttl_remaining_seconds": ttl,
            }

        except Exception as e:
            logger.warning("cache_info_error", domain=domain, error=str(e))
            return None


# Singleton instance
crawl_cache = CrawlCache()


async def get_cached_or_crawl(
    url: str,
    max_pages: int = 250,
    max_depth: int = 3,
    user_agent: str = "FindableBot/1.0",
    use_cache: bool = True,
    force_refresh: bool = False,
) -> CrawlResult:
    """
    Get crawl result from cache or perform fresh crawl.

    Args:
        url: The URL to crawl
        max_pages: Maximum pages to crawl
        max_depth: Maximum link depth
        user_agent: User agent string
        use_cache: Whether to use cache (default: True)
        force_refresh: Force a fresh crawl even if cached (default: False)

    Returns:
        CrawlResult from cache or fresh crawl
    """
    from worker.crawler.crawler import crawl_site
    from worker.crawler.url import extract_domain

    domain = extract_domain(url)
    if not domain:
        raise ValueError(f"Could not extract domain from: {url}")

    # Check cache unless disabled or force refresh
    if use_cache and not force_refresh:
        cached = await crawl_cache.get(domain)
        if cached:
            return cached

    # Perform fresh crawl
    result = await crawl_site(
        url=url,
        max_pages=max_pages,
        max_depth=max_depth,
        user_agent=user_agent,
    )

    # Cache the result if caching is enabled
    if use_cache:
        await crawl_cache.set(result)

    return result
