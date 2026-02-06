"""
Prometheus metrics endpoint.

This module provides a /metrics endpoint compatible with Prometheus scraping.
Metrics are collected via OpenTelemetry and exposed in Prometheus format.
"""
import logging
from fastapi import APIRouter, Response
from starlette.status import HTTP_503_SERVICE_UNAVAILABLE

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/metrics",
    include_in_schema=False,
    response_class=Response,
)
async def prometheus_metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Exposes metrics in Prometheus text format for scraping by Prometheus server.

    Note: This endpoint is intentionally unauthenticated to allow Prometheus
    scrapers to collect metrics. No sensitive data (user IDs, emails, etc.)
    should be exposed via metric labels.

    Returns:
        Response: Metrics in Prometheus text format
    """
    # Import here to avoid circular dependencies and allow graceful degradation
    try:
        from app.metrics.prometheus import get_prometheus_metrics_text
    except (ImportError, AttributeError) as e:
        logger.error(f"Prometheus exporter not available: {e}")
        return Response(
            content="# Prometheus metrics not available\n",
            media_type="text/plain; version=0.0.4",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not settings.OTEL_ENABLED or not settings.OTEL_METRICS_ENABLED:
        return Response(
            content="# Metrics not enabled (set OTEL_ENABLED=true and OTEL_METRICS_ENABLED=true)\n",
            media_type="text/plain; version=0.0.4",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )

    if not settings.PROMETHEUS_METRICS_ENABLED:
        return Response(
            content="# Prometheus endpoint not enabled (set PROMETHEUS_METRICS_ENABLED=true)\n",
            media_type="text/plain; version=0.0.4",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )

    try:
        metrics_text = get_prometheus_metrics_text()
        return Response(
            content=metrics_text,
            media_type="text/plain; version=0.0.4",
        )
    except Exception:
        logger.exception("Failed to generate Prometheus metrics")
        return Response(
            content="# Error generating metrics\n",
            media_type="text/plain; version=0.0.4",
            status_code=HTTP_503_SERVICE_UNAVAILABLE,
        )
