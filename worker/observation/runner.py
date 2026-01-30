"""Observation runner with retries and failover."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from worker.observation.models import (
    ObservationRequest,
    ObservationResult,
    ObservationRun,
    ObservationStatus,
    ProviderError,
    ProviderType,
)
from worker.observation.providers import (
    ObservationProvider,
    ProviderConfig,
    get_provider,
)


@dataclass
class RunConfig:
    """Configuration for an observation run."""

    # Provider settings
    primary_provider: ProviderType = ProviderType.OPENROUTER
    fallback_provider: ProviderType = ProviderType.OPENAI
    model: str = "openai/gpt-4o-mini"

    # API keys (loaded from env if not provided)
    openrouter_api_key: str = ""
    openai_api_key: str = ""

    # Retry settings
    max_retries: int = 3
    retry_delay_seconds: float = 1.0
    retry_backoff_multiplier: float = 2.0

    # Rate limiting
    requests_per_minute: int = 30
    concurrent_requests: int = 3

    # Timeouts
    request_timeout_seconds: float = 30.0
    total_timeout_seconds: float = 600.0  # 10 minutes max

    # Limits
    max_questions: int = 50
    max_tokens_per_request: int = 1024

    def get_provider_config(self, provider_type: ProviderType) -> ProviderConfig:
        """Get config for a specific provider."""
        api_key = ""
        if provider_type == ProviderType.OPENROUTER:
            api_key = self.openrouter_api_key
        elif provider_type == ProviderType.OPENAI:
            api_key = self.openai_api_key

        return ProviderConfig(
            api_key=api_key,
            timeout_seconds=self.request_timeout_seconds,
            max_retries=self.max_retries,
            retry_delay_seconds=self.retry_delay_seconds,
            requests_per_minute=self.requests_per_minute,
        )


# Progress callback type
ProgressCallback = Callable[[int, int, str], None]


class ObservationRunner:
    """Runs observations with retries, failover, and progress tracking."""

    def __init__(
        self,
        config: RunConfig | None = None,
        progress_callback: ProgressCallback | None = None,
    ):
        self.config = config or RunConfig()
        self.progress_callback = progress_callback

        # Initialize providers
        self._providers: dict[ProviderType, ObservationProvider] = {}

    def _get_provider(self, provider_type: ProviderType) -> ObservationProvider:
        """Get or create a provider instance."""
        if provider_type not in self._providers:
            config = self.config.get_provider_config(provider_type)
            self._providers[provider_type] = get_provider(provider_type, config)
        return self._providers[provider_type]

    def _report_progress(self, completed: int, total: int, status: str) -> None:
        """Report progress if callback is set."""
        if self.progress_callback:
            self.progress_callback(completed, total, status)

    async def run_observation(
        self,
        site_id: UUID | None,
        run_id: UUID | None,
        company_name: str,
        domain: str,
        questions: list[tuple[str, str]],  # (question_id, question_text)
    ) -> ObservationRun:
        """
        Run observations for a set of questions.

        Args:
            site_id: Site identifier
            run_id: Run identifier (links to simulation run)
            company_name: Company name for observations
            domain: Domain for tracking mentions
            questions: List of (question_id, question_text) tuples

        Returns:
            ObservationRun with all results
        """
        # Create the run
        obs_run = ObservationRun(
            site_id=site_id,
            run_id=run_id,
            company_name=company_name,
            domain=domain,
            provider=self.config.primary_provider,
            model=self.config.model,
            total_questions=min(len(questions), self.config.max_questions),
            status=ObservationStatus.IN_PROGRESS,
            started_at=datetime.utcnow(),
        )

        # Create requests
        requests = [
            ObservationRequest(
                question_id=q_id,
                question_text=q_text,
                company_name=company_name,
                domain=domain,
                model=self.config.model,
                max_tokens=self.config.max_tokens_per_request,
            )
            for q_id, q_text in questions[: self.config.max_questions]
        ]

        self._report_progress(0, len(requests), "Starting observations")

        # Process requests with concurrency limit
        semaphore = asyncio.Semaphore(self.config.concurrent_requests)
        completed = 0

        async def process_request(request: ObservationRequest) -> ObservationResult:
            nonlocal completed
            async with semaphore:
                result = await self._observe_with_retry(request)
                completed += 1
                self._report_progress(
                    completed,
                    len(requests),
                    f"Processed {completed}/{len(requests)} questions",
                )
                return result

        try:
            # Run all requests concurrently (within semaphore limit)
            tasks = [process_request(req) for req in requests]
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.config.total_timeout_seconds,
            )

            # Process results
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    # Task failed with exception
                    error_result = ObservationResult(
                        question_id=requests[i].question_id,
                        question_text=requests[i].question_text,
                        company_name=company_name,
                        domain=domain,
                    )
                    obs_run.add_result(error_result)
                    obs_run.errors.append(
                        ProviderError(
                            provider=self.config.primary_provider,
                            error_type="exception",
                            message=str(result),
                            retryable=False,
                        )
                    )
                elif isinstance(result, ObservationResult):
                    obs_run.add_result(result)

            # Determine final status
            if obs_run.questions_failed == 0:
                obs_run.status = ObservationStatus.COMPLETED
            elif obs_run.questions_completed > 0:
                obs_run.status = ObservationStatus.PARTIAL
            else:
                obs_run.status = ObservationStatus.FAILED

        except TimeoutError:
            obs_run.status = ObservationStatus.PARTIAL
            obs_run.errors.append(
                ProviderError(
                    provider=self.config.primary_provider,
                    error_type="timeout",
                    message=f"Run timed out after {self.config.total_timeout_seconds}s",
                    retryable=False,
                )
            )

        obs_run.completed_at = datetime.utcnow()
        self._report_progress(
            obs_run.questions_completed,
            obs_run.total_questions,
            f"Completed: {obs_run.status.value}",
        )

        return obs_run

    async def _observe_with_retry(
        self,
        request: ObservationRequest,
    ) -> ObservationResult:
        """Observe with retries and provider failover."""
        providers_to_try = [
            self.config.primary_provider,
            self.config.fallback_provider,
        ]

        last_error: ProviderError | None = None

        for provider_type in providers_to_try:
            provider = self._get_provider(provider_type)

            # Check if provider is available
            if not await provider.health_check():
                continue

            # Try with retries
            delay = self.config.retry_delay_seconds

            for attempt in range(self.config.max_retries):
                response = await provider.observe(request)

                if response.success:
                    # Parse the response for mentions
                    result = self._parse_response_to_result(request, response)
                    return result

                last_error = response.error

                # Don't retry if not retryable
                if last_error and not last_error.retryable:
                    break

                # Wait before retry with backoff
                if attempt < self.config.max_retries - 1:
                    await asyncio.sleep(delay)
                    delay *= self.config.retry_backoff_multiplier

        # All attempts failed
        return ObservationResult(
            question_id=request.question_id,
            question_text=request.question_text,
            company_name=request.company_name,
            domain=request.domain,
        )

    def _parse_response_to_result(  # type: ignore[no-untyped-def]
        self,
        request: ObservationRequest,
        response,
    ) -> ObservationResult:
        """Parse response content for mentions and citations."""
        content = response.content.lower()
        company_lower = request.company_name.lower()
        domain_lower = request.domain.lower()

        # Check for mentions
        mentions_company = company_lower in content
        mentions_domain = domain_lower in content

        # Extract URLs
        import re

        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, response.content)
        cited_urls = [u for u in urls if domain_lower in u.lower()]

        mentions_url = len(cited_urls) > 0

        # Determine confidence expressed
        confidence = "unknown"
        if any(phrase in content for phrase in ["i'm not sure", "i don't know", "uncertain"]):
            confidence = "low"
        elif any(phrase in content for phrase in ["based on my knowledge", "i believe", "likely"]):
            confidence = "medium"
        elif any(phrase in content for phrase in ["definitely", "certainly", "i can confirm"]):
            confidence = "high"

        return ObservationResult(
            question_id=request.question_id,
            question_text=request.question_text,
            company_name=request.company_name,
            domain=request.domain,
            response=response,
            mentions_company=mentions_company,
            mentions_domain=mentions_domain,
            mentions_url=mentions_url,
            cited_urls=cited_urls,
            confidence_expressed=confidence,
        )


async def run_observation(
    company_name: str,
    domain: str,
    questions: list[tuple[str, str]],
    config: RunConfig | None = None,
    progress_callback: ProgressCallback | None = None,
) -> ObservationRun:
    """
    Convenience function to run observations.

    Args:
        company_name: Company name
        domain: Domain to track
        questions: List of (question_id, question_text)
        config: Optional run configuration
        progress_callback: Optional progress callback

    Returns:
        ObservationRun with results
    """
    runner = ObservationRunner(config=config, progress_callback=progress_callback)
    return await runner.run_observation(
        site_id=None,
        run_id=None,
        company_name=company_name,
        domain=domain,
        questions=questions,
    )
