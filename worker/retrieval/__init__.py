"""Retrieval package for hybrid search."""

# Lazy imports to avoid requiring all dependencies at import time
# Use explicit imports when needed:
# from worker.retrieval.retriever import HybridRetriever, RetrieverConfig
# from worker.retrieval.bm25 import BM25Index

__all__ = [
    # Retriever
    "HybridRetriever",
    "RetrieverConfig",
    "RetrievalResult",
    # BM25
    "BM25Index",
    "BM25Config",
    # Fusion
    "reciprocal_rank_fusion",
    "RRFConfig",
]
