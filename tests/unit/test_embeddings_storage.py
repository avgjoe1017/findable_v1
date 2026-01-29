"""Tests for embedding storage."""

from uuid import uuid4

from worker.embeddings.storage import (
    CREATE_TABLE_SQL,
    EmbeddingStoreConfig,
    SearchResult,
    StoredEmbedding,
)


class TestStoredEmbedding:
    """Tests for StoredEmbedding dataclass."""

    def test_create_stored_embedding(self) -> None:
        """Can create StoredEmbedding."""
        embedding = StoredEmbedding(
            id=uuid4(),
            chunk_id=uuid4(),
            page_id=uuid4(),
            site_id=uuid4(),
            content="Test content",
            content_hash="abc123",
            embedding=[0.1, 0.2, 0.3],
            model_name="mock",
            dimensions=3,
            chunk_index=0,
            chunk_type="text",
            heading_context="Section 1",
            position_ratio=0.25,
        )

        assert embedding.content == "Test content"
        assert embedding.dimensions == 3
        assert embedding.chunk_type == "text"

    def test_to_dict(self) -> None:
        """StoredEmbedding converts to dict."""
        emb_id = uuid4()
        embedding = StoredEmbedding(
            id=emb_id,
            chunk_id=uuid4(),
            page_id=uuid4(),
            site_id=uuid4(),
            content="Test",
            content_hash="abc",
            embedding=[0.1, 0.2],
            model_name="mock",
            dimensions=2,
            chunk_index=0,
            chunk_type="text",
            heading_context=None,
            position_ratio=0.0,
        )

        d = embedding.to_dict()
        assert d["id"] == str(emb_id)
        assert d["content"] == "Test"
        assert d["model_name"] == "mock"
        assert "created_at" in d


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_create_search_result(self) -> None:
        """Can create SearchResult."""
        result = SearchResult(
            embedding_id=uuid4(),
            chunk_id=uuid4(),
            page_id=uuid4(),
            content="Found content",
            score=0.95,
            distance=0.05,
            heading_context="Introduction",
            chunk_type="text",
            source_url="https://example.com",
            page_title="Test Page",
        )

        assert result.content == "Found content"
        assert result.score == 0.95
        assert result.distance == 0.05

    def test_to_dict(self) -> None:
        """SearchResult converts to dict."""
        emb_id = uuid4()
        result = SearchResult(
            embedding_id=emb_id,
            chunk_id=uuid4(),
            page_id=uuid4(),
            content="Content",
            score=0.9,
            distance=0.1,
        )

        d = result.to_dict()
        assert d["embedding_id"] == str(emb_id)
        assert d["score"] == 0.9
        assert d["distance"] == 0.1

    def test_default_values(self) -> None:
        """SearchResult has sensible defaults."""
        result = SearchResult(
            embedding_id=uuid4(),
            chunk_id=uuid4(),
            page_id=uuid4(),
            content="Content",
            score=0.9,
            distance=0.1,
        )

        assert result.heading_context is None
        assert result.chunk_type == "text"
        assert result.source_url is None
        assert result.page_title is None


class TestEmbeddingStoreConfig:
    """Tests for EmbeddingStoreConfig."""

    def test_default_values(self) -> None:
        """Check default configuration."""
        config = EmbeddingStoreConfig()

        assert config.table_name == "embeddings"
        assert config.index_type == "ivfflat"
        assert config.distance_metric == "cosine"
        assert config.lists == 100
        assert config.ef_construction == 64

    def test_custom_values(self) -> None:
        """Can set custom configuration."""
        config = EmbeddingStoreConfig(
            table_name="custom_embeddings",
            index_type="hnsw",
            distance_metric="l2",
        )

        assert config.table_name == "custom_embeddings"
        assert config.index_type == "hnsw"
        assert config.distance_metric == "l2"


class TestCreateTableSQL:
    """Tests for SQL statements."""

    def test_create_table_sql_exists(self) -> None:
        """CREATE_TABLE_SQL is defined."""
        assert CREATE_TABLE_SQL is not None
        assert len(CREATE_TABLE_SQL) > 0

    def test_create_table_sql_has_required_elements(self) -> None:
        """SQL has required table elements."""
        sql = CREATE_TABLE_SQL.lower()

        # Check for pgvector extension
        assert "create extension" in sql
        assert "vector" in sql

        # Check for table creation
        assert "create table" in sql
        assert "embeddings" in sql

        # Check for required columns
        assert "chunk_id" in sql
        assert "page_id" in sql
        assert "site_id" in sql
        assert "content" in sql
        assert "embedding" in sql
        assert "model_name" in sql

        # Check for indexes
        assert "create index" in sql

    def test_create_table_sql_has_vector_index(self) -> None:
        """SQL creates vector index."""
        sql = CREATE_TABLE_SQL.lower()

        assert "ivfflat" in sql or "hnsw" in sql
        assert "vector_cosine_ops" in sql


class TestSimilarityScoring:
    """Tests for similarity score logic."""

    def test_score_range(self) -> None:
        """Scores should be between 0 and 1 for cosine."""
        # Cosine similarity: -1 to 1
        # Cosine distance: 0 to 2
        # Score = 1 - distance: -1 to 1

        # For normalized vectors, cosine distance is 0 to 2
        # Score = 1 - distance ranges from -1 to 1
        # But for similar vectors, score should be close to 1

        result = SearchResult(
            embedding_id=uuid4(),
            chunk_id=uuid4(),
            page_id=uuid4(),
            content="Test",
            score=0.95,  # High similarity
            distance=0.05,  # Low distance
        )

        assert 0 <= result.score <= 1
        assert 0 <= result.distance <= 2

    def test_score_distance_relationship(self) -> None:
        """Score and distance are inversely related."""
        # score = 1 - distance (for cosine)
        result = SearchResult(
            embedding_id=uuid4(),
            chunk_id=uuid4(),
            page_id=uuid4(),
            content="Test",
            score=0.8,
            distance=0.2,
        )

        assert result.score + result.distance == 1.0
