"""
Railway cron job: Send test reminder and Day 30 notifications.

Runs daily at 9 AM UTC.  Creates an async DB session, instantiates
NotificationScheduler, and calls both send_notifications_to_users() and
send_day_30_reminder_notifications().

Deployment
----------
1. ``railway service create`` in the AIQ project.
2. Point the service at this repo with root directory ``/``.
3. Set the service config to ``backend/infra/railway-cron-notifications.json``
   (or paste the JSON into the Railway dashboard).
4. Copy all env vars from the main backend service (DATABASE_URL, APNS_*,
   SENTRY_DSN, ENV, SLACK_ALERT_WEBHOOK, etc.).
5. Deploy.  Railway will build from ``backend/Dockerfile`` and run
   ``python run_notifications.py`` on the ``0 9 * * *`` schedule.
6. Verify via Railway logs or the heartbeat JSON that the first run succeeds.
"""

import asyncio
import logging
import sys

from gioe_libs.alerting.alerting import AlertManager, RunSummary
from gioe_libs.cron_runner.cron_job import CronJob
from gioe_libs.observability import observability

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.models.base import AsyncSessionLocal
from app.services.notification_scheduler import NotificationScheduler

logger = logging.getLogger("notifications_cron")


async def _send_all() -> RunSummary:
    """Send test-reminder and Day 30 notifications, return a RunSummary dict."""
    async with AsyncSessionLocal() as db:
        scheduler = NotificationScheduler(db)

        test_results = await scheduler.send_notifications_to_users()
        day30_results = await scheduler.send_day_30_reminder_notifications()

    total_sent = test_results.get("success", 0) + day30_results.get("success", 0)
    total_failed = test_results.get("failed", 0) + day30_results.get("failed", 0)

    logger.info(
        "Notifications complete: test_reminders=%s, day_30=%s",
        test_results,
        day30_results,
    )

    return {
        "test_reminders": test_results,
        "day_30_reminders": day30_results,
        "total_sent": total_sent,
        "total_failed": total_failed,
        "sent_at": utc_now().isoformat(),
    }


def work_fn() -> RunSummary:
    """Synchronous wrapper expected by CronJob."""
    return asyncio.run(_send_all())


def main() -> int:
    observability.init(
        config_path="config/observability.yaml",
        service_name="notifications-cron",
        environment=settings.ENV,
    )

    alert_manager = AlertManager(
        discord_webhook_url=settings.SLACK_ALERT_WEBHOOK or None,
        service_name="notifications-cron",
    )

    job = CronJob(
        name="notification-sender",
        schedule="0 9 * * *",
        work_fn=work_fn,
        observability=observability,
        alert_manager=alert_manager,
    )
    return job.run_once()


if __name__ == "__main__":
    sys.exit(main())
