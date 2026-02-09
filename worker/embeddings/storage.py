"""pgvector storage for embeddings."""

from dataclasses import dataclass, field
from datetime import datetime

# Type hints for SQLAlchemy without requiring import
from typing import TYPE_CHECKING, Any
from uuid import UUID

import numpy as np

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class StoredEmbedding:
    """An embedding stored in the database."""

    id: UUID
    chunk_id: UUID
    page_id: UUID
    site_id: UUID

    content: str
    content_hash: str
    embedding: list[float]

    model_name: str
    dimensions: int

    # Metadata
    chunk_index: int
    chunk_type: str
    heading_context: str | None
    position_ratio: float

    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "id": str(self.id),
            "chunk_id": str(self.chunk_id),
            "page_id": str(self.page_id),
            "site_id": str(self.site_id),
            "content": self.content,
            "content_hash": self.content_hash,
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "chunk_index": self.chunk_index,
            "chunk_type": self.chunk_type,
            "heading_context": self.heading_context,
            "position_ratio": self.position_ratio,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SearchResult:
    """Result from similarity search."""

    embedding_id: UUID
    chunk_id: UUID
    page_id: UUID
    content: str
    score: float  # Similarity score (higher = more similar)
    distance: float  # Vector distance (lower = more similar)

    # Context
    heading_context: str | None = None
    chunk_type: str = "text"
    source_url: str | None = None
    page_title: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "embedding_id": str(self.embedding_id),
            "chunk_id": str(self.chunk_id),
            "page_id": str(self.page_id),
            "content": self.content,
            "score": self.score,
            "distance": self.distance,
            "heading_context": self.heading_context,
            "chunk_type": self.chunk_type,
            "source_url": self.source_url,
            "page_title": self.page_title,
        }


@dataclass
class EmbeddingStoreConfig:
    """Configuration for embedding storage."""

    table_name: str = "embeddings"
    index_type: str = "ivfflat"  # ivfflat or hnsw
    distance_metric: str = "cosine"  # cosine, l2, or inner_product
    lists: int = 100  # For ivfflat: number of lists
    ef_construction: int = 64  # For hnsw: construction parameter


