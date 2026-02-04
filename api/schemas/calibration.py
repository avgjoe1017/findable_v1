"""Calibration API schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

# ============================================================================
# Calibration Sample Schemas
# ============================================================================


class CalibrationSampleResponse(BaseModel):
    """Calibration sample for API responses."""

    id: UUID
    site_id: UUID
    run_id: UUID
    question_id: str
    question_text: str
    question_category: str
    question_difficulty: str

    # Simulation prediction
    sim_answerability: str
    sim_score: float
    sim_signals_found: int
    sim_signals_total: int

    # Observation outcome
    obs_mentioned: bool
    obs_cited: bool
    obs_provider: str
    obs_model: str

    # Derived
    outcome_match: str
    prediction_accurate: bool

    created_at: datetime

    model_config = {"from_attributes": True}


class CalibrationSampleListResponse(BaseModel):
    """List of calibration samples."""

    samples: list[CalibrationSampleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============================================================================
# Calibration Analysis Schemas
# ============================================================================


class CategoryAccuracy(BaseModel):
    """Accuracy for a specific category."""

    category: str
    accuracy: float
    sample_count: int


class DifficultyAccuracy(BaseModel):
    """Accuracy for a specific difficulty level."""

    difficulty: str
    accuracy: float
    sample_count: int


class OutcomeCounts(BaseModel):
    """Counts by outcome type."""

    correct: int
    optimistic: int
    pessimistic: int
    unknown: int


class CalibrationAnalysisResponse(BaseModel):
    """Calibration analysis results."""

    total_samples: int
    sufficient_data: bool
    min_required: int = 100

    # Only present if sufficient_data is True
    known_samples: int | None = None
    prediction_accuracy: float | None = None
    optimism_bias: float | None = None
    pessimism_bias: float | None = None

    outcome_counts: OutcomeCounts | None = None
    accuracy_by_category: dict[str, float] | None = None
    accuracy_by_difficulty: dict[str, float] | None = None

    window_start: datetime | None = None
    window_days: int | None = None


class AnswerabilityAccuracy(BaseModel):
    """Accuracy stats for an answerability level."""

    total: int
    accurate: int
    accuracy: float


class ProviderAccuracy(BaseModel):
    """Accuracy stats for a provider/model combo."""

    provider: str
    model: str
    total: int
    accurate: int
    accuracy: float


class PillarCorrelation(BaseModel):
    """Correlation data for a pillar."""

    high_score_accuracy: float | None = None
    high_score_samples: int = 0
    low_score_accuracy: float | None = None
    low_score_samples: int = 0
    correlation_strength: float | None = None
    significant: bool | None = None
    insufficient_data: bool = False


class CalibrationRecommendation(BaseModel):
    """A calibration recommendation."""

    type: str
    priority: str
    message: str
    action: str


class CalibrationDetailedAnalysisResponse(BaseModel):
    """Detailed calibration analysis with pillar correlations."""

    # Basic analysis fields
    total_samples: int
    sufficient_data: bool
    min_required: int = 50
    known_samples: int | None = None
    prediction_accuracy: float | None = None
    optimism_bias: float | None = None
    pessimism_bias: float | None = None
    outcome_counts: OutcomeCounts | None = None
    accuracy_by_category: dict[str, float] | None = None
    accuracy_by_difficulty: dict[str, float] | None = None
    window_start: datetime | None = None
    window_days: int | None = None

    # Detailed analysis fields
    accuracy_by_answerability: dict[str, AnswerabilityAccuracy] | None = None
    accuracy_by_provider: dict[str, ProviderAccuracy] | None = None
    pillar_correlation: dict[str, PillarCorrelation] | None = None
    recommendations: list[CalibrationRecommendation] | None = None


class CalibrationSummaryResponse(BaseModel):
    """Concise calibration summary for dashboards."""

    status: str  # healthy, acceptable, needs_attention, insufficient_data
    prediction_accuracy: float | None = None
    optimism_bias: float | None = None
    pessimism_bias: float | None = None
    samples_last_7_days: int | None = None
    samples_collected: int | None = None
    samples_needed: int | None = None
    outcome_breakdown: OutcomeCounts | None = None


# ============================================================================
# Calibration Config Schemas
# ============================================================================


class PillarWeights(BaseModel):
    """Pillar weight configuration (7-pillar system)."""

    technical: float = Field(ge=5.0, le=35.0, default=12.0)
    structure: float = Field(ge=5.0, le=35.0, default=18.0)
    schema_: float = Field(ge=5.0, le=35.0, default=13.0, alias="schema")
    authority: float = Field(ge=5.0, le=35.0, default=12.0)
    entity_recognition: float = Field(ge=5.0, le=35.0, default=13.0)
    retrieval: float = Field(ge=5.0, le=35.0, default=22.0)
    coverage: float = Field(ge=5.0, le=35.0, default=10.0)

    model_config = {"populate_by_name": True}


class AnswerabilityThresholds(BaseModel):
    """Answerability threshold configuration."""

    fully_answerable: float = Field(ge=0.5, le=0.95, default=0.7)
    partially_answerable: float = Field(ge=0.1, le=0.5, default=0.3)


class CalibrationConfigCreate(BaseModel):
    """Request to create a new calibration config."""

    name: str = Field(min_length=3, max_length=100)
    description: str | None = None
    weights: PillarWeights = Field(default_factory=PillarWeights)
    thresholds: AnswerabilityThresholds = Field(default_factory=AnswerabilityThresholds)
    notes: str | None = None


class CalibrationConfigResponse(BaseModel):
    """Calibration config for API responses."""

    id: UUID
    name: str
    description: str | None
    status: str
    is_active: bool

    # Weights (7-pillar system)
    weight_technical: float
    weight_structure: float
    weight_schema: float
    weight_authority: float
    weight_entity_recognition: float
    weight_retrieval: float
    weight_coverage: float

    # Thresholds
    threshold_fully_answerable: float
    threshold_partially_answerable: float

    # Validation metrics
    validation_accuracy: float | None
    validation_sample_count: int | None
    validation_optimism_bias: float | None
    validation_pessimism_bias: float | None

    # Timestamps
    created_at: datetime
    validated_at: datetime | None
    activated_at: datetime | None

    model_config = {"from_attributes": True}


class CalibrationConfigListResponse(BaseModel):
    """List of calibration configs."""

    configs: list[CalibrationConfigResponse]
    active_config_id: UUID | None


class ConfigValidationResult(BaseModel):
    """Result of config validation against historical samples."""

    config_id: UUID
    validation_accuracy: float
    validation_optimism_bias: float
    validation_pessimism_bias: float
    sample_count: int
    holdout_count: int
    is_improvement: bool
    improvement_margin: float | None = None
    errors: list[str] = []


# ============================================================================
# Calibration Experiment Schemas
# ============================================================================


class ExperimentCreate(BaseModel):
    """Request to create an A/B experiment."""

    name: str = Field(min_length=3, max_length=200)
    description: str | None = None
    control_config_id: UUID
    treatment_config_id: UUID
    treatment_allocation: float = Field(ge=0.05, le=0.5, default=0.1)
    min_samples_per_arm: int = Field(ge=50, le=1000, default=100)


class ExperimentResponse(BaseModel):
    """Experiment for API responses."""

    id: UUID
    name: str
    description: str | None
    control_config_id: UUID
    treatment_config_id: UUID
    treatment_allocation: float
    status: str
    min_samples_per_arm: int

    # Results
    control_samples: int
    treatment_samples: int
    control_accuracy: float | None
    treatment_accuracy: float | None
    p_value: float | None
    is_significant: bool | None
    winner: str | None
    winner_reason: str | None

    # Timestamps
    created_at: datetime
    started_at: datetime | None
    concluded_at: datetime | None

    model_config = {"from_attributes": True}


class ExperimentListResponse(BaseModel):
    """List of experiments."""

    experiments: list[ExperimentResponse]
    total: int


# ============================================================================
# Drift Alert Schemas
# ============================================================================


class DriftAlertResponse(BaseModel):
    """Drift alert for API responses."""

    id: UUID
    drift_type: str
    affected_pillar: str | None
    expected_value: float
    observed_value: float
    drift_magnitude: float
    sample_window_start: datetime
    sample_window_end: datetime
    sample_count: int
    status: str
    resolution_notes: str | None
    resolution_action: str | None
    created_at: datetime
    acknowledged_at: datetime | None
    resolved_at: datetime | None

    model_config = {"from_attributes": True}


class DriftAlertListResponse(BaseModel):
    """List of drift alerts."""

    alerts: list[DriftAlertResponse]
    total: int
    open_count: int


class DriftAlertAcknowledge(BaseModel):
    """Request to acknowledge a drift alert."""

    pass  # No fields needed


class DriftAlertResolve(BaseModel):
    """Request to resolve a drift alert."""

    resolution_notes: str = Field(min_length=10, max_length=1000)
    resolution_action: str = Field(
        description="Action taken: recalibrated, acceptable, content_issue, false_positive"
    )
