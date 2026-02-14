"""Tests for configuration settings."""

import os

import pytest
from unittest.mock import patch

from app.config.config import Settings


class TestDedupConfig:
    """Tests for deduplication configuration settings."""

    def test_default_dedup_similarity_threshold(self):
        """Test default similarity threshold value."""
        settings = Settings()
        assert settings.dedup_similarity_threshold == pytest.approx(0.98)

    def test_default_dedup_embedding_model(self):
        """Test default embedding model value."""
        settings = Settings()
        assert settings.dedup_embedding_model == "text-embedding-3-small"

    def test_custom_dedup_similarity_threshold_from_env(self):
        """Test loading custom similarity threshold from environment."""
        with patch.dict(
            "os.environ", {"DEDUP_SIMILARITY_THRESHOLD": "0.90"}, clear=False
        ):
            settings = Settings()
            assert settings.dedup_similarity_threshold == pytest.approx(0.90)

    def test_custom_dedup_embedding_model_from_env(self):
        """Test loading custom embedding model from environment."""
        with patch.dict(
            "os.environ",
            {"DEDUP_EMBEDDING_MODEL": "text-embedding-ada-002"},
            clear=False,
        ):
            settings = Settings()
            assert settings.dedup_embedding_model == "text-embedding-ada-002"

    def test_similarity_threshold_boundary_zero(self):
        """Test similarity threshold at boundary value 0.0."""
        with patch.dict(
            "os.environ", {"DEDUP_SIMILARITY_THRESHOLD": "0.0"}, clear=False
        ):
            settings = Settings()
            assert settings.dedup_similarity_threshold == pytest.approx(0.0)

    def test_similarity_threshold_boundary_one(self):
        """Test similarity threshold at boundary value 1.0."""
        with patch.dict(
            "os.environ", {"DEDUP_SIMILARITY_THRESHOLD": "1.0"}, clear=False
        ):
            settings = Settings()
            assert settings.dedup_similarity_threshold == pytest.approx(1.0)


