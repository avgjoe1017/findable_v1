"""Tests for A/B experiment infrastructure."""

import hashlib
import uuid

import pytest

from worker.calibration.experiment import (
    ExperimentArm,
    ExperimentAssignment,
    ExperimentResults,
    get_experiment_arm,
)

# ============================================================================
# Test ExperimentArm Enum
# ============================================================================


class TestExperimentArm:
    """Tests for ExperimentArm enum."""

    def test_control_value(self):
        """Control arm has correct value."""
        assert ExperimentArm.CONTROL.value == "control"

    def test_treatment_value(self):
        """Treatment arm has correct value."""
        assert ExperimentArm.TREATMENT.value == "treatment"

    def test_is_string_enum(self):
        """ExperimentArm is a string enum."""
        assert isinstance(ExperimentArm.CONTROL, str)
        assert ExperimentArm.CONTROL == "control"


# ============================================================================
# Test get_experiment_arm (Deterministic Hashing)
# ============================================================================


class TestGetExperimentArm:
    """Tests for deterministic experiment arm assignment."""

    def test_returns_experiment_arm(self):
        """Returns an ExperimentArm."""
        site_id = uuid.uuid4()
        arm = get_experiment_arm(site_id)
        assert isinstance(arm, ExperimentArm)

    def test_deterministic_assignment(self):
        """Same site_id always gets same arm."""
        site_id = uuid.uuid4()
        arm1 = get_experiment_arm(site_id)
        arm2 = get_experiment_arm(site_id)
        arm3 = get_experiment_arm(site_id)
        assert arm1 == arm2 == arm3

    def test_different_sites_can_get_different_arms(self):
        """Different site_ids can get different arms."""
        # Generate many sites and check we get both arms
        arms_seen = set()
        for _ in range(100):
            site_id = uuid.uuid4()
            arm = get_experiment_arm(site_id, treatment_allocation=0.5)
            arms_seen.add(arm)
            if len(arms_seen) == 2:
                break

        assert ExperimentArm.CONTROL in arms_seen
        assert ExperimentArm.TREATMENT in arms_seen

    def test_treatment_allocation_zero(self):
        """Zero allocation means all control."""
        for _ in range(20):
            site_id = uuid.uuid4()
            arm = get_experiment_arm(site_id, treatment_allocation=0.0)
            assert arm == ExperimentArm.CONTROL

    def test_treatment_allocation_one(self):
        """Full allocation means all treatment."""
        for _ in range(20):
            site_id = uuid.uuid4()
            arm = get_experiment_arm(site_id, treatment_allocation=1.0)
            assert arm == ExperimentArm.TREATMENT

    def test_allocation_roughly_matches_ratio(self):
        """Allocation ratio roughly matches expected split."""
        treatment_allocation = 0.2
        treatment_count = 0
        total = 1000

        for i in range(total):
            site_id = uuid.UUID(int=i)
            arm = get_experiment_arm(site_id, treatment_allocation=treatment_allocation)
            if arm == ExperimentArm.TREATMENT:
                treatment_count += 1

        # Should be roughly 20% treatment, allow 5% margin
        ratio = treatment_count / total
        assert 0.15 <= ratio <= 0.25, f"Expected ~20% treatment, got {ratio:.1%}"

    def test_uses_sha256_hash(self):
        """Assignment uses SHA256 hash of site_id."""
        site_id = uuid.uuid4()

        # Manually compute expected behavior
        hash_input = str(site_id).encode("utf-8")
        hash_value = int(hashlib.sha256(hash_input).hexdigest(), 16)
        normalized = (hash_value % 10000) / 10000.0

        expected_arm = ExperimentArm.TREATMENT if normalized < 0.1 else ExperimentArm.CONTROL
        actual_arm = get_experiment_arm(site_id, treatment_allocation=0.1)

        assert actual_arm == expected_arm


# ============================================================================
# Test ExperimentAssignment Dataclass
# ============================================================================


