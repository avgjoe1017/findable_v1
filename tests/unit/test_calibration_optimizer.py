"""Tests for calibration optimizer module."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.calibration.optimizer import (
    DEFAULT_WEIGHTS,
    MAX_WEIGHT,
    MIN_WEIGHT,
    OptimizationResult,
    _are_adjacent,
    _calculate_threshold_accuracy,
    _calculate_weighted_accuracy,
    _frange,
    generate_weight_combinations,
    optimize_answerability_thresholds,
    optimize_pillar_weights,
    validate_config_improvement,
)


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_default_values(self):
        """OptimizationResult has sensible defaults."""
        result = OptimizationResult()

        assert result.best_weights is None
        assert result.best_thresholds is None
        assert result.best_accuracy == 0.0
        assert result.baseline_accuracy == 0.0
        assert result.is_improvement is False
        assert result.improvement_sufficient is False
        assert result.min_improvement_threshold == 0.02
        assert result.errors == []

    def test_to_dict(self):
        """OptimizationResult serializes correctly."""
        result = OptimizationResult(
            best_weights={"technical": 20.0, "structure": 20.0},
            best_accuracy=0.85,
            baseline_accuracy=0.80,
            improvement=0.05,
            is_improvement=True,
            improvement_sufficient=True,
        )

        data = result.to_dict()

        assert data["best_accuracy"] == 0.85
        assert data["baseline_accuracy"] == 0.80
        assert data["improvement"] == 0.05
        assert data["is_improvement"] is True
        assert data["improvement_sufficient"] is True


class TestGenerateWeightCombinations:
    """Tests for weight combination generation."""

    def test_generates_combinations(self):
        """Generates non-empty list of combinations."""
        combinations = generate_weight_combinations()

        assert len(combinations) > 0

    def test_all_combinations_sum_to_100(self):
        """All generated combinations sum to 100."""
        combinations = generate_weight_combinations()

        for weights in combinations:
            total = sum(weights.values())
            assert abs(total - 100.0) < 0.01, f"Weights sum to {total}, not 100"

    def test_all_weights_within_bounds(self):
        """All weights are within min/max bounds."""
        combinations = generate_weight_combinations()

        for weights in combinations:
            for pillar, weight in weights.items():
                assert weight >= MIN_WEIGHT, f"{pillar} weight {weight} < {MIN_WEIGHT}"
                assert weight <= MAX_WEIGHT, f"{pillar} weight {weight} > {MAX_WEIGHT}"

    def test_includes_all_pillars(self):
        """Each combination includes all 7 pillars."""
        expected_pillars = {
            "technical",
            "structure",
            "schema",
            "authority",
            "entity_recognition",
            "retrieval",
            "coverage",
        }
        combinations = generate_weight_combinations()

        for weights in combinations:
            assert set(weights.keys()) == expected_pillars

    def test_includes_combination_near_defaults(self):
        """At least one combination is close to default weights."""
        combinations = generate_weight_combinations()

        # With 7 pillars and step=5, exact defaults may not be on grid
        # Check if any combination is within 25 total points of defaults
        found_close = False
        for weights in combinations:
            total_diff = sum(abs(weights[p] - DEFAULT_WEIGHTS[p]) for p in weights)
            if total_diff < 25:
                found_close = True
                break

        assert found_close, "No combination close to default weights"


class TestCalculateWeightedAccuracy:
    """Tests for _calculate_weighted_accuracy function."""

    def test_empty_samples_returns_zero(self):
        """Empty sample list returns 0 accuracy."""
        accuracy = _calculate_weighted_accuracy([], DEFAULT_WEIGHTS)
        assert accuracy == 0.0

    def test_perfect_accuracy_when_all_correct(self):
        """Returns 1.0 when all predictions are correct."""
        # Create mock samples where high pillar scores = mentioned
        samples = []
        for _ in range(10):
            sample = MagicMock()
            sample.pillar_scores = {
                "technical": 80.0,
                "structure": 80.0,
                "schema": 80.0,
                "authority": 80.0,
                "entity_recognition": 80.0,
                "retrieval": 80.0,
                "coverage": 80.0,
            }
            sample.obs_mentioned = True  # High score -> should be mentioned
            samples.append(sample)

        accuracy = _calculate_weighted_accuracy(samples, DEFAULT_WEIGHTS)
        assert accuracy == 1.0

    def test_zero_accuracy_when_all_wrong(self):
        """Returns 0.0 when all predictions are wrong."""
        # Create mock samples where high pillar scores but NOT mentioned
        samples = []
        for _ in range(10):
            sample = MagicMock()
            sample.pillar_scores = {
                "technical": 80.0,
                "structure": 80.0,
                "schema": 80.0,
                "authority": 80.0,
                "entity_recognition": 80.0,
                "retrieval": 80.0,
                "coverage": 80.0,
            }
            sample.obs_mentioned = False  # Prediction wrong: high score but not mentioned
            samples.append(sample)

        accuracy = _calculate_weighted_accuracy(samples, DEFAULT_WEIGHTS)
        assert accuracy == 0.0

    def test_skips_samples_without_pillar_scores(self):
        """Samples without pillar_scores are skipped."""
        samples = [
            MagicMock(pillar_scores=None, obs_mentioned=True),
            MagicMock(pillar_scores=None, obs_mentioned=False),
        ]

        accuracy = _calculate_weighted_accuracy(samples, DEFAULT_WEIGHTS)
        assert accuracy == 0.0  # No valid samples


class TestCalculateThresholdAccuracy:
    """Tests for _calculate_threshold_accuracy function."""

    def test_empty_samples_returns_zero(self):
        """Empty sample list returns 0 accuracy."""
        thresholds = {"fully_answerable": 0.7, "partially_answerable": 0.3}
        accuracy = _calculate_threshold_accuracy([], thresholds)
        assert accuracy == 0.0

    def test_fully_answerable_prediction(self):
        """Correctly predicts fully answerable."""
        sample = MagicMock()
        sample.sim_score = 0.8  # Above fully_answerable threshold
        sample.obs_mentioned = True
        sample.obs_cited = True  # Cited = fully answerable

        thresholds = {"fully_answerable": 0.7, "partially_answerable": 0.3}
        accuracy = _calculate_threshold_accuracy([sample], thresholds)

        assert accuracy == 1.0

    def test_not_answerable_prediction(self):
        """Correctly predicts not answerable."""
        sample = MagicMock()
        sample.sim_score = 0.2  # Below partially_answerable threshold
        sample.obs_mentioned = False
        sample.obs_cited = False

        thresholds = {"fully_answerable": 0.7, "partially_answerable": 0.3}
        accuracy = _calculate_threshold_accuracy([sample], thresholds)

        assert accuracy == 1.0


class TestAreAdjacent:
    """Tests for _are_adjacent helper function."""

    def test_not_and_partial_are_adjacent(self):
        """not_answerable and partially_answerable are adjacent."""
        assert _are_adjacent("not_answerable", "partially_answerable") is True
        assert _are_adjacent("partially_answerable", "not_answerable") is True

    def test_partial_and_fully_are_adjacent(self):
        """partially_answerable and fully_answerable are adjacent."""
        assert _are_adjacent("partially_answerable", "fully_answerable") is True
        assert _are_adjacent("fully_answerable", "partially_answerable") is True

    def test_not_and_fully_not_adjacent(self):
        """not_answerable and fully_answerable are not adjacent."""
        assert _are_adjacent("not_answerable", "fully_answerable") is False
        assert _are_adjacent("fully_answerable", "not_answerable") is False

    def test_same_level_not_adjacent(self):
        """Same level is not adjacent to itself."""
        assert _are_adjacent("fully_answerable", "fully_answerable") is False


class TestFrange:
    """Tests for _frange helper function."""

    def test_generates_floats(self):
        """Generates correct float sequence."""
        result = list(_frange(0.0, 1.0, 0.25))
        expected = [0.0, 0.25, 0.5, 0.75, 1.0]

        assert len(result) == len(expected)
        for r, e in zip(result, expected, strict=False):
            assert abs(r - e) < 0.001

    def test_single_value(self):
        """Single value when start equals stop."""
        result = list(_frange(0.5, 0.5, 0.1))
        assert result == [0.5]

    def test_empty_when_start_exceeds_stop(self):
        """Empty when start > stop."""
        result = list(_frange(1.0, 0.0, 0.1))
        assert result == []


class TestOptimizePillarWeightsAsync:
    """Tests for async optimize_pillar_weights function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.optimizer.async_session_maker")
    async def test_returns_error_with_insufficient_samples(self, mock_session_maker):
        """Returns error when not enough samples."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No samples
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await optimize_pillar_weights(min_samples=100)

        assert len(result.errors) > 0
        assert "Insufficient samples" in result.errors[0]
        assert result.best_weights is None


class TestOptimizeAnswerabilityThresholdsAsync:
    """Tests for async optimize_answerability_thresholds function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.optimizer.async_session_maker")
    async def test_returns_error_with_insufficient_samples(self, mock_session_maker):
        """Returns error when not enough samples."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # No samples
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await optimize_answerability_thresholds(min_samples=100)

        assert len(result.errors) > 0
        assert "Insufficient samples" in result.errors[0]
        assert result.best_thresholds is None


class TestValidateConfigImprovementAsync:
    """Tests for async validate_config_improvement function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.optimizer.async_session_maker")
    async def test_returns_error_when_config_not_found(self, mock_session_maker):
        """Returns error when config doesn't exist."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Config not found
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await validate_config_improvement(uuid.uuid4())

        assert result["valid"] is False
        assert "not found" in result["error"]


class TestDefaultWeights:
    """Tests for default weight configuration."""

    def test_default_weights_sum_to_100(self):
        """Default weights sum to 100."""
        total = sum(DEFAULT_WEIGHTS.values())
        assert abs(total - 100.0) < 0.01

    def test_default_weights_within_bounds(self):
        """Default weights are within min/max bounds."""
        for pillar, weight in DEFAULT_WEIGHTS.items():
            assert weight >= MIN_WEIGHT, f"{pillar} weight {weight} < {MIN_WEIGHT}"
            assert weight <= MAX_WEIGHT, f"{pillar} weight {weight} > {MAX_WEIGHT}"

    def test_all_pillars_present(self):
        """All seven pillars are present in defaults."""
        expected = {
            "technical",
            "structure",
            "schema",
            "authority",
            "entity_recognition",
            "retrieval",
            "coverage",
        }
        assert set(DEFAULT_WEIGHTS.keys()) == expected
