"""LLM response recording and replay for deterministic testing.

Provides caching and replay of LLM API responses for reproducible tests.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from tests.fixtures.determinism import prompt_hash


@dataclass
class LLMResponse:
    """A recorded LLM response."""

    prompt: str
    response: str
    model: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    usage: dict | None = None
    latency_ms: float | None = None
    recorded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def prompt_hash(self) -> str:
        """Generate a hash for prompt matching."""
        return prompt_hash(self.prompt, self.model)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "prompt": self.prompt,
            "response": self.response,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LLMResponse:
        """Create from dictionary."""
        return cls(
            prompt=data.get("prompt", ""),
            response=data.get("response", ""),
            model=data.get("model"),
            temperature=data.get("temperature"),
            max_tokens=data.get("max_tokens"),
            usage=data.get("usage"),
            latency_ms=data.get("latency_ms"),
            recorded_at=data.get("recorded_at", ""),
        )


@dataclass
class LLMCassette:
    """A collection of LLM responses for replay.

    Stores recorded LLM responses indexed by prompt hash.
    """

    name: str
    responses: list[LLMResponse] = field(default_factory=list)
    _index: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Build the lookup index."""
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the hash-to-index lookup."""
        self._index.clear()
        for i, response in enumerate(self.responses):
            self._index[response.prompt_hash] = i

    def add(self, response: LLMResponse) -> None:
        """Add a response to the cassette."""
        # Check if we already have this prompt
        existing_idx = self._index.get(response.prompt_hash)
        if existing_idx is not None:
            # Update existing
            self.responses[existing_idx] = response
        else:
            # Add new
            self.responses.append(response)
            self._index[response.prompt_hash] = len(self.responses) - 1

    def find(self, prompt: str, model: str | None = None) -> LLMResponse | None:
        """Find a matching response."""
        hash_key = prompt_hash(prompt, model)
        idx = self._index.get(hash_key)
        if idx is not None:
            return self.responses[idx]

        # Try without model if not found
        if model:
            hash_key = prompt_hash(prompt, None)
            idx = self._index.get(hash_key)
            if idx is not None:
                return self.responses[idx]

        return None

    def find_similar(self, prompt: str, threshold: float = 0.8) -> LLMResponse | None:
        """Find a response with a similar prompt (fuzzy matching).

        Uses simple word overlap for similarity.
        """
        prompt_words = set(prompt.lower().split())

        best_match = None
        best_score = 0.0

        for response in self.responses:
            response_words = set(response.prompt.lower().split())

            # Jaccard similarity
            intersection = len(prompt_words & response_words)
            union = len(prompt_words | response_words)

            if union > 0:
                score = intersection / union
                if score > best_score and score >= threshold:
                    best_score = score
                    best_match = response

        return best_match

    def save(self, path: Path) -> None:
        """Save cassette to file."""
        data = {
            "name": self.name,
            "responses": [r.to_dict() for r in self.responses],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> LLMCassette:
        """Load cassette from file."""
        with open(path) as f:
            data = json.load(f)

        return cls(
            name=data.get("name", path.stem),
            responses=[LLMResponse.from_dict(r) for r in data.get("responses", [])],
        )


class LLMRecorder:
    """Records and replays LLM responses.

    Can be used to make LLM-based tests deterministic by
    recording responses and replaying them in subsequent runs.
    """

    def __init__(
        self,
        cassette: LLMCassette | None = None,
        cassette_dir: Path | None = None,
        strict: bool = False,
        fuzzy_match: bool = False,
        fuzzy_threshold: float = 0.8,
    ):
        """Initialize recorder.

        Args:
            cassette: Cassette to use for recording/replay
            cassette_dir: Directory for cassette storage
            strict: If True, raise error when no match found
            fuzzy_match: If True, use fuzzy matching for prompts
            fuzzy_threshold: Similarity threshold for fuzzy matching
        """
        self.cassette = cassette or LLMCassette(name="default")
        self.cassette_dir = cassette_dir or Path("tests/fixtures/llm_cassettes")
        self.strict = strict
        self.fuzzy_match = fuzzy_match
        self.fuzzy_threshold = fuzzy_threshold
        self._active = False

    def start(self) -> None:
        """Start recording/replaying."""
        self._active = True

    def stop(self) -> None:
        """Stop recording."""
        self._active = False

    def __enter__(self) -> LLMRecorder:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def get_response(
        self,
        prompt: str,
        model: str | None = None,
        default: str | None = None,
    ) -> str | None:
        """Get a recorded response for a prompt.

        Args:
            prompt: The prompt to look up
            model: Optional model name for matching
            default: Default response if not found (and not strict)

        Returns:
            The recorded response, default, or None

        Raises:
            KeyError: If strict=True and no match found
        """
        # Try exact match first
        response = self.cassette.find(prompt, model)

        # Try fuzzy match if enabled
        if response is None and self.fuzzy_match:
            response = self.cassette.find_similar(prompt, self.fuzzy_threshold)

        if response is not None:
            return response.response

        if self.strict:
            raise KeyError(f"No recorded response for prompt: {prompt[:100]}...")

        return default

    def record_response(
        self,
        prompt: str,
        response: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Record a new response.

        Args:
            prompt: The prompt that was sent
            response: The response received
            model: The model used
            **kwargs: Additional metadata (temperature, max_tokens, etc.)
        """
        llm_response = LLMResponse(
            prompt=prompt,
            response=response,
            model=model,
            temperature=kwargs.get("temperature"),
            max_tokens=kwargs.get("max_tokens"),
            usage=kwargs.get("usage"),
            latency_ms=kwargs.get("latency_ms"),
        )
        self.cassette.add(llm_response)

    def save_cassette(self, name: str | None = None) -> Path:
        """Save the current cassette to disk."""
        cassette_name = name or self.cassette.name
        path = self.cassette_dir / f"{cassette_name}.json"
        self.cassette.save(path)
        return path

    def has_response(self, prompt: str, model: str | None = None) -> bool:
        """Check if a response exists for a prompt."""
        return self.cassette.find(prompt, model) is not None


