"""
Railway cron job: Evaluate CAT readiness daily.

Runs at 3:30 AM UTC (90 minutes after question generation).
Evaluates whether the calibrated item pool supports Computerized Adaptive
Testing across all 6 cognitive domains, and persists the result to the
system_config table.
"""

import logging
import sys

from gioe_libs.alerting.alerting import AlertManager, RunSummary
from gioe_libs.cron_runner.cron_job import CronJob
from gioe_libs.observability import observability

from app.core.cat.readiness import (
    evaluate_cat_readiness,
    serialize_readiness_result,
)
from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.core.system_config import set_cat_readiness
from app.models.base import SessionLocal

logger = logging.getLogger("cat_readiness_cron")


def work_fn() -> RunSummary:
    """Evaluate CAT readiness and persist the result."""
    db = SessionLocal()
    try:
        result = evaluate_cat_readiness(db)

        now = utc_now()
        config_value = serialize_readiness_result(result, now)
        set_cat_readiness(db, config_value)

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

        return {
            "is_globally_ready": result.is_globally_ready,
            "summary": result.summary,
            "evaluated_at": now.isoformat(),
        }
    finally:
        db.close()


def main() -> int:
    observability.init(
        config_path="config/observability.yaml",
        service_name="cat-readiness-cron",
        environment=settings.ENV,
    )

    alert_manager = AlertManager(
        discord_webhook_url=settings.SLACK_ALERT_WEBHOOK or None,
        service_name="cat-readiness-cron",
    )

    job = CronJob(
        name="cat-readiness",
        schedule="30 3 * * *",
        work_fn=work_fn,
        observability=observability,
        alert_manager=alert_manager,
    )
    return job.run_once()


if __name__ == "__main__":
    sys.exit(main())
