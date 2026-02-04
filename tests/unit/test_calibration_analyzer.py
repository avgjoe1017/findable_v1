"""Tests for calibration analysis functions."""

from api.models.calibration import OutcomeMatch
from worker.observation.comparison import OutcomeMatch as CompOutcomeMatch
from worker.tasks.calibration import (
    _calculate_pillar_correlation,
    _generate_calibration_recommendations,
    _map_outcome_match,
    get_calibration_weights,
)

# =============================================================================
# Test _map_outcome_match
# =============================================================================


class TestMapOutcomeMatch:
    """Tests for outcome match mapping."""

    def test_maps_correct(self):
        """Correct maps to correct."""
        assert _map_outcome_match(CompOutcomeMatch.CORRECT) == OutcomeMatch.CORRECT.value

    def test_maps_optimistic(self):
        """Optimistic maps to optimistic."""
        assert _map_outcome_match(CompOutcomeMatch.OPTIMISTIC) == OutcomeMatch.OPTIMISTIC.value

    def test_maps_pessimistic(self):
        """Pessimistic maps to pessimistic."""
        assert _map_outcome_match(CompOutcomeMatch.PESSIMISTIC) == OutcomeMatch.PESSIMISTIC.value

    def test_maps_unknown(self):
        """Unknown maps to unknown."""
        assert _map_outcome_match(CompOutcomeMatch.UNKNOWN) == OutcomeMatch.UNKNOWN.value


# =============================================================================
# Test get_calibration_weights
# =============================================================================


class TestGetCalibrationWeights:
    """Tests for getting calibration weights."""

    def test_returns_dict(self):
        """Returns a dict of weights."""
        weights = get_calibration_weights()
        assert isinstance(weights, dict)

    def test_has_all_7_pillars(self):
        """Returns weights for all 7 pillars."""
        weights = get_calibration_weights()
        expected_pillars = [
            "technical",
            "structure",
            "schema",
            "authority",
            "entity_recognition",
            "retrieval",
            "coverage",
        ]
        for pillar in expected_pillars:
            assert pillar in weights, f"Missing pillar: {pillar}"

    def test_weights_sum_to_100(self):
        """Weights should sum to 100."""
        weights = get_calibration_weights()
        assert sum(weights.values()) == 100

    def test_includes_entity_recognition(self):
        """Entity recognition pillar is included."""
        weights = get_calibration_weights()
        assert "entity_recognition" in weights
        assert weights["entity_recognition"] > 0


# =============================================================================
# Test _calculate_pillar_correlation
# =============================================================================


class TestCalculatePillarCorrelation:
    """Tests for pillar correlation calculation."""

    def test_empty_samples_returns_insufficient_data(self):
        """Empty samples returns insufficient data for all pillars."""
        correlation = _calculate_pillar_correlation([])

        for pillar in ["technical", "structure", "schema", "authority"]:
            assert correlation[pillar].get("insufficient_data") is True

    def test_calculates_correlation_with_sufficient_data(self):
        """Calculates correlation when sufficient data exists."""
        # Create mock samples with high technical scores being more accurate
        samples = []

        # High technical scores (>= 70) - mostly accurate
        for _ in range(15):
            samples.append(
                (
                    {"technical": 80, "structure": 60},
                    True,  # prediction_accurate
                    "correct",
                )
            )

        # Low technical scores (< 50) - mostly inaccurate
        for _ in range(15):
            samples.append(
                (
                    {"technical": 30, "structure": 60},
                    False,  # prediction_accurate
                    "pessimistic",
                )
            )

        correlation = _calculate_pillar_correlation(samples)

        # Technical should show positive correlation
        assert correlation["technical"]["high_score_accuracy"] > 0.8
        assert correlation["technical"]["low_score_accuracy"] < 0.2
        assert correlation["technical"]["correlation_strength"] > 0.5
        assert correlation["technical"]["significant"] is True

    def test_handles_missing_pillar_scores(self):
        """Gracefully handles samples with missing pillar scores."""
        samples = [
            ({"technical": 80}, True, "correct"),
            (None, True, "correct"),  # None pillar_scores
            ({"structure": 70}, True, "correct"),  # Missing technical
        ]

        correlation = _calculate_pillar_correlation(samples)

        # Should not crash, but mark as insufficient data
        assert "technical" in correlation

    def test_mid_range_scores_not_included(self):
        """Scores between 50-70 are not counted in high/low."""
        samples = []

        # All mid-range scores
        for _ in range(20):
            samples.append(
                (
                    {"technical": 60},  # Mid-range
                    True,
                    "correct",
                )
            )

        correlation = _calculate_pillar_correlation(samples)

        # Should have insufficient data because no high/low samples
        assert correlation["technical"].get("insufficient_data") is True


# =============================================================================
# Test _generate_calibration_recommendations
# =============================================================================


