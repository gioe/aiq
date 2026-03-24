"""Tests for alerting module including inventory alerting."""

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from app.observability.alerting import (
    AlertManager,
    AlertingConfig,
    ResourceMonitor,
    ResourceMonitorResult,
    ResourceStatus,
)
from app.infrastructure.error_classifier import (
    ClassifiedError,
    ErrorCategory,
    ErrorSeverity,
    LLMErrorCategory,
)
from app.data.models import DifficultyLevel, QuestionType


class TestAlertManager:
    """Tests for the base AlertManager class."""

    def test_initialization_with_defaults(self):
        """Test AlertManager initializes correctly with defaults."""
        manager = AlertManager()

        assert manager.email_enabled is False
        assert manager.smtp_host is None
        assert manager.smtp_port == 587
        assert manager.to_emails == []
        assert manager.alerts_sent == []

    def test_initialization_with_email_config(self):
        """Test AlertManager initializes with email configuration."""
        manager = AlertManager(
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="test-password-not-real",  # pragma: allowlist secret
            from_email="alerts@example.com",
            to_emails=["recipient@example.com"],
        )

        assert manager.email_enabled is True
        assert manager.smtp_host == "smtp.example.com"
        assert manager.to_emails == ["recipient@example.com"]

    def test_email_disabled_without_full_config(self):
        """Test email is disabled when config is incomplete."""
        manager = AlertManager(
            email_enabled=True,
            smtp_host="smtp.example.com",
            # Missing username, password, from_email
        )

        assert manager.email_enabled is False

    def test_email_disabled_without_recipients(self):
        """Test email is disabled when no recipients configured."""
        manager = AlertManager(
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_username="user@example.com",
            smtp_password="test-pass-fake",  # pragma: allowlist secret
            from_email="alerts@example.com",
            to_emails=[],  # No recipients
        )

        assert manager.email_enabled is False

    def test_send_alert_to_file(self):
        """Test alert is written to file when configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")

            manager = AlertManager(
                email_enabled=False,
                alert_file_path=alert_file,
            )

            error = ClassifiedError(
                category=LLMErrorCategory.BILLING_QUOTA,
                severity=ErrorSeverity.CRITICAL,
                provider="openai",
                original_error="BillingError",
                message="Insufficient funds",
                is_retryable=False,
            )

            success = manager.send_alert(error, context="Test context")

            assert success is True
            assert os.path.exists(alert_file)

            with open(alert_file) as f:
                content = f.read()
                assert "BILLING_QUOTA" in content
                assert "Insufficient funds" in content

    def test_build_alert_message_billing(self):
        """Test alert message building for billing errors."""
        manager = AlertManager()

        error = ClassifiedError(
            category=LLMErrorCategory.BILLING_QUOTA,
            severity=ErrorSeverity.CRITICAL,
            provider="openai",
            original_error="BillingError",
            message="Insufficient funds",
            is_retryable=False,
        )

        message = manager._build_alert_message(error)

        assert "BILLING_QUOTA" in message
        assert "CRITICAL" in message
        assert "openai" in message
        assert "Check your openai account balance" in message

    def test_build_alert_message_inventory_low(self):
        """Test alert message building for inventory alerts."""
        manager = AlertManager()

        error = ClassifiedError(
            category=ErrorCategory.INVENTORY_LOW,
            severity=ErrorSeverity.HIGH,
            provider="inventory",
            original_error="LowInventory",
            message="5 strata below threshold",
            is_retryable=True,
        )

        message = manager._build_alert_message(error)

        assert "INVENTORY_LOW" in message
        assert "Run question generation with --auto-balance flag" in message

    def test_build_alert_message_script_failure(self):
        """Test alert message building for script-level failures."""
        manager = AlertManager()

        error = ClassifiedError(
            category=ErrorCategory.SCRIPT_FAILURE,
            severity=ErrorSeverity.CRITICAL,
            provider="bootstrap",
            original_error="MultiTypeFailure",
            message="3 question types failed: math, verbal, logic",
            is_retryable=False,
        )

        message = manager._build_alert_message(error)

        assert "SCRIPT_FAILURE" in message
        assert "CRITICAL" in message
        assert "bootstrap" in message
        assert "Check bootstrap script logs" in message
        assert "Re-run failed types individually" in message

    def test_get_alerts_summary_empty(self):
        """Test alerts summary when no alerts sent."""
        manager = AlertManager()
        summary = manager.get_alerts_summary()

        assert summary["total_alerts"] == 0
        assert summary["successful"] == 0
        assert summary["failed"] == 0

    def test_get_alerts_summary_with_alerts(self):
        """Test alerts summary after sending alerts."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            manager = AlertManager(alert_file_path=alert_file)

            error = ClassifiedError(
                category=LLMErrorCategory.BILLING_QUOTA,
                severity=ErrorSeverity.CRITICAL,
                provider="openai",
                original_error="BillingError",
                message="Test",
                is_retryable=False,
            )

            manager.send_alert(error)
            summary = manager.get_alerts_summary()

            assert summary["total_alerts"] == 1
            assert summary["successful"] == 1
            assert "billing_quota" in summary["by_category"]


