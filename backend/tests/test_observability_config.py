"""Tests for backend-specific observability configuration."""

import os
from pathlib import Path
from unittest import mock

import pytest

from libs.observability.config import load_config


class TestBackendObservabilityConfig:
    """Tests for backend/config/observability.yaml configuration."""

    @pytest.fixture
    def backend_config_path(self) -> str:
        """Return path to backend observability config."""
        return str(Path(__file__).parent.parent / "config" / "observability.yaml")

    def test_config_file_exists(self, backend_config_path: str) -> None:
        """Verify the backend observability config file exists."""
        assert Path(backend_config_path).exists()

    def test_config_loads_successfully(self, backend_config_path: str) -> None:
        """Test that backend config loads and validates successfully."""
        with mock.patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://test@sentry.io/123",
                "ENV": "development",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            },
        ):
            config = load_config(config_path=backend_config_path)

            # Verify backend-specific values
            assert config.otel.service_name == "aiq-backend"
            assert config.sentry.enabled is True
            assert config.otel.enabled is True

    def test_config_routing_values(self, backend_config_path: str) -> None:
        """Test that routing values are correctly configured."""
        with mock.patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://test@sentry.io/123",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            },
        ):
            config = load_config(config_path=backend_config_path)

            # Verify routing as specified in task
            assert config.routing.errors == "sentry"
            assert config.routing.metrics == "otel"
            assert config.routing.traces == "both"

    def test_config_env_substitution(self, backend_config_path: str) -> None:
        """Test that environment variables are substituted correctly."""
        with mock.patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://custom@sentry.io/456",
                "ENV": "production",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "https://otel.example.com:4317",
                "RELEASE": "v1.2.3",
            },
        ):
            config = load_config(config_path=backend_config_path)

            assert config.sentry.dsn == "https://custom@sentry.io/456"
            assert config.sentry.environment == "production"
            assert config.otel.endpoint == "https://otel.example.com:4317"
            assert config.sentry.release == "v1.2.3"

    def test_config_default_environment(self, backend_config_path: str) -> None:
        """Test that environment defaults to 'development' when ENV not set."""
        with mock.patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://test@sentry.io/123",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            },
            clear=True,
        ):
            # Clear ENV if it exists
            os.environ.pop("ENV", None)

            config = load_config(config_path=backend_config_path)

            assert config.sentry.environment == "development"

    def test_config_otel_settings(self, backend_config_path: str) -> None:
        """Test that OTEL settings are correctly configured."""
        with mock.patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://test@sentry.io/123",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            },
        ):
            config = load_config(config_path=backend_config_path)

            assert config.otel.metrics_enabled is True
            assert (
                config.otel.traces_enabled is False
            )  # Traces routed to Sentry, not OTLP
            assert config.otel.prometheus_enabled is True
            assert config.otel.insecure is False

    def test_config_sentry_settings(self, backend_config_path: str) -> None:
        """Test that Sentry settings are correctly configured."""
        with mock.patch.dict(
            os.environ,
            {
                "SENTRY_DSN": "https://test@sentry.io/123",
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://localhost:4317",
            },
        ):
            config = load_config(config_path=backend_config_path)

            assert config.sentry.traces_sample_rate == pytest.approx(0.1)
            assert config.sentry.profiles_sample_rate == pytest.approx(0.0)
            assert config.sentry.send_default_pii is False
