"""Adapter mapping question-service native stats to the generic RunSummary dict.

CronJob receives the RunSummary returned by work_fn and converts it to
(label, value) tuples via _run_summary_to_fields(), which are then passed to
alert_manager.send_notification().  Top-level scalar keys (generated, inserted,
errors, duration_seconds) become top-level fields; everything under 'details'
is flattened and appended.
"""

from typing import Any, Dict

from gioe_libs.alerting.alerting import RunSummary


def to_run_summary(stats: Dict[str, Any]) -> RunSummary:
    """Convert question-service native stats dict to a generic RunSummary.

    Args:
        stats: Dict as built in run_generation.py, typically containing keys:
            questions_generated, questions_inserted, approval_rate,
            duration_seconds, by_type, by_difficulty, questions_requested,
            questions_rejected, duplicates_found, error_message.

    Returns:
        A RunSummary dict with standard top-level keys and the original stats
        stored verbatim under 'details' for CronJob to flatten into notification
        fields.
    """
    return {
        "generated": stats.get("questions_generated", 0),
        "inserted": stats.get("questions_inserted", 0),
        "errors": stats.get("questions_rejected", 0),
        "duration_seconds": float(stats.get("duration_seconds") or 0.0),
        "details": stats,
    }
