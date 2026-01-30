"""Tests for LLM response recording and replay."""

import tempfile
from pathlib import Path

import pytest

from tests.fixtures.llm_recorder import (
    LLMCassette,
    LLMRecorder,
    LLMResponse,
    create_llm_response,
    load_llm_cassette,
    record_llm,
)


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_create_response(self):
        response = LLMResponse(
            prompt="What is the capital of France?",
            response="The capital of France is Paris.",
            model="gpt-4",
        )
        assert response.prompt == "What is the capital of France?"
        assert response.response == "The capital of France is Paris."
        assert response.model == "gpt-4"

    def test_prompt_hash(self):
        response1 = LLMResponse(
            prompt="What is the capital of France?",
            response="Paris",
            model="gpt-4",
        )
        response2 = LLMResponse(
            prompt="What is the capital of France?",
            response="The capital is Paris.",
            model="gpt-4",
        )
        # Same prompt + model = same hash
        assert response1.prompt_hash == response2.prompt_hash

    def test_different_prompts_different_hash(self):
        response1 = LLMResponse(
            prompt="What is the capital of France?",
            response="Paris",
        )
        response2 = LLMResponse(
            prompt="What is the capital of Germany?",
            response="Berlin",
        )
        assert response1.prompt_hash != response2.prompt_hash

    def test_different_models_different_hash(self):
        response1 = LLMResponse(
            prompt="Test prompt",
            response="Response",
            model="gpt-4",
        )
        response2 = LLMResponse(
            prompt="Test prompt",
            response="Response",
            model="gpt-3.5",
        )
        assert response1.prompt_hash != response2.prompt_hash

    def test_to_dict(self):
        response = LLMResponse(
            prompt="Hello",
            response="Hi there!",
            model="gpt-4",
            temperature=0.7,
            max_tokens=100,
            usage={"prompt_tokens": 5, "completion_tokens": 10},
            latency_ms=150.5,
        )
        data = response.to_dict()

        assert data["prompt"] == "Hello"
        assert data["response"] == "Hi there!"
        assert data["model"] == "gpt-4"
        assert data["temperature"] == 0.7
        assert data["max_tokens"] == 100
        assert data["usage"]["prompt_tokens"] == 5
        assert data["latency_ms"] == 150.5

    def test_from_dict(self):
        data = {
            "prompt": "What is 2+2?",
            "response": "4",
            "model": "gpt-4",
            "temperature": 0.5,
            "max_tokens": 50,
            "usage": {"total_tokens": 15},
            "latency_ms": 200.0,
            "recorded_at": "2026-01-29T12:00:00",
        }
        response = LLMResponse.from_dict(data)

        assert response.prompt == "What is 2+2?"
        assert response.response == "4"
        assert response.model == "gpt-4"
        assert response.temperature == 0.5
        assert response.max_tokens == 50


