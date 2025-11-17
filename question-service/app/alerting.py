"""Alert notification system for critical errors.

This module provides functionality to send alerts via email and other channels
when critical errors occur in the question generation pipeline.
"""

import logging
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional

from .error_classifier import ClassifiedError, ErrorCategory, ErrorSeverity

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert notifications for critical errors."""

    def __init__(
        self,
        email_enabled: bool = False,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_username: Optional[str] = None,
        smtp_password: Optional[str] = None,
        from_email: Optional[str] = None,
        to_emails: Optional[List[str]] = None,
        alert_file_path: Optional[str] = None,
    ):
        """Initialize alert manager.

        Args:
            email_enabled: Enable email alerts
            smtp_host: SMTP server host
            smtp_port: SMTP server port (default: 587 for TLS)
            smtp_username: SMTP username
            smtp_password: SMTP password
            from_email: Sender email address
            to_emails: List of recipient email addresses
            alert_file_path: Path to file for logging critical alerts
        """
        self.email_enabled = email_enabled
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.from_email = from_email
        self.to_emails = to_emails or []
        self.alert_file_path = alert_file_path

        # Track alerts sent to avoid spam
        self.alerts_sent: List[dict] = []

        if self.email_enabled:
            if not all([smtp_host, smtp_username, smtp_password, from_email]):
                logger.warning(
                    "Email alerts enabled but configuration incomplete. "
                    "Email alerts will not be sent."
                )
                self.email_enabled = False
            elif not self.to_emails:
                logger.warning(
                    "Email alerts enabled but no recipients configured. "
                    "Email alerts will not be sent."
                )
                self.email_enabled = False

        logger.info(
            f"AlertManager initialized: email_enabled={self.email_enabled}, "
            f"alert_file={bool(self.alert_file_path)}"
        )

    def send_alert(
        self,
        classified_error: ClassifiedError,
        context: Optional[str] = None,
    ) -> bool:
        """Send an alert for a classified error.

        Args:
            classified_error: The classified error to alert on
            context: Additional context about the error

        Returns:
            True if alert was sent successfully
        """
        # Build alert message
        alert_message = self._build_alert_message(classified_error, context)

        success = True

        # Send email alert if enabled
        if self.email_enabled:
            try:
                self._send_email_alert(classified_error, alert_message)
                logger.info(f"Email alert sent for {classified_error.category.value}")
            except Exception as e:
                logger.error(f"Failed to send email alert: {e}")
                success = False

        # Write to alert file if configured
        if self.alert_file_path:
            try:
                self._write_alert_file(classified_error, alert_message)
                logger.info(f"Alert written to file: {self.alert_file_path}")
            except Exception as e:
                logger.error(f"Failed to write alert file: {e}")
                success = False

        # Track alert
        self.alerts_sent.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": classified_error.to_dict(),
                "context": context,
                "success": success,
            }
        )

        return success

    def _build_alert_message(
        self,
        classified_error: ClassifiedError,
        context: Optional[str] = None,
    ) -> str:
        """Build formatted alert message.

        Args:
            classified_error: The classified error
            context: Additional context

        Returns:
            Formatted alert message
        """
        lines = [
            f"ALERT: {classified_error.category.value.upper()}",
            f"Severity: {classified_error.severity.value.upper()}",
            f"Provider: {classified_error.provider}",
            f"Time: {datetime.now(timezone.utc).isoformat()}",
            "",
            f"Message: {classified_error.message}",
            "",
            f"Original Error: {classified_error.original_error}",
        ]

        if context:
            lines.extend(["", f"Context: {context}"])

        if classified_error.is_retryable:
            lines.extend(["", "Note: This error may be transient and retryable."])
        else:
            lines.extend(["", "Note: This error requires manual intervention."])

        # Add action items based on category
        lines.extend(["", "Recommended Actions:"])

        if classified_error.category == ErrorCategory.BILLING_QUOTA:
            lines.extend(
                [
                    f"1. Check your {classified_error.provider} account balance",
                    f"2. Review usage quotas and limits",
                    "3. Add funds or upgrade plan if needed",
                    "4. Verify billing information is up to date",
                ]
            )
        elif classified_error.category == ErrorCategory.AUTHENTICATION:
            lines.extend(
                [
                    f"1. Verify {classified_error.provider} API key is correct",
                    "2. Check if API key has expired",
                    "3. Regenerate API key if necessary",
                    "4. Update environment variables with new key",
                ]
            )
        elif classified_error.category == ErrorCategory.RATE_LIMIT:
            lines.extend(
                [
                    "1. Reduce request frequency",
                    "2. Implement exponential backoff",
                    "3. Consider upgrading API tier for higher limits",
                ]
            )
        else:
            lines.extend(
                [
                    "1. Review error details above",
                    "2. Check provider status page",
                    "3. Review application logs for more context",
                ]
            )

        return "\n".join(lines)

    def _send_email_alert(
        self,
        classified_error: ClassifiedError,
        alert_message: str,
    ) -> None:
        """Send email alert.

        Args:
            classified_error: The classified error
            alert_message: Formatted alert message

        Raises:
            Exception: If email send fails
        """
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = self._get_email_subject(classified_error)
        msg["From"] = self.from_email
        msg["To"] = ", ".join(self.to_emails)

        # Create plain text body
        text_body = alert_message

        # Create HTML body
        html_body = self._create_html_alert(classified_error, alert_message)

        # Attach both plain text and HTML
        msg.attach(MIMEText(text_body, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        # Send email
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)

        logger.info(f"Email sent to {len(self.to_emails)} recipients")

    def _get_email_subject(self, classified_error: ClassifiedError) -> str:
        """Generate email subject line.

        Args:
            classified_error: The classified error

        Returns:
            Email subject line
        """
        emoji = "🚨" if classified_error.severity == ErrorSeverity.CRITICAL else "⚠️"

        return (
            f"{emoji} IQ Tracker Alert: {classified_error.category.value.title()} "
            f"({classified_error.provider})"
        )

    def _create_html_alert(
        self,
        classified_error: ClassifiedError,
        alert_message: str,
    ) -> str:
        """Create HTML version of alert email.

        Args:
            classified_error: The classified error
            alert_message: Plain text alert message

        Returns:
            HTML formatted alert
        """
        # Determine color based on severity
        color_map = {
            ErrorSeverity.CRITICAL: "#dc3545",  # Red
            ErrorSeverity.HIGH: "#fd7e14",  # Orange
            ErrorSeverity.MEDIUM: "#ffc107",  # Yellow
            ErrorSeverity.LOW: "#17a2b8",  # Cyan
        }
        color = color_map.get(classified_error.severity, "#6c757d")

        html = f"""
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                }}
                .alert-box {{
                    border-left: 4px solid {color};
                    padding: 15px;
                    background-color: #f8f9fa;
                    margin: 20px 0;
                }}
                .severity {{
                    color: {color};
                    font-weight: bold;
                    font-size: 18px;
                }}
                .detail {{
                    margin: 10px 0;
                }}
                .label {{
                    font-weight: bold;
                }}
                .actions {{
                    background-color: #e9ecef;
                    padding: 15px;
                    margin-top: 20px;
                    border-radius: 4px;
                }}
                .footer {{
                    margin-top: 30px;
                    font-size: 12px;
                    color: #6c757d;
                }}
            </style>
        </head>
        <body>
            <div class="alert-box">
                <div class="severity">{classified_error.severity.value.upper()} Alert</div>
                <div class="detail">
                    <span class="label">Category:</span> {classified_error.category.value.title()}
                </div>
                <div class="detail">
                    <span class="label">Provider:</span> {classified_error.provider}
                </div>
                <div class="detail">
                    <span class="label">Time:</span> {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
                </div>
            </div>

            <div class="detail">
                <span class="label">Message:</span><br>
                {classified_error.message}
            </div>

            <div class="actions">
                <div class="label">Recommended Actions:</div>
                <pre style="white-space: pre-wrap; font-family: Arial, sans-serif;">{alert_message.split('Recommended Actions:')[1] if 'Recommended Actions:' in alert_message else ''}</pre>
            </div>

            <div class="footer">
                <p>This is an automated alert from the IQ Tracker Question Generation Service.</p>
                <p>Original error: {classified_error.original_error}</p>
            </div>
        </body>
        </html>
        """
        return html

    def _write_alert_file(
        self,
        classified_error: ClassifiedError,
        alert_message: str,
    ) -> None:
        """Write alert to file.

        Args:
            classified_error: The classified error
            alert_message: Formatted alert message

        Raises:
            Exception: If file write fails
        """
        timestamp = datetime.now(timezone.utc).isoformat()

        alert_entry = f"""
{'=' * 80}
TIMESTAMP: {timestamp}
{alert_message}
{'=' * 80}

"""

        with open(self.alert_file_path, "a") as f:
            f.write(alert_entry)

    def get_alerts_summary(self) -> dict:
        """Get summary of alerts sent.

        Returns:
            Dictionary with alert statistics
        """
        if not self.alerts_sent:
            return {
                "total_alerts": 0,
                "successful": 0,
                "failed": 0,
                "by_category": {},
                "by_severity": {},
            }

        successful = sum(1 for a in self.alerts_sent if a["success"])
        failed = len(self.alerts_sent) - successful

        # Count by category
        by_category = {}
        by_severity = {}

        for alert in self.alerts_sent:
            category = alert["error"]["category"]
            severity = alert["error"]["severity"]

            by_category[category] = by_category.get(category, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1

        return {
            "total_alerts": len(self.alerts_sent),
            "successful": successful,
            "failed": failed,
            "by_category": by_category,
            "by_severity": by_severity,
            "alerts": self.alerts_sent,
        }
