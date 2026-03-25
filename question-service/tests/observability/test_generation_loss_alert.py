"""Tests for generation loss alert logic in run_generation.py.

The alert block (run_generation.py ~L1958-1985) fires send_notification when
generation_loss_pct exceeds the configured threshold and dry_run is False.
These tests reproduce that logic inline, mirroring the pattern used by
TestDedupByTypeMetric in test_run_generation_otel.py.
"""

from unittest.mock import MagicMock


def _run_loss_alert_logic(
    *,
    dry_run: bool,
    generation_loss_pct: float,
    loss_threshold: float,
    alert_manager: MagicMock,
) -> None:
    """Reproduce the generation-loss alert block from run_generation.py L1958-1985."""
    _run_stats = {
        "questions_requested": 100,
        "questions_generated": int(100 * (1 - generation_loss_pct / 100)),
        "generation_loss": int(100 * generation_loss_pct / 100),
        "generation_loss_pct": generation_loss_pct,
    }
    if not dry_run and _run_stats["generation_loss_pct"] > loss_threshold:
        try:
            alert_manager.send_notification(
                title="Generation Loss Alert",
                fields=[
                    ("Requested", _run_stats["questions_requested"]),
                    ("Generated", _run_stats["questions_generated"]),
                    (
                        "Loss",
                        f"{_run_stats['generation_loss']} ({_run_stats['generation_loss_pct']}%)",
                    ),
                    ("Threshold", f"{loss_threshold}%"),
                ],
                severity="warning",
            )
        except Exception:
            pass


class TestGenerationLossAlert:
    """Verify send_notification is called/suppressed based on threshold and dry_run."""

    def test_alert_fires_when_loss_exceeds_threshold(self) -> None:
        alert_manager = MagicMock()
        _run_loss_alert_logic(
            dry_run=False,
            generation_loss_pct=30.0,
            loss_threshold=20.0,
            alert_manager=alert_manager,
        )
        alert_manager.send_notification.assert_called_once_with(
            title="Generation Loss Alert",
            fields=[
                ("Requested", 100),
                ("Generated", 70),
                ("Loss", "30 (30.0%)"),
                ("Threshold", "20.0%"),
            ],
            severity="warning",
        )

    def test_alert_suppressed_when_loss_equals_threshold(self) -> None:
        alert_manager = MagicMock()
        _run_loss_alert_logic(
            dry_run=False,
            generation_loss_pct=20.0,
            loss_threshold=20.0,
            alert_manager=alert_manager,
        )
        alert_manager.send_notification.assert_not_called()

    def test_alert_suppressed_when_loss_below_threshold(self) -> None:
        alert_manager = MagicMock()
        _run_loss_alert_logic(
            dry_run=False,
            generation_loss_pct=10.0,
            loss_threshold=20.0,
            alert_manager=alert_manager,
        )
        alert_manager.send_notification.assert_not_called()

    def test_alert_suppressed_in_dry_run_mode(self) -> None:
        alert_manager = MagicMock()
        _run_loss_alert_logic(
            dry_run=True,
            generation_loss_pct=50.0,
            loss_threshold=20.0,
            alert_manager=alert_manager,
        )
        alert_manager.send_notification.assert_not_called()

    def test_alert_suppressed_in_dry_run_even_at_100_pct_loss(self) -> None:
        alert_manager = MagicMock()
        _run_loss_alert_logic(
            dry_run=True,
            generation_loss_pct=100.0,
            loss_threshold=0.0,
            alert_manager=alert_manager,
        )
        alert_manager.send_notification.assert_not_called()
