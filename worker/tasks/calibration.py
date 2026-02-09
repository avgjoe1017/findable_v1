"""Calibration tasks for learning from observation outcomes.

This module provides tasks for:
- Collecting calibration samples from completed runs with observation
- Analyzing calibration data to compute accuracy metrics
- Detecting calibration drift

The calibration system allows the Findable Score to learn from real AI
observation outcomes, improving prediction accuracy over time.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import structlog
from sqlalchemy import func, select

from api.database import async_session_maker
from api.models import Run, Site
from api.models.calibration import (
    CalibrationConfig,
    CalibrationDriftAlert,
    CalibrationExperiment,
    CalibrationSample,
    DriftAlertStatus,
    DriftType,
    ExperimentStatus,
    OutcomeMatch,
)
from worker.calibration.experiment import ExperimentArm, get_experiment_arm
from worker.observation.comparison import (
    OutcomeMatch as CompOutcomeMatch,
)
from worker.observation.comparison import (
    SimulationObservationComparator,
)
from worker.observation.models import ObservationRun
from worker.simulation.runner import SimulationResult

logger = structlog.get_logger(__name__)


async def collect_calibration_samples(
    run_id: uuid.UUID,
    simulation_result: SimulationResult,
    observation_run: ObservationRun,
    pillar_scores: dict[str, float] | None = None,
    site_type: str | None = None,
) -> int:
    """
    Collect calibration samples from a completed run with observation.

    This should be called after both simulation and observation complete.
    It pairs each question's simulation prediction with the observation
    outcome to build the calibration dataset.

    Args:
        run_id: The run ID
        simulation_result: Simulation result with question predictions
        observation_run: Observation run with ground truth outcomes
        pillar_scores: Optional pillar scores at time of sample

    Returns:
        Number of samples collected
    """
    logger.info(
        "calibration_sample_collection_starting",
        run_id=str(run_id),
        questions=len(simulation_result.question_results),
    )

    # Compare simulation with observation
    comparator = SimulationObservationComparator()
    comparison = comparator.compare(simulation_result, observation_run)

    # Get site info for context
    async with async_session_maker() as db:
        run_result = await db.execute(select(Run).join(Site).where(Run.id == run_id))
        run = run_result.scalar_one_or_none()

        if not run:
            logger.error("run_not_found", run_id=str(run_id))
            return 0

        site_id = run.site_id

        # Get site for industry context
        site_result = await db.execute(select(Site).where(Site.id == site_id))
        site = site_result.scalar_one_or_none()
        domain_industry = None
        if site and site.industry_tags:
            domain_industry = site.industry_tags[0] if site.industry_tags else None

        # Get active calibration config ID
        config_result = await db.execute(
            select(CalibrationConfig).where(CalibrationConfig.is_active == True)  # noqa: E712
        )
        active_config = config_result.scalar_one_or_none()
        config_id = active_config.id if active_config else None

        # Check for running experiments and assign arm
        # If multiple experiments running, use the most recently started one
        experiment_id = None
        experiment_arm = None
        exp_result = await db.execute(
            select(CalibrationExperiment)
            .where(CalibrationExperiment.status == ExperimentStatus.RUNNING.value)
            .order_by(CalibrationExperiment.started_at.desc())
            .limit(1)
        )
        active_experiment = exp_result.scalar_one_or_none()

        if active_experiment:
            # Assign site to experiment arm deterministically
            arm = get_experiment_arm(site_id, active_experiment.treatment_allocation)
            experiment_id = active_experiment.id
            experiment_arm = arm.value

            # Use the config for this arm
            if arm == ExperimentArm.TREATMENT:
                config_id = active_experiment.treatment_config_id
            else:
                config_id = active_experiment.control_config_id

            logger.info(
                "experiment_arm_assigned",
                site_id=str(site_id),
                experiment_id=str(experiment_id),
                arm=experiment_arm,
            )

        # Build samples from comparisons
        samples = []
        sim_map = {r.question_id: r for r in simulation_result.question_results}

        for comp in comparison.comparisons:
            sim_result = sim_map.get(comp.question_id)
            if not sim_result:
                continue

            # Map outcome match to our enum
            outcome_match_value = _map_outcome_match(comp.outcome_match)

            # Per-question pillar scores: copy site-level scores and override
            # retrieval + coverage with per-question simulation data.
            # This gives the optimizer within-domain variation to learn from.
            question_pillar_scores = dict(pillar_scores) if pillar_scores else {}
            if sim_result:
                # Retrieval: per-question simulation score (0-1 -> 0-100)
                question_pillar_scores["retrieval"] = round(sim_result.score * 100, 1)
                # Coverage: per-question answerability mapped to 0-100
                _answerability_to_score = {
                    "fully_answerable": 100.0,
                    "partially_answerable": 50.0,
                    "not_answerable": 0.0,
                    "contradictory": 25.0,
                }
                ans_val = (
                    sim_result.answerability.value if sim_result.answerability else "not_answerable"
                )
                question_pillar_scores["coverage"] = _answerability_to_score.get(ans_val, 0.0)

            sample = CalibrationSample(
                id=uuid.uuid4(),
                site_id=site_id,
                run_id=run_id,
                question_id=comp.question_id,
                # Simulation prediction
                sim_answerability=(
                    sim_result.answerability.value if sim_result.answerability else "unknown"
                ),
                sim_score=sim_result.score,
                sim_signals_found=comp.sim_signals_found,
                sim_signals_total=comp.sim_signals_total,
                sim_relevance_score=(
                    sim_result.context.avg_relevance_score if sim_result.context else 0.0
                ),
                # Observation outcome
                obs_mentioned=comp.obs_mentioned,
                obs_cited=comp.obs_cited,
                obs_sentiment=comp.obs_sentiment or None,
                obs_confidence=comp.obs_confidence or None,
                obs_provider=observation_run.provider.value,
                obs_model=observation_run.model,
                # Derived
                outcome_match=outcome_match_value,
                prediction_accurate=comp.prediction_accurate,
                # Context
                question_category=sim_result.category.value if sim_result.category else "unknown",
                question_difficulty=(
                    sim_result.difficulty.value if sim_result.difficulty else "medium"
                ),
                question_text=comp.question_text,
                domain_industry=domain_industry,
                site_type=site_type,
                pillar_scores=question_pillar_scores,
                config_id=config_id,
                experiment_id=experiment_id,
                experiment_arm=experiment_arm,
            )
            samples.append(sample)

        # Bulk insert samples
        if samples:
            for sample in samples:
                db.add(sample)
            await db.commit()

        logger.info(
            "calibration_samples_collected",
            run_id=str(run_id),
            samples_collected=len(samples),
            prediction_accuracy=comparison.prediction_accuracy,
        )

        return len(samples)


def _map_outcome_match(comp_match: CompOutcomeMatch) -> str:
    """Map comparison OutcomeMatch to calibration OutcomeMatch value."""
    mapping = {
        CompOutcomeMatch.CORRECT: OutcomeMatch.CORRECT.value,
        CompOutcomeMatch.OPTIMISTIC: OutcomeMatch.OPTIMISTIC.value,
        CompOutcomeMatch.PESSIMISTIC: OutcomeMatch.PESSIMISTIC.value,
        CompOutcomeMatch.UNKNOWN: OutcomeMatch.UNKNOWN.value,
    }
    return mapping.get(comp_match, OutcomeMatch.UNKNOWN.value)


async def analyze_calibration_data(
    window_days: int = 30,
    min_samples: int = 100,
) -> dict:
    """
    Analyze accumulated calibration samples to compute metrics.

    Args:
        window_days: Number of days to look back
        min_samples: Minimum samples required for analysis

    Returns:
        Dict with analysis results including:
        - total_samples: Number of samples in window
        - prediction_accuracy: Overall accuracy percentage
        - optimism_bias: Percentage of optimistic predictions
        - pessimism_bias: Percentage of pessimistic predictions
        - accuracy_by_category: Dict of category -> accuracy
        - accuracy_by_difficulty: Dict of difficulty -> accuracy
    """
    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session_maker() as db:
        # Count total samples
        total_count_result = await db.execute(
            select(func.count(CalibrationSample.id)).where(
                CalibrationSample.created_at >= window_start
            )
        )
        total_samples = total_count_result.scalar() or 0

        if total_samples < min_samples:
            logger.warning(
                "insufficient_calibration_samples",
                total_samples=total_samples,
                min_required=min_samples,
            )
            return {
                "total_samples": total_samples,
                "sufficient_data": False,
                "min_required": min_samples,
            }

        # Count by outcome
        outcome_counts_result = await db.execute(
            select(
                CalibrationSample.outcome_match,
                func.count(CalibrationSample.id),
            )
            .where(CalibrationSample.created_at >= window_start)
            .group_by(CalibrationSample.outcome_match)
        )
        outcome_counts: dict[str, int] = dict(outcome_counts_result.fetchall())  # type: ignore[arg-type]

        correct = outcome_counts.get(OutcomeMatch.CORRECT.value, 0)
        optimistic = outcome_counts.get(OutcomeMatch.OPTIMISTIC.value, 0)
        pessimistic = outcome_counts.get(OutcomeMatch.PESSIMISTIC.value, 0)
        unknown = outcome_counts.get(OutcomeMatch.UNKNOWN.value, 0)

        # Calculate rates (excluding unknown)
        known_samples = total_samples - unknown
        prediction_accuracy = correct / known_samples if known_samples > 0 else 0.0
        optimism_bias = optimistic / known_samples if known_samples > 0 else 0.0
        pessimism_bias = pessimistic / known_samples if known_samples > 0 else 0.0

        # Accuracy by category
        from sqlalchemy import Integer

        category_results = await db.execute(
            select(
                CalibrationSample.question_category,
                func.count(CalibrationSample.id).label("total"),
                func.sum(func.cast(CalibrationSample.prediction_accurate, Integer)).label(
                    "accurate"
                ),
            )
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .group_by(CalibrationSample.question_category)
        )
        accuracy_by_category = {}
        for row in category_results.fetchall():
            cat_total = row[1] or 0
            cat_accurate = row[2] or 0
            if cat_total > 0:
                accuracy_by_category[row[0]] = cat_accurate / cat_total

        # Accuracy by difficulty
        difficulty_results = await db.execute(
            select(
                CalibrationSample.question_difficulty,
                func.count(CalibrationSample.id).label("total"),
                func.sum(func.cast(CalibrationSample.prediction_accurate, Integer)).label(
                    "accurate"
                ),
            )
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .group_by(CalibrationSample.question_difficulty)
        )
        accuracy_by_difficulty = {}
        for row in difficulty_results.fetchall():
            diff_total = row[1] or 0
            diff_accurate = row[2] or 0
            if diff_total > 0:
                accuracy_by_difficulty[row[0]] = diff_accurate / diff_total

        logger.info(
            "calibration_analysis_completed",
            total_samples=total_samples,
            prediction_accuracy=prediction_accuracy,
            optimism_bias=optimism_bias,
            pessimism_bias=pessimism_bias,
        )

        return {
            "total_samples": total_samples,
            "sufficient_data": True,
            "known_samples": known_samples,
            "prediction_accuracy": prediction_accuracy,
            "optimism_bias": optimism_bias,
            "pessimism_bias": pessimism_bias,
            "outcome_counts": {
                "correct": correct,
                "optimistic": optimistic,
                "pessimistic": pessimistic,
                "unknown": unknown,
            },
            "accuracy_by_category": accuracy_by_category,
            "accuracy_by_difficulty": accuracy_by_difficulty,
            "window_start": window_start.isoformat(),
            "window_days": window_days,
        }


async def check_calibration_drift(
    baseline_window_days: int = 30,
    recent_window_days: int = 7,
    accuracy_threshold: float = 0.10,
    bias_threshold: float = 0.20,
    min_samples: int = 50,
) -> list[CalibrationDriftAlert]:
    """
    Check for calibration drift by comparing recent samples to baseline.

    Args:
        baseline_window_days: Days for baseline window
        recent_window_days: Days for recent window
        accuracy_threshold: Alert if accuracy drops by this much
        bias_threshold: Alert if bias exceeds this level
        min_samples: Minimum samples in recent window to check

    Returns:
        List of new drift alerts created
    """
    now = datetime.now(UTC)
    recent_start = now - timedelta(days=recent_window_days)
    baseline_start = now - timedelta(days=baseline_window_days)
    baseline_end = recent_start  # Baseline excludes recent window

    alerts = []

    async with async_session_maker() as db:
        # Get recent window stats
        recent_stats = await _get_window_stats(db, recent_start, now)
        if recent_stats["total"] < min_samples:
            logger.info(
                "drift_check_skipped_insufficient_samples",
                recent_samples=recent_stats["total"],
                min_required=min_samples,
            )
            return []

        # Get baseline stats
        baseline_stats = await _get_window_stats(db, baseline_start, baseline_end)
        if baseline_stats["total"] < min_samples:
            logger.info(
                "drift_check_skipped_insufficient_baseline",
                baseline_samples=baseline_stats["total"],
                min_required=min_samples,
            )
            return []

        # Check accuracy drift
        accuracy_drift = baseline_stats["accuracy"] - recent_stats["accuracy"]
        if accuracy_drift > accuracy_threshold:
            alert = CalibrationDriftAlert(
                id=uuid.uuid4(),
                drift_type=DriftType.ACCURACY.value,
                expected_value=baseline_stats["accuracy"],
                observed_value=recent_stats["accuracy"],
                drift_magnitude=accuracy_drift,
                sample_window_start=recent_start,
                sample_window_end=now,
                sample_count=recent_stats["total"],
                baseline_window_start=baseline_start,
                baseline_window_end=baseline_end,
                baseline_sample_count=baseline_stats["total"],
                status=DriftAlertStatus.OPEN.value,
            )
            db.add(alert)
            alerts.append(alert)
            logger.warning(
                "calibration_drift_detected",
                drift_type="accuracy",
                expected=baseline_stats["accuracy"],
                observed=recent_stats["accuracy"],
                magnitude=accuracy_drift,
            )

        # Check optimism bias drift
        if recent_stats["optimism_bias"] > bias_threshold:
            alert = CalibrationDriftAlert(
                id=uuid.uuid4(),
                drift_type=DriftType.OPTIMISM.value,
                expected_value=bias_threshold,
                observed_value=recent_stats["optimism_bias"],
                drift_magnitude=recent_stats["optimism_bias"] - bias_threshold,
                sample_window_start=recent_start,
                sample_window_end=now,
                sample_count=recent_stats["total"],
                baseline_window_start=baseline_start,
                baseline_window_end=baseline_end,
                baseline_sample_count=baseline_stats["total"],
                status=DriftAlertStatus.OPEN.value,
            )
            db.add(alert)
            alerts.append(alert)
            logger.warning(
                "calibration_drift_detected",
                drift_type="optimism",
                threshold=bias_threshold,
                observed=recent_stats["optimism_bias"],
            )

        # Check pessimism bias drift
        if recent_stats["pessimism_bias"] > bias_threshold:
            alert = CalibrationDriftAlert(
                id=uuid.uuid4(),
                drift_type=DriftType.PESSIMISM.value,
                expected_value=bias_threshold,
                observed_value=recent_stats["pessimism_bias"],
                drift_magnitude=recent_stats["pessimism_bias"] - bias_threshold,
                sample_window_start=recent_start,
                sample_window_end=now,
                sample_count=recent_stats["total"],
                baseline_window_start=baseline_start,
                baseline_window_end=baseline_end,
                baseline_sample_count=baseline_stats["total"],
                status=DriftAlertStatus.OPEN.value,
            )
            db.add(alert)
            alerts.append(alert)
            logger.warning(
                "calibration_drift_detected",
                drift_type="pessimism",
                threshold=bias_threshold,
                observed=recent_stats["pessimism_bias"],
            )

        if alerts:
            await db.commit()

        logger.info(
            "drift_check_completed",
            alerts_created=len(alerts),
            recent_accuracy=recent_stats["accuracy"],
            baseline_accuracy=baseline_stats["accuracy"],
        )

        return alerts


async def _get_window_stats(db: "Any", start: datetime, end: datetime) -> dict:
    """Get statistics for a time window."""
    # Count by outcome
    result = await db.execute(
        select(
            CalibrationSample.outcome_match,
            func.count(CalibrationSample.id),
        )
        .where(CalibrationSample.created_at >= start)
        .where(CalibrationSample.created_at < end)
        .group_by(CalibrationSample.outcome_match)
    )
    counts = dict(result.fetchall())

    total = sum(counts.values())
    correct = counts.get(OutcomeMatch.CORRECT.value, 0)
    optimistic = counts.get(OutcomeMatch.OPTIMISTIC.value, 0)
    pessimistic = counts.get(OutcomeMatch.PESSIMISTIC.value, 0)
    unknown = counts.get(OutcomeMatch.UNKNOWN.value, 0)

    known = total - unknown

    return {
        "total": total,
        "known": known,
        "correct": correct,
        "optimistic": optimistic,
        "pessimistic": pessimistic,
        "accuracy": correct / known if known > 0 else 0.0,
        "optimism_bias": optimistic / known if known > 0 else 0.0,
        "pessimism_bias": pessimistic / known if known > 0 else 0.0,
    }


async def get_active_calibration_config() -> CalibrationConfig | None:
    """
    Get the currently active calibration configuration.

    Returns:
        Active CalibrationConfig or None if using defaults
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(CalibrationConfig).where(CalibrationConfig.is_active == True)  # noqa: E712
        )
        return result.scalar_one_or_none()  # type: ignore[no-any-return]