class TestAlertingConfig:
    """Tests for AlertingConfig dataclass."""

    def test_default_values(self):
        """Test default configuration values."""
        config = AlertingConfig()

        assert config.healthy_min == 50
        assert config.warning_min == 20
        assert config.critical_min == 5
        assert config.per_resource_cooldown_minutes == 60
        assert config.global_cooldown_minutes == 15
        assert config.max_alerts_per_hour == 10

    def test_from_yaml_with_valid_file(self):
        """Test loading configuration from valid YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "alerting.yaml")

            yaml_content = """
inventory:
  thresholds:
    healthy_min: 100
    warning_min: 30
    critical_min: 10
  cooldown:
    per_resource_minutes: 120
    global_minutes: 30
    max_alerts_per_hour: 5
"""
            with open(config_file, "w") as f:
                f.write(yaml_content)

            config = AlertingConfig.from_yaml(config_file)

            assert config.healthy_min == 100
            assert config.warning_min == 30
            assert config.critical_min == 10
            assert config.per_resource_cooldown_minutes == 120
            assert config.global_cooldown_minutes == 30
            assert config.max_alerts_per_hour == 5

    def test_from_yaml_with_missing_file(self):
        """Test loading configuration from non-existent file returns defaults."""
        config = AlertingConfig.from_yaml("/nonexistent/path/alerting.yaml")

        assert config.healthy_min == 50  # Default value
        assert config.warning_min == 20

    def test_from_yaml_with_partial_config(self):
        """Test loading partial configuration uses defaults for missing values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "alerting.yaml")

            yaml_content = """
inventory:
  thresholds:
    critical_min: 3
"""
            with open(config_file, "w") as f:
                f.write(yaml_content)

            config = AlertingConfig.from_yaml(config_file)

            assert config.critical_min == 3
            assert config.healthy_min == 50  # Default
            assert config.warning_min == 20  # Default


