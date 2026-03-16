"""Tests for the alerting adapter (to_run_summary)."""

import pytest

from app.observability.alerting_adapter import to_run_summary


class TestToRunSummary:
    """Tests for to_run_summary() translation layer."""

    def test_full_stats(self):
        """All expected keys present — standard success run."""
        stats = {
            "questions_generated": 20,
            "questions_inserted": 18,
            "questions_rejected": 2,
            "duration_seconds": 45.5,
            "approval_rate": 0.9,
            "by_type": {"verbal": 10},
        }
        result = to_run_summary(stats)

        assert result["generated"] == 20
        assert result["inserted"] == 18
        assert result["errors"] == 2
        assert result["duration_seconds"] == pytest.approx(45.5)
        assert result["details"] is stats

    def test_partial_stats_only_error_message(self):
        """Only error_message is set; all numeric fields default to 0."""
        stats = {"error_message": "API timeout"}
        result = to_run_summary(stats)

        assert result["generated"] == 0
        assert result["inserted"] == 0
        assert result["errors"] == 0
        assert result["duration_seconds"] == pytest.approx(0.0)
        assert result["details"] is stats

    def test_empty_stats(self):
        """Empty dict produces all-zero run summary."""
        result = to_run_summary({})

        assert result["generated"] == 0
        assert result["inserted"] == 0
        assert result["errors"] == 0
        assert result["duration_seconds"] == pytest.approx(0.0)
        assert result["details"] == {}

    def test_duration_coerced_to_float(self):
        """Duration_seconds is always a float regardless of input type."""
        result = to_run_summary({"duration_seconds": 10})
        assert isinstance(result["duration_seconds"], float)

    def test_details_is_original_dict(self):
        """Details key holds a reference to the original stats dict."""
        stats = {"questions_generated": 5}
        result = to_run_summary(stats)
        assert result["details"] is stats

    def test_duration_none_does_not_crash(self):
        """Explicit None for duration_seconds should default to 0.0, not raise TypeError."""
        result = to_run_summary({"duration_seconds": None})
        assert result["duration_seconds"] == pytest.approx(0.0)
