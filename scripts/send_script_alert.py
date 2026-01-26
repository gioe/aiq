#!/usr/bin/env python3
"""Send script-level alerts for bootstrap failures.

This utility script is called by bootstrap_inventory.sh when multiple question
types fail during generation. It provides a bridge between bash orchestration
and the Python alerting infrastructure.

Usage:
    python send_script_alert.py --failed-count N --failed-types "type1,type2,..." \
        [--error-details "error message"]

Example:
    python send_script_alert.py --failed-count 3 --failed-types "math,verbal,logic" \
        --error-details "API rate limits exceeded"
"""

import argparse
import logging
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Minimum failed types to trigger alert (matches acceptance criteria)
CRITICAL_FAILURE_THRESHOLD = 3


def build_alert_message(
    failed_count: int,
    failed_types: list[str],
    error_details: str | None = None,
) -> str:
    """Build formatted alert message.

    Args:
        failed_count: Number of question types that failed
        failed_types: List of failed type names
        error_details: Optional error details from logs

    Returns:
        Formatted alert message
    """
    types_str = ", ".join(failed_types)
    timestamp = datetime.now(timezone.utc).isoformat()

    lines = [
        "ALERT: SCRIPT_FAILURE",
        "Severity: CRITICAL",
        "Provider: bootstrap",
        f"Time: {timestamp}",
        "",
        f"Message: {failed_count} question types failed during bootstrap: {types_str}.",
        "This indicates a systemic issue requiring investigation.",
        "",
    ]

    if error_details:
        lines.extend([f"Error Details: {error_details}", ""])

    # NOTE: These recommended actions are intentionally duplicated from
    # question-service/app/alerting.py (AlertManager._build_alert_message, SCRIPT_FAILURE case).
    # This script is standalone to avoid importing the full question-service app module
    # (which requires API keys and other config). If updating these actions, also update
    # the corresponding section in alerting.py.
    lines.extend(
        [
            "Recommended Actions:",
            "1. Check bootstrap script logs for detailed error messages",
            "2. Review LLM provider status pages for outages",
            "3. Verify API keys are valid and have sufficient quota",
            "4. Check network connectivity to LLM providers",
            "5. Re-run failed types individually: ./scripts/bootstrap_inventory.sh --types <type>",
        ]
    )

    return "\n".join(lines)


def send_email_alert(
    failed_count: int,
    failed_types: list[str],
    error_details: str | None = None,
) -> bool:
    """Send email alert if configured.

    Args:
        failed_count: Number of question types that failed
        failed_types: List of failed type names
        error_details: Optional error details from logs

    Returns:
        True if email was sent successfully
    """
    # Check if email is enabled
    if os.environ.get("ALERT_EMAIL_ENABLED", "").lower() != "true":
        logger.info("Email alerts not enabled (set ALERT_EMAIL_ENABLED=true)")
        return True  # Not a failure

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("ALERT_FROM_EMAIL")
    to_emails_str = os.environ.get("ALERT_TO_EMAILS", "")

    if not all([smtp_host, smtp_username, smtp_password, from_email, to_emails_str]):
        logger.warning("Email configuration incomplete, skipping email alert")
        return True  # Not a failure

    to_emails = [e.strip() for e in to_emails_str.split(",") if e.strip()]
    if not to_emails:
        logger.warning("No email recipients configured, skipping email alert")
        return True

    try:
        # Build message
        alert_message = build_alert_message(failed_count, failed_types, error_details)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AIQ] CRITICAL: {failed_count} Question Types Failed in Bootstrap"
        msg["From"] = from_email
        msg["To"] = ", ".join(to_emails)

        # Plain text body
        msg.attach(MIMEText(alert_message, "plain"))

        # Send email
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)

        logger.info(f"Email alert sent to {len(to_emails)} recipients")
        return True
    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False


def write_alert_file(
    failed_count: int,
    failed_types: list[str],
    error_details: str | None = None,
) -> bool:
    """Write alert to file.

    Args:
        failed_count: Number of question types that failed
        failed_types: List of failed type names
        error_details: Optional error details from logs

    Returns:
        True if file was written successfully
    """
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    question_service_dir = project_root / "question-service"

    alert_file_path = os.environ.get(
        "ALERT_FILE_PATH",
        str(question_service_dir / "logs" / "script_alerts.log"),
    )

    try:
        alert_path = Path(alert_file_path)
        alert_path.parent.mkdir(parents=True, exist_ok=True)

        alert_message = build_alert_message(failed_count, failed_types, error_details)
        timestamp = datetime.now(timezone.utc).isoformat()

        alert_entry = f"""
{'=' * 80}
TIMESTAMP: {timestamp}
{alert_message}
{'=' * 80}

"""

        with open(alert_path, "a") as f:
            f.write(alert_entry)

        logger.info(f"Alert written to file: {alert_file_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to write alert file: {e}")
        return False


def send_alert(
    failed_count: int,
    failed_types: list[str],
    error_details: str | None = None,
) -> bool:
    """Send an alert for script-level failures.

    Args:
        failed_count: Number of question types that failed
        failed_types: List of failed type names
        error_details: Optional error details from logs

    Returns:
        True if alert was sent successfully
    """
    success = True

    # Write to file (always)
    if not write_alert_file(failed_count, failed_types, error_details):
        success = False

    # Send email (if configured)
    if not send_email_alert(failed_count, failed_types, error_details):
        success = False

    if success:
        logger.info(f"Alert processed for {failed_count} failed types: {failed_types}")
    else:
        logger.warning(f"Some alert channels failed for {failed_count} failed types")

    return success


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Send script-level alerts for bootstrap failures"
    )
    parser.add_argument(
        "--failed-count",
        type=int,
        required=True,
        help="Number of question types that failed",
    )
    parser.add_argument(
        "--failed-types",
        type=str,
        required=True,
        help="Comma-separated list of failed type names",
    )
    parser.add_argument(
        "--error-details",
        type=str,
        default=None,
        help="Optional error details from logs",
    )

    args = parser.parse_args()

    # Parse failed types
    failed_types = [t.strip() for t in args.failed_types.split(",") if t.strip()]

    # Validate threshold
    if args.failed_count < CRITICAL_FAILURE_THRESHOLD:
        logger.info(
            f"Failed count ({args.failed_count}) below threshold "
            f"({CRITICAL_FAILURE_THRESHOLD}), skipping alert"
        )
        return 0

    # Send alert
    success = send_alert(
        failed_count=args.failed_count,
        failed_types=failed_types,
        error_details=args.error_details,
    )

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
