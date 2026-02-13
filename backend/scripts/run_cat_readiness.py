"""
Railway cron job: Evaluate CAT readiness daily.

Runs at 3:30 AM UTC (90 minutes after question generation).
Evaluates whether the calibrated item pool supports Computerized Adaptive
Testing across all 6 cognitive domains, and persists the result to the
system_config table.

Exit codes:
    0 - Success
    1 - Database error
    2 - Evaluation error
    3 - Configuration/import error
"""
import json
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("cat_readiness_cron")


def main() -> int:
    # Defer imports so config/import failures produce exit code 3
    try:
        from app.core.cat.readiness import (
            evaluate_cat_readiness,
            serialize_readiness_result,
        )
        from app.core.datetime_utils import utc_now
        from app.core.system_config import set_cat_readiness
        from app.models.base import SessionLocal
    except Exception as exc:
        logger.error("Failed to import required modules: %s", exc)
        return 3

    # Open a database session
    try:
        db = SessionLocal()
    except Exception as exc:
        logger.error("Failed to create database session: %s", exc)
        return 1

    try:
        # Run evaluation
        try:
            result = evaluate_cat_readiness(db)
        except Exception as exc:
            logger.error("CAT readiness evaluation failed: %s", exc)
            return 2

        # Persist result
        now = utc_now()
        config_value = serialize_readiness_result(result, now)
        set_cat_readiness(db, config_value)

        # Log per-domain breakdown
        for domain in result.domains:
            status = "READY" if domain.is_ready else "NOT READY"
            logger.info(
                "  %-10s %s  calibrated=%d  well_calibrated=%d  "
                "easy=%d  medium=%d  hard=%d",
                domain.domain,
                status,
                domain.total_calibrated,
                domain.well_calibrated,
                domain.easy_count,
                domain.medium_count,
                domain.hard_count,
            )

        logger.info(
            "CAT readiness: globally_ready=%s, %s",
            result.is_globally_ready,
            result.summary,
        )

        # Emit heartbeat JSON for Railway log monitoring
        heartbeat = {
            "type": "HEARTBEAT",
            "service": "cat_readiness_cron",
            "is_globally_ready": result.is_globally_ready,
            "summary": result.summary,
            "evaluated_at": now.isoformat(),
        }
        print(json.dumps(heartbeat), flush=True)

        return 0

    except Exception as exc:
        logger.error("Unexpected error during CAT readiness cron: %s", exc)
        return 2
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
