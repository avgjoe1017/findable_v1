"""Determinism utilities for reproducible testing."""

from __future__ import annotations

import hashlib
import random
from collections.abc import Generator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from unittest.mock import patch


@dataclass
class DeterministicContext:
    """Context manager for deterministic test execution.

    Provides seeded randomization and optional time freezing.
    """

    seed: int = 42
    frozen_time: datetime | None = None
    _original_random_state: Any = field(default=None, repr=False)
    _patches: list = field(default_factory=list, repr=False)

    def __enter__(self) -> DeterministicContext:
        """Enter deterministic context."""
        # Save and set random state
        self._original_random_state = random.getstate()
        random.seed(self.seed)

        # Freeze time if specified
        if self.frozen_time:
            self._freeze_time()

        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit deterministic context and restore state."""
        # Restore random state
        if self._original_random_state:
            random.setstate(self._original_random_state)

        # Unfreeze time
        for p in self._patches:
            p.stop()
        self._patches.clear()

    def _freeze_time(self) -> None:
        """Freeze time to the specified datetime."""
        frozen = self.frozen_time

        # Patch datetime.now()
        class FrozenDatetime:
            @classmethod
            def now(cls, tz: Any = None) -> datetime:
                if tz is not None:
                    return frozen.replace(tzinfo=tz)
                return frozen

            @classmethod
            def utcnow(cls) -> datetime:
                return frozen.replace(tzinfo=None)

            def __new__(cls, *args: Any, **kwargs: Any) -> datetime:
                return datetime(*args, **kwargs)

        # Patch in multiple modules
        modules_to_patch = [
            "datetime.datetime",
        ]

        for module in modules_to_patch:
            try:
                p = patch(module, FrozenDatetime)
                p.start()
                self._patches.append(p)
            except (ModuleNotFoundError, AttributeError):
                pass

    def deterministic_choice(self, items: list) -> Any:
        """Make a deterministic choice from a list."""
        if not items:
            raise ValueError("Cannot choose from empty list")
        return random.choice(items)

    def deterministic_sample(self, items: list, k: int) -> list:
        """Make a deterministic sample from a list."""
        return random.sample(items, min(k, len(items)))

    def deterministic_shuffle(self, items: list) -> list:
        """Return a deterministically shuffled copy of the list."""
        result = items.copy()
        random.shuffle(result)
        return result

    def deterministic_float(self, min_val: float = 0.0, max_val: float = 1.0) -> float:
        """Generate a deterministic random float."""
        return random.uniform(min_val, max_val)

    def deterministic_int(self, min_val: int, max_val: int) -> int:
        """Generate a deterministic random integer."""
        return random.randint(min_val, max_val)


def set_seed(seed: int) -> None:
    """Set the global random seed for reproducibility.

    Sets seeds for:
    - Python's random module
    - NumPy (if available)
    - PyTorch (if available)
    """
    random.seed(seed)

    # Try to set numpy seed
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass

    # Try to set torch seed
    try:
        import torch

        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)
    except ImportError:
        pass


def reset_seeds() -> None:
    """Reset all random seeds to system entropy."""
    random.seed()

    try:
        import numpy as np

        np.random.seed()
    except ImportError:
        pass


@contextmanager
def freeze_time(
    frozen_time: datetime | str | None = None,
) -> Generator[datetime, None, None]:
    """Context manager to freeze time for testing.

    Args:
        frozen_time: The time to freeze to. If None, uses current time.
                    Can be a datetime or ISO format string.

    Yields:
        The frozen datetime.

    Example:
        with freeze_time("2026-01-29T12:00:00Z") as frozen:
            assert datetime.now(UTC) == frozen
    """
    if frozen_time is None:
        frozen = datetime.now(UTC)
    elif isinstance(frozen_time, str):
        frozen = datetime.fromisoformat(frozen_time.replace("Z", "+00:00"))
    else:
        frozen = frozen_time

    ctx = DeterministicContext(frozen_time=frozen)
    with ctx:
        yield frozen


def content_hash(content: str | bytes) -> str:
    """Generate a deterministic hash for content.

    Used for content-based caching and deduplication.
    """
    if isinstance(content, str):
        content = content.encode("utf-8")
    return hashlib.sha256(content).hexdigest()[:16]


def request_hash(method: str, url: str, body: str | bytes | None = None) -> str:
    """Generate a deterministic hash for an HTTP request.

    Used for cassette matching.
    """
    parts = [method.upper(), url]
    if body:
        if isinstance(body, bytes):
            body = body.decode("utf-8", errors="ignore")
        parts.append(body)

    combined = "|".join(parts)
    return content_hash(combined)


def prompt_hash(prompt: str, model: str | None = None) -> str:
    """Generate a deterministic hash for an LLM prompt.

    Used for response caching.
    """
    parts = [prompt]
    if model:
        parts.append(model)

    combined = "|".join(parts)
    return content_hash(combined)


class SeededRandom:
    """A seeded random number generator for isolated randomness.

    Useful when you need deterministic randomness that doesn't
    affect the global random state.
    """

    def __init__(self, seed: int = 42):
        self._random = random.Random(seed)
        self._seed = seed

    def reset(self) -> None:
        """Reset to initial seed."""
        self._random.seed(self._seed)

    def choice(self, items: list) -> Any:
        """Choose a random item."""
        return self._random.choice(items)

    def sample(self, items: list, k: int) -> list:
        """Sample k items."""
        return self._random.sample(items, min(k, len(items)))

    def shuffle(self, items: list) -> list:
        """Return a shuffled copy."""
        result = items.copy()
        self._random.shuffle(result)
        return result

    def random(self) -> float:
        """Return a random float in [0, 1)."""
        return self._random.random()

    def randint(self, a: int, b: int) -> int:
        """Return a random integer in [a, b]."""
        return self._random.randint(a, b)

    def uniform(self, a: float, b: float) -> float:
        """Return a random float in [a, b]."""
        return self._random.uniform(a, b)

    def gauss(self, mu: float, sigma: float) -> float:
        """Return a random float from Gaussian distribution."""
        return self._random.gauss(mu, sigma)