class TestResourceMonitorResult:
    """Tests for ResourceMonitorResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = ResourceMonitorResult()

        assert result.alerts_sent == 0
        assert result.alerts_suppressed == 0
        assert result.resources_checked == 0
        assert result.critical_resources == []
        assert result.warning_resources == []
        assert result.healthy_resources == 0


class TestResourceMonitorInventory:
    """Tests for ResourceMonitor used for AIQ inventory alerting."""

    @pytest.fixture
    def mock_alert_manager(self):
        """Create a mock AlertManager."""
        manager = Mock(spec=AlertManager)
        manager.send_alert = Mock(return_value=True)
        return manager

    @pytest.fixture
    def default_config(self):
        """Create a default AlertingConfig."""
        return AlertingConfig(
            healthy_min=50,
            warning_min=20,
            critical_min=5,
            per_resource_cooldown_minutes=60,
            global_cooldown_minutes=15,
            max_alerts_per_hour=10,
        )

    def _make_monitor(self, strata_counts, alert_manager, config):
        """Create a ResourceMonitor with a check_fn built from (name, count) pairs."""
        resources = [
            ResourceStatus(name=name, count=count) for name, count in strata_counts
        ]
        return ResourceMonitor(
            check_fn=lambda: resources,
            alert_manager=alert_manager,
            config=config,
        )

    def test_initialization(self, mock_alert_manager, default_config):
        """Test ResourceMonitor initialization."""
        monitor = self._make_monitor([], mock_alert_manager, default_config)
        assert monitor.config.critical_min == 5
        assert monitor.config.warning_min == 20

    def test_check_and_alert_healthy_inventory(
        self, mock_alert_manager, default_config
    ):
        """Test that no alerts are sent for healthy inventory."""
        monitor = self._make_monitor(
            [("math/easy", 60), ("math/medium", 55), ("math/hard", 70)],
            mock_alert_manager,
            default_config,
        )

        result = monitor.check_and_alert()

        assert result.alerts_sent == 0
        assert result.healthy_resources == 3
        assert len(result.critical_resources) == 0
        assert len(result.warning_resources) == 0
        mock_alert_manager.send_alert.assert_not_called()

    def test_check_and_alert_critical_resources(
        self, mock_alert_manager, default_config
    ):
        """Test alerts are sent for critical resources."""
        monitor = self._make_monitor(
            [("math/easy", 2), ("math/medium", 3), ("math/hard", 60)],
            mock_alert_manager,
            default_config,
        )

        result = monitor.check_and_alert()

        assert result.alerts_sent == 2
        assert len(result.critical_resources) == 2
        assert result.healthy_resources == 1
        mock_alert_manager.send_alert.assert_called()

    def test_check_and_alert_warning_resources(
        self, mock_alert_manager, default_config
    ):
        """Test alerts are sent for warning resources."""
        monitor = self._make_monitor(
            [("math/easy", 15), ("math/medium", 10), ("math/hard", 60)],
            mock_alert_manager,
            default_config,
        )

        result = monitor.check_and_alert()

        assert result.alerts_sent == 2
        assert len(result.warning_resources) == 2
        mock_alert_manager.send_alert.assert_called()

    def test_per_resource_cooldown(self, mock_alert_manager, default_config):
        """Test that per-resource cooldown prevents repeated alerts."""
        monitor = self._make_monitor(
            [("math/easy", 2)],
            mock_alert_manager,
            default_config,
        )

        # First check should send alert
        result1 = monitor.check_and_alert()
        assert result1.alerts_sent == 1

        # Second check should be suppressed by cooldown
        result2 = monitor.check_and_alert()
        assert result2.alerts_sent == 0
        assert result2.alerts_suppressed == 1

    def test_global_cooldown(self, mock_alert_manager):
        """Test that global cooldown prevents back-to-back alerts from different resources."""
        config = AlertingConfig(
            critical_min=5,
            warning_min=20,
            healthy_min=50,
            per_resource_cooldown_minutes=1,  # Very short per-resource cooldown
            global_cooldown_minutes=60,  # Longer global cooldown
            max_alerts_per_hour=100,
        )

        monitor1 = self._make_monitor([("math/easy", 2)], mock_alert_manager, config)
        result1 = monitor1.check_and_alert()
        assert result1.alerts_sent == 1

        # Different resource on a second monitor (same alert_manager state) —
        # simulate global cooldown by using same monitor with different check_fn
        monitor2 = ResourceMonitor(
            check_fn=lambda: [ResourceStatus(name="logic/hard", count=3)],
            alert_manager=mock_alert_manager,
            config=config,
        )
        # Carry over global cooldown state from first monitor
        monitor2._global_last_alert = monitor1._global_last_alert

        result2 = monitor2.check_and_alert()
        assert result2.alerts_sent == 0
        assert result2.alerts_suppressed == 1

    def test_hourly_rate_limit(self, mock_alert_manager):
        """Test that hourly rate limit is enforced."""
        config = AlertingConfig(
            critical_min=5,
            warning_min=20,
            healthy_min=50,
            per_resource_cooldown_minutes=0,  # Disable per-resource cooldown
            global_cooldown_minutes=0,  # Disable global cooldown
            max_alerts_per_hour=2,  # Very low limit for testing
        )

        monitor = self._make_monitor([("math/easy", 2)], mock_alert_manager, config)

        # Manually add alert timestamps to simulate hitting the limit
        now = datetime.now(timezone.utc)
        monitor._alerts_this_hour = [
            now - timedelta(minutes=30),
            now - timedelta(minutes=15),
        ]

        result = monitor.check_and_alert()

        assert result.alerts_sent == 0
        assert result.alerts_suppressed == 1

    def test_get_cooldown_status(self, mock_alert_manager, default_config):
        """Test getting cooldown status."""
        monitor = self._make_monitor(
            [("math/easy", 2)], mock_alert_manager, default_config
        )
        monitor.check_and_alert()

        status = monitor.get_cooldown_status()

        assert "global_cooldown_active" in status
        assert "alerts_this_hour" in status
        assert status["alerts_this_hour"] >= 1

    def test_is_in_cooldown(self, mock_alert_manager, default_config):
        """Test cooldown checking logic."""
        monitor = self._make_monitor([], mock_alert_manager, default_config)
        now = datetime.now(timezone.utc)

        # No cooldown initially
        assert monitor._is_in_cooldown("math/easy", now) is False

        # Set last alert time
        monitor._resource_last_alert["math/easy"] = now - timedelta(minutes=30)

        # Should still be in cooldown (60 min default)
        assert monitor._is_in_cooldown("math/easy", now) is True

        # After cooldown expires
        monitor._resource_last_alert["math/easy"] = now - timedelta(minutes=61)
        assert monitor._is_in_cooldown("math/easy", now) is False

    def test_check_hourly_rate_limit_removes_old_alerts(
        self, mock_alert_manager, default_config
    ):
        """Test that old alerts are removed from hourly tracking."""
        monitor = self._make_monitor([], mock_alert_manager, default_config)
        now = datetime.now(timezone.utc)

        # Add some old and recent alerts
        monitor._alerts_this_hour = [
            now - timedelta(hours=2),  # Should be removed
            now - timedelta(minutes=90),  # Should be removed
            now - timedelta(minutes=30),  # Should be kept
        ]

        can_alert = monitor._check_hourly_rate_limit(now)

        assert can_alert is True
        assert len(monitor._alerts_this_hour) == 1  # Only recent one kept

    def test_inventory_check_fn_converts_strata_correctly(self):
        """Test that a check_fn built from StratumInventory objects produces correct ResourceStatus."""
        strata = [
            Mock(
                question_type=Mock(value="math"),
                difficulty=Mock(value="easy"),
                current_count=3,
            ),
            Mock(
                question_type=Mock(value="logic"),
                difficulty=Mock(value="hard"),
                current_count=60,
            ),
        ]

        resources = [
            ResourceStatus(
                name=f"{s.question_type.value}/{s.difficulty.value}",
                count=s.current_count,
            )
            for s in strata
        ]

        assert resources[0].name == "math/easy"
        assert resources[0].count == 3
        assert resources[1].name == "logic/hard"
        assert resources[1].count == 60


class TestSendNotification:
    """Tests for AlertManager.send_notification()."""

    def test_noop_when_email_disabled_and_no_discord(self):
        """send_notification is a no-op when email is disabled and no Discord URL."""
        manager = AlertManager(email_enabled=False)
        manager.send_notification(
            title="Run Complete",
            fields=[("Generated", 10), ("Inserted", 8)],
            severity="info",
        )

    def test_noop_when_email_disabled_no_smtp_call(self):
        """No SMTP connection is attempted when email is disabled."""
        import smtplib
        from unittest.mock import patch

        manager = AlertManager(email_enabled=False)
        with patch.object(smtplib, "SMTP") as mock_smtp:
            manager.send_notification(title="Test", fields=[], severity="info")
            mock_smtp.assert_not_called()

    def test_smtp_error_caught_and_logged(self, caplog):
        """SMTP errors are caught and logged, not raised."""
        import smtplib
        from unittest.mock import patch
        import logging

        manager = AlertManager(
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="test-password-not-real",  # pragma: allowlist secret
            from_email="alerts@example.com",
            to_emails=["recipient@example.com"],
        )

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_smtp_class.return_value.__enter__.return_value.send_message.side_effect = smtplib.SMTPException(
                "connection refused"
            )
            with caplog.at_level(logging.ERROR):
                manager.send_notification(title="Test", fields=[], severity="info")

        assert any(
            "Failed to send notification email" in r.message for r in caplog.records
        )

    def test_send_notification_sends_email_on_success(self):
        """Email is sent when email_enabled and SMTP is configured."""
        from unittest.mock import MagicMock, patch

        manager = AlertManager(
            email_enabled=True,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_username="user@example.com",
            smtp_password="test-password-not-real",  # pragma: allowlist secret
            from_email="alerts@example.com",
            to_emails=["recipient@example.com"],
        )

        with patch("smtplib.SMTP") as mock_smtp_class:
            mock_server = MagicMock()
            mock_smtp_class.return_value.__enter__.return_value = mock_server

            manager.send_notification(
                title="✅ question-generation: Success",
                fields=[
                    ("Generated", 10),
                    ("Inserted", 8),
                    ("Duration", "30.0s"),
                    ("Approval Rate", "80.0%"),
                ],
                severity="info",
            )

            mock_server.send_message.assert_called_once()

    def test_html_uses_green_for_info(self):
        """HTML notification body uses green color for severity='info'."""
        manager = AlertManager()
        html = manager._build_notification_html(
            title="Success", fields=[], severity="info", metadata=None
        )
        assert "#28a745" in html

    def test_html_uses_yellow_for_warning(self):
        """HTML notification body uses yellow color for severity='warning'."""
        manager = AlertManager()
        html = manager._build_notification_html(
            title="Warning", fields=[], severity="warning", metadata=None
        )
        assert "#ffc107" in html

    def test_html_uses_red_for_critical(self):
        """HTML notification body uses red color for severity='critical'."""
        manager = AlertManager()
        html = manager._build_notification_html(
            title="Failed", fields=[], severity="critical", metadata=None
        )
        assert "#dc3545" in html

    def test_html_includes_field_values(self):
        """HTML body contains field labels and values."""
        manager = AlertManager()
        html = manager._build_notification_html(
            title="Run Complete",
            fields=[("Generated", 50), ("Inserted", 42), ("Duration", "123.5s")],
            severity="info",
            metadata=None,
        )
        assert "50" in html
        assert "42" in html
        assert "123.5s" in html


class TestResourceMonitorAlertingIntegration:
    """Integration tests for ResourceMonitor-based inventory alerting."""

    def test_full_alerting_flow(self):
        """Test complete alerting flow from strata to alert via ResourceMonitor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            resource_alert_file = os.path.join(tmpdir, "resource_alerts.log")

            # Create real AlertManager
            alert_manager = AlertManager(
                email_enabled=False,
                alert_file_path=alert_file,
            )

            # Create config with resource alert file
            config = AlertingConfig(
                critical_min=5,
                warning_min=20,
                healthy_min=50,
                resource_alert_file=resource_alert_file,
                log_all_checks=True,
            )

            # Build mock strata and check_fn
            strata = []
            for q_type in [QuestionType.MATH, QuestionType.LOGIC]:
                for difficulty in DifficultyLevel:
                    stratum = Mock()
                    stratum.question_type = q_type
                    stratum.difficulty = difficulty
                    stratum.current_count = (
                        2
                        if q_type == QuestionType.MATH
                        and difficulty == DifficultyLevel.EASY
                        else 60
                    )
                    strata.append(stratum)

            def check_fn():
                return [
                    ResourceStatus(
                        name=f"{s.question_type.value}/{s.difficulty.value}",
                        count=s.current_count,
                    )
                    for s in strata
                ]

            monitor = ResourceMonitor(
                check_fn=check_fn,
                alert_manager=alert_manager,
                config=config,
            )

            # Run check
            result = monitor.check_and_alert()

            # Verify results
            assert result.alerts_sent >= 1
            assert len(result.critical_resources) >= 1

            # Alert file should be written
            assert os.path.exists(alert_file)

            with open(alert_file) as f:
                content = f.read()
                assert "RESOURCE_LOW" in content


