"""Configuration management for observability.

Supports YAML configuration files with environment variable substitution.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when observability configuration is invalid."""

    pass


@dataclass
class SentryConfig:
    """Configuration for Sentry backend."""

    enabled: bool = True
    dsn: str | None = None
    environment: str = "development"
    release: str | None = None
    traces_sample_rate: float = 0.1
    profiles_sample_rate: float = 0.0
    send_default_pii: bool = False


@dataclass
class OTELConfig:
    """Configuration for OpenTelemetry backend."""

    enabled: bool = True
    service_name: str = "unknown-service"
    service_version: str | None = None
    endpoint: str | None = None
    exporter: Literal["console", "otlp", "none"] = "otlp"
    otlp_headers: str = ""  # Format: "key1=value1,key2=value2" (e.g., Grafana Cloud auth)
    metrics_enabled: bool = True
    metrics_export_interval_millis: int = 60000  # 60 seconds
    traces_enabled: bool = True
    traces_sample_rate: float = 1.0  # 1.0 = 100% sampling, 0.1 = 10% sampling
    logs_enabled: bool = False
    prometheus_enabled: bool = True
    insecure: bool = False  # Set to True only for local development without TLS


@dataclass
class RoutingConfig:
    """Configuration for signal routing."""

    errors: Literal["sentry", "otel", "both"] = "sentry"
    metrics: Literal["sentry", "otel", "both"] = "otel"
    traces: Literal["sentry", "otel", "both"] = "otel"


@dataclass
class ObservabilityConfig:
    """Root configuration for observability."""

    sentry: SentryConfig = field(default_factory=SentryConfig)
    otel: OTELConfig = field(default_factory=OTELConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)

    def validate(self) -> None:
        """Validate the configuration.

        Validates that:
        - When sentry.enabled=True, sentry.dsn is set (non-empty)
        - When otel.enabled=True and routing uses "otel", otel.endpoint should be set (warning)
        - traces_sample_rate is between 0.0 and 1.0
        - profiles_sample_rate is between 0.0 and 1.0
        - routing values are one of: "sentry", "otel", "both"

        Raises:
            ConfigurationError: If any validation errors are found.
        """
        errors: list[str] = []

        # Validate Sentry DSN when enabled
        if self.sentry.enabled and not self.sentry.dsn:
            errors.append(
                "Sentry DSN is required when sentry.enabled=True. "
                "Set SENTRY_DSN environment variable or configure sentry.dsn in your config."
            )

        # Validate sample rates
        if not (0.0 <= self.sentry.traces_sample_rate <= 1.0):
            errors.append(
                f"Invalid sentry.traces_sample_rate: {self.sentry.traces_sample_rate}. "
                "Value must be between 0.0 and 1.0."
            )

        if not (0.0 <= self.sentry.profiles_sample_rate <= 1.0):
            errors.append(
                f"Invalid sentry.profiles_sample_rate: {self.sentry.profiles_sample_rate}. "
                "Value must be between 0.0 and 1.0."
            )

        # Validate routing values
        valid_routing_values = {"sentry", "otel", "both"}
        if self.routing.errors not in valid_routing_values:
            errors.append(
                f"Invalid routing.errors: '{self.routing.errors}'. "
                f"Value must be one of: {', '.join(sorted(valid_routing_values))}."
            )

        if self.routing.metrics not in valid_routing_values:
            errors.append(
                f"Invalid routing.metrics: '{self.routing.metrics}'. "
                f"Value must be one of: {', '.join(sorted(valid_routing_values))}."
            )

        if self.routing.traces not in valid_routing_values:
            errors.append(
                f"Invalid routing.traces: '{self.routing.traces}'. "
                f"Value must be one of: {', '.join(sorted(valid_routing_values))}."
            )

        # Validate OTEL sample rate
        if not (0.0 <= self.otel.traces_sample_rate <= 1.0):
            errors.append(
                f"Invalid otel.traces_sample_rate: {self.otel.traces_sample_rate}. "
                "Value must be between 0.0 and 1.0."
            )

        # Validate OTEL exporter value
        valid_exporters = {"console", "otlp", "none"}
        if self.otel.exporter not in valid_exporters:
            errors.append(
                f"Invalid otel.exporter: '{self.otel.exporter}'. "
                f"Value must be one of: {', '.join(sorted(valid_exporters))}."
            )

        # Validate metrics export interval
        if self.otel.metrics_export_interval_millis <= 0:
            errors.append(
                f"Invalid otel.metrics_export_interval_millis: {self.otel.metrics_export_interval_millis}. "
                "Value must be positive."
            )

        # Check if OTEL endpoint should be set (warning, not error)
        if self.otel.enabled:
            uses_otel = (
                "otel" in self.routing.errors
                or "otel" in self.routing.metrics
                or "otel" in self.routing.traces
            )
            # Only warn about missing endpoint if using OTLP exporter
            if uses_otel and self.otel.exporter == "otlp" and not self.otel.endpoint:
                logger.warning(
                    "OTEL endpoint is not configured but using OTLP exporter. "
                    "Set OTEL_ENDPOINT environment variable or configure otel.endpoint "
                    "to enable OpenTelemetry export."
                )

        # Raise aggregated errors
        if errors:
            error_message = "Configuration validation failed:\n" + "\n".join(
                f"  - {error}" for error in errors
            )
            raise ConfigurationError(error_message)


