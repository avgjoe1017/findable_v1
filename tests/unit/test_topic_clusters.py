"""Unit tests for topic cluster detection."""

import pytest

from worker.extraction.topic_clusters import (
    analyze_topic_clusters,
)


class TestTopicClusterAnalyzer:
    """Tests for TopicClusterAnalyzer class."""

    def test_empty_pages(self):
        """Test with no pages."""
        result = analyze_topic_clusters([])

        assert result.cluster_count == 0
        assert result.level == "limited"
        assert "No pages" in result.issues[0]

    def test_single_page(self):
        """Test with single page."""
        pages = [
            {
                "url": "https://example.com",
                "word_count": 500,
                "title": "Home",
                "internal_links": [],
            }
        ]
        result = analyze_topic_clusters(pages)

        assert result.cluster_count == 0
        assert result.total_score >= 0

    def test_pillar_page_detection(self):
        """Test detection of pillar pages."""
        pages = [
            {
                "url": "https://example.com/guide",
                "word_count": 3000,  # Long content
                "title": "Complete Guide to Topic",
                "internal_links": [
                    "https://example.com/subtopic1",
                    "https://example.com/subtopic2",
                    "https://example.com/subtopic3",
                    "https://example.com/subtopic4",
                    "https://example.com/subtopic5",
                ],
            },
            {
                "url": "https://example.com/subtopic1",
                "word_count": 1200,
                "title": "Subtopic 1",
                "internal_links": [],
            },
            {
                "url": "https://example.com/subtopic2",
                "word_count": 1500,
                "title": "Subtopic 2",
                "internal_links": [],
            },
            {
                "url": "https://example.com/subtopic3",
                "word_count": 1100,
                "title": "Subtopic 3",
                "internal_links": [],
            },
            {
                "url": "https://example.com/subtopic4",
                "word_count": 1300,
                "title": "Subtopic 4",
                "internal_links": [],
            },
            {
                "url": "https://example.com/subtopic5",
                "word_count": 1400,
                "title": "Subtopic 5",
                "internal_links": [],
            },
        ]
        result = analyze_topic_clusters(pages)

        assert len(result.pillar_pages) == 1
        assert "https://example.com/guide" in result.pillar_pages

    def test_cluster_detection(self):
        """Test detection of topic clusters."""
        pages = [
            {
                "url": "https://example.com/pillar",
                "word_count": 2500,
                "title": "Main Guide",
                "internal_links": [
                    "https://example.com/cluster1",
                    "https://example.com/cluster2",
                    "https://example.com/cluster3",
                    "https://example.com/cluster4",
                    "https://example.com/cluster5",
                ],
            },
            {
                "url": "https://example.com/cluster1",
                "word_count": 1200,
                "title": "Cluster 1",
                "internal_links": ["https://example.com/pillar"],
            },
            {
                "url": "https://example.com/cluster2",
                "word_count": 1300,
                "title": "Cluster 2",
                "internal_links": ["https://example.com/pillar"],
            },
            {
                "url": "https://example.com/cluster3",
                "word_count": 1100,
                "title": "Cluster 3",
                "internal_links": ["https://example.com/pillar"],
            },
            {
                "url": "https://example.com/cluster4",
                "word_count": 1400,
                "title": "Cluster 4",
                "internal_links": [],  # No link back
            },
            {
                "url": "https://example.com/cluster5",
                "word_count": 1500,
                "title": "Cluster 5",
                "internal_links": ["https://example.com/pillar"],
            },
        ]
        result = analyze_topic_clusters(pages)

        assert result.cluster_count == 1
        assert result.clusters[0].pillar_url == "https://example.com/pillar"
        assert len(result.clusters[0].cluster_pages) >= 3

    def test_bidirectional_link_detection(self):
        """Test detection of bidirectional links."""
        pages = [
            {
                "url": "https://example.com/page1",
                "word_count": 2500,
                "title": "Page 1",
                "internal_links": [
                    "https://example.com/page2",
                    "https://example.com/page3",
                    "https://example.com/page4",
                    "https://example.com/page5",
                    "https://example.com/page6",
                ],
            },
            {
                "url": "https://example.com/page2",
                "word_count": 1200,
                "title": "Page 2",
                "internal_links": ["https://example.com/page1"],  # Links back
            },
            {
                "url": "https://example.com/page3",
                "word_count": 1300,
                "title": "Page 3",
                "internal_links": ["https://example.com/page1"],  # Links back
            },
            {
                "url": "https://example.com/page4",
                "word_count": 1100,
                "title": "Page 4",
                "internal_links": [],  # No link back
            },
            {
                "url": "https://example.com/page5",
                "word_count": 1400,
                "title": "Page 5",
                "internal_links": [],  # No link back
            },
            {
                "url": "https://example.com/page6",
                "word_count": 1500,
                "title": "Page 6",
                "internal_links": ["https://example.com/page1"],  # Links back
            },
        ]
        result = analyze_topic_clusters(pages)

        assert result.bidirectional_link_count >= 3
        assert result.bidirectional_ratio > 0

    def test_orphan_page_detection(self):
        """Test detection of orphan pages."""
        pages = [
            {
                "url": "https://example.com",
                "word_count": 500,
                "title": "Home",
                "internal_links": ["https://example.com/page1"],
            },
            {
                "url": "https://example.com/page1",
                "word_count": 800,
                "title": "Page 1",
                "internal_links": [],
            },
            {
                "url": "https://example.com/orphan",
                "word_count": 600,
                "title": "Orphan Page",
                "internal_links": [],  # No one links to this
            },
        ]
        result = analyze_topic_clusters(pages)

        assert len(result.orphan_pages) == 1
        assert "https://example.com/orphan" in result.orphan_pages

    def test_thin_content_detection(self):
        """Test detection of thin content pages."""
        pages = [
            {
                "url": "https://example.com/thin",
                "word_count": 150,  # Very thin
                "title": "Thin Page",
                "internal_links": [],
            },
            {
                "url": "https://example.com/normal",
                "word_count": 800,
                "title": "Normal Page",
                "internal_links": ["https://example.com/thin"],
            },
        ]
        result = analyze_topic_clusters(pages)

        assert len(result.thin_pages) == 1
        assert "https://example.com/thin" in result.thin_pages

    def test_cluster_bidirectional_ratio(self):
        """Test cluster bidirectional ratio calculation."""
        pages = [
            {
                "url": "https://example.com/pillar",
                "word_count": 3000,
                "title": "Pillar",
                "internal_links": [
                    "https://example.com/c1",
                    "https://example.com/c2",
                    "https://example.com/c3",
                    "https://example.com/c4",
                    "https://example.com/c5",
                ],
            },
            {
                "url": "https://example.com/c1",
                "word_count": 1200,
                "title": "C1",
                "internal_links": ["https://example.com/pillar"],
            },
            {
                "url": "https://example.com/c2",
                "word_count": 1200,
                "title": "C2",
                "internal_links": ["https://example.com/pillar"],
            },
            {
                "url": "https://example.com/c3",
                "word_count": 1200,
                "title": "C3",
                "internal_links": [],  # No link back
            },
            {
                "url": "https://example.com/c4",
                "word_count": 1200,
                "title": "C4",
                "internal_links": [],  # No link back
            },
            {
                "url": "https://example.com/c5",
                "word_count": 1200,
                "title": "C5",
                "internal_links": [],  # No link back
            },
        ]
        result = analyze_topic_clusters(pages)

        assert result.cluster_count == 1
        # 2 out of 5 link back = 40%
        assert result.clusters[0].bidirectional_ratio == pytest.approx(0.4, rel=0.1)

    def test_scoring_good_structure(self):
        """Test that good cluster structure scores well."""
        # Well-structured site with pillar and cluster pages that link back
        pages = [
            {
                "url": "https://example.com/guide",
                "word_count": 2500,
                "title": "Complete Guide",
                "internal_links": [
                    "https://example.com/part1",
                    "https://example.com/part2",
                    "https://example.com/part3",
                    "https://example.com/part4",
                    "https://example.com/part5",
                ],
            },
        ]
        # Add cluster pages that link back
        for i in range(1, 6):
            pages.append(
                {
                    "url": f"https://example.com/part{i}",
                    "word_count": 1200,
                    "title": f"Part {i}",
                    "internal_links": ["https://example.com/guide"],
                }
            )

        result = analyze_topic_clusters(pages)

        assert result.cluster_count >= 1
        assert result.total_score >= 50
        assert result.level in ["full", "partial"]

    def test_scoring_poor_structure(self):
        """Test that poor structure scores low."""
        # Disconnected pages with no linking
        pages = [
            {
                "url": f"https://example.com/page{i}",
                "word_count": 500,
                "title": f"Page {i}",
                "internal_links": [],
            }
            for i in range(10)
        ]
        result = analyze_topic_clusters(pages)

        assert result.cluster_count == 0
        assert len(result.orphan_pages) > 0
        assert result.total_score < 50

    def test_recommendations_generated(self):
        """Test that recommendations are generated for issues."""
        # Site with issues
        pages = [
            {
                "url": "https://example.com/orphan1",
                "word_count": 500,
                "title": "Orphan 1",
                "internal_links": [],
            },
            {
                "url": "https://example.com/orphan2",
                "word_count": 500,
                "title": "Orphan 2",
                "internal_links": [],
            },
            {
                "url": "https://example.com/thin",
                "word_count": 100,
                "title": "Thin",
                "internal_links": [],
            },
        ]
        result = analyze_topic_clusters(pages)

        assert len(result.issues) > 0
        assert len(result.recommendations) > 0

    def test_to_dict_serializable(self):
        """Test that to_dict produces JSON-serializable output."""
        import json

        pages = [
            {
                "url": "https://example.com/page",
                "word_count": 1000,
                "title": "Test",
                "internal_links": [],
            }
        ]
        result = analyze_topic_clusters(pages)
        data = result.to_dict()

        # Should not raise
        json_str = json.dumps(data)
        assert len(json_str) > 0

    def test_url_normalization(self):
        """Test URL normalization for comparison."""
        pages = [
            {
                "url": "https://example.com/page/",
                "word_count": 2500,
                "title": "Page",
                "internal_links": [
                    "https://example.com/other",  # Without slash
                    "HTTPS://EXAMPLE.COM/ANOTHER/",  # Uppercase
                    "https://example.com/fragment#section",  # With fragment
                    "https://example.com/query?foo=bar",  # With query
                    "https://example.com/c1",
                    "https://example.com/c2",
                ],
            },
            {
                "url": "https://example.com/other/",  # With slash
                "word_count": 1200,
                "title": "Other",
                "internal_links": ["https://example.com/page"],
            },
            {
                "url": "https://example.com/another",  # Without slash
                "word_count": 1200,
                "title": "Another",
                "internal_links": ["https://example.com/page/"],
            },
            {
                "url": "https://example.com/c1",
                "word_count": 1200,
                "title": "C1",
                "internal_links": [],
            },
            {
                "url": "https://example.com/c2",
                "word_count": 1200,
                "title": "C2",
                "internal_links": [],
            },
        ]
        result = analyze_topic_clusters(pages)

        # Should recognize bidirectional links despite URL variations
        assert result.bidirectional_link_count >= 2


