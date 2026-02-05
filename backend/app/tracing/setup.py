"""
OpenTelemetry tracing, metrics, and logging setup and configuration.
"""
import logging
from typing import TYPE_CHECKING, Optional

from app.core.config import settings

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk._logs import LoggerProvider
    from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)

_tracer_provider: Optional["TracerProvider"] = None
_meter_provider: Optional["MeterProvider"] = None
_logger_provider: Optional["LoggerProvider"] = None


def _parse_otlp_headers() -> dict[str, str]:
    """
    Parse OTEL_EXPORTER_OTLP_HEADERS environment variable into a dictionary.

    Format: "key1=value1,key2=value2"
    Returns: {"key1": "value1", "key2": "value2"}

    Note: Empty keys or values are skipped to avoid malformed headers.
    """
    if not settings.OTEL_EXPORTER_OTLP_HEADERS:
        return {}

    headers: dict[str, str] = {}
    for pair in settings.OTEL_EXPORTER_OTLP_HEADERS.split(","):
        if "=" in pair:
            key, value = pair.split("=", 1)
            key = key.strip()
            value = value.strip()
            if key and value:
                headers[key] = value
    return headers


def setup_tracing(app) -> None:
    """
    Initialize OpenTelemetry tracing, metrics, and logging for the application.

    Args:
        app: FastAPI application instance
    """
    global _tracer_provider, _meter_provider, _logger_provider

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

    # Create shared resource with service name
    resource = Resource(attributes={"service.name": settings.OTEL_SERVICE_NAME})

    # Parse OTLP headers for authentication (e.g., Grafana Cloud)
    otlp_headers = _parse_otlp_headers()

    # ============================================================================
    # TRACES SETUP
    # ============================================================================
    sampler = TraceIdRatioBasedSampler(settings.OTEL_TRACES_SAMPLE_RATE)
    trace_provider = TracerProvider(resource=resource, sampler=sampler)

    if settings.OTEL_EXPORTER == "console":
        exporter = ConsoleSpanExporter()
        processor = BatchSpanProcessor(exporter)
        trace_provider.add_span_processor(processor)
    elif settings.OTEL_EXPORTER == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(
                endpoint=settings.OTEL_OTLP_ENDPOINT,
                headers=otlp_headers,
            )
            processor = BatchSpanProcessor(exporter)
            trace_provider.add_span_processor(processor)
        except ImportError:
            trace_provider.shutdown()
            logger.warning(
                "OTLP exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )
            return

    trace.set_tracer_provider(trace_provider)
    _tracer_provider = trace_provider

    # Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # Instrument SQLAlchemy
    try:
        from app.models import engine

        SQLAlchemyInstrumentor().instrument(engine=engine)
    except Exception as e:
        logger.warning(f"Failed to instrument SQLAlchemy: {e}")

    logger.info(
        f"OpenTelemetry tracing initialized with {settings.OTEL_EXPORTER} exporter "
        f"(sample_rate={settings.OTEL_TRACES_SAMPLE_RATE * 100:.0f}%)"
    )

    # ============================================================================
    # METRICS SETUP
    # ============================================================================
    if settings.OTEL_METRICS_ENABLED:
        _setup_metrics(resource, otlp_headers)

    # ============================================================================
    # LOGS SETUP
    # ============================================================================
    if settings.OTEL_LOGS_ENABLED:
        _setup_logs(resource, otlp_headers)


def _setup_metrics(resource: "Resource", otlp_headers: dict) -> None:
    """
    Initialize OpenTelemetry metrics provider and exporter.

    Args:
        resource: OpenTelemetry Resource with service name
        otlp_headers: Headers for OTLP exporter authentication
    """
    global _meter_provider

    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            PeriodicExportingMetricReader,
            ConsoleMetricExporter,
        )
    except ImportError:
        logger.warning(
            "OpenTelemetry metrics packages not installed. " "Skipping metrics setup."
        )
        return

    if settings.OTEL_EXPORTER == "console":
        exporter = ConsoleMetricExporter()
        reader = PeriodicExportingMetricReader(
            exporter,
            export_interval_millis=settings.OTEL_METRICS_EXPORT_INTERVAL_MILLIS,
        )
        meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
    elif settings.OTEL_EXPORTER == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )

            exporter = OTLPMetricExporter(
                endpoint=settings.OTEL_OTLP_ENDPOINT,
                headers=otlp_headers,
            )
            reader = PeriodicExportingMetricReader(
                exporter,
                export_interval_millis=settings.OTEL_METRICS_EXPORT_INTERVAL_MILLIS,
            )
            meter_provider = MeterProvider(resource=resource, metric_readers=[reader])
        except ImportError:
            logger.warning(
                "OTLP metric exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )
            return
    else:
        return

    metrics.set_meter_provider(meter_provider)
    _meter_provider = meter_provider

    logger.info(
        f"OpenTelemetry metrics initialized with {settings.OTEL_EXPORTER} exporter "
        f"(export_interval={settings.OTEL_METRICS_EXPORT_INTERVAL_MILLIS}ms)"
    )

    # Initialize Prometheus exporter if enabled
    if settings.PROMETHEUS_METRICS_ENABLED:
        try:
            from app.metrics.prometheus import initialize_prometheus_exporter

            initialize_prometheus_exporter(meter_provider)
        except Exception as e:
            logger.warning(f"Failed to initialize Prometheus exporter: {e}")


def _setup_logs(resource: "Resource", otlp_headers: dict) -> None:
    """
    Initialize OpenTelemetry logging provider and exporter.

    Args:
        resource: OpenTelemetry Resource with service name
        otlp_headers: Headers for OTLP exporter authentication
    """
    global _logger_provider

    try:
        from opentelemetry._logs import set_logger_provider
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
    except ImportError:
        logger.warning(
            "OpenTelemetry logging packages not installed. " "Skipping logs setup."
        )
        return

    logger_provider = LoggerProvider(resource=resource)

    if settings.OTEL_EXPORTER == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
                OTLPLogExporter,
            )

            exporter = OTLPLogExporter(
                endpoint=settings.OTEL_OTLP_ENDPOINT,
                headers=otlp_headers,
            )
            processor = BatchLogRecordProcessor(exporter)
            logger_provider.add_log_record_processor(processor)
        except ImportError:
            logger.warning(
                "OTLP log exporter not available. "
                "Install with: pip install opentelemetry-exporter-otlp"
            )
            return

    set_logger_provider(logger_provider)
    _logger_provider = logger_provider

    # Attach OpenTelemetry handler to root logger to forward all logs
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)

    logger.info(
        f"OpenTelemetry logging initialized with {settings.OTEL_EXPORTER} exporter"
    )


