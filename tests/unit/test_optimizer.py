"""Tests for calibration optimizer."""

from worker.calibration.optimizer import (
    DEFAULT_WEIGHTS,
    MAX_WEIGHT,
    MIN_WEIGHT,
    TOTAL_WEIGHT,
    OptimizationResult,
    _are_adjacent,
    _calculate_threshold_accuracy,
    _calculate_weighted_accuracy,
    _generate_fine_search_combinations,
    generate_weight_combinations,
)

# ============================================================================
# Test Weight Constraints
# ============================================================================


class TestWeightConstraints:
    """Tests for weight constraint constants."""

    def test_default_weights_sum_to_100(self):
        """Default weights should sum to 100."""
        assert sum(DEFAULT_WEIGHTS.values()) == 100.0

    def test_default_weights_has_7_pillars(self):
        """Default weights should have 7 pillars including entity_recognition."""
        expected_pillars = [
            "technical",
            "structure",
            "schema",
            "authority",
            "entity_recognition",
            "retrieval",
            "coverage",
        ]
        assert len(DEFAULT_WEIGHTS) == 7
        for pillar in expected_pillars:
            assert pillar in DEFAULT_WEIGHTS

    def test_default_weights_within_bounds(self):
        """Each default weight should be within MIN_WEIGHT and MAX_WEIGHT."""
        for pillar, weight in DEFAULT_WEIGHTS.items():
            assert weight >= MIN_WEIGHT, f"{pillar} weight {weight} below minimum"
            assert weight <= MAX_WEIGHT, f"{pillar} weight {weight} above maximum"

    def test_total_weight_constant(self):
        """Total weight constant should be 100."""
        assert TOTAL_WEIGHT == 100.0


# ============================================================================
# Test Weight Combinations Generation
# ============================================================================


class TestGenerateWeightCombinations:
    """Tests for weight combination generation."""

    def test_generates_combinations(self):
        """Should generate non-empty list of combinations."""
        # With 7 pillars, step=5 works (step=10 produces no valid combos)
        combinations = generate_weight_combinations(step=5)
        assert len(combinations) > 0

    def test_all_combinations_sum_to_100(self):
        """All generated combinations should sum to 100."""
        combinations = generate_weight_combinations(step=5)
        # Just test first 100 to avoid slow test
        for weights in combinations[:100]:
            total = sum(weights.values())
            assert total == 100.0, f"Combination sums to {total}, not 100"

    def test_all_combinations_within_bounds(self):
        """All weights in combinations should be within bounds."""
        combinations = generate_weight_combinations(step=5)
        # Just test first 100 to avoid slow test
        for weights in combinations[:100]:
            for pillar, weight in weights.items():
                assert weight >= MIN_WEIGHT, f"{pillar}={weight} below minimum"
                assert weight <= MAX_WEIGHT, f"{pillar}={weight} above maximum"

    def test_all_combinations_have_7_pillars(self):
        """All combinations should have 7 pillars."""
        combinations = generate_weight_combinations(step=5)
        for weights in combinations[:100]:
            assert len(weights) == 7

    def test_step_10_produces_no_combos_for_7_pillars(self):
        """Step=10 with 7 pillars produces no valid combinations."""
        # With 7 pillars and step=10, values are [5,15,25,35]
        # Average is 20, but we need average ~14.3 to sum to 100
        coarse = generate_weight_combinations(step=10)
        assert len(coarse) == 0

    def test_combinations_include_defaults_approximately(self):
        """At least one combination should be close to defaults."""
        combinations = generate_weight_combinations(step=5)

        # Check if any combination is close to defaults
        # (defaults won't match exactly if they're not on the grid)
        found_close = False
        for weights in combinations:
            diffs = sum(abs(weights[p] - DEFAULT_WEIGHTS[p]) for p in weights)
            if diffs < 30:  # Within 30 total points
                found_close = True
                break

        assert found_close, "No combination close to default weights"


# ============================================================================
# Test Fine Search Generation
# ============================================================================


class TestFineSearchCombinations:
    """Tests for fine search around a center point."""

    def test_generates_combinations_around_center(self):
        """Should generate combinations around center weights."""
        center = {
            "technical": 15.0,
            "structure": 15.0,
            "schema": 15.0,
            "authority": 15.0,
            "entity_recognition": 10.0,
            "retrieval": 20.0,
            "coverage": 10.0,
        }
        combinations = _generate_fine_search_combinations(center, step=5)
        assert len(combinations) > 0

    def test_fine_combinations_sum_to_100(self):
        """All fine search combinations should sum to 100."""
        center = DEFAULT_WEIGHTS.copy()
        combinations = _generate_fine_search_combinations(center, step=5)
        for weights in combinations:
            total = sum(weights.values())
            assert total == 100.0

    def test_fine_combinations_within_bounds(self):
        """Fine search combinations should stay within bounds."""
        center = DEFAULT_WEIGHTS.copy()
        combinations = _generate_fine_search_combinations(center, step=5)
        for weights in combinations:
            for _, weight in weights.items():
                assert weight >= MIN_WEIGHT
                assert weight <= MAX_WEIGHT


# ============================================================================
# Test Weighted Accuracy Calculation
# ============================================================================


