"""Hybrid retriever combining vector and lexical search."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

from worker.embeddings.embedder import Embedder, EmbedderConfig
from worker.embeddings.models import MODELS, MockEmbeddingModel
from worker.retrieval.bm25 import BM25Config, BM25Index

if TYPE_CHECKING:
    pass


@dataclass
class RRFConfig:
    """Configuration for Reciprocal Rank Fusion."""

    k: int = 60  # Ranking constant (default from original paper)
    vector_weight: float = 0.5  # Weight for vector search (0-1)
    bm25_weight: float = 0.5  # Weight for BM25 search (0-1)


@dataclass
class RetrievalResult:
    """Result from hybrid retrieval."""

    doc_id: str
    content: str
    score: float  # Combined score
    vector_score: float | None = None  # Score from vector search
    bm25_score: float | None = None  # Score from BM25 search
    vector_rank: int | None = None  # Rank in vector results
    bm25_rank: int | None = None  # Rank in BM25 results

    # Metadata
    source_url: str | None = None
    page_title: str | None = None
    heading_context: str | None = None
    chunk_type: str = "text"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "score": self.score,
            "vector_score": self.vector_score,
            "bm25_score": self.bm25_score,
            "vector_rank": self.vector_rank,
            "bm25_rank": self.bm25_rank,
            "source_url": self.source_url,
            "page_title": self.page_title,
            "heading_context": self.heading_context,
            "chunk_type": self.chunk_type,
            "metadata": self.metadata,
        }


@dataclass
class RetrieverConfig:
    """Configuration for hybrid retriever."""

    # Vector search
    embedding_model: str = "bge-small"
    vector_search_limit: int = 20  # Initial vector results to fetch

    # BM25 search
    bm25_config: BM25Config = field(default_factory=BM25Config)
    bm25_search_limit: int = 20  # Initial BM25 results to fetch

    # Fusion
    rrf_config: RRFConfig = field(default_factory=RRFConfig)

    # Output
    final_limit: int = 10  # Final results to return
    max_per_page: int = 2  # Max chunks from same page (diversity)
    min_score: float = 0.0  # Minimum combined score


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[str, float]]],
    weights: list[float] | None = None,
    k: int = 60,
) -> list[tuple[str, float]]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion (RRF).

    RRF score for document d: sum(weight_i / (k + rank_i(d)))

    Args:
        ranked_lists: List of (doc_id, score) tuples for each ranker
        weights: Optional weights for each ranker (default: equal)
        k: Ranking constant (default 60)

    Returns:
        Fused ranked list of (doc_id, score)
    """
    if not ranked_lists:
        return []

    if weights is None:
        weights = [1.0] * len(ranked_lists)

    # Normalize weights
    total_weight = sum(weights)
    weights = [w / total_weight for w in weights]

    # Calculate RRF scores
    scores: dict[str, float] = {}

    for i, ranked_list in enumerate(ranked_lists):
        for rank, (doc_id, _original_score) in enumerate(ranked_list, start=1):
            rrf_score = weights[i] / (k + rank)

            if doc_id not in scores:
                scores[doc_id] = 0.0
            scores[doc_id] += rrf_score

    # Sort by combined score
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return fused


def enforce_page_diversity(
    results: list[RetrievalResult],
    max_per_page: int = 2,
) -> list[RetrievalResult]:
    """
    Enforce diversity constraint: max N chunks per page.

    Args:
        results: Ranked results
        max_per_page: Maximum results from same page

    Returns:
        Filtered results
    """
    if max_per_page <= 0:
        return results

    page_counts: dict[str, int] = {}
    filtered: list[RetrievalResult] = []

    for result in results:
        page_key = result.source_url or result.doc_id

        if page_key not in page_counts:
            page_counts[page_key] = 0

        if page_counts[page_key] < max_per_page:
            filtered.append(result)
            page_counts[page_key] += 1

    return filtered