def shutdown_tracing() -> None:
    """
    Shutdown OpenTelemetry tracing, metrics, and logging, and flush any pending data.
    """
    global _tracer_provider, _meter_provider, _logger_provider

    # Shutdown tracer provider
    if _tracer_provider is not None:
        try:
            if hasattr(_tracer_provider, "shutdown"):
                _tracer_provider.shutdown()
                logger.info("OpenTelemetry tracing shutdown complete")
        except Exception as e:
            logger.warning(f"Error shutting down OpenTelemetry tracing: {e}")
        finally:
            _tracer_provider = None

    # Shutdown meter provider
    if _meter_provider is not None:
        try:
            if hasattr(_meter_provider, "shutdown"):
                _meter_provider.shutdown()
                logger.info("OpenTelemetry metrics shutdown complete")
        except Exception as e:
            logger.warning(f"Error shutting down OpenTelemetry metrics: {e}")
        finally:
            _meter_provider = None

    # Shutdown logger provider
    if _logger_provider is not None:
        try:
            if hasattr(_logger_provider, "shutdown"):
                _logger_provider.shutdown()
                logger.info("OpenTelemetry logging shutdown complete")
        except Exception as e:
            logger.warning(f"Error shutting down OpenTelemetry logging: {e}")
        finally:
            _logger_provider = None
