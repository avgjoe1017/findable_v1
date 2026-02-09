"""Calibration optimizer using grid search.

This module provides weight and threshold optimization without ML infrastructure:
- Grid search over weight combinations (each pillar 5-35%, sum=100)
- Threshold optimization for answerability predictions
- Holdout validation to prevent overfitting
"""

import itertools
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import numpy as np
import structlog
from sqlalchemy import select

from api.database import async_session_maker
from api.models.calibration import (
    CalibrationConfig,
    CalibrationSample,
    OutcomeMatch,
)

logger = structlog.get_logger(__name__)


# Weight constraints
MIN_WEIGHT = 5.0
MAX_WEIGHT = 35.0
WEIGHT_STEP = 5.0  # Step size for grid search
TOTAL_WEIGHT = 100.0

# Default weights for reference (7-pillar system)
DEFAULT_WEIGHTS = {
    "technical": 12.0,
    "structure": 18.0,
    "schema": 13.0,
    "authority": 12.0,
    "entity_recognition": 13.0,
    "retrieval": 22.0,
    "coverage": 10.0,
}

# Default findability threshold (calibrated from 820+ samples across 20 domains)
# Lowered from 50 to 30 based on optimizer grid search:
# At threshold=50, 27% of findable sites were predicted "not findable".
# At threshold=30, accuracy reaches 99.5% train / 100% holdout with balanced bias.
# Note: further refinement blocked by class imbalance (only 2 negative samples).
DEFAULT_FINDABILITY_THRESHOLD = 30

# Threshold constraints
MIN_FULLY_ANSWERABLE = 0.50
MAX_FULLY_ANSWERABLE = 0.90
MIN_PARTIALLY_ANSWERABLE = 0.15
MAX_PARTIALLY_ANSWERABLE = 0.50
THRESHOLD_STEP = 0.05


@dataclass
class OptimizationResult:
    """Result of an optimization run."""

    # Best configuration found
    best_weights: dict[str, float] | None = None
    best_thresholds: dict[str, float] | None = None

    # Performance metrics (bias-adjusted)
    best_score: float = 0.0  # Bias-adjusted score
    best_accuracy: float = 0.0
    baseline_accuracy: float = 0.0
    baseline_score: float = 0.0
    improvement: float = 0.0

    # Bias metrics for best config
    best_over_rate: float = 0.0  # Optimistic prediction rate
    best_under_rate: float = 0.0  # Pessimistic prediction rate
    baseline_over_rate: float = 0.0
    baseline_under_rate: float = 0.0

    # Best findability threshold (jointly optimized with weights)
    best_threshold: int = 50

    # Source primacy bonus weight (independent of sum-to-100 pillar weights)
    best_primacy_weight: float = 0.0

    # Validation metrics
    holdout_accuracy: float = 0.0
    holdout_score: float = 0.0
    holdout_sample_count: int = 0

    # Domain diversity
    training_domains: int = 0
    holdout_domains: int = 0

    # Search stats
    combinations_tested: int = 0
    training_sample_count: int = 0

    # Status
    is_improvement: bool = False
    improvement_sufficient: bool = False  # True if > min_improvement threshold
    min_improvement_threshold: float = 0.02  # 2% default

    # Per-domain accuracy breakdown (holdout)
    domain_accuracy: dict[str, dict] = field(default_factory=dict)

    # Errors encountered
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "best_weights": self.best_weights,
            "best_thresholds": self.best_thresholds,
            "best_score": round(self.best_score, 4),
            "best_accuracy": round(self.best_accuracy, 4),
            "baseline_accuracy": round(self.baseline_accuracy, 4),
            "baseline_score": round(self.baseline_score, 4),
            "improvement": round(self.improvement, 4),
            "best_threshold": self.best_threshold,
            "best_primacy_weight": self.best_primacy_weight,
            "best_over_rate": round(self.best_over_rate, 4),
            "best_under_rate": round(self.best_under_rate, 4),
            "baseline_over_rate": round(self.baseline_over_rate, 4),
            "baseline_under_rate": round(self.baseline_under_rate, 4),
            "holdout_accuracy": round(self.holdout_accuracy, 4),
            "holdout_score": round(self.holdout_score, 4),
            "holdout_sample_count": self.holdout_sample_count,
            "training_domains": self.training_domains,
            "holdout_domains": self.holdout_domains,
            "combinations_tested": self.combinations_tested,
            "training_sample_count": self.training_sample_count,
            "is_improvement": self.is_improvement,
            "improvement_sufficient": self.improvement_sufficient,
            "min_improvement_threshold": self.min_improvement_threshold,
            "domain_accuracy": self.domain_accuracy,
            "errors": self.errors,
        }


