"""Tests for BM25 lexical search."""

from worker.retrieval.bm25 import (
    BM25Config,
    BM25Document,
    BM25Index,
    BM25Result,
    tokenize,
)


class TestTokenize:
    """Tests for tokenize function."""

    def test_simple_text(self) -> None:
        """Tokenize simple text."""
        config = BM25Config()
        tokens = tokenize("Hello world", config)

        assert "hello" in tokens
        assert "world" in tokens

    def test_lowercase(self) -> None:
        """Tokens are lowercased by default."""
        config = BM25Config(lowercase=True)
        tokens = tokenize("Hello World", config)

        assert "hello" in tokens
        assert "Hello" not in tokens

    def test_no_lowercase(self) -> None:
        """Can disable lowercasing."""
        config = BM25Config(lowercase=False)
        tokens = tokenize("Hello World", config)

        assert "Hello" in tokens
        assert "hello" not in tokens

    def test_min_token_length(self) -> None:
        """Short tokens are filtered."""
        config = BM25Config(min_token_length=3)
        tokens = tokenize("I am a test", config)

        assert "test" in tokens
        assert "am" not in tokens
        assert "a" not in tokens

    def test_punctuation_removed(self) -> None:
        """Punctuation is removed."""
        config = BM25Config()
        tokens = tokenize("Hello, world! How are you?", config)

        assert "hello" in tokens
        assert "," not in tokens
        assert "!" not in tokens

    def test_empty_string(self) -> None:
        """Empty string returns empty list."""
        config = BM25Config()
        tokens = tokenize("", config)

        assert tokens == []


