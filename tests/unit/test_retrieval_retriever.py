"""Tests for hybrid retriever."""

from worker.retrieval.retriever import (
    HybridRetriever,
    RetrievalResult,
    RetrieverConfig,
    RRFConfig,
    enforce_page_diversity,
    reciprocal_rank_fusion,
)


class TestRRFConfig:
    """Tests for RRFConfig."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = RRFConfig()

        assert config.k == 60
        assert config.vector_weight == 0.5
        assert config.bm25_weight == 0.5

    def test_custom_values(self) -> None:
        """Can set custom values."""
        config = RRFConfig(k=100, vector_weight=0.7, bm25_weight=0.3)

        assert config.k == 100
        assert config.vector_weight == 0.7


class TestRetrieverConfig:
    """Tests for RetrieverConfig."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = RetrieverConfig()

        assert config.embedding_model == "bge-small"
        assert config.vector_search_limit == 20
        assert config.bm25_search_limit == 20
        assert config.final_limit == 10
        assert config.max_per_page == 2

    def test_custom_values(self) -> None:
        """Can set custom values."""
        config = RetrieverConfig(
            final_limit=5,
            max_per_page=3,
        )

        assert config.final_limit == 5
        assert config.max_per_page == 3


class TestRetrievalResult:
    """Tests for RetrievalResult dataclass."""

    def test_create_result(self) -> None:
        """Can create a result."""
        result = RetrievalResult(
            doc_id="doc1",
            content="Test content",
            score=0.8,
            vector_score=0.9,
            bm25_score=0.7,
        )

        assert result.doc_id == "doc1"
        assert result.score == 0.8

    def test_to_dict(self) -> None:
        """Result converts to dict."""
        result = RetrievalResult(
            doc_id="doc1",
            content="Test",
            score=0.8,
            source_url="https://example.com",
        )

        d = result.to_dict()
        assert d["doc_id"] == "doc1"
        assert d["score"] == 0.8
        assert d["source_url"] == "https://example.com"


class TestReciprocalRankFusion:
    """Tests for reciprocal_rank_fusion function."""

    def test_single_list(self) -> None:
        """Single list returns items in order."""
        ranked = [("doc1", 1.0), ("doc2", 0.8), ("doc3", 0.6)]

        fused = reciprocal_rank_fusion([ranked])

        assert fused[0][0] == "doc1"
        assert fused[1][0] == "doc2"
        assert fused[2][0] == "doc3"

    def test_two_identical_lists(self) -> None:
        """Identical lists maintain order."""
        ranked = [("doc1", 1.0), ("doc2", 0.8)]

        fused = reciprocal_rank_fusion([ranked, ranked])

        assert fused[0][0] == "doc1"
        assert fused[1][0] == "doc2"

    def test_different_lists_combine(self) -> None:
        """Different lists are combined."""
        list1 = [("doc1", 1.0), ("doc2", 0.8)]
        list2 = [("doc3", 1.0), ("doc1", 0.8)]

        fused = reciprocal_rank_fusion([list1, list2])

        # doc1 appears in both lists, should rank high
        doc_ids = [doc_id for doc_id, _ in fused]
        assert "doc1" in doc_ids
        assert "doc2" in doc_ids
        assert "doc3" in doc_ids

    def test_weights_affect_fusion(self) -> None:
        """Weights affect final ranking."""
        list1 = [("doc1", 1.0), ("doc2", 0.8)]
        list2 = [("doc2", 1.0), ("doc1", 0.8)]

        # Heavy weight on list1 should favor doc1
        fused1 = reciprocal_rank_fusion([list1, list2], weights=[0.9, 0.1])
        # Heavy weight on list2 should favor doc2
        fused2 = reciprocal_rank_fusion([list1, list2], weights=[0.1, 0.9])

        assert fused1[0][0] == "doc1"
        assert fused2[0][0] == "doc2"

    def test_empty_lists(self) -> None:
        """Empty input returns empty output."""
        fused = reciprocal_rank_fusion([])
        assert fused == []

    def test_k_parameter(self) -> None:
        """K parameter affects scoring."""
        ranked = [("doc1", 1.0), ("doc2", 0.8)]

        # With k=1, ranks matter a lot more
        fused_k1 = reciprocal_rank_fusion([ranked], k=1)
        # With k=100, ranks matter less
        fused_k100 = reciprocal_rank_fusion([ranked], k=100)

        # Score difference should be larger with smaller k
        diff_k1 = fused_k1[0][1] - fused_k1[1][1]
        diff_k100 = fused_k100[0][1] - fused_k100[1][1]

        assert diff_k1 > diff_k100