class TestTopicClusterScoring:
    """Tests for topic cluster scoring specifics."""

    def test_small_site_no_penalty(self):
        """Small sites shouldn't be penalized for lacking clusters."""
        pages = [
            {
                "url": f"https://example.com/page{i}",
                "word_count": 800,
                "title": f"Page {i}",
                "internal_links": [f"https://example.com/page{(i+1) % 5}"],
            }
            for i in range(5)
        ]
        result = analyze_topic_clusters(pages)

        # Small site, clusters less relevant
        assert result.total_score >= 40

    def test_link_density_impact(self):
        """Test that link density affects score."""
        # Good link density
        pages_good = [
            {
                "url": "https://example.com/page1",
                "word_count": 1000,
                "title": "Page 1",
                "internal_links": [
                    "https://example.com/page2",
                    "https://example.com/page3",
                    "https://example.com/page4",
                    "https://example.com/page5",
                    "https://example.com/page6",
                ],
            },
        ]
        for i in range(2, 7):
            pages_good.append(
                {
                    "url": f"https://example.com/page{i}",
                    "word_count": 800,
                    "title": f"Page {i}",
                    "internal_links": ["https://example.com/page1"],
                }
            )

        # Poor link density
        pages_poor = [
            {
                "url": f"https://example.com/page{i}",
                "word_count": 800,
                "title": f"Page {i}",
                "internal_links": [],  # No links
            }
            for i in range(6)
        ]

        result_good = analyze_topic_clusters(pages_good)
        result_poor = analyze_topic_clusters(pages_poor)

        assert result_good.link_health_score > result_poor.link_health_score
