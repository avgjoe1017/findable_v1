"""Tests for calibration models and tasks."""

import uuid
from datetime import UTC, datetime, timedelta

from api.models.calibration import (
    CalibrationConfig,
    CalibrationConfigStatus,
    CalibrationDriftAlert,
    CalibrationExperiment,
    CalibrationSample,
    DriftAlertStatus,
    DriftType,
    ExperimentStatus,
    OutcomeMatch,
)


class TestCalibrationSampleModel:
    """Tests for CalibrationSample model."""

    def test_create_sample(self):
        """Test creating a calibration sample."""
        sample = CalibrationSample(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            question_id="q1",
            sim_answerability="fully_answerable",
            sim_score=0.85,
            sim_signals_found=4,
            sim_signals_total=5,
            sim_relevance_score=0.72,
            obs_mentioned=True,
            obs_cited=True,
            obs_provider="openrouter",
            obs_model="openai/gpt-4o-mini",
            outcome_match=OutcomeMatch.CORRECT.value,
            prediction_accurate=True,
            question_category="identity",
            question_difficulty="easy",
            question_text="What does Test Company do?",
        )

        assert sample.sim_answerability == "fully_answerable"
        assert sample.sim_score == 0.85
        assert sample.obs_mentioned is True
        assert sample.obs_cited is True
        assert sample.prediction_accurate is True
        assert sample.outcome_match == "correct"

    def test_sample_with_pillar_scores(self):
        """Test sample with pillar scores snapshot."""
        pillar_scores = {
            "technical": 75.0,
            "structure": 80.0,
            "schema": 60.0,
            "authority": 70.0,
            "retrieval": 65.0,
            "coverage": 72.0,
        }

        sample = CalibrationSample(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            question_id="q1",
            sim_answerability="partially_answerable",
            sim_score=0.55,
            sim_signals_found=2,
            sim_signals_total=5,
            sim_relevance_score=0.45,
            obs_mentioned=False,
            obs_cited=False,
            obs_provider="openai",
            obs_model="gpt-4o-mini",
            outcome_match=OutcomeMatch.OPTIMISTIC.value,
            prediction_accurate=False,
            question_category="offerings",
            question_difficulty="medium",
            question_text="What products does Test Company offer?",
            pillar_scores=pillar_scores,
        )

        assert sample.pillar_scores == pillar_scores
        assert sample.pillar_scores["technical"] == 75.0
        assert sample.outcome_match == "optimistic"
        assert sample.prediction_accurate is False