class TestLLMCassette:
    """Tests for LLMCassette."""

    def test_create_cassette(self):
        cassette = LLMCassette(name="test_cassette")
        assert cassette.name == "test_cassette"
        assert len(cassette.responses) == 0

    def test_add_response(self):
        cassette = LLMCassette(name="test")
        response = LLMResponse(
            prompt="Hello",
            response="Hi!",
        )
        cassette.add(response)

        assert len(cassette.responses) == 1

    def test_add_updates_existing(self):
        cassette = LLMCassette(name="test")
        response1 = LLMResponse(
            prompt="Hello",
            response="Hi!",
            model="gpt-4",
        )
        response2 = LLMResponse(
            prompt="Hello",
            response="Hello there!",
            model="gpt-4",
        )
        cassette.add(response1)
        cassette.add(response2)

        # Should update, not add
        assert len(cassette.responses) == 1
        assert cassette.responses[0].response == "Hello there!"

    def test_find_response(self):
        cassette = LLMCassette(name="test")
        response = LLMResponse(
            prompt="What is AI?",
            response="AI is artificial intelligence.",
            model="gpt-4",
        )
        cassette.add(response)

        found = cassette.find("What is AI?", "gpt-4")
        assert found is not None
        assert found.response == "AI is artificial intelligence."

    def test_find_not_found(self):
        cassette = LLMCassette(name="test")
        found = cassette.find("Unknown prompt")
        assert found is None

    def test_find_without_model_fallback(self):
        cassette = LLMCassette(name="test")
        response = LLMResponse(
            prompt="Test prompt",
            response="Test response",
            model=None,
        )
        cassette.add(response)

        # Should find even when searching with model
        found = cassette.find("Test prompt", "gpt-4")
        assert found is not None

    def test_find_similar(self):
        cassette = LLMCassette(name="test")
        response = LLMResponse(
            prompt="What is the capital city of France?",
            response="Paris",
        )
        cassette.add(response)

        # Similar prompt
        found = cassette.find_similar("What is the capital of France?", threshold=0.5)
        assert found is not None
        assert found.response == "Paris"

    def test_find_similar_below_threshold(self):
        cassette = LLMCassette(name="test")
        response = LLMResponse(
            prompt="What is the capital city of France?",
            response="Paris",
        )
        cassette.add(response)

        # Very different prompt
        found = cassette.find_similar("How do computers work?", threshold=0.8)
        assert found is None

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_cassette.json"

            # Create and save
            cassette = LLMCassette(name="test")
            cassette.add(
                LLMResponse(
                    prompt="Hello",
                    response="Hi!",
                    model="gpt-4",
                )
            )
            cassette.save(path)

            # Load and verify
            loaded = LLMCassette.load(path)
            assert loaded.name == "test"
            assert len(loaded.responses) == 1
            assert loaded.responses[0].prompt == "Hello"
            assert loaded.responses[0].response == "Hi!"