class TestCircuitBreakerConfig:
    """Tests for circuit breaker configuration settings."""

    def test_default_circuit_breaker_enabled(self):
        """Test default circuit breaker enabled value."""
        settings = Settings()
        assert settings.circuit_breaker_enabled is True

    def test_default_circuit_breaker_failure_threshold(self):
        """Test default failure threshold value."""
        settings = Settings()
        assert settings.circuit_breaker_failure_threshold == 5

    def test_default_circuit_breaker_error_rate_threshold(self):
        """Test default error rate threshold value."""
        settings = Settings()
        assert settings.circuit_breaker_error_rate_threshold == pytest.approx(0.5)

    def test_default_circuit_breaker_recovery_timeout(self):
        """Test default recovery timeout value."""
        settings = Settings()
        assert settings.circuit_breaker_recovery_timeout == pytest.approx(60.0)

    def test_default_circuit_breaker_success_threshold(self):
        """Test default success threshold value."""
        settings = Settings()
        assert settings.circuit_breaker_success_threshold == 2

    def test_default_circuit_breaker_window_size(self):
        """Test default window size value."""
        settings = Settings()
        assert settings.circuit_breaker_window_size == 10

    def test_custom_circuit_breaker_failure_threshold_from_env(self):
        """Test loading custom failure threshold from environment."""
        with patch.dict(
            "os.environ", {"CIRCUIT_BREAKER_FAILURE_THRESHOLD": "10"}, clear=False
        ):
            settings = Settings()
            assert settings.circuit_breaker_failure_threshold == 10

    def test_custom_circuit_breaker_recovery_timeout_from_env(self):
        """Test loading custom recovery timeout from environment."""
        with patch.dict(
            "os.environ", {"CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "120.0"}, clear=False
        ):
            settings = Settings()
            assert settings.circuit_breaker_recovery_timeout == pytest.approx(120.0)

    def test_circuit_breaker_disabled_from_env(self):
        """Test disabling circuit breaker from environment."""
        with patch.dict(
            "os.environ", {"CIRCUIT_BREAKER_ENABLED": "false"}, clear=False
        ):
            settings = Settings()
            assert settings.circuit_breaker_enabled is False


class TestPrometheusConfig:
    """Tests for Prometheus metrics configuration settings."""

    def test_default_enable_prometheus_metrics(self):
        """Test default prometheus metrics enabled value."""
        settings = Settings()
        assert settings.enable_prometheus_metrics is True

    def test_prometheus_metrics_disabled_from_env(self):
        """Test disabling prometheus metrics from environment."""
        with patch.dict(
            "os.environ", {"ENABLE_PROMETHEUS_METRICS": "false"}, clear=False
        ):
            settings = Settings()
            assert settings.enable_prometheus_metrics is False


class TestSecretsIntegration:
    """Tests for secrets management integration in config."""

    def test_llm_api_keys_loaded_from_secrets(self):
        """Test that LLM API keys are loaded through secrets backend."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test-openai",
            "ANTHROPIC_API_KEY": "sk-test-anthropic",
            "GOOGLE_API_KEY": "test-google",
            "XAI_API_KEY": "test-xai",
        }
        with patch.dict("os.environ", env_vars, clear=False):
            settings = Settings()
            assert settings.openai_api_key == "sk-test-openai"
            assert settings.anthropic_api_key == "sk-test-anthropic"
            assert settings.google_api_key == "test-google"
            assert settings.xai_api_key == "test-xai"

    def test_at_least_one_llm_key_required(self):
        """Test that at least one LLM API key must be configured."""
        # Remove all LLM keys by setting them to empty strings
        env_vars = {
            "DATABASE_URL": "postgresql://test",
            "ENV": "test",
            "OPENAI_API_KEY": "",
            "ANTHROPIC_API_KEY": "",
            "GOOGLE_API_KEY": "",
            "XAI_API_KEY": "",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            with pytest.raises(ValueError) as exc_info:
                Settings()
            # Check the error message contains the expected text
            error_msg = str(exc_info.value).lower()
            assert "at least one" in error_msg
            assert "api key" in error_msg

    def test_smtp_password_loaded_from_secrets(self):
        """Test that SMTP password is loaded through secrets backend."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test",  # Need at least one LLM key
            "SMTP_PASSWORD": "secret-smtp-password",
        }
        with patch.dict("os.environ", env_vars, clear=False):
            settings = Settings()
            assert settings.smtp_password == "secret-smtp-password"

    def test_backend_service_key_loaded_from_secrets(self):
        """Test that backend service key is loaded through secrets backend."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test",  # Need at least one LLM key
            "BACKEND_SERVICE_KEY": "secret-service-key",
        }
        with patch.dict("os.environ", env_vars, clear=False):
            settings = Settings()
            assert settings.backend_service_key == "secret-service-key"

    def test_email_alerts_validation_with_missing_smtp_password(self):
        """Test that enabling email alerts without SMTP password fails."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test",
            "ENABLE_EMAIL_ALERTS": "true",
            "SMTP_USERNAME": "user@example.com",
            "ALERT_TO_EMAILS": "admin@example.com",
            "ENV": "production",  # Validation only in non-dev
        }
        with patch.dict("os.environ", env_vars, clear=False):
            os.environ.pop("SMTP_PASSWORD", None)
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert "SMTP_PASSWORD" in str(exc_info.value)

    def test_run_reporting_validation_skipped_in_development(self):
        """Test that run reporting validation is skipped in development."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test",
            "ENABLE_RUN_REPORTING": "true",
            "ENV": "development",
            # Note: No BACKEND_SERVICE_KEY or BACKEND_API_URL
        }
        with patch.dict("os.environ", env_vars, clear=False):
            os.environ.pop("BACKEND_SERVICE_KEY", None)
            os.environ.pop("BACKEND_API_URL", None)
            # Should not raise in development
            settings = Settings()
            assert settings.enable_run_reporting is True
            assert settings.env == "development"

    def test_run_reporting_validation_enforced_in_production(self):
        """Test that run reporting validation is enforced in production."""
        env_vars = {
            "OPENAI_API_KEY": "sk-test",
            "ENABLE_RUN_REPORTING": "true",
            "ENV": "production",
            # Note: No BACKEND_SERVICE_KEY
        }
        with patch.dict("os.environ", env_vars, clear=False):
            os.environ.pop("BACKEND_SERVICE_KEY", None)
            with pytest.raises(ValueError) as exc_info:
                Settings()
            assert "BACKEND_SERVICE_KEY" in str(exc_info.value)
