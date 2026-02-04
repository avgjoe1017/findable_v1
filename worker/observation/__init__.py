"""Observation provider layer for AI model queries.

This package provides a unified interface for running observations
(questions about companies) through various AI providers, parsing
the responses for mentions, citations, and sourceability signals,
comparing results with simulation predictions, and benchmarking
against competitors.

Use explicit imports:
    from worker.observation.providers import ObservationProvider, get_provider
    from worker.observation.models import ObservationRequest, ObservationResult
    from worker.observation.runner import ObservationRunner
    from worker.observation.parser import ObservationParser, parse_observation
    from worker.observation.comparison import compare_simulation_observation
    from worker.observation.benchmark import CompetitorBenchmarker, run_benchmark
    from worker.observation.benchmark_v2 import CompetitorBenchmarkerV2, run_benchmark_v2
"""

__all__ = [
    # Providers
    "ObservationProvider",
    "OpenRouterProvider",
    "OpenAIProvider",
    "MockProvider",
    "get_provider",
    "ProviderConfig",
    # Models
    "ObservationRequest",
    "ObservationResponse",
    "ObservationResult",
    "ObservationRun",
    "ObservationStatus",
    "UsageStats",
    "ProviderError",
    "ProviderType",
    # Runner
    "ObservationRunner",
    "RunConfig",
    "run_observation",
    # Parser (Day 21)
    "ObservationParser",
    "ParsedObservation",
    "Mention",
    "MentionType",
    "Citation",
    "CitationType",
    "Sentiment",
    "ConfidenceLevel",
    "parse_observation",
    # Comparison (Day 21)
    "SimulationObservationComparator",
    "ComparisonSummary",
    "QuestionComparison",
    "OutcomeMatch",
    "SourceabilityOutcome",
    "compare_simulation_observation",
    # Benchmark (Day 22)
    "CompetitorBenchmarker",
    "CompetitorInfo",
    "CompetitorResult",
    "BenchmarkResult",
    "QuestionBenchmark",
    "HeadToHead",
    "BenchmarkOutcome",
    "MentionLevel",
    "run_benchmark",
    # Benchmark v2 (pillar comparison)
    "CompetitorBenchmarkerV2",
    "BenchmarkV2Result",
    "HeadToHeadV2",
    "PillarComparison",
    "CompetitorV2Score",
    "run_benchmark_v2",
]
