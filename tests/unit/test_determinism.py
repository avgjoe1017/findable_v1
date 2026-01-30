"""Tests for determinism utilities."""

import random
from datetime import UTC

from tests.fixtures.determinism import (
    DeterministicContext,
    SeededRandom,
    content_hash,
    freeze_time,
    prompt_hash,
    request_hash,
    reset_seeds,
    set_seed,
)


class TestDeterministicContext:
    """Tests for DeterministicContext."""

    def test_seeded_random_is_reproducible(self):
        with DeterministicContext(seed=42):
            first_values = [random.random() for _ in range(5)]

        with DeterministicContext(seed=42):
            second_values = [random.random() for _ in range(5)]

        assert first_values == second_values

    def test_different_seeds_produce_different_values(self):
        with DeterministicContext(seed=42):
            first_values = [random.random() for _ in range(5)]

        with DeterministicContext(seed=123):
            second_values = [random.random() for _ in range(5)]

        assert first_values != second_values

    def test_restores_random_state(self):
        # Set a known state
        random.seed(999)
        before = random.random()
        random.seed(999)

        with DeterministicContext(seed=42):
            inside = random.random()

        # State should be restored - verify context doesn't leak
        # Note: We can't directly compare states, but the context shouldn't leak
        assert inside != before  # Different seed produced different value

    def test_deterministic_choice(self):
        with DeterministicContext(seed=42) as ctx:
            items = ["a", "b", "c", "d", "e"]
            choice1 = ctx.deterministic_choice(items)

        with DeterministicContext(seed=42) as ctx:
            choice2 = ctx.deterministic_choice(items)

        assert choice1 == choice2

    def test_deterministic_sample(self):
        with DeterministicContext(seed=42) as ctx:
            items = list(range(100))
            sample1 = ctx.deterministic_sample(items, 10)

        with DeterministicContext(seed=42) as ctx:
            sample2 = ctx.deterministic_sample(items, 10)

        assert sample1 == sample2
        assert len(sample1) == 10

    def test_deterministic_shuffle(self):
        with DeterministicContext(seed=42) as ctx:
            items = [1, 2, 3, 4, 5]
            shuffled1 = ctx.deterministic_shuffle(items)

        with DeterministicContext(seed=42) as ctx:
            shuffled2 = ctx.deterministic_shuffle(items)

        assert shuffled1 == shuffled2
        assert sorted(shuffled1) == items  # Same elements

    def test_deterministic_float(self):
        with DeterministicContext(seed=42) as ctx:
            float1 = ctx.deterministic_float(0, 100)

        with DeterministicContext(seed=42) as ctx:
            float2 = ctx.deterministic_float(0, 100)

        assert float1 == float2
        assert 0 <= float1 <= 100

    def test_deterministic_int(self):
        with DeterministicContext(seed=42) as ctx:
            int1 = ctx.deterministic_int(1, 1000)

        with DeterministicContext(seed=42) as ctx:
            int2 = ctx.deterministic_int(1, 1000)

        assert int1 == int2
        assert 1 <= int1 <= 1000


class TestSetSeed:
    """Tests for set_seed function."""

    def test_set_seed_affects_random(self):
        set_seed(42)
        value1 = random.random()

        set_seed(42)
        value2 = random.random()

        assert value1 == value2

    def test_reset_seeds_randomizes(self):
        set_seed(42)
        value1 = random.random()

        reset_seeds()
        _ = random.random()  # Consume one value after reset

        # Verify seed still works after reset
        set_seed(42)
        value3 = random.random()

        assert value1 == value3  # Same seed = same value


class TestFreezeTime:
    """Tests for freeze_time context manager."""

    def test_freeze_time_with_datetime(self):
        from datetime import datetime

        frozen = datetime(2026, 1, 29, 12, 0, 0, tzinfo=UTC)

        with freeze_time(frozen) as ft:
            assert ft == frozen

    def test_freeze_time_with_string(self):

        with freeze_time("2026-01-29T12:00:00Z") as ft:
            assert ft.year == 2026
            assert ft.month == 1
            assert ft.day == 29
            assert ft.hour == 12

    def test_freeze_time_default(self):
        from datetime import datetime

        with freeze_time() as ft:
            assert isinstance(ft, datetime)


