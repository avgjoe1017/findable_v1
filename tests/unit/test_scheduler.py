"""Tests for the monitoring scheduler."""

from datetime import UTC, datetime, timedelta

import pytest

from worker.scheduler import (
    DEFAULT_DAY_OF_WEEK,
    DEFAULT_HOUR,
    ScheduleFrequency,
    calculate_next_run,
    get_frequency_for_plan,
)


class TestScheduleFrequency:
    """Tests for ScheduleFrequency enum."""

    def test_weekly_value(self) -> None:
        """Test weekly frequency value."""
        assert ScheduleFrequency.WEEKLY.value == "weekly"

    def test_monthly_value(self) -> None:
        """Test monthly frequency value."""
        assert ScheduleFrequency.MONTHLY.value == "monthly"


class TestGetFrequencyForPlan:
    """Tests for get_frequency_for_plan function."""

    def test_starter_plan_monthly(self) -> None:
        """Starter plan should get monthly frequency."""
        freq = get_frequency_for_plan("starter")
        assert freq == ScheduleFrequency.MONTHLY

    def test_professional_plan_weekly(self) -> None:
        """Professional plan should get weekly frequency."""
        freq = get_frequency_for_plan("professional")
        assert freq == ScheduleFrequency.WEEKLY

    def test_agency_plan_weekly(self) -> None:
        """Agency plan should get weekly frequency."""
        freq = get_frequency_for_plan("agency")
        assert freq == ScheduleFrequency.WEEKLY

    def test_unknown_plan_defaults_monthly(self) -> None:
        """Unknown plan should default to monthly."""
        freq = get_frequency_for_plan("unknown")
        assert freq == ScheduleFrequency.MONTHLY


class TestCalculateNextRunWeekly:
    """Tests for calculate_next_run with weekly frequency."""

    def test_next_monday_from_sunday(self) -> None:
        """Next Monday from a Sunday."""
        # Sunday at 10:00
        from_time = datetime(2024, 1, 7, 10, 0, 0, tzinfo=UTC)  # Sunday
        next_run = calculate_next_run(
            ScheduleFrequency.WEEKLY,
            day_of_week=0,  # Monday
            hour=6,
            from_time=from_time,
        )

        assert next_run.weekday() == 0  # Monday
        assert next_run.hour == 6
        assert next_run.minute == 0
        assert next_run > from_time

    def test_next_monday_from_monday_before_hour(self) -> None:
        """Next Monday from Monday before the scheduled hour."""
        # Monday at 4:00 (before 6:00)
        from_time = datetime(2024, 1, 8, 4, 0, 0, tzinfo=UTC)  # Monday
        next_run = calculate_next_run(
            ScheduleFrequency.WEEKLY,
            day_of_week=0,
            hour=6,
            from_time=from_time,
        )

        # Should be same day at 6:00
        assert next_run.date() == from_time.date()
        assert next_run.hour == 6

    def test_next_monday_from_monday_after_hour(self) -> None:
        """Next Monday from Monday after the scheduled hour."""
        # Monday at 10:00 (after 6:00)
        from_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=UTC)  # Monday
        next_run = calculate_next_run(
            ScheduleFrequency.WEEKLY,
            day_of_week=0,
            hour=6,
            from_time=from_time,
        )

        # Should be next Monday at 6:00 (6 days and 20 hours later)
        assert next_run.weekday() == 0
        assert next_run.hour == 6
        assert next_run > from_time
        # January 8 to January 15 is 7 days apart calendar-wise
        assert next_run.day == from_time.day + 7

    def test_friday_schedule(self) -> None:
        """Test scheduling for Friday."""
        # Monday at 10:00
        from_time = datetime(2024, 1, 8, 10, 0, 0, tzinfo=UTC)  # Monday
        next_run = calculate_next_run(
            ScheduleFrequency.WEEKLY,
            day_of_week=4,  # Friday
            hour=14,  # 2 PM
            from_time=from_time,
        )

        assert next_run.weekday() == 4  # Friday
        assert next_run.hour == 14
        # Monday to Friday is 4 days
        assert (next_run.date() - from_time.date()).days == 4


class TestCalculateNextRunMonthly:
    """Tests for calculate_next_run with monthly frequency."""

    def test_first_monday_of_next_month(self) -> None:
        """First Monday of next month."""
        # January 15th
        from_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        next_run = calculate_next_run(
            ScheduleFrequency.MONTHLY,
            day_of_week=0,  # Monday
            hour=6,
            from_time=from_time,
        )

        # February 2024 starts on Thursday, first Monday is Feb 5th
        assert next_run.month == 2
        assert next_run.year == 2024
        assert next_run.weekday() == 0
        assert next_run.hour == 6

    def test_december_to_january(self) -> None:
        """Monthly schedule crossing year boundary."""
        # December 15th
        from_time = datetime(2024, 12, 15, 10, 0, 0, tzinfo=UTC)
        next_run = calculate_next_run(
            ScheduleFrequency.MONTHLY,
            day_of_week=0,  # Monday
            hour=6,
            from_time=from_time,
        )

        # January 2025 starts on Wednesday, first Monday is Jan 6th
        assert next_run.month == 1
        assert next_run.year == 2025
        assert next_run.weekday() == 0

    def test_first_friday_of_next_month(self) -> None:
        """First Friday of next month."""
        from_time = datetime(2024, 1, 15, 10, 0, 0, tzinfo=UTC)
        next_run = calculate_next_run(
            ScheduleFrequency.MONTHLY,
            day_of_week=4,  # Friday
            hour=9,
            from_time=from_time,
        )

        # February 2024 starts on Thursday, first Friday is Feb 2nd
        assert next_run.month == 2
        assert next_run.day == 2
        assert next_run.weekday() == 4
        assert next_run.hour == 9


class TestDefaultValues:
    """Tests for default schedule values."""

    def test_default_hour(self) -> None:
        """Default hour should be 6 AM UTC."""
        assert DEFAULT_HOUR == 6

    def test_default_day_of_week(self) -> None:
        """Default day should be Monday."""
        assert DEFAULT_DAY_OF_WEEK == 0

    def test_calculate_with_defaults(self) -> None:
        """Test calculate_next_run with default values."""
        next_run = calculate_next_run(ScheduleFrequency.WEEKLY)

        assert next_run.hour == DEFAULT_HOUR
        assert next_run.weekday() == DEFAULT_DAY_OF_WEEK
        assert next_run > datetime.now(UTC)
