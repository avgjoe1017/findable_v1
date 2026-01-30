"""Observation providers - unified interface for AI model queries."""

import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID

from worker.observation.models import (
    ObservationRequest,
    ObservationResponse,
    ProviderError,
    ProviderType,
    UsageStats,
)


@dataclass
class ProviderConfig:
    """Configuration for an observation provider."""

    api_key: str = ""
    base_url: str = ""
    timeout_seconds: float = 30.0
    max_retries: int = 3
    retry_delay_seconds: float = 1.0

    # Rate limiting
    requests_per_minute: int = 60
    tokens_per_minute: int = 100000


class ObservationProvider(ABC):
    """Abstract base class for observation providers."""

    provider_type: ProviderType

    def __init__(self, config: ProviderConfig):
        self.config = config

    @abstractmethod
    async def observe(self, request: ObservationRequest) -> ObservationResponse:
        """Run a single observation request."""
        ...

    @abstractmethod
    async def observe_batch(
        self,
        requests: list[ObservationRequest],
    ) -> AsyncIterator[ObservationResponse]:
        """Run multiple observation requests."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available."""
        ...

    def _estimate_cost(self, model: str, usage: UsageStats) -> float:
        """Estimate cost based on model and usage."""
        # Approximate pricing per 1M tokens (as of 2024)
        pricing = {
            # OpenAI
            "gpt-4o": (2.5, 10.0),  # input, output per 1M
            "gpt-4o-mini": (0.15, 0.6),
            "gpt-4-turbo": (10.0, 30.0),
            "gpt-3.5-turbo": (0.5, 1.5),
            # Anthropic
            "claude-3-opus": (15.0, 75.0),
            "claude-3-sonnet": (3.0, 15.0),
            "claude-3-haiku": (0.25, 1.25),
            # OpenRouter format
            "openai/gpt-4o": (2.5, 10.0),
            "openai/gpt-4o-mini": (0.15, 0.6),
            "anthropic/claude-3-opus": (15.0, 75.0),
            "anthropic/claude-3-sonnet": (3.0, 15.0),
            "anthropic/claude-3-haiku": (0.25, 1.25),
        }

        # Default pricing if model not found
        input_price, output_price = pricing.get(model, (1.0, 3.0))

        cost = (usage.prompt_tokens / 1_000_000) * input_price + (
            usage.completion_tokens / 1_000_000
        ) * output_price
        return cost


