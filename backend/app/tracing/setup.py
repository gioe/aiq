"""
OpenTelemetry tracing setup and configuration.
"""
import logging
from typing import TYPE_CHECKING, Optional

from app.core.config import settings

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider

logger = logging.getLogger(__name__)

_tracer_provider: Optional["TracerProvider"] = None


def setup_tracing(app) -> None:
    """
    Initialize OpenTelemetry tracing for the application.

    Args:
        app: FastAPI application instance
    """
    global _tracer_provider

    if not settings.OTEL_ENABLED:
        return

    if settings.OTEL_EXPORTER == "none":
        return

    if _tracer_provider is not None:
        logger.warning("OpenTelemetry already initialized, skipping")
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.trace.sampling import TraceIdRatioBasedSampler
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy "
            "opentelemetry-exporter-otlp"
        )
        return

    resource = Resource(attributes={"service.name": settings.OTEL_SERVICE_NAME})

    sampler = TraceIdRatioBasedSampler(settings.OTEL_TRACES_SAMPLE_RATE)

    provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.OTEL_EXPORTER == "console":
        exporter = ConsoleSpanExporter()
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)
    elif settings.OTEL_EXPORTER == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=settings.OTEL_OTLP_ENDPOINT)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
        except ImportError:
            provider.shutdown()
            logger.warning(
                "OTLP exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )
            return

    trace.set_tracer_provider(provider)
    _tracer_provider = provider

    FastAPIInstrumentor.instrument_app(app)

    try:
        from app.models import engine

        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")

    logger.info(
        f"OpenTelemetry tracing initialized with {settings.OTEL_EXPORTER} exporter "
        f"(sample_rate={settings.OTEL_TRACES_SAMPLE_RATE * 100:.0f}%)"
    )


def shutdown_tracing() -> None:
    """
    Shutdown OpenTelemetry tracing and flush any pending spans.
    """
    global _tracer_provider

    if _tracer_provider is None:
        return

    try:
        if hasattr(_tracer_provider, "shutdown"):
            _tracer_provider.shutdown()
            logger.info("OpenTelemetry tracing shutdown complete")
    except Exception as e:
        logger.warning(f"Error shutting down OpenTelemetry tracing: {e}")
    finally:
        _tracer_provider = None