class HybridRetriever:
    """
    Hybrid retriever combining vector similarity and BM25 lexical search.

    Uses Reciprocal Rank Fusion (RRF) to combine results from both
    ranking methods.
    """

    def __init__(
        self,
        config: RetrieverConfig | None = None,
        embedder: Embedder | None = None,
        bm25_index: BM25Index | None = None,
    ):
        self.config = config or RetrieverConfig()

        # Initialize embedder
        if embedder:
            self._embedder = embedder
        else:
            # Use mock model by default for testing
            mock_model = MockEmbeddingModel(MODELS["mock"])
            self._embedder = Embedder(
                config=EmbedderConfig(model_name="mock"),
                model=mock_model,
            )

        # Initialize BM25 index
        self._bm25 = bm25_index or BM25Index(self.config.bm25_config)

        # In-memory document store for hybrid search
        self._documents: dict[str, dict] = {}

    def add_document(
        self,
        doc_id: str,
        content: str,
        embedding: np.ndarray | None = None,
        source_url: str | None = None,
        page_title: str | None = None,
        heading_context: str | None = None,
        chunk_type: str = "text",
        metadata: dict | None = None,
    ) -> None:
        """
        Add a document to both indexes.

        Args:
            doc_id: Unique document identifier
            content: Document text
            embedding: Pre-computed embedding (optional)
            source_url: Source URL
            page_title: Page title
            heading_context: Heading context
            chunk_type: Type of chunk
            metadata: Additional metadata
        """
        # Generate embedding if not provided
        if embedding is None:
            embeddings = self._embedder.embed_texts([content])
            embedding = embeddings[0] if embeddings else None

        # Store document
        self._documents[doc_id] = {
            "content": content,
            "embedding": embedding,
            "source_url": source_url,
            "page_title": page_title,
            "heading_context": heading_context,
            "chunk_type": chunk_type,
            "metadata": metadata or {},
        }

        # Add to BM25 index
        self._bm25.add_document(
            doc_id=doc_id,
            content=content,
            metadata={
                "source_url": source_url,
                "page_title": page_title,
                "heading_context": heading_context,
                "chunk_type": chunk_type,
                **(metadata or {}),
            },
        )

    def add_documents(self, documents: list[dict]) -> None:
        """
        Add multiple documents.

        Args:
            documents: List of document dicts
        """
        for doc in documents:
            self.add_document(**doc)

    def search(
        self,
        query: str,
        limit: int | None = None,
    ) -> list[RetrievalResult]:
        """
        Perform hybrid search.

        Args:
            query: Search query
            limit: Maximum results (default from config)

        Returns:
            List of RetrievalResult objects
        """
        limit = limit or self.config.final_limit

        # Vector search
        vector_results = self._vector_search(query)

        # BM25 search
        bm25_results = self._bm25.search(
            query=query,
            limit=self.config.bm25_search_limit,
        )

        # Convert to ranked lists for RRF
        vector_ranked = [(r[0], r[1]) for r in vector_results]
        bm25_ranked = [(r.doc_id, r.score) for r in bm25_results]

        # Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion(
            ranked_lists=[vector_ranked, bm25_ranked],
            weights=[
                self.config.rrf_config.vector_weight,
                self.config.rrf_config.bm25_weight,
            ],
            k=self.config.rrf_config.k,
        )

        # Build result objects with detailed scores
        vector_ranks = {doc_id: i + 1 for i, (doc_id, _) in enumerate(vector_ranked)}
        bm25_ranks = {doc_id: i + 1 for i, (doc_id, _) in enumerate(bm25_ranked)}
        vector_scores = dict(vector_ranked)
        bm25_scores = {r.doc_id: r.score for r in bm25_results}

        results: list[RetrievalResult] = []
        for doc_id, combined_score in fused:
            doc = self._documents.get(doc_id)
            if not doc:
                continue

            result = RetrievalResult(
                doc_id=doc_id,
                content=doc["content"],
                score=combined_score,
                vector_score=vector_scores.get(doc_id),
                bm25_score=bm25_scores.get(doc_id),
                vector_rank=vector_ranks.get(doc_id),
                bm25_rank=bm25_ranks.get(doc_id),
                source_url=doc.get("source_url"),
                page_title=doc.get("page_title"),
                heading_context=doc.get("heading_context"),
                chunk_type=doc.get("chunk_type", "text"),
                metadata=doc.get("metadata", {}),
            )
            results.append(result)

        # Apply diversity constraint
        if self.config.max_per_page > 0:
            results = enforce_page_diversity(results, self.config.max_per_page)

        # Apply minimum score filter
        if self.config.min_score > 0:
            results = [r for r in results if r.score >= self.config.min_score]

        return results[:limit]

    def _vector_search(self, query: str) -> list[tuple[str, float]]:
        """
        Perform vector similarity search.

        Returns list of (doc_id, score) tuples.
        """
        # Get query embedding
        query_embedding = self._embedder.embed_query(query)

        # Calculate cosine similarity with all documents
        results: list[tuple[str, float]] = []

        for doc_id, doc in self._documents.items():
            embedding = doc.get("embedding")
            if embedding is None:
                continue

            # Cosine similarity
            similarity = float(np.dot(query_embedding, embedding))
            results.append((doc_id, similarity))

        # Sort by similarity (descending)
        results.sort(key=lambda x: x[1], reverse=True)

        return results[: self.config.vector_search_limit]

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document from both indexes."""
        if doc_id not in self._documents:
            return False

        del self._documents[doc_id]
        self._bm25.remove_document(doc_id)
        return True

    def clear(self) -> None:
        """Clear all documents."""
        self._documents.clear()
        self._bm25.clear()

    def get_stats(self) -> dict:
        """Get retriever statistics."""
        return {
            "total_documents": len(self._documents),
            "bm25_stats": self._bm25.get_stats(),
            "config": {
                "vector_weight": self.config.rrf_config.vector_weight,
                "bm25_weight": self.config.rrf_config.bm25_weight,
                "rrf_k": self.config.rrf_config.k,
                "max_per_page": self.config.max_per_page,
            },
        }