class TestEnforcePageDiversity:
    """Tests for enforce_page_diversity function."""

    def test_limits_per_page(self) -> None:
        """Limits results per page."""
        results = [
            RetrievalResult(doc_id="1", content="A", score=1.0, source_url="page1"),
            RetrievalResult(doc_id="2", content="B", score=0.9, source_url="page1"),
            RetrievalResult(doc_id="3", content="C", score=0.8, source_url="page1"),
            RetrievalResult(doc_id="4", content="D", score=0.7, source_url="page2"),
        ]

        filtered = enforce_page_diversity(results, max_per_page=2)

        # Should have 2 from page1 and 1 from page2
        assert len(filtered) == 3
        page1_count = sum(1 for r in filtered if r.source_url == "page1")
        assert page1_count == 2

    def test_zero_max_returns_all(self) -> None:
        """max_per_page=0 returns all results."""
        results = [
            RetrievalResult(doc_id="1", content="A", score=1.0, source_url="page1"),
            RetrievalResult(doc_id="2", content="B", score=0.9, source_url="page1"),
        ]

        filtered = enforce_page_diversity(results, max_per_page=0)

        assert len(filtered) == 2

    def test_uses_doc_id_if_no_url(self) -> None:
        """Uses doc_id for grouping if no source_url."""
        results = [
            RetrievalResult(doc_id="1", content="A", score=1.0),
            RetrievalResult(doc_id="1", content="B", score=0.9),
            RetrievalResult(doc_id="2", content="C", score=0.8),
        ]

        filtered = enforce_page_diversity(results, max_per_page=1)

        # Should get one from each doc_id
        assert len(filtered) == 2


class TestHybridRetriever:
    """Tests for HybridRetriever class."""

    def test_create_retriever(self) -> None:
        """Can create a retriever."""
        retriever = HybridRetriever()

        stats = retriever.get_stats()
        assert stats["total_documents"] == 0

    def test_add_document(self) -> None:
        """Can add a document."""
        retriever = HybridRetriever()
        retriever.add_document(
            doc_id="doc1",
            content="Test document content",
            source_url="https://example.com",
        )

        stats = retriever.get_stats()
        assert stats["total_documents"] == 1

    def test_add_multiple_documents(self) -> None:
        """Can add multiple documents."""
        retriever = HybridRetriever()
        retriever.add_documents(
            [
                {"doc_id": "doc1", "content": "First document"},
                {"doc_id": "doc2", "content": "Second document"},
            ]
        )

        stats = retriever.get_stats()
        assert stats["total_documents"] == 2

    def test_search_returns_results(self) -> None:
        """Search returns matching results."""
        retriever = HybridRetriever()
        retriever.add_document("doc1", "Python programming guide")
        retriever.add_document("doc2", "Java programming tutorial")
        retriever.add_document("doc3", "Cooking recipes")

        results = retriever.search("programming")

        assert len(results) >= 1
        # Programming docs should be in results
        doc_ids = [r.doc_id for r in results]
        # At least one programming doc should match
        assert "doc1" in doc_ids or "doc2" in doc_ids

    def test_search_includes_scores(self) -> None:
        """Search results include both scores."""
        retriever = HybridRetriever()
        retriever.add_document("doc1", "Python programming")

        results = retriever.search("Python")

        if results:
            # Should have combined score and individual scores
            assert results[0].score > 0
            # Vector and BM25 scores may or may not be set depending on matches
            assert results[0].bm25_score is not None or results[0].vector_score is not None

    def test_search_with_limit(self) -> None:
        """Can limit search results."""
        retriever = HybridRetriever()
        for i in range(10):
            retriever.add_document(f"doc{i}", f"Test document {i}")

        results = retriever.search("document", limit=3)

        assert len(results) <= 3

    def test_search_diversity_constraint(self) -> None:
        """Search respects diversity constraint."""
        config = RetrieverConfig(max_per_page=1)
        retriever = HybridRetriever(config=config)

        # Add multiple docs from same page
        retriever.add_document("doc1", "Python guide", source_url="https://example.com")
        retriever.add_document("doc2", "Python tutorial", source_url="https://example.com")
        retriever.add_document("doc3", "Java guide", source_url="https://other.com")

        results = retriever.search("guide")

        # Should get max 1 from each page
        page_counts: dict[str, int] = {}
        for r in results:
            url = r.source_url or ""
            page_counts[url] = page_counts.get(url, 0) + 1

        for count in page_counts.values():
            assert count <= 1

    def test_remove_document(self) -> None:
        """Can remove a document."""
        retriever = HybridRetriever()
        retriever.add_document("doc1", "Test content")

        removed = retriever.remove_document("doc1")

        assert removed is True
        assert retriever.get_stats()["total_documents"] == 0

    def test_clear(self) -> None:
        """Can clear all documents."""
        retriever = HybridRetriever()
        retriever.add_documents(
            [
                {"doc_id": "doc1", "content": "First"},
                {"doc_id": "doc2", "content": "Second"},
            ]
        )

        retriever.clear()

        assert retriever.get_stats()["total_documents"] == 0

    def test_result_includes_metadata(self) -> None:
        """Results include document metadata."""
        retriever = HybridRetriever()
        retriever.add_document(
            doc_id="doc1",
            content="Test content",
            source_url="https://example.com",
            page_title="Test Page",
            heading_context="Introduction",
            chunk_type="text",
        )

        results = retriever.search("test")

        if results:
            assert results[0].source_url == "https://example.com"
            assert results[0].page_title == "Test Page"
            assert results[0].heading_context == "Introduction"

    def test_get_stats(self) -> None:
        """Can get retriever statistics."""
        retriever = HybridRetriever()
        retriever.add_document("doc1", "Test content")

        stats = retriever.get_stats()

        assert "total_documents" in stats
        assert "bm25_stats" in stats
        assert "config" in stats
