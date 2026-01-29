"""Render delta detection for JavaScript-heavy sites.

This module determines whether a site requires JavaScript rendering
by comparing static vs. rendered content.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

try:
    from playwright.async_api import Browser, Page, async_playwright
    from playwright.async_api import TimeoutError as PlaywrightTimeout

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from worker.crawler.fetcher import Fetcher
from worker.extraction.cleaner import clean_html

if TYPE_CHECKING:
    from playwright.async_api import Browser, Page


class RenderMode(str, Enum):
    """How to fetch pages."""

    STATIC = "static"  # httpx only
    RENDERED = "rendered"  # Playwright only
    AUTO = "auto"  # Detect based on delta


@dataclass
class RenderDelta:
    """Result of comparing static vs rendered content."""

    static_content: str
    rendered_content: str
    static_word_count: int
    rendered_word_count: int
    word_delta: int
    word_delta_ratio: float
    content_similarity: float
    needs_rendering: bool
    detection_url: str


@dataclass
class RendererConfig:
    """Configuration for the renderer."""

    # Thresholds for detecting JS-heavy sites
    min_word_delta: int = 50  # Minimum word difference to trigger
    min_delta_ratio: float = 0.2  # 20% more content triggers rendering
    similarity_threshold: float = 0.7  # Below this = different content

    # Playwright settings
    wait_for_load: int = 5000  # ms to wait after load
    timeout: int = 30000  # ms total timeout
    viewport_width: int = 1280
    viewport_height: int = 720

    # Sample pages for delta detection
    sample_count: int = 3  # Number of pages to sample


def _jaccard_similarity(text1: str, text2: str) -> float:
    """Calculate Jaccard similarity between two texts."""
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union)


class PageRenderer:
    """Renders pages using Playwright headless browser."""

    def __init__(self, config: RendererConfig | None = None):
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError(
                "Playwright not installed. Install with: pip install playwright && playwright install"
            )
        self.config = config or RendererConfig()
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()

    async def __aenter__(self) -> "PageRenderer":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    async def start(self) -> None:
        """Start the browser."""
        async with self._lock:
            if self._browser is None:
                pw = await async_playwright().start()
                self._browser = await pw.chromium.launch(headless=True)

    async def stop(self) -> None:
        """Stop the browser."""
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None

    async def render_page(self, url: str) -> tuple[str, str | None]:
        """
        Render a page and return HTML content.

        Args:
            url: URL to render

        Returns:
            Tuple of (html_content, error_message)
        """
        if not self._browser:
            await self.start()

        page: Page | None = None
        try:
            page = await self._browser.new_page(  # type: ignore[union-attr]
                viewport={
                    "width": self.config.viewport_width,
                    "height": self.config.viewport_height,
                }
            )

            # Navigate and wait for network idle
            await page.goto(
                url,
                timeout=self.config.timeout,
                wait_until="networkidle",
            )

            # Additional wait for JS execution
            await page.wait_for_timeout(self.config.wait_for_load)

            # Get rendered HTML
            html = await page.content()

            return html, None

        except PlaywrightTimeout:
            return "", f"Timeout rendering {url}"
        except Exception as e:
            return "", f"Error rendering {url}: {str(e)}"
        finally:
            if page:
                await page.close()


class RenderDeltaDetector:
    """Detects whether a site needs JavaScript rendering."""

    def __init__(
        self,
        config: RendererConfig | None = None,
        fetcher: Fetcher | None = None,
    ):
        self.config = config or RendererConfig()
        self.fetcher = fetcher

    async def detect_delta(self, url: str) -> RenderDelta:
        """
        Compare static vs rendered content for a single URL.

        Args:
            url: URL to test

        Returns:
            RenderDelta with comparison results
        """
        # Fetch static content
        fetcher = self.fetcher or Fetcher()
        static_result = await fetcher.fetch(url)

        if not static_result.html:
            return RenderDelta(
                static_content="",
                rendered_content="",
                static_word_count=0,
                rendered_word_count=0,
                word_delta=0,
                word_delta_ratio=0.0,
                content_similarity=0.0,
                needs_rendering=True,  # Can't fetch static, try rendered
                detection_url=url,
            )

        # Extract static text
        static_cleaned = clean_html(static_result.html)
        static_text = static_cleaned.main_content

        # Render with Playwright
        async with PageRenderer(self.config) as renderer:
            rendered_html, error = await renderer.render_page(url)

        if error or not rendered_html:
            # Can't render, fall back to static
            return RenderDelta(
                static_content=static_text,
                rendered_content="",
                static_word_count=len(static_text.split()),
                rendered_word_count=0,
                word_delta=0,
                word_delta_ratio=0.0,
                content_similarity=1.0,  # Assume same if can't render
                needs_rendering=False,
                detection_url=url,
            )

        # Extract rendered text
        rendered_cleaned = clean_html(rendered_html)
        rendered_text = rendered_cleaned.main_content

        # Calculate metrics
        static_words = len(static_text.split())
        rendered_words = len(rendered_text.split())
        word_delta = rendered_words - static_words
        word_delta_ratio = word_delta / static_words if static_words > 0 else 0.0
        similarity = _jaccard_similarity(static_text, rendered_text)

        # Determine if rendering is needed
        needs_rendering = (
            word_delta >= self.config.min_word_delta
            and word_delta_ratio >= self.config.min_delta_ratio
        ) or similarity < self.config.similarity_threshold

        return RenderDelta(
            static_content=static_text,
            rendered_content=rendered_text,
            static_word_count=static_words,
            rendered_word_count=rendered_words,
            word_delta=word_delta,
            word_delta_ratio=word_delta_ratio,
            content_similarity=similarity,
            needs_rendering=needs_rendering,
            detection_url=url,
        )

    async def detect_site_mode(
        self,
        urls: list[str],
    ) -> tuple[RenderMode, list[RenderDelta]]:
        """
        Determine render mode for a site by sampling multiple pages.

        Args:
            urls: List of URLs to sample (will use up to sample_count)

        Returns:
            Tuple of (recommended_mode, list of delta results)
        """
        if not urls:
            return RenderMode.STATIC, []

        # Sample up to config.sample_count pages
        sample_urls = urls[: self.config.sample_count]

        deltas: list[RenderDelta] = []
        needs_rendering_count = 0

        for url in sample_urls:
            try:
                delta = await self.detect_delta(url)
                deltas.append(delta)
                if delta.needs_rendering:
                    needs_rendering_count += 1
            except Exception:
                # Skip failed URLs
                continue

        if not deltas:
            return RenderMode.STATIC, []

        # If majority of sampled pages need rendering, use rendered mode
        if needs_rendering_count > len(deltas) / 2:
            return RenderMode.RENDERED, deltas

        return RenderMode.STATIC, deltas


async def detect_render_mode(
    url: str,
    additional_urls: list[str] | None = None,
    config: RendererConfig | None = None,
) -> tuple[RenderMode, list[RenderDelta]]:
    """
    Convenience function to detect render mode for a site.

    Args:
        url: Primary URL to test
        additional_urls: Additional URLs to sample
        config: Renderer configuration

    Returns:
        Tuple of (render_mode, delta_results)
    """
    if not PLAYWRIGHT_AVAILABLE:
        # Without Playwright, can only do static
        return RenderMode.STATIC, []

    urls = [url] + (additional_urls or [])
    detector = RenderDeltaDetector(config=config)

    return await detector.detect_site_mode(urls)
