"""Alert notification system for critical errors and inventory monitoring.

This module provides functionality to send alerts via email and other channels
when critical errors occur in the question generation pipeline, including
low inventory alerts for question strata.
"""

import logging
import re
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from .error_classifier import ClassifiedError, ErrorCategory, ErrorSeverity

# Basic email format validation pattern (RFC 5322 simplified)
_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert notifications for critical errors."""

    # Maximum number of alerts to retain in memory
    MAX_ALERTS_RETENTION = 1000

    # Default SMTP timeout in seconds
    SMTP_TIMEOUT_SECONDS = 30

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

        # Track alerts sent (capped to prevent unbounded memory growth)
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
            else:
                # Validate email formats
                if from_email and not _EMAIL_PATTERN.match(from_email):
                    logger.warning(
                        f"Invalid from_email format: {from_email}. "
                        "Email alerts will not be sent."
                    )
                    self.email_enabled = False
                invalid_recipients = [
                    e for e in self.to_emails if not _EMAIL_PATTERN.match(e)
                ]
                if invalid_recipients:
                    logger.warning(
                        f"Invalid recipient email format(s): {invalid_recipients}. "
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

        # Track alert (with bounded memory)
        self.alerts_sent.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": classified_error.to_dict(),
                "context": context,
                "success": success,
            }
        )

        # Trim to max retention to prevent unbounded memory growth
        if len(self.alerts_sent) > self.MAX_ALERTS_RETENTION:
            self.alerts_sent = self.alerts_sent[-self.MAX_ALERTS_RETENTION :]

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
                    "2. Review usage quotas and limits",
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
        elif classified_error.category == ErrorCategory.INVENTORY_LOW:
            lines.extend(
                [
                    "1. Run question generation with --auto-balance flag",
                    "2. Review generation logs for recent failures",
                    "3. Check LLM provider API quotas and billing",
                    "4. Consider increasing questions_per_run in config",
                    "5. Monitor /v1/admin/inventory-health endpoint",
                ]
            )
        elif classified_error.category == ErrorCategory.SCRIPT_FAILURE:
            # NOTE: These recommended actions are intentionally duplicated in
            # scripts/send_script_alert.py (build_alert_message function).
            # That script is standalone to avoid importing this module (which requires
            # API keys and other config). If updating these actions, also update
            # the corresponding section in send_script_alert.py.
            lines.extend(
                [
                    "1. Check bootstrap script logs for detailed error messages",
                    "2. Review LLM provider status pages for outages",
                    "3. Verify API keys are valid and have sufficient quota",
                    "4. Check network connectivity to LLM providers",
                    "5. Re-run failed types individually: ./scripts/bootstrap_inventory.sh --types <type>",
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

        # Validate required SMTP configuration
        if self.smtp_host is None:
            raise ValueError("SMTP host must be configured for email alerts")
        if self.smtp_username is None:
            raise ValueError("SMTP username must be configured for email alerts")
        if self.smtp_password is None:
            raise ValueError("SMTP password must be configured for email alerts")

        with smtplib.SMTP(
            self.smtp_host, self.smtp_port, timeout=self.SMTP_TIMEOUT_SECONDS
        ) as server:
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)

        logger.debug(f"Email sent to {len(self.to_emails)} recipients")

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

        if self.alert_file_path is None:
            raise ValueError("Alert file path must be configured")

        # Ensure directory exists
        alert_path = Path(self.alert_file_path)
        alert_path.parent.mkdir(parents=True, exist_ok=True)

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


@dataclass
class AlertingConfig:
    """Configuration for inventory alerting loaded from YAML."""

    # Inventory thresholds
    healthy_min: int = 50
    warning_min: int = 20
    critical_min: int = 5

    # Cooldown settings (in minutes)
    per_stratum_cooldown_minutes: int = 60
    global_cooldown_minutes: int = 15
    max_alerts_per_hour: int = 10

    # Content settings
    include_affected_strata: bool = True
    max_strata_detail: int = 5
    include_recommendations: bool = True

    # Email settings
    subject_prefix_warning: str = "[AIQ] Inventory Warning"
    subject_prefix_critical: str = "[AIQ] CRITICAL: Inventory Alert"

    # File logging
    inventory_alert_file: str = "./logs/inventory_alerts.log"
    log_all_checks: bool = False

    @classmethod
    def from_yaml(cls, config_path: str) -> "AlertingConfig":
        """Load alerting configuration from YAML file.

        Args:
            config_path: Path to alerting.yaml configuration file

        Returns:
            AlertingConfig instance with loaded settings
        """
        path = Path(config_path)
        if not path.exists():
            logger.warning(
                f"Alerting config not found at {config_path}, using defaults"
            )
            return cls()

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML in alerting config: {e}")
            logger.warning("Using default alerting configuration")
            return cls()
        except (IOError, OSError) as e:
            logger.error(f"Failed to read alerting config: {e}")
            logger.warning("Using default alerting configuration")
            return cls()

        if not data:
            logger.warning("Empty alerting config, using defaults")
            return cls()

        inventory = data.get("inventory", {})
        thresholds = inventory.get("thresholds", {})
        cooldown = inventory.get("cooldown", {})
        content = inventory.get("content", {})
        email = data.get("email", {})
        file_logging = data.get("file_logging", {})

        # Load threshold values with defaults
        healthy = thresholds.get("healthy_min", 50)
        warning = thresholds.get("warning_min", 20)
        critical = thresholds.get("critical_min", 5)

        # Validate threshold ordering
        if not (critical < warning < healthy):
            logger.error(
                f"Invalid threshold configuration: critical_min ({critical}) < "
                f"warning_min ({warning}) < healthy_min ({healthy}) required"
            )
            logger.warning("Using default thresholds")
            healthy, warning, critical = 50, 20, 5

        return cls(
            healthy_min=healthy,
            warning_min=warning,
            critical_min=critical,
            per_stratum_cooldown_minutes=cooldown.get("per_stratum_minutes", 60),
            global_cooldown_minutes=cooldown.get("global_minutes", 15),
            max_alerts_per_hour=cooldown.get("max_alerts_per_hour", 10),
            include_affected_strata=content.get("include_affected_strata", True),
            max_strata_detail=content.get("max_strata_detail", 5),
            include_recommendations=content.get("include_recommendations", True),
            subject_prefix_warning=email.get(
                "subject_prefix_warning", "[AIQ] Inventory Warning"
            ),
            subject_prefix_critical=email.get(
                "subject_prefix_critical", "[AIQ] CRITICAL: Inventory Alert"
            ),
            inventory_alert_file=file_logging.get(
                "inventory_alert_file", "./logs/inventory_alerts.log"
            ),
            log_all_checks=file_logging.get("log_all_checks", False),
        )


@dataclass
class StratumAlert:
    """Alert information for a single stratum."""

    question_type: str
    difficulty: str
    current_count: int
    threshold: int
    severity: ErrorSeverity


@dataclass
class InventoryAlertResult:
    """Result of an inventory alert check."""

    alerts_sent: int = 0
    alerts_suppressed: int = 0
    strata_checked: int = 0
    critical_strata: List[StratumAlert] = field(default_factory=list)
    warning_strata: List[StratumAlert] = field(default_factory=list)
    healthy_strata: int = 0


class InventoryAlertManager:
    """Manages inventory-specific alerting with cooldown tracking.

    This class extends the base AlertManager with inventory-specific functionality:
    - Threshold-based alerts (critical, warning, healthy)
    - Per-stratum cooldowns to prevent alert spam
    - Global cooldowns for overall alert rate limiting
    - Actionable alert content with affected strata details

    Note: This class is NOT thread-safe. It must only be called from a single
    thread. For concurrent access, use external synchronization.

    Example usage:
        from app.alerting import InventoryAlertManager, AlertingConfig

        config = AlertingConfig.from_yaml("./config/alerting.yaml")
        inventory_alerter = InventoryAlertManager(
            alert_manager=alert_manager,
            config=config,
        )

        # Check inventory and send alerts if needed
        result = inventory_alerter.check_and_alert(analysis)
    """

    # Buffer time (in minutes) after cooldown to keep entries before cleanup
    COOLDOWN_CLEANUP_BUFFER_MINUTES = 60

    def __init__(
        self,
        alert_manager: AlertManager,
        config: Optional[AlertingConfig] = None,
    ):
        """Initialize inventory alert manager.

        Args:
            alert_manager: Base AlertManager for sending alerts
            config: Alerting configuration (uses defaults if not provided)
        """
        self.alert_manager = alert_manager
        self.config = config or AlertingConfig()

        # Cooldown tracking
        # Key: (question_type, difficulty) tuple, Value: datetime of last alert
        self._stratum_last_alert: Dict[Tuple[str, str], datetime] = {}
        self._global_last_alert: Optional[datetime] = None
        self._alerts_this_hour: List[datetime] = []

        logger.info(
            f"InventoryAlertManager initialized: "
            f"critical_min={self.config.critical_min}, "
            f"warning_min={self.config.warning_min}, "
            f"cooldown={self.config.per_stratum_cooldown_minutes}min"
        )

    def _cleanup_old_cooldowns(self, now: datetime) -> None:
        """Remove cooldown entries older than cooldown period plus buffer.

        This prevents unbounded memory growth in long-running processes.

        Args:
            now: Current timestamp
        """
        cutoff = now - timedelta(
            minutes=self.config.per_stratum_cooldown_minutes
            + self.COOLDOWN_CLEANUP_BUFFER_MINUTES
        )

        keys_to_remove = [
            key
            for key, last_alert in self._stratum_last_alert.items()
            if last_alert < cutoff
        ]

        for key in keys_to_remove:
            del self._stratum_last_alert[key]

        if keys_to_remove:
            logger.debug(f"Cleaned up {len(keys_to_remove)} old cooldown entries")

    def check_and_alert(
        self,
        strata_inventory: List[Any],
    ) -> InventoryAlertResult:
        """Check inventory levels and send alerts for strata below thresholds.

        This is the main entry point for inventory alerting. It:
        1. Evaluates each stratum against thresholds
        2. Applies cooldown rules to prevent spam
        3. Sends alerts for strata that need attention
        4. Logs inventory check results

        Args:
            strata_inventory: List of StratumInventory objects from InventoryAnalyzer

        Returns:
            InventoryAlertResult with check statistics
        """
        result = InventoryAlertResult(strata_checked=len(strata_inventory))
        now = datetime.now(timezone.utc)

        # Cleanup old cooldown entries to prevent memory growth
        self._cleanup_old_cooldowns(now)

        # Categorize strata by severity
        critical_strata: List[StratumAlert] = []
        warning_strata: List[StratumAlert] = []

        for stratum in strata_inventory:
            q_type = stratum.question_type.value
            difficulty = stratum.difficulty.value
            count = stratum.current_count

            if count < self.config.critical_min:
                critical_strata.append(
                    StratumAlert(
                        question_type=q_type,
                        difficulty=difficulty,
                        current_count=count,
                        threshold=self.config.critical_min,
                        severity=ErrorSeverity.CRITICAL,
                    )
                )
            elif count < self.config.warning_min:
                warning_strata.append(
                    StratumAlert(
                        question_type=q_type,
                        difficulty=difficulty,
                        current_count=count,
                        threshold=self.config.warning_min,
                        severity=ErrorSeverity.HIGH,
                    )
                )
            else:
                result.healthy_strata += 1

        result.critical_strata = critical_strata
        result.warning_strata = warning_strata

        # Log inventory check if configured
        if self.config.log_all_checks:
            self._log_inventory_check(result)

        # Send alerts for critical strata (highest priority)
        if critical_strata:
            alerts_sent, alerts_suppressed = self._send_inventory_alerts(
                strata=critical_strata,
                severity=ErrorSeverity.CRITICAL,
                now=now,
            )
            result.alerts_sent += alerts_sent
            result.alerts_suppressed += alerts_suppressed

        # Send alerts for warning strata
        if warning_strata:
            alerts_sent, alerts_suppressed = self._send_inventory_alerts(
                strata=warning_strata,
                severity=ErrorSeverity.HIGH,
                now=now,
            )
            result.alerts_sent += alerts_sent
            result.alerts_suppressed += alerts_suppressed

        logger.info(
            f"Inventory alert check complete: "
            f"{result.alerts_sent} alerts sent, "
            f"{result.alerts_suppressed} suppressed by cooldown"
        )

        return result

    def _send_inventory_alerts(
        self,
        strata: List[StratumAlert],
        severity: ErrorSeverity,
        now: datetime,
    ) -> Tuple[int, int]:
        """Send alerts for a list of strata with the given severity.

        Args:
            strata: List of StratumAlert objects to alert on
            severity: Severity level for these alerts
            now: Current timestamp

        Returns:
            Tuple of (alerts_sent, alerts_suppressed)
        """
        alerts_sent = 0
        alerts_suppressed = 0

        # Filter strata that are not in cooldown
        alertable_strata: List[StratumAlert] = []
        for stratum in strata:
            key = (stratum.question_type, stratum.difficulty)
            if self._is_in_cooldown(key, now):
                alerts_suppressed += 1
                logger.debug(f"Alert suppressed for {key[0]}/{key[1]} (in cooldown)")
            else:
                alertable_strata.append(stratum)

        if not alertable_strata:
            return alerts_sent, alerts_suppressed

        # Check global cooldown
        if self._is_global_cooldown_active(now):
            logger.info(
                f"Global cooldown active, suppressing {len(alertable_strata)} alerts"
            )
            return alerts_sent, alerts_suppressed + len(alertable_strata)

        # Check hourly rate limit
        if not self._check_hourly_rate_limit(now):
            logger.warning(
                f"Hourly alert limit reached ({self.config.max_alerts_per_hour}), "
                f"suppressing {len(alertable_strata)} alerts"
            )
            return alerts_sent, alerts_suppressed + len(alertable_strata)

        # Build and send a single consolidated alert for all affected strata
        classified_error = self._build_inventory_error(
            strata=alertable_strata,
            severity=severity,
        )
        context = self._build_inventory_context(alertable_strata)

        success = self.alert_manager.send_alert(classified_error, context)

        if success:
            alerts_sent = len(alertable_strata)
            # Update cooldown tracking
            for stratum in alertable_strata:
                key = (stratum.question_type, stratum.difficulty)
                self._stratum_last_alert[key] = now
            self._global_last_alert = now
            self._alerts_this_hour.append(now)

            # Write to inventory-specific alert file
            self._write_inventory_alert_file(alertable_strata, severity)
        else:
            alerts_suppressed += len(alertable_strata)

        return alerts_sent, alerts_suppressed

    def _is_in_cooldown(self, key: Tuple[str, str], now: datetime) -> bool:
        """Check if a stratum is in cooldown period.

        Args:
            key: Tuple of (question_type, difficulty)
            now: Current timestamp

        Returns:
            True if stratum is in cooldown and should not be alerted
        """
        last_alert = self._stratum_last_alert.get(key)
        if last_alert is None:
            return False

        cooldown_delta = timedelta(minutes=self.config.per_stratum_cooldown_minutes)
        return now < last_alert + cooldown_delta

    def _is_global_cooldown_active(self, now: datetime) -> bool:
        """Check if global cooldown is active.

        Args:
            now: Current timestamp

        Returns:
            True if global cooldown is active
        """
        if self._global_last_alert is None:
            return False

        cooldown_delta = timedelta(minutes=self.config.global_cooldown_minutes)
        return now < self._global_last_alert + cooldown_delta

    def _check_hourly_rate_limit(self, now: datetime) -> bool:
        """Check if we're under the hourly rate limit.

        Args:
            now: Current timestamp

        Returns:
            True if we can send more alerts this hour
        """
        # Remove alerts older than 1 hour
        one_hour_ago = now - timedelta(hours=1)
        self._alerts_this_hour = [
            ts for ts in self._alerts_this_hour if ts > one_hour_ago
        ]

        return len(self._alerts_this_hour) < self.config.max_alerts_per_hour

    def _build_inventory_error(
        self,
        strata: List[StratumAlert],
        severity: ErrorSeverity,
    ) -> ClassifiedError:
        """Build a ClassifiedError for inventory alerts.

        Args:
            strata: List of affected strata
            severity: Alert severity

        Returns:
            ClassifiedError representing the inventory issue
        """
        severity_word = "critical" if severity == ErrorSeverity.CRITICAL else "low"
        threshold = strata[0].threshold if strata else 0

        message = (
            f"{len(strata)} question strata have {severity_word} inventory levels "
            f"(below {threshold} questions). "
            f"Question generation may be needed to replenish inventory."
        )

        return ClassifiedError(
            category=ErrorCategory.INVENTORY_LOW,
            severity=severity,
            provider="inventory",
            original_error="LowInventory",
            message=message,
            is_retryable=True,
        )

    def _build_inventory_context(self, strata: List[StratumAlert]) -> str:
        """Build context string with affected strata details.

        Args:
            strata: List of affected strata

        Returns:
            Context string with stratum details
        """
        lines = ["Affected strata:"]

        # Sort by count (lowest first)
        sorted_strata = sorted(strata, key=lambda s: s.current_count)

        # Show detailed info for top N strata
        for i, stratum in enumerate(sorted_strata[: self.config.max_strata_detail]):
            lines.append(
                f"  - {stratum.question_type}/{stratum.difficulty}: "
                f"{stratum.current_count} questions (threshold: {stratum.threshold})"
            )

        # Summarize remaining if any
        remaining = len(strata) - self.config.max_strata_detail
        if remaining > 0:
            lines.append(f"  ... and {remaining} more strata")

        if self.config.include_recommendations:
            lines.extend(
                [
                    "",
                    "Recommended Actions:",
                    "1. Run question generation with --auto-balance flag",
                    "2. Review generation logs for any failures",
                    "3. Check LLM provider API quotas and billing",
                    "4. Consider increasing questions_per_run in config",
                ]
            )

        return "\n".join(lines)

    def _log_inventory_check(self, result: InventoryAlertResult) -> None:
        """Log inventory check results to file.

        Args:
            result: Results of the inventory check
        """
        try:
            log_path = Path(self.config.inventory_alert_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).isoformat()
            entry = {
                "timestamp": timestamp,
                "type": "inventory_check",
                "strata_checked": result.strata_checked,
                "healthy_strata": result.healthy_strata,
                "warning_strata": len(result.warning_strata),
                "critical_strata": len(result.critical_strata),
            }

            with open(log_path, "a") as f:
                f.write(f"{entry}\n")
        except (IOError, OSError) as e:
            logger.error(f"Failed to log inventory check: {e}")

    def _write_inventory_alert_file(
        self,
        strata: List[StratumAlert],
        severity: ErrorSeverity,
    ) -> None:
        """Write inventory alert to dedicated alert file.

        Args:
            strata: List of affected strata
            severity: Alert severity
        """
        try:
            log_path = Path(self.config.inventory_alert_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now(timezone.utc).isoformat()

            lines = [
                "=" * 80,
                f"TIMESTAMP: {timestamp}",
                f"SEVERITY: {severity.value.upper()}",
                "TYPE: INVENTORY_LOW",
                f"AFFECTED_STRATA: {len(strata)}",
                "",
            ]

            for stratum in strata:
                lines.append(
                    f"  {stratum.question_type}/{stratum.difficulty}: "
                    f"{stratum.current_count} (threshold: {stratum.threshold})"
                )

            lines.extend(["", "=" * 80, ""])

            with open(log_path, "a") as f:
                f.write("\n".join(lines))
        except (IOError, OSError) as e:
            logger.error(f"Failed to write inventory alert file: {e}")

    def get_cooldown_status(self) -> Dict[str, Any]:
        """Get current cooldown status for debugging/monitoring.

        Returns:
            Dictionary with cooldown state information
        """
        now = datetime.now(timezone.utc)
        one_hour_ago = now - timedelta(hours=1)

        active_cooldowns = {}
        for key, last_alert in self._stratum_last_alert.items():
            cooldown_delta = timedelta(minutes=self.config.per_stratum_cooldown_minutes)
            if now < last_alert + cooldown_delta:
                remaining = (last_alert + cooldown_delta - now).total_seconds() / 60
                active_cooldowns[
                    f"{key[0]}/{key[1]}"
                ] = f"{remaining:.1f} min remaining"

        return {
            "global_cooldown_active": self._is_global_cooldown_active(now),
            "alerts_this_hour": len(
                [ts for ts in self._alerts_this_hour if ts > one_hour_ago]
            ),
            "max_alerts_per_hour": self.config.max_alerts_per_hour,
            "active_stratum_cooldowns": active_cooldowns,
        }
