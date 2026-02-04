"""Tests for calibration scheduling functionality."""

from unittest.mock import MagicMock, patch

from worker.scheduler import (
    DEFAULT_CALIBRATION_HOUR,
    CalibrationScheduler,
    ensure_calibration_schedules,
    run_calibration_drift_check_sync,
)


class TestRunCalibrationDriftCheckSync:
    """Tests for the sync drift check wrapper."""

    @patch("worker.scheduler.get_settings")
    def test_skips_when_disabled(self, mock_settings):
        """Drift check is skipped when disabled in settings."""
        mock_settings.return_value.calibration_drift_check_enabled = False

        result = run_calibration_drift_check_sync()

        assert result["status"] == "disabled"
        assert result["alerts_created"] == 0

    @patch("worker.scheduler.get_settings")
    @patch("worker.tasks.calibration.check_calibration_drift")
    @patch("asyncio.run")
    def test_runs_when_enabled(self, mock_asyncio_run, mock_check, mock_settings):
        """Drift check runs when enabled."""
        mock_settings.return_value.calibration_drift_check_enabled = True
        mock_settings.return_value.calibration_drift_threshold_accuracy = 0.10
        mock_settings.return_value.calibration_drift_threshold_bias = 0.20
        mock_settings.return_value.calibration_min_samples_for_analysis = 100

        # Mock no alerts
        mock_asyncio_run.return_value = []

        result = run_calibration_drift_check_sync()

        assert result["status"] == "completed"
        assert result["alerts_created"] == 0
        mock_asyncio_run.assert_called_once()

    @patch("worker.scheduler.get_settings")
    @patch("asyncio.run")
    def test_returns_alert_info_when_alerts_created(self, mock_asyncio_run, mock_settings):
        """Returns alert details when drift is detected."""
        mock_settings.return_value.calibration_drift_check_enabled = True
        mock_settings.return_value.calibration_drift_threshold_accuracy = 0.10
        mock_settings.return_value.calibration_drift_threshold_bias = 0.20
        mock_settings.return_value.calibration_min_samples_for_analysis = 100

        # Mock an accuracy alert
        mock_alert = MagicMock()
        mock_alert.drift_type = "accuracy"
        mock_asyncio_run.return_value = [mock_alert]

        result = run_calibration_drift_check_sync()

        assert result["status"] == "completed"
        assert result["alerts_created"] == 1
        assert result["alert_types"] == ["accuracy"]

    @patch("worker.scheduler.get_settings")
    @patch("asyncio.run")
    def test_handles_errors_gracefully(self, mock_asyncio_run, mock_settings):
        """Errors are caught and reported."""
        mock_settings.return_value.calibration_drift_check_enabled = True
        mock_settings.return_value.calibration_drift_threshold_accuracy = 0.10
        mock_settings.return_value.calibration_drift_threshold_bias = 0.20
        mock_settings.return_value.calibration_min_samples_for_analysis = 100

        mock_asyncio_run.side_effect = Exception("Database error")

        result = run_calibration_drift_check_sync()

        assert result["status"] == "error"
        assert "Database error" in result["error"]
        assert result["alerts_created"] == 0