def get_calibration_weights() -> dict[str, float]:
    """
    Get pillar weights from active config or defaults.

    This is a synchronous wrapper for use in scoring.
    Uses the 7-pillar system with entity_recognition.

    Returns:
        Dict of pillar name -> weight
    """
    from worker.scoring.calculator_v2 import DEFAULT_PILLAR_WEIGHTS, get_pillar_weights

    try:
        # Use the cached weights from calculator_v2 if available
        return get_pillar_weights()
    except Exception:
        # Fallback to defaults
        return DEFAULT_PILLAR_WEIGHTS.copy()  # type: ignore[return-value]


async def analyze_calibration_detailed(
    window_days: int = 30,
    min_samples: int = 50,
) -> dict:
    """
    Perform detailed calibration analysis including pillar correlations.

    This extends the basic analysis with:
    - Accuracy by answerability level
    - Accuracy by provider/model
    - Pillar score correlations with outcomes
    - Recommendations for weight adjustments

    Args:
        window_days: Number of days to look back
        min_samples: Minimum samples required for analysis

    Returns:
        Comprehensive analysis dict
    """
    # Get basic analysis first
    basic_analysis = await analyze_calibration_data(window_days, min_samples)

    if not basic_analysis.get("sufficient_data"):
        return basic_analysis

    window_start = datetime.now(UTC) - timedelta(days=window_days)

    async with async_session_maker() as db:
        # Accuracy by answerability level
        answerability_results = await db.execute(
            select(
                CalibrationSample.sim_answerability,
                func.count(CalibrationSample.id).label("total"),
                func.sum(func.cast(CalibrationSample.prediction_accurate, func.Integer)).label(  # type: ignore[arg-type]
                    "accurate"
                ),
            )
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .group_by(CalibrationSample.sim_answerability)
        )
        accuracy_by_answerability = {}
        for row in answerability_results.fetchall():
            ans_total = row[1] or 0
            ans_accurate = row[2] or 0
            if ans_total > 0:
                accuracy_by_answerability[row[0]] = {
                    "total": ans_total,
                    "accurate": ans_accurate,
                    "accuracy": ans_accurate / ans_total,
                }

        # Accuracy by provider/model
        provider_results = await db.execute(
            select(
                CalibrationSample.obs_provider,
                CalibrationSample.obs_model,
                func.count(CalibrationSample.id).label("total"),
                func.sum(func.cast(CalibrationSample.prediction_accurate, func.Integer)).label(  # type: ignore[arg-type]
                    "accurate"
                ),
            )
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
            .group_by(CalibrationSample.obs_provider, CalibrationSample.obs_model)
        )
        accuracy_by_provider: dict[str, dict[str, Any]] = {}
        for row in provider_results.fetchall():  # type: ignore[assignment]
            provider_key = f"{row[0]}:{row[1]}"
            prov_total = row[2] or 0
            prov_accurate = row[3] or 0
            if prov_total > 0:
                accuracy_by_provider[provider_key] = {
                    "provider": row[0],
                    "model": row[1],
                    "total": prov_total,
                    "accurate": prov_accurate,
                    "accuracy": prov_accurate / prov_total,
                }

        # Pillar score correlations with outcomes
        # Fetch samples with pillar scores
        samples_with_pillars = await db.execute(
            select(
                CalibrationSample.pillar_scores,
                CalibrationSample.prediction_accurate,
                CalibrationSample.outcome_match,
            )
            .where(CalibrationSample.created_at >= window_start)
            .where(CalibrationSample.pillar_scores.isnot(None))
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
        )

        pillar_correlation = _calculate_pillar_correlation(samples_with_pillars.fetchall())  # type: ignore[arg-type]

        # Generate recommendations
        recommendations = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability=accuracy_by_answerability,
            pillar_correlation=pillar_correlation,
        )

        # Combine results
        detailed_analysis = {
            **basic_analysis,
            "accuracy_by_answerability": accuracy_by_answerability,
            "accuracy_by_provider": accuracy_by_provider,
            "pillar_correlation": pillar_correlation,
            "recommendations": recommendations,
        }

        logger.info(
            "detailed_calibration_analysis_completed",
            total_samples=basic_analysis["total_samples"],
            recommendations_count=len(recommendations),
        )

        return detailed_analysis


