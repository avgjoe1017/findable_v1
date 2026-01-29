"""Embeddings package for vector generation and storage."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.embeddings.embedder import Embedder, EmbedderConfig
# from worker.embeddings.models import EmbeddingModel, get_model

__all__ = [
    # Embedder
    "Embedder",
    "EmbedderConfig",
    "EmbeddingResult",
    # Models
    "EmbeddingModel",
    "get_model",
    "list_models",
    # Storage
    "EmbeddingStore",
    "StoredEmbedding",
]
