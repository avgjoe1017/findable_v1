"""Tests for observation providers."""

from uuid import uuid4

import pytest

from worker.observation.models import (
    ObservationRequest,
    ObservationResponse,
    ObservationResult,
    ObservationRun,
    ObservationStatus,
    ProviderError,
    ProviderType,
    UsageStats,
)
from worker.observation.providers import (
    MockProvider,
    OpenAIProvider,
    OpenRouterProvider,
    ProviderConfig,
    get_provider,
)


class TestUsageStats:
    """Tests for UsageStats dataclass."""

    def test_create_usage_stats(self) -> None:
        """Can create usage stats."""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
        )

        assert usage.prompt_tokens == 100
        assert usage.total_tokens == 150

    def test_add_usage_stats(self) -> None:
        """Can add usage stats together."""
        a = UsageStats(prompt_tokens=100, completion_tokens=50)
        b = UsageStats(prompt_tokens=200, completion_tokens=100)

        combined = a.add(b)

        assert combined.prompt_tokens == 300
        assert combined.completion_tokens == 150

    def test_to_dict(self) -> None:
        """Converts to dict."""
        usage = UsageStats(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.00123456,
        )

        d = usage.to_dict()

        assert d["prompt_tokens"] == 100
        assert d["estimated_cost_usd"] == 0.001235  # Rounded


class TestProviderError:
    """Tests for ProviderError dataclass."""

    def test_create_error(self) -> None:
        """Can create a provider error."""
        error = ProviderError(
            provider=ProviderType.OPENROUTER,
            error_type="api_error",
            message="Rate limit exceeded",
            retryable=True,
        )

        assert error.provider == ProviderType.OPENROUTER
        assert error.retryable is True

    def test_to_dict(self) -> None:
        """Converts to dict."""
        error = ProviderError(
            provider=ProviderType.OPENAI,
            error_type="timeout",
            message="Request timed out",
        )

        d = error.to_dict()

        assert d["provider"] == "openai"
        assert "timestamp" in d


class TestObservationRequest:
    """Tests for ObservationRequest dataclass."""

    def test_create_request(self) -> None:
        """Can create a request."""
        request = ObservationRequest(
            question_id="q1",
            question_text="What does Acme do?",
            company_name="Acme Corp",
            domain="acme.com",
        )

        assert request.question_id == "q1"
        assert request.company_name == "Acme Corp"

    def test_to_prompt(self) -> None:
        """Generates a prompt."""
        request = ObservationRequest(
            question_id="q1",
            question_text="What does Acme do?",
            company_name="Acme Corp",
            domain="acme.com",
        )

        prompt = request.to_prompt()

        assert "Acme Corp" in prompt
        assert "What does Acme do?" in prompt

    def test_to_prompt_with_context(self) -> None:
        """Includes context in prompt."""
        request = ObservationRequest(
            question_id="q1",
            question_text="What does Acme do?",
            company_name="Acme Corp",
            domain="acme.com",
            context="Please be concise.",
        )

        prompt = request.to_prompt()

        assert "Please be concise" in prompt

    def test_default_model(self) -> None:
        """Has default model."""
        request = ObservationRequest()

        assert request.model == "openai/gpt-4o-mini"


class TestObservationResponse:
    """Tests for ObservationResponse dataclass."""

    def test_create_response(self) -> None:
        """Can create a response."""
        request_id = uuid4()
        response = ObservationResponse(
            request_id=request_id,
            provider=ProviderType.OPENROUTER,
            model="gpt-4o-mini",
            content="Acme Corp is a technology company.",
            success=True,
        )

        assert response.request_id == request_id
        assert response.success is True

    def test_to_dict_truncates_content(self) -> None:
        """Long content is truncated in dict."""
        response = ObservationResponse(
            request_id=uuid4(),
            provider=ProviderType.OPENROUTER,
            model="gpt-4o",
            content="x" * 1000,
            success=True,
        )

        d = response.to_dict()

        assert len(d["content"]) < 1000
        assert d["content"].endswith("...")


class TestObservationResult:
    """Tests for ObservationResult dataclass."""

    def test_create_result(self) -> None:
        """Can create a result."""
        result = ObservationResult(
            question_id="q1",
            question_text="What does Acme do?",
            company_name="Acme Corp",
            domain="acme.com",
            mentions_company=True,
            mentions_domain=True,
        )

        assert result.mentions_company is True
        assert result.mentions_domain is True

    def test_to_dict(self) -> None:
        """Converts to dict."""
        result = ObservationResult(
            question_id="q1",
            question_text="Test question",
            company_name="Test Co",
            domain="test.com",
            cited_urls=["https://test.com/page"],
        )

        d = result.to_dict()

        assert d["question_id"] == "q1"
        assert "https://test.com/page" in d["cited_urls"]


