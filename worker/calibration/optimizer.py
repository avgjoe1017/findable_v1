"""Calibration optimizer using grid search.

This module provides weight and threshold optimization without ML infrastructure:
- Grid search over weight combinations (each pillar 5-35%, sum=100)
- Threshold optimization for answerability predictions
- Holdout validation to prevent overfitting
"""

import itertools
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

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

    # Performance metrics
    best_accuracy: float = 0.0
    baseline_accuracy: float = 0.0
    improvement: float = 0.0

    # Validation metrics
    holdout_accuracy: float = 0.0
    holdout_sample_count: int = 0

    # Search stats
    combinations_tested: int = 0
    training_sample_count: int = 0

    # Status
    is_improvement: bool = False
    improvement_sufficient: bool = False  # True if > min_improvement threshold
    min_improvement_threshold: float = 0.02  # 2% default

    # Errors encountered
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "best_weights": self.best_weights,
            "best_thresholds": self.best_thresholds,
            "best_accuracy": round(self.best_accuracy, 4),
            "baseline_accuracy": round(self.baseline_accuracy, 4),
            "improvement": round(self.improvement, 4),
            "holdout_accuracy": round(self.holdout_accuracy, 4),
            "holdout_sample_count": self.holdout_sample_count,
            "combinations_tested": self.combinations_tested,
            "training_sample_count": self.training_sample_count,
            "is_improvement": self.is_improvement,
            "improvement_sufficient": self.improvement_sufficient,
            "min_improvement_threshold": self.min_improvement_threshold,
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


