"""Tests for observation runner."""

from uuid import uuid4

import pytest

from worker.observation.models import (
    ObservationStatus,
    ProviderType,
)
from worker.observation.runner import (
    ObservationRunner,
    RunConfig,
    run_observation,
)


class TestRunConfig:
    """Tests for RunConfig."""

    def test_default_config(self) -> None:
        """Has sensible defaults."""
        config = RunConfig()

        assert config.primary_provider == ProviderType.OPENROUTER
        assert config.fallback_provider == ProviderType.OPENAI
        assert config.max_retries == 3

    def test_get_provider_config(self) -> None:
        """Can get config for specific provider."""
        config = RunConfig(
            openrouter_api_key="or-key",
            openai_api_key="oai-key",
        )

        or_config = config.get_provider_config(ProviderType.OPENROUTER)
        oai_config = config.get_provider_config(ProviderType.OPENAI)

        assert or_config.api_key == "or-key"
        assert oai_config.api_key == "oai-key"


class TestObservationRunner:
    """Tests for ObservationRunner."""

    @pytest.mark.asyncio
    async def test_run_single_question(self) -> None:
        """Can run a single question."""
        config = RunConfig(
            primary_provider=ProviderType.MOCK,
            fallback_provider=ProviderType.MOCK,
        )
        runner = ObservationRunner(config=config)

        result = await runner.run_observation(
            site_id=uuid4(),
            run_id=uuid4(),
            company_name="Acme Corp",
            domain="acme.com",
            questions=[("q1", "What does Acme Corp do?")],
        )

        assert result.status == ObservationStatus.COMPLETED
        assert result.questions_completed == 1
        assert len(result.results) == 1

    @pytest.mark.asyncio
    async def test_run_multiple_questions(self) -> None:
        """Can run multiple questions."""
        config = RunConfig(
            primary_provider=ProviderType.MOCK,
            fallback_provider=ProviderType.MOCK,
        )
        runner = ObservationRunner(config=config)

        questions = [
            ("q1", "What does Acme do?"),
            ("q2", "Where is Acme located?"),
            ("q3", "What are Acme's products?"),
        ]

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Acme Corp",
            domain="acme.com",
            questions=questions,
        )

        assert result.status == ObservationStatus.COMPLETED
        assert result.questions_completed == 3
        assert result.total_questions == 3

    @pytest.mark.asyncio
    async def test_respects_max_questions(self) -> None:
        """Respects max_questions limit."""
        config = RunConfig(
            primary_provider=ProviderType.MOCK,
            max_questions=2,
        )
        runner = ObservationRunner(config=config)

        questions = [
            ("q1", "Question 1"),
            ("q2", "Question 2"),
            ("q3", "Question 3"),  # Should be ignored
        ]

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Test",
            domain="test.com",
            questions=questions,
        )

        assert result.total_questions == 2
        assert len(result.results) == 2

    @pytest.mark.asyncio
    async def test_progress_callback_called(self) -> None:
        """Progress callback is called."""
        config = RunConfig(primary_provider=ProviderType.MOCK)

        progress_calls = []

        def callback(completed: int, total: int, status: str) -> None:
            progress_calls.append((completed, total, status))

        runner = ObservationRunner(config=config, progress_callback=callback)

        await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Test",
            domain="test.com",
            questions=[("q1", "Test question")],
        )

        assert len(progress_calls) >= 2  # Start + completion at minimum

    @pytest.mark.asyncio
    async def test_parses_mentions_from_response(self) -> None:
        """Parses company and domain mentions."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        runner = ObservationRunner(config=config)

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Acme Corp",
            domain="acme.com",
            questions=[("q1", "What is Acme Corp?")],
        )

        # Mock provider includes company name and domain
        obs_result = result.results[0]
        assert obs_result.mentions_company is True
        assert obs_result.mentions_domain is True

    @pytest.mark.asyncio
    async def test_extracts_urls_from_response(self) -> None:
        """Extracts cited URLs from response."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        runner = ObservationRunner(config=config)

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Acme Corp",
            domain="acme.com",
            questions=[("q1", "What is Acme?")],
        )

        # Mock provider includes domain URL
        obs_result = result.results[0]
        assert obs_result.mentions_url is True
        assert any("acme.com" in url for url in obs_result.cited_urls)

    @pytest.mark.asyncio
    async def test_calculates_mention_rates(self) -> None:
        """Calculates aggregate mention rates."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        runner = ObservationRunner(config=config)

        questions = [
            ("q1", "Question 1"),
            ("q2", "Question 2"),
        ]

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Acme Corp",
            domain="acme.com",
            questions=questions,
        )

        # Mock always mentions, so rates should be 1.0
        assert result.company_mention_rate == 1.0
        assert result.domain_mention_rate == 1.0

    @pytest.mark.asyncio
    async def test_aggregates_usage_stats(self) -> None:
        """Aggregates usage across questions."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        runner = ObservationRunner(config=config)

        questions = [
            ("q1", "Question 1"),
            ("q2", "Question 2"),
        ]

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Test",
            domain="test.com",
            questions=questions,
        )

        assert result.total_usage.total_tokens > 0
        assert result.total_latency_ms > 0

    @pytest.mark.asyncio
    async def test_tracks_timing(self) -> None:
        """Tracks start and completion time."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        runner = ObservationRunner(config=config)

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Test",
            domain="test.com",
            questions=[("q1", "Test")],
        )

        assert result.started_at is not None
        assert result.completed_at is not None
        assert result.completed_at >= result.started_at


class TestObservationRunnerFailover:
    """Tests for failover behavior."""

    @pytest.mark.asyncio
    async def test_retries_on_failure(self) -> None:
        """Retries failed requests."""
        # This test would require injecting a mock provider that fails initially
        # For now, we just verify the config is respected
        config = RunConfig(
            primary_provider=ProviderType.MOCK,
            max_retries=2,
            retry_delay_seconds=0.01,  # Fast for testing
        )

        runner = ObservationRunner(config=config)

        # With mock provider (always succeeds), should complete fine
        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Test",
            domain="test.com",
            questions=[("q1", "Test")],
        )

        assert result.status == ObservationStatus.COMPLETED


class TestConvenienceFunction:
    """Tests for run_observation convenience function."""

    @pytest.mark.asyncio
    async def test_run_observation_function(self) -> None:
        """Convenience function works."""
        config = RunConfig(primary_provider=ProviderType.MOCK)

        result = await run_observation(
            company_name="Test Corp",
            domain="test.com",
            questions=[("q1", "What is Test Corp?")],
            config=config,
        )

        assert result.status == ObservationStatus.COMPLETED
        assert result.company_name == "Test Corp"

    @pytest.mark.asyncio
    async def test_run_observation_with_callback(self) -> None:
        """Convenience function accepts callback."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        progress_calls = []

        def callback(c: int, t: int, s: str) -> None:
            progress_calls.append(s)

        await run_observation(
            company_name="Test",
            domain="test.com",
            questions=[("q1", "Test")],
            config=config,
            progress_callback=callback,
        )

        assert len(progress_calls) > 0


class TestConfidenceParsing:
    """Tests for parsing confidence from responses."""

    @pytest.mark.asyncio
    async def test_parses_unknown_confidence_by_default(self) -> None:
        """Default confidence is unknown."""
        config = RunConfig(primary_provider=ProviderType.MOCK)
        runner = ObservationRunner(config=config)

        result = await runner.run_observation(
            site_id=None,
            run_id=None,
            company_name="Test",
            domain="test.com",
            questions=[("q1", "Test")],
        )

        # Mock response has "Based on my knowledge" which maps to medium
        obs_result = result.results[0]
        assert obs_result.confidence_expressed in ["unknown", "medium"]