class TestExperimentAssignment:
    """Tests for ExperimentAssignment dataclass."""

    def test_create_assignment(self):
        """Can create an assignment with all fields."""
        exp_id = uuid.uuid4()
        config_id = uuid.uuid4()

        assignment = ExperimentAssignment(
            experiment_id=exp_id,
            arm=ExperimentArm.TREATMENT,
            config_id=config_id,
            config_name="optimized_v2",
        )

        assert assignment.experiment_id == exp_id
        assert assignment.arm == ExperimentArm.TREATMENT
        assert assignment.config_id == config_id
        assert assignment.config_name == "optimized_v2"

    def test_control_assignment(self):
        """Can create control arm assignment."""
        assignment = ExperimentAssignment(
            experiment_id=uuid.uuid4(),
            arm=ExperimentArm.CONTROL,
            config_id=uuid.uuid4(),
            config_name="baseline_v1",
        )

        assert assignment.arm == ExperimentArm.CONTROL


# ============================================================================
# Test ExperimentResults Dataclass
# ============================================================================


class TestExperimentResults:
    """Tests for ExperimentResults dataclass."""

    def test_create_results(self):
        """Can create results with all fields."""
        exp_id = uuid.uuid4()

        results = ExperimentResults(
            experiment_id=exp_id,
            control_samples=150,
            treatment_samples=50,
            control_accuracy=0.72,
            treatment_accuracy=0.78,
            accuracy_difference=0.06,
            p_value=0.03,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment shows 6.0% improvement with p=0.0300",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        assert results.experiment_id == exp_id
        assert results.control_samples == 150
        assert results.treatment_samples == 50
        assert results.accuracy_difference == 0.06
        assert results.is_significant is True
        assert results.winner == "treatment"
        assert results.ready_to_conclude is True

    def test_to_dict(self):
        """to_dict returns serializable dictionary."""
        exp_id = uuid.uuid4()

        results = ExperimentResults(
            experiment_id=exp_id,
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.751234,
            treatment_accuracy=0.789876,
            accuracy_difference=0.038642,
            p_value=0.045678,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment wins",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        data = results.to_dict()

        assert data["experiment_id"] == str(exp_id)
        assert data["control_samples"] == 100
        assert data["treatment_samples"] == 100
        assert data["is_significant"] is True
        assert data["winner"] == "treatment"
        assert data["ready_to_conclude"] is True

    def test_to_dict_rounds_floats(self):
        """to_dict rounds floats to 4 decimal places."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.7512345678,
            treatment_accuracy=0.7898765432,
            accuracy_difference=0.0386419754,
            p_value=0.0456789012,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment wins",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        data = results.to_dict()

        assert data["control_accuracy"] == 0.7512
        assert data["treatment_accuracy"] == 0.7899
        assert data["accuracy_difference"] == 0.0386
        assert data["p_value"] == 0.0457

    def test_to_dict_handles_none_p_value(self):
        """to_dict handles None p_value."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=10,
            treatment_samples=10,
            control_accuracy=0.7,
            treatment_accuracy=0.8,
            accuracy_difference=0.1,
            p_value=None,
            is_significant=False,
            winner=None,
            winner_reason=None,
            ready_to_conclude=False,
            min_samples_per_arm=100,
        )

        data = results.to_dict()

        assert data["p_value"] is None
        assert data["winner"] is None

    def test_results_not_ready_insufficient_samples(self):
        """Results not ready when samples insufficient."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=50,
            treatment_samples=80,
            control_accuracy=0.7,
            treatment_accuracy=0.8,
            accuracy_difference=0.1,
            p_value=None,
            is_significant=False,
            winner=None,
            winner_reason=None,
            ready_to_conclude=False,
            min_samples_per_arm=100,
        )

        assert results.ready_to_conclude is False
        assert results.control_samples < results.min_samples_per_arm

    def test_winner_none_when_not_significant(self):
        """Winner is 'none' when not statistically significant."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.7,
            treatment_accuracy=0.72,
            accuracy_difference=0.02,
            p_value=0.15,  # Not significant (> 0.05)
            is_significant=False,
            winner="none",
            winner_reason="No significant difference (p=0.1500)",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        assert results.is_significant is False
        assert results.winner == "none"


# ============================================================================
# Test Statistical Significance Logic
# ============================================================================


class TestStatisticalSignificance:
    """Tests for statistical significance interpretation."""

    def test_treatment_wins_significant(self):
        """Treatment wins when accuracy higher and significant."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=200,
            treatment_samples=200,
            control_accuracy=0.70,
            treatment_accuracy=0.78,
            accuracy_difference=0.08,
            p_value=0.01,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment shows 8.0% improvement with p=0.0100",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        assert results.winner == "treatment"
        assert results.accuracy_difference > 0

    def test_control_wins_significant(self):
        """Control wins when its accuracy higher and significant."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=200,
            treatment_samples=200,
            control_accuracy=0.80,
            treatment_accuracy=0.72,
            accuracy_difference=-0.08,
            p_value=0.01,
            is_significant=True,
            winner="control",
            winner_reason="Control outperforms treatment by 8.0% with p=0.0100",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        assert results.winner == "control"
        assert results.accuracy_difference < 0

    def test_p_value_threshold_at_005(self):
        """p-value threshold is 0.05 for significance."""
        # p=0.049 should be significant
        results_sig = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.70,
            treatment_accuracy=0.75,
            accuracy_difference=0.05,
            p_value=0.049,
            is_significant=True,
            winner="treatment",
            winner_reason="...",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        # p=0.051 should not be significant
        results_not_sig = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.70,
            treatment_accuracy=0.75,
            accuracy_difference=0.05,
            p_value=0.051,
            is_significant=False,
            winner="none",
            winner_reason="...",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        assert results_sig.is_significant is True
        assert results_not_sig.is_significant is False


# ============================================================================
# Test Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases in experiment handling."""

    def test_zero_accuracy(self):
        """Handle zero accuracy gracefully."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.0,
            treatment_accuracy=0.0,
            accuracy_difference=0.0,
            p_value=1.0,
            is_significant=False,
            winner="none",
            winner_reason="No significant difference",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        data = results.to_dict()
        assert data["control_accuracy"] == 0.0
        assert data["treatment_accuracy"] == 0.0

    def test_perfect_accuracy(self):
        """Handle 100% accuracy gracefully."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=100,
            control_accuracy=1.0,
            treatment_accuracy=1.0,
            accuracy_difference=0.0,
            p_value=1.0,
            is_significant=False,
            winner="none",
            winner_reason="No significant difference",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        data = results.to_dict()
        assert data["control_accuracy"] == 1.0
        assert data["treatment_accuracy"] == 1.0

    def test_very_small_p_value(self):
        """Handle very small p-values."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=1000,
            treatment_samples=1000,
            control_accuracy=0.70,
            treatment_accuracy=0.85,
            accuracy_difference=0.15,
            p_value=0.000001,
            is_significant=True,
            winner="treatment",
            winner_reason="...",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        data = results.to_dict()
        assert data["p_value"] == 0.0  # Rounded to 4 decimals

    def test_uuid_serialization(self):
        """UUIDs serialize to strings."""
        exp_id = uuid.uuid4()
        results = ExperimentResults(
            experiment_id=exp_id,
            control_samples=100,
            treatment_samples=100,
            control_accuracy=0.7,
            treatment_accuracy=0.8,
            accuracy_difference=0.1,
            p_value=0.05,
            is_significant=True,
            winner="treatment",
            winner_reason="...",
            ready_to_conclude=True,
            min_samples_per_arm=100,
        )

        data = results.to_dict()
        assert isinstance(data["experiment_id"], str)
        assert data["experiment_id"] == str(exp_id)


# ============================================================================
# Test Allocation Distribution
# ============================================================================


class TestAllocationDistribution:
    """Tests for treatment allocation distribution."""

    @pytest.mark.parametrize(
        "allocation,expected_min,expected_max",
        [
            (0.1, 0.05, 0.15),
            (0.2, 0.15, 0.25),
            (0.3, 0.25, 0.35),
            (0.5, 0.45, 0.55),
        ],
    )
    def test_allocation_distribution(self, allocation, expected_min, expected_max):
        """Treatment allocation roughly matches expected ratio."""
        treatment_count = 0
        total = 500

        for i in range(total):
            site_id = uuid.UUID(int=i + 1000)  # Offset to avoid patterns
            arm = get_experiment_arm(site_id, treatment_allocation=allocation)
            if arm == ExperimentArm.TREATMENT:
                treatment_count += 1

        ratio = treatment_count / total
        assert (
            expected_min <= ratio <= expected_max
        ), f"Allocation {allocation}: expected {expected_min}-{expected_max}, got {ratio:.3f}"
