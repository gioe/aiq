"""Tests for alerting module including inventory alerting."""

import os
import tempfile
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

import pytest

from app.alerting import (
    AlertManager,
    AlertingConfig,
    InventoryAlertManager,
    InventoryAlertResult,
    StratumAlert,
)
from app.error_classifier import ClassifiedError, ErrorCategory, ErrorSeverity
from app.models import DifficultyLevel, QuestionType


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
                category=ErrorCategory.BILLING_QUOTA,
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
            category=ErrorCategory.BILLING_QUOTA,
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
                category=ErrorCategory.BILLING_QUOTA,
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
        assert config.per_stratum_cooldown_minutes == 60
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
    per_stratum_minutes: 120
    global_minutes: 30
    max_alerts_per_hour: 5
"""
            with open(config_file, "w") as f:
                f.write(yaml_content)

            config = AlertingConfig.from_yaml(config_file)

            assert config.healthy_min == 100
            assert config.warning_min == 30
            assert config.critical_min == 10
            assert config.per_stratum_cooldown_minutes == 120
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


class TestStratumAlert:
    """Tests for StratumAlert dataclass."""

    def test_creation(self):
        """Test creating a StratumAlert."""
        alert = StratumAlert(
            question_type="math",
            difficulty="easy",
            current_count=3,
            threshold=5,
            severity=ErrorSeverity.CRITICAL,
        )

        assert alert.question_type == "math"
        assert alert.difficulty == "easy"
        assert alert.current_count == 3
        assert alert.threshold == 5
        assert alert.severity == ErrorSeverity.CRITICAL


class TestInventoryAlertResult:
    """Tests for InventoryAlertResult dataclass."""

    def test_default_values(self):
        """Test default result values."""
        result = InventoryAlertResult()

        assert result.alerts_sent == 0
        assert result.alerts_suppressed == 0
        assert result.strata_checked == 0
        assert result.critical_strata == []
        assert result.warning_strata == []
        assert result.healthy_strata == 0


class TestInventoryAlertManager:
    """Tests for InventoryAlertManager class."""

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
            per_stratum_cooldown_minutes=60,
            global_cooldown_minutes=15,
            max_alerts_per_hour=10,
        )

    @pytest.fixture
    def mock_stratum(self):
        """Factory for creating mock strata."""

        def _create_stratum(
            q_type: QuestionType, difficulty: DifficultyLevel, count: int
        ):
            stratum = Mock()
            stratum.question_type = q_type
            stratum.difficulty = difficulty
            stratum.current_count = count
            return stratum

        return _create_stratum

    def test_initialization(self, mock_alert_manager, default_config):
        """Test InventoryAlertManager initialization."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        assert manager.config.critical_min == 5
        assert manager.config.warning_min == 20

    def test_check_and_alert_healthy_inventory(
        self, mock_alert_manager, default_config, mock_stratum
    ):
        """Test that no alerts are sent for healthy inventory."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        strata = [
            mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 60),
            mock_stratum(QuestionType.MATH, DifficultyLevel.MEDIUM, 55),
            mock_stratum(QuestionType.MATH, DifficultyLevel.HARD, 70),
        ]

        result = manager.check_and_alert(strata)

        assert result.alerts_sent == 0
        assert result.healthy_strata == 3
        assert len(result.critical_strata) == 0
        assert len(result.warning_strata) == 0
        mock_alert_manager.send_alert.assert_not_called()

    def test_check_and_alert_critical_strata(
        self, mock_alert_manager, default_config, mock_stratum
    ):
        """Test alerts are sent for critical strata."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        strata = [
            mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 2),  # Critical
            mock_stratum(QuestionType.MATH, DifficultyLevel.MEDIUM, 3),  # Critical
            mock_stratum(QuestionType.MATH, DifficultyLevel.HARD, 60),  # Healthy
        ]

        result = manager.check_and_alert(strata)

        assert result.alerts_sent == 2
        assert len(result.critical_strata) == 2
        assert result.healthy_strata == 1
        mock_alert_manager.send_alert.assert_called()

    def test_check_and_alert_warning_strata(
        self, mock_alert_manager, default_config, mock_stratum
    ):
        """Test alerts are sent for warning strata."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        strata = [
            mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 15),  # Warning
            mock_stratum(QuestionType.MATH, DifficultyLevel.MEDIUM, 10),  # Warning
            mock_stratum(QuestionType.MATH, DifficultyLevel.HARD, 60),  # Healthy
        ]

        result = manager.check_and_alert(strata)

        assert result.alerts_sent == 2
        assert len(result.warning_strata) == 2
        mock_alert_manager.send_alert.assert_called()

    def test_per_stratum_cooldown(
        self, mock_alert_manager, default_config, mock_stratum
    ):
        """Test that per-stratum cooldown prevents repeated alerts."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        strata = [mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 2)]

        # First check should send alert
        result1 = manager.check_and_alert(strata)
        assert result1.alerts_sent == 1

        # Second check should be suppressed by cooldown
        result2 = manager.check_and_alert(strata)
        assert result2.alerts_sent == 0
        assert result2.alerts_suppressed == 1

    def test_global_cooldown(self, mock_alert_manager, default_config, mock_stratum):
        """Test that global cooldown prevents back-to-back alerts."""
        config = AlertingConfig(
            critical_min=5,
            warning_min=20,
            healthy_min=50,
            per_stratum_cooldown_minutes=1,  # Very short per-stratum cooldown
            global_cooldown_minutes=60,  # Longer global cooldown
            max_alerts_per_hour=100,
        )

        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=config,
        )

        # First alert for math/easy
        strata1 = [mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 2)]
        result1 = manager.check_and_alert(strata1)
        assert result1.alerts_sent == 1

        # Second alert for different stratum should be blocked by global cooldown
        strata2 = [mock_stratum(QuestionType.LOGIC, DifficultyLevel.HARD, 3)]
        result2 = manager.check_and_alert(strata2)
        assert result2.alerts_sent == 0
        assert result2.alerts_suppressed == 1

    def test_hourly_rate_limit(self, mock_alert_manager, mock_stratum):
        """Test that hourly rate limit is enforced."""
        config = AlertingConfig(
            critical_min=5,
            warning_min=20,
            healthy_min=50,
            per_stratum_cooldown_minutes=0,  # Disable per-stratum cooldown
            global_cooldown_minutes=0,  # Disable global cooldown
            max_alerts_per_hour=2,  # Very low limit for testing
        )

        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=config,
        )

        # Manually add alert timestamps to simulate hitting the limit
        now = datetime.now(timezone.utc)
        manager._alerts_this_hour = [
            now - timedelta(minutes=30),
            now - timedelta(minutes=15),
        ]

        strata = [mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 2)]
        result = manager.check_and_alert(strata)

        assert result.alerts_sent == 0
        assert result.alerts_suppressed == 1

    def test_build_inventory_error_critical(self, mock_alert_manager, default_config):
        """Test building ClassifiedError for critical inventory."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        strata = [
            StratumAlert(
                question_type="math",
                difficulty="easy",
                current_count=2,
                threshold=5,
                severity=ErrorSeverity.CRITICAL,
            ),
            StratumAlert(
                question_type="logic",
                difficulty="hard",
                current_count=1,
                threshold=5,
                severity=ErrorSeverity.CRITICAL,
            ),
        ]

        error = manager._build_inventory_error(strata, ErrorSeverity.CRITICAL)

        assert error.category == ErrorCategory.INVENTORY_LOW
        assert error.severity == ErrorSeverity.CRITICAL
        assert error.provider == "inventory"
        assert "2 question strata" in error.message
        assert "critical" in error.message

    def test_build_inventory_context(self, mock_alert_manager, default_config):
        """Test building context string for inventory alerts."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        strata = [
            StratumAlert("math", "easy", 2, 5, ErrorSeverity.CRITICAL),
            StratumAlert("logic", "hard", 1, 5, ErrorSeverity.CRITICAL),
        ]

        context = manager._build_inventory_context(strata)

        assert "Affected strata:" in context
        assert "math/easy: 2 questions" in context
        assert "logic/hard: 1 questions" in context
        assert "Recommended Actions:" in context
        assert "--auto-balance" in context

    def test_get_cooldown_status(
        self, mock_alert_manager, default_config, mock_stratum
    ):
        """Test getting cooldown status."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        # Send an alert to trigger cooldowns
        strata = [mock_stratum(QuestionType.MATH, DifficultyLevel.EASY, 2)]
        manager.check_and_alert(strata)

        status = manager.get_cooldown_status()

        assert "global_cooldown_active" in status
        assert "alerts_this_hour" in status
        assert "active_stratum_cooldowns" in status
        assert status["alerts_this_hour"] >= 1

    def test_is_in_cooldown(self, mock_alert_manager, default_config):
        """Test cooldown checking logic."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        key = ("math", "easy")
        now = datetime.now(timezone.utc)

        # No cooldown initially
        assert manager._is_in_cooldown(key, now) is False

        # Set last alert time
        manager._stratum_last_alert[key] = now - timedelta(minutes=30)

        # Should still be in cooldown (60 min default)
        assert manager._is_in_cooldown(key, now) is True

        # After cooldown expires
        manager._stratum_last_alert[key] = now - timedelta(minutes=61)
        assert manager._is_in_cooldown(key, now) is False

    def test_check_hourly_rate_limit_removes_old_alerts(
        self, mock_alert_manager, default_config
    ):
        """Test that old alerts are removed from hourly tracking."""
        manager = InventoryAlertManager(
            alert_manager=mock_alert_manager,
            config=default_config,
        )

        now = datetime.now(timezone.utc)

        # Add some old and recent alerts
        manager._alerts_this_hour = [
            now - timedelta(hours=2),  # Should be removed
            now - timedelta(minutes=90),  # Should be removed
            now - timedelta(minutes=30),  # Should be kept
        ]

        can_alert = manager._check_hourly_rate_limit(now)

        assert can_alert is True
        assert len(manager._alerts_this_hour) == 1  # Only recent one kept