def _substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} or ${VAR:default} patterns with environment variable values.

    Supports default values using colon syntax: ${VAR:default_value}
    If no default is provided and the variable is not set, returns empty string.
    """
    pattern = r"\$\{([^}]+)\}"

    def replace(match: re.Match[str]) -> str:
        var_expr = match.group(1)
        # Support default values: ${VAR:default}
        if ":" in var_expr:
            var_name, default = var_expr.split(":", 1)
            return os.environ.get(var_name, default)
        return os.environ.get(var_expr, "")

    return re.sub(pattern, replace, value)


def _process_config_values(config: dict[str, Any]) -> dict[str, Any]:
    """Recursively process config values, substituting environment variables."""
    result = {}
    for key, value in config.items():
        if isinstance(value, str):
            result[key] = _substitute_env_vars(value)
        elif isinstance(value, dict):
            result[key] = _process_config_values(value)
        elif isinstance(value, list):
            result[key] = [
                _substitute_env_vars(item) if isinstance(item, str) else item for item in value
            ]
        else:
            result[key] = value
    return result


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError("PyYAML is required for YAML configuration: pip install pyyaml")

    with open(path) as f:
        return yaml.safe_load(f) or {}


def _dict_to_config(data: dict[str, Any]) -> ObservabilityConfig:
    """Convert a dictionary to ObservabilityConfig."""
    sentry_data = data.get("sentry", {})
    otel_data = data.get("otel", {})
    routing_data = data.get("routing", {})

    return ObservabilityConfig(
        sentry=SentryConfig(
            enabled=sentry_data.get("enabled", True),
            dsn=sentry_data.get("dsn"),
            environment=sentry_data.get("environment", "development"),
            release=sentry_data.get("release"),
            traces_sample_rate=float(sentry_data.get("traces_sample_rate", 0.1)),
            profiles_sample_rate=float(sentry_data.get("profiles_sample_rate", 0.0)),
            send_default_pii=sentry_data.get("send_default_pii", False),
        ),
        otel=OTELConfig(
            enabled=otel_data.get("enabled", True),
            service_name=otel_data.get("service_name", "unknown-service"),
            service_version=otel_data.get("service_version"),
            endpoint=otel_data.get("endpoint"),
            exporter=otel_data.get("exporter", "otlp"),
            otlp_headers=otel_data.get("otlp_headers", ""),
            metrics_enabled=otel_data.get("metrics_enabled", True),
            metrics_export_interval_millis=int(
                otel_data.get("metrics_export_interval_millis", 60000)
            ),
            traces_enabled=otel_data.get("traces_enabled", True),
            traces_sample_rate=float(otel_data.get("traces_sample_rate", 1.0)),
            logs_enabled=otel_data.get("logs_enabled", False),
            prometheus_enabled=otel_data.get("prometheus_enabled", True),
            insecure=otel_data.get("insecure", False),
        ),
        routing=RoutingConfig(
            errors=routing_data.get("errors", "sentry"),
            metrics=routing_data.get("metrics", "otel"),
            traces=routing_data.get("traces", "otel"),
        ),
    )


def load_config(
    config_path: str | None = None,
    service_name: str | None = None,
    environment: str | None = None,
    **overrides: Any,
) -> ObservabilityConfig:
    """Load observability configuration.

    Configuration is loaded from (in order of precedence):
    1. Explicit overrides passed to this function
    2. Environment variables (via ${VAR} substitution in YAML)
    3. Specified YAML config file
    4. Default YAML config file (libs/observability/config/default.yaml)
    5. Default values in config dataclasses

    Args:
        config_path: Path to YAML configuration file.
        service_name: Override service name.
        environment: Override environment.
        **overrides: Additional config overrides.

    Returns:
        ObservabilityConfig instance.
    """
    # Start with empty config
    config_data: dict[str, Any] = {}

    # Load default config if it exists
    default_config_path = Path(__file__).parent / "config" / "default.yaml"
    if default_config_path.exists():
        config_data = _load_yaml(default_config_path)

    # Load specified config file if provided
    if config_path:
        specified_path = Path(config_path)
        if specified_path.exists():
            specified_data = _load_yaml(specified_path)
            # Deep merge specified into default
            for key, value in specified_data.items():
                if isinstance(value, dict) and key in config_data:
                    config_data[key] = {**config_data[key], **value}
                else:
                    config_data[key] = value

    # Substitute environment variables
    config_data = _process_config_values(config_data)

    # Convert to config object
    config = _dict_to_config(config_data)

    # Apply explicit overrides
    if service_name:
        config.otel.service_name = service_name
    if environment:
        config.sentry.environment = environment

    # Apply any additional overrides
    for key, value in overrides.items():
        if key.startswith("sentry_"):
            setattr(config.sentry, key[7:], value)
        elif key.startswith("otel_"):
            setattr(config.otel, key[5:], value)
        elif key.startswith("routing_"):
            setattr(config.routing, key[8:], value)

    # Validate configuration before returning
    config.validate()

    return config