def _calculate_pillar_correlation(samples: list) -> dict:
    """
    Calculate correlation between pillar scores and prediction accuracy.

    Returns dict with each pillar's correlation metrics:
    - high_score_accuracy: Accuracy when pillar score >= 70
    - low_score_accuracy: Accuracy when pillar score < 50
    - correlation_strength: High/low score accuracy difference
    """
    pillar_names = [
        "technical",
        "structure",
        "schema",
        "authority",
        "entity_recognition",
        "retrieval",
        "coverage",
    ]

    pillar_data: dict[str, dict[str, list[float]]] = {
        name: {"high": [], "low": [], "mid": []} for name in pillar_names
    }

    for pillar_scores, prediction_accurate, _outcome_match in samples:
        if not pillar_scores:
            continue

        for pillar_name in pillar_names:
            score = pillar_scores.get(pillar_name)
            if score is None:
                continue

            accurate = 1 if prediction_accurate else 0

            if score >= 70:
                pillar_data[pillar_name]["high"].append(accurate)
            elif score < 50:
                pillar_data[pillar_name]["low"].append(accurate)
            else:
                pillar_data[pillar_name]["mid"].append(accurate)

    correlation = {}
    for pillar_name, data in pillar_data.items():
        high_samples = len(data["high"])
        low_samples = len(data["low"])

        if high_samples >= 10 and low_samples >= 10:
            high_accuracy = sum(data["high"]) / high_samples
            low_accuracy = sum(data["low"]) / low_samples
            correlation_strength = high_accuracy - low_accuracy

            correlation[pillar_name] = {
                "high_score_accuracy": high_accuracy,
                "high_score_samples": high_samples,
                "low_score_accuracy": low_accuracy,
                "low_score_samples": low_samples,
                "correlation_strength": correlation_strength,
                "significant": abs(correlation_strength) > 0.1,
            }
        else:
            correlation[pillar_name] = {
                "insufficient_data": True,
                "high_score_samples": high_samples,
                "low_score_samples": low_samples,
            }

    return correlation


