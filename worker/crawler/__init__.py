"""Crawler package for web crawling functionality."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.crawler.crawler import Crawler, CrawlConfig, crawl_site
# from worker.crawler.url import normalize_url, extract_domain
# from worker.crawler.robots import RobotsChecker
# from worker.crawler.render import PageRenderer, RenderDeltaDetector
# from worker.crawler.robots_ai import check_ai_crawler_access
# from worker.crawler.performance import measure_ttfb, measure_site_ttfb
# from worker.crawler.llms_txt import check_llms_txt

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
    # AI Crawler Access (v2)
    "AIRobotsChecker",
    "RobotsTxtAIResult",
    "check_ai_crawler_access",
    # Performance (v2)
    "PerformanceChecker",
    "TTFBResult",
    "SitePerformanceResult",
    "measure_ttfb",
    "measure_site_ttfb",
    # llms.txt (v2)
    "LlmsTxtChecker",
    "LlmsTxtResult",
    "check_llms_txt",
    # Render delta
    "PageRenderer",
    "RenderDeltaDetector",
    "RenderDelta",
    "RenderMode",
    "RendererConfig",
    "detect_render_mode",
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
