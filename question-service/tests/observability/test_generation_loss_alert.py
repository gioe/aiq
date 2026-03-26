"""Tests for generation-loss warning fields in to_run_summary().

Since TASK-140, the separate 'Generation Loss Alert' send_notification call has
been removed. Loss information is now surfaced as extra fields in the RunSummary
details when generation_loss_pct exceeds the configured threshold.
"""

import pytest

from app.observability.alerting_adapter import to_run_summary


def _make_stats(generation_loss_pct: float) -> dict:  # type: ignore[type-arg]
    requested = 100
    generated = int(requested * (1 - generation_loss_pct / 100))
    loss = requested - generated
    return {
        "questions_requested": requested,
        "questions_generated": generated,
        "generation_loss": loss,
        "generation_loss_pct": generation_loss_pct,
        "questions_inserted": generated,
        "questions_rejected": 0,
        "duration_seconds": 1.0,
    }


class TestGenerationLossWarningInSummary:
    """to_run_summary injects warning fields into details when loss > threshold."""

    def test_warning_fields_present_when_loss_exceeds_threshold(self) -> None:
        stats = _make_stats(30.0)
        summary = to_run_summary(stats, loss_threshold=20.0)
        details = summary["details"]
        assert details["generation_loss_warning"] == "30 (30.0%)"
        assert details["generation_loss_threshold"] == "20.0%"

    def test_warning_fields_absent_when_loss_equals_threshold(self) -> None:
        stats = _make_stats(20.0)
        summary = to_run_summary(stats, loss_threshold=20.0)
        details = summary["details"]
        assert "generation_loss_warning" not in details
        assert "generation_loss_threshold" not in details

    def test_warning_fields_absent_when_loss_below_threshold(self) -> None:
        stats = _make_stats(10.0)
        summary = to_run_summary(stats, loss_threshold=20.0)
        details = summary["details"]
        assert "generation_loss_warning" not in details
        assert "generation_loss_threshold" not in details

    def test_warning_fields_absent_when_no_threshold_provided(self) -> None:
        """Covers dry-run mode where loss_threshold=None is passed."""
        stats = _make_stats(50.0)
        summary = to_run_summary(stats)
        details = summary["details"]
        assert "generation_loss_warning" not in details
        assert "generation_loss_threshold" not in details

    def test_warning_fields_absent_when_threshold_is_none(self) -> None:
        stats = _make_stats(100.0)
        summary = to_run_summary(stats, loss_threshold=None)
        details = summary["details"]
        assert "generation_loss_warning" not in details

    @pytest.mark.parametrize(
        "loss_pct,threshold,expected_warning",
        [
            (25.0, 20.0, "25 (25.0%)"),
            (100.0, 20.0, "100 (100.0%)"),
        ],
    )
    def test_warning_format(
        self, loss_pct: float, threshold: float, expected_warning: str
    ) -> None:
        stats = _make_stats(loss_pct)
        summary = to_run_summary(stats, loss_threshold=threshold)
        assert summary["details"]["generation_loss_warning"] == expected_warning
        assert summary["details"]["generation_loss_threshold"] == f"{threshold}%"
