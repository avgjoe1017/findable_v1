"""A/B experiment infrastructure for calibration testing.

This module provides:
- Experiment assignment based on site_id hashing
- Sample tracking per experiment arm
- Statistical significance testing
- Experiment conclusion logic
"""

import hashlib
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

import structlog
from scipy import stats
from sqlalchemy import func, select, update

from api.database import async_session_maker
from api.models.calibration import (
    CalibrationConfig,
    CalibrationExperiment,
    CalibrationSample,
    ExperimentStatus,
    OutcomeMatch,
)

logger = structlog.get_logger(__name__)


class ExperimentArm(StrEnum):
    """Experiment arm assignment."""

    CONTROL = "control"
    TREATMENT = "treatment"


@dataclass
class ExperimentAssignment:
    """Result of experiment assignment."""

    experiment_id: uuid.UUID
    arm: ExperimentArm
    config_id: uuid.UUID
    config_name: str


@dataclass
class ExperimentResults:
    """Results of an experiment analysis."""

    experiment_id: uuid.UUID
    control_samples: int
    treatment_samples: int
    control_accuracy: float
    treatment_accuracy: float
    accuracy_difference: float
    p_value: float | None
    is_significant: bool
    winner: Literal["control", "treatment", "none"] | None
    winner_reason: str | None
    ready_to_conclude: bool
    min_samples_per_arm: int

    def to_dict(self) -> dict:
        return {
            "experiment_id": str(self.experiment_id),
            "control_samples": self.control_samples,
            "treatment_samples": self.treatment_samples,
            "control_accuracy": round(self.control_accuracy, 4),
            "treatment_accuracy": round(self.treatment_accuracy, 4),
            "accuracy_difference": round(self.accuracy_difference, 4),
            "p_value": round(self.p_value, 4) if self.p_value else None,
            "is_significant": self.is_significant,
            "winner": self.winner,
            "winner_reason": self.winner_reason,
            "ready_to_conclude": self.ready_to_conclude,
            "min_samples_per_arm": self.min_samples_per_arm,
        }


def get_experiment_arm(site_id: uuid.UUID, treatment_allocation: float = 0.1) -> ExperimentArm:
    """
    Deterministically assign a site to an experiment arm.

    Uses consistent hashing so the same site always gets the same arm.

    Args:
        site_id: The site ID to assign
        treatment_allocation: Fraction of sites in treatment (0-1)

    Returns:
        ExperimentArm.TREATMENT or ExperimentArm.CONTROL
    """
    # Create a consistent hash from site_id
    hash_input = str(site_id).encode("utf-8")
    hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)

    # Map to [0, 1) range
    normalized = (hash_value % 10000) / 10000.0

    if normalized < treatment_allocation:
        return ExperimentArm.TREATMENT
    return ExperimentArm.CONTROL


async def get_active_experiment() -> CalibrationExperiment | None:
    """
    Get the currently running experiment, if any.

    Returns:
        Active CalibrationExperiment or None
    """
    async with async_session_maker() as db:
        result = await db.execute(
            select(CalibrationExperiment).where(
                CalibrationExperiment.status == ExperimentStatus.RUNNING.value
            )
        )
        return result.scalar_one_or_none()  # type: ignore[no-any-return]


async def assign_to_experiment(
    site_id: uuid.UUID,
) -> ExperimentAssignment | None:
    """
    Assign a site to an experiment arm if an experiment is running.

    Args:
        site_id: The site ID to assign

    Returns:
        ExperimentAssignment or None if no experiment running
    """
    async with async_session_maker() as db:
        # Get active experiment
        experiment_result = await db.execute(
            select(CalibrationExperiment).where(
                CalibrationExperiment.status == ExperimentStatus.RUNNING.value
            )
        )
        experiment = experiment_result.scalar_one_or_none()

        if not experiment:
            return None

        # Determine arm
        arm = get_experiment_arm(site_id, experiment.treatment_allocation)

        # Get the config for this arm
        config_id = (
            experiment.treatment_config_id
            if arm == ExperimentArm.TREATMENT
            else experiment.control_config_id
        )

        config_result = await db.execute(
            select(CalibrationConfig).where(CalibrationConfig.id == config_id)
        )
        config = config_result.scalar_one_or_none()

        if not config:
            logger.error(
                "experiment_config_not_found",
                experiment_id=str(experiment.id),
                config_id=str(config_id),
                arm=arm.value,
            )
            return None

        logger.debug(
            "site_assigned_to_experiment",
            site_id=str(site_id),
            experiment_id=str(experiment.id),
            arm=arm.value,
            config_name=config.name,
        )

        return ExperimentAssignment(
            experiment_id=experiment.id,
            arm=arm,
            config_id=config.id,
            config_name=config.name,
        )