async def optimize_pillar_weights(
    window_days: int = 60,
    min_samples: int = 200,
    holdout_pct: float = 0.2,
    min_improvement: float = 0.02,
    step: float = WEIGHT_STEP,
    coarse_then_fine: bool = True,
) -> OptimizationResult:
    """
    Optimize pillar weights using grid search over historical samples.

    This function:
    1. Loads calibration samples from the specified window
    2. Splits into training (80%) and holdout (20%) sets
    3. Tests all valid weight combinations against training set
    4. Validates best config against holdout set
    5. Returns result if improvement exceeds threshold

    Args:
        window_days: Number of days to look back for samples
        min_samples: Minimum samples required for optimization
        holdout_pct: Percentage of samples to hold out for validation
        min_improvement: Minimum accuracy improvement required (default 2%)
        step: Step size for grid search (default 5, use 10 for faster coarse search)
        coarse_then_fine: If True, do coarse search (step=10) then fine search (step=5)
                          around the best coarse result

    Returns:
        OptimizationResult with best weights and metrics
    """
    result = OptimizationResult(min_improvement_threshold=min_improvement)

    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session_maker() as db:
        # Load calibration samples with pillar scores
        samples_result = await db.execute(
            select(CalibrationSample)
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .where(CalibrationSample.pillar_scores.isnot(None))
            .order_by(CalibrationSample.created_at)
        )
        samples = list(samples_result.scalars().all())

        if len(samples) < min_samples:
            result.errors.append(f"Insufficient samples: {len(samples)} < {min_samples} required")
            logger.warning(
                "weight_optimization_skipped_insufficient_samples",
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

        logger.info(
            "weight_optimization_starting",
            total_samples=len(samples),
            training_samples=len(training_samples),
            holdout_samples=len(holdout_samples),
            coarse_then_fine=coarse_then_fine,
        )

        # Calculate baseline accuracy with default weights
        result.baseline_accuracy = _calculate_weighted_accuracy(training_samples, DEFAULT_WEIGHTS)

        best_accuracy = result.baseline_accuracy
        best_weights = DEFAULT_WEIGHTS.copy()
        total_combinations_tested = 0

        if coarse_then_fine:
            # Phase 1: Try coarse search with step=10
            coarse_combinations = generate_weight_combinations(step=10)

            # With 7 pillars, step=10 may produce no valid combinations
            # Fall back to step=5 if needed
            if len(coarse_combinations) == 0:
                logger.info("coarse_search_empty_using_full_search", step=5)
                combinations = generate_weight_combinations(step=5)
                total_combinations_tested = len(combinations)

                for weights in combinations:
                    accuracy = _calculate_weighted_accuracy(training_samples, weights)
                    if accuracy > best_accuracy:
                        best_accuracy = accuracy
                        best_weights = weights.copy()
            else:
                total_combinations_tested += len(coarse_combinations)

                for weights in coarse_combinations:
                    accuracy = _calculate_weighted_accuracy(training_samples, weights)
                    if accuracy > best_accuracy:
                        best_accuracy = accuracy
                        best_weights = weights.copy()

                # Phase 2: Fine search around best coarse result with step=5
                fine_combinations = _generate_fine_search_combinations(best_weights, step=5)
                total_combinations_tested += len(fine_combinations)

                for weights in fine_combinations:
                    accuracy = _calculate_weighted_accuracy(training_samples, weights)
                    if accuracy > best_accuracy:
                        best_accuracy = accuracy
                        best_weights = weights.copy()

                logger.info(
                    "coarse_fine_search_completed",
                    coarse_combinations=len(coarse_combinations),
                    fine_combinations=len(fine_combinations),
                    total_tested=total_combinations_tested,
                )
        else:
            # Single-phase search with specified step
            combinations = generate_weight_combinations(step=step)
            total_combinations_tested = len(combinations)

            for weights in combinations:
                accuracy = _calculate_weighted_accuracy(training_samples, weights)
                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_weights = weights.copy()

        result.combinations_tested = total_combinations_tested

        result.best_accuracy = best_accuracy
        result.best_weights = best_weights
        result.improvement = best_accuracy - result.baseline_accuracy
        result.is_improvement = result.improvement > 0

        # Validate on holdout set
        if holdout_samples:
            result.holdout_accuracy = _calculate_weighted_accuracy(holdout_samples, best_weights)
        else:
            result.holdout_accuracy = result.best_accuracy

        # Check if improvement is sufficient
        result.improvement_sufficient = result.improvement >= min_improvement

        logger.info(
            "weight_optimization_completed",
            baseline_accuracy=result.baseline_accuracy,
            best_accuracy=result.best_accuracy,
            improvement=result.improvement,
            holdout_accuracy=result.holdout_accuracy,
            improvement_sufficient=result.improvement_sufficient,
            best_weights=result.best_weights,
        )

        return result


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

    # Generate ranges for each pillar around the center
    pillar_ranges = {}
    for pillar in pillars:
        center = center_weights[pillar]
        min_val = max(MIN_WEIGHT, center - radius)
        max_val = min(MAX_WEIGHT, center + radius)
        pillar_ranges[pillar] = list(range(int(min_val), int(max_val) + 1, int(step)))

    # Generate all combinations and filter by sum=100
    for combo in itertools.product(*[pillar_ranges[p] for p in pillars]):
        if sum(combo) == int(TOTAL_WEIGHT):
            weights = dict(zip(pillars, [float(v) for v in combo], strict=False))
            combinations.append(weights)

    return combinations


def _calculate_weighted_accuracy(
    samples: list[CalibrationSample],
    weights: dict[str, float],
) -> float:
    """
    Calculate prediction accuracy using given weights.

    This simulates what the prediction would have been with different weights,
    then compares to actual observation outcomes.

    Args:
        samples: Calibration samples with pillar_scores
        weights: Weight dict to test

    Returns:
        Accuracy as float (0-1)
    """
    if not samples:
        return 0.0

    correct = 0
    total = 0

    for sample in samples:
        if not sample.pillar_scores:
            continue

        # Calculate weighted score using provided weights
        weighted_score = 0.0
        for pillar, weight in weights.items():
            pillar_score = sample.pillar_scores.get(pillar, 0.0)
            weighted_score += pillar_score * (weight / 100.0)

        # Determine predicted answerability based on weighted score
        # (simplified: higher score = higher predicted findability)
        predicted_findable = weighted_score >= 50  # Threshold for "findable"

        # Compare to actual observation outcome
        was_mentioned = sample.obs_mentioned

        # Prediction is correct if:
        # - Predicted findable AND was mentioned
        # - Predicted not findable AND was not mentioned
        if predicted_findable == was_mentioned:
            correct += 1

        total += 1

    return correct / total if total > 0 else 0.0


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
            correct += 0.5

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


def _frange(start: float, stop: float, step: float):
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
