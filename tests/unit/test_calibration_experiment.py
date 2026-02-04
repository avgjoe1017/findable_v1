"""Tests for calibration A/B experiment module."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from worker.calibration.experiment import (
    ExperimentArm,
    ExperimentAssignment,
    ExperimentResults,
    assign_to_experiment,
    conclude_experiment,
    get_active_experiment,
    get_experiment_arm,
    start_experiment,
)


class TestExperimentArm:
    """Tests for ExperimentArm enum."""

    def test_arm_values(self):
        """ExperimentArm has correct values."""
        assert ExperimentArm.CONTROL.value == "control"
        assert ExperimentArm.TREATMENT.value == "treatment"


class TestExperimentResults:
    """Tests for ExperimentResults dataclass."""

    def test_to_dict(self):
        """ExperimentResults serializes correctly."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=100,
            treatment_samples=95,
            control_accuracy=0.75,
            treatment_accuracy=0.82,
            accuracy_difference=0.07,
            p_value=0.03,
            is_significant=True,
            winner="treatment",
            winner_reason="Treatment shows 7% improvement",
            ready_to_conclude=True,
            min_samples_per_arm=50,
        )

        data = results.to_dict()

        assert data["control_samples"] == 100
        assert data["treatment_samples"] == 95
        assert data["control_accuracy"] == 0.75
        assert data["treatment_accuracy"] == 0.82
        assert data["accuracy_difference"] == 0.07
        assert data["p_value"] == 0.03
        assert data["is_significant"] is True
        assert data["winner"] == "treatment"
        assert data["ready_to_conclude"] is True

    def test_to_dict_with_none_p_value(self):
        """ExperimentResults handles None p_value."""
        results = ExperimentResults(
            experiment_id=uuid.uuid4(),
            control_samples=10,
            treatment_samples=10,
            control_accuracy=0.5,
            treatment_accuracy=0.5,
            accuracy_difference=0.0,
            p_value=None,
            is_significant=False,
            winner=None,
            winner_reason=None,
            ready_to_conclude=False,
            min_samples_per_arm=100,
        )

        data = results.to_dict()
        assert data["p_value"] is None


class TestGetExperimentArm:
    """Tests for get_experiment_arm function."""

    def test_deterministic_assignment(self):
        """Same site always gets same arm."""
        site_id = uuid.uuid4()

        # Call multiple times
        results = [get_experiment_arm(site_id, 0.1) for _ in range(10)]

        # All should be the same
        assert len(set(results)) == 1

    def test_different_sites_can_get_different_arms(self):
        """Different sites can be assigned to different arms."""
        # Generate many site IDs and check distribution
        arms = []
        for i in range(1000):
            site_id = uuid.UUID(int=i)
            arm = get_experiment_arm(site_id, 0.5)  # 50% allocation
            arms.append(arm)

        control_count = arms.count(ExperimentArm.CONTROL)
        treatment_count = arms.count(ExperimentArm.TREATMENT)

        # Should be roughly 50/50 (allow for some variance)
        assert 400 < control_count < 600
        assert 400 < treatment_count < 600

    def test_allocation_affects_distribution(self):
        """Treatment allocation affects arm distribution."""
        # With 10% allocation
        arms_10 = []
        for i in range(1000):
            site_id = uuid.UUID(int=i)
            arm = get_experiment_arm(site_id, 0.1)
            arms_10.append(arm)

        treatment_10 = arms_10.count(ExperimentArm.TREATMENT)

        # With 50% allocation
        arms_50 = []
        for i in range(1000):
            site_id = uuid.UUID(int=i)
            arm = get_experiment_arm(site_id, 0.5)
            arms_50.append(arm)

        treatment_50 = arms_50.count(ExperimentArm.TREATMENT)

        # 50% allocation should have more treatment
        assert treatment_50 > treatment_10

    def test_zero_allocation_all_control(self):
        """0% allocation puts everyone in control."""
        arms = []
        for i in range(100):
            site_id = uuid.UUID(int=i)
            arm = get_experiment_arm(site_id, 0.0)
            arms.append(arm)

        assert all(arm == ExperimentArm.CONTROL for arm in arms)


class TestGetActiveExperimentAsync:
    """Tests for async get_active_experiment function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_none_when_no_experiment(self, mock_session_maker):
        """Returns None when no running experiment."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await get_active_experiment()

        assert result is None

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_experiment_when_running(self, mock_session_maker):
        """Returns experiment when one is running."""
        mock_experiment = MagicMock()
        mock_experiment.id = uuid.uuid4()
        mock_experiment.status = "running"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_experiment
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await get_active_experiment()

        assert result == mock_experiment


class TestAssignToExperimentAsync:
    """Tests for async assign_to_experiment function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_none_when_no_experiment(self, mock_session_maker):
        """Returns None when no running experiment."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await assign_to_experiment(uuid.uuid4())

        assert result is None


class TestStartExperimentAsync:
    """Tests for async start_experiment function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_error_when_not_found(self, mock_session_maker):
        """Returns error when experiment not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await start_experiment(uuid.uuid4())

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_error_when_not_draft(self, mock_session_maker):
        """Returns error when experiment is not in draft status."""
        mock_experiment = MagicMock()
        mock_experiment.status = "running"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_experiment
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await start_experiment(uuid.uuid4())

        assert "error" in result
        assert "not in draft" in result["error"]


class TestConcludeExperimentAsync:
    """Tests for async conclude_experiment function."""

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_error_when_not_found(self, mock_session_maker):
        """Returns error when experiment not found."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await conclude_experiment(uuid.uuid4())

        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    @patch("worker.calibration.experiment.async_session_maker")
    async def test_returns_error_when_not_running(self, mock_session_maker):
        """Returns error when experiment is not running."""
        mock_experiment = MagicMock()
        mock_experiment.status = "draft"

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_experiment
        mock_db.execute = AsyncMock(return_value=mock_result)
        mock_db.__aenter__ = AsyncMock(return_value=mock_db)
        mock_db.__aexit__ = AsyncMock(return_value=None)
        mock_session_maker.return_value = mock_db

        result = await conclude_experiment(uuid.uuid4())

        assert "error" in result
        assert "not running" in result["error"]


class TestExperimentAssignment:
    """Tests for ExperimentAssignment dataclass."""

    def test_assignment_fields(self):
        """ExperimentAssignment has all required fields."""
        assignment = ExperimentAssignment(
            experiment_id=uuid.uuid4(),
            arm=ExperimentArm.TREATMENT,
            config_id=uuid.uuid4(),
            config_name="test-config",
        )

        assert assignment.arm == ExperimentArm.TREATMENT
        assert assignment.config_name == "test-config"
