"""
Prometheus metrics exporter integration.

This module configures the Prometheus exporter for OpenTelemetry metrics
and provides a function to retrieve metrics in Prometheus text format.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Global Prometheus registry - initialized on first use
_prometheus_registry: Optional[Any] = None
_prometheus_initialized = False


def initialize_prometheus_exporter() -> None:
    """
    Capture the global Prometheus registry and mark the exporter as initialized.

    The PrometheusMetricReader must already be registered with the MeterProvider
    at construction time (see app/tracing/setup.py). This function only captures
    the prometheus_client REGISTRY reference used by get_prometheus_metrics_text().
    """
    global _prometheus_registry, _prometheus_initialized

    if _prometheus_initialized:
        logger.warning("Prometheus exporter already initialized")
        return

    try:
        from prometheus_client import REGISTRY

        _prometheus_registry = REGISTRY
        _prometheus_initialized = True

        logger.info("Prometheus exporter initialized successfully")

    except ImportError:
        logger.warning(
            "prometheus_client not available. "
            "Install with: pip install prometheus-client"
        )
    except Exception as e:
        logger.error(f"Failed to initialize Prometheus exporter: {e}")


def get_prometheus_metrics_text() -> str:
    """
    Get current metrics in Prometheus text format.

    Returns:
        str: Metrics in Prometheus exposition format

    Raises:
        RuntimeError: If Prometheus exporter is not initialized
    """
    global _prometheus_registry

    if not _prometheus_initialized or _prometheus_registry is None:
        raise RuntimeError(
            "Prometheus exporter not initialized. "
            "Ensure OpenTelemetry metrics are enabled and initialized."
        )

    try:
        from prometheus_client import generate_latest

        # Generate metrics in Prometheus text format
        metrics_bytes = generate_latest(_prometheus_registry)
        return metrics_bytes.decode("utf-8")

    except ImportError:
        raise RuntimeError(
            "prometheus_client not available. "
            "Install with: pip install prometheus-client"
        )
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}")
        raise


def is_prometheus_enabled() -> bool:
    """
    Check if Prometheus exporter is initialized.

    Returns:
        bool: True if Prometheus metrics are available
    """
    return _prometheus_initialized
