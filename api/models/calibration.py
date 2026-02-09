"""Calibration models for learning from observation outcomes.

This module provides models for:
- CalibrationSample: Ground truth data pairing simulation predictions with observation outcomes
- CalibrationConfig: Parameter configurations (weights, thresholds) that can be A/B tested
- CalibrationExperiment: A/B testing infrastructure for config changes
- CalibrationDriftAlert: Alerts when prediction accuracy degrades
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.database import Base

if TYPE_CHECKING:
    from api.models.run import Run
    from api.models.site import Site


class OutcomeMatch(StrEnum):
    """How well simulation matched observation."""

    CORRECT = "correct"  # Simulation prediction matched reality
    OPTIMISTIC = "optimistic"  # Simulation was more positive than reality
    PESSIMISTIC = "pessimistic"  # Simulation was more negative than reality
    UNKNOWN = "unknown"  # Can't determine


class CalibrationConfigStatus(StrEnum):
    """Status of a calibration configuration."""

    DRAFT = "draft"  # Being edited, not yet validated
    VALIDATED = "validated"  # Passed validation, ready to activate
    ACTIVE = "active"  # Currently in use
    ARCHIVED = "archived"  # No longer used, kept for history


class ExperimentStatus(StrEnum):
    """Status of a calibration experiment."""

    DRAFT = "draft"  # Not yet started
    RUNNING = "running"  # Actively collecting samples
    CONCLUDED = "concluded"  # Finished, winner determined


class DriftType(StrEnum):
    """Type of calibration drift detected."""

    ACCURACY = "accuracy"  # Overall prediction accuracy dropped
    OPTIMISM = "optimism"  # Too many optimistic predictions
    PESSIMISM = "pessimism"  # Too many pessimistic predictions
    PILLAR = "pillar"  # Specific pillar correlation dropped


class DriftAlertStatus(StrEnum):
    """Status of a drift alert."""

    OPEN = "open"  # Needs attention
    ACKNOWLEDGED = "acknowledged"  # Seen but not yet resolved
    RESOLVED = "resolved"  # Fixed or determined to be acceptable


class CalibrationSample(Base):
    """Ground truth sample pairing simulation prediction with observation outcome.

    Collected after each observation run to build calibration dataset.
    Used for analyzing prediction accuracy and optimizing parameters.
    """

    __tablename__ = "calibration_samples"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # References
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sites.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    # Simulation prediction
    sim_answerability: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )  # fully_answerable, partially_answerable, not_answerable
    sim_score: Mapped[float] = mapped_column(Float, nullable=False)
    sim_signals_found: Mapped[int] = mapped_column(Integer, nullable=False)
    sim_signals_total: Mapped[int] = mapped_column(Integer, nullable=False)
    sim_relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Observation outcome (ground truth)
    obs_mentioned: Mapped[bool] = mapped_column(Boolean, nullable=False)
    obs_cited: Mapped[bool] = mapped_column(Boolean, nullable=False)
    obs_sentiment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    obs_confidence: Mapped[str | None] = mapped_column(String(50), nullable=True)
    obs_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    obs_model: Mapped[str] = mapped_column(String(100), nullable=False)

    # Derived outcome
    outcome_match: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # correct, optimistic, pessimistic, unknown
    prediction_accurate: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)

    # Context for analysis
    question_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    question_difficulty: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Site context at time of sample
    domain_industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    site_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )  # documentation, reference, developer_tools, saas_marketing, etc.

    # Pillar scores at time of sample (for correlation analysis)
    pillar_scores: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Example: {"technical": 75, "structure": 80, "schema": 60, ...}

    # Experiment tracking (if part of A/B test)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_experiments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    experiment_arm: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Calibration config used (for tracking which config produced this sample)
    config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_configs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    # Relationships
    site: Mapped[Site] = relationship("Site")
    run: Mapped[Run] = relationship("Run")


class CalibrationConfig(Base):
    """Calibration parameter configuration.

    Stores pillar weights, thresholds, and other tunable parameters.
    Can be validated against historical samples before activation.
    """

    __tablename__ = "calibration_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=CalibrationConfigStatus.DRAFT.value,
        nullable=False,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # Pillar weights (must sum to 100)
    # Entity Recognition (13%) added to address 23% pessimism bias
    weight_technical: Mapped[float] = mapped_column(Float, default=12.0, nullable=False)
    weight_structure: Mapped[float] = mapped_column(Float, default=18.0, nullable=False)
    weight_schema: Mapped[float] = mapped_column(Float, default=13.0, nullable=False)
    weight_authority: Mapped[float] = mapped_column(Float, default=12.0, nullable=False)
    weight_entity_recognition: Mapped[float] = mapped_column(Float, default=13.0, nullable=False)
    weight_retrieval: Mapped[float] = mapped_column(Float, default=22.0, nullable=False)
    weight_coverage: Mapped[float] = mapped_column(Float, default=10.0, nullable=False)

    # Answerability thresholds
    threshold_fully_answerable: Mapped[float] = mapped_column(Float, default=0.7, nullable=False)
    threshold_partially_answerable: Mapped[float] = mapped_column(
        Float, default=0.3, nullable=False
    )

    # Signal matching threshold
    threshold_signal_match: Mapped[float] = mapped_column(Float, default=0.6, nullable=False)

    # Scoring weights within simulation
    scoring_relevance_weight: Mapped[float] = mapped_column(Float, default=0.4, nullable=False)
    scoring_signal_weight: Mapped[float] = mapped_column(Float, default=0.4, nullable=False)
    scoring_confidence_weight: Mapped[float] = mapped_column(Float, default=0.2, nullable=False)

    # Validation metrics (from holdout validation)
    validation_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validation_optimism_bias: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_pessimism_bias: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_f1_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Audit trail
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def weights(self) -> dict[str, float]:
        """Get pillar weights as dictionary."""
        return {
            "technical": self.weight_technical,
            "structure": self.weight_structure,
            "schema": self.weight_schema,
            "authority": self.weight_authority,
            "entity_recognition": self.weight_entity_recognition,
            "retrieval": self.weight_retrieval,
            "coverage": self.weight_coverage,
        }

    @property
    def weights_sum(self) -> float:
        """Sum of all pillar weights (should be 100)."""
        return sum(self.weights.values())

    def validate_weights(self) -> list[str]:
        """Validate weight constraints. Returns list of errors."""
        errors = []
        weights = self.weights

        # Check sum
        total = sum(weights.values())
        if abs(total - 100.0) > 0.01:
            errors.append(f"Weights must sum to 100, got {total:.2f}")

        # Check individual bounds
        for name, value in weights.items():
            if value < 5.0:
                errors.append(f"{name} weight ({value:.1f}) must be at least 5")
            if value > 35.0:
                errors.append(f"{name} weight ({value:.1f}) must be at most 35")

        return errors


class CalibrationExperiment(Base):
    """A/B test experiment for calibration configurations.

    Allows safe testing of new configurations by splitting traffic
    and comparing prediction accuracy between control and treatment.
    """

    __tablename__ = "calibration_experiments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Experiment setup
    control_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_configs.id", ondelete="CASCADE"),
        nullable=False,
    )
    treatment_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("calibration_configs.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Traffic allocation (0.0 to 1.0) - fraction going to treatment
    treatment_allocation: Mapped[float] = mapped_column(Float, default=0.1, nullable=False)

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=ExperimentStatus.DRAFT.value,
        nullable=False,
        index=True,
    )

    # Sample requirements
    min_samples_per_arm: Mapped[int] = mapped_column(Integer, default=100, nullable=False)

    # Results
    control_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    treatment_samples: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    control_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    treatment_accuracy: Mapped[float | None] = mapped_column(Float, nullable=True)
    control_optimism: Mapped[float | None] = mapped_column(Float, nullable=True)
    treatment_optimism: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Statistical significance
    p_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_significant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # Winner determination
    winner: Mapped[str | None] = mapped_column(String(50), nullable=True)  # control, treatment, tie
    winner_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    concluded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    control_config: Mapped[CalibrationConfig] = relationship(
        "CalibrationConfig",
        foreign_keys=[control_config_id],
    )
    treatment_config: Mapped[CalibrationConfig] = relationship(
        "CalibrationConfig",
        foreign_keys=[treatment_config_id],
    )


class CalibrationDriftAlert(Base):
    """Alert when calibration accuracy degrades.

    Created by drift detection task when prediction accuracy
    falls below thresholds or bias exceeds limits.
    """

    __tablename__ = "calibration_drift_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    # What drifted
    drift_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # accuracy, optimism, pessimism, pillar
    affected_pillar: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Metrics
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    observed_value: Mapped[float] = mapped_column(Float, nullable=False)
    drift_magnitude: Mapped[float] = mapped_column(Float, nullable=False)

    # Context
    sample_window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    sample_window_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # Baseline reference
    baseline_window_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    baseline_window_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    baseline_sample_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String(50),
        default=DriftAlertStatus.OPEN.value,
        nullable=False,
        index=True,
    )

    # Resolution
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_action: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )  # e.g., "recalibrated", "acceptable", "content_issue"

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
