"""Internal link analysis for content structure.

Analyzes internal linking patterns which affect AI's ability
to understand site structure and find related content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse

import structlog
from bs4 import BeautifulSoup

logger = structlog.get_logger(__name__)


# Optimal internal link density range
MIN_LINKS_PER_PAGE = 5
MAX_LINKS_PER_PAGE = 50
OPTIMAL_MIN = 5
OPTIMAL_MAX = 15


@dataclass
class LinkInfo:
    """Information about a single link."""

    href: str
    anchor_text: str
    is_internal: bool
    is_navigation: bool  # In nav/header/footer
    is_in_content: bool  # In main content area
    has_good_anchor: bool  # Descriptive anchor text


@dataclass
class LinkAnalysis:
    """Complete link analysis result for a page."""

    # Counts
    total_links: int = 0
    internal_links: int = 0
    external_links: int = 0

    # Quality metrics
    content_internal_links: int = 0  # Internal links in main content
    nav_links: int = 0  # Links in navigation areas
    good_anchor_count: int = 0  # Links with descriptive anchors

    # Density
    link_density: float = 0.0  # Internal links per 1000 words
    density_level: str = "unknown"  # low, optimal, high

    # Score
    score: float = 100.0  # 0-100
    issues: list[str] = field(default_factory=list)

    # Detailed link data
    links: list[LinkInfo] = field(default_factory=list)

    # Anchor text analysis
    unique_anchors: int = 0
    empty_anchors: int = 0  # Links with no text (just images, etc.)
    generic_anchors: int = 0  # "click here", "read more", etc.

    def to_dict(self) -> dict:
        return {
            "total_links": self.total_links,
            "internal_links": self.internal_links,
            "external_links": self.external_links,
            "content_internal_links": self.content_internal_links,
            "nav_links": self.nav_links,
            "good_anchor_count": self.good_anchor_count,
            "link_density": round(self.link_density, 2),
            "density_level": self.density_level,
            "score": round(self.score, 2),
            "issues": self.issues,
            "unique_anchors": self.unique_anchors,
            "empty_anchors": self.empty_anchors,
            "generic_anchors": self.generic_anchors,
        }


# Generic anchor text patterns (bad for SEO and AI understanding)
GENERIC_ANCHORS = {
    "click here",
    "click",
    "here",
    "read more",
    "more",
    "learn more",
    "continue",
    "link",
    "this",
    "this link",
    "see more",
    "view more",
    "details",
    "info",
    "read",
}

# Navigation container selectors
NAV_CONTAINERS = ["nav", "header", "footer", ".nav", ".navigation", ".menu", ".sidebar"]


class LinkAnalyzer:
    """Analyzes internal linking for AI extractability."""

    def __init__(
        self,
        optimal_min: int = OPTIMAL_MIN,
        optimal_max: int = OPTIMAL_MAX,
        min_anchor_length: int = 3,
    ):
        self.optimal_min = optimal_min
        self.optimal_max = optimal_max
        self.min_anchor_length = min_anchor_length

    def analyze(self, html: str, url: str, word_count: int = 0) -> LinkAnalysis:
        """
        Analyze internal linking in HTML.

        Args:
            html: HTML content to analyze
            url: Page URL for determining internal vs external
            word_count: Word count for density calculation

        Returns:
            LinkAnalysis with link metrics and score
        """
        soup = BeautifulSoup(html, "html.parser")
        result = LinkAnalysis()

        # Extract domain from URL
        parsed = urlparse(url)
        base_domain = parsed.netloc.lower()
        if base_domain.startswith("www."):
            base_domain = base_domain[4:]

        # Find all navigation containers
        nav_containers = set()
        for selector in NAV_CONTAINERS:
            if selector.startswith("."):
                for el in soup.select(selector):
                    nav_containers.add(id(el))
            else:
                for el in soup.find_all(selector):
                    nav_containers.add(id(el))

        # Find main content area
        main_content = (
            soup.find("main")
            or soup.find("article")
            or soup.find(id="content")
            or soup.find(class_="content")
        )

        # Pre-compute which links are in main content (O(n) vs O(n²))
        main_content_links = set()
        if main_content:
            for a_tag in main_content.find_all("a", href=True):  # type: ignore[union-attr]
                main_content_links.add(id(a_tag))

        # Pre-compute which links are in nav containers (O(n) vs O(n²))
        nav_links = set()
        for container in soup.find_all(NAV_CONTAINERS[:3]):  # nav, header, footer
            for a_tag in container.find_all("a", href=True):
                nav_links.add(id(a_tag))
        for selector in NAV_CONTAINERS[3:]:  # class selectors
            if selector.startswith("."):
                for container in soup.select(selector):
                    for a_tag in container.find_all("a", href=True):
                        nav_links.add(id(a_tag))

        # Process all links
        links = []
        seen_anchors = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            anchor_text = a_tag.get_text(strip=True)

            # Skip empty hrefs
            if not href or href == "#":
                continue

            # Determine if internal
            is_internal = self._is_internal_link(href, base_domain, url)

            # Determine if in navigation (O(1) lookup instead of O(n))
            is_nav = id(a_tag) in nav_links

            # Determine if in content (O(1) lookup instead of O(n))
            is_in_content = id(a_tag) in main_content_links or (main_content is None and not is_nav)

            # Analyze anchor text quality
            has_good_anchor = self._is_good_anchor(anchor_text)

            link_info = LinkInfo(
                href=href,
                anchor_text=anchor_text[:200] if anchor_text else "",
                is_internal=is_internal,
                is_navigation=is_nav,
                is_in_content=is_in_content,
                has_good_anchor=has_good_anchor,
            )
            links.append(link_info)

            # Update counts
            result.total_links += 1

            if is_internal:
                result.internal_links += 1
                if is_in_content:
                    result.content_internal_links += 1
                if is_nav:
                    result.nav_links += 1
            else:
                result.external_links += 1

            if has_good_anchor:
                result.good_anchor_count += 1

            # Anchor analysis
            if anchor_text:
                anchor_lower = anchor_text.lower().strip()
                if anchor_lower not in seen_anchors:
                    result.unique_anchors += 1
                    seen_anchors.add(anchor_lower)

                if anchor_lower in GENERIC_ANCHORS:
                    result.generic_anchors += 1
            else:
                result.empty_anchors += 1

        result.links = links

        # Calculate density
        if word_count > 0:
            result.link_density = (result.internal_links / word_count) * 1000

        # Determine density level
        if result.internal_links < self.optimal_min:
            result.density_level = "low"
        elif result.internal_links > self.optimal_max:
            result.density_level = "high"
        else:
            result.density_level = "optimal"

        # Calculate score and identify issues
        result.score, result.issues = self._calculate_score(result)

        logger.debug(
            "link_analysis_complete",
            internal_links=result.internal_links,
            external_links=result.external_links,
            density_level=result.density_level,
            score=result.score,
        )

        return result

    def _is_internal_link(self, href: str, base_domain: str, page_url: str) -> bool:
        """Check if a link is internal."""
        # Relative URLs are internal
        if href.startswith(("/", "#", "?")):
            return True
        if href.startswith("mailto:") or href.startswith("tel:"):
            return False

        try:
            # Resolve relative URLs
            full_url = urljoin(page_url, href)
            parsed = urlparse(full_url)
            link_domain = parsed.netloc.lower()
            if link_domain.startswith("www."):
                link_domain = link_domain[4:]
            return link_domain == base_domain
        except Exception:
            return False

    def _is_in_container(self, element: Any, container_ids: set[int]) -> bool:
        """Check if element is inside any of the specified containers."""
        parent = element.parent
        while parent:
            if id(parent) in container_ids:
                return True
            parent = parent.parent
        return False

    def _is_good_anchor(self, anchor_text: str) -> bool:
        """Check if anchor text is descriptive."""
        if not anchor_text:
            return False

        text = anchor_text.lower().strip()

        # Too short
        if len(text) < self.min_anchor_length:
            return False

        # Generic anchor
        if text in GENERIC_ANCHORS:
            return False

        # Just a URL
        return not (text.startswith("http://") or text.startswith("https://"))

    def _calculate_score(self, analysis: LinkAnalysis) -> tuple[float, list[str]]:
        """Calculate link quality score and identify issues."""
        score = 100.0
        issues = []

        # Penalize low internal link count
        if analysis.internal_links < MIN_LINKS_PER_PAGE:
            penalty = (MIN_LINKS_PER_PAGE - analysis.internal_links) * 5
            score -= penalty
            issues.append(
                f"Low internal link count ({analysis.internal_links}). "
                f"Target: {OPTIMAL_MIN}-{OPTIMAL_MAX} per page."
            )

        # Penalize too many links (can dilute value)
        if analysis.internal_links > MAX_LINKS_PER_PAGE:
            penalty = min(20, (analysis.internal_links - MAX_LINKS_PER_PAGE) * 0.5)  # type: ignore[assignment]
            score -= penalty
            issues.append(
                f"High internal link count ({analysis.internal_links}). " f"May dilute link value."
            )

        # Penalize no content links (all in nav)
        if analysis.internal_links > 0 and analysis.content_internal_links == 0:
            score -= 15
            issues.append(
                "No internal links in main content. " "All internal links are in navigation."
            )

        # Penalize empty anchors
        if analysis.empty_anchors > 3:
            penalty = min(10, analysis.empty_anchors * 2)
            score -= penalty
            issues.append(
                f"{analysis.empty_anchors} links have no anchor text. "
                "This hurts AI understanding."
            )

        # Penalize generic anchors
        if analysis.generic_anchors > 5:
            penalty = min(10, analysis.generic_anchors)
            score -= penalty
            issues.append(
                f"{analysis.generic_anchors} links use generic anchor text "
                "(e.g., 'click here'). Use descriptive anchors."
            )

        # Bonus for good anchor text ratio
        if analysis.total_links > 0:
            good_ratio = analysis.good_anchor_count / analysis.total_links
            if good_ratio >= 0.8:
                score = min(100, score + 5)  # Bonus

        return max(0, score), issues


def analyze_links(html: str, url: str, word_count: int = 0) -> LinkAnalysis:
    """
    Convenience function to analyze internal linking.

    Args:
        html: HTML content to analyze
        url: Page URL for determining internal vs external
        word_count: Word count for density calculation

    Returns:
        LinkAnalysis with link metrics and score
    """
    analyzer = LinkAnalyzer()
    return analyzer.analyze(html, url, word_count)
