"""Embedding model definitions and loading."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

import numpy as np

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class ModelType(StrEnum):
    """Type of embedding model."""

    SENTENCE_TRANSFORMER = "sentence_transformer"
    OPENAI = "openai"
    MOCK = "mock"  # For testing


@dataclass
class ModelInfo:
    """Information about an embedding model."""

    name: str
    model_id: str
    model_type: ModelType
    dimensions: int
    max_tokens: int
    description: str


# Available models registry
MODELS: dict[str, ModelInfo] = {
    "bge-small": ModelInfo(
        name="bge-small",
        model_id="BAAI/bge-small-en-v1.5",
        model_type=ModelType.SENTENCE_TRANSFORMER,
        dimensions=384,
        max_tokens=512,
        description="Fast, small model with good quality",
    ),
    "bge-base": ModelInfo(
        name="bge-base",
        model_id="BAAI/bge-base-en-v1.5",
        model_type=ModelType.SENTENCE_TRANSFORMER,
        dimensions=768,
        max_tokens=512,
        description="Better quality, larger model",
    ),
    "minilm": ModelInfo(
        name="minilm",
        model_id="sentence-transformers/all-MiniLM-L6-v2",
        model_type=ModelType.SENTENCE_TRANSFORMER,
        dimensions=384,
        max_tokens=256,
        description="Very fast, good for prototyping",
    ),
    "e5-small": ModelInfo(
        name="e5-small",
        model_id="intfloat/e5-small-v2",
        model_type=ModelType.SENTENCE_TRANSFORMER,
        dimensions=384,
        max_tokens=512,
        description="Microsoft E5, excellent retrieval",
    ),
    "mock": ModelInfo(
        name="mock",
        model_id="mock",
        model_type=ModelType.MOCK,
        dimensions=384,
        max_tokens=512,
        description="Mock model for testing",
    ),
}

# Default model
DEFAULT_MODEL = "bge-small"


class EmbeddingModelProtocol(Protocol):
    """Protocol for embedding models."""

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        ...

    @property
    def model_info(self) -> ModelInfo:
        """Return model info."""
        ...

    def embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        ...

    def embed_query(self, query: str) -> np.ndarray:
        """Generate embedding for a query (may add special prefix)."""
        ...


class SentenceTransformerModel:
    """Wrapper for sentence-transformers models."""

    def __init__(self, model_info: ModelInfo):
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        self._model_info = model_info
        self._model = SentenceTransformer(model_info.model_id)

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._model_info.dimensions

    @property
    def model_info(self) -> ModelInfo:
        """Return model info."""
        return self._model_info

    def embed(self, texts: list[str]) -> np.ndarray:
        """Generate embeddings for texts."""
        if not texts:
            return np.array([])

        # BGE and E5 models need special prefixes for documents
        if "bge" in self._model_info.model_id.lower():
            # BGE doesn't need prefix for documents, only queries
            pass
        elif "e5" in self._model_info.model_id.lower():
            # E5 uses "passage: " prefix for documents
            texts = [f"passage: {t}" for t in texts]

        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return np.array(embeddings)

    def embed_query(self, query: str) -> np.ndarray:
        """Generate embedding for a query."""
        # BGE and E5 models need special prefixes for queries
        if "bge" in self._model_info.model_id.lower():
            query = f"Represent this sentence for searching relevant passages: {query}"
        elif "e5" in self._model_info.model_id.lower():
            query = f"query: {query}"

        embedding = self._model.encode(
            [query],
            normalize_embeddings=True,
            show_progress_bar=False,
        )

        return np.array(embedding[0])


class MockEmbeddingModel:
    """Mock embedding model for testing."""

    def __init__(self, model_info: ModelInfo):
        self._model_info = model_info
        self._dimensions = model_info.dimensions

    @property
    def dimensions(self) -> int:
        """Return embedding dimensions."""
        return self._dimensions

    @property
    def model_info(self) -> ModelInfo:
        """Return model info."""
        return self._model_info

    def embed(self, texts: list[str]) -> np.ndarray:
        """Generate deterministic mock embeddings."""
        if not texts:
            return np.array([])

        embeddings = []
        for text in texts:
            # Create deterministic embedding based on text hash
            np.random.seed(hash(text) % (2**32))
            embedding = np.random.randn(self._dimensions)
            # Normalize
            embedding = embedding / np.linalg.norm(embedding)
            embeddings.append(embedding)

        # np.array() is typed as Any when numpy stubs are incomplete
        result: np.ndarray[Any, Any] = np.array(embeddings)
        return result

    def embed_query(self, query: str) -> np.ndarray:
        """Generate mock query embedding."""
        embeddings = self.embed([query])
        return embeddings[0]  # type: ignore[no-any-return]


# Model cache
_model_cache: dict[str, EmbeddingModelProtocol] = {}


def get_model(model_name: str | None = None) -> EmbeddingModelProtocol:
    """
    Get an embedding model by name.

    Args:
        model_name: Model name from MODELS registry, or None for default

    Returns:
        Embedding model instance
    """
    model_name = model_name or DEFAULT_MODEL

    if model_name in _model_cache:
        return _model_cache[model_name]

    if model_name not in MODELS:
        raise ValueError(f"Unknown model: {model_name}. Available: {list(MODELS.keys())}")

    model_info = MODELS[model_name]
    model: EmbeddingModelProtocol

    if model_info.model_type == ModelType.SENTENCE_TRANSFORMER:
        model = SentenceTransformerModel(model_info)
    elif model_info.model_type == ModelType.MOCK:
        model = MockEmbeddingModel(model_info)
    else:
        raise ValueError(f"Unsupported model type: {model_info.model_type}")

    _model_cache[model_name] = model
    return model


def list_models() -> list[ModelInfo]:
    """List all available models."""
    return list(MODELS.values())


def get_model_info(model_name: str) -> ModelInfo | None:
    """Get info for a specific model."""
    return MODELS.get(model_name)
