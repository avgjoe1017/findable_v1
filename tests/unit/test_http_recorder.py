"""Tests for HTTP recording and replay."""

import tempfile
from pathlib import Path

import pytest

from tests.fixtures.http_recorder import (
    HTTPCassette,
    HTTPInteraction,
    HTTPRecorder,
    RecordMode,
    create_interaction,
    load_cassette,
    record_http,
)


class TestHTTPInteraction:
    """Tests for HTTPInteraction dataclass."""

    def test_create_interaction(self):
        interaction = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com/users",
            response_status=200,
            response_body='{"users": []}',
        )
        assert interaction.request_method == "GET"
        assert interaction.response_status == 200

    def test_request_hash(self):
        interaction1 = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com/users",
        )
        interaction2 = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com/users",
        )
        assert interaction1.request_hash == interaction2.request_hash

    def test_different_requests_different_hash(self):
        interaction1 = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com/users",
        )
        interaction2 = HTTPInteraction(
            request_method="POST",
            request_url="https://api.example.com/users",
        )
        assert interaction1.request_hash != interaction2.request_hash

    def test_to_dict(self):
        interaction = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com",
            request_headers={"Accept": "application/json"},
            response_status=200,
            response_body='{"ok": true}',
            response_headers={"Content-Type": "application/json"},
        )
        data = interaction.to_dict()

        assert data["request"]["method"] == "GET"
        assert data["request"]["url"] == "https://api.example.com"
        assert data["response"]["status"] == 200
        assert data["response"]["body"] == '{"ok": true}'

    def test_from_dict(self):
        data = {
            "request": {
                "method": "POST",
                "url": "https://api.example.com/create",
                "headers": {},
                "body": '{"name": "test"}',
            },
            "response": {
                "status": 201,
                "headers": {},
                "body": '{"id": 1}',
            },
            "recorded_at": "2026-01-29T12:00:00",
        }
        interaction = HTTPInteraction.from_dict(data)

        assert interaction.request_method == "POST"
        assert interaction.request_body == '{"name": "test"}'
        assert interaction.response_status == 201


class TestHTTPCassette:
    """Tests for HTTPCassette."""

    def test_create_cassette(self):
        cassette = HTTPCassette(name="test_cassette")
        assert cassette.name == "test_cassette"
        assert len(cassette.interactions) == 0

    def test_add_interaction(self):
        cassette = HTTPCassette(name="test")
        interaction = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com",
            response_body='{"ok": true}',
        )
        cassette.add(interaction)

        assert len(cassette.interactions) == 1

    def test_find_interaction(self):
        cassette = HTTPCassette(name="test")
        interaction = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com/users",
            response_body='{"users": []}',
        )
        cassette.add(interaction)

        found = cassette.find("GET", "https://api.example.com/users")
        assert found is not None
        assert found.response_body == '{"users": []}'

    def test_find_not_found(self):
        cassette = HTTPCassette(name="test")
        found = cassette.find("GET", "https://nonexistent.com")
        assert found is None

    def test_find_with_body(self):
        cassette = HTTPCassette(name="test")
        interaction = HTTPInteraction(
            request_method="POST",
            request_url="https://api.example.com/create",
            request_body='{"name": "test"}',
            response_body='{"id": 1}',
        )
        cassette.add(interaction)

        found = cassette.find("POST", "https://api.example.com/create", '{"name": "test"}')
        assert found is not None

    def test_find_by_url_pattern(self):
        cassette = HTTPCassette(name="test")
        interaction = HTTPInteraction(
            request_method="GET",
            request_url="https://api.example.com/users/123",
            response_body='{"id": 123}',
        )
        cassette.add(interaction)

        found = cassette.find_by_url_pattern("GET", r"https://api\.example\.com/users/\d+")
        assert found is not None

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test_cassette.json"

            # Create and save
            cassette = HTTPCassette(name="test")
            cassette.add(
                HTTPInteraction(
                    request_method="GET",
                    request_url="https://api.example.com",
                    response_body='{"ok": true}',
                )
            )
            cassette.save(path)

            # Load and verify
            loaded = HTTPCassette.load(path)
            assert loaded.name == "test"
            assert len(loaded.interactions) == 1
            assert loaded.interactions[0].response_body == '{"ok": true}'