class TestDiscordAlerting:
    """Tests for Discord webhook alert functionality."""

    FAKE_WEBHOOK = "https://discord.com/api/webhooks/test/fake"

    def _make_manager(self, webhook: str = FAKE_WEBHOOK) -> AlertManager:
        return AlertManager(discord_webhook_url=webhook)

    def _billing_error(self, provider: str = "openai") -> ClassifiedError:
        return ClassifiedError(
            category=LLMErrorCategory.BILLING_QUOTA,
            severity=ErrorSeverity.CRITICAL,
            provider=provider,
            original_error="BillingError",
            message="Quota exhausted",
            is_retryable=False,
        )

    # ------------------------------------------------------------------
    # _send_discord_alert
    # ------------------------------------------------------------------

    def test_send_discord_alert_no_webhook_returns_false(self):
        manager = AlertManager()  # no webhook
        result = manager._send_discord_alert("title", "desc", 0xFF0000)
        assert result is False

    def test_send_discord_alert_http_success(self):
        manager = self._make_manager()
        with patch("urllib.request.urlopen") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = Mock(return_value=False)
            result = manager._send_discord_alert("t", "d", 0xFF0000, fields=[])
        assert result is True
        assert mock_open.called

    def test_send_discord_alert_http_failure_returns_false(self):
        manager = self._make_manager()
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            result = manager._send_discord_alert("t", "d", 0xFF0000)
        assert result is False

    def test_send_discord_alert_payload_format(self):
        """Verify the JSON payload sent to Discord has the expected structure."""
        import json

        manager = self._make_manager()
        captured = {}

        def fake_urlopen(req, timeout):
            captured["data"] = json.loads(req.data)
            ctx = Mock()
            ctx.__enter__ = lambda s: s
            ctx.__exit__ = Mock(return_value=False)
            return ctx

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            manager._send_discord_alert(
                title="Test Title",
                description="Test Desc",
                color=0xDC3545,
                fields=[{"name": "Provider", "value": "openai", "inline": True}],
            )

        payload = captured["data"]
        assert "embeds" in payload
        embed = payload["embeds"][0]
        assert embed["title"] == "Test Title"
        assert embed["description"] == "Test Desc"
        assert embed["color"] == 0xDC3545
        assert embed["fields"][0]["name"] == "Provider"

    # ------------------------------------------------------------------
    # send_circuit_breaker_alert
    # ------------------------------------------------------------------

    def test_circuit_breaker_alert_no_webhook_returns_false(self):
        manager = AlertManager()
        result = manager.send_circuit_breaker_alert("openai", "threshold exceeded")
        assert result is False

    def test_circuit_breaker_alert_sends_discord(self):
        manager = self._make_manager()
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            result = manager.send_circuit_breaker_alert(
                "openai", "5 consecutive failures"
            )
        assert result is True
        assert mock_send.called
        args = mock_send.call_args
        assert "openai" in args.kwargs.get("title", args[0][0] if args[0] else "")

    def test_circuit_breaker_alert_sets_cooldown(self):
        manager = self._make_manager()
        with patch.object(manager, "_send_discord_alert", return_value=True):
            manager.send_circuit_breaker_alert("openai", "reason")
        assert "cb:openai" in manager._discord_cooldowns

    def test_circuit_breaker_alert_cooldown_suppresses_second(self):
        manager = self._make_manager()
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            manager.send_circuit_breaker_alert("openai", "reason")
            result = manager.send_circuit_breaker_alert("openai", "reason again")
        assert result is False
        # Only one actual Discord send should have occurred
        assert mock_send.call_count == 1

    def test_circuit_breaker_alert_different_providers_independent_cooldowns(self):
        manager = self._make_manager()
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            manager.send_circuit_breaker_alert("openai", "reason")
            result = manager.send_circuit_breaker_alert("anthropic", "reason")
        assert result is True
        assert mock_send.call_count == 2

    def test_circuit_breaker_alert_cooldown_expires(self):
        manager = self._make_manager()
        # Pre-set cooldown to 11 minutes ago (expired)
        manager._discord_cooldowns["cb:openai"] = time.time() - 660
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            result = manager.send_circuit_breaker_alert("openai", "new open")
        assert result is True
        assert mock_send.call_count == 1

    # ------------------------------------------------------------------
    # BILLING_QUOTA → Discord via send_alert
    # ------------------------------------------------------------------

    def test_send_alert_billing_quota_triggers_discord(self):
        manager = self._make_manager()
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            manager.send_alert(self._billing_error())
        assert mock_send.called

    def test_send_alert_rate_limit_does_not_trigger_discord(self):
        manager = self._make_manager()
        rate_error = ClassifiedError(
            category=LLMErrorCategory.RATE_LIMIT,
            severity=ErrorSeverity.HIGH,
            provider="openai",
            original_error="RateLimitError",
            message="rate limit hit",
            is_retryable=True,
        )
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            manager.send_alert(rate_error)
        assert not mock_send.called

    def test_billing_quota_alert_cooldown(self):
        manager = self._make_manager()
        with patch.object(
            manager, "_send_discord_alert", return_value=True
        ) as mock_send:
            manager.send_alert(self._billing_error("openai"))
            manager.send_alert(self._billing_error("openai"))
        assert mock_send.call_count == 1

    def test_discord_alert_callback_failure_does_not_raise(self):
        """Discord failure must never propagate to the caller."""
        manager = self._make_manager()
        with patch.object(
            manager, "_send_discord_alert", side_effect=RuntimeError("bang")
        ):
            # Should not raise
            manager.send_circuit_breaker_alert("openai", "reason")


