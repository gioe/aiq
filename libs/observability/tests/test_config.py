"""Tests for observability configuration."""

import logging
import os
from pathlib import Path
from unittest import mock

import pytest

from libs.observability.config import (
    ConfigurationError,
    ObservabilityConfig,
    OTELConfig,
    RoutingConfig,
    SentryConfig,
    _process_config_values,
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
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
            clear=True,
        ):
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
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(service_name="my-custom-service")
            assert config.otel.service_name == "my-custom-service"

    def test_environment_override(self) -> None:
        """Test environment parameter overrides config."""
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(environment="production")
            assert config.sentry.environment == "production"

    def test_kwargs_override_sentry(self) -> None:
        """Test sentry_* kwargs override config."""
        config = load_config(sentry_enabled=False)
        assert config.sentry.enabled is False

    def test_kwargs_override_otel(self) -> None:
        """Test otel_* kwargs override config."""
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(otel_endpoint="http://localhost:4317")
            assert config.otel.endpoint == "http://localhost:4317"

    def test_kwargs_override_routing(self) -> None:
        """Test routing_* kwargs override config."""
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
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


class TestConfigValidation:
    """Tests for configuration validation."""

    def test_valid_config_passes_validation(self) -> None:
        """Test that a valid configuration passes validation."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn="https://test@sentry.io/123",
                traces_sample_rate=0.1,
                profiles_sample_rate=0.0,
            ),
            otel=OTELConfig(enabled=True, endpoint="http://localhost:4317"),
            routing=RoutingConfig(errors="sentry", metrics="otel", traces="otel"),
        )
        # Should not raise
        config.validate()

    def test_missing_sentry_dsn_when_enabled_raises_error(self) -> None:
        """Test that missing Sentry DSN when enabled raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn=None),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Sentry DSN is required when sentry.enabled=True" in error_message
        assert "SENTRY_DSN" in error_message

    def test_empty_sentry_dsn_when_enabled_raises_error(self) -> None:
        """Test that empty string Sentry DSN when enabled raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn=""),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        assert "Sentry DSN is required" in str(exc_info.value)

    def test_missing_sentry_dsn_when_disabled_passes(self) -> None:
        """Test that missing Sentry DSN is OK when Sentry is disabled."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=False, dsn=None),
        )
        # Should not raise
        config.validate()

    def test_invalid_traces_sample_rate_too_high_raises_error(self) -> None:
        """Test that traces_sample_rate > 1.0 raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn="https://test@sentry.io/123",
                traces_sample_rate=1.5,
            ),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid sentry.traces_sample_rate: 1.5" in error_message
        assert "must be between 0.0 and 1.0" in error_message

    def test_invalid_traces_sample_rate_negative_raises_error(self) -> None:
        """Test that traces_sample_rate < 0.0 raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn="https://test@sentry.io/123",
                traces_sample_rate=-0.1,
            ),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid sentry.traces_sample_rate: -0.1" in error_message

    def test_invalid_profiles_sample_rate_too_high_raises_error(self) -> None:
        """Test that profiles_sample_rate > 1.0 raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn="https://test@sentry.io/123",
                profiles_sample_rate=2.0,
            ),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid sentry.profiles_sample_rate: 2.0" in error_message
        assert "must be between 0.0 and 1.0" in error_message

    def test_invalid_profiles_sample_rate_negative_raises_error(self) -> None:
        """Test that profiles_sample_rate < 0.0 raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn="https://test@sentry.io/123",
                profiles_sample_rate=-0.5,
            ),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid sentry.profiles_sample_rate: -0.5" in error_message

    def test_valid_sample_rates_at_boundaries(self) -> None:
        """Test that sample rates at 0.0 and 1.0 are valid."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn="https://test@sentry.io/123",
                traces_sample_rate=0.0,
                profiles_sample_rate=1.0,
            ),
        )
        # Should not raise
        config.validate()

    def test_invalid_routing_errors_value_raises_error(self) -> None:
        """Test that invalid routing.errors value raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            routing=RoutingConfig(errors="invalid"),  # type: ignore
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid routing.errors: 'invalid'" in error_message
        assert "both, otel, sentry" in error_message

    def test_invalid_routing_metrics_value_raises_error(self) -> None:
        """Test that invalid routing.metrics value raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            routing=RoutingConfig(metrics="datadog"),  # type: ignore
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid routing.metrics: 'datadog'" in error_message

    def test_invalid_routing_traces_value_raises_error(self) -> None:
        """Test that invalid routing.traces value raises ConfigurationError."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            routing=RoutingConfig(traces="zipkin"),  # type: ignore
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        assert "Invalid routing.traces: 'zipkin'" in error_message

    def test_all_valid_routing_values_pass(self) -> None:
        """Test that all valid routing values pass validation."""
        for routing_value in ["sentry", "otel", "both"]:
            config = ObservabilityConfig(
                sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
                routing=RoutingConfig(
                    errors=routing_value,  # type: ignore
                    metrics=routing_value,  # type: ignore
                    traces=routing_value,  # type: ignore
                ),
            )
            # Should not raise
            config.validate()

    def test_multiple_errors_aggregated_into_one_exception(self) -> None:
        """Test that multiple validation errors are aggregated into a single exception."""
        config = ObservabilityConfig(
            sentry=SentryConfig(
                enabled=True,
                dsn=None,  # Error 1: Missing DSN
                traces_sample_rate=1.5,  # Error 2: Invalid sample rate
                profiles_sample_rate=-0.1,  # Error 3: Invalid sample rate
            ),
            routing=RoutingConfig(
                errors="invalid",  # Error 4: Invalid routing value
                metrics="datadog",  # Error 5: Invalid routing value
            ),
        )
        with pytest.raises(ConfigurationError) as exc_info:
            config.validate()

        error_message = str(exc_info.value)
        # Check that all errors are present
        assert "Sentry DSN is required" in error_message
        assert "Invalid sentry.traces_sample_rate: 1.5" in error_message
        assert "Invalid sentry.profiles_sample_rate: -0.1" in error_message
        assert "Invalid routing.errors: 'invalid'" in error_message
        assert "Invalid routing.metrics: 'datadog'" in error_message
        # Check that errors are listed with bullets
        assert "Configuration validation failed:" in error_message
        assert error_message.count("  - ") == 5

    def test_missing_otel_endpoint_when_otel_routing_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that missing OTEL endpoint when routing to OTEL logs a warning."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            otel=OTELConfig(enabled=True, endpoint=None),
            routing=RoutingConfig(errors="otel"),
        )

        with caplog.at_level(logging.WARNING):
            config.validate()

        # Should log warning but not raise
        assert len(caplog.records) == 1
        assert "OTEL endpoint is not configured" in caplog.text
        assert "routing includes 'otel'" in caplog.text
        assert "OTEL_ENDPOINT" in caplog.text

    def test_missing_otel_endpoint_when_routing_both_logs_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that missing OTEL endpoint when routing to 'both' logs a warning."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            otel=OTELConfig(enabled=True, endpoint=None),
            routing=RoutingConfig(traces="both"),
        )

        with caplog.at_level(logging.WARNING):
            config.validate()

        assert "OTEL endpoint is not configured" in caplog.text

    def test_missing_otel_endpoint_when_only_sentry_routing_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that missing OTEL endpoint doesn't warn when routing only to Sentry."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            otel=OTELConfig(enabled=True, endpoint=None),
            routing=RoutingConfig(errors="sentry", metrics="sentry", traces="sentry"),
        )

        with caplog.at_level(logging.WARNING):
            config.validate()

        assert len(caplog.records) == 0

    def test_missing_otel_endpoint_when_otel_disabled_no_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that missing OTEL endpoint doesn't warn when OTEL is disabled."""
        config = ObservabilityConfig(
            sentry=SentryConfig(enabled=True, dsn="https://test@sentry.io/123"),
            otel=OTELConfig(enabled=False, endpoint=None),
            routing=RoutingConfig(errors="otel"),
        )

        with caplog.at_level(logging.WARNING):
            config.validate()

        assert len(caplog.records) == 0

    def test_load_config_calls_validate(self) -> None:
        """Test that load_config() calls validate() on the returned config."""
        with mock.patch.dict(os.environ, {"SENTRY_DSN": ""}):
            # This should raise because Sentry is enabled by default with empty DSN
            with pytest.raises(ConfigurationError) as exc_info:
                load_config()

            assert "Sentry DSN is required" in str(exc_info.value)

    def test_load_config_with_valid_env_vars_passes_validation(self) -> None:
        """Test that load_config() with valid env vars passes validation."""
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config()
            # Should not raise and should have the DSN set
            assert config.sentry.dsn == "https://test@sentry.io/123"

    def test_load_config_with_sentry_disabled_passes_validation(self) -> None:
        """Test that load_config() with Sentry disabled doesn't require DSN."""
        with mock.patch.dict(os.environ, {}, clear=True):
            config = load_config(sentry_enabled=False)
            # Should not raise even without DSN
            assert config.sentry.enabled is False

    def test_load_config_with_invalid_override_raises_error(self) -> None:
        """Test that load_config() with invalid override raises ConfigurationError."""
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            with pytest.raises(ConfigurationError) as exc_info:
                load_config(sentry_traces_sample_rate=2.0)

            assert "Invalid sentry.traces_sample_rate: 2.0" in str(exc_info.value)


