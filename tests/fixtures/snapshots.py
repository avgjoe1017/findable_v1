"""Snapshot testing utilities for comparing complex outputs.

Provides tools for comparing test outputs against stored snapshots,
similar to Jest snapshots but for Python.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Default snapshot directory
DEFAULT_SNAPSHOT_DIR = Path("tests/fixtures/snapshots")


@dataclass
class SnapshotDiff:
    """Represents the difference between actual and expected."""

    expected: str
    actual: str
    diff_lines: list[str] = field(default_factory=list)

    @property
    def is_match(self) -> bool:
        """Check if actual matches expected."""
        return self.expected == self.actual

    def unified_diff(self) -> str:
        """Generate unified diff output."""
        expected_lines = self.expected.splitlines(keepends=True)
        actual_lines = self.actual.splitlines(keepends=True)

        diff = difflib.unified_diff(
            expected_lines,
            actual_lines,
            fromfile="expected",
            tofile="actual",
            lineterm="",
        )
        return "".join(diff)

    def __str__(self) -> str:
        if self.is_match:
            return "Snapshot matches"
        return f"Snapshot mismatch:\n{self.unified_diff()}"


@dataclass
class Snapshot:
    """A stored snapshot for comparison."""

    name: str
    content: str
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "content": self.content,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Snapshot:
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


class SnapshotStore:
    """Manages snapshot storage and retrieval."""

    def __init__(self, snapshot_dir: Path | None = None):
        self.snapshot_dir = snapshot_dir or DEFAULT_SNAPSHOT_DIR
        self._snapshots: dict[str, Snapshot] = {}
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Load snapshots from disk if not already loaded."""
        if self._loaded:
            return

        if self.snapshot_dir.exists():
            for path in self.snapshot_dir.glob("*.snap.json"):
                snapshot = self._load_file(path)
                if snapshot:
                    self._snapshots[snapshot.name] = snapshot

        self._loaded = True

    def _load_file(self, path: Path) -> Snapshot | None:
        """Load a snapshot from file."""
        try:
            with open(path) as f:
                data = json.load(f)
            return Snapshot.from_dict(data)
        except (OSError, json.JSONDecodeError):
            return None

    def _save_file(self, snapshot: Snapshot) -> None:
        """Save a snapshot to file."""
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.snapshot_dir / f"{snapshot.name}.snap.json"
        with open(path, "w") as f:
            json.dump(snapshot.to_dict(), f, indent=2)

    def get(self, name: str) -> Snapshot | None:
        """Get a snapshot by name."""
        self._ensure_loaded()
        return self._snapshots.get(name)

    def save(self, snapshot: Snapshot) -> None:
        """Save a snapshot."""
        self._snapshots[snapshot.name] = snapshot
        self._save_file(snapshot)

    def delete(self, name: str) -> bool:
        """Delete a snapshot."""
        self._ensure_loaded()
        if name in self._snapshots:
            del self._snapshots[name]
            path = self.snapshot_dir / f"{name}.snap.json"
            if path.exists():
                path.unlink()
            return True
        return False

    def list_all(self) -> list[str]:
        """List all snapshot names."""
        self._ensure_loaded()
        return list(self._snapshots.keys())


class SnapshotAssertion:
    """Context for snapshot assertions in tests."""

    def __init__(
        self,
        snapshot_dir: Path | None = None,
        update_snapshots: bool = False,
    ):
        """Initialize snapshot assertion.

        Args:
            snapshot_dir: Directory for snapshot storage
            update_snapshots: If True, update snapshots instead of comparing
        """
        self.store = SnapshotStore(snapshot_dir)
        self.update_snapshots = update_snapshots

    def assert_match(
        self,
        name: str,
        actual: Any,
        serializer: Any | None = None,
        normalizers: list | None = None,
    ) -> SnapshotDiff:
        """Assert that actual matches the stored snapshot.

        Args:
            name: Snapshot name
            actual: Actual value to compare
            serializer: Custom serializer (default: JSON)
            normalizers: List of normalizer functions

        Returns:
            SnapshotDiff with comparison results

        Raises:
            AssertionError: If snapshot doesn't match and not updating
        """
        # Serialize actual value
        actual_str = self._serialize(actual, serializer)

        # Apply normalizers
        if normalizers:
            for normalizer in normalizers:
                actual_str = normalizer(actual_str)

        # Get existing snapshot
        snapshot = self.store.get(name)

        if snapshot is None or self.update_snapshots:
            # Create/update snapshot
            snapshot = Snapshot(
                name=name,
                content=actual_str,
                metadata={"serializer": serializer.__name__ if serializer else "json"},
            )
            self.store.save(snapshot)
            return SnapshotDiff(expected=actual_str, actual=actual_str)

        # Compare
        diff = SnapshotDiff(expected=snapshot.content, actual=actual_str)

        if not diff.is_match:
            raise AssertionError(f"Snapshot '{name}' doesn't match:\n{diff}")

        return diff

    def _serialize(self, value: Any, serializer: Any | None = None) -> str:
        """Serialize a value to string."""
        if serializer:
            return serializer(value)

        if isinstance(value, str):
            return value

        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2, sort_keys=True, default=str)

        if hasattr(value, "to_dict"):
            return json.dumps(value.to_dict(), indent=2, sort_keys=True, default=str)

        if hasattr(value, "__dict__"):
            return json.dumps(value.__dict__, indent=2, sort_keys=True, default=str)

        return str(value)