class TestBuildCompletionTextNewFields:
    """Tests for _build_completion_text covering new email fields."""

    def _manager(self) -> AlertManager:
        return AlertManager()

    def test_new_stat_fields_appear_in_output(self):
        """questions_requested, questions_rejected, duplicates_found appear in text."""
        manager = self._manager()
        run_summary = {
            "details": {
                "questions_requested": 100,
                "questions_rejected": 15,
                "duplicates_found": 5,
            }
        }
        text = manager._build_completion_text(0, run_summary)

        assert "100" in text
        assert "15" in text
        assert "5" in text
        assert "Questions Requested" in text
        assert "Questions Rejected" in text
        assert "Duplicates Found" in text

    def test_new_stat_fields_none_falls_back_to_na(self):
        """None values for new stat fields produce N/A in text output."""
        manager = self._manager()
        run_summary = {
            "details": {
                "questions_requested": None,
                "questions_rejected": None,
                "duplicates_found": None,
            }
        }
        text = manager._build_completion_text(0, run_summary)

        # Each new field should individually produce N/A
        lines = text.splitlines()
        assert any("Questions Requested" in line and "N/A" in line for line in lines)
        assert any("Questions Rejected" in line and "N/A" in line for line in lines)
        assert any("Duplicates Found" in line and "N/A" in line for line in lines)

    def test_new_stat_fields_missing_falls_back_to_na(self):
        """Missing new stat keys produce N/A in text output."""
        manager = self._manager()
        text = manager._build_completion_text(0, {})

        assert "N/A" in text

    def test_by_type_section_present_when_non_empty(self):
        """by_type breakdown appears in text when dict is non-empty."""
        manager = self._manager()
        run_summary = {"details": {"by_type": {"math": 30, "logic": 20}}}
        text = manager._build_completion_text(0, run_summary)

        assert "By Type" in text
        assert "math" in text
        assert "30" in text
        assert "logic" in text
        assert "20" in text

    def test_by_difficulty_section_present_when_non_empty(self):
        """by_difficulty breakdown appears in text when dict is non-empty."""
        manager = self._manager()
        run_summary = {"details": {"by_difficulty": {"easy": 40, "hard": 10}}}
        text = manager._build_completion_text(0, run_summary)

        assert "By Difficulty" in text
        assert "easy" in text
        assert "40" in text
        assert "hard" in text
        assert "10" in text

    def test_by_type_section_absent_when_empty(self):
        """by_type section is omitted when dict is empty."""
        manager = self._manager()
        text = manager._build_completion_text(0, {"details": {"by_type": {}}})

        assert "By Type" not in text

    def test_by_difficulty_section_absent_when_empty(self):
        """by_difficulty section is omitted when dict is empty."""
        manager = self._manager()
        text = manager._build_completion_text(0, {"details": {"by_difficulty": {}}})

        assert "By Difficulty" not in text

    def test_error_message_appears_in_text(self):
        """error_message is included in text output when present."""
        manager = self._manager()
        run_summary = {"details": {"error_message": "Pipeline crashed at step 3"}}
        text = manager._build_completion_text(2, run_summary)

        assert "Pipeline crashed at step 3" in text
        assert "Error" in text

    def test_error_message_absent_when_none(self):
        """No error section when error_message is None."""
        manager = self._manager()
        text = manager._build_completion_text(0, {"details": {"error_message": None}})

        assert "Error:" not in text


