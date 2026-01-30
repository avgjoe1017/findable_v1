"""HTTP recording and replay for deterministic testing.

Provides VCR-style recording of HTTP interactions for replay in tests.
"""

from __future__ import annotations

import json
import re
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

from tests.fixtures.determinism import request_hash


class RecordMode(str, Enum):
    """Recording mode for HTTP interactions."""

    # Only replay from cassette, fail if no match
    NONE = "none"
    # Record new interactions, replay existing
    NEW_EPISODES = "new_episodes"
    # Record all interactions, overwrite existing
    ALL = "all"
    # Replay only, but don't fail on missing (return None)
    OPTIONAL = "optional"


@dataclass
class HTTPInteraction:
    """A single HTTP request/response interaction."""

    request_method: str
    request_url: str
    request_headers: dict[str, str] = field(default_factory=dict)
    request_body: str | None = None

    response_status: int = 200
    response_headers: dict[str, str] = field(default_factory=dict)
    response_body: str = ""

    recorded_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    @property
    def request_hash(self) -> str:
        """Generate a hash for request matching."""
        return request_hash(
            self.request_method,
            self.request_url,
            self.request_body,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "request": {
                "method": self.request_method,
                "url": self.request_url,
                "headers": self.request_headers,
                "body": self.request_body,
            },
            "response": {
                "status": self.response_status,
                "headers": self.response_headers,
                "body": self.response_body,
            },
            "recorded_at": self.recorded_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> HTTPInteraction:
        """Create from dictionary."""
        req = data.get("request", {})
        resp = data.get("response", {})
        return cls(
            request_method=req.get("method", "GET"),
            request_url=req.get("url", ""),
            request_headers=req.get("headers", {}),
            request_body=req.get("body"),
            response_status=resp.get("status", 200),
            response_headers=resp.get("headers", {}),
            response_body=resp.get("body", ""),
            recorded_at=data.get("recorded_at", ""),
        )


@dataclass
class HTTPCassette:
    """A collection of HTTP interactions for replay.

    Similar to VCR cassettes - stores recorded HTTP interactions.
    """

    name: str
    interactions: list[HTTPInteraction] = field(default_factory=list)
    _index: dict[str, int] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        """Build the lookup index."""
        self._rebuild_index()

    def _rebuild_index(self) -> None:
        """Rebuild the hash-to-index lookup."""
        self._index.clear()
        for i, interaction in enumerate(self.interactions):
            self._index[interaction.request_hash] = i

    def add(self, interaction: HTTPInteraction) -> None:
        """Add an interaction to the cassette."""
        self.interactions.append(interaction)
        self._index[interaction.request_hash] = len(self.interactions) - 1

    def find(
        self, method: str, url: str, body: str | None = None
    ) -> HTTPInteraction | None:
        """Find a matching interaction."""
        req_hash = request_hash(method, url, body)
        idx = self._index.get(req_hash)
        if idx is not None:
            return self.interactions[idx]
        return None

    def find_by_url_pattern(
        self, method: str, url_pattern: str
    ) -> HTTPInteraction | None:
        """Find an interaction by URL regex pattern."""
        pattern = re.compile(url_pattern)
        for interaction in self.interactions:
            if (
                interaction.request_method.upper() == method.upper()
                and pattern.match(interaction.request_url)
            ):
                return interaction
        return None

    def save(self, path: Path) -> None:
        """Save cassette to file."""
        data = {
            "name": self.name,
            "interactions": [i.to_dict() for i in self.interactions],
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, path: Path) -> HTTPCassette:
        """Load cassette from file."""
        with open(path) as f:
            data = json.load(f)

        return cls(
            name=data.get("name", path.stem),
            interactions=[
                HTTPInteraction.from_dict(i) for i in data.get("interactions", [])
            ],
        )


class HTTPRecorder:
    """Records and replays HTTP interactions.

    Can be used as a context manager or with explicit start/stop.
    """

    def __init__(
        self,
        cassette: HTTPCassette | None = None,
        mode: RecordMode = RecordMode.NEW_EPISODES,
        cassette_dir: Path | None = None,
    ):
        self.cassette = cassette or HTTPCassette(name="default")
        self.mode = mode
        self.cassette_dir = cassette_dir or Path("tests/fixtures/cassettes")
        self._patches: list = []
        self._original_methods: dict = {}

    def start(self) -> None:
        """Start recording/replaying HTTP interactions."""
        # Patch httpx.AsyncClient
        self._patch_httpx()

    def stop(self) -> None:
        """Stop recording and restore original methods."""
        for p in self._patches:
            p.stop()
        self._patches.clear()

    def __enter__(self) -> HTTPRecorder:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()

    def _patch_httpx(self) -> None:
        """Patch httpx for recording/replay."""
        recorder = self

        async def mock_request(
            self: Any,
            method: str,
            url: str,
            **kwargs: Any,
        ) -> Any:
            """Mock httpx request method."""
            body = kwargs.get("content") or kwargs.get("data") or kwargs.get("json")
            if body and not isinstance(body, str):
                body = json.dumps(body) if isinstance(body, dict) else str(body)

            # Try to find in cassette
            interaction = recorder.cassette.find(method, str(url), body)

            if interaction:
                # Return recorded response
                return _create_mock_response(interaction)

            if recorder.mode == RecordMode.NONE:
                raise ValueError(
                    f"No recorded interaction for {method} {url} "
                    f"(mode=NONE, cassette={recorder.cassette.name})"
                )

            if recorder.mode == RecordMode.OPTIONAL:
                return None

            # Record new interaction (modes: NEW_EPISODES, ALL)
            # In real implementation, would make actual request
            # For now, return a placeholder
            raise NotImplementedError(
                "Recording requires actual HTTP client. "
                "Use record_http() with real requests or provide cassette data."
            )

        # Create patch
        try:
            p = patch("httpx.AsyncClient.request", mock_request)
            p.start()
            self._patches.append(p)
        except (ModuleNotFoundError, AttributeError):
            pass

    def save_cassette(self, name: str | None = None) -> Path:
        """Save the current cassette to disk."""
        cassette_name = name or self.cassette.name
        path = self.cassette_dir / f"{cassette_name}.json"
        self.cassette.save(path)
        return path


def _create_mock_response(interaction: HTTPInteraction) -> Any:
    """Create a mock httpx Response from an interaction."""
    # Create a mock response object
    mock = AsyncMock()
    mock.status_code = interaction.response_status
    mock.headers = interaction.response_headers
    mock.text = interaction.response_body
    mock.content = interaction.response_body.encode("utf-8")
    mock.json.return_value = (
        json.loads(interaction.response_body)
        if interaction.response_body.strip().startswith(("{", "["))
        else {}
    )
    mock.is_success = 200 <= interaction.response_status < 300
    mock.is_error = interaction.response_status >= 400
    return mock


@contextmanager
def record_http(
    cassette_name: str,
    mode: RecordMode = RecordMode.NEW_EPISODES,
    cassette_dir: Path | None = None,
) -> Generator[HTTPRecorder, None, None]:
    """Context manager for HTTP recording/replay.

    Args:
        cassette_name: Name of the cassette file (without extension)
        mode: Recording mode
        cassette_dir: Directory for cassette storage

    Yields:
        HTTPRecorder instance

    Example:
        with record_http("my_test") as recorder:
            # HTTP calls will be recorded/replayed
            response = await client.get("https://api.example.com")
    """
    cassette_dir = cassette_dir or Path("tests/fixtures/cassettes")
    cassette_path = cassette_dir / f"{cassette_name}.json"

    # Load existing cassette if it exists
    if cassette_path.exists() and mode != RecordMode.ALL:
        cassette = HTTPCassette.load(cassette_path)
    else:
        cassette = HTTPCassette(name=cassette_name)

    recorder = HTTPRecorder(cassette=cassette, mode=mode, cassette_dir=cassette_dir)

    with recorder:
        yield recorder

    # Save cassette if we recorded anything new
    if mode in (RecordMode.NEW_EPISODES, RecordMode.ALL):
        recorder.save_cassette()


def load_cassette(name: str, cassette_dir: Path | None = None) -> HTTPCassette:
    """Load a cassette from disk.

    Args:
        name: Cassette name (without extension)
        cassette_dir: Directory to load from

    Returns:
        Loaded HTTPCassette
    """
    cassette_dir = cassette_dir or Path("tests/fixtures/cassettes")
    path = cassette_dir / f"{name}.json"

    if not path.exists():
        raise FileNotFoundError(f"Cassette not found: {path}")

    return HTTPCassette.load(path)


def create_interaction(
    method: str,
    url: str,
    response_body: str,
    response_status: int = 200,
    request_body: str | None = None,
    request_headers: dict | None = None,
    response_headers: dict | None = None,
) -> HTTPInteraction:
    """Helper to create an HTTP interaction for testing.

    Example:
        interaction = create_interaction(
            "GET",
            "https://api.example.com/users",
            '{"users": []}',
        )
        cassette.add(interaction)
    """
    return HTTPInteraction(
        request_method=method,
        request_url=url,
        request_body=request_body,
        request_headers=request_headers or {},
        response_status=response_status,
        response_body=response_body,
        response_headers=response_headers or {"content-type": "application/json"},
    )
