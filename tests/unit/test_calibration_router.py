"""Tests for calibration API router."""

import uuid

import pytest


class TestCalibrationSchemasValidation:
    """Tests for calibration schema validation."""

    def test_pillar_weights_valid(self):
        """Test valid pillar weights."""
        from api.schemas.calibration import PillarWeights

        weights = PillarWeights(
            technical=15.0,
            structure=20.0,
            schema=15.0,
            authority=15.0,
            retrieval=25.0,
            coverage=10.0,
        )
        assert weights.technical == 15.0
        assert weights.retrieval == 25.0

    def test_pillar_weights_bounds(self):
        """Test pillar weights bounds validation."""
        from pydantic import ValidationError

        from api.schemas.calibration import PillarWeights

        # Too low
        with pytest.raises(ValidationError):
            PillarWeights(
                technical=3.0,  # Below 5
                structure=20.0,
                schema=15.0,
                authority=15.0,
                retrieval=25.0,
                coverage=10.0,
            )

        # Too high
        with pytest.raises(ValidationError):
            PillarWeights(
                technical=40.0,  # Above 35
                structure=20.0,
                schema=15.0,
                authority=15.0,
                retrieval=25.0,
                coverage=10.0,
            )

    def test_answerability_thresholds_valid(self):
        """Test valid answerability thresholds."""
        from api.schemas.calibration import AnswerabilityThresholds

        thresholds = AnswerabilityThresholds(
            fully_answerable=0.75,
            partially_answerable=0.35,
        )
        assert thresholds.fully_answerable == 0.75
        assert thresholds.partially_answerable == 0.35

    def test_config_create_schema(self):
        """Test config create schema."""
        from api.schemas.calibration import (
            AnswerabilityThresholds,
            CalibrationConfigCreate,
            PillarWeights,
        )

        config = CalibrationConfigCreate(
            name="test-config",
            description="Test configuration",
            weights=PillarWeights(
                technical=15.0,
                structure=20.0,
                schema=15.0,
                authority=15.0,
                retrieval=25.0,
                coverage=10.0,
            ),
            thresholds=AnswerabilityThresholds(
                fully_answerable=0.7,
                partially_answerable=0.3,
            ),
        )
        assert config.name == "test-config"
        assert config.weights.technical == 15.0

    def test_config_create_name_too_short(self):
        """Test config create with name too short."""
        from pydantic import ValidationError

        from api.schemas.calibration import CalibrationConfigCreate

        with pytest.raises(ValidationError):
            CalibrationConfigCreate(name="ab")  # Less than 3 chars


class TestCalibrationAnalysisResponse:
    """Tests for calibration analysis response schema."""

    def test_insufficient_data_response(self):
        """Test response when insufficient data."""
        from api.schemas.calibration import CalibrationAnalysisResponse

        response = CalibrationAnalysisResponse(
            total_samples=50,
            sufficient_data=False,
            min_required=100,
        )
        assert response.total_samples == 50
        assert response.sufficient_data is False
        assert response.prediction_accuracy is None

    def test_sufficient_data_response(self):
        """Test response with sufficient data."""
        from datetime import UTC, datetime

        from api.schemas.calibration import CalibrationAnalysisResponse, OutcomeCounts

        response = CalibrationAnalysisResponse(
            total_samples=150,
            sufficient_data=True,
            min_required=100,
            known_samples=140,
            prediction_accuracy=0.72,
            optimism_bias=0.15,
            pessimism_bias=0.08,
            outcome_counts=OutcomeCounts(
                correct=100,
                optimistic=21,
                pessimistic=11,
                unknown=10,
            ),
            accuracy_by_category={"identity": 0.8, "offerings": 0.65},
            accuracy_by_difficulty={"easy": 0.82, "medium": 0.7, "hard": 0.55},
            window_start=datetime.now(UTC),
            window_days=30,
        )
        assert response.prediction_accuracy == 0.72
        assert response.outcome_counts.correct == 100


class TestDriftAlertSchemas:
    """Tests for drift alert schemas."""

    def test_drift_alert_response(self):
        """Test drift alert response schema."""
        from datetime import UTC, datetime

        from api.schemas.calibration import DriftAlertResponse

        now = datetime.now(UTC)
        response = DriftAlertResponse(
            id=uuid.uuid4(),
            drift_type="accuracy",
            affected_pillar=None,
            expected_value=0.75,
            observed_value=0.62,
            drift_magnitude=0.13,
            sample_window_start=now,
            sample_window_end=now,
            sample_count=120,
            status="open",
            resolution_notes=None,
            resolution_action=None,
            created_at=now,
            acknowledged_at=None,
            resolved_at=None,
        )
        assert response.drift_type == "accuracy"
        assert response.drift_magnitude == 0.13

    def test_drift_alert_resolve_request(self):
        """Test drift alert resolve request schema."""
        from api.schemas.calibration import DriftAlertResolve

        request = DriftAlertResolve(
            resolution_notes="Recalibrated weights after observing consistent bias",
            resolution_action="recalibrated",
        )
        assert len(request.resolution_notes) >= 10

    def test_drift_alert_resolve_notes_too_short(self):
        """Test drift alert resolve with notes too short."""
        from pydantic import ValidationError

        from api.schemas.calibration import DriftAlertResolve

        with pytest.raises(ValidationError):
            DriftAlertResolve(
                resolution_notes="Short",  # Less than 10 chars
                resolution_action="recalibrated",
            )


class TestExperimentSchemas:
    """Tests for experiment schemas."""

    def test_experiment_create_valid(self):
        """Test valid experiment create request."""
        from api.schemas.calibration import ExperimentCreate

        request = ExperimentCreate(
            name="Weight Optimization Test",
            description="Testing new pillar weights",
            control_config_id=uuid.uuid4(),
            treatment_config_id=uuid.uuid4(),
            treatment_allocation=0.1,
            min_samples_per_arm=100,
        )
        assert request.treatment_allocation == 0.1
        assert request.min_samples_per_arm == 100

    def test_experiment_create_allocation_bounds(self):
        """Test experiment create allocation bounds."""
        from pydantic import ValidationError

        from api.schemas.calibration import ExperimentCreate

        # Too low
        with pytest.raises(ValidationError):
            ExperimentCreate(
                name="Test",
                control_config_id=uuid.uuid4(),
                treatment_config_id=uuid.uuid4(),
                treatment_allocation=0.01,  # Below 0.05
            )

        # Too high
        with pytest.raises(ValidationError):
            ExperimentCreate(
                name="Test",
                control_config_id=uuid.uuid4(),
                treatment_config_id=uuid.uuid4(),
                treatment_allocation=0.6,  # Above 0.5
            )

    def test_experiment_response(self):
        """Test experiment response schema."""
        from datetime import UTC, datetime

        from api.schemas.calibration import ExperimentResponse

        now = datetime.now(UTC)
        response = ExperimentResponse(
            id=uuid.uuid4(),
            name="Completed Experiment",
            description="Test description",
            control_config_id=uuid.uuid4(),
            treatment_config_id=uuid.uuid4(),
            treatment_allocation=0.1,
            status="concluded",
            min_samples_per_arm=100,
            control_samples=150,
            treatment_samples=145,
            control_accuracy=0.72,
            treatment_accuracy=0.78,
            p_value=0.03,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment improved accuracy by 6%",
            created_at=now,
            started_at=now,
            concluded_at=now,
        )
        assert response.winner == "treatment"
        assert response.is_significant is True