class TestHTTPRecorder:
    """Tests for HTTPRecorder."""

    def test_create_recorder(self):
        recorder = HTTPRecorder()
        assert recorder.mode == RecordMode.NEW_EPISODES

    def test_recorder_with_mode(self):
        recorder = HTTPRecorder(mode=RecordMode.NONE)
        assert recorder.mode == RecordMode.NONE

    def test_recorder_with_cassette(self):
        cassette = HTTPCassette(name="my_cassette")
        recorder = HTTPRecorder(cassette=cassette)
        assert recorder.cassette.name == "my_cassette"

    def test_save_cassette(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cassette = HTTPCassette(name="test")
            cassette.add(
                HTTPInteraction(
                    request_method="GET",
                    request_url="https://example.com",
                    response_body="{}",
                )
            )

            recorder = HTTPRecorder(
                cassette=cassette,
                cassette_dir=Path(tmpdir),
            )
            path = recorder.save_cassette()

            assert path.exists()
            assert path.name == "test.json"


class TestRecordMode:
    """Tests for RecordMode enum."""

    def test_none_mode(self):
        assert RecordMode.NONE.value == "none"

    def test_new_episodes_mode(self):
        assert RecordMode.NEW_EPISODES.value == "new_episodes"

    def test_all_mode(self):
        assert RecordMode.ALL.value == "all"

    def test_optional_mode(self):
        assert RecordMode.OPTIONAL.value == "optional"


class TestCreateInteraction:
    """Tests for create_interaction helper."""

    def test_basic_creation(self):
        interaction = create_interaction(
            "GET",
            "https://api.example.com",
            '{"status": "ok"}',
        )
        assert interaction.request_method == "GET"
        assert interaction.request_url == "https://api.example.com"
        assert interaction.response_body == '{"status": "ok"}'
        assert interaction.response_status == 200

    def test_with_custom_status(self):
        interaction = create_interaction(
            "POST",
            "https://api.example.com",
            '{"error": "not found"}',
            response_status=404,
        )
        assert interaction.response_status == 404

    def test_with_request_body(self):
        interaction = create_interaction(
            "POST",
            "https://api.example.com",
            '{"id": 1}',
            request_body='{"name": "test"}',
        )
        assert interaction.request_body == '{"name": "test"}'

    def test_with_headers(self):
        interaction = create_interaction(
            "GET",
            "https://api.example.com",
            "{}",
            request_headers={"Authorization": "Bearer token"},
            response_headers={"X-Custom": "value"},
        )
        assert interaction.request_headers["Authorization"] == "Bearer token"
        assert interaction.response_headers["X-Custom"] == "value"


class TestRecordHttpContextManager:
    """Tests for record_http context manager."""

    def test_creates_new_cassette(self):
        with (
            tempfile.TemporaryDirectory() as tmpdir,
            record_http(
                "new_test",
                cassette_dir=Path(tmpdir),
            ) as recorder,
        ):
            assert recorder.cassette.name == "new_test"

    def test_loads_existing_cassette(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a cassette
            cassette = HTTPCassette(name="existing")
            cassette.add(
                HTTPInteraction(
                    request_method="GET",
                    request_url="https://example.com",
                    response_body="{}",
                )
            )
            cassette.save(Path(tmpdir) / "existing.json")

            # Load it via context manager
            with record_http(
                "existing",
                cassette_dir=Path(tmpdir),
            ) as recorder:
                assert len(recorder.cassette.interactions) == 1


class TestLoadCassette:
    """Tests for load_cassette function."""

    def test_load_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create cassette file
            cassette = HTTPCassette(name="test")
            cassette.add(
                HTTPInteraction(
                    request_method="GET",
                    request_url="https://example.com",
                    response_body="{}",
                )
            )
            cassette.save(Path(tmpdir) / "test.json")

            # Load it
            loaded = load_cassette("test", cassette_dir=Path(tmpdir))
            assert loaded.name == "test"

    def test_load_nonexistent_raises(self):
        with tempfile.TemporaryDirectory() as tmpdir, pytest.raises(FileNotFoundError):
            load_cassette("nonexistent", cassette_dir=Path(tmpdir))
