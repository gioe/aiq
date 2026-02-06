"""Configuration management for observability.

Supports YAML configuration files with environment variable substitution.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


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
    endpoint: str | None = None
    metrics_enabled: bool = True
    traces_enabled: bool = True
    prometheus_enabled: bool = True


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


def _substitute_env_vars(value: str) -> str:
    """Substitute ${VAR} patterns with environment variable values."""
    pattern = r"\$\{([^}]+)\}"

    def replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        return os.environ.get(var_name, "")

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
            endpoint=otel_data.get("endpoint"),
            metrics_enabled=otel_data.get("metrics_enabled", True),
            traces_enabled=otel_data.get("traces_enabled", True),
            prometheus_enabled=otel_data.get("prometheus_enabled", True),
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

    return config
