"""
Railway cron job: Weekly IRT recalibration.

Runs at 4:00 AM UTC on Sundays (after question generation at 2:00 AM
and CAT readiness at 3:30 AM). Recalibrates IRT parameters for all
eligible questions if new response data has accumulated since the last
successful calibration.

Exit codes:
    0 - Success (calibration ran or was skipped due to no new responses)
    1 - Database error
    2 - Calibration error
    3 - Configuration/import error
"""

import json
import logging
import secrets
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("irt_calibration_cron")

# Minimum new responses since last calibration to justify re-running.
# Prevents wasted computation when the item pool hasn't changed meaningfully.
MIN_NEW_RESPONSES = 100


def _count_new_responses(db, last_successful_at):
    """Count responses from completed fixed-form tests since last calibration.

    Args:
        db: Database session.
        last_successful_at: Timestamp of last successful calibration, or None
            if no prior calibration exists.

    Returns:
        Number of new responses since last_successful_at.
    """
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
    """Get the most recent successful calibration run.

    Returns:
        CalibrationRun instance or None if no successful run exists.
    """
    from app.models.models import CalibrationRun, CalibrationRunStatus

    return (
        db.query(CalibrationRun)
        .filter(CalibrationRun.status == CalibrationRunStatus.COMPLETED)
        .order_by(CalibrationRun.started_at.desc())
        .first()
    )


def _record_calibration_run(db, **kwargs):
    """Insert a calibration run record into the audit table.

    Args:
        db: Database session.
        **kwargs: Fields for the CalibrationRun model.
    """
    from app.models.models import CalibrationRun

    run = CalibrationRun(**kwargs)
    db.add(run)
    db.commit()
    return run


def _safe_record_calibration_run(db, **kwargs):
    """Record a calibration run, logging and suppressing any errors.

    Audit trail writes should not change the exit code or mask the actual
    outcome. If the record fails to write, log the error but continue.
    """
    try:
        return _record_calibration_run(db, **kwargs)
    except Exception as record_err:
        logger.error("Failed to record calibration run in audit trail: %s", record_err)
        _capture_sentry(record_err)
        return None


def _capture_sentry(error):
    """Capture an exception to Sentry if configured."""
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(error)
    except Exception:
        pass  # Sentry not configured or import failed


def main() -> int:
    # Defer imports so config/import failures produce exit code 3
    try:
        from app.core.cat.calibration import CalibrationError, run_calibration_job
        from app.core.datetime_utils import utc_now
        from app.models.base import SessionLocal
        from app.models.models import CalibrationRunStatus, CalibrationTrigger

        # Initialize Sentry if configured
        try:
            from app.core.config import settings

            if settings.SENTRY_DSN:
                import sentry_sdk

                sentry_sdk.init(
                    dsn=settings.SENTRY_DSN,
                    environment=settings.ENV,
                    release=settings.APP_VERSION,
                    send_default_pii=False,
                )
        except Exception as exc:
            logger.warning("Sentry initialization failed (non-fatal): %s", exc)
    except Exception as exc:
        logger.error("Failed to import required modules: %s", exc)
        return 3

    # Open a database session
    try:
        db = SessionLocal()
    except Exception as exc:
        logger.error("Failed to create database session: %s", exc)
        _capture_sentry(exc)
        return 1

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
                "Skipping calibration: only %d new responses "
                "(< %d minimum threshold)",
                new_response_count,
                MIN_NEW_RESPONSES,
            )
            # Record the skip in the audit trail
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

            # Emit heartbeat
            heartbeat = {
                "type": "HEARTBEAT",
                "service": "irt_calibration_cron",
                "status": "skipped",
                "new_responses": new_response_count,
                "reason": "insufficient_new_responses",
                "evaluated_at": started_at.isoformat(),
            }
            print(json.dumps(heartbeat), flush=True)
            return 0

        # Run calibration
        logger.info("Running IRT calibration (job_id=%s)...", job_id)
        try:
            summary = run_calibration_job(db=db)
        except CalibrationError as exc:
            completed_at = utc_now()
            logger.error("Calibration failed: %s", exc)
            _capture_sentry(exc)
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
            return 2

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

        # Emit heartbeat JSON for Railway log monitoring
        heartbeat = {
            "type": "HEARTBEAT",
            "service": "irt_calibration_cron",
            "status": "completed",
            "job_id": job_id,
            "calibrated": summary["calibrated"],
            "skipped": summary["skipped"],
            "mean_difficulty": round(summary["mean_difficulty"], 3),
            "mean_discrimination": round(summary["mean_discrimination"], 3),
            "new_responses": new_response_count,
            "duration_seconds": round(duration, 1),
            "completed_at": completed_at.isoformat(),
        }
        print(json.dumps(heartbeat), flush=True)

        return 0

    except Exception as exc:
        logger.error("Unexpected error during IRT calibration cron: %s", exc)
        _capture_sentry(exc)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