class TestProcessConfigValues:
    """Tests for _process_config_values helper."""

    def test_list_with_env_var_strings(self) -> None:
        """Test list values with environment variable substitution."""
        with mock.patch.dict(os.environ, {"LIST_VAR": "substituted"}):
            config = {"items": ["${LIST_VAR}", "plain"]}
            result = _process_config_values(config)
            assert result["items"] == ["substituted", "plain"]

    def test_list_with_non_string_items(self) -> None:
        """Test list values with non-string items pass through unchanged."""
        config = {"numbers": [1, 2, 3], "mixed": ["string", 42, True]}
        result = _process_config_values(config)
        assert result["numbers"] == [1, 2, 3]
        assert result["mixed"] == ["string", 42, True]


class TestYAMLLoading:
    """Tests for YAML file loading."""

    def test_load_yaml_import_error(self) -> None:
        """Test ImportError raised when PyYAML is not installed."""
        import sys

        # Save the original yaml module reference
        yaml_module = sys.modules.get("yaml")

        try:
            # Remove yaml from sys.modules to simulate it not being installed
            sys.modules["yaml"] = None  # type: ignore

            # Reload the config module to trigger the import
            import importlib

            import libs.observability.config as config_module

            # We need to call the function directly and have it try to import yaml
            # Since the import happens inside the function, we mock the builtins
            with mock.patch.dict(sys.modules, {"yaml": None}):
                with pytest.raises(ImportError) as exc_info:
                    config_module._load_yaml(Path("/nonexistent/path.yaml"))

                assert "PyYAML is required" in str(exc_info.value)
        finally:
            # Restore the original yaml module
            if yaml_module is not None:
                sys.modules["yaml"] = yaml_module
            elif "yaml" in sys.modules:
                del sys.modules["yaml"]


