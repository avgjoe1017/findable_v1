"""Tests for job queue functionality."""

from datetime import UTC, datetime

from worker.queue import JobInfo, JobStatus, QueuePriority


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_job_status_values(self) -> None:
        """Test all job status values exist."""
        assert JobStatus.QUEUED.value == "queued"
        assert JobStatus.STARTED.value == "started"
        assert JobStatus.FINISHED.value == "finished"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.CANCELED.value == "canceled"

    def test_job_status_from_string(self) -> None:
        """Test creating status from string."""
        status = JobStatus("queued")
        assert status == JobStatus.QUEUED


class TestQueuePriority:
    """Tests for QueuePriority enum."""

    def test_queue_priority_values(self) -> None:
        """Test all priority values exist."""
        assert QueuePriority.HIGH.value == "high"
        assert QueuePriority.DEFAULT.value == "default"
        assert QueuePriority.LOW.value == "low"


class TestJobInfo:
    """Tests for JobInfo dataclass."""

    def test_job_info_creation(self) -> None:
        """Test creating JobInfo."""
        now = datetime.now(UTC)
        info = JobInfo(
            id="test-123",
            status=JobStatus.QUEUED,
            created_at=now,
            started_at=None,
            ended_at=None,
            result=None,
            error=None,
            meta={"key": "value"},
        )

        assert info.id == "test-123"
        assert info.status == JobStatus.QUEUED
        assert info.created_at == now
        assert info.meta == {"key": "value"}

    def test_job_info_to_dict(self) -> None:
        """Test converting JobInfo to dict."""
        now = datetime.now(UTC)
        info = JobInfo(
            id="test-456",
            status=JobStatus.FINISHED,
            created_at=now,
            started_at=now,
            ended_at=now,
            result={"success": True},
            error=None,
            meta={},
        )

        result = info.to_dict()

        assert result["id"] == "test-456"
        assert result["status"] == "finished"
        assert result["result"] == {"success": True}
        assert result["error"] is None

    def test_job_info_failed_with_error(self) -> None:
        """Test JobInfo with failed status and error."""
        info = JobInfo(
            id="test-789",
            status=JobStatus.FAILED,
            created_at=datetime.now(UTC),
            started_at=datetime.now(UTC),
            ended_at=datetime.now(UTC),
            result=None,
            error="Connection timeout",
            meta={"run_id": "abc"},
        )

        result = info.to_dict()

        assert result["status"] == "failed"
        assert result["error"] == "Connection timeout"
        assert result["result"] is None


class TestQueueNames:
    """Tests for queue name constants."""

    def test_queue_names(self) -> None:
        """Test queue names are correctly defined."""
        from worker.redis import QUEUE_DEFAULT, QUEUE_HIGH, QUEUE_LOW

        assert QUEUE_HIGH == "findable-high"
        assert QUEUE_DEFAULT == "findable-default"
        assert QUEUE_LOW == "findable-low"


class TestJobResultTTL:
    """Tests for job result TTL constant."""

    def test_job_result_ttl(self) -> None:
        """Test job result TTL is 7 days."""
        from worker.redis import JOB_RESULT_TTL

        # 7 days in seconds
        expected = 60 * 60 * 24 * 7
        assert expected == JOB_RESULT_TTL