# Normalizers for common patterns


def normalize_timestamps(content: str) -> str:
    """Replace ISO timestamps with placeholder."""
    # ISO 8601 format: 2026-01-29T12:00:00Z or 2026-01-29T12:00:00+00:00
    pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})?"
    return re.sub(pattern, "<TIMESTAMP>", content)


def normalize_uuids(content: str) -> str:
    """Replace UUIDs with placeholder."""
    pattern = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    return re.sub(pattern, "<UUID>", content, flags=re.IGNORECASE)


def normalize_ids(content: str) -> str:
    """Replace numeric IDs with placeholder."""
    # Match "id": 12345 or "user_id": 12345
    pattern = r'("[\w_]*id"\s*:\s*)\d+'
    return re.sub(pattern, r'\1<ID>', content, flags=re.IGNORECASE)


def normalize_floats(content: str, precision: int = 2) -> str:
    """Normalize floating point precision."""
    def replace_float(match: re.Match) -> str:
        value = float(match.group())
        return f"{value:.{precision}f}"

    pattern = r"-?\d+\.\d+"
    return re.sub(pattern, replace_float, content)


def normalize_whitespace(content: str) -> str:
    """Normalize whitespace."""
    # Replace multiple spaces/tabs with single space
    content = re.sub(r"[ \t]+", " ", content)
    # Remove trailing whitespace
    content = re.sub(r" +\n", "\n", content)
    # Normalize line endings
    content = content.replace("\r\n", "\n")
    return content.strip()


# Convenience functions


def assert_snapshot(
    name: str,
    actual: Any,
    snapshot_dir: Path | None = None,
    update: bool = False,
    normalizers: list | None = None,
) -> SnapshotDiff:
    """Assert that actual matches the stored snapshot.

    Convenience function for one-off snapshot assertions.

    Args:
        name: Snapshot name
        actual: Actual value to compare
        snapshot_dir: Directory for snapshot storage
        update: If True, update snapshot instead of comparing
        normalizers: List of normalizer functions

    Returns:
        SnapshotDiff with comparison results

    Example:
        assert_snapshot("my_test_output", result_dict)
    """
    assertion = SnapshotAssertion(
        snapshot_dir=snapshot_dir,
        update_snapshots=update,
    )
    return assertion.assert_match(name, actual, normalizers=normalizers)


def update_snapshot(
    name: str,
    content: Any,
    snapshot_dir: Path | None = None,
) -> Snapshot:
    """Update or create a snapshot.

    Args:
        name: Snapshot name
        content: Content to store
        snapshot_dir: Directory for snapshot storage

    Returns:
        The created/updated Snapshot
    """
    store = SnapshotStore(snapshot_dir)

    # Serialize content
    if isinstance(content, str):
        content_str = content
    elif isinstance(content, (dict, list)):
        content_str = json.dumps(content, indent=2, sort_keys=True, default=str)
    else:
        content_str = str(content)

    snapshot = Snapshot(name=name, content=content_str)
    store.save(snapshot)
    return snapshot


def get_snapshot(name: str, snapshot_dir: Path | None = None) -> Snapshot | None:
    """Get a snapshot by name.

    Args:
        name: Snapshot name
        snapshot_dir: Directory to search

    Returns:
        Snapshot if found, None otherwise
    """
    store = SnapshotStore(snapshot_dir)
    return store.get(name)


def list_snapshots(snapshot_dir: Path | None = None) -> list[str]:
    """List all snapshot names.

    Args:
        snapshot_dir: Directory to search

    Returns:
        List of snapshot names
    """
    store = SnapshotStore(snapshot_dir)
    return store.list_all()