async def update_experiment_sample_counts(experiment_id: uuid.UUID) -> dict:
    """
    Update the sample counts for an experiment.

    Counts samples tagged with this experiment in each arm.

    Args:
        experiment_id: The experiment to update

    Returns:
        Dict with control_samples and treatment_samples
    """
    async with async_session_maker() as db:
        # Get experiment
        experiment_result = await db.execute(
            select(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        experiment = experiment_result.scalar_one_or_none()

        if not experiment:
            return {"error": "Experiment not found"}

        # Count samples by config_id (arm)
        control_count_result = await db.execute(
            select(func.count(CalibrationSample.id))
            .where(CalibrationSample.experiment_id == experiment_id)
            .where(CalibrationSample.config_id == experiment.control_config_id)
        )
        control_samples = control_count_result.scalar() or 0

        treatment_count_result = await db.execute(
            select(func.count(CalibrationSample.id))
            .where(CalibrationSample.experiment_id == experiment_id)
            .where(CalibrationSample.config_id == experiment.treatment_config_id)
        )
        treatment_samples = treatment_count_result.scalar() or 0

        # Update experiment
        await db.execute(
            update(CalibrationExperiment)
            .where(CalibrationExperiment.id == experiment_id)
            .values(
                control_samples=control_samples,
                treatment_samples=treatment_samples,
            )
        )
        await db.commit()

        logger.info(
            "experiment_sample_counts_updated",
            experiment_id=str(experiment_id),
            control_samples=control_samples,
            treatment_samples=treatment_samples,
        )

        return {
            "control_samples": control_samples,
            "treatment_samples": treatment_samples,
        }


async def analyze_experiment(experiment_id: uuid.UUID) -> ExperimentResults:
    """
    Analyze experiment results and compute statistics.

    Args:
        experiment_id: The experiment to analyze

    Returns:
        ExperimentResults with accuracy and significance info
    """
    async with async_session_maker() as db:
        # Get experiment
        experiment_result = await db.execute(
            select(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        experiment = experiment_result.scalar_one_or_none()

        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Get control arm samples
        control_result = await db.execute(
            select(CalibrationSample)
            .where(CalibrationSample.experiment_id == experiment_id)
            .where(CalibrationSample.config_id == experiment.control_config_id)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
        )
        control_samples = list(control_result.scalars().all())

        # Get treatment arm samples
        treatment_result = await db.execute(
            select(CalibrationSample)
            .where(CalibrationSample.experiment_id == experiment_id)
            .where(CalibrationSample.config_id == experiment.treatment_config_id)
            .where(CalibrationSample.outcome_match != OutcomeMatch.UNKNOWN.value)
        )
        treatment_samples = list(treatment_result.scalars().all())

        # Calculate accuracy for each arm
        control_correct = sum(1 for s in control_samples if s.prediction_accurate)
        treatment_correct = sum(1 for s in treatment_samples if s.prediction_accurate)

        control_accuracy = control_correct / len(control_samples) if control_samples else 0.0
        treatment_accuracy = (
            treatment_correct / len(treatment_samples) if treatment_samples else 0.0
        )

        accuracy_difference = treatment_accuracy - control_accuracy

        # Statistical significance test (chi-squared)
        p_value = None
        is_significant = False

        if len(control_samples) >= 20 and len(treatment_samples) >= 20:
            # Build contingency table
            # [[control_correct, control_incorrect], [treatment_correct, treatment_incorrect]]
            control_incorrect = len(control_samples) - control_correct
            treatment_incorrect = len(treatment_samples) - treatment_correct

            contingency = [
                [control_correct, control_incorrect],
                [treatment_correct, treatment_incorrect],
            ]

            try:
                chi2, p_value, dof, expected = stats.chi2_contingency(contingency)
                is_significant = p_value < 0.05
            except Exception as e:
                logger.warning("chi2_test_failed", error=str(e))

        # Determine winner
        winner = None
        winner_reason = None
        ready_to_conclude = False

        min_samples = experiment.min_samples_per_arm
        has_enough_samples = (
            len(control_samples) >= min_samples and len(treatment_samples) >= min_samples
        )

        if has_enough_samples:
            ready_to_conclude = True

            if is_significant:
                if accuracy_difference > 0:
                    winner = "treatment"
                    winner_reason = (
                        f"Treatment shows {accuracy_difference:.1%} improvement "
                        f"with p={p_value:.4f}"
                    )
                else:
                    winner = "control"
                    winner_reason = (
                        f"Control outperforms treatment by {-accuracy_difference:.1%} "
                        f"with p={p_value:.4f}"
                    )
            else:
                winner = "none"
                winner_reason = f"No significant difference (p={p_value:.4f})"

        return ExperimentResults(
            experiment_id=experiment_id,
            control_samples=len(control_samples),
            treatment_samples=len(treatment_samples),
            control_accuracy=control_accuracy,
            treatment_accuracy=treatment_accuracy,
            accuracy_difference=accuracy_difference,
            p_value=p_value,
            is_significant=is_significant,
            winner=winner,  # type: ignore[arg-type]
            winner_reason=winner_reason,
            ready_to_conclude=ready_to_conclude,
            min_samples_per_arm=min_samples,
        )


async def conclude_experiment(
    experiment_id: uuid.UUID,
    activate_winner: bool = False,
) -> dict:
    """
    Conclude an experiment and optionally activate the winner.

    Args:
        experiment_id: The experiment to conclude
        activate_winner: If True, activate the winning config

    Returns:
        Dict with conclusion results
    """
    async with async_session_maker() as db:
        # Get experiment
        experiment_result = await db.execute(
            select(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        experiment = experiment_result.scalar_one_or_none()

        if not experiment:
            return {"error": "Experiment not found"}

        if experiment.status != ExperimentStatus.RUNNING.value:
            return {"error": f"Experiment is not running (status: {experiment.status})"}

        # Analyze results
        results = await analyze_experiment(experiment_id)

        if not results.ready_to_conclude:
            return {
                "error": "Insufficient samples to conclude",
                "control_samples": results.control_samples,
                "treatment_samples": results.treatment_samples,
                "min_required": results.min_samples_per_arm,
            }

        # Update experiment with results
        await db.execute(
            update(CalibrationExperiment)
            .where(CalibrationExperiment.id == experiment_id)
            .values(
                status=ExperimentStatus.CONCLUDED.value,
                control_accuracy=results.control_accuracy,
                treatment_accuracy=results.treatment_accuracy,
                p_value=results.p_value,
                is_significant=results.is_significant,
                winner=results.winner,
                winner_reason=results.winner_reason,
                concluded_at=datetime.now(UTC),
            )
        )

        # Optionally activate winner
        activated_config_id = None
        if activate_winner and results.winner in ("control", "treatment"):
            winner_config_id = (
                experiment.treatment_config_id
                if results.winner == "treatment"
                else experiment.control_config_id
            )

            # Deactivate current active config
            await db.execute(
                update(CalibrationConfig)
                .where(CalibrationConfig.is_active == True)  # noqa: E712
                .values(is_active=False)
            )

            # Activate winner
            await db.execute(
                update(CalibrationConfig)
                .where(CalibrationConfig.id == winner_config_id)
                .values(is_active=True, activated_at=datetime.now(UTC))
            )

            activated_config_id = winner_config_id

            logger.info(
                "experiment_winner_activated",
                experiment_id=str(experiment_id),
                winner=results.winner,
                config_id=str(winner_config_id),
            )

        await db.commit()

        logger.info(
            "experiment_concluded",
            experiment_id=str(experiment_id),
            winner=results.winner,
            is_significant=results.is_significant,
            activated=activated_config_id is not None,
        )

        return {
            "experiment_id": str(experiment_id),
            "status": "concluded",
            "winner": results.winner,
            "winner_reason": results.winner_reason,
            "is_significant": results.is_significant,
            "control_accuracy": results.control_accuracy,
            "treatment_accuracy": results.treatment_accuracy,
            "activated_config_id": str(activated_config_id) if activated_config_id else None,
        }


async def start_experiment(experiment_id: uuid.UUID) -> dict:
    """
    Start a draft experiment.

    Args:
        experiment_id: The experiment to start

    Returns:
        Dict with status
    """
    async with async_session_maker() as db:
        # Get experiment
        experiment_result = await db.execute(
            select(CalibrationExperiment).where(CalibrationExperiment.id == experiment_id)
        )
        experiment = experiment_result.scalar_one_or_none()

        if not experiment:
            return {"error": "Experiment not found"}

        if experiment.status != ExperimentStatus.DRAFT.value:
            return {"error": f"Experiment is not in draft status (status: {experiment.status})"}

        # Check no other experiment is running
        running_result = await db.execute(
            select(CalibrationExperiment).where(
                CalibrationExperiment.status == ExperimentStatus.RUNNING.value
            )
        )
        running = running_result.scalar_one_or_none()

        if running:
            return {
                "error": "Another experiment is already running",
                "running_experiment_id": str(running.id),
            }

        # Verify both configs exist
        for config_id in [experiment.control_config_id, experiment.treatment_config_id]:
            config_result = await db.execute(
                select(CalibrationConfig).where(CalibrationConfig.id == config_id)
            )
            if not config_result.scalar_one_or_none():
                return {"error": f"Config {config_id} not found"}

        # Start the experiment
        await db.execute(
            update(CalibrationExperiment)
            .where(CalibrationExperiment.id == experiment_id)
            .values(
                status=ExperimentStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )
        await db.commit()

        logger.info("experiment_started", experiment_id=str(experiment_id))

        return {
            "experiment_id": str(experiment_id),
            "status": "running",
            "started_at": datetime.now(UTC).isoformat(),
        }