class EmbeddingStore:
    """
    Store and search embeddings using pgvector.

    This class provides methods for:
    - Storing embeddings with metadata
    - Similarity search (vector)
    - Hybrid search (vector + keyword)
    - Batch operations
    """

    def __init__(self, config: EmbeddingStoreConfig | None = None):
        self.config = config or EmbeddingStoreConfig()

    async def store_embedding(
        self,
        session: "AsyncSession",
        chunk_id: UUID,
        page_id: UUID,
        site_id: UUID,
        content: str,
        content_hash: str,
        embedding: np.ndarray | list[float],
        model_name: str,
        chunk_index: int = 0,
        chunk_type: str = "text",
        heading_context: str | None = None,
        position_ratio: float = 0.0,
        source_url: str | None = None,
        page_title: str | None = None,
    ) -> UUID:
        """
        Store a single embedding.

        Args:
            session: Database session
            chunk_id: ID of the chunk
            page_id: ID of the source page
            site_id: ID of the site
            content: Original text content
            content_hash: Hash of content for deduplication
            embedding: Vector embedding
            model_name: Name of embedding model
            chunk_index: Index of chunk in page
            chunk_type: Type of chunk (text, list, etc.)
            heading_context: Nearest heading
            position_ratio: Position in document (0-1)

        Returns:
            ID of stored embedding
        """
        from uuid import uuid4

        from sqlalchemy import text

        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else embedding
        embedding_id = uuid4()

        query = text(
            f"""
            INSERT INTO {self.config.table_name} (
                id, chunk_id, page_id, site_id,
                content, content_hash, embedding,
                model_name, dimensions,
                chunk_index, chunk_type, heading_context, position_ratio,
                source_url, page_title,
                created_at
            ) VALUES (
                :id, :chunk_id, :page_id, :site_id,
                :content, :content_hash, :embedding,
                :model_name, :dimensions,
                :chunk_index, :chunk_type, :heading_context, :position_ratio,
                :source_url, :page_title,
                NOW()
            )
            ON CONFLICT (content_hash, site_id) DO UPDATE SET
                embedding = EXCLUDED.embedding,
                model_name = EXCLUDED.model_name,
                updated_at = NOW()
            RETURNING id
        """
        )

        result = await session.execute(
            query,
            {
                "id": embedding_id,
                "chunk_id": chunk_id,
                "page_id": page_id,
                "site_id": site_id,
                "content": content,
                "content_hash": content_hash,
                "embedding": str(embedding_list),
                "model_name": model_name,
                "dimensions": len(embedding_list),
                "chunk_index": chunk_index,
                "chunk_type": chunk_type,
                "heading_context": heading_context,
                "position_ratio": position_ratio,
                "source_url": source_url,
                "page_title": page_title,
            },
        )

        row = result.fetchone()
        return row[0] if row else embedding_id

    async def store_embeddings_batch(
        self,
        session: "AsyncSession",
        embeddings: list[dict[str, Any]],
    ) -> list[UUID]:
        """
        Store multiple embeddings in batch.

        Args:
            session: Database session
            embeddings: List of embedding dicts with required fields

        Returns:
            List of stored embedding IDs
        """
        ids: list[UUID] = []

        for emb in embeddings:
            emb_id = await self.store_embedding(
                session=session,
                chunk_id=emb["chunk_id"],
                page_id=emb["page_id"],
                site_id=emb["site_id"],
                content=emb["content"],
                content_hash=emb["content_hash"],
                embedding=emb["embedding"],
                model_name=emb["model_name"],
                chunk_index=emb.get("chunk_index", 0),
                chunk_type=emb.get("chunk_type", "text"),
                heading_context=emb.get("heading_context"),
                position_ratio=emb.get("position_ratio", 0.0),
            )
            ids.append(emb_id)

        return ids

    async def search_similar(
        self,
        session: "AsyncSession",
        query_embedding: np.ndarray | list[float],
        site_id: UUID,
        limit: int = 10,
        min_score: float = 0.0,
    ) -> list[SearchResult]:
        """
        Search for similar embeddings using vector similarity.

        Args:
            session: Database session
            query_embedding: Query vector
            site_id: Site to search within
            limit: Maximum results to return
            min_score: Minimum similarity score (0-1)

        Returns:
            List of SearchResult objects
        """
        from sqlalchemy import text

        embedding_list = (
            query_embedding.tolist() if isinstance(query_embedding, np.ndarray) else query_embedding
        )

        # Use cosine distance (1 - cosine similarity)
        # pgvector: <=> is cosine distance, <-> is L2, <#> is inner product
        distance_op = "<=>" if self.config.distance_metric == "cosine" else "<->"

        query = text(
            f"""
            SELECT
                e.id,
                e.chunk_id,
                e.page_id,
                e.content,
                1 - (e.embedding {distance_op} :query_embedding) as score,
                e.embedding {distance_op} :query_embedding as distance,
                e.heading_context,
                e.chunk_type
            FROM {self.config.table_name} e
            WHERE e.site_id = :site_id
            ORDER BY e.embedding {distance_op} :query_embedding
            LIMIT :limit
        """
        )

        result = await session.execute(
            query,
            {
                "query_embedding": str(embedding_list),
                "site_id": site_id,
                "limit": limit,
            },
        )

        results: list[SearchResult] = []
        for row in result.fetchall():
            score = float(row[4])
            if score >= min_score:
                results.append(
                    SearchResult(
                        embedding_id=row[0],
                        chunk_id=row[1],
                        page_id=row[2],
                        content=row[3],
                        score=score,
                        distance=float(row[5]),
                        heading_context=row[6],
                        chunk_type=row[7],
                    )
                )

        return results

    async def delete_site_embeddings(
        self,
        session: "AsyncSession",
        site_id: UUID,
    ) -> int:
        """
        Delete all embeddings for a site.

        Args:
            session: Database session
            site_id: Site ID

        Returns:
            Number of deleted embeddings
        """
        from sqlalchemy import text

        query = text(
            f"""
            DELETE FROM {self.config.table_name}
            WHERE site_id = :site_id
        """
        )

        result = await session.execute(query, {"site_id": site_id})
        if result.rowcount is not None:  # type: ignore[attr-defined]
            return int(result.rowcount)  # type: ignore[attr-defined]
        return 0

    async def delete_page_embeddings(
        self,
        session: "AsyncSession",
        page_id: UUID,
    ) -> int:
        """
        Delete all embeddings for a page.

        Args:
            session: Database session
            page_id: Page ID

        Returns:
            Number of deleted embeddings
        """
        from sqlalchemy import text

        query = text(
            f"""
            DELETE FROM {self.config.table_name}
            WHERE page_id = :page_id
        """
        )

        result = await session.execute(query, {"page_id": page_id})
        if result.rowcount is not None:  # type: ignore[attr-defined]
            return int(result.rowcount)  # type: ignore[attr-defined]
        return 0

    async def get_embedding_count(
        self,
        session: "AsyncSession",
        site_id: UUID,
    ) -> int:
        """
        Get count of embeddings for a site.

        Args:
            session: Database session
            site_id: Site ID

        Returns:
            Count of embeddings
        """
        from sqlalchemy import text

        query = text(
            f"""
            SELECT COUNT(*) FROM {self.config.table_name}
            WHERE site_id = :site_id
        """
        )

        result = await session.execute(query, {"site_id": site_id})
        row = result.fetchone()
        return row[0] if row else 0


# SQL for creating the embeddings table with pgvector
CREATE_TABLE_SQL = """
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create embeddings table
CREATE TABLE IF NOT EXISTS embeddings (
    id UUID PRIMARY KEY,
    chunk_id UUID NOT NULL,
    page_id UUID NOT NULL,
    site_id UUID NOT NULL,

    content TEXT NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    embedding vector(384),  -- Adjust dimensions as needed

    model_name VARCHAR(100) NOT NULL,
    dimensions INTEGER NOT NULL,

    chunk_index INTEGER DEFAULT 0,
    chunk_type VARCHAR(50) DEFAULT 'text',
    heading_context TEXT,
    position_ratio FLOAT DEFAULT 0.0,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,

    -- Unique constraint for deduplication
    CONSTRAINT unique_chunk_site UNIQUE (content_hash, site_id)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_embeddings_site_id ON embeddings(site_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_page_id ON embeddings(page_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_content_hash ON embeddings(content_hash);

-- Create vector index for similarity search (IVFFlat)
CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
"""

# Alternative HNSW index (better recall, more memory)
CREATE_HNSW_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_embeddings_vector_hnsw ON embeddings
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
"""
