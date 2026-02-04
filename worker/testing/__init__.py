"""Real-world test runner for validating Findable Score predictions.

This module provides infrastructure for:
- Defining test corpora (known cited/uncited sites)
- Running the scoring pipeline on test sites
- Querying AI systems for ground truth
- Comparing predictions to reality
- Generating validation reports
"""

from worker.testing.comparison import (
    SiteComparison,
    ValidationMetrics,
    ValidationReport,
    calculate_metrics,
    compare_all,
    compare_site,
)
from worker.testing.corpus import SiteCategory, TestCorpus, TestSite
from worker.testing.ground_truth import (
    CitedSource,
    GroundTruthResult,
    ProviderResponse,
    collect_ground_truth,
    collect_ground_truth_batch,
    extract_domains_from_text,
)
from worker.testing.pipeline import (
    PillarScores,
    PipelineResult,
    QuestionResult,
    run_pipeline,
    run_pipeline_batch,
)
from worker.testing.queries import TEST_QUERIES, QueryCategory, TestQuery

__all__ = [
    "TestSite",
    "TestCorpus",
    "SiteCategory",
    "TestQuery",
    "QueryCategory",
    "TEST_QUERIES",
    "PipelineResult",
    "PillarScores",
    "QuestionResult",
    "run_pipeline",
    "run_pipeline_batch",
    "GroundTruthResult",
    "ProviderResponse",
    "CitedSource",
    "collect_ground_truth",
    "collect_ground_truth_batch",
    "extract_domains_from_text",
    "SiteComparison",
    "ValidationMetrics",
    "ValidationReport",
    "compare_site",
    "compare_all",
    "calculate_metrics",
]