def generate_weight_combinations(step: float = WEIGHT_STEP) -> list[dict[str, float]]:
    """
    Generate all valid weight combinations for grid search.

    Constraints:
    - Each weight between 5-35
    - All weights sum to 100
    - Step size configurable (default 5)

    With 7 pillars and step=5, this generates ~4500 combinations.
    With step=10, this generates ~200 combinations (faster but coarser).

    Args:
        step: Step size for weight values (default 5)

    Returns:
        List of weight dicts
    """
    pillars = [
        "technical",
        "structure",
        "schema",
        "authority",
        "entity_recognition",
        "retrieval",
        "coverage",
    ]
    valid_values = list(range(int(MIN_WEIGHT), int(MAX_WEIGHT) + 1, int(step)))

    combinations = []

    # Generate all combinations and filter by sum=100
    for combo in itertools.product(valid_values, repeat=len(pillars)):
        if sum(combo) == int(TOTAL_WEIGHT):
            weights = dict(zip(pillars, [float(v) for v in combo], strict=False))
            combinations.append(weights)

    logger.debug("weight_combinations_generated", count=len(combinations), step=step)
    return combinations


def _split_by_domain(
    samples: list[CalibrationSample],
    holdout_pct: float = 0.2,
) -> tuple[list[CalibrationSample], list[CalibrationSample], set[str], set[str]]:
    """
    Split samples by domain (not randomly) to prevent overfitting.

    Each domain goes entirely to training or holdout, not split between them.
    This ensures the model generalizes across domain types.

    Args:
        samples: All calibration samples
        holdout_pct: Percentage of domains to hold out

    Returns:
        Tuple of (training_samples, holdout_samples, training_domains, holdout_domains)
    """
    # Group samples by domain
    domain_samples: dict[str, list[CalibrationSample]] = {}
    for sample in samples:
        domain = str(sample.site_id)  # Use site_id as domain identifier
        if domain not in domain_samples:
            domain_samples[domain] = []
        domain_samples[domain].append(sample)

    domains = list(domain_samples.keys())
    holdout_count = max(1, int(len(domains) * holdout_pct))

    # Take last N domains as holdout (preserves time ordering somewhat)
    holdout_domains = set(domains[-holdout_count:])
    training_domains = set(domains[:-holdout_count]) if holdout_count < len(domains) else set()

    training_samples = []
    holdout_samples = []

    for domain, domain_sample_list in domain_samples.items():
        if domain in holdout_domains:
            holdout_samples.extend(domain_sample_list)
        else:
            training_samples.extend(domain_sample_list)

    return training_samples, holdout_samples, training_domains, holdout_domains