class TestConfigFileMerging:
    """Tests for configuration file merging."""

    def test_load_config_with_custom_yaml_file(self, tmp_path: Path) -> None:
        """Test loading config from a custom YAML file merges with defaults."""
        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(
            """
sentry:
  traces_sample_rate: 0.5
  environment: staging
otel:
  service_name: custom-service
"""
        )

        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(config_path=str(custom_config))

            # Custom values should override defaults
            assert config.sentry.traces_sample_rate == 0.5
            assert config.sentry.environment == "staging"
            assert config.otel.service_name == "custom-service"

            # Default values should be preserved
            assert config.sentry.enabled is True
            assert config.otel.metrics_enabled is True

    def test_load_config_with_nonexistent_file(self) -> None:
        """Test loading config with nonexistent file uses defaults only."""
        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(config_path="/nonexistent/path/config.yaml")

            # Should still work with default config
            assert config.sentry.enabled is True
            assert config.otel.enabled is True

    def test_load_config_merges_nested_dict_values(self, tmp_path: Path) -> None:
        """Test that nested dict values are properly merged (not replaced)."""
        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(
            """
sentry:
  traces_sample_rate: 0.8
routing:
  traces: both
"""
        )

        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(config_path=str(custom_config))

            # Custom values
            assert config.sentry.traces_sample_rate == 0.8
            assert config.routing.traces == "both"

            # Default routing values should be preserved (from default.yaml merge)
            assert config.routing.errors == "sentry"
            assert config.routing.metrics == "otel"

    def test_load_config_custom_file_overwrites_top_level(self, tmp_path: Path) -> None:
        """Test that non-dict top-level values are overwritten, not merged."""
        custom_config = tmp_path / "custom.yaml"
        custom_config.write_text(
            """
custom_key: custom_value
"""
        )

        with mock.patch.dict(
            os.environ,
            {"SENTRY_DSN": "https://test@sentry.io/123"},
        ):
            config = load_config(config_path=str(custom_config))

            # Config should still be valid
            assert config.sentry.enabled is True
