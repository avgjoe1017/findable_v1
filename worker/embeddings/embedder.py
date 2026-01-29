"""Embedder for generating chunk embeddings."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np

from worker.chunking.chunker import Chunk, ChunkedPage
from worker.embeddings.models import (
    DEFAULT_MODEL,
    EmbeddingModelProtocol,
    get_model,
)


@dataclass
class EmbeddingResult:
    """Result of embedding a chunk."""

    chunk_index: int
    content_hash: str
    embedding: np.ndarray
    model_name: str
    dimensions: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    # Source info
    source_url: str | None = None
    page_title: str | None = None
    heading_context: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary (embedding as list)."""
        return {
            "chunk_index": self.chunk_index,
            "content_hash": self.content_hash,
            "embedding": self.embedding.tolist(),
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "created_at": self.created_at.isoformat(),
            "source_url": self.source_url,
            "page_title": self.page_title,
            "heading_context": self.heading_context,
        }


@dataclass
class EmbeddedPage:
    """A page with all chunks embedded."""

    url: str
    title: str | None
    embeddings: list[EmbeddingResult]
    total_chunks: int
    model_name: str
    dimensions: int
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "url": self.url,
            "title": self.title,
            "total_chunks": self.total_chunks,
            "model_name": self.model_name,
            "dimensions": self.dimensions,
            "created_at": self.created_at.isoformat(),
            "embeddings": [e.to_dict() for e in self.embeddings],
        }


@dataclass
class EmbedderConfig:
    """Configuration for embedder."""

    model_name: str = DEFAULT_MODEL
    batch_size: int = 32  # Process this many chunks at once
    cache_embeddings: bool = True  # Cache by content hash
    normalize: bool = True  # Normalize embeddings


class Embedder:
    """Generates embeddings for chunks."""

    def __init__(
        self,
        config: EmbedderConfig | None = None,
        model: EmbeddingModelProtocol | None = None,
    ):
        self.config = config or EmbedderConfig()
        self._model = model or get_model(self.config.model_name)
        self._cache: dict[str, np.ndarray] = {}

    @property
    def model_name(self) -> str:
        """Get model name."""
        return self._model.model_info.name

    @property
    def dimensions(self) -> int:
        """Get embedding dimensions."""
        return self._model.dimensions

    def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        """
        Embed a list of texts.

        Args:
            texts: List of text strings

        Returns:
            List of embedding arrays
        """
        if not texts:
            return []

        # Check cache for already embedded texts
        results: list[np.ndarray | None] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str]] = []

        if self.config.cache_embeddings:
            for i, text in enumerate(texts):
                cache_key = self._cache_key(text)
                if cache_key in self._cache:
                    results[i] = self._cache[cache_key]
                else:
                    texts_to_embed.append((i, text))
        else:
            texts_to_embed = list(enumerate(texts))

        # Embed uncached texts in batches
        if texts_to_embed:
            for batch_start in range(0, len(texts_to_embed), self.config.batch_size):
                batch = texts_to_embed[batch_start : batch_start + self.config.batch_size]
                batch_texts = [t for _, t in batch]
                batch_embeddings = self._model.embed(batch_texts)

                for j, (original_idx, text) in enumerate(batch):
                    embedding = batch_embeddings[j]

                    if self.config.normalize:
                        norm = np.linalg.norm(embedding)
                        if norm > 0:
                            embedding = embedding / norm

                    results[original_idx] = embedding

                    if self.config.cache_embeddings:
                        cache_key = self._cache_key(text)
                        self._cache[cache_key] = embedding

        return [r for r in results if r is not None]

    def embed_query(self, query: str) -> np.ndarray:
        """
        Embed a query for similarity search.

        Args:
            query: Query text

        Returns:
            Query embedding
        """
        embedding = self._model.embed_query(query)

        if self.config.normalize:
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = embedding / norm

        return embedding

    def embed_chunks(self, chunks: list[Chunk]) -> list[EmbeddingResult]:
        """
        Embed a list of chunks.

        Args:
            chunks: List of Chunk objects

        Returns:
            List of EmbeddingResult objects
        """
        if not chunks:
            return []

        texts = [chunk.content for chunk in chunks]
        embeddings = self.embed_texts(texts)

        results: list[EmbeddingResult] = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            result = EmbeddingResult(
                chunk_index=chunk.chunk_index,
                content_hash=chunk.content_hash,
                embedding=embedding,
                model_name=self.model_name,
                dimensions=self.dimensions,
                source_url=chunk.source_url,
                page_title=chunk.page_title,
                heading_context=chunk.heading_context,
            )
            results.append(result)

        return results

    def embed_page(self, chunked_page: ChunkedPage) -> EmbeddedPage:
        """
        Embed all chunks from a chunked page.

        Args:
            chunked_page: ChunkedPage with chunks

        Returns:
            EmbeddedPage with embeddings
        """
        embeddings = self.embed_chunks(chunked_page.chunks)

        return EmbeddedPage(
            url=chunked_page.url,
            title=chunked_page.title,
            embeddings=embeddings,
            total_chunks=len(embeddings),
            model_name=self.model_name,
            dimensions=self.dimensions,
        )

    def embed_pages(self, chunked_pages: list[ChunkedPage]) -> list[EmbeddedPage]:
        """
        Embed all chunks from multiple pages.

        Args:
            chunked_pages: List of ChunkedPage objects

        Returns:
            List of EmbeddedPage objects
        """
        return [self.embed_page(page) for page in chunked_pages]

    def clear_cache(self) -> None:
        """Clear the embedding cache."""
        self._cache.clear()

    def _cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        # Include model name in key so different models don't collide
        content = f"{self.model_name}:{text}"
        return hashlib.md5(content.encode()).hexdigest()


def embed_content(
    texts: list[str],
    model_name: str | None = None,
) -> list[np.ndarray]:
    """
    Convenience function to embed texts.

    Args:
        texts: List of texts to embed
        model_name: Model name (optional)

    Returns:
        List of embeddings
    """
    config = EmbedderConfig(model_name=model_name or DEFAULT_MODEL)
    embedder = Embedder(config)
    return embedder.embed_texts(texts)
