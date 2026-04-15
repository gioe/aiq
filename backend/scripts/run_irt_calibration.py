"""
Railway cron job: Weekly IRT recalibration.

Runs at 4:00 AM UTC on Sundays (after question generation at 2:00 AM
and CAT readiness at 3:30 AM). Recalibrates IRT parameters for all
eligible questions if new response data has accumulated since the last
successful calibration.
"""

import logging
import secrets
import sys

from gioe_libs.alerting.alerting import AlertManager, RunSummary
from gioe_libs.cron_runner.cron_job import CronJob
from gioe_libs.observability import observability

from app.core.cat.calibration import CalibrationError, run_calibration_job
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.models.base import SessionLocal
from app.models.models import (
    CalibrationRun,
    CalibrationRunStatus,
    CalibrationTrigger,
)

logger = logging.getLogger("irt_calibration_cron")

# Minimum new responses since last calibration to justify re-running.
MIN_NEW_RESPONSES = 100


def _count_new_responses(db, last_successful_at):
    """Count responses from completed fixed-form tests since last calibration."""
    from sqlalchemy import func

    from app.models.models import Response, TestSession, TestStatus

    query = (
        db.query(func.count(Response.id))
        .join(TestSession, Response.test_session_id == TestSession.id)
        .filter(
            TestSession.status == TestStatus.COMPLETED,
            TestSession.is_adaptive == False,  # noqa: E712
        )
    )
    if last_successful_at is not None:
        query = query.filter(Response.answered_at >= last_successful_at)
    return query.scalar() or 0


def _get_last_successful_calibration(db):
    """Get the most recent successful calibration run."""
    return (
        db.query(CalibrationRun)
        .filter(CalibrationRun.status == CalibrationRunStatus.COMPLETED)
        .order_by(CalibrationRun.started_at.desc())
        .first()
    )


def _safe_record_calibration_run(db, **kwargs):
    """Record a calibration run, logging and suppressing any errors."""
    try:
        run = CalibrationRun(**kwargs)
        db.add(run)
        db.commit()
        return run
    except Exception as record_err:
        logger.error("Failed to record calibration run in audit trail: %s", record_err)
        return None


def work_fn() -> RunSummary:
    """Run IRT calibration if enough new responses have accumulated."""
    db = SessionLocal()
    try:
        started_at = utc_now()
        timestamp_str = started_at.strftime("%Y%m%d%H%M%S")
        job_id = f"irt_cron_{timestamp_str}_{secrets.token_hex(4)}"

        # Check if new responses have accumulated since last calibration
        last_run = _get_last_successful_calibration(db)
        last_calibrated_at = last_run.completed_at if last_run else None
        new_response_count = _count_new_responses(db, last_calibrated_at)

        logger.info(
            "New responses since last calibration: %d (threshold: %d, last: %s)",
            new_response_count,
            MIN_NEW_RESPONSES,
            last_calibrated_at.isoformat() if last_calibrated_at else "never",
        )

        if new_response_count < MIN_NEW_RESPONSES:
            logger.info(
                "Skipping calibration: only %d new responses (< %d minimum threshold)",
                new_response_count,
                MIN_NEW_RESPONSES,
            )
            completed_at = utc_now()
            _safe_record_calibration_run(
                db,
                job_id=job_id,
                status=CalibrationRunStatus.SKIPPED,
                triggered_by=CalibrationTrigger.CRON,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                new_responses_since_last=new_response_count,
            )
            return {
                "status": "skipped",
                "reason": "insufficient_new_responses",
                "new_responses": new_response_count,
                "threshold": MIN_NEW_RESPONSES,
            }

        # Run calibration
        logger.info("Running IRT calibration (job_id=%s)...", job_id)
        try:
            summary = run_calibration_job(db=db)
        except CalibrationError as exc:
            completed_at = utc_now()
            logger.error("Calibration failed: %s", exc)
            _safe_record_calibration_run(
                db,
                job_id=job_id,
                status=CalibrationRunStatus.FAILED,
                triggered_by=CalibrationTrigger.CRON,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=(completed_at - started_at).total_seconds(),
                new_responses_since_last=new_response_count,
                error_message=str(exc)[:2000],
            )
            raise

        # Record successful run
        completed_at = utc_now()
        duration = (completed_at - started_at).total_seconds()
        _safe_record_calibration_run(
            db,
            job_id=job_id,
            status=CalibrationRunStatus.COMPLETED,
            triggered_by=CalibrationTrigger.CRON,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration,
            questions_calibrated=summary["calibrated"],
            questions_skipped=summary["skipped"],
            mean_difficulty=summary["mean_difficulty"],
            mean_discrimination=summary["mean_discrimination"],
            new_responses_since_last=new_response_count,
        )

        logger.info(
            "Calibration complete: %d calibrated, %d skipped, "
            "mean_b=%.2f, mean_a=%.2f, duration=%.1fs",
            summary["calibrated"],
            summary["skipped"],
            summary["mean_difficulty"],
            summary["mean_discrimination"],
            duration,
        )

        return {
            "status": "completed",
            "job_id": job_id,
            "calibrated": summary["calibrated"],
            "skipped": summary["skipped"],
            "mean_difficulty": round(summary["mean_difficulty"], 3),
            "mean_discrimination": round(summary["mean_discrimination"], 3),
            "new_responses": new_response_count,
            "duration_seconds": round(duration, 1),
        }
    finally:
        db.close()


def main() -> int:
    observability.init(
        config_path="config/observability.yaml",
        service_name="irt-calibration-cron",
        environment=settings.ENV,
    )

    alert_manager = AlertManager(
        discord_webhook_url=settings.SLACK_ALERT_WEBHOOK or None,
        service_name="irt-calibration-cron",
    )

    job = CronJob(
        name="irt-calibration",
        schedule="0 4 * * 0",
        work_fn=work_fn,
        observability=observability,
        alert_manager=alert_manager,
    )
    return job.run_once()


if __name__ == "__main__":
    sys.exit(main())
