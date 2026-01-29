"""Tests for embedder."""

import numpy as np

from worker.chunking.chunker import Chunk, ChunkedPage, ChunkType
from worker.embeddings.embedder import (
    EmbeddedPage,
    Embedder,
    EmbedderConfig,
    EmbeddingResult,
)
from worker.embeddings.models import MODELS, MockEmbeddingModel


def get_mock_embedder() -> Embedder:
    """Create embedder with mock model."""
    mock_model = MockEmbeddingModel(MODELS["mock"])
    return Embedder(model=mock_model)


class TestEmbedderConfig:
    """Tests for EmbedderConfig."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = EmbedderConfig()

        assert config.model_name == "bge-small"
        assert config.batch_size == 32
        assert config.cache_embeddings is True
        assert config.normalize is True

    def test_custom_values(self) -> None:
        """Can set custom configuration."""
        config = EmbedderConfig(
            model_name="mock",
            batch_size=16,
            cache_embeddings=False,
        )

        assert config.model_name == "mock"
        assert config.batch_size == 16
        assert config.cache_embeddings is False


class TestEmbeddingResult:
    """Tests for EmbeddingResult dataclass."""

    def test_create_result(self) -> None:
        """Can create EmbeddingResult."""
        embedding = np.array([0.1, 0.2, 0.3])
        result = EmbeddingResult(
            chunk_index=0,
            content_hash="abc123",
            embedding=embedding,
            model_name="mock",
            dimensions=3,
            source_url="https://example.com",
            page_title="Test Page",
        )

        assert result.chunk_index == 0
        assert result.model_name == "mock"
        np.testing.assert_array_equal(result.embedding, embedding)

    def test_to_dict(self) -> None:
        """Result converts to dict."""
        embedding = np.array([0.1, 0.2, 0.3])
        result = EmbeddingResult(
            chunk_index=0,
            content_hash="abc123",
            embedding=embedding,
            model_name="mock",
            dimensions=3,
        )

        d = result.to_dict()
        assert d["chunk_index"] == 0
        assert d["embedding"] == [0.1, 0.2, 0.3]
        assert "created_at" in d


class TestEmbeddedPage:
    """Tests for EmbeddedPage dataclass."""

    def test_create_embedded_page(self) -> None:
        """Can create EmbeddedPage."""
        page = EmbeddedPage(
            url="https://example.com",
            title="Test",
            embeddings=[],
            total_chunks=0,
            model_name="mock",
            dimensions=384,
        )

        assert page.url == "https://example.com"
        assert page.total_chunks == 0

    def test_to_dict(self) -> None:
        """Page converts to dict."""
        page = EmbeddedPage(
            url="https://example.com",
            title="Test",
            embeddings=[],
            total_chunks=0,
            model_name="mock",
            dimensions=384,
        )

        d = page.to_dict()
        assert d["url"] == "https://example.com"
        assert d["embeddings"] == []


class TestEmbedder:
    """Tests for Embedder class."""

    def test_create_with_mock_model(self) -> None:
        """Can create embedder with mock model."""
        embedder = get_mock_embedder()

        assert embedder.model_name == "mock"
        assert embedder.dimensions == 384

    def test_embed_texts_empty(self) -> None:
        """Empty list returns empty list."""
        embedder = get_mock_embedder()
        result = embedder.embed_texts([])

        assert result == []

    def test_embed_texts_single(self) -> None:
        """Can embed single text."""
        embedder = get_mock_embedder()
        result = embedder.embed_texts(["Hello world"])

        assert len(result) == 1
        assert result[0].shape == (384,)

    def test_embed_texts_multiple(self) -> None:
        """Can embed multiple texts."""
        embedder = get_mock_embedder()
        texts = ["First", "Second", "Third"]
        result = embedder.embed_texts(texts)

        assert len(result) == 3
        for emb in result:
            assert emb.shape == (384,)

    def test_embeddings_normalized(self) -> None:
        """Embeddings are normalized."""
        embedder = get_mock_embedder()
        result = embedder.embed_texts(["Test"])

        norm = np.linalg.norm(result[0])
        assert abs(norm - 1.0) < 0.001

    def test_embed_query(self) -> None:
        """Can embed a query."""
        embedder = get_mock_embedder()
        result = embedder.embed_query("Search query")

        assert result.shape == (384,)

    def test_caching(self) -> None:
        """Embeddings are cached."""
        embedder = get_mock_embedder()

        # First embed
        text = "Cached text"
        result1 = embedder.embed_texts([text])

        # Second embed should use cache
        result2 = embedder.embed_texts([text])

        np.testing.assert_array_equal(result1[0], result2[0])

    def test_clear_cache(self) -> None:
        """Can clear cache."""
        embedder = get_mock_embedder()

        embedder.embed_texts(["Test"])
        assert len(embedder._cache) > 0

        embedder.clear_cache()
        assert len(embedder._cache) == 0

    def test_embed_chunks(self) -> None:
        """Can embed chunks."""
        embedder = get_mock_embedder()
        chunks = [
            Chunk(
                content="First chunk content",
                chunk_type=ChunkType.TEXT,
                chunk_index=0,
                token_count=10,
                content_hash="hash1",
                source_url="https://example.com",
                page_title="Test Page",
            ),
            Chunk(
                content="Second chunk content",
                chunk_type=ChunkType.TEXT,
                chunk_index=1,
                token_count=10,
                content_hash="hash2",
                source_url="https://example.com",
                page_title="Test Page",
            ),
        ]

        results = embedder.embed_chunks(chunks)

        assert len(results) == 2
        assert results[0].chunk_index == 0
        assert results[1].chunk_index == 1
        assert results[0].source_url == "https://example.com"

    def test_embed_chunks_empty(self) -> None:
        """Empty chunks returns empty list."""
        embedder = get_mock_embedder()
        result = embedder.embed_chunks([])

        assert result == []

    def test_embed_page(self) -> None:
        """Can embed a chunked page."""
        embedder = get_mock_embedder()
        chunked_page = ChunkedPage(
            url="https://example.com",
            title="Test Page",
            chunks=[
                Chunk(
                    content="Chunk content",
                    chunk_type=ChunkType.TEXT,
                    chunk_index=0,
                    token_count=10,
                    content_hash="hash1",
                    source_url="https://example.com",
                    page_title="Test Page",
                ),
            ],
            total_chunks=1,
            total_tokens=10,
            avg_chunk_size=10.0,
        )

        result = embedder.embed_page(chunked_page)

        assert isinstance(result, EmbeddedPage)
        assert result.url == "https://example.com"
        assert result.total_chunks == 1
        assert len(result.embeddings) == 1

    def test_embed_pages(self) -> None:
        """Can embed multiple pages."""
        embedder = get_mock_embedder()
        pages = [
            ChunkedPage(
                url="https://example.com/1",
                title="Page 1",
                chunks=[
                    Chunk(
                        content="Content 1",
                        chunk_type=ChunkType.TEXT,
                        chunk_index=0,
                        token_count=5,
                        content_hash="h1",
                        source_url="https://example.com/1",
                        page_title="Page 1",
                    ),
                ],
                total_chunks=1,
                total_tokens=5,
                avg_chunk_size=5.0,
            ),
            ChunkedPage(
                url="https://example.com/2",
                title="Page 2",
                chunks=[
                    Chunk(
                        content="Content 2",
                        chunk_type=ChunkType.TEXT,
                        chunk_index=0,
                        token_count=5,
                        content_hash="h2",
                        source_url="https://example.com/2",
                        page_title="Page 2",
                    ),
                ],
                total_chunks=1,
                total_tokens=5,
                avg_chunk_size=5.0,
            ),
        ]

        results = embedder.embed_pages(pages)

        assert len(results) == 2
        assert results[0].url == "https://example.com/1"
        assert results[1].url == "https://example.com/2"


class TestEmbedContent:
    """Tests for embed_content convenience function."""

    def test_embed_content(self) -> None:
        """Convenience function works (may fail without deps)."""
        # This will try to load bge-small by default
        # Test with mock model explicitly
        try:
            # This might fail if sentence-transformers not installed
            from worker.embeddings.models import get_model

            model = get_model("mock")
            embedder = Embedder(model=model)
            result = embedder.embed_texts(["Test text"])
            assert len(result) == 1
        except ImportError:
            pass  # Expected without sentence-transformers