class TestCalibrationConfigModel:
    """Tests for CalibrationConfig model."""

    def test_create_config_with_defaults(self):
        """Test creating a config with default weights."""
        # Note: SQLAlchemy defaults only apply on DB insert, not instantiation
        # We explicitly set the default values here
        config = CalibrationConfig(
            id=uuid.uuid4(),
            name="test-config",
            status=CalibrationConfigStatus.DRAFT.value,
            weight_technical=15.0,
            weight_structure=20.0,
            weight_schema=15.0,
            weight_authority=15.0,
            weight_retrieval=25.0,
            weight_coverage=10.0,
            threshold_fully_answerable=0.7,
            threshold_partially_answerable=0.3,
        )

        # Check default weights
        assert config.weight_technical == 15.0
        assert config.weight_structure == 20.0
        assert config.weight_schema == 15.0
        assert config.weight_authority == 15.0
        assert config.weight_retrieval == 25.0
        assert config.weight_coverage == 10.0

        # Check default thresholds
        assert config.threshold_fully_answerable == 0.7
        assert config.threshold_partially_answerable == 0.3

    def test_weights_property(self):
        """Test weights property returns dict."""
        config = CalibrationConfig(
            id=uuid.uuid4(),
            name="test-config",
            weight_technical=12.0,
            weight_structure=18.0,
            weight_schema=13.0,
            weight_authority=12.0,
            weight_entity_recognition=13.0,
            weight_retrieval=22.0,
            weight_coverage=10.0,
        )

        weights = config.weights
        assert weights["technical"] == 12.0
        assert weights["structure"] == 18.0
        assert weights["entity_recognition"] == 13.0
        assert sum(weights.values()) == 100.0

    def test_weights_sum_property(self):
        """Test weights_sum property."""
        config = CalibrationConfig(
            id=uuid.uuid4(),
            name="valid-config",
            weight_technical=12.0,
            weight_structure=18.0,
            weight_schema=13.0,
            weight_authority=12.0,
            weight_entity_recognition=13.0,
            weight_retrieval=22.0,
            weight_coverage=10.0,
        )

        assert config.weights_sum == 100.0

    def test_validate_weights_valid(self):
        """Test weight validation with valid weights."""
        config = CalibrationConfig(
            id=uuid.uuid4(),
            name="valid-config",
            weight_technical=12.0,
            weight_structure=18.0,
            weight_schema=13.0,
            weight_authority=12.0,
            weight_entity_recognition=13.0,
            weight_retrieval=22.0,
            weight_coverage=10.0,
        )

        errors = config.validate_weights()
        assert len(errors) == 0

    def test_validate_weights_sum_error(self):
        """Test weight validation with incorrect sum."""
        config = CalibrationConfig(
            id=uuid.uuid4(),
            name="invalid-config",
            weight_technical=20.0,
            weight_structure=20.0,
            weight_schema=20.0,
            weight_authority=20.0,
            weight_entity_recognition=13.0,
            weight_retrieval=25.0,
            weight_coverage=10.0,  # Sum = 128
        )

        errors = config.validate_weights()
        assert len(errors) > 0
        assert any("sum to 100" in e for e in errors)

    def test_validate_weights_bounds_error(self):
        """Test weight validation with out-of-bounds weights."""
        config = CalibrationConfig(
            id=uuid.uuid4(),
            name="invalid-config",
            weight_technical=3.0,  # Below min 5
            weight_structure=40.0,  # Above max 35
            weight_schema=15.0,
            weight_authority=15.0,
            weight_entity_recognition=10.0,
            weight_retrieval=17.0,
            weight_coverage=10.0,
        )

        errors = config.validate_weights()
        assert len(errors) >= 2
        assert any("at least 5" in e for e in errors)
        assert any("at most 35" in e for e in errors)


class TestCalibrationExperimentModel:
    """Tests for CalibrationExperiment model."""

    def test_create_experiment(self):
        """Test creating an A/B experiment."""
        control_id = uuid.uuid4()
        treatment_id = uuid.uuid4()

        experiment = CalibrationExperiment(
            id=uuid.uuid4(),
            name="Test Weight Optimization",
            control_config_id=control_id,
            treatment_config_id=treatment_id,
            treatment_allocation=0.1,
            status=ExperimentStatus.DRAFT.value,
            min_samples_per_arm=100,
            control_samples=0,
            treatment_samples=0,
        )

        assert experiment.control_config_id == control_id
        assert experiment.treatment_config_id == treatment_id
        assert experiment.treatment_allocation == 0.1
        assert experiment.status == "draft"
        assert experiment.control_samples == 0
        assert experiment.treatment_samples == 0

    def test_experiment_results(self):
        """Test experiment with results."""
        experiment = CalibrationExperiment(
            id=uuid.uuid4(),
            name="Completed Experiment",
            control_config_id=uuid.uuid4(),
            treatment_config_id=uuid.uuid4(),
            status=ExperimentStatus.CONCLUDED.value,
            control_samples=150,
            treatment_samples=145,
            control_accuracy=0.72,
            treatment_accuracy=0.78,
            p_value=0.03,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment showed 6% improvement with p < 0.05",
        )

        assert experiment.control_accuracy == 0.72
        assert experiment.treatment_accuracy == 0.78
        assert experiment.is_significant is True
        assert experiment.winner == "treatment"