class OpenRouterProvider(ObservationProvider):
    """OpenRouter aggregator provider - primary observation provider."""

    provider_type = ProviderType.OPENROUTER

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        if not config.base_url:
            config.base_url = "https://openrouter.ai/api/v1"

    async def observe(self, request: ObservationRequest) -> ObservationResponse:
        """Run observation via OpenRouter."""
        import httpx

        start_time = time.perf_counter()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://findable.app",
            "X-Title": "Findable Score Analyzer",
        }

        payload = {
            "model": request.model,
            "messages": [{"role": "user", "content": request.to_prompt()}],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code != 200:
                    error_body = response.text
                    return ObservationResponse(
                        request_id=request.id,
                        provider=self.provider_type,
                        model=request.model,
                        content="",
                        success=False,
                        latency_ms=latency_ms,
                        error=ProviderError(
                            provider=self.provider_type,
                            error_type="api_error",
                            message=f"HTTP {response.status_code}: {error_body}",
                            retryable=response.status_code >= 500,
                        ),
                    )

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage_data = data.get("usage", {})

                usage = UsageStats(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                )
                usage.estimated_cost_usd = self._estimate_cost(request.model, usage)

                return ObservationResponse(
                    request_id=request.id,
                    provider=self.provider_type,
                    model=request.model,
                    content=content,
                    raw_response=data,
                    usage=usage,
                    latency_ms=latency_ms,
                    success=True,
                )

        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ObservationResponse(
                request_id=request.id,
                provider=self.provider_type,
                model=request.model,
                content="",
                success=False,
                latency_ms=latency_ms,
                error=ProviderError(
                    provider=self.provider_type,
                    error_type="timeout",
                    message=f"Request timed out after {self.config.timeout_seconds}s",
                    retryable=True,
                ),
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ObservationResponse(
                request_id=request.id,
                provider=self.provider_type,
                model=request.model,
                content="",
                success=False,
                latency_ms=latency_ms,
                error=ProviderError(
                    provider=self.provider_type,
                    error_type="exception",
                    message=str(e),
                    retryable=True,
                ),
            )

    async def observe_batch(  # type: ignore[override]
        self,
        requests: list[ObservationRequest],
    ) -> AsyncIterator[ObservationResponse]:
        """Run multiple observations sequentially."""
        import asyncio

        for request in requests:
            response = await self.observe(request)
            yield response

            # Rate limiting pause
            if len(requests) > 1:
                await asyncio.sleep(60 / self.config.requests_per_minute)

    async def health_check(self) -> bool:
        """Check if OpenRouter is available."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.config.base_url}/models",
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
                is_healthy: bool = response.status_code == 200
                return is_healthy
        except Exception:
            return False


class OpenAIProvider(ObservationProvider):
    """Direct OpenAI provider - fallback."""

    provider_type = ProviderType.OPENAI

    def __init__(self, config: ProviderConfig):
        super().__init__(config)
        if not config.base_url:
            config.base_url = "https://api.openai.com/v1"

    async def observe(self, request: ObservationRequest) -> ObservationResponse:
        """Run observation via OpenAI."""
        import httpx

        start_time = time.perf_counter()

        # Map OpenRouter model names to OpenAI
        model = request.model
        if model.startswith("openai/"):
            model = model.replace("openai/", "")

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": request.to_prompt()}],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.post(
                    f"{self.config.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )

                latency_ms = (time.perf_counter() - start_time) * 1000

                if response.status_code != 200:
                    error_body = response.text
                    return ObservationResponse(
                        request_id=request.id,
                        provider=self.provider_type,
                        model=model,
                        content="",
                        success=False,
                        latency_ms=latency_ms,
                        error=ProviderError(
                            provider=self.provider_type,
                            error_type="api_error",
                            message=f"HTTP {response.status_code}: {error_body}",
                            retryable=response.status_code >= 500,
                        ),
                    )

                data = response.json()
                content = data["choices"][0]["message"]["content"]
                usage_data = data.get("usage", {})

                usage = UsageStats(
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    total_tokens=usage_data.get("total_tokens", 0),
                )
                usage.estimated_cost_usd = self._estimate_cost(model, usage)

                return ObservationResponse(
                    request_id=request.id,
                    provider=self.provider_type,
                    model=model,
                    content=content,
                    raw_response=data,
                    usage=usage,
                    latency_ms=latency_ms,
                    success=True,
                )

        except httpx.TimeoutException:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ObservationResponse(
                request_id=request.id,
                provider=self.provider_type,
                model=model,
                content="",
                success=False,
                latency_ms=latency_ms,
                error=ProviderError(
                    provider=self.provider_type,
                    error_type="timeout",
                    message=f"Request timed out after {self.config.timeout_seconds}s",
                    retryable=True,
                ),
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ObservationResponse(
                request_id=request.id,
                provider=self.provider_type,
                model=model,
                content="",
                success=False,
                latency_ms=latency_ms,
                error=ProviderError(
                    provider=self.provider_type,
                    error_type="exception",
                    message=str(e),
                    retryable=True,
                ),
            )

    async def observe_batch(  # type: ignore[override]
        self,
        requests: list[ObservationRequest],
    ) -> AsyncIterator[ObservationResponse]:
        """Run multiple observations sequentially."""
        import asyncio

        for request in requests:
            response = await self.observe(request)
            yield response

            # Rate limiting pause
            if len(requests) > 1:
                await asyncio.sleep(60 / self.config.requests_per_minute)

    async def health_check(self) -> bool:
        """Check if OpenAI is available."""
        import httpx

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(
                    f"{self.config.base_url}/models",
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
                is_healthy: bool = response.status_code == 200
                return is_healthy
        except Exception:
            return False


class MockProvider(ObservationProvider):
    """Mock provider for testing."""

    provider_type = ProviderType.MOCK

    def __init__(self, config: ProviderConfig | None = None):
        super().__init__(config or ProviderConfig())
        self.responses: dict[UUID, str] = {}
        self.should_fail: bool = False
        self.fail_count: int = 0
        self.calls: list[ObservationRequest] = []

    def set_response(self, request_id: UUID, content: str) -> None:
        """Set a specific response for a request ID."""
        self.responses[request_id] = content

    def set_failure_mode(self, should_fail: bool, fail_count: int = 1) -> None:
        """Configure failure behavior."""
        self.should_fail = should_fail
        self.fail_count = fail_count

    async def observe(self, request: ObservationRequest) -> ObservationResponse:
        """Return mock observation response."""
        self.calls.append(request)

        # Simulate failure if configured
        if self.should_fail and self.fail_count > 0:
            self.fail_count -= 1
            return ObservationResponse(
                request_id=request.id,
                provider=self.provider_type,
                model=request.model,
                content="",
                success=False,
                latency_ms=50.0,
                error=ProviderError(
                    provider=self.provider_type,
                    error_type="mock_failure",
                    message="Simulated failure",
                    retryable=True,
                ),
            )

        # Use preset response or generate one
        content = self.responses.get(request.id)
        if content is None:
            content = self._generate_mock_response(request)

        usage = UsageStats(
            prompt_tokens=len(request.to_prompt().split()) * 4,
            completion_tokens=len(content.split()) * 4,
            total_tokens=0,
        )
        usage.total_tokens = usage.prompt_tokens + usage.completion_tokens
        usage.estimated_cost_usd = 0.001

        return ObservationResponse(
            request_id=request.id,
            provider=self.provider_type,
            model=request.model,
            content=content,
            usage=usage,
            latency_ms=50.0,
            success=True,
        )

    def _generate_mock_response(self, request: ObservationRequest) -> str:
        """Generate a realistic mock response."""
        company = request.company_name
        domain = request.domain

        return f"""Based on my knowledge, {company} is a company that operates in its industry.

You can find more information about them at https://{domain}/ where they provide details about their products and services.

{company} offers various solutions to help businesses achieve their goals. Their website at {domain} contains comprehensive information about their offerings, pricing, and contact details.

I would recommend visiting {domain} directly for the most accurate and up-to-date information about {company}."""

    async def observe_batch(  # type: ignore[override]
        self,
        requests: list[ObservationRequest],
    ) -> AsyncIterator[ObservationResponse]:
        """Run multiple mock observations."""
        for request in requests:
            response = await self.observe(request)
            yield response

    async def health_check(self) -> bool:
        """Mock provider is always healthy."""
        return True


def get_provider(
    provider_type: ProviderType,
    config: ProviderConfig | None = None,
) -> ObservationProvider:
    """Factory function to get an observation provider."""
    if config is None:
        config = ProviderConfig()

    providers = {
        ProviderType.OPENROUTER: OpenRouterProvider,
        ProviderType.OPENAI: OpenAIProvider,
        ProviderType.MOCK: MockProvider,
    }

    provider_class = providers.get(provider_type)
    if provider_class is None:
        raise ValueError(f"Unknown provider type: {provider_type}")

    result: ObservationProvider = provider_class(config)
    return result