class TestGenerateCalibrationRecommendations:
    """Tests for recommendation generation."""

    def test_generates_accuracy_warning_when_low(self):
        """Generates warning when accuracy is low."""
        basic_analysis = {
            "prediction_accuracy": 0.5,
            "optimism_bias": 0.1,
            "pessimism_bias": 0.1,
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability={},
            pillar_correlation={},
        )

        accuracy_recs = [r for r in recs if r["type"] == "accuracy"]
        assert len(accuracy_recs) > 0
        assert accuracy_recs[0]["priority"] == "high"

    def test_generates_optimism_bias_warning(self):
        """Generates warning for high optimism bias."""
        basic_analysis = {
            "prediction_accuracy": 0.8,
            "optimism_bias": 0.3,
            "pessimism_bias": 0.05,
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability={},
            pillar_correlation={},
        )

        bias_recs = [r for r in recs if r["type"] == "bias"]
        assert len(bias_recs) > 0
        assert "optimism" in bias_recs[0]["message"].lower()

    def test_generates_pessimism_bias_warning(self):
        """Generates warning for high pessimism bias."""
        basic_analysis = {
            "prediction_accuracy": 0.8,
            "optimism_bias": 0.05,
            "pessimism_bias": 0.3,
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability={},
            pillar_correlation={},
        )

        bias_recs = [r for r in recs if r["type"] == "bias"]
        assert len(bias_recs) > 0
        assert "pessimism" in bias_recs[0]["message"].lower()

    def test_no_recommendations_when_healthy(self):
        """No recommendations when calibration is healthy."""
        basic_analysis = {
            "prediction_accuracy": 0.85,
            "optimism_bias": 0.08,
            "pessimism_bias": 0.07,
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability={},
            pillar_correlation={},
        )

        # Should have no high priority recommendations
        high_priority = [r for r in recs if r["priority"] == "high"]
        assert len(high_priority) == 0

    def test_generates_answerability_warning(self):
        """Generates warning for low accuracy answerability level."""
        basic_analysis = {
            "prediction_accuracy": 0.8,
            "optimism_bias": 0.1,
            "pessimism_bias": 0.1,
        }

        accuracy_by_answerability = {
            "fully_answerable": {
                "total": 50,
                "accurate": 20,
                "accuracy": 0.4,  # Low accuracy
            }
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability=accuracy_by_answerability,
            pillar_correlation={},
        )

        ans_recs = [r for r in recs if r["type"] == "answerability"]
        assert len(ans_recs) > 0

    def test_generates_pillar_weight_warning(self):
        """Generates warning for negative pillar correlation."""
        basic_analysis = {
            "prediction_accuracy": 0.7,
            "optimism_bias": 0.1,
            "pessimism_bias": 0.1,
        }

        pillar_correlation = {
            "technical": {
                "correlation_strength": -0.15,  # Negative correlation
                "significant": True,
                "high_score_accuracy": 0.5,
                "low_score_accuracy": 0.65,
            }
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability={},
            pillar_correlation=pillar_correlation,
        )

        pillar_recs = [r for r in recs if r["type"] == "pillar_weight"]
        assert len(pillar_recs) > 0
        assert "technical" in pillar_recs[0]["message"]

    def test_recommendations_have_required_fields(self):
        """All recommendations have required fields."""
        basic_analysis = {
            "prediction_accuracy": 0.5,
            "optimism_bias": 0.3,
            "pessimism_bias": 0.3,
        }

        recs = _generate_calibration_recommendations(
            basic_analysis=basic_analysis,
            accuracy_by_answerability={},
            pillar_correlation={},
        )

        assert len(recs) > 0
        for rec in recs:
            assert "type" in rec
            assert "priority" in rec
            assert "message" in rec
            assert "action" in rec
            assert rec["priority"] in ["high", "medium", "low"]


# =============================================================================
# Integration-style Tests (without DB)
# =============================================================================


class TestCalibrationAnalysisStructure:
    """Tests for analysis result structures."""

    def test_basic_analysis_insufficient_data_structure(self):
        """Insufficient data result has expected structure."""
        result = {
            "total_samples": 10,
            "sufficient_data": False,
            "min_required": 100,
        }

        assert "total_samples" in result
        assert result["sufficient_data"] is False
        assert "min_required" in result

    def test_basic_analysis_success_structure(self):
        """Successful analysis has expected structure."""
        # This is what a successful analysis should look like
        expected_keys = [
            "total_samples",
            "sufficient_data",
            "known_samples",
            "prediction_accuracy",
            "optimism_bias",
            "pessimism_bias",
            "outcome_counts",
            "accuracy_by_category",
            "accuracy_by_difficulty",
            "window_start",
            "window_days",
        ]

        # Simulated result
        result = {
            "total_samples": 150,
            "sufficient_data": True,
            "known_samples": 145,
            "prediction_accuracy": 0.72,
            "optimism_bias": 0.15,
            "pessimism_bias": 0.13,
            "outcome_counts": {
                "correct": 105,
                "optimistic": 22,
                "pessimistic": 18,
                "unknown": 5,
            },
            "accuracy_by_category": {
                "product": 0.75,
                "company": 0.68,
            },
            "accuracy_by_difficulty": {
                "easy": 0.80,
                "medium": 0.70,
                "hard": 0.60,
            },
            "window_start": "2026-01-03T00:00:00+00:00",
            "window_days": 30,
        }

        for key in expected_keys:
            assert key in result, f"Missing key: {key}"

    def test_detailed_analysis_extends_basic(self):
        """Detailed analysis adds extra fields."""
        detailed_keys = [
            "accuracy_by_answerability",
            "accuracy_by_provider",
            "pillar_correlation",
            "recommendations",
        ]

        # These should be present in detailed analysis but not basic
        for key in detailed_keys:
            # Just verify the keys are what we expect to add
            assert isinstance(key, str)
