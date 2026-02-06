"""Tests for observability configuration."""

import os
from pathlib import Path
from unittest import mock

import pytest

from libs.observability.config import (
    ObservabilityConfig,
    OTELConfig,
    RoutingConfig,
    SentryConfig,
    _substitute_env_vars,
    load_config,
)


class TestEnvVarSubstitution:
    """Tests for environment variable substitution."""

    def test_simple_substitution(self) -> None:
        """Test simple ${VAR} substitution."""
        with mock.patch.dict(os.environ, {"TEST_VAR": "test_value"}):
            result = _substitute_env_vars("prefix-${TEST_VAR}-suffix")
            assert result == "prefix-test_value-suffix"

    def test_missing_var_returns_empty(self) -> None:
        """Test missing variable returns empty string."""
        with mock.patch.dict(os.environ, {}, clear=True):
            # Ensure the var is not set
            os.environ.pop("MISSING_VAR", None)
            result = _substitute_env_vars("${MISSING_VAR}")
            assert result == ""

    def test_default_value_when_missing(self) -> None:
        """Test ${VAR:default} returns default when var not set."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MISSING_VAR", None)
            result = _substitute_env_vars("${MISSING_VAR:default_value}")
            assert result == "default_value"

    def test_default_value_ignored_when_set(self) -> None:
        """Test ${VAR:default} uses env var when set."""
        with mock.patch.dict(os.environ, {"SET_VAR": "actual_value"}):
            result = _substitute_env_vars("${SET_VAR:default_value}")
            assert result == "actual_value"

    def test_multiple_substitutions(self) -> None:
        """Test multiple variables in one string."""
        with mock.patch.dict(os.environ, {"VAR1": "one", "VAR2": "two"}):
            result = _substitute_env_vars("${VAR1}-${VAR2}")
            assert result == "one-two"

    def test_no_substitution_needed(self) -> None:
        """Test string without env vars passes through unchanged."""
        result = _substitute_env_vars("plain string")
        assert result == "plain string"

    def test_empty_default_value(self) -> None:
        """Test ${VAR:} with empty default."""
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("MISSING_VAR", None)
            result = _substitute_env_vars("${MISSING_VAR:}")
            assert result == ""


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_default_config_values(self) -> None:
        """Test default configuration values are applied."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = load_config()

            # Sentry defaults
            assert config.sentry.enabled is True
            assert config.sentry.traces_sample_rate == 0.1
            assert config.sentry.send_default_pii is False

            # OTEL defaults
            assert config.otel.enabled is True
            assert config.otel.metrics_enabled is True
            assert config.otel.traces_enabled is True
            assert config.otel.insecure is False

            # Routing defaults
            assert config.routing.errors == "sentry"
            assert config.routing.metrics == "otel"
            assert config.routing.traces == "otel"

    def test_service_name_override(self) -> None:
        """Test service_name parameter overrides config."""
        config = load_config(service_name="my-custom-service")
        assert config.otel.service_name == "my-custom-service"

    def test_environment_override(self) -> None:
        """Test environment parameter overrides config."""
        config = load_config(environment="production")
        assert config.sentry.environment == "production"

    def test_kwargs_override_sentry(self) -> None:
        """Test sentry_* kwargs override config."""
        config = load_config(sentry_enabled=False)
        assert config.sentry.enabled is False

    def test_kwargs_override_otel(self) -> None:
        """Test otel_* kwargs override config."""
        config = load_config(otel_endpoint="http://localhost:4317")
        assert config.otel.endpoint == "http://localhost:4317"

    def test_kwargs_override_routing(self) -> None:
        """Test routing_* kwargs override config."""
        config = load_config(routing_traces="both")
        assert config.routing.traces == "both"

    def test_env_var_in_config(self) -> None:
        """Test environment variables are substituted in config."""
        with mock.patch.dict(os.environ, {"SENTRY_DSN": "https://test@sentry.io/123"}):
            config = load_config()
            assert config.sentry.dsn == "https://test@sentry.io/123"


class TestDataclassDefaults:
    """Tests for configuration dataclass defaults."""

    def test_sentry_config_defaults(self) -> None:
        """Test SentryConfig default values."""
        config = SentryConfig()
        assert config.enabled is True
        assert config.dsn is None
        assert config.environment == "development"
        assert config.release is None
        assert config.traces_sample_rate == 0.1
        assert config.profiles_sample_rate == 0.0
        assert config.send_default_pii is False

    def test_otel_config_defaults(self) -> None:
        """Test OTELConfig default values."""
        config = OTELConfig()
        assert config.enabled is True
        assert config.service_name == "unknown-service"
        assert config.endpoint is None
        assert config.metrics_enabled is True
        assert config.traces_enabled is True
        assert config.prometheus_enabled is True
        assert config.insecure is False

    def test_routing_config_defaults(self) -> None:
        """Test RoutingConfig default values."""
        config = RoutingConfig()
        assert config.errors == "sentry"
        assert config.metrics == "otel"
        assert config.traces == "otel"

    def test_observability_config_defaults(self) -> None:
        """Test ObservabilityConfig creates nested defaults."""
        config = ObservabilityConfig()
        assert isinstance(config.sentry, SentryConfig)
        assert isinstance(config.otel, OTELConfig)
        assert isinstance(config.routing, RoutingConfig)
