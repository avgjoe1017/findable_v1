"""Comparison engine for validating predictions against ground truth.

Compares pipeline predictions (Findable Score) against actual AI citations
to measure prediction accuracy and identify calibration opportunities.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import structlog

from worker.testing.corpus import TestSite
from worker.testing.ground_truth import GroundTruthResult
from worker.testing.pipeline import PipelineResult

logger = structlog.get_logger(__name__)


@dataclass
class SiteComparison:
    """Comparison result for a single site."""

    site_url: str
    site_name: str
    site_domain: str
    site_category: str

    # Pipeline predictions
    predicted_score: float
    predicted_findable: bool  # True if score >= threshold
    prediction_confidence: str  # "high", "medium", "low"

    # Ground truth
    queries_analyzed: int
    queries_cited: int  # Number of queries where site was cited
    citation_rate: float  # queries_cited / queries_analyzed
    actually_cited: bool  # True if citation_rate >= threshold

    # Comparison
    prediction_correct: bool
    prediction_type: str  # "true_positive", "true_negative", "false_positive", "false_negative"
    score_vs_citation_delta: float  # Difference between predicted score and actual citation rate

    def to_dict(self) -> dict[str, Any]:
        return {
            "site_url": self.site_url,
            "site_name": self.site_name,
            "site_domain": self.site_domain,
            "site_category": self.site_category,
            "predicted_score": self.predicted_score,
            "predicted_findable": self.predicted_findable,
            "prediction_confidence": self.prediction_confidence,
            "queries_analyzed": self.queries_analyzed,
            "queries_cited": self.queries_cited,
            "citation_rate": self.citation_rate,
            "actually_cited": self.actually_cited,
            "prediction_correct": self.prediction_correct,
            "prediction_type": self.prediction_type,
            "score_vs_citation_delta": self.score_vs_citation_delta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteComparison":
        return cls(
            site_url=data["site_url"],
            site_name=data["site_name"],
            site_domain=data["site_domain"],
            site_category=data["site_category"],
            predicted_score=data["predicted_score"],
            predicted_findable=data["predicted_findable"],
            prediction_confidence=data["prediction_confidence"],
            queries_analyzed=data["queries_analyzed"],
            queries_cited=data["queries_cited"],
            citation_rate=data["citation_rate"],
            actually_cited=data["actually_cited"],
            prediction_correct=data["prediction_correct"],
            prediction_type=data["prediction_type"],
            score_vs_citation_delta=data["score_vs_citation_delta"],
        )


@dataclass
class ValidationMetrics:
    """Aggregate validation metrics."""

    # Sample counts
    total_sites: int
    sites_with_predictions: int
    sites_with_ground_truth: int
    sites_compared: int

    # Prediction accuracy
    true_positives: int  # Predicted findable, actually cited
    true_negatives: int  # Predicted not findable, actually not cited
    false_positives: int  # Predicted findable, actually not cited (optimistic)
    false_negatives: int  # Predicted not findable, actually cited (pessimistic)

    # Metrics
    accuracy: float  # (TP + TN) / total
    precision: float  # TP / (TP + FP)
    recall: float  # TP / (TP + FN)
    f1_score: float  # 2 * (precision * recall) / (precision + recall)

    # Bias metrics
    optimism_rate: float  # FP / total (over-predicting)
    pessimism_rate: float  # FN / total (under-predicting)

    # Score correlation
    score_citation_correlation: float  # Correlation between score and citation rate
    mean_absolute_error: float  # Average |predicted - actual|

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_sites": self.total_sites,
            "sites_with_predictions": self.sites_with_predictions,
            "sites_with_ground_truth": self.sites_with_ground_truth,
            "sites_compared": self.sites_compared,
            "true_positives": self.true_positives,
            "true_negatives": self.true_negatives,
            "false_positives": self.false_positives,
            "false_negatives": self.false_negatives,
            "accuracy": self.accuracy,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score,
            "optimism_rate": self.optimism_rate,
            "pessimism_rate": self.pessimism_rate,
            "score_citation_correlation": self.score_citation_correlation,
            "mean_absolute_error": self.mean_absolute_error,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationMetrics":
        return cls(
            total_sites=data["total_sites"],
            sites_with_predictions=data["sites_with_predictions"],
            sites_with_ground_truth=data["sites_with_ground_truth"],
            sites_compared=data["sites_compared"],
            true_positives=data["true_positives"],
            true_negatives=data["true_negatives"],
            false_positives=data["false_positives"],
            false_negatives=data["false_negatives"],
            accuracy=data["accuracy"],
            precision=data["precision"],
            recall=data["recall"],
            f1_score=data["f1_score"],
            optimism_rate=data["optimism_rate"],
            pessimism_rate=data["pessimism_rate"],
            score_citation_correlation=data["score_citation_correlation"],
            mean_absolute_error=data["mean_absolute_error"],
        )


@dataclass
class ValidationReport:
    """Complete validation report."""

    run_id: str
    generated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    # Summary
    corpus_name: str = ""
    total_sites: int = 0
    total_queries: int = 0

    # Metrics
    metrics: ValidationMetrics | None = None

    # Site comparisons
    site_comparisons: list[SiteComparison] = field(default_factory=list)

    # By category breakdown
    metrics_by_category: dict[str, ValidationMetrics] = field(default_factory=dict)

    # Insights
    insights: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "generated_at": self.generated_at,
            "corpus_name": self.corpus_name,
            "total_sites": self.total_sites,
            "total_queries": self.total_queries,
            "metrics": self.metrics.to_dict() if self.metrics else None,
            "site_comparisons": [c.to_dict() for c in self.site_comparisons],
            "metrics_by_category": {k: v.to_dict() for k, v in self.metrics_by_category.items()},
            "insights": self.insights,
            "recommendations": self.recommendations,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationReport":
        metrics = ValidationMetrics.from_dict(data["metrics"]) if data.get("metrics") else None
        site_comparisons = [SiteComparison.from_dict(c) for c in data.get("site_comparisons", [])]
        metrics_by_category = {
            k: ValidationMetrics.from_dict(v)
            for k, v in data.get("metrics_by_category", {}).items()
        }

        return cls(
            run_id=data["run_id"],
            generated_at=data.get("generated_at", datetime.now(UTC).isoformat()),
            corpus_name=data.get("corpus_name", ""),
            total_sites=data.get("total_sites", 0),
            total_queries=data.get("total_queries", 0),
            metrics=metrics,
            site_comparisons=site_comparisons,
            metrics_by_category=metrics_by_category,
            insights=data.get("insights", []),
            recommendations=data.get("recommendations", []),
        )


def get_site_citation_rate(
    site_domain: str,
    ground_truth_results: list[GroundTruthResult],
) -> tuple[int, int, float]:
    """
    Calculate how often a site domain was cited across all queries.

    Returns:
        (queries_analyzed, queries_cited, citation_rate)
    """
    queries_analyzed = 0
    queries_cited = 0

    for gt in ground_truth_results:
        # Skip if all providers had errors
        if all(r.error for r in gt.provider_responses):
            continue

        queries_analyzed += 1

        # Check if domain was cited in any response
        domain_lower = site_domain.lower()
        for domain in gt.all_cited_domains:
            if domain.lower() == domain_lower or domain.lower().endswith("." + domain_lower):
                queries_cited += 1
                break

    citation_rate = queries_cited / queries_analyzed if queries_analyzed > 0 else 0.0
    return queries_analyzed, queries_cited, citation_rate


def compare_site(
    site: TestSite,
    pipeline_result: PipelineResult | None,
    ground_truth_results: list[GroundTruthResult],
    findable_threshold: float = 50.0,
    citation_threshold: float = 0.1,
) -> SiteComparison | None:
    """
    Compare a single site's pipeline prediction against ground truth.

    Args:
        site: The test site
        pipeline_result: Pipeline result for the site (or None if failed)
        ground_truth_results: All ground truth results
        findable_threshold: Score threshold for "findable" prediction
        citation_threshold: Citation rate threshold for "actually cited"

    Returns:
        SiteComparison or None if insufficient data
    """
    # Get pipeline prediction
    if pipeline_result is None or pipeline_result.status == "failed":
        predicted_score = 0.0
        prediction_confidence = "low"
    else:
        predicted_score = pipeline_result.overall_score
        if predicted_score >= 70:
            prediction_confidence = "high"
        elif predicted_score >= 40:
            prediction_confidence = "medium"
        else:
            prediction_confidence = "low"

    predicted_findable = predicted_score >= findable_threshold

    # Get ground truth
    queries_analyzed, queries_cited, citation_rate = get_site_citation_rate(
        site.domain, ground_truth_results
    )

    if queries_analyzed == 0:
        return None  # No data to compare

    actually_cited = citation_rate >= citation_threshold

    # Determine prediction type
    if predicted_findable and actually_cited:
        prediction_type = "true_positive"
        prediction_correct = True
    elif not predicted_findable and not actually_cited:
        prediction_type = "true_negative"
        prediction_correct = True
    elif predicted_findable and not actually_cited:
        prediction_type = "false_positive"
        prediction_correct = False
    else:
        prediction_type = "false_negative"
        prediction_correct = False

    # Calculate delta (normalized to 0-100 scale)
    score_vs_citation_delta = predicted_score - (citation_rate * 100)

    return SiteComparison(
        site_url=site.url,
        site_name=site.name,
        site_domain=site.domain,
        site_category=site.category.value,
        predicted_score=predicted_score,
        predicted_findable=predicted_findable,
        prediction_confidence=prediction_confidence,
        queries_analyzed=queries_analyzed,
        queries_cited=queries_cited,
        citation_rate=citation_rate,
        actually_cited=actually_cited,
        prediction_correct=prediction_correct,
        prediction_type=prediction_type,
        score_vs_citation_delta=score_vs_citation_delta,
    )


def calculate_metrics(comparisons: list[SiteComparison]) -> ValidationMetrics:
    """Calculate validation metrics from site comparisons."""
    if not comparisons:
        return ValidationMetrics(
            total_sites=0,
            sites_with_predictions=0,
            sites_with_ground_truth=0,
            sites_compared=0,
            true_positives=0,
            true_negatives=0,
            false_positives=0,
            false_negatives=0,
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            optimism_rate=0.0,
            pessimism_rate=0.0,
            score_citation_correlation=0.0,
            mean_absolute_error=0.0,
        )

    # Count prediction types
    tp = sum(1 for c in comparisons if c.prediction_type == "true_positive")
    tn = sum(1 for c in comparisons if c.prediction_type == "true_negative")
    fp = sum(1 for c in comparisons if c.prediction_type == "false_positive")
    fn = sum(1 for c in comparisons if c.prediction_type == "false_negative")

    total = len(comparisons)

    # Calculate metrics
    accuracy = (tp + tn) / total if total > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    optimism_rate = fp / total if total > 0 else 0.0
    pessimism_rate = fn / total if total > 0 else 0.0

    # Calculate correlation and MAE
    scores = [c.predicted_score for c in comparisons]
    citation_rates = [c.citation_rate * 100 for c in comparisons]  # Scale to 0-100

    # Simple correlation calculation
    if len(scores) > 1:
        mean_score = sum(scores) / len(scores)
        mean_citation = sum(citation_rates) / len(citation_rates)

        numerator = sum(
            (s - mean_score) * (c - mean_citation)
            for s, c in zip(scores, citation_rates, strict=False)
        )
        denominator_score = sum((s - mean_score) ** 2 for s in scores) ** 0.5
        denominator_citation = sum((c - mean_citation) ** 2 for c in citation_rates) ** 0.5

        if denominator_score > 0 and denominator_citation > 0:
            correlation = numerator / (denominator_score * denominator_citation)
        else:
            correlation = 0.0
    else:
        correlation = 0.0

    # Mean absolute error
    mae = sum(abs(c.score_vs_citation_delta) for c in comparisons) / total if total > 0 else 0.0

    return ValidationMetrics(
        total_sites=total,
        sites_with_predictions=sum(1 for c in comparisons if c.predicted_score > 0),
        sites_with_ground_truth=sum(1 for c in comparisons if c.queries_analyzed > 0),
        sites_compared=total,
        true_positives=tp,
        true_negatives=tn,
        false_positives=fp,
        false_negatives=fn,
        accuracy=accuracy,
        precision=precision,
        recall=recall,
        f1_score=f1,
        optimism_rate=optimism_rate,
        pessimism_rate=pessimism_rate,
        score_citation_correlation=correlation,
        mean_absolute_error=mae,
    )


def generate_insights(
    metrics: ValidationMetrics,
    comparisons: list[SiteComparison],
) -> list[str]:
    """Generate human-readable insights from validation metrics."""
    insights = []

    # Accuracy insights
    if metrics.accuracy >= 0.8:
        insights.append(
            f"Strong prediction accuracy: {metrics.accuracy:.1%} of predictions correct"
        )
    elif metrics.accuracy >= 0.6:
        insights.append(
            f"Moderate prediction accuracy: {metrics.accuracy:.1%} of predictions correct"
        )
    else:
        insights.append(
            f"Low prediction accuracy: {metrics.accuracy:.1%} of predictions correct - calibration needed"
        )

    # Bias insights
    if metrics.optimism_rate > 0.2:
        insights.append(
            f"Optimism bias detected: {metrics.optimism_rate:.1%} false positives (over-predicting findability)"
        )
    if metrics.pessimism_rate > 0.2:
        insights.append(
            f"Pessimism bias detected: {metrics.pessimism_rate:.1%} false negatives (under-predicting findability)"
        )

    # Correlation insights
    if metrics.score_citation_correlation > 0.7:
        insights.append(
            f"Strong score-citation correlation ({metrics.score_citation_correlation:.2f}): scores predict citations well"
        )
    elif metrics.score_citation_correlation > 0.4:
        insights.append(
            f"Moderate score-citation correlation ({metrics.score_citation_correlation:.2f})"
        )
    else:
        insights.append(
            f"Weak score-citation correlation ({metrics.score_citation_correlation:.2f}): scores may need recalibration"
        )

    # Category-specific insights
    known_cited = [c for c in comparisons if c.site_category == "known_cited"]
    if known_cited:
        cited_accuracy = sum(1 for c in known_cited if c.prediction_correct) / len(known_cited)
        if cited_accuracy < 0.7:
            insights.append(
                f"Known-cited sites have {cited_accuracy:.1%} prediction accuracy - may be under-scoring authorities"
            )

    known_uncited = [c for c in comparisons if c.site_category == "known_uncited"]
    if known_uncited:
        uncited_accuracy = sum(1 for c in known_uncited if c.prediction_correct) / len(
            known_uncited
        )
        if uncited_accuracy < 0.7:
            insights.append(
                f"Known-uncited sites have {uncited_accuracy:.1%} prediction accuracy - may be over-scoring non-authorities"
            )

    return insights


def generate_recommendations(
    metrics: ValidationMetrics,
    comparisons: list[SiteComparison],
) -> list[str]:
    """Generate actionable recommendations from validation results."""
    recommendations = []

    # Threshold recommendations
    if metrics.false_positives > metrics.false_negatives * 2:
        recommendations.append(
            "Consider raising the findable score threshold to reduce false positives"
        )
    elif metrics.false_negatives > metrics.false_positives * 2:
        recommendations.append(
            "Consider lowering the findable score threshold to reduce false negatives"
        )

    # Pillar weight recommendations
    fp_sites = [c for c in comparisons if c.prediction_type == "false_positive"]
    if fp_sites:
        avg_fp_score = sum(c.predicted_score for c in fp_sites) / len(fp_sites)
        if avg_fp_score > 70:
            recommendations.append(
                f"False positives average score {avg_fp_score:.1f} - investigate which pillars are over-weighted"
            )

    # Sample size recommendations
    if metrics.sites_compared < 20:
        recommendations.append(
            f"Only {metrics.sites_compared} sites compared - increase corpus size for more reliable metrics"
        )

    # Correlation-based recommendations
    if metrics.score_citation_correlation < 0.4:
        recommendations.append(
            "Low score-citation correlation suggests pillar weights may need recalibration"
        )

    # Category-specific recommendations
    known_cited = [
        c for c in comparisons if c.site_category == "known_cited" and not c.prediction_correct
    ]
    if known_cited:
        recommendations.append(
            f"{len(known_cited)} known-cited sites incorrectly predicted - review authority signals"
        )

    return recommendations


def compare_all(
    sites: list[TestSite],
    pipeline_results: list[PipelineResult],
    ground_truth_results: list[GroundTruthResult],
    run_id: str,
    corpus_name: str = "",
    findable_threshold: float = 50.0,
    citation_threshold: float = 0.1,
) -> ValidationReport:
    """
    Compare all sites' predictions against ground truth and generate report.

    Args:
        sites: Test corpus sites
        pipeline_results: Pipeline results (indexed same as sites)
        ground_truth_results: All ground truth results from AI queries
        run_id: Unique run identifier
        corpus_name: Name of the test corpus
        findable_threshold: Score threshold for "findable" prediction
        citation_threshold: Citation rate threshold for "actually cited"

    Returns:
        Complete ValidationReport
    """
    logger.info(
        "comparison_starting",
        sites=len(sites),
        pipeline_results=len(pipeline_results),
        ground_truth=len(ground_truth_results),
    )

    # Build pipeline results lookup by URL
    pipeline_by_url = {r.url: r for r in pipeline_results}

    # Compare each site
    comparisons = []
    for site in sites:
        pipeline_result = pipeline_by_url.get(site.url)
        comparison = compare_site(
            site=site,
            pipeline_result=pipeline_result,
            ground_truth_results=ground_truth_results,
            findable_threshold=findable_threshold,
            citation_threshold=citation_threshold,
        )
        if comparison:
            comparisons.append(comparison)

    # Calculate overall metrics
    metrics = calculate_metrics(comparisons)

    # Calculate metrics by category
    metrics_by_category = {}
    categories = {c.site_category for c in comparisons}
    for category in categories:
        category_comparisons = [c for c in comparisons if c.site_category == category]
        metrics_by_category[category] = calculate_metrics(category_comparisons)

    # Generate insights and recommendations
    insights = generate_insights(metrics, comparisons)
    recommendations = generate_recommendations(metrics, comparisons)

    logger.info(
        "comparison_completed",
        sites_compared=len(comparisons),
        accuracy=metrics.accuracy,
        precision=metrics.precision,
        recall=metrics.recall,
    )

    return ValidationReport(
        run_id=run_id,
        corpus_name=corpus_name,
        total_sites=len(sites),
        total_queries=len(ground_truth_results),
        metrics=metrics,
        site_comparisons=comparisons,
        metrics_by_category=metrics_by_category,
        insights=insights,
        recommendations=recommendations,
    )
