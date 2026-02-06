"""OpenTelemetry backend for metrics and tracing.

This module handles all OpenTelemetry SDK interactions including
metrics recording and distributed tracing.
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Literal

if TYPE_CHECKING:
    from opentelemetry.trace import Span

    from libs.observability.config import OTELConfig

logger = logging.getLogger(__name__)


class OTELBackend:
    """Backend for OpenTelemetry metrics and tracing."""

    def __init__(self, config: OTELConfig) -> None:
        self._config = config
        self._initialized = False
        self._meter: Any = None
        self._tracer: Any = None
        self._counters: dict[str, Any] = {}
        self._histograms: dict[str, Any] = {}
        self._gauges: dict[str, Any] = {}
        self._gauge_values: dict[str, dict[str, float]] = {}  # Track gauge values for callbacks
        self._meter_provider: Any = None
        self._tracer_provider: Any = None

    def init(self) -> None:
        """Initialize OpenTelemetry metrics and tracing."""
        if not self._config.enabled:
            return

        self._init_metrics()
        self._init_tracing()
        self._initialized = True

    def _init_metrics(self) -> None:
        """Initialize OpenTelemetry metrics."""
        if not self._config.metrics_enabled:
            return

        from opentelemetry import metrics
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.prometheus import PrometheusMetricReader
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource

        resource = Resource(attributes={SERVICE_NAME: self._config.service_name})

        readers = []

        # Add OTLP exporter if endpoint configured
        if self._config.endpoint:
            otlp_exporter = OTLPMetricExporter(
                endpoint=self._config.endpoint,
                insecure=self._config.insecure,
            )
            readers.append(PeriodicExportingMetricReader(otlp_exporter))

        # Add Prometheus reader for scraping
        if self._config.prometheus_enabled:
            readers.append(PrometheusMetricReader())

        if readers:
            self._meter_provider = MeterProvider(resource=resource, metric_readers=readers)
            metrics.set_meter_provider(self._meter_provider)

        self._meter = metrics.get_meter(self._config.service_name, version="1.0.0")

    def _init_tracing(self) -> None:
        """Initialize OpenTelemetry tracing."""
        if not self._config.traces_enabled:
            return

        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource(attributes={SERVICE_NAME: self._config.service_name})
        self._tracer_provider = TracerProvider(resource=resource)

        # Add Sentry span processor if available (for OTEL->Sentry trace correlation)
        try:
            from sentry_sdk.integrations.opentelemetry import SentrySpanProcessor

            self._tracer_provider.add_span_processor(SentrySpanProcessor())
            logger.info("Sentry span processor added for OTEL trace correlation")
        except ImportError:
            logger.debug("Sentry OpenTelemetry integration not available")
        except Exception as e:
            logger.debug(f"Could not add Sentry span processor: {e}")

        if self._config.endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=self._config.endpoint,
                insecure=self._config.insecure,
            )
            self._tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

        trace.set_tracer_provider(self._tracer_provider)
        self._tracer = trace.get_tracer(self._config.service_name, version="1.0.0")

    def record_metric(
        self,
        name: str,
        value: float | int,
        *,
        labels: dict[str, str] | None = None,
        metric_type: Literal["counter", "histogram", "gauge"] = "counter",
        unit: str | None = None,
    ) -> None:
        """Record a metric value."""
        if not self._initialized or self._meter is None:
            return

        attributes = labels or {}

        if metric_type == "counter":
            if name not in self._counters:
                self._counters[name] = self._meter.create_counter(
                    name=name,
                    unit=unit or "1",
                    description=f"Counter for {name}",
                )
            self._counters[name].add(value, attributes=attributes)

        elif metric_type == "histogram":
            if name not in self._histograms:
                self._histograms[name] = self._meter.create_histogram(
                    name=name,
                    unit=unit or "ms",
                    description=f"Histogram for {name}",
                )
            self._histograms[name].record(value, attributes=attributes)

        elif metric_type == "gauge":
            # OTEL gauges use ObservableGauge with callbacks for true gauge semantics.
            # We store the current value and let the callback report it during scrape.
            # Use JSON serialization for safety (no eval).
            attr_key = json.dumps(sorted(attributes.items())) if attributes else ""
            if name not in self._gauge_values:
                self._gauge_values[name] = {}

            # Store the absolute value (gauge semantics)
            self._gauge_values[name][attr_key] = float(value)

            # Create the observable gauge with callback if not exists
            if name not in self._gauges:

                def make_callback(metric_name: str) -> Any:
                    def callback(options: Any) -> Any:
                        from opentelemetry.metrics import Observation

                        observations = []
                        for attr_str, val in self._gauge_values.get(metric_name, {}).items():
                            # Reconstruct attributes from JSON key
                            attrs = dict(json.loads(attr_str)) if attr_str else {}
                            observations.append(Observation(val, attrs))
                        return observations

                    return callback

                self._gauges[name] = self._meter.create_observable_gauge(
                    name=name,
                    callbacks=[make_callback(name)],
                    unit=unit or "1",
                    description=f"Gauge for {name}",
                )

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        kind: Literal["internal", "server", "client", "producer", "consumer"] = "internal",
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Span]:
        """Start a new tracing span.

        Yields:
            OTEL Span object.
        """
        if not self._initialized or self._tracer is None:
            # Return a no-op context manager
            from contextlib import nullcontext

            with nullcontext() as _:
                yield None  # type: ignore[misc]
            return

        from opentelemetry.trace import SpanKind

        kind_map = {
            "internal": SpanKind.INTERNAL,
            "server": SpanKind.SERVER,
            "client": SpanKind.CLIENT,
            "producer": SpanKind.PRODUCER,
            "consumer": SpanKind.CONSUMER,
        }

        with self._tracer.start_as_current_span(
            name,
            kind=kind_map.get(kind, SpanKind.INTERNAL),
            attributes=attributes,
        ) as span:
            yield span

    def flush(self, timeout: float = 2.0) -> None:
        """Flush pending metrics and traces."""
        if not self._initialized:
            return

        # Force flush is available on providers
        if self._meter_provider is not None:
            try:
                self._meter_provider.force_flush(timeout_millis=int(timeout * 1000))
            except Exception as e:
                logger.warning("Failed to flush meter provider: %s", e)

        if self._tracer_provider is not None:
            try:
                self._tracer_provider.force_flush(timeout_millis=int(timeout * 1000))
            except Exception as e:
                logger.warning("Failed to flush tracer provider: %s", e)

    def shutdown(self) -> None:
        """Shutdown OpenTelemetry providers."""
        if not self._initialized:
            return

        if self._meter_provider is not None:
            try:
                self._meter_provider.shutdown()
            except Exception as e:
                logger.warning("Failed to shutdown meter provider: %s", e)

        if self._tracer_provider is not None:
            try:
                self._tracer_provider.shutdown()
            except Exception as e:
                logger.warning("Failed to shutdown tracer provider: %s", e)

        self._initialized = False
