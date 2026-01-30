"""Tests for snapshot testing utilities."""

import json
import tempfile
from pathlib import Path

import pytest

from tests.fixtures.snapshots import (
    Snapshot,
    SnapshotAssertion,
    SnapshotDiff,
    SnapshotStore,
    assert_snapshot,
    get_snapshot,
    list_snapshots,
    normalize_floats,
    normalize_ids,
    normalize_timestamps,
    normalize_uuids,
    normalize_whitespace,
    update_snapshot,
)


class TestSnapshotDiff:
    """Tests for SnapshotDiff."""

    def test_is_match_when_equal(self):
        diff = SnapshotDiff(expected="hello", actual="hello")
        assert diff.is_match is True

    def test_is_match_when_different(self):
        diff = SnapshotDiff(expected="hello", actual="world")
        assert diff.is_match is False

    def test_unified_diff_output(self):
        diff = SnapshotDiff(
            expected="line1\nline2\nline3",
            actual="line1\nmodified\nline3",
        )
        output = diff.unified_diff()
        assert "--- expected" in output
        assert "+++ actual" in output
        assert "-line2" in output
        assert "+modified" in output

    def test_str_when_match(self):
        diff = SnapshotDiff(expected="test", actual="test")
        assert str(diff) == "Snapshot matches"

    def test_str_when_mismatch(self):
        diff = SnapshotDiff(expected="old", actual="new")
        output = str(diff)
        assert "Snapshot mismatch" in output


class TestSnapshot:
    """Tests for Snapshot dataclass."""

    def test_create_snapshot(self):
        snap = Snapshot(name="test", content="hello world")
        assert snap.name == "test"
        assert snap.content == "hello world"

    def test_snapshot_metadata(self):
        snap = Snapshot(
            name="test",
            content="data",
            metadata={"key": "value"},
        )
        assert snap.metadata["key"] == "value"

    def test_to_dict(self):
        snap = Snapshot(
            name="test",
            content="content here",
            metadata={"format": "json"},
        )
        data = snap.to_dict()

        assert data["name"] == "test"
        assert data["content"] == "content here"
        assert data["metadata"]["format"] == "json"
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_dict(self):
        data = {
            "name": "my_snapshot",
            "content": "snapshot content",
            "metadata": {"type": "output"},
            "created_at": "2026-01-29T12:00:00",
            "updated_at": "2026-01-29T12:00:00",
        }
        snap = Snapshot.from_dict(data)

        assert snap.name == "my_snapshot"
        assert snap.content == "snapshot content"
        assert snap.metadata["type"] == "output"


