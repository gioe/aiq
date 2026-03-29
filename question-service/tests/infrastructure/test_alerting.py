"""Tests for alerting module including inventory alerting."""

import os
import tempfile
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from gioe_libs.alerting.alerting import (
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

        assert manager.alerts_sent == []

    def test_send_alert_to_file(self):
        """Test alert is written to file when configured."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")

            manager = AlertManager(
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
        assert "Review resource inventory levels and replenish as needed" in message

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
        assert "Re-run individual failed components if applicable" in message

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

    def test_noop_when_no_discord(self):
        """send_notification is a no-op when no Discord URL is configured."""
        import requests
        from unittest.mock import patch

        manager = AlertManager()
        assert manager.discord_webhook_url is None
        with patch.object(requests, "post") as mock_post:
            manager.send_notification(
                title="Run Complete",
                fields=[("Generated", 10), ("Inserted", 8)],
                severity="info",
            )
            mock_post.assert_not_called()


class TestResourceMonitorAlertingIntegration:
    """Integration tests for ResourceMonitor-based inventory alerting."""

    def test_full_alerting_flow(self):
        """Test complete alerting flow from strata to alert via ResourceMonitor."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            resource_alert_file = os.path.join(tmpdir, "resource_alerts.log")

            # Create real AlertManager
            alert_manager = AlertManager(
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