@contextmanager
def record_llm(
    cassette_name: str,
    cassette_dir: Path | None = None,
    strict: bool = False,
    fuzzy_match: bool = False,
) -> Generator[LLMRecorder, None, None]:
    """Context manager for LLM recording/replay.

    Args:
        cassette_name: Name of the cassette file (without extension)
        cassette_dir: Directory for cassette storage
        strict: If True, raise error when no match found
        fuzzy_match: If True, use fuzzy matching for prompts

    Yields:
        LLMRecorder instance

    Example:
        with record_llm("my_test") as recorder:
            response = recorder.get_response(prompt, default="test response")
    """
    cassette_dir = cassette_dir or Path("tests/fixtures/llm_cassettes")
    cassette_path = cassette_dir / f"{cassette_name}.json"

    # Load existing cassette if it exists
    if cassette_path.exists():
        cassette = LLMCassette.load(cassette_path)
    else:
        cassette = LLMCassette(name=cassette_name)

    recorder = LLMRecorder(
        cassette=cassette,
        cassette_dir=cassette_dir,
        strict=strict,
        fuzzy_match=fuzzy_match,
    )

    with recorder:
        yield recorder

    # Save cassette
    recorder.save_cassette()


def load_llm_cassette(name: str, cassette_dir: Path | None = None) -> LLMCassette:
    """Load an LLM cassette from disk.

    Args:
        name: Cassette name (without extension)
        cassette_dir: Directory to load from

    Returns:
        Loaded LLMCassette
    """
    cassette_dir = cassette_dir or Path("tests/fixtures/llm_cassettes")
    path = cassette_dir / f"{name}.json"

    if not path.exists():
        raise FileNotFoundError(f"LLM cassette not found: {path}")

    return LLMCassette.load(path)


def create_llm_response(
    prompt: str,
    response: str,
    model: str | None = None,
    **kwargs: Any,
) -> LLMResponse:
    """Helper to create an LLM response for testing.

    Example:
        response = create_llm_response(
            "What is the capital of France?",
            "The capital of France is Paris.",
            model="gpt-4",
        )
        cassette.add(response)
    """
    return LLMResponse(
        prompt=prompt,
        response=response,
        model=model,
        temperature=kwargs.get("temperature"),
        max_tokens=kwargs.get("max_tokens"),
        usage=kwargs.get("usage"),
        latency_ms=kwargs.get("latency_ms"),
    )
