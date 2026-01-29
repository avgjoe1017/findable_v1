"""Observation provider layer for AI model queries.

This package provides a unified interface for running observations
(questions about companies) through various AI providers and parsing
the responses for mentions, citations, and sourceability signals.

Use explicit imports:
    from worker.observation.providers import ObservationProvider, get_provider
    from worker.observation.models import ObservationRequest, ObservationResult
    from worker.observation.runner import ObservationRunner
"""

__all__ = [
    # Providers
    "ObservationProvider",
    "OpenRouterProvider",
    "OpenAIProvider",
    "MockProvider",
    "get_provider",
    # Models
    "ObservationRequest",
    "ObservationResponse",
    "ObservationResult",
    "ObservationRun",
    "UsageStats",
    "ProviderError",
    # Runner
    "ObservationRunner",
    "RunConfig",
]