class TestCalibrationScheduler:
    """Tests for CalibrationScheduler class."""

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_init_creates_scheduler(self, mock_settings, mock_get_scheduler):
        """CalibrationScheduler initializes properly."""
        mock_settings.return_value.calibration_drift_check_enabled = True
        mock_scheduler = MagicMock()
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()

        assert scheduler.scheduler == mock_scheduler

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_schedule_skips_when_disabled(self, mock_settings, mock_get_scheduler):
        """schedule_daily_drift_check returns None when disabled."""
        mock_settings.return_value.calibration_drift_check_enabled = False

        scheduler = CalibrationScheduler()
        result = scheduler.schedule_daily_drift_check()

        assert result is None

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_schedule_creates_job_when_enabled(self, mock_settings, mock_get_scheduler):
        """schedule_daily_drift_check creates job when enabled."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []  # No existing jobs
        mock_job = MagicMock()
        mock_job.id = "test_job_id"
        mock_scheduler.schedule.return_value = mock_job
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()
        result = scheduler.schedule_daily_drift_check(hour=4)

        assert result == mock_job
        mock_scheduler.schedule.assert_called_once()

        # Verify schedule args
        call_kwargs = mock_scheduler.schedule.call_args[1]
        assert call_kwargs["interval"] == 86400  # Daily
        assert call_kwargs["id"] == CalibrationScheduler.DRIFT_CHECK_JOB_ID

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_cancel_drift_check(self, mock_settings, mock_get_scheduler):
        """cancel_drift_check cancels existing job."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_job = MagicMock()
        mock_job.id = CalibrationScheduler.DRIFT_CHECK_JOB_ID

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()
        result = scheduler.cancel_drift_check()

        assert result is True
        mock_scheduler.cancel.assert_called_once_with(mock_job)

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_cancel_returns_false_when_not_found(self, mock_settings, mock_get_scheduler):
        """cancel_drift_check returns False when job not found."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []  # No jobs
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()
        result = scheduler.cancel_drift_check()

        assert result is False

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_get_drift_check_status(self, mock_settings, mock_get_scheduler):
        """get_drift_check_status returns job info."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_job = MagicMock()
        mock_job.id = CalibrationScheduler.DRIFT_CHECK_JOB_ID
        mock_job.meta = {
            "type": "calibration_drift_check",
            "scheduled_at": "2025-01-01T00:00:00",
            "interval": "daily",
        }

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = [mock_job]
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()
        status = scheduler.get_drift_check_status()

        assert status is not None
        assert status["job_id"] == CalibrationScheduler.DRIFT_CHECK_JOB_ID
        assert status["type"] == "calibration_drift_check"
        assert status["interval"] == "daily"

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_get_drift_check_status_returns_none_when_not_scheduled(
        self, mock_settings, mock_get_scheduler
    ):
        """get_drift_check_status returns None when not scheduled."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_scheduler = MagicMock()
        mock_scheduler.get_jobs.return_value = []
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()
        status = scheduler.get_drift_check_status()

        assert status is None

    @patch("worker.scheduler.get_scheduler")
    @patch("worker.scheduler.get_settings")
    def test_run_drift_check_now(self, mock_settings, mock_get_scheduler):
        """run_drift_check_now enqueues immediate job."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_job = MagicMock()
        mock_job.id = "manual_job_id"

        mock_scheduler = MagicMock()
        mock_scheduler.enqueue_at.return_value = mock_job
        mock_get_scheduler.return_value = mock_scheduler

        scheduler = CalibrationScheduler()
        result = scheduler.run_drift_check_now()

        assert result == mock_job
        mock_scheduler.enqueue_at.assert_called_once()


class TestEnsureCalibrationSchedules:
    """Tests for ensure_calibration_schedules function."""

    @patch("worker.scheduler.CalibrationScheduler")
    @patch("worker.scheduler.get_settings")
    def test_skips_when_disabled(self, mock_settings, mock_scheduler_class):
        """Does not schedule when drift check is disabled."""
        mock_settings.return_value.calibration_drift_check_enabled = False

        result = ensure_calibration_schedules()

        assert result["drift_check_enabled"] is False
        assert result["drift_check_scheduled"] is False

    @patch("worker.scheduler.CalibrationScheduler")
    @patch("worker.scheduler.get_settings")
    def test_uses_existing_schedule(self, mock_settings, mock_scheduler_class):
        """Uses existing schedule if already scheduled."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_scheduler = MagicMock()
        mock_scheduler.get_drift_check_status.return_value = {
            "job_id": "existing_job",
        }
        mock_scheduler_class.return_value = mock_scheduler

        result = ensure_calibration_schedules()

        assert result["drift_check_enabled"] is True
        assert result["drift_check_scheduled"] is True
        assert result["drift_check_job_id"] == "existing_job"
        mock_scheduler.schedule_daily_drift_check.assert_not_called()

    @patch("worker.scheduler.CalibrationScheduler")
    @patch("worker.scheduler.get_settings")
    def test_creates_schedule_when_not_exists(self, mock_settings, mock_scheduler_class):
        """Creates new schedule when not already scheduled."""
        mock_settings.return_value.calibration_drift_check_enabled = True

        mock_job = MagicMock()
        mock_job.id = "new_job_id"

        mock_scheduler = MagicMock()
        mock_scheduler.get_drift_check_status.return_value = None
        mock_scheduler.schedule_daily_drift_check.return_value = mock_job
        mock_scheduler_class.return_value = mock_scheduler

        result = ensure_calibration_schedules()

        assert result["drift_check_enabled"] is True
        assert result["drift_check_scheduled"] is True
        assert result["drift_check_job_id"] == "new_job_id"
        mock_scheduler.schedule_daily_drift_check.assert_called_once()


class TestDefaultCalibrationHour:
    """Tests for default configuration values."""

    def test_default_hour_is_off_peak(self):
        """Default calibration hour is during off-peak hours."""
        # 4 AM UTC is off-peak for most business hours
        assert DEFAULT_CALIBRATION_HOUR == 4
        assert 0 <= DEFAULT_CALIBRATION_HOUR <= 6  # Early morning