class TestObservationRun:
    """Tests for ObservationRun dataclass."""

    def test_create_run(self) -> None:
        """Can create a run."""
        run = ObservationRun(
            company_name="Acme Corp",
            domain="acme.com",
            total_questions=10,
        )

        assert run.company_name == "Acme Corp"
        assert run.status == ObservationStatus.PENDING

    def test_add_result_updates_counts(self) -> None:
        """Adding results updates counts."""
        run = ObservationRun(
            company_name="Acme Corp",
            domain="acme.com",
            total_questions=2,
        )

        result = ObservationResult(
            question_id="q1",
            question_text="Test",
            company_name="Acme Corp",
            domain="acme.com",
            response=ObservationResponse(
                request_id=uuid4(),
                provider=ProviderType.MOCK,
                model="mock",
                content="Test response",
                success=True,
            ),
            mentions_company=True,
        )

        run.add_result(result)

        assert run.questions_completed == 1
        assert run.company_mention_rate == 1.0

    def test_mention_rate_calculation(self) -> None:
        """Mention rates are calculated correctly."""
        run = ObservationRun(
            company_name="Test Co",
            domain="test.com",
            total_questions=4,
        )

        # Add 4 results: 2 mention company, 1 mentions domain
        for i in range(4):
            result = ObservationResult(
                question_id=f"q{i}",
                question_text="Test",
                company_name="Test Co",
                domain="test.com",
                response=ObservationResponse(
                    request_id=uuid4(),
                    provider=ProviderType.MOCK,
                    model="mock",
                    content="Response",
                    success=True,
                ),
                mentions_company=(i < 2),  # First 2
                mentions_domain=(i == 0),  # Only first
            )
            run.add_result(result)

        assert run.company_mention_rate == 0.5  # 2/4
        assert run.domain_mention_rate == 0.25  # 1/4


class TestProviderConfig:
    """Tests for ProviderConfig."""

    def test_default_config(self) -> None:
        """Has sensible defaults."""
        config = ProviderConfig()

        assert config.timeout_seconds == 30.0
        assert config.max_retries == 3

    def test_custom_config(self) -> None:
        """Can customize config."""
        config = ProviderConfig(
            api_key="test-key",
            timeout_seconds=60.0,
        )

        assert config.api_key == "test-key"
        assert config.timeout_seconds == 60.0


class TestMockProvider:
    """Tests for MockProvider."""

    @pytest.mark.asyncio
    async def test_observe_returns_response(self) -> None:
        """Returns a mock response."""
        provider = MockProvider()
        request = ObservationRequest(
            question_id="q1",
            question_text="What does Acme do?",
            company_name="Acme Corp",
            domain="acme.com",
        )

        response = await provider.observe(request)

        assert response.success is True
        assert "Acme Corp" in response.content
        assert "acme.com" in response.content

    @pytest.mark.asyncio
    async def test_set_custom_response(self) -> None:
        """Can set custom responses."""
        provider = MockProvider()
        request_id = uuid4()
        request = ObservationRequest(
            id=request_id,
            question_id="q1",
            question_text="Test",
            company_name="Test",
            domain="test.com",
        )

        provider.set_response(request_id, "Custom response content")
        response = await provider.observe(request)

        assert response.content == "Custom response content"

    @pytest.mark.asyncio
    async def test_failure_mode(self) -> None:
        """Can simulate failures."""
        provider = MockProvider()
        provider.set_failure_mode(should_fail=True, fail_count=2)

        request = ObservationRequest(
            question_id="q1",
            question_text="Test",
            company_name="Test",
            domain="test.com",
        )

        # First two should fail
        r1 = await provider.observe(request)
        r2 = await provider.observe(request)
        r3 = await provider.observe(request)

        assert r1.success is False
        assert r2.success is False
        assert r3.success is True

    @pytest.mark.asyncio
    async def test_tracks_calls(self) -> None:
        """Tracks all calls made."""
        provider = MockProvider()
        request = ObservationRequest(
            question_id="q1",
            question_text="Test",
            company_name="Test",
            domain="test.com",
        )

        await provider.observe(request)
        await provider.observe(request)

        assert len(provider.calls) == 2

    @pytest.mark.asyncio
    async def test_health_check_always_passes(self) -> None:
        """Health check always returns True."""
        provider = MockProvider()

        result = await provider.health_check()

        assert result is True

    @pytest.mark.asyncio
    async def test_observe_batch(self) -> None:
        """Can process batch requests."""
        provider = MockProvider()
        requests = [
            ObservationRequest(
                question_id=f"q{i}",
                question_text=f"Question {i}",
                company_name="Test",
                domain="test.com",
            )
            for i in range(3)
        ]

        responses = []
        async for response in provider.observe_batch(requests):
            responses.append(response)

        assert len(responses) == 3
        assert all(r.success for r in responses)


class TestGetProvider:
    """Tests for get_provider factory function."""

    def test_get_mock_provider(self) -> None:
        """Can get mock provider."""
        provider = get_provider(ProviderType.MOCK)

        assert isinstance(provider, MockProvider)

    def test_get_openrouter_provider(self) -> None:
        """Can get OpenRouter provider."""
        config = ProviderConfig(api_key="test-key")
        provider = get_provider(ProviderType.OPENROUTER, config)

        assert isinstance(provider, OpenRouterProvider)

    def test_get_openai_provider(self) -> None:
        """Can get OpenAI provider."""
        config = ProviderConfig(api_key="test-key")
        provider = get_provider(ProviderType.OPENAI, config)

        assert isinstance(provider, OpenAIProvider)

    def test_invalid_provider_raises(self) -> None:
        """Invalid provider type raises."""
        with pytest.raises(ValueError):
            get_provider(ProviderType.ANTHROPIC)  # Not implemented yet


class TestCostEstimation:
    """Tests for cost estimation."""

    @pytest.mark.asyncio
    async def test_mock_has_cost_estimate(self) -> None:
        """Mock provider includes cost estimate."""
        provider = MockProvider()
        request = ObservationRequest(
            question_id="q1",
            question_text="Test question",
            company_name="Test",
            domain="test.com",
        )

        response = await provider.observe(request)

        assert response.usage.estimated_cost_usd > 0