class TestCalibrationDriftAlertModel:
    """Tests for CalibrationDriftAlert model."""

    def test_create_accuracy_drift_alert(self):
        """Test creating an accuracy drift alert."""
        now = datetime.now(UTC)
        week_ago = now - timedelta(days=7)

        alert = CalibrationDriftAlert(
            id=uuid.uuid4(),
            drift_type=DriftType.ACCURACY.value,
            expected_value=0.75,
            observed_value=0.62,
            drift_magnitude=0.13,
            sample_window_start=week_ago,
            sample_window_end=now,
            sample_count=120,
            status=DriftAlertStatus.OPEN.value,
        )

        assert alert.drift_type == "accuracy"
        assert alert.drift_magnitude == 0.13
        assert alert.status == "open"

    def test_create_optimism_drift_alert(self):
        """Test creating an optimism bias drift alert."""
        alert = CalibrationDriftAlert(
            id=uuid.uuid4(),
            drift_type=DriftType.OPTIMISM.value,
            expected_value=0.20,
            observed_value=0.35,
            drift_magnitude=0.15,
            sample_window_start=datetime.now(UTC) - timedelta(days=7),
            sample_window_end=datetime.now(UTC),
            sample_count=100,
            status=DriftAlertStatus.OPEN.value,
        )

        assert alert.drift_type == "optimism"
        assert alert.observed_value > alert.expected_value

    def test_alert_resolution(self):
        """Test drift alert resolution."""
        alert = CalibrationDriftAlert(
            id=uuid.uuid4(),
            drift_type=DriftType.ACCURACY.value,
            expected_value=0.75,
            observed_value=0.65,
            drift_magnitude=0.10,
            sample_window_start=datetime.now(UTC) - timedelta(days=7),
            sample_window_end=datetime.now(UTC),
            sample_count=100,
            status=DriftAlertStatus.RESOLVED.value,
            resolved_by=uuid.uuid4(),
            resolution_notes="Recalibrated weights based on new data",
            resolution_action="recalibrated",
            resolved_at=datetime.now(UTC),
        )

        assert alert.status == "resolved"
        assert alert.resolution_action == "recalibrated"
        assert alert.resolved_at is not None


class TestOutcomeMatchEnum:
    """Tests for OutcomeMatch enum."""

    def test_outcome_match_values(self):
        """Test OutcomeMatch enum values."""
        assert OutcomeMatch.CORRECT.value == "correct"
        assert OutcomeMatch.OPTIMISTIC.value == "optimistic"
        assert OutcomeMatch.PESSIMISTIC.value == "pessimistic"
        assert OutcomeMatch.UNKNOWN.value == "unknown"


class TestDriftTypeEnum:
    """Tests for DriftType enum."""

    def test_drift_type_values(self):
        """Test DriftType enum values."""
        assert DriftType.ACCURACY.value == "accuracy"
        assert DriftType.OPTIMISM.value == "optimism"
        assert DriftType.PESSIMISM.value == "pessimism"
        assert DriftType.PILLAR.value == "pillar"


class TestConfigStatusEnum:
    """Tests for CalibrationConfigStatus enum."""

    def test_config_status_values(self):
        """Test CalibrationConfigStatus enum values."""
        assert CalibrationConfigStatus.DRAFT.value == "draft"
        assert CalibrationConfigStatus.VALIDATED.value == "validated"
        assert CalibrationConfigStatus.ACTIVE.value == "active"
        assert CalibrationConfigStatus.ARCHIVED.value == "archived"


class TestExperimentStatusEnum:
    """Tests for ExperimentStatus enum."""

    def test_experiment_status_values(self):
        """Test ExperimentStatus enum values."""
        assert ExperimentStatus.DRAFT.value == "draft"
        assert ExperimentStatus.RUNNING.value == "running"
        assert ExperimentStatus.CONCLUDED.value == "concluded"


class TestCalibrationTaskHelpers:
    """Tests for calibration task helper functions."""

    def test_map_outcome_match(self):
        """Test outcome match mapping function."""
        from worker.observation.comparison import OutcomeMatch as CompOutcomeMatch
        from worker.tasks.calibration import _map_outcome_match

        assert _map_outcome_match(CompOutcomeMatch.CORRECT) == "correct"
        assert _map_outcome_match(CompOutcomeMatch.OPTIMISTIC) == "optimistic"
        assert _map_outcome_match(CompOutcomeMatch.PESSIMISTIC) == "pessimistic"
        assert _map_outcome_match(CompOutcomeMatch.UNKNOWN) == "unknown"

    def test_get_calibration_weights_returns_dict(self):
        """Test that get_calibration_weights returns a dict with correct keys."""
        from worker.tasks.calibration import get_calibration_weights

        weights = get_calibration_weights()

        assert isinstance(weights, dict)
        assert "technical" in weights
        assert "structure" in weights
        assert "schema" in weights
        assert "authority" in weights
        assert "entity_recognition" in weights
        assert "retrieval" in weights
        assert "coverage" in weights

        # Check default values (7-pillar system)
        assert weights["technical"] == 12.0
        assert weights["structure"] == 18.0
        assert weights["retrieval"] == 22.0
        assert sum(weights.values()) == 100.0
