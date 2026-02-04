"""Topic cluster and pillar page detection.

Analyzes site structure to identify topic clusters - a key factor
in AI citation likelihood. Research shows clustered content generates
30% more organic traffic and maintains rankings 2.5x longer.

A topic cluster consists of:
- Pillar page: Comprehensive guide (2000-4000 words) that links to cluster pages
- Cluster pages: Deep-dive articles (1000-2000 words) that link back to pillar
- Bidirectional linking: Pillar ↔ Cluster connections
"""

from dataclasses import dataclass, field
from urllib.parse import urlparse

import structlog

logger = structlog.get_logger(__name__)


# Thresholds based on research
PILLAR_MIN_WORDS = 2000
PILLAR_MAX_WORDS = 5000
CLUSTER_MIN_WORDS = 800
CLUSTER_MAX_WORDS = 2500
MIN_CLUSTER_SIZE = 3  # Minimum pages to form a cluster
MIN_INTERNAL_LINKS_PILLAR = 5  # Pillar should link to at least 5 cluster pages


@dataclass
class PageInfo:
    """Information about a single page for cluster analysis."""

    url: str
    word_count: int = 0
    title: str = ""

    # Link data
    outbound_internal_links: list[str] = field(default_factory=list)
    inbound_internal_links: list[str] = field(default_factory=list)

    # Classification
    page_type: str = "unknown"  # pillar, cluster, orphan, thin, normal
    cluster_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "word_count": self.word_count,
            "title": self.title[:100] if self.title else "",
            "outbound_count": len(self.outbound_internal_links),
            "inbound_count": len(self.inbound_internal_links),
            "page_type": self.page_type,
            "cluster_id": self.cluster_id,
        }


@dataclass
class TopicCluster:
    """A detected topic cluster."""

    id: str
    pillar_url: str
    pillar_title: str
    cluster_pages: list[str] = field(default_factory=list)

    # Quality metrics
    bidirectional_links: int = 0  # Pages that link both ways
    total_links: int = 0
    bidirectional_ratio: float = 0.0

    # Completeness
    cluster_size: int = 0
    avg_cluster_word_count: float = 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pillar_url": self.pillar_url,
            "pillar_title": self.pillar_title[:100] if self.pillar_title else "",
            "cluster_pages": self.cluster_pages[:20],  # Limit output
            "cluster_size": self.cluster_size,
            "bidirectional_links": self.bidirectional_links,
            "bidirectional_ratio": round(self.bidirectional_ratio, 2),
            "avg_cluster_word_count": round(self.avg_cluster_word_count, 1),
        }


@dataclass
class TopicClusterAnalysis:
    """Complete topic cluster analysis result."""

    # Detected clusters
    clusters: list[TopicCluster] = field(default_factory=list)
    cluster_count: int = 0

    # Page classification
    pillar_pages: list[str] = field(default_factory=list)
    cluster_pages: list[str] = field(default_factory=list)
    orphan_pages: list[str] = field(default_factory=list)  # No inbound links
    thin_pages: list[str] = field(default_factory=list)  # < 300 words

    # Link health
    total_internal_links: int = 0
    bidirectional_link_count: int = 0
    bidirectional_ratio: float = 0.0  # Site-wide
    avg_internal_links_per_page: float = 0.0

    # Score
    cluster_score: float = 0.0  # 0-100
    link_health_score: float = 0.0  # 0-100
    total_score: float = 0.0
    level: str = "unknown"  # good, warning, critical

    # Issues and recommendations
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clusters": [c.to_dict() for c in self.clusters[:10]],
            "cluster_count": self.cluster_count,
            "page_classification": {
                "pillar_pages": len(self.pillar_pages),
                "cluster_pages": len(self.cluster_pages),
                "orphan_pages": len(self.orphan_pages),
                "thin_pages": len(self.thin_pages),
            },
            "link_health": {
                "total_internal_links": self.total_internal_links,
                "bidirectional_count": self.bidirectional_link_count,
                "bidirectional_ratio": round(self.bidirectional_ratio, 2),
                "avg_links_per_page": round(self.avg_internal_links_per_page, 1),
            },
            "scores": {
                "cluster_score": round(self.cluster_score, 1),
                "link_health_score": round(self.link_health_score, 1),
                "total_score": round(self.total_score, 1),
            },
            "level": self.level,
            "issues": self.issues[:10],
            "recommendations": self.recommendations[:5],
        }