class TestBM25Config:
    """Tests for BM25Config."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = BM25Config()

        assert config.k1 == 1.5
        assert config.b == 0.75
        assert config.min_token_length == 2
        assert config.lowercase is True

    def test_custom_values(self) -> None:
        """Can set custom values."""
        config = BM25Config(k1=2.0, b=0.5)

        assert config.k1 == 2.0
        assert config.b == 0.5


class TestBM25Document:
    """Tests for BM25Document dataclass."""

    def test_create_document(self) -> None:
        """Can create a document."""
        doc = BM25Document(
            doc_id="doc1",
            content="Test content",
            tokens=["test", "content"],
            token_count=2,
        )

        assert doc.doc_id == "doc1"
        assert doc.token_count == 2


class TestBM25Result:
    """Tests for BM25Result dataclass."""

    def test_create_result(self) -> None:
        """Can create a result."""
        result = BM25Result(
            doc_id="doc1",
            score=1.5,
            content="Test content",
        )

        assert result.doc_id == "doc1"
        assert result.score == 1.5

    def test_to_dict(self) -> None:
        """Result converts to dict."""
        result = BM25Result(
            doc_id="doc1",
            score=1.5,
            content="Test",
        )

        d = result.to_dict()
        assert d["doc_id"] == "doc1"
        assert d["score"] == 1.5


class TestBM25Index:
    """Tests for BM25Index."""

    def test_create_empty_index(self) -> None:
        """Can create empty index."""
        index = BM25Index()

        assert index.document_count == 0

    def test_add_document(self) -> None:
        """Can add a document."""
        index = BM25Index()
        index.add_document("doc1", "This is a test document")

        assert index.document_count == 1

    def test_add_multiple_documents(self) -> None:
        """Can add multiple documents."""
        index = BM25Index()
        index.add_documents(
            [
                {"doc_id": "doc1", "content": "First document"},
                {"doc_id": "doc2", "content": "Second document"},
                {"doc_id": "doc3", "content": "Third document"},
            ]
        )

        assert index.document_count == 3

    def test_search_returns_results(self) -> None:
        """Search returns matching results."""
        index = BM25Index()
        index.add_document("doc1", "Python programming language")
        index.add_document("doc2", "Java programming language")
        index.add_document("doc3", "Cooking recipes and food")

        results = index.search("programming")

        assert len(results) == 2
        # Both docs should match "programming"
        doc_ids = [r.doc_id for r in results]
        assert "doc1" in doc_ids
        assert "doc2" in doc_ids

    def test_search_ranks_by_relevance(self) -> None:
        """More relevant documents rank higher."""
        index = BM25Index()
        index.add_document("doc1", "Python is great")
        index.add_document("doc2", "Python Python Python programming Python")
        index.add_document("doc3", "Java is also good")

        results = index.search("Python")

        # doc2 has more occurrences of "Python"
        assert results[0].doc_id == "doc2"

    def test_search_empty_query(self) -> None:
        """Empty query returns no results."""
        index = BM25Index()
        index.add_document("doc1", "Test document")

        results = index.search("")

        assert len(results) == 0

    def test_search_no_matches(self) -> None:
        """Query with no matches returns empty."""
        index = BM25Index()
        index.add_document("doc1", "Python programming")

        results = index.search("JavaScript")

        assert len(results) == 0

    def test_search_limit(self) -> None:
        """Can limit search results."""
        index = BM25Index()
        for i in range(10):
            index.add_document(f"doc{i}", f"Test document {i} content")

        results = index.search("document", limit=3)

        assert len(results) == 3

    def test_search_min_score(self) -> None:
        """Can filter by minimum score."""
        index = BM25Index()
        index.add_document("doc1", "Python programming language")
        index.add_document("doc2", "Cooking recipes")

        # High min_score should filter out weak matches
        results = index.search("Python", min_score=100.0)

        assert len(results) == 0

    def test_remove_document(self) -> None:
        """Can remove a document."""
        index = BM25Index()
        index.add_document("doc1", "Test document")

        assert index.document_count == 1

        removed = index.remove_document("doc1")

        assert removed is True
        assert index.document_count == 0

    def test_remove_nonexistent_document(self) -> None:
        """Removing nonexistent document returns False."""
        index = BM25Index()

        removed = index.remove_document("nonexistent")

        assert removed is False

    def test_clear_index(self) -> None:
        """Can clear entire index."""
        index = BM25Index()
        index.add_documents(
            [
                {"doc_id": "doc1", "content": "First"},
                {"doc_id": "doc2", "content": "Second"},
            ]
        )

        index.clear()

        assert index.document_count == 0

    def test_get_document(self) -> None:
        """Can retrieve document by ID."""
        index = BM25Index()
        index.add_document("doc1", "Test content", metadata={"key": "value"})

        doc = index.get_document("doc1")

        assert doc is not None
        assert doc.doc_id == "doc1"
        assert doc.metadata["key"] == "value"

    def test_get_nonexistent_document(self) -> None:
        """Getting nonexistent document returns None."""
        index = BM25Index()

        doc = index.get_document("nonexistent")

        assert doc is None

    def test_get_stats(self) -> None:
        """Can get index statistics."""
        index = BM25Index()
        index.add_document("doc1", "Hello world test")
        index.add_document("doc2", "Another test document here")

        stats = index.get_stats()

        assert stats["total_documents"] == 2
        assert stats["total_tokens"] > 0
        assert stats["vocabulary_size"] > 0

    def test_update_document(self) -> None:
        """Adding same doc_id updates the document."""
        index = BM25Index()
        index.add_document("doc1", "Original content")

        results1 = index.search("original")
        assert len(results1) == 1

        index.add_document("doc1", "Updated content")

        results2 = index.search("original")
        assert len(results2) == 0

        results3 = index.search("updated")
        assert len(results3) == 1

    def test_document_with_metadata(self) -> None:
        """Documents preserve metadata."""
        index = BM25Index()
        index.add_document(
            "doc1",
            "Test content",
            metadata={"url": "https://example.com", "title": "Test Page"},
        )

        results = index.search("test")

        assert len(results) == 1
        assert results[0].metadata["url"] == "https://example.com"