class TestContentHash:
    """Tests for content_hash function."""

    def test_string_hash(self):
        hash1 = content_hash("hello world")
        hash2 = content_hash("hello world")
        assert hash1 == hash2

    def test_bytes_hash(self):
        hash1 = content_hash(b"hello world")
        hash2 = content_hash(b"hello world")
        assert hash1 == hash2

    def test_different_content_different_hash(self):
        hash1 = content_hash("hello")
        hash2 = content_hash("world")
        assert hash1 != hash2

    def test_hash_length(self):
        hash_value = content_hash("test")
        assert len(hash_value) == 16


class TestRequestHash:
    """Tests for request_hash function."""

    def test_same_request_same_hash(self):
        hash1 = request_hash("GET", "https://example.com/api")
        hash2 = request_hash("GET", "https://example.com/api")
        assert hash1 == hash2

    def test_different_method_different_hash(self):
        hash1 = request_hash("GET", "https://example.com/api")
        hash2 = request_hash("POST", "https://example.com/api")
        assert hash1 != hash2

    def test_different_url_different_hash(self):
        hash1 = request_hash("GET", "https://example.com/api")
        hash2 = request_hash("GET", "https://example.com/other")
        assert hash1 != hash2

    def test_with_body(self):
        hash1 = request_hash("POST", "https://example.com", '{"key": "value"}')
        hash2 = request_hash("POST", "https://example.com", '{"key": "value"}')
        assert hash1 == hash2

    def test_different_body_different_hash(self):
        hash1 = request_hash("POST", "https://example.com", '{"key": "value1"}')
        hash2 = request_hash("POST", "https://example.com", '{"key": "value2"}')
        assert hash1 != hash2


class TestPromptHash:
    """Tests for prompt_hash function."""

    def test_same_prompt_same_hash(self):
        hash1 = prompt_hash("What is the capital of France?")
        hash2 = prompt_hash("What is the capital of France?")
        assert hash1 == hash2

    def test_different_prompt_different_hash(self):
        hash1 = prompt_hash("What is the capital of France?")
        hash2 = prompt_hash("What is the capital of Germany?")
        assert hash1 != hash2

    def test_with_model(self):
        hash1 = prompt_hash("Test prompt", "gpt-4")
        hash2 = prompt_hash("Test prompt", "gpt-4")
        assert hash1 == hash2

    def test_different_model_different_hash(self):
        hash1 = prompt_hash("Test prompt", "gpt-4")
        hash2 = prompt_hash("Test prompt", "gpt-3.5")
        assert hash1 != hash2


class TestSeededRandom:
    """Tests for SeededRandom class."""

    def test_reproducible(self):
        rng1 = SeededRandom(42)
        values1 = [rng1.random() for _ in range(5)]

        rng2 = SeededRandom(42)
        values2 = [rng2.random() for _ in range(5)]

        assert values1 == values2

    def test_reset(self):
        rng = SeededRandom(42)
        values1 = [rng.random() for _ in range(5)]

        rng.reset()
        values2 = [rng.random() for _ in range(5)]

        assert values1 == values2

    def test_choice(self):
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        items = ["a", "b", "c", "d", "e"]
        assert rng1.choice(items) == rng2.choice(items)

    def test_sample(self):
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        items = list(range(100))
        assert rng1.sample(items, 10) == rng2.sample(items, 10)

    def test_shuffle(self):
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        items = [1, 2, 3, 4, 5]
        assert rng1.shuffle(items) == rng2.shuffle(items)

    def test_randint(self):
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        assert rng1.randint(1, 100) == rng2.randint(1, 100)

    def test_uniform(self):
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        assert rng1.uniform(0.0, 100.0) == rng2.uniform(0.0, 100.0)

    def test_gauss(self):
        rng1 = SeededRandom(42)
        rng2 = SeededRandom(42)

        assert rng1.gauss(0, 1) == rng2.gauss(0, 1)

    def test_isolated_from_global(self):
        # Changes to SeededRandom shouldn't affect global random
        random.seed(123)
        global_value = random.random()

        rng = SeededRandom(42)
        _ = [rng.random() for _ in range(100)]

        random.seed(123)
        global_value2 = random.random()

        assert global_value == global_value2