class TestSnapshotStore:
    """Tests for SnapshotStore."""

    def test_create_store(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir))
            assert store.snapshot_dir == Path(tmpdir)

    def test_save_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir))

            snap = Snapshot(name="test", content="hello")
            store.save(snap)

            retrieved = store.get("test")
            assert retrieved is not None
            assert retrieved.content == "hello"

    def test_get_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir))
            result = store.get("nonexistent")
            assert result is None

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir))

            snap = Snapshot(name="to_delete", content="data")
            store.save(snap)

            assert store.delete("to_delete") is True
            assert store.get("to_delete") is None

    def test_delete_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir))
            assert store.delete("nonexistent") is False

    def test_list_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            store = SnapshotStore(Path(tmpdir))

            store.save(Snapshot(name="snap1", content="a"))
            store.save(Snapshot(name="snap2", content="b"))
            store.save(Snapshot(name="snap3", content="c"))

            names = store.list_all()
            assert len(names) == 3
            assert "snap1" in names
            assert "snap2" in names
            assert "snap3" in names

    def test_persistence(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Save with one store instance
            store1 = SnapshotStore(Path(tmpdir))
            store1.save(Snapshot(name="persistent", content="data"))

            # Load with another instance
            store2 = SnapshotStore(Path(tmpdir))
            retrieved = store2.get("persistent")

            assert retrieved is not None
            assert retrieved.content == "data"


class TestSnapshotAssertion:
    """Tests for SnapshotAssertion."""

    def test_assert_match_creates_new(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )

            diff = assertion.assert_match("new_snap", {"key": "value"})
            assert diff.is_match is True

    def test_assert_match_succeeds(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial snapshot
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            assertion.assert_match("test", "expected content")

            # Verify it matches
            assertion2 = SnapshotAssertion(snapshot_dir=Path(tmpdir))
            diff = assertion2.assert_match("test", "expected content")
            assert diff.is_match is True

    def test_assert_match_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial snapshot
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            assertion.assert_match("test", "original content")

            # Different content should fail
            assertion2 = SnapshotAssertion(snapshot_dir=Path(tmpdir))
            with pytest.raises(AssertionError) as exc_info:
                assertion2.assert_match("test", "different content")

            assert "doesn't match" in str(exc_info.value)

    def test_assert_match_with_dict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )

            data = {"users": [{"id": 1, "name": "Alice"}]}
            diff = assertion.assert_match("dict_snap", data)
            assert diff.is_match is True

    def test_assert_match_with_normalizer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create snapshot with normalized content
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            assertion.assert_match(
                "normalized",
                '{"created_at": "2026-01-29T12:00:00Z"}',
                normalizers=[normalize_timestamps],
            )

            # Should match with different timestamp
            assertion2 = SnapshotAssertion(snapshot_dir=Path(tmpdir))
            diff = assertion2.assert_match(
                "normalized",
                '{"created_at": "2026-01-30T15:30:00Z"}',
                normalizers=[normalize_timestamps],
            )
            assert diff.is_match is True

    def test_custom_serializer(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )

            def custom_serializer(value):
                return f"CUSTOM:{value}"

            diff = assertion.assert_match(
                "custom",
                "test",
                serializer=custom_serializer,
            )
            assert diff.expected == "CUSTOM:test"


class TestNormalizers:
    """Tests for normalizer functions."""

    def test_normalize_timestamps(self):
        content = '{"created": "2026-01-29T12:00:00Z", "updated": "2026-01-30T15:30:00+00:00"}'
        normalized = normalize_timestamps(content)

        assert "2026-01-29" not in normalized
        assert "<TIMESTAMP>" in normalized

    def test_normalize_timestamps_with_milliseconds(self):
        content = '{"time": "2026-01-29T12:00:00.123Z"}'
        normalized = normalize_timestamps(content)
        assert "<TIMESTAMP>" in normalized

    def test_normalize_uuids(self):
        content = '{"id": "550e8400-e29b-41d4-a716-446655440000"}'
        normalized = normalize_uuids(content)

        assert "550e8400" not in normalized
        assert "<UUID>" in normalized

    def test_normalize_uuids_case_insensitive(self):
        content = '{"id": "550E8400-E29B-41D4-A716-446655440000"}'
        normalized = normalize_uuids(content)
        assert "<UUID>" in normalized

    def test_normalize_ids(self):
        content = '{"id": 12345, "user_id": 67890}'
        normalized = normalize_ids(content)

        assert "12345" not in normalized
        assert "67890" not in normalized
        assert "<ID>" in normalized

    def test_normalize_floats(self):
        content = "value: 3.14159265359"
        normalized = normalize_floats(content, precision=2)

        assert "3.14159" not in normalized
        assert "3.14" in normalized

    def test_normalize_whitespace(self):
        content = "hello   world\t\there  \nline2   \n"
        normalized = normalize_whitespace(content)

        assert "  " not in normalized
        assert normalized == "hello world here\nline2"

    def test_normalize_whitespace_crlf(self):
        content = "line1\r\nline2\r\n"
        normalized = normalize_whitespace(content)
        assert "\r" not in normalized


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_assert_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create
            diff = assert_snapshot(
                "convenience_test",
                {"data": "test"},
                snapshot_dir=Path(tmpdir),
                update=True,
            )
            assert diff.is_match is True

            # Verify
            diff2 = assert_snapshot(
                "convenience_test",
                {"data": "test"},
                snapshot_dir=Path(tmpdir),
            )
            assert diff2.is_match is True

    def test_update_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = update_snapshot(
                "updated",
                {"key": "value"},
                snapshot_dir=Path(tmpdir),
            )

            assert snap.name == "updated"
            # Should be JSON serialized
            assert "key" in snap.content

    def test_get_snapshot(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first
            update_snapshot("get_test", "content", snapshot_dir=Path(tmpdir))

            # Get it
            snap = get_snapshot("get_test", snapshot_dir=Path(tmpdir))
            assert snap is not None
            assert snap.content == "content"

    def test_get_snapshot_nonexistent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            snap = get_snapshot("nonexistent", snapshot_dir=Path(tmpdir))
            assert snap is None

    def test_list_snapshots(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            update_snapshot("list1", "a", snapshot_dir=Path(tmpdir))
            update_snapshot("list2", "b", snapshot_dir=Path(tmpdir))

            names = list_snapshots(snapshot_dir=Path(tmpdir))
            assert "list1" in names
            assert "list2" in names


class TestComplexScenarios:
    """Tests for complex usage scenarios."""

    def test_snapshot_with_multiple_normalizers(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            content = {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_at": "2026-01-29T12:00:00Z",
                "user_id": 12345,
            }

            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            assertion.assert_match(
                "multi_normalized",
                content,
                normalizers=[normalize_uuids, normalize_timestamps, normalize_ids],
            )

            # Different values but same structure
            content2 = {
                "id": "11111111-2222-3333-4444-555555555555",
                "created_at": "2026-02-15T08:30:00Z",
                "user_id": 99999,
            }

            assertion2 = SnapshotAssertion(snapshot_dir=Path(tmpdir))
            diff = assertion2.assert_match(
                "multi_normalized",
                content2,
                normalizers=[normalize_uuids, normalize_timestamps, normalize_ids],
            )
            assert diff.is_match is True

    def test_snapshot_update_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initial snapshot
            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            assertion.assert_match("evolving", "version 1")

            # Update the snapshot
            assertion2 = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            assertion2.assert_match("evolving", "version 2")

            # Verify updated version
            assertion3 = SnapshotAssertion(snapshot_dir=Path(tmpdir))
            diff = assertion3.assert_match("evolving", "version 2")
            assert diff.is_match is True

    def test_object_with_to_dict(self):
        """Test serialization of objects with to_dict method."""
        with tempfile.TemporaryDirectory() as tmpdir:

            class CustomObject:
                def __init__(self):
                    self.value = 42
                    self.name = "test"

                def to_dict(self):
                    return {"value": self.value, "name": self.name}

            obj = CustomObject()

            assertion = SnapshotAssertion(
                snapshot_dir=Path(tmpdir),
                update_snapshots=True,
            )
            diff = assertion.assert_match("custom_obj", obj)
            assert diff.is_match is True

            # Verify serialization
            snap = get_snapshot("custom_obj", snapshot_dir=Path(tmpdir))
            data = json.loads(snap.content)
            assert data["value"] == 42
            assert data["name"] == "test"
