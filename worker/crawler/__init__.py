"""Crawler package for web crawling functionality."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.crawler.crawler import Crawler, CrawlConfig, crawl_site
# from worker.crawler.url import normalize_url, extract_domain
# from worker.crawler.robots import RobotsChecker

__all__ = [
    # Crawler
    "Crawler",
    "CrawlConfig",
    "CrawlPage",
    "CrawlResult",
    "crawl_site",
    # Fetcher
    "Fetcher",
    "FetchResult",
    # Robots
    "RobotsChecker",
    "RobotsParser",
    # Storage
    "CrawlStorage",
    "CrawlManifest",
    "StoredPage",
    # URL utilities
    "normalize_url",
    "extract_domain",
    "is_same_domain",
    "is_internal_url",
    "get_url_depth",
]
