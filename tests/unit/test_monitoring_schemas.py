"""Tests for monitoring API schemas."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from api.schemas.monitoring import (
    MonitoringEnableRequest,
    MonitoringScheduleResponse,
    MonitoringStatusResponse,
    ScoreTrendPoint,
    ScoreTrendResponse,
    ScheduledJobResponse,
    SchedulerStatsResponse,
    SnapshotListResponse,
    SnapshotResponse,
)


class TestMonitoringEnableRequest:
    """Tests for MonitoringEnableRequest schema."""

    def test_default_values(self) -> None:
        """Test default values."""
        request = MonitoringEnableRequest()

        assert request.day_of_week == 0  # Monday
        assert request.hour == 6  # 6 AM UTC
        assert request.include_observation is True
        assert request.include_benchmark is True

    def test_custom_values(self) -> None:
        """Test with custom values."""
        request = MonitoringEnableRequest(
            day_of_week=4,  # Friday
            hour=14,  # 2 PM
            include_observation=False,
            include_benchmark=False,
        )

        assert request.day_of_week == 4
        assert request.hour == 14
        assert request.include_observation is False
        assert request.include_benchmark is False

    def test_day_of_week_validation_min(self) -> None:
        """Test day_of_week minimum validation."""
        with pytest.raises(ValidationError) as exc:
            MonitoringEnableRequest(day_of_week=-1)

        assert "greater than or equal to 0" in str(exc.value)

    def test_day_of_week_validation_max(self) -> None:
        """Test day_of_week maximum validation."""
        with pytest.raises(ValidationError) as exc:
            MonitoringEnableRequest(day_of_week=7)

        assert "less than or equal to 6" in str(exc.value)

    def test_hour_validation_min(self) -> None:
        """Test hour minimum validation."""
        with pytest.raises(ValidationError) as exc:
            MonitoringEnableRequest(hour=-1)

        assert "greater than or equal to 0" in str(exc.value)

    def test_hour_validation_max(self) -> None:
        """Test hour maximum validation."""
        with pytest.raises(ValidationError) as exc:
            MonitoringEnableRequest(hour=24)

        assert "less than or equal to 23" in str(exc.value)


class TestMonitoringScheduleResponse:
    """Tests for MonitoringScheduleResponse schema."""

    def test_full_response(self) -> None:
        """Test full schedule response."""
        now = datetime.now(UTC)
        schedule = MonitoringScheduleResponse(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            frequency="weekly",
            day_of_week=0,
            hour=6,
            include_observation=True,
            include_benchmark=True,
            next_run_at=now,
            last_run_at=None,
            last_run_status=None,
            created_at=now,
        )

        assert schedule.frequency == "weekly"
        assert schedule.day_of_week == 0
        assert schedule.hour == 6

    def test_with_last_run(self) -> None:
        """Test schedule with last run info."""
        now = datetime.now(UTC)
        schedule = MonitoringScheduleResponse(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            frequency="monthly",
            day_of_week=4,
            hour=14,
            include_observation=True,
            include_benchmark=False,
            next_run_at=now,
            last_run_at=now,
            last_run_status="complete",
            created_at=now,
        )

        assert schedule.last_run_status == "complete"
        assert schedule.frequency == "monthly"


class TestMonitoringStatusResponse:
    """Tests for MonitoringStatusResponse schema."""

    def test_disabled_status(self) -> None:
        """Test disabled monitoring status."""
        status = MonitoringStatusResponse(enabled=False)

        assert status.enabled is False
        assert status.frequency is None
        assert status.schedule is None

    def test_enabled_status(self) -> None:
        """Test enabled monitoring status."""
        now = datetime.now(UTC)
        schedule = MonitoringScheduleResponse(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            frequency="weekly",
            day_of_week=0,
            hour=6,
            include_observation=True,
            include_benchmark=True,
            next_run_at=now,
            last_run_at=None,
            last_run_status=None,
            created_at=now,
        )

        status = MonitoringStatusResponse(
            enabled=True,
            frequency="weekly",
            next_run_at=now,
            schedule=schedule,
        )

        assert status.enabled is True
        assert status.frequency == "weekly"
        assert status.schedule is not None


class TestSnapshotResponse:
    """Tests for SnapshotResponse schema."""

    def test_full_snapshot(self) -> None:
        """Test full snapshot response."""
        now = datetime.now(UTC)
        snapshot = SnapshotResponse(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            report_id=uuid.uuid4(),
            trigger="scheduled_weekly",
            score_conservative=65,
            score_typical=75,
            score_generous=85,
            mention_rate=0.45,
            score_delta=5,
            mention_rate_delta=0.05,
            category_scores={"identity": 78, "offerings": 72},
            benchmark_data={"win_rate": 0.65},
            changes={"score_improved": True},
            snapshot_at=now,
            created_at=now,
        )

        assert snapshot.score_typical == 75
        assert snapshot.score_delta == 5
        assert snapshot.trigger == "scheduled_weekly"

    def test_minimal_snapshot(self) -> None:
        """Test snapshot with minimal data."""
        now = datetime.now(UTC)
        snapshot = SnapshotResponse(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            run_id=None,
            report_id=None,
            trigger="manual",
            score_conservative=None,
            score_typical=None,
            score_generous=None,
            mention_rate=None,
            score_delta=None,
            mention_rate_delta=None,
            category_scores=None,
            benchmark_data=None,
            changes=None,
            snapshot_at=now,
            created_at=now,
        )

        assert snapshot.score_typical is None
        assert snapshot.trigger == "manual"


class TestSnapshotListResponse:
    """Tests for SnapshotListResponse schema."""

    def test_paginated_list(self) -> None:
        """Test paginated snapshot list."""
        now = datetime.now(UTC)
        snapshot = SnapshotResponse(
            id=uuid.uuid4(),
            site_id=uuid.uuid4(),
            run_id=None,
            report_id=None,
            trigger="manual",
            score_conservative=None,
            score_typical=75,
            score_generous=None,
            mention_rate=None,
            score_delta=None,
            mention_rate_delta=None,
            category_scores=None,
            benchmark_data=None,
            changes=None,
            snapshot_at=now,
            created_at=now,
        )

        response = SnapshotListResponse(
            items=[snapshot],
            total=10,
            limit=12,
            offset=0,
        )

        assert len(response.items) == 1
        assert response.total == 10
        assert response.limit == 12
        assert response.offset == 0


class TestScoreTrendPoint:
    """Tests for ScoreTrendPoint schema."""

    def test_trend_point(self) -> None:
        """Test score trend point."""
        now = datetime.now(UTC)
        point = ScoreTrendPoint(
            date=now,
            score_typical=75,
            score_delta=5,
            mention_rate=0.45,
        )

        assert point.score_typical == 75
        assert point.score_delta == 5

    def test_trend_point_null_values(self) -> None:
        """Test trend point with null values."""
        now = datetime.now(UTC)
        point = ScoreTrendPoint(
            date=now,
            score_typical=None,
            score_delta=None,
            mention_rate=None,
        )

        assert point.score_typical is None


class TestScoreTrendResponse:
    """Tests for ScoreTrendResponse schema."""

    def test_trend_response(self) -> None:
        """Test score trend response."""
        now = datetime.now(UTC)
        site_id = uuid.uuid4()

        response = ScoreTrendResponse(
            site_id=site_id,
            points=[
                ScoreTrendPoint(
                    date=now,
                    score_typical=70,
                    score_delta=None,
                    mention_rate=0.40,
                ),
                ScoreTrendPoint(
                    date=now,
                    score_typical=75,
                    score_delta=5,
                    mention_rate=0.45,
                ),
            ],
            period_start=now,
            period_end=now,
            overall_delta=5,
        )

        assert response.site_id == site_id
        assert len(response.points) == 2
        assert response.overall_delta == 5


class TestSchedulerStatsResponse:
    """Tests for SchedulerStatsResponse schema."""

    def test_stats_response(self) -> None:
        """Test scheduler stats response."""
        job = ScheduledJobResponse(
            job_id="snapshot_123",
            site_id="site-uuid",
            run_at="2024-01-15T06:00:00Z",
            scheduled_at="2024-01-08T10:00:00Z",
            frequency="weekly",
        )

        stats = SchedulerStatsResponse(
            jobs_count=1,
            jobs=[job],
        )

        assert stats.jobs_count == 1
        assert len(stats.jobs) == 1
        assert stats.jobs[0].job_id == "snapshot_123"
