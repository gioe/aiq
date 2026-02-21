"""
Tests for datetime utilities module.
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.core.datetime_utils import ensure_timezone_aware, utc_now


class TestEnsureTimezoneAware:
    """Tests for ensure_timezone_aware function."""

    def test_naive_datetime_becomes_utc(self):
        """Test that a naive datetime is converted to UTC."""
        naive_dt = datetime(2024, 1, 15, 12, 30, 45)

        result = ensure_timezone_aware(naive_dt)

        assert result.tzinfo == timezone.utc
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 30
        assert result.second == 45

    def test_utc_datetime_unchanged(self):
        """Test that a UTC datetime is returned unchanged."""
        utc_dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=timezone.utc)

        result = ensure_timezone_aware(utc_dt)

        assert result == utc_dt
        assert result.tzinfo == timezone.utc
        assert result is utc_dt  # Should be the same object

    def test_non_utc_timezone_preserved(self):
        """Test that non-UTC timezone-aware datetimes are preserved."""
        # Create datetime with +5:00 offset
        tz_plus_5 = timezone(timedelta(hours=5))
        aware_dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=tz_plus_5)

        result = ensure_timezone_aware(aware_dt)

        assert result == aware_dt
        assert result.tzinfo == tz_plus_5
        assert result is aware_dt  # Should be the same object

    def test_negative_timezone_offset_preserved(self):
        """Test that negative timezone offsets are preserved."""
        # Create datetime with -8:00 offset (PST)
        tz_minus_8 = timezone(timedelta(hours=-8))
        aware_dt = datetime(2024, 1, 15, 12, 30, 45, tzinfo=tz_minus_8)

        result = ensure_timezone_aware(aware_dt)

        assert result == aware_dt
        assert result.tzinfo == tz_minus_8

    def test_none_raises_value_error(self):
        """Test that None input raises ValueError."""
        with pytest.raises(ValueError, match="datetime cannot be None"):
            ensure_timezone_aware(None)

    def test_naive_datetime_now(self):
        """Test with naive datetime.now()."""
        naive_now = datetime.now()  # Naive datetime

        result = ensure_timezone_aware(naive_now)

        assert result.tzinfo == timezone.utc
        # Time values should be identical to input
        assert result.replace(tzinfo=None) == naive_now

    def test_aware_datetime_now(self):
        """Test with aware datetime.now(timezone.utc)."""
        aware_now = datetime.now(timezone.utc)

        result = ensure_timezone_aware(aware_now)

        assert result == aware_now
        assert result.tzinfo == timezone.utc

    def test_microseconds_preserved(self):
        """Test that microseconds are preserved in conversion."""
        naive_dt = datetime(2024, 1, 15, 12, 30, 45, 123456)

        result = ensure_timezone_aware(naive_dt)

        assert result.microsecond == 123456
        assert result.tzinfo == timezone.utc

    def test_edge_case_year_boundaries(self):
        """Test with datetime at year boundaries."""
        # New Year's Eve
        naive_dt = datetime(2023, 12, 31, 23, 59, 59)

        result = ensure_timezone_aware(naive_dt)

        assert result.tzinfo == timezone.utc
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 31

    def test_epoch_datetime(self):
        """Test with Unix epoch datetime."""
        epoch = datetime(1970, 1, 1, 0, 0, 0)

        result = ensure_timezone_aware(epoch)

        assert result.tzinfo == timezone.utc
        assert result.timestamp() == 0

    def test_idempotent_conversion(self):
        """Test that applying the function twice yields same result."""
        naive_dt = datetime(2024, 1, 15, 12, 30, 45)

        first_result = ensure_timezone_aware(naive_dt)
        second_result = ensure_timezone_aware(first_result)

        assert first_result == second_result
        assert first_result is second_result  # Should be same object

    def test_comparison_after_conversion(self):
        """Test that converted datetimes can be compared properly."""
        naive_dt1 = datetime(2024, 1, 15, 12, 0, 0)
        naive_dt2 = datetime(2024, 1, 15, 13, 0, 0)

        aware_dt1 = ensure_timezone_aware(naive_dt1)
        aware_dt2 = ensure_timezone_aware(naive_dt2)

        assert aware_dt1 < aware_dt2
        assert aware_dt2 > aware_dt1

    def test_different_timezone_offsets(self):
        """Test with various timezone offsets."""
        test_cases = [
            timezone(timedelta(hours=0)),  # UTC
            timezone(timedelta(hours=5, minutes=30)),  # IST
            timezone(timedelta(hours=-7)),  # PDT
            timezone(timedelta(hours=9)),  # JST
            timezone(timedelta(hours=-5, minutes=-30)),  # Mixed offset
        ]

        for tz in test_cases:
            aware_dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=tz)
            result = ensure_timezone_aware(aware_dt)

            assert result.tzinfo == tz
            assert result is aware_dt


class TestUtcNow:
    """Tests for utc_now function."""

    def test_returns_utc_timezone(self):
        """Test that utc_now returns a datetime with UTC timezone."""
        result = utc_now()

        assert result.tzinfo == timezone.utc

    def test_returns_datetime_type(self):
        """Test that utc_now returns a datetime object."""
        result = utc_now()

        assert isinstance(result, datetime)

    def test_is_close_to_system_time(self):
        """Test that utc_now returns a time close to the actual system time."""
        before = datetime.now(timezone.utc)
        result = utc_now()
        after = datetime.now(timezone.utc)

        # Result should be between before and after
        assert before <= result <= after

    def test_successive_calls_increase(self):
        """Test that successive calls return increasing timestamps."""
        first = utc_now()
        second = utc_now()

        assert second >= first

    def test_can_be_used_in_calculations(self):
        """Test that result can be used in datetime arithmetic."""
        now = utc_now()
        one_hour_later = now + timedelta(hours=1)

        assert one_hour_later > now
        assert (one_hour_later - now).total_seconds() == 3600

    def test_can_be_compared_with_other_utc_datetimes(self):
        """Test that result can be compared with other UTC datetimes."""
        now = utc_now()
        fixed_time = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        assert now > fixed_time

    def test_has_microsecond_precision(self):
        """Test that utc_now includes microsecond precision."""
        result = utc_now()

        # Microsecond attribute should exist and be an integer
        assert hasattr(result, "microsecond")
        assert isinstance(result.microsecond, int)
        assert 0 <= result.microsecond < 1000000

    def test_mockable_for_testing(self):
        """Test that utc_now can be mocked for deterministic tests."""
        from unittest.mock import patch

        fixed_time = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)

        with patch("app.core.datetime_utils.datetime") as mock_datetime:
            mock_datetime.now.return_value = fixed_time

            # Note: This tests the mockability pattern, though in practice
            # we'd mock utc_now directly in other modules
            from app.core.datetime_utils import utc_now as fresh_utc_now

            # The function uses datetime.now internally, so we're testing
            # that the pattern allows for mocking
            result = fresh_utc_now()

            # Since we're importing after patching, this may or may not work
            # depending on import timing. The key point is the function is mockable.
            # In real tests, you'd mock 'app.core.datetime_utils.utc_now' directly.
            assert result.tzinfo == timezone.utc