class TestBuildCompletionHtmlNewFields:
    """Tests for _build_completion_html covering new email fields."""

    def _manager(self) -> AlertManager:
        return AlertManager()

    def test_new_stat_fields_appear_in_html(self):
        """questions_requested, questions_rejected, duplicates_found appear in HTML."""
        manager = self._manager()
        run_summary = {
            "details": {
                "questions_requested": 200,
                "questions_rejected": 25,
                "duplicates_found": 8,
            }
        }
        html = manager._build_completion_html(0, run_summary)

        assert "200" in html
        assert "25" in html
        assert "8" in html
        assert "Questions Requested" in html
        assert "Questions Rejected" in html
        assert "Duplicates Found" in html

    def test_new_stat_fields_none_falls_back_to_na(self):
        """None values for new stat fields produce N/A in HTML output."""
        manager = self._manager()
        run_summary = {
            "details": {
                "questions_requested": None,
                "questions_rejected": None,
                "duplicates_found": None,
            }
        }
        html = manager._build_completion_html(0, run_summary)

        # Each new field row should contain N/A in its value cell
        assert "<td>Questions Requested</td><td>N/A</td>" in html
        assert "<td>Questions Rejected</td><td>N/A</td>" in html
        assert "<td>Duplicates Found</td><td>N/A</td>" in html

    def test_new_stat_fields_missing_falls_back_to_na(self):
        """Missing new stat keys produce N/A in HTML output."""
        manager = self._manager()
        html = manager._build_completion_html(0, {})

        assert "N/A" in html

    def test_by_type_table_present_when_non_empty(self):
        """by_type table is rendered when dict is non-empty."""
        manager = self._manager()
        run_summary = {"details": {"by_type": {"verbal": 50, "spatial": 15}}}
        html = manager._build_completion_html(0, run_summary)

        assert "By Type" in html
        assert "Verbal" in html  # _display_name applies title-case
        assert "50" in html
        assert "Spatial" in html
        assert "15" in html

    def test_by_type_table_header_is_inserted(self):
        """By Type table column header reads 'Inserted' (not 'Generated')."""
        manager = self._manager()
        run_summary = {"details": {"by_type": {"math": 12}}}
        html = manager._build_completion_html(0, run_summary)

        assert "<th>Inserted</th>" in html
        assert "<th>Generated</th>" not in html

    def test_by_difficulty_table_present_when_non_empty(self):
        """by_difficulty table is rendered when dict is non-empty."""
        manager = self._manager()
        run_summary = {"details": {"by_difficulty": {"medium": 60, "hard": 20}}}
        html = manager._build_completion_html(0, run_summary)

        assert "By Difficulty" in html
        assert "Medium" in html  # _display_name applies title-case
        assert "60" in html
        assert "Hard" in html
        assert "20" in html

    def test_by_type_table_absent_when_empty(self):
        """by_type table is omitted when dict is empty."""
        manager = self._manager()
        html = manager._build_completion_html(0, {"details": {"by_type": {}}})

        assert "By Type" not in html

    def test_by_difficulty_table_absent_when_empty(self):
        """by_difficulty table is omitted when dict is empty."""
        manager = self._manager()
        html = manager._build_completion_html(0, {"details": {"by_difficulty": {}}})

        assert "By Difficulty" not in html

    def test_error_message_html_escaped_in_html_output(self):
        """html.escape is applied to error_message to prevent XSS."""
        manager = self._manager()
        run_summary = {"details": {"error_message": "<script>alert('xss')</script>"}}
        html = manager._build_completion_html(2, run_summary)

        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_error_message_with_ampersand_is_escaped(self):
        """Ampersands in error_message are HTML-escaped."""
        manager = self._manager()
        run_summary = {"details": {"error_message": "error: foo & bar"}}
        html = manager._build_completion_html(2, run_summary)

        assert "foo & bar" not in html
        assert "foo &amp; bar" in html

    def test_error_section_absent_when_error_message_none(self):
        """No error section rendered when error_message is None."""
        manager = self._manager()
        html = manager._build_completion_html(0, {"details": {"error_message": None}})

        # The CSS class definition is always present; check no error-box div is rendered
        assert '<div class="error-box">' not in html

    def test_error_section_present_when_error_message_set(self):
        """error-box div rendered when error_message is present."""
        manager = self._manager()
        run_summary = {"details": {"error_message": "Something went wrong"}}
        html = manager._build_completion_html(2, run_summary)

        assert "error-box" in html
        assert "Something went wrong" in html

    def test_by_type_display_name_converts_underscores_to_title_case(self):
        """Underscore-separated type keys are rendered with title-case display names."""
        manager = self._manager()
        run_summary = {
            "details": {"by_type": {"verbal_reasoning": 12, "short_term_memory": 7}}
        }
        html = manager._build_completion_html(0, run_summary)

        assert "Verbal Reasoning" in html
        assert "Short Term Memory" in html
        # Raw underscore keys must not appear in rendered table cells
        assert "<td>verbal_reasoning</td>" not in html
        assert "<td>short_term_memory</td>" not in html