class TestCalculateWeightedAccuracy:
    """Tests for weighted accuracy calculation."""

    def test_empty_samples_returns_zero(self):
        """Empty samples should return 0 accuracy."""
        accuracy = _calculate_weighted_accuracy([], DEFAULT_WEIGHTS)
        assert accuracy == 0.0

    def test_returns_value_between_0_and_1(self):
        """Accuracy should be between 0 and 1."""

        # Create mock samples
        class MockSample:
            def __init__(self, pillar_scores, obs_cited):
                self.pillar_scores = pillar_scores
                self.obs_cited = obs_cited

        samples = [
            MockSample(
                {
                    "technical": 80,
                    "structure": 70,
                    "schema": 60,
                    "authority": 50,
                    "entity_recognition": 40,
                    "retrieval": 30,
                    "coverage": 20,
                },
                True,
            ),
            MockSample(
                {
                    "technical": 20,
                    "structure": 30,
                    "schema": 40,
                    "authority": 50,
                    "entity_recognition": 60,
                    "retrieval": 70,
                    "coverage": 80,
                },
                False,
            ),
        ]

        accuracy = _calculate_weighted_accuracy(samples, DEFAULT_WEIGHTS)
        assert 0.0 <= accuracy <= 1.0

    def test_handles_missing_pillar_scores(self):
        """Should handle samples with None pillar_scores."""

        class MockSample:
            def __init__(self, pillar_scores, obs_cited):
                self.pillar_scores = pillar_scores
                self.obs_cited = obs_cited

        samples = [
            MockSample(None, True),
            MockSample({}, False),
        ]

        accuracy = _calculate_weighted_accuracy(samples, DEFAULT_WEIGHTS)
        assert 0.0 <= accuracy <= 1.0


# ============================================================================
# Test Threshold Accuracy Calculation
# ============================================================================


class TestCalculateThresholdAccuracy:
    """Tests for threshold accuracy calculation."""

    def test_empty_samples_returns_zero(self):
        """Empty samples should return 0 accuracy."""
        thresholds = {"fully_answerable": 0.7, "partially_answerable": 0.3}
        accuracy = _calculate_threshold_accuracy([], thresholds)
        assert accuracy == 0.0

    def test_returns_value_between_0_and_1(self):
        """Accuracy should be between 0 and 1."""

        class MockSample:
            def __init__(self, sim_score, obs_cited, obs_mentioned):
                self.sim_score = sim_score
                self.obs_cited = obs_cited
                self.obs_mentioned = obs_mentioned

        samples = [
            MockSample(0.8, True, True),  # High score, was cited
            MockSample(0.5, False, True),  # Medium score, mentioned
            MockSample(0.2, False, False),  # Low score, not mentioned
        ]

        thresholds = {"fully_answerable": 0.7, "partially_answerable": 0.3}
        accuracy = _calculate_threshold_accuracy(samples, thresholds)
        assert 0.0 <= accuracy <= 1.0


# ============================================================================
# Test Adjacent Levels
# ============================================================================


class TestAreAdjacent:
    """Tests for adjacent answerability level detection."""

    def test_same_level_not_adjacent(self):
        """Same levels are not adjacent."""
        assert not _are_adjacent("fully_answerable", "fully_answerable")
        assert not _are_adjacent("not_answerable", "not_answerable")

    def test_adjacent_levels(self):
        """Adjacent levels should return True."""
        assert _are_adjacent("fully_answerable", "partially_answerable")
        assert _are_adjacent("partially_answerable", "fully_answerable")
        assert _are_adjacent("partially_answerable", "not_answerable")
        assert _are_adjacent("not_answerable", "partially_answerable")

    def test_non_adjacent_levels(self):
        """Non-adjacent levels should return False."""
        assert not _are_adjacent("fully_answerable", "not_answerable")
        assert not _are_adjacent("not_answerable", "fully_answerable")

    def test_invalid_levels(self):
        """Invalid levels should return False."""
        assert not _are_adjacent("invalid", "fully_answerable")
        assert not _are_adjacent("fully_answerable", "invalid")


# ============================================================================
# Test OptimizationResult
# ============================================================================


class TestOptimizationResult:
    """Tests for OptimizationResult dataclass."""

    def test_default_values(self):
        """Default values should be sensible."""
        result = OptimizationResult()
        assert result.best_weights is None
        assert result.best_accuracy == 0.0
        assert result.is_improvement is False
        assert result.errors == []

    def test_to_dict(self):
        """to_dict should return serializable dict."""
        result = OptimizationResult(
            best_weights=DEFAULT_WEIGHTS.copy(),
            best_accuracy=0.75,
            baseline_accuracy=0.70,
            improvement=0.05,
            is_improvement=True,
            improvement_sufficient=True,
        )

        data = result.to_dict()

        assert "best_weights" in data
        assert "best_accuracy" in data
        assert "improvement" in data
        assert data["best_accuracy"] == 0.75
        assert data["improvement"] == 0.05
        assert data["is_improvement"] is True

    def test_to_dict_rounds_floats(self):
        """to_dict should round floats to 4 decimal places."""
        result = OptimizationResult(
            best_accuracy=0.75123456,
            baseline_accuracy=0.70987654,
        )

        data = result.to_dict()

        assert data["best_accuracy"] == 0.7512
        assert data["baseline_accuracy"] == 0.7099