async def optimize_pillar_weights(
    window_days: int = 60,
    min_samples: int = 200,
    holdout_pct: float = 0.2,
    min_improvement: float = 0.02,
    step: float = WEIGHT_STEP,
    coarse_then_fine: bool = True,
    use_bias_adjusted: bool = True,  # Deprecated: MCC is now always used  # noqa: ARG001
    max_weight_change: float = 10.0,
    site_type: str | None = None,
) -> OptimizationResult:
    """
    Optimize pillar weights using grid search over historical samples.

    This function:
    1. Loads calibration samples from the specified window
    2. Splits by DOMAIN (not random) into training and holdout sets
    3. Tests weight combinations using Matthews Correlation Coefficient (MCC)
    4. Validates best config against holdout set
    5. Returns result if improvement exceeds threshold

    MCC is used instead of bias-adjusted accuracy because it correctly handles
    class imbalance: a trivial "predict all positive" classifier gets MCC=0.

    Args:
        window_days: Number of days to look back for samples
        min_samples: Minimum samples required for optimization
        holdout_pct: Percentage of DOMAINS to hold out for validation
        min_improvement: Minimum score improvement required (default 2%)
        step: Step size for grid search (default 5, use 10 for faster coarse search)
        coarse_then_fine: If True, do coarse search (step=5) then fine search (step=2)
        use_bias_adjusted: Deprecated, MCC is always used
        max_weight_change: Maximum change per pillar from defaults (default 10%)
        site_type: Optional filter to train weights only for a specific site type

    Returns:
        OptimizationResult with best weights and metrics
    """
    result = OptimizationResult(min_improvement_threshold=min_improvement)

    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session_maker() as db:
        # Load calibration samples with pillar scores
        query = (
            select(CalibrationSample)
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .where(CalibrationSample.pillar_scores.isnot(None))
        )
        if site_type:
            query = query.where(CalibrationSample.site_type == site_type)
        query = query.order_by(CalibrationSample.created_at)
        samples_result = await db.execute(query)
        all_samples = list(samples_result.scalars().all())

        # Filter for samples with sufficient pillar coverage
        # We need at least 70% of the weight to be populated (avoid samples missing retrieval+coverage)
        pillar_keys = list(DEFAULT_WEIGHTS.keys())
        min_weight_coverage = 70.0  # Require 70% of weight to be covered

        def get_weight_coverage(sample: CalibrationSample) -> float:
            """Calculate the percentage of total weight covered by non-null pillars."""
            covered_weight = 0.0
            for pillar in pillar_keys:
                if sample.pillar_scores and sample.pillar_scores.get(pillar) is not None:
                    covered_weight += DEFAULT_WEIGHTS[pillar]
            return covered_weight

        samples = [s for s in all_samples if get_weight_coverage(s) >= min_weight_coverage]

        logger.info(
            "samples_filtered_for_weight_coverage",
            total=len(all_samples),
            with_70pct_coverage=len(samples),
            filtered=len(all_samples) - len(samples),
            min_weight_coverage=min_weight_coverage,
        )

        if len(samples) < min_samples:
            result.errors.append(
                f"Insufficient complete samples: {len(samples)} < {min_samples} required"
            )
            logger.warning(
                "weight_optimization_skipped_insufficient_samples",
                samples=len(samples),
                min_required=min_samples,
            )
            return result

        # Domain-stratified split
        training_samples, holdout_samples, training_domains, holdout_domains = _split_by_domain(
            samples, holdout_pct
        )

        result.training_sample_count = len(training_samples)
        result.holdout_sample_count = len(holdout_samples)
        result.training_domains = len(training_domains)
        result.holdout_domains = len(holdout_domains)

        # Check we have enough domains for meaningful optimization
        # With too few domains, the optimizer memorizes domain identity instead of
        # learning generalizable scoring patterns. Minimum: 10 train + 3 holdout.
        min_train_domains = 10
        min_holdout_domains = 3
        if len(training_domains) < min_train_domains:
            result.errors.append(
                f"Insufficient domain diversity: {len(training_domains)} training domains "
                f"(need {min_train_domains}+). Use expert-set weights or site-type baselines."
            )
            logger.warning(
                "weight_optimization_skipped_low_domain_diversity",
                training_domains=len(training_domains),
                min_required=min_train_domains,
            )
            return result
        if len(holdout_domains) < min_holdout_domains:
            result.errors.append(
                f"Insufficient holdout domains: {len(holdout_domains)} "
                f"(need {min_holdout_domains}+). Cannot validate reliably."
            )
            logger.warning(
                "weight_optimization_skipped_low_holdout_domains",
                holdout_domains=len(holdout_domains),
                min_required=min_holdout_domains,
            )
            return result

        logger.info(
            "weight_optimization_starting",
            total_samples=len(samples),
            training_samples=len(training_samples),
            holdout_samples=len(holdout_samples),
            training_domains=len(training_domains),
            holdout_domains=len(holdout_domains),
            scoring_metric="mcc",
            max_weight_change=max_weight_change,
        )

        # Calculate baseline metrics with default weights
        baseline_metrics = _calculate_weighted_metrics(training_samples, DEFAULT_WEIGHTS)
        result.baseline_accuracy = baseline_metrics.accuracy
        result.baseline_score = baseline_metrics.mcc  # Use MCC as primary scoring metric
        result.baseline_over_rate = baseline_metrics.over_rate
        result.baseline_under_rate = baseline_metrics.under_rate

        # Use MCC for optimization (robust to class imbalance)
        best_score = baseline_metrics.mcc

        best_weights = DEFAULT_WEIGHTS.copy()
        best_metrics = baseline_metrics
        best_threshold = 50
        best_primacy_weight = 0.0
        total_combinations_tested = 0

        # Primacy weight search values (independent bonus, not part of sum-to-100)
        # Check if any samples have source_primacy data
        has_primacy_data = any(
            s.pillar_scores and s.pillar_scores.get("source_primacy") is not None
            for s in training_samples
        )
        primacy_weights_to_test = [0, 5, 10, 15, 20] if has_primacy_data else [0]

        # Phase 1: Coarse search (or single pass if coarse_then_fine=False)
        # Note: step=10 produces 0 combos for 7 pillars (no 7-tuple from {5,15,25,35} sums to 100)
        # Use step=5 for coarse with wider constraint radius, then refine with smaller step
        coarse_step = 5.0 if coarse_then_fine else step
        if max_weight_change < 35:
            combinations = _generate_constrained_combinations(
                DEFAULT_WEIGHTS, max_change=max_weight_change, step=coarse_step
            )
        else:
            combinations = generate_weight_combinations(step=coarse_step)

        total_combinations_tested = len(combinations)

        # Search over findability thresholds jointly with weights
        thresholds_to_test = [30, 35, 40, 45, 50, 55, 60]

        for weights in combinations:
            for threshold in thresholds_to_test:
                for pw in primacy_weights_to_test:
                    metrics = _calculate_weighted_metrics(
                        training_samples,
                        weights,
                        threshold=threshold,
                        primacy_weight=pw,
                    )

                    score = metrics.mcc

                    if score > best_score:
                        best_score = score
                        best_weights = weights.copy()
                        best_metrics = metrics
                        best_threshold = threshold
                        best_primacy_weight = pw

        # Phase 2: Fine search around best coarse result
        if coarse_then_fine:
            fine_step = min(step, 2.0)  # Use step=2 for fine refinement
            fine_radius = max(coarse_step, 10.0)  # Search ±10 around best
            fine_combinations = _generate_fine_search_combinations(
                best_weights, step=fine_step, radius=fine_radius
            )
            total_combinations_tested += len(fine_combinations)

            # Fine threshold search around best threshold
            fine_thresholds = list(
                range(max(20, best_threshold - 10), min(70, best_threshold + 11), 2)
            )

            # Fine primacy weight search around best
            if has_primacy_data:
                fine_primacy = list(
                    range(
                        max(0, int(best_primacy_weight) - 5),
                        min(25, int(best_primacy_weight) + 6),
                        2,
                    )
                )
            else:
                fine_primacy = [0]

            logger.info(
                "fine_search_starting",
                center_weights=best_weights,
                center_threshold=best_threshold,
                center_primacy_weight=best_primacy_weight,
                fine_combinations=len(fine_combinations),
                fine_thresholds=fine_thresholds,
                fine_primacy=fine_primacy,
            )

            for weights in fine_combinations:
                for threshold in fine_thresholds:
                    for pw in fine_primacy:
                        metrics = _calculate_weighted_metrics(
                            training_samples,
                            weights,
                            threshold=threshold,
                            primacy_weight=pw,
                        )

                        score = metrics.mcc

                        if score > best_score:
                            best_score = score
                            best_weights = weights.copy()
                            best_metrics = metrics
                            best_threshold = threshold
                            best_primacy_weight = pw

        result.combinations_tested = total_combinations_tested

        result.best_score = best_score
        result.best_accuracy = best_metrics.accuracy
        result.best_over_rate = best_metrics.over_rate
        result.best_under_rate = best_metrics.under_rate
        result.best_weights = best_weights
        result.best_threshold = best_threshold
        result.best_primacy_weight = best_primacy_weight

        result.improvement = best_score - baseline_metrics.mcc

        result.is_improvement = result.improvement > 0

        # Validate on holdout set using best threshold + primacy weight
        if holdout_samples:
            holdout_metrics = _calculate_weighted_metrics(
                holdout_samples,
                best_weights,
                threshold=best_threshold,
                primacy_weight=best_primacy_weight,
            )
            result.holdout_accuracy = holdout_metrics.accuracy
            result.holdout_score = holdout_metrics.bias_adjusted_score
        else:
            result.holdout_accuracy = result.best_accuracy
            result.holdout_score = result.best_score

        # Compute per-domain accuracy on both training and holdout
        for domain_set, label in [
            (training_domains, "training"),
            (holdout_domains, "holdout"),
        ]:
            for domain in domain_set:
                domain_samp = [s for s in samples if str(s.site_id) == domain]
                if not domain_samp:
                    continue
                dm = _calculate_weighted_metrics(
                    domain_samp,
                    best_weights,
                    threshold=best_threshold,
                    primacy_weight=best_primacy_weight,
                )
                result.domain_accuracy[f"{label}:{domain[:8]}"] = {
                    "set": label,
                    "samples": dm.total,
                    "accuracy": round(dm.accuracy, 4),
                    "over_rate": round(dm.over_rate, 4),
                    "under_rate": round(dm.under_rate, 4),
                }

        # Check if improvement is sufficient
        result.improvement_sufficient = result.improvement >= min_improvement

        logger.info(
            "weight_optimization_completed",
            baseline_accuracy=result.baseline_accuracy,
            baseline_score=result.baseline_score,
            best_accuracy=result.best_accuracy,
            best_score=result.best_score,
            best_threshold=result.best_threshold,
            best_primacy_weight=result.best_primacy_weight,
            improvement=result.improvement,
            holdout_accuracy=result.holdout_accuracy,
            holdout_score=result.holdout_score,
            best_over_rate=result.best_over_rate,
            best_under_rate=result.best_under_rate,
            improvement_sufficient=result.improvement_sufficient,
            best_weights=result.best_weights,
        )

        return result


