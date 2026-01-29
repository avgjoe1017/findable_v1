"""Tests for embedding models."""

import numpy as np

from worker.embeddings.models import (
    DEFAULT_MODEL,
    MODELS,
    MockEmbeddingModel,
    ModelInfo,
    ModelType,
    get_model,
    get_model_info,
    list_models,
)


class TestModelInfo:
    """Tests for ModelInfo dataclass."""

    def test_create_model_info(self) -> None:
        """Can create ModelInfo."""
        info = ModelInfo(
            name="test",
            model_id="test/model",
            model_type=ModelType.MOCK,
            dimensions=384,
            max_tokens=512,
            description="Test model",
        )

        assert info.name == "test"
        assert info.dimensions == 384
        assert info.model_type == ModelType.MOCK


class TestModelsRegistry:
    """Tests for models registry."""

    def test_models_exist(self) -> None:
        """All expected models are registered."""
        assert "bge-small" in MODELS
        assert "bge-base" in MODELS
        assert "minilm" in MODELS
        assert "e5-small" in MODELS
        assert "mock" in MODELS

    def test_default_model_exists(self) -> None:
        """Default model is in registry."""
        assert DEFAULT_MODEL in MODELS

    def test_model_dimensions(self) -> None:
        """Models have correct dimensions."""
        assert MODELS["bge-small"].dimensions == 384
        assert MODELS["bge-base"].dimensions == 768
        assert MODELS["minilm"].dimensions == 384


class TestMockEmbeddingModel:
    """Tests for MockEmbeddingModel."""

    def test_create_mock_model(self) -> None:
        """Can create mock model."""
        info = MODELS["mock"]
        model = MockEmbeddingModel(info)

        assert model.dimensions == info.dimensions
        assert model.model_info == info

    def test_embed_single_text(self) -> None:
        """Can embed single text."""
        model = MockEmbeddingModel(MODELS["mock"])
        embeddings = model.embed(["Hello world"])

        assert len(embeddings) == 1
        assert embeddings[0].shape == (384,)

    def test_embed_multiple_texts(self) -> None:
        """Can embed multiple texts."""
        model = MockEmbeddingModel(MODELS["mock"])
        texts = ["First text", "Second text", "Third text"]
        embeddings = model.embed(texts)

        assert len(embeddings) == 3
        for emb in embeddings:
            assert emb.shape == (384,)

    def test_embed_empty_list(self) -> None:
        """Empty list returns empty array."""
        model = MockEmbeddingModel(MODELS["mock"])
        embeddings = model.embed([])

        assert len(embeddings) == 0

    def test_embeddings_are_normalized(self) -> None:
        """Mock embeddings are normalized."""
        model = MockEmbeddingModel(MODELS["mock"])
        embeddings = model.embed(["Test text"])

        norm = np.linalg.norm(embeddings[0])
        assert abs(norm - 1.0) < 0.001

    def test_embeddings_are_deterministic(self) -> None:
        """Same text produces same embedding."""
        model = MockEmbeddingModel(MODELS["mock"])
        text = "Deterministic test"

        emb1 = model.embed([text])
        emb2 = model.embed([text])

        np.testing.assert_array_equal(emb1, emb2)

    def test_different_texts_different_embeddings(self) -> None:
        """Different texts produce different embeddings."""
        model = MockEmbeddingModel(MODELS["mock"])

        emb1 = model.embed(["First text"])
        emb2 = model.embed(["Second text"])

        assert not np.array_equal(emb1[0], emb2[0])

    def test_embed_query(self) -> None:
        """Can embed a query."""
        model = MockEmbeddingModel(MODELS["mock"])
        embedding = model.embed_query("Search query")

        assert embedding.shape == (384,)


class TestGetModel:
    """Tests for get_model function."""

    def test_get_mock_model(self) -> None:
        """Can get mock model."""
        model = get_model("mock")

        assert model.dimensions == 384
        assert model.model_info.name == "mock"

    def test_get_default_model(self) -> None:
        """None returns default model (may fail without deps)."""
        # This will try to load bge-small, which needs sentence-transformers
        # So we just test that it raises appropriate error or works
        try:
            model = get_model(None)
            assert model is not None
        except ImportError:
            # Expected if sentence-transformers not installed
            pass

    def test_unknown_model_raises(self) -> None:
        """Unknown model raises ValueError."""
        try:
            get_model("nonexistent-model")
            raise AssertionError("Should have raised ValueError")
        except ValueError as e:
            assert "Unknown model" in str(e)

    def test_model_caching(self) -> None:
        """Models are cached."""
        model1 = get_model("mock")
        model2 = get_model("mock")

        assert model1 is model2


class TestListModels:
    """Tests for list_models function."""

    def test_list_models(self) -> None:
        """Can list all models."""
        models = list_models()

        assert len(models) >= 5
        assert all(isinstance(m, ModelInfo) for m in models)


class TestGetModelInfo:
    """Tests for get_model_info function."""

    def test_get_existing_model_info(self) -> None:
        """Can get info for existing model."""
        info = get_model_info("mock")

        assert info is not None
        assert info.name == "mock"

    def test_get_nonexistent_model_info(self) -> None:
        """Returns None for nonexistent model."""
        info = get_model_info("nonexistent")

        assert info is None


class TestModelType:
    """Tests for ModelType enum."""

    def test_all_types(self) -> None:
        """All model types exist."""
        assert ModelType.SENTENCE_TRANSFORMER == "sentence_transformer"
        assert ModelType.OPENAI == "openai"
        assert ModelType.MOCK == "mock"