class TopicClusterAnalyzer:
    """Analyzes site structure for topic clusters."""

    def __init__(
        self,
        pillar_min_words: int = PILLAR_MIN_WORDS,
        cluster_min_words: int = CLUSTER_MIN_WORDS,
        min_cluster_size: int = MIN_CLUSTER_SIZE,
    ):
        self.pillar_min_words = pillar_min_words
        self.cluster_min_words = cluster_min_words
        self.min_cluster_size = min_cluster_size

    def analyze(
        self,
        pages: list[dict],
    ) -> TopicClusterAnalysis:
        """
        Analyze pages for topic cluster structure.

        Args:
            pages: List of page data dicts with keys:
                - url: Page URL
                - word_count: Number of words
                - title: Page title
                - internal_links: List of internal URLs this page links to

        Returns:
            TopicClusterAnalysis with cluster detection and scoring
        """
        result = TopicClusterAnalysis()

        if not pages:
            result.level = "critical"
            result.issues.append("No pages to analyze")
            return result

        # Build page info objects
        page_map: dict[str, PageInfo] = {}
        for page in pages:
            url = self._normalize_url(page.get("url", ""))
            if not url:
                continue

            page_info = PageInfo(
                url=url,
                word_count=page.get("word_count", 0),
                title=page.get("title", ""),
                outbound_internal_links=[
                    self._normalize_url(link) for link in page.get("internal_links", [])
                ],
            )
            page_map[url] = page_info

        # Build inbound link map
        for url, page_info in page_map.items():
            for target_url in page_info.outbound_internal_links:
                if target_url in page_map:
                    page_map[target_url].inbound_internal_links.append(url)

        # Classify pages
        self._classify_pages(page_map, result)

        # Detect clusters
        self._detect_clusters(page_map, result)

        # Calculate link health
        self._calculate_link_health(page_map, result)

        # Calculate scores
        self._calculate_scores(page_map, result)

        # Generate issues and recommendations
        self._generate_recommendations(page_map, result)

        logger.info(
            "topic_cluster_analysis_complete",
            cluster_count=result.cluster_count,
            pillar_pages=len(result.pillar_pages),
            orphan_pages=len(result.orphan_pages),
            bidirectional_ratio=result.bidirectional_ratio,
            total_score=result.total_score,
        )

        return result

    def _normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        if not url:
            return ""
        # Remove trailing slashes and fragments
        url = url.rstrip("/").split("#")[0].split("?")[0]
        return url.lower()

    def _classify_pages(
        self,
        page_map: dict[str, PageInfo],
        result: TopicClusterAnalysis,
    ) -> None:
        """Classify pages by type."""
        for url, page in page_map.items():
            word_count = page.word_count
            inbound_count = len(page.inbound_internal_links)
            outbound_count = len(page.outbound_internal_links)

            # Thin content
            if word_count < 300:
                page.page_type = "thin"
                result.thin_pages.append(url)
            # Pillar candidate: long content + many outbound links
            elif (
                word_count >= self.pillar_min_words and outbound_count >= MIN_INTERNAL_LINKS_PILLAR
            ):
                page.page_type = "pillar"
                result.pillar_pages.append(url)
            # Cluster candidate: medium content + has inbound links
            elif self.cluster_min_words <= word_count < self.pillar_min_words and inbound_count > 0:
                page.page_type = "cluster"
                result.cluster_pages.append(url)
            # Orphan: no inbound links (except homepage)
            elif inbound_count == 0 and not self._is_homepage(url):
                page.page_type = "orphan"
                result.orphan_pages.append(url)
            else:
                page.page_type = "normal"

    def _is_homepage(self, url: str) -> bool:
        """Check if URL is likely the homepage."""
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        return path == "" or path in ["index", "index.html", "home"]

    def _detect_clusters(
        self,
        page_map: dict[str, PageInfo],
        result: TopicClusterAnalysis,
    ) -> None:
        """Detect topic clusters around pillar pages."""
        cluster_id = 0

        for pillar_url in result.pillar_pages:
            pillar = page_map[pillar_url]

            # Find cluster pages linked from this pillar
            cluster_pages = []
            bidirectional = 0

            for target_url in pillar.outbound_internal_links:
                if target_url not in page_map:
                    continue

                target = page_map[target_url]

                # Check if target links back (bidirectional)
                links_back = pillar_url in target.outbound_internal_links

                # Include if it's a cluster-type page or links back
                if target.page_type in ["cluster", "normal"] or links_back:
                    cluster_pages.append(target_url)
                    if links_back:
                        bidirectional += 1

            # Only create cluster if minimum size met
            if len(cluster_pages) >= self.min_cluster_size:
                cluster_id += 1

                # Calculate average word count
                word_counts = [page_map[url].word_count for url in cluster_pages if url in page_map]
                avg_words = sum(word_counts) / len(word_counts) if word_counts else 0

                cluster = TopicCluster(
                    id=f"cluster_{cluster_id}",
                    pillar_url=pillar_url,
                    pillar_title=pillar.title,
                    cluster_pages=cluster_pages,
                    bidirectional_links=bidirectional,
                    total_links=len(cluster_pages),
                    bidirectional_ratio=(
                        bidirectional / len(cluster_pages) if cluster_pages else 0
                    ),
                    cluster_size=len(cluster_pages),
                    avg_cluster_word_count=avg_words,
                )

                result.clusters.append(cluster)

                # Mark pages as belonging to this cluster
                pillar.cluster_id = cluster.id
                for page_url in cluster_pages:
                    if page_url in page_map:
                        page_map[page_url].cluster_id = cluster.id

        result.cluster_count = len(result.clusters)

    def _calculate_link_health(
        self,
        page_map: dict[str, PageInfo],
        result: TopicClusterAnalysis,
    ) -> None:
        """Calculate link health metrics."""
        total_links = 0
        bidirectional_pairs = set()

        for url, page in page_map.items():
            total_links += len(page.outbound_internal_links)

            # Check for bidirectional links
            for target_url in page.outbound_internal_links:
                if target_url in page_map:
                    target = page_map[target_url]
                    if url in target.outbound_internal_links:
                        # Store as sorted tuple to avoid counting twice
                        pair = tuple(sorted([url, target_url]))
                        bidirectional_pairs.add(pair)

        result.total_internal_links = total_links
        result.bidirectional_link_count = len(bidirectional_pairs)

        # Calculate ratios
        if len(page_map) > 0:
            result.avg_internal_links_per_page = total_links / len(page_map)

        # Bidirectional ratio: what % of pages have at least one bidirectional link
        pages_with_bidirectional = set()
        for pair in bidirectional_pairs:
            pages_with_bidirectional.add(pair[0])
            pages_with_bidirectional.add(pair[1])

        if len(page_map) > 0:
            result.bidirectional_ratio = len(pages_with_bidirectional) / len(page_map)

    def _calculate_scores(
        self,
        page_map: dict[str, PageInfo],
        result: TopicClusterAnalysis,
    ) -> None:
        """Calculate cluster and link health scores."""
        total_pages = len(page_map)
        if total_pages == 0:
            result.level = "critical"
            return

        # Cluster score (0-100)
        # Based on: having clusters, cluster coverage, bidirectional linking within clusters
        cluster_score = 0.0

        if result.cluster_count > 0:
            cluster_score += 30  # Base for having any clusters

            # Pages in clusters vs total
            pages_in_clusters = len(result.pillar_pages) + len(result.cluster_pages)
            coverage = pages_in_clusters / total_pages
            cluster_score += coverage * 30  # Up to 30 for coverage

            # Average bidirectional ratio within clusters
            if result.clusters:
                avg_bidir = sum(c.bidirectional_ratio for c in result.clusters) / len(
                    result.clusters
                )
                cluster_score += avg_bidir * 40  # Up to 40 for bidirectional linking
        else:
            # No clusters - check if site is small enough that it doesn't need them
            if total_pages < 10:
                cluster_score = 50  # Small site, clusters less relevant

        result.cluster_score = min(100, cluster_score)

        # Link health score (0-100)
        link_score = 50.0  # Base

        # Penalize orphan pages
        orphan_ratio = len(result.orphan_pages) / total_pages if total_pages > 0 else 0
        link_score -= orphan_ratio * 30  # Up to -30 for orphans

        # Reward good link density (5-15 per page is optimal)
        avg_links = result.avg_internal_links_per_page
        if 5 <= avg_links <= 15:
            link_score += 25
        elif 3 <= avg_links < 5 or 15 < avg_links <= 25:
            link_score += 15
        elif avg_links < 3:
            link_score -= 10

        # Reward bidirectional linking
        link_score += result.bidirectional_ratio * 25

        result.link_health_score = max(0, min(100, link_score))

        # Total score (weighted average)
        result.total_score = result.cluster_score * 0.6 + result.link_health_score * 0.4

        # Determine level
        if result.total_score >= 70:
            result.level = "good"
        elif result.total_score >= 40:
            result.level = "warning"
        else:
            result.level = "critical"

    def _generate_recommendations(
        self,
        page_map: dict[str, PageInfo],
        result: TopicClusterAnalysis,
    ) -> None:
        """Generate actionable recommendations."""
        total_pages = len(page_map)

        # Cluster issues
        if result.cluster_count == 0 and total_pages >= 10:
            result.issues.append("No topic clusters detected. Content appears disconnected.")
            result.recommendations.append(
                "Create pillar pages (2000+ words) that comprehensively cover your main topics, "
                "then link them to related cluster pages (1000-2000 words each)."
            )

        # Low bidirectional linking
        if result.bidirectional_ratio < 0.3 and total_pages >= 5:
            result.issues.append(
                f"Only {result.bidirectional_ratio:.0%} of pages have bidirectional links. "
                "AI systems use link patterns to understand topic relationships."
            )
            result.recommendations.append(
                "Add links from cluster pages back to their pillar pages. "
                "Each article should link to its parent topic guide."
            )

        # Orphan pages
        if result.orphan_pages:
            orphan_count = len(result.orphan_pages)
            result.issues.append(
                f"{orphan_count} orphan page(s) with no inbound links. "
                "These are invisible to AI crawlers following links."
            )
            if orphan_count <= 5:
                result.recommendations.append(
                    f"Add internal links to these orphan pages: {', '.join(result.orphan_pages[:5])}"
                )
            else:
                result.recommendations.append(
                    f"Add internal links to {orphan_count} orphan pages. "
                    "Start with the most important content."
                )

        # Thin content
        if result.thin_pages:
            thin_count = len(result.thin_pages)
            if thin_count > total_pages * 0.2:  # More than 20% thin
                result.issues.append(
                    f"{thin_count} pages ({thin_count/total_pages:.0%}) have thin content (<300 words). "
                    "AI systems prefer substantial content."
                )
                result.recommendations.append(
                    "Expand thin pages to at least 800 words, or consolidate them into comprehensive guides."
                )

        # Low link density
        if result.avg_internal_links_per_page < 3:
            result.issues.append(
                f"Average {result.avg_internal_links_per_page:.1f} internal links per page. "
                "Target is 5-15 for good discoverability."
            )
            result.recommendations.append(
                "Add contextual internal links within your content. "
                "Link to related articles when mentioning relevant topics."
            )

        # Clusters with poor bidirectional linking
        for cluster in result.clusters:
            if cluster.bidirectional_ratio < 0.5:
                result.recommendations.append(
                    f"Cluster '{cluster.pillar_title[:50]}' has {cluster.bidirectional_ratio:.0%} "
                    f"bidirectional linking. Add links from cluster pages back to the pillar."
                )


def analyze_topic_clusters(pages: list[dict]) -> TopicClusterAnalysis:
    """
    Convenience function to analyze topic clusters.

    Args:
        pages: List of page data dicts with url, word_count, title, internal_links

    Returns:
        TopicClusterAnalysis with cluster detection and scoring
    """
    analyzer = TopicClusterAnalyzer()
    return analyzer.analyze(pages)