def _generate_constrained_combinations(
    base_weights: dict[str, float],
    max_change: float = 10.0,
    step: float = 5.0,
) -> list[dict[str, float]]:
    """
    Generate weight combinations constrained to ±max_change from base weights.

    This prevents dramatic weight shifts that don't generalize.

    Args:
        base_weights: Starting weights (typically defaults)
        max_change: Maximum change per pillar (default ±10%)
        step: Step size for values

    Returns:
        List of valid weight combinations
    """
    pillars = list(base_weights.keys())
    combinations = []
    int_step = int(step)

    # Generate ranges for each pillar around the base
    # Align to multiples of step so values can sum to 100
    pillar_ranges = {}
    for pillar in pillars:
        base = base_weights[pillar]
        min_val = max(MIN_WEIGHT, base - max_change)
        max_val = min(MAX_WEIGHT, base + max_change)
        # Round min_val UP and max_val DOWN to nearest multiple of step
        aligned_min = int(((min_val + int_step - 1) // int_step) * int_step)
        aligned_max = int((max_val // int_step) * int_step)
        aligned_min = max(int(MIN_WEIGHT), aligned_min)
        pillar_ranges[pillar] = list(range(aligned_min, aligned_max + 1, int_step))

    # Generate all combinations and filter by sum=100
    for combo in itertools.product(*[pillar_ranges[p] for p in pillars]):
        if sum(combo) == int(TOTAL_WEIGHT):
            weights = dict(zip(pillars, [float(v) for v in combo], strict=False))
            combinations.append(weights)

    logger.debug(
        "constrained_combinations_generated",
        count=len(combinations),
        max_change=max_change,
        step=step,
    )

    return combinations


def _generate_fine_search_combinations(
    center_weights: dict[str, float],
    step: float = 5.0,
    radius: float = 15.0,
) -> list[dict[str, float]]:
    """
    Generate weight combinations around a center point for fine search.

    Args:
        center_weights: The center weights to search around
        step: Step size for the fine search
        radius: How far to search from center (each pillar varies ±radius)

    Returns:
        List of valid weight combinations around the center
    """
    pillars = list(center_weights.keys())
    combinations = []
    int_step = int(step)

    # Generate ranges for each pillar around the center
    # Align to multiples of step so values can sum to 100
    pillar_ranges = {}
    for pillar in pillars:
        center = center_weights[pillar]
        min_val = max(MIN_WEIGHT, center - radius)
        max_val = min(MAX_WEIGHT, center + radius)
        aligned_min = int(((min_val + int_step - 1) // int_step) * int_step)
        aligned_max = int((max_val // int_step) * int_step)
        aligned_min = max(int(MIN_WEIGHT), aligned_min)
        pillar_ranges[pillar] = list(range(aligned_min, aligned_max + 1, int_step))

    # Generate all combinations and filter by sum=100
    for combo in itertools.product(*[pillar_ranges[p] for p in pillars]):
        if sum(combo) == int(TOTAL_WEIGHT):
            weights = dict(zip(pillars, [float(v) for v in combo], strict=False))
            combinations.append(weights)

    return combinations


@dataclass
class AccuracyMetrics:
    """Detailed accuracy metrics including bias and MCC."""

    accuracy: float = 0.0
    over_rate: float = 0.0  # Optimistic predictions (predicted findable, was not)
    under_rate: float = 0.0  # Pessimistic predictions (predicted not findable, was)
    correct: int = 0
    over: int = 0  # FP: predicted findable, was not cited
    under: int = 0  # FN: predicted not findable, was cited
    total: int = 0
    true_positives: int = 0  # Predicted findable AND was cited
    true_negatives: int = 0  # Predicted not findable AND was not cited

    @property
    def mcc(self) -> float:
        """
        Matthews Correlation Coefficient - robust metric for imbalanced classes.

        MCC = (TP*TN - FP*FN) / sqrt((TP+FP)*(TP+FN)*(TN+FP)*(TN+FN))

        Returns 0 for trivial classifiers (always-positive or always-negative),
        +1 for perfect classification, -1 for perfectly wrong.
        Unlike bias_adjusted_score, MCC correctly handles class imbalance.
        """
        tp, tn, fp, fn = self.true_positives, self.true_negatives, self.over, self.under
        denominator = (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
        if denominator == 0:
            return 0.0
        return float((tp * tn - fp * fn) / (denominator**0.5))

    @property
    def bias_adjusted_score(self) -> float:
        """
        Legacy bias-adjusted score. Kept for backward compatibility.

        WARNING: This metric rewards "predict all positive" with imbalanced classes.
        Use MCC instead for optimizer scoring.
        """
        if self.total == 0:
            return 0.0
        bias_penalty = 0.5 * abs(self.over_rate - self.under_rate)
        return max(0.0, self.accuracy - bias_penalty)


def _prepare_sample_matrices(
    samples: list,
    pillar_order: list[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Pre-compute numpy arrays from samples for vectorized evaluation.

    Returns:
        pillar_matrix: (N, 7) array of pillar scores (None -> 0.0)
        actuals: (N,) boolean array of obs_cited (was obs_mentioned, but
                 obs_mentioned has 99.8% positive rate making it useless for
                 calibration. obs_cited has ~68% positive / 32% negative.)
        primacy_scores: (N,) array of source_primacy scores (0-100, 0 if missing)
    """
    n = len(samples)
    p = len(pillar_order)
    pillar_matrix = np.zeros((n, p), dtype=np.float64)
    actuals = np.zeros(n, dtype=bool)
    primacy_scores = np.zeros(n, dtype=np.float64)

    for i, sample in enumerate(samples):
        if not sample.pillar_scores:
            continue
        for j, pillar in enumerate(pillar_order):
            val = sample.pillar_scores.get(pillar)
            pillar_matrix[i, j] = val if val is not None else 0.0
        actuals[i] = sample.obs_cited
        ps = sample.pillar_scores.get("source_primacy")
        primacy_scores[i] = ps if ps is not None else 0.0

    return pillar_matrix, actuals, primacy_scores


def _batch_evaluate(
    pillar_matrix: np.ndarray,
    actuals: np.ndarray,
    weight_combos: list[dict[str, float]],
    pillar_order: list[str],
    thresholds: list[int],
    primacy_scores: np.ndarray | None = None,
    primacy_weights: list[float] | None = None,
) -> tuple[dict[str, float], int, float, AccuracyMetrics, float]:
    """
    Vectorized evaluation of all weight+threshold combinations.

    Args:
        pillar_matrix: (N, P) array of pillar scores
        actuals: (N,) boolean array of obs_cited
        weight_combos: List of weight dicts to test
        pillar_order: Order of pillars in matrix columns
        thresholds: Findability thresholds to test
        primacy_scores: Optional (N,) array of source primacy scores (0-100)
        primacy_weights: Optional list of primacy bonus weights to search over

    Returns:
        best_weights, best_threshold, best_score, best_metrics, best_primacy_weight
    """
    n_samples = pillar_matrix.shape[0]
    if n_samples == 0:
        return DEFAULT_WEIGHTS.copy(), 50, 0.0, AccuracyMetrics(), 0.0

    # Convert weight combos to numpy array (C, P)
    weight_array = (
        np.array(
            [[w[p] for p in pillar_order] for w in weight_combos],
            dtype=np.float64,
        )
        / 100.0
    )  # Normalize to 0-1

    # Compute all weighted scores: (C, N) = (C, P) @ (P, N)
    base_scores = weight_array @ pillar_matrix.T  # (C, N)

    # Primacy weights to test (default: just 0)
    pw_list = primacy_weights if primacy_weights else [0.0]
    has_primacy = primacy_scores is not None and any(pw > 0 for pw in pw_list)

    best_score = -1.0
    best_weights = weight_combos[0]
    best_threshold = thresholds[0]
    best_metrics = AccuracyMetrics()
    best_pw = 0.0

    for pw in pw_list:
        if has_primacy and pw > 0:
            # Add primacy bonus: (C, N) + (1, N) broadcast
            primacy_bonus = primacy_scores * (pw / 100.0)  # type: ignore[operator]
            all_scores = base_scores + primacy_bonus[np.newaxis, :]  # type: ignore[index]
        else:
            all_scores = base_scores

        # Pre-compute positive/negative counts for MCC
        n_positive = int(actuals.sum())
        n_negative = n_samples - n_positive

        for threshold in thresholds:
            # Predictions: (C, N) boolean
            predictions = all_scores >= threshold

            # Compare to actuals (broadcast)
            actuals_row = actuals[np.newaxis, :]  # (1, N)
            over_mask = predictions & ~actuals_row  # FP
            under_mask = ~predictions & actuals_row  # FN

            fp = over_mask.sum(axis=1)  # (C,)
            fn = under_mask.sum(axis=1)
            tp = n_positive - fn  # TP = total positives - false negatives
            tn = n_negative - fp  # TN = total negatives - false positives

            accuracy = (tp + tn) / n_samples
            over_rate = fp / n_samples
            under_rate = fn / n_samples

            # Matthews Correlation Coefficient (vectorized)
            # MCC = (TP*TN - FP*FN) / sqrt((TP+FP)*(TP+FN)*(TN+FP)*(TN+FN))
            numerator = (tp * tn - fp * fn).astype(np.float64)
            denom_parts = (
                (tp + fp).astype(np.float64)
                * (tp + fn).astype(np.float64)
                * (tn + fp).astype(np.float64)
                * (tn + fn).astype(np.float64)
            )
            # Avoid division by zero (happens when all predictions are same class)
            denom = np.sqrt(np.maximum(denom_parts, 1e-10))
            scores = numerator / denom
            # Clamp MCC to [-1, 1] (numerical precision)
            scores = np.clip(scores, -1.0, 1.0)

            # Find best in this threshold
            best_idx = np.argmax(scores)
            if scores[best_idx] > best_score:
                best_score = float(scores[best_idx])
                best_weights = weight_combos[best_idx]
                best_threshold = threshold
                best_pw = pw
                best_metrics = AccuracyMetrics(
                    accuracy=float(accuracy[best_idx]),
                    over_rate=float(over_rate[best_idx]),
                    under_rate=float(under_rate[best_idx]),
                    correct=int(tp[best_idx] + tn[best_idx]),
                    over=int(fp[best_idx]),
                    under=int(fn[best_idx]),
                    total=n_samples,
                    true_positives=int(tp[best_idx]),
                    true_negatives=int(tn[best_idx]),
                )

    return best_weights, best_threshold, best_score, best_metrics, best_pw


def _calculate_weighted_metrics(
    samples: list[CalibrationSample],
    weights: dict[str, float],
    threshold: int = 50,
    primacy_weight: float = 0.0,
) -> AccuracyMetrics:
    """
    Calculate prediction accuracy and bias metrics using given weights.

    This simulates what the prediction would have been with different weights,
    then compares to actual observation outcomes.

    Args:
        samples: Calibration samples with pillar_scores
        weights: Weight dict to test
        threshold: Findability threshold (weighted score >= threshold = findable)
        primacy_weight: Bonus weight for source_primacy (0-20, added independently)

    Returns:
        AccuracyMetrics with accuracy, over_rate, under_rate
    """
    metrics = AccuracyMetrics()

    if not samples:
        return metrics

    for sample in samples:
        if not sample.pillar_scores:
            continue

        # Skip samples with insufficient pillar coverage (need at least 70% of weight)
        covered_weight = sum(
            DEFAULT_WEIGHTS[p] for p in weights if sample.pillar_scores.get(p) is not None
        )
        if covered_weight < 70.0:
            continue

        # Calculate weighted score using provided weights
        weighted_score = 0.0
        for pillar, weight in weights.items():
            pillar_score = sample.pillar_scores.get(pillar)
            if pillar_score is None:
                pillar_score = 0.0
            weighted_score += pillar_score * (weight / 100.0)

        # Add source primacy bonus (independent of sum-to-100 constraint)
        if primacy_weight > 0:
            primacy_score = sample.pillar_scores.get("source_primacy")
            if primacy_score is not None:
                weighted_score += primacy_score * (primacy_weight / 100.0)

        # Determine predicted answerability based on weighted score
        predicted_findable = weighted_score >= threshold

        # Compare to actual observation outcome
        # Use obs_cited (not obs_mentioned) as ground truth:
        # obs_mentioned is 99.8% positive (useless for calibration).
        # obs_cited has 68/32 split — much better signal.
        was_cited = sample.obs_cited

        metrics.total += 1

        if predicted_findable and was_cited:
            metrics.correct += 1
            metrics.true_positives += 1
        elif not predicted_findable and not was_cited:
            metrics.correct += 1
            metrics.true_negatives += 1
        elif predicted_findable and not was_cited:
            # Over-prediction (optimistic): predicted findable but wasn't cited
            metrics.over += 1
        else:
            # Under-prediction (pessimistic): predicted not findable but was cited
            metrics.under += 1

    if metrics.total > 0:
        metrics.accuracy = metrics.correct / metrics.total
        metrics.over_rate = metrics.over / metrics.total
        metrics.under_rate = metrics.under / metrics.total

    return metrics


def _calculate_weighted_accuracy(
    samples: list[CalibrationSample],
    weights: dict[str, float],
) -> float:
    """
    Calculate prediction accuracy using given weights.

    Legacy wrapper for backward compatibility.
    """
    return _calculate_weighted_metrics(samples, weights).accuracy


async def optimize_answerability_thresholds(
    window_days: int = 60,
    min_samples: int = 200,
    holdout_pct: float = 0.2,
    min_improvement: float = 0.02,
) -> OptimizationResult:
    """
    Optimize answerability thresholds using grid search.

    Thresholds determine when a question is classified as:
    - fully_answerable (score >= fully_threshold)
    - partially_answerable (partially_threshold <= score < fully_threshold)
    - not_answerable (score < partially_threshold)

    Args:
        window_days: Number of days to look back for samples
        min_samples: Minimum samples required for optimization
        holdout_pct: Percentage of samples to hold out for validation
        min_improvement: Minimum accuracy improvement required

    Returns:
        OptimizationResult with best thresholds and metrics
    """
    result = OptimizationResult(min_improvement_threshold=min_improvement)

    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session_maker() as db:
        # Load calibration samples
        samples_result = await db.execute(
            select(CalibrationSample)
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .order_by(CalibrationSample.created_at)
        )
        samples = list(samples_result.scalars().all())

        if len(samples) < min_samples:
            result.errors.append(f"Insufficient samples: {len(samples)} < {min_samples} required")
            logger.warning(
                "threshold_optimization_skipped_insufficient_samples",
                samples=len(samples),
                min_required=min_samples,
            )
            return result

        # Split into training and holdout
        holdout_size = int(len(samples) * holdout_pct)
        training_samples = samples[:-holdout_size] if holdout_size > 0 else samples
        holdout_samples = samples[-holdout_size:] if holdout_size > 0 else []

        result.training_sample_count = len(training_samples)
        result.holdout_sample_count = len(holdout_samples)

        # Default thresholds
        default_thresholds = {
            "fully_answerable": 0.70,
            "partially_answerable": 0.30,
        }

        # Calculate baseline accuracy
        result.baseline_accuracy = _calculate_threshold_accuracy(
            training_samples, default_thresholds
        )

        # Generate threshold combinations
        fully_values = [
            round(v, 2) for v in _frange(MIN_FULLY_ANSWERABLE, MAX_FULLY_ANSWERABLE, THRESHOLD_STEP)
        ]
        partially_values = [
            round(v, 2)
            for v in _frange(MIN_PARTIALLY_ANSWERABLE, MAX_PARTIALLY_ANSWERABLE, THRESHOLD_STEP)
        ]

        combinations_tested = 0
        best_accuracy = result.baseline_accuracy
        best_thresholds = default_thresholds.copy()

        for fully in fully_values:
            for partially in partially_values:
                # Constraint: partially < fully
                if partially >= fully:
                    continue

                thresholds = {
                    "fully_answerable": fully,
                    "partially_answerable": partially,
                }

                accuracy = _calculate_threshold_accuracy(training_samples, thresholds)
                combinations_tested += 1

                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_thresholds = thresholds.copy()

        result.combinations_tested = combinations_tested
        result.best_accuracy = best_accuracy
        result.best_thresholds = best_thresholds
        result.improvement = best_accuracy - result.baseline_accuracy
        result.is_improvement = result.improvement > 0

        # Validate on holdout set
        if holdout_samples:
            result.holdout_accuracy = _calculate_threshold_accuracy(
                holdout_samples, best_thresholds
            )
        else:
            result.holdout_accuracy = result.best_accuracy

        result.improvement_sufficient = result.improvement >= min_improvement

        logger.info(
            "threshold_optimization_completed",
            baseline_accuracy=result.baseline_accuracy,
            best_accuracy=result.best_accuracy,
            improvement=result.improvement,
            holdout_accuracy=result.holdout_accuracy,
            improvement_sufficient=result.improvement_sufficient,
            best_thresholds=result.best_thresholds,
        )

        return result


def _calculate_threshold_accuracy(
    samples: list[CalibrationSample],
    thresholds: dict[str, float],
) -> float:
    """
    Calculate prediction accuracy using given thresholds.

    Args:
        samples: Calibration samples
        thresholds: Dict with 'fully_answerable' and 'partially_answerable'

    Returns:
        Accuracy as float (0-1)
    """
    if not samples:
        return 0.0

    fully_threshold = thresholds["fully_answerable"]
    partially_threshold = thresholds["partially_answerable"]

    correct = 0
    total = 0

    for sample in samples:
        score = sample.sim_score

        # Classify based on thresholds
        if score >= fully_threshold:
            predicted = "fully_answerable"
        elif score >= partially_threshold:
            predicted = "partially_answerable"
        else:
            predicted = "not_answerable"

        # Compare to actual outcome
        # - mentioned AND cited -> likely fully answerable prediction was correct
        # - mentioned but not cited -> partially answerable
        # - not mentioned -> not answerable
        if sample.obs_cited:
            actual = "fully_answerable"
        elif sample.obs_mentioned:
            actual = "partially_answerable"
        else:
            actual = "not_answerable"

        if predicted == actual:
            correct += 1
        # Also count adjacent predictions as partially correct for smoothing
        elif _are_adjacent(predicted, actual):
            correct += 0.5  # type: ignore[assignment]

        total += 1

    return correct / total if total > 0 else 0.0


def _are_adjacent(pred: str, actual: str) -> bool:
    """Check if two answerability levels are adjacent."""
    levels = ["not_answerable", "partially_answerable", "fully_answerable"]
    try:
        pred_idx = levels.index(pred)
        actual_idx = levels.index(actual)
        return abs(pred_idx - actual_idx) == 1
    except ValueError:
        return False


def _frange(start: float, stop: float, step: float) -> Iterator[float]:
    """Generate floats in a range (like range() but for floats)."""
    while start <= stop:
        yield start
        start += step


async def validate_config_improvement(
    config_id: uuid.UUID,
    window_days: int = 30,
    min_samples: int = 100,
) -> dict:
    """
    Validate a configuration against recent samples.

    Use this to validate a candidate config before activation.

    Args:
        config_id: CalibrationConfig ID to validate
        window_days: Number of days for validation window
        min_samples: Minimum samples required

    Returns:
        Dict with validation results
    """
    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session_maker() as db:
        # Load the config
        config_result = await db.execute(
            select(CalibrationConfig).where(CalibrationConfig.id == config_id)
        )
        config = config_result.scalar_one_or_none()

        if not config:
            return {
                "valid": False,
                "error": "Config not found",
            }

        # Load samples
        samples_result = await db.execute(
            select(CalibrationSample)
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .where(CalibrationSample.pillar_scores.isnot(None))
        )
        samples = list(samples_result.scalars().all())

        if len(samples) < min_samples:
            return {
                "valid": False,
                "error": f"Insufficient samples: {len(samples)} < {min_samples}",
                "sample_count": len(samples),
            }

        # Get config weights
        config_weights = config.weights

        # Calculate accuracy with config weights
        config_accuracy = _calculate_weighted_accuracy(samples, config_weights)

        # Calculate baseline accuracy
        baseline_accuracy = _calculate_weighted_accuracy(samples, DEFAULT_WEIGHTS)

        improvement = config_accuracy - baseline_accuracy

        return {
            "valid": True,
            "config_id": str(config_id),
            "config_name": config.name,
            "config_accuracy": round(config_accuracy, 4),
            "baseline_accuracy": round(baseline_accuracy, 4),
            "improvement": round(improvement, 4),
            "is_improvement": improvement > 0,
            "sample_count": len(samples),
            "window_days": window_days,
        }


async def optimize_per_site_type(
    site_types: list[str] | None = None,
    min_samples: int = 50,
    window_days: int = 90,
) -> dict[str, OptimizationResult]:
    """
    Train separate weight profiles for each site type.

    Runs optimize_pillar_weights for each site type that has enough samples.
    Site types with too few samples fall back to the global weights.

    Args:
        site_types: Optional list of site types to train. If None, trains all.
        min_samples: Minimum samples per site type (lower than global since subsets)
        window_days: Number of days to look back

    Returns:
        Dict mapping site_type -> OptimizationResult
    """
    from worker.extraction.site_type import SiteType

    types_to_train = site_types or [st.value for st in SiteType if st != SiteType.MIXED]

    results: dict[str, OptimizationResult] = {}

    for st in types_to_train:
        logger.info("optimizing_site_type_weights", site_type=st)
        result = await optimize_pillar_weights(
            window_days=window_days,
            min_samples=min_samples,
            site_type=st,
            coarse_then_fine=True,
        )
        results[st] = result

        if result.errors:
            logger.info(
                "site_type_optimization_skipped",
                site_type=st,
                reason=result.errors[0],
            )
        else:
            logger.info(
                "site_type_optimization_complete",
                site_type=st,
                best_accuracy=round(result.best_accuracy, 4),
                improvement=round(result.improvement or 0, 4),
            )

    return results