def _generate_calibration_recommendations(
    basic_analysis: dict,
    accuracy_by_answerability: dict,
    pillar_correlation: dict,
) -> list[dict]:
    """
    Generate actionable recommendations based on calibration analysis.

    Returns list of recommendation dicts with:
    - type: Category of recommendation
    - priority: high/medium/low
    - message: Human-readable recommendation
    - action: Suggested action to take
    """
    recommendations = []

    # Check overall accuracy
    accuracy = basic_analysis.get("prediction_accuracy", 0)
    if accuracy < 0.6:
        recommendations.append(
            {
                "type": "accuracy",
                "priority": "high",
                "message": f"Overall prediction accuracy is low ({accuracy:.1%})",
                "action": "Consider recalibrating pillar weights or thresholds",
            }
        )
    elif accuracy < 0.75:
        recommendations.append(
            {
                "type": "accuracy",
                "priority": "medium",
                "message": f"Prediction accuracy could be improved ({accuracy:.1%})",
                "action": "Review threshold settings and consider A/B testing new weights",
            }
        )

    # Check bias
    optimism = basic_analysis.get("optimism_bias", 0)
    pessimism = basic_analysis.get("pessimism_bias", 0)

    if optimism > 0.25:
        recommendations.append(
            {
                "type": "bias",
                "priority": "high",
                "message": f"High optimism bias ({optimism:.1%}) - predictions too positive",
                "action": "Increase answerability thresholds or reduce pillar weights",
            }
        )
    elif optimism > 0.15:
        recommendations.append(
            {
                "type": "bias",
                "priority": "medium",
                "message": f"Moderate optimism bias ({optimism:.1%})",
                "action": "Consider slightly increasing fully_answerable threshold",
            }
        )

    if pessimism > 0.25:
        recommendations.append(
            {
                "type": "bias",
                "priority": "high",
                "message": f"High pessimism bias ({pessimism:.1%}) - predictions too negative",
                "action": "Decrease answerability thresholds or increase entity_recognition weight",
            }
        )
    elif pessimism > 0.15:
        recommendations.append(
            {
                "type": "bias",
                "priority": "medium",
                "message": f"Moderate pessimism bias ({pessimism:.1%})",
                "action": "Consider entity recognition adjustments for brand awareness",
            }
        )

    # Check answerability accuracy
    for ans_level, data in accuracy_by_answerability.items():
        if data.get("total", 0) >= 20:
            ans_accuracy = data.get("accuracy", 0)
            if ans_accuracy < 0.5:
                recommendations.append(
                    {
                        "type": "answerability",
                        "priority": "medium",
                        "message": f"Low accuracy for '{ans_level}' predictions ({ans_accuracy:.1%})",
                        "action": f"Review threshold for {ans_level} classification",
                    }
                )

    # Check pillar correlations
    for pillar_name, corr_data in pillar_correlation.items():
        if corr_data.get("insufficient_data"):
            continue

        strength = corr_data.get("correlation_strength", 0)
        if strength < 0:
            recommendations.append(
                {
                    "type": "pillar_weight",
                    "priority": "medium",
                    "message": f"'{pillar_name}' pillar shows negative correlation with accuracy",
                    "action": f"Consider reducing weight for {pillar_name} pillar",
                }
            )
        elif strength > 0.2 and corr_data.get("significant"):
            # Strong positive correlation - pillar is predictive
            pass  # This is good, no recommendation needed

    return recommendations


async def get_calibration_summary() -> dict:
    """
    Get a concise summary of current calibration state.

    Useful for dashboards and quick checks.

    Returns:
        Dict with key metrics and status
    """
    analysis = await analyze_calibration_data(window_days=7, min_samples=20)

    if not analysis.get("sufficient_data"):
        return {
            "status": "insufficient_data",
            "samples_collected": analysis.get("total_samples", 0),
            "samples_needed": 20,
        }

    accuracy = analysis.get("prediction_accuracy", 0)
    optimism = analysis.get("optimism_bias", 0)
    pessimism = analysis.get("pessimism_bias", 0)

    # Determine overall health status
    if accuracy >= 0.75 and optimism <= 0.15 and pessimism <= 0.15:
        status = "healthy"
    elif accuracy >= 0.6 and optimism <= 0.25 and pessimism <= 0.25:
        status = "acceptable"
    else:
        status = "needs_attention"

    return {
        "status": status,
        "prediction_accuracy": accuracy,
        "optimism_bias": optimism,
        "pessimism_bias": pessimism,
        "samples_last_7_days": analysis.get("total_samples", 0),
        "outcome_breakdown": analysis.get("outcome_counts", {}),
    }