class TestLLMRecorder:
    """Tests for LLMRecorder."""

    def test_create_recorder(self):
        recorder = LLMRecorder()
        assert recorder.strict is False
        assert recorder.fuzzy_match is False

    def test_recorder_with_cassette(self):
        cassette = LLMCassette(name="my_cassette")
        recorder = LLMRecorder(cassette=cassette)
        assert recorder.cassette.name == "my_cassette"

    def test_get_response_found(self):
        cassette = LLMCassette(name="test")
        cassette.add(
            LLMResponse(
                prompt="What is 2+2?",
                response="4",
            )
        )
        recorder = LLMRecorder(cassette=cassette)

        result = recorder.get_response("What is 2+2?")
        assert result == "4"

    def test_get_response_not_found_returns_default(self):
        recorder = LLMRecorder()

        result = recorder.get_response("Unknown prompt", default="default response")
        assert result == "default response"

    def test_get_response_not_found_returns_none(self):
        recorder = LLMRecorder()

        result = recorder.get_response("Unknown prompt")
        assert result is None

    def test_get_response_strict_raises(self):
        recorder = LLMRecorder(strict=True)

        with pytest.raises(KeyError):
            recorder.get_response("Unknown prompt")

    def test_get_response_fuzzy_match(self):
        cassette = LLMCassette(name="test")
        cassette.add(
            LLMResponse(
                prompt="explain python decorators in simple terms",
                response="Decorators wrap functions to add behavior.",
            )
        )
        recorder = LLMRecorder(cassette=cassette, fuzzy_match=True, fuzzy_threshold=0.4)

        # Similar words should match
        result = recorder.get_response("explain decorators in python simple terms")
        assert result == "Decorators wrap functions to add behavior."

    def test_record_response(self):
        recorder = LLMRecorder()

        recorder.record_response(
            prompt="Hello",
            response="Hi!",
            model="gpt-4",
            temperature=0.7,
        )

        assert len(recorder.cassette.responses) == 1
        assert recorder.cassette.responses[0].prompt == "Hello"
        assert recorder.cassette.responses[0].temperature == 0.7

    def test_has_response(self):
        cassette = LLMCassette(name="test")
        cassette.add(
            LLMResponse(
                prompt="Test",
                response="Response",
            )
        )
        recorder = LLMRecorder(cassette=cassette)

        assert recorder.has_response("Test") is True
        assert recorder.has_response("Other") is False

    def test_save_cassette(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette = LLMCassette(name="test")
            cassette.add(
                LLMResponse(
                    prompt="Hello",
                    response="Hi!",
                )
            )

            recorder = LLMRecorder(
                cassette=cassette,
                cassette_dir=Path(tmpdir),
            )
            path = recorder.save_cassette()

            assert path.exists()
            assert path.name == "test.json"

    def test_context_manager(self):
        cassette = LLMCassette(name="test")
        recorder = LLMRecorder(cassette=cassette)

        with recorder:
            assert recorder._active is True

        assert recorder._active is False


class TestCreateLLMResponse:
    """Tests for create_llm_response helper."""

    def test_basic_creation(self):
        response = create_llm_response(
            "What is Python?",
            "Python is a programming language.",
        )
        assert response.prompt == "What is Python?"
        assert response.response == "Python is a programming language."

    def test_with_model(self):
        response = create_llm_response(
            "Test",
            "Response",
            model="gpt-4",
        )
        assert response.model == "gpt-4"

    def test_with_metadata(self):
        response = create_llm_response(
            "Test",
            "Response",
            temperature=0.5,
            max_tokens=100,
            usage={"total_tokens": 50},
        )
        assert response.temperature == 0.5
        assert response.max_tokens == 100
        assert response.usage["total_tokens"] == 50


class TestRecordLLMContextManager:
    """Tests for record_llm context manager."""

    def test_creates_new_cassette(self):
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            record_llm(
                "new_test",
                cassette_dir=Path(tmpdir),
            ) as recorder,
        ):
            assert recorder.cassette.name == "new_test"

    def test_loads_existing_cassette(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a cassette
            cassette = LLMCassette(name="existing")
            cassette.add(
                LLMResponse(
                    prompt="Hello",
                    response="Hi!",
                )
            )
            cassette.save(Path(tmpdir) / "existing.json")

            # Load it via context manager
            with record_llm(
                "existing",
                cassette_dir=Path(tmpdir),
            ) as recorder:
                assert len(recorder.cassette.responses) == 1

    def test_saves_on_exit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with record_llm(
                "auto_save",
                cassette_dir=Path(tmpdir),
            ) as recorder:
                recorder.record_response("Test", "Response")

            # Should be saved
            saved_path = Path(tmpdir) / "auto_save.json"
            assert saved_path.exists()

    def test_strict_mode(self):
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            record_llm(
                "strict_test",
                cassette_dir=Path(tmpdir),
                strict=True,
            ) as recorder,
            pytest.raises(KeyError),
        ):
            recorder.get_response("Unknown")

    def test_fuzzy_mode(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cassette with response
            cassette = LLMCassette(name="fuzzy_test")
            cassette.add(
                LLMResponse(
                    prompt="how do python lists work with examples",
                    response="Lists are ordered collections.",
                )
            )
            cassette.save(Path(tmpdir) / "fuzzy_test.json")

            with record_llm(
                "fuzzy_test",
                cassette_dir=Path(tmpdir),
                fuzzy_match=True,
            ) as recorder:
                # Similar words should match (high overlap)
                result = recorder.get_response("how python lists work with examples")
                assert result == "Lists are ordered collections."


class TestLoadLLMCassette:
    """Tests for load_llm_cassette function."""

    def test_load_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cassette file
            cassette = LLMCassette(name="test")
            cassette.add(
                LLMResponse(
                    prompt="Hello",
                    response="Hi!",
                )
            )
            cassette.save(Path(tmpdir) / "test.json")

            # Load it
            loaded = load_llm_cassette("test", cassette_dir=Path(tmpdir))
            assert loaded.name == "test"

    def test_load_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(FileNotFoundError):
            load_llm_cassette("nonexistent", cassette_dir=Path(tmpdir))