class TestInventoryAlertingIntegration:
    """Integration tests for inventory alerting."""

    def test_full_alerting_flow(self):
        """Test complete alerting flow from strata to alert."""
        with tempfile.TemporaryDirectory() as tmpdir:
            alert_file = os.path.join(tmpdir, "alerts.log")
            inventory_alert_file = os.path.join(tmpdir, "inventory_alerts.log")

            # Create real AlertManager
            alert_manager = AlertManager(
                email_enabled=False,
                alert_file_path=alert_file,
            )

            # Create config with inventory file
            config = AlertingConfig(
                critical_min=5,
                warning_min=20,
                healthy_min=50,
                inventory_alert_file=inventory_alert_file,
            )

            # Create InventoryAlertManager
            inventory_alerter = InventoryAlertManager(
                alert_manager=alert_manager,
                config=config,
            )

            # Create mock strata
            strata = []
            for q_type in [QuestionType.MATH, QuestionType.LOGIC]:
                for difficulty in DifficultyLevel:
                    stratum = Mock()
                    stratum.question_type = q_type
                    stratum.difficulty = difficulty
                    # Make some strata critical
                    if (
                        q_type == QuestionType.MATH
                        and difficulty == DifficultyLevel.EASY
                    ):
                        stratum.current_count = 2
                    else:
                        stratum.current_count = 60
                    strata.append(stratum)

            # Run check
            result = inventory_alerter.check_and_alert(strata)

            # Verify results
            assert result.alerts_sent >= 1
            assert len(result.critical_strata) >= 1

            # Verify files were written
            assert os.path.exists(alert_file)
            assert os.path.exists(inventory_alert_file)

            with open(alert_file) as f:
                content = f.read()
                assert "INVENTORY_LOW" in content

            with open(inventory_alert_file) as f:
                content = f.read()
                assert "CRITICAL" in content
                assert "math/easy" in content
