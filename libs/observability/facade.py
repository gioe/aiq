"""Public API facade for observability.

This module provides the unified interface that application code uses.
It routes calls to the appropriate backend (Sentry, OpenTelemetry, or both)
based on configuration.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator, Literal

if TYPE_CHECKING:
    from libs.observability.config import ObservabilityConfig

MetricType = Literal["counter", "histogram", "gauge"]
ErrorLevel = Literal["debug", "info", "warning", "error", "fatal"]


class SpanContext:
    """Context manager wrapper for tracing spans."""

    def __init__(self, name: str, otel_span: Any = None, sentry_span: Any = None):
        self._name = name
        self._otel_span = otel_span
        self._sentry_span = sentry_span

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span."""
        if self._otel_span is not None:
            self._otel_span.set_attribute(key, value)
        if self._sentry_span is not None:
            self._sentry_span.set_data(key, value)

    def set_status(self, status: Literal["ok", "error"], description: str = "") -> None:
        """Set the span status."""
        if self._otel_span is not None:
            from opentelemetry.trace import StatusCode

            code = StatusCode.OK if status == "ok" else StatusCode.ERROR
            self._otel_span.set_status(code, description)

    def record_exception(self, exception: BaseException) -> None:
        """Record an exception on the span."""
        if self._otel_span is not None:
            self._otel_span.record_exception(exception)

    def __enter__(self) -> SpanContext:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None:
            self.record_exception(exc_val)
            self.set_status("error", str(exc_val))


class ObservabilityFacade:
    """Unified facade for observability operations.

    Provides a single API for error capture, metrics, and tracing that
    routes to the configured backend systems.
    """

    def __init__(self) -> None:
        self._initialized = False
        self._config: ObservabilityConfig | None = None
        self._sentry_backend: Any = None
        self._otel_backend: Any = None

    @property
    def is_initialized(self) -> bool:
        """Check if observability has been initialized."""
        return self._initialized

    def init(
        self,
        config_path: str | None = None,
        service_name: str | None = None,
        environment: str | None = None,
        **overrides: Any,
    ) -> None:
        """Initialize observability backends.

        Args:
            config_path: Path to YAML configuration file.
            service_name: Override service name from config.
            environment: Override environment from config.
            **overrides: Additional config overrides.
        """
        from libs.observability.config import load_config

        self._config = load_config(
            config_path=config_path,
            service_name=service_name,
            environment=environment,
            **overrides,
        )

        # Initialize backends based on config
        if self._config.sentry.enabled:
            from libs.observability.sentry_backend import SentryBackend

            self._sentry_backend = SentryBackend(self._config.sentry)
            self._sentry_backend.init()

        if self._config.otel.enabled:
            from libs.observability.otel_backend import OTELBackend

            self._otel_backend = OTELBackend(self._config.otel)
            self._otel_backend.init()

        self._initialized = True

    def capture_error(
        self,
        exception: BaseException,
        *,
        context: dict[str, Any] | None = None,
        level: ErrorLevel = "error",
        user: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        fingerprint: list[str] | None = None,
    ) -> str | None:
        """Capture an error and send to error tracking backend (Sentry).

        Args:
            exception: The exception to capture.
            context: Additional context data to attach.
            level: Error severity level.
            user: User information (id, email, etc.).
            tags: Tags for categorization.
            fingerprint: Custom grouping fingerprint.

        Returns:
            Event ID if captured, None if skipped.
        """
        if not self._initialized:
            return None

        if self._sentry_backend is not None:
            return self._sentry_backend.capture_error(
                exception=exception,
                context=context,
                level=level,
                user=user,
                tags=tags,
                fingerprint=fingerprint,
            )
        return None

    def capture_message(
        self,
        message: str,
        *,
        level: ErrorLevel = "info",
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str | None:
        """Capture a message and send to error tracking backend.

        Args:
            message: The message to capture.
            level: Message severity level.
            context: Additional context data.
            tags: Tags for categorization.

        Returns:
            Event ID if captured, None if skipped.
        """
        if not self._initialized:
            return None

        if self._sentry_backend is not None:
            return self._sentry_backend.capture_message(
                message=message,
                level=level,
                context=context,
                tags=tags,
            )
        return None

    def record_metric(
        self,
        name: str,
        value: float | int,
        *,
        labels: dict[str, str] | None = None,
        metric_type: MetricType = "counter",
        unit: str | None = None,
    ) -> None:
        """Record a metric value.

        Args:
            name: Metric name (e.g., "requests.processed").
            value: Metric value.
            labels: Labels/dimensions for the metric.
            metric_type: Type of metric (counter, histogram, gauge).
            unit: Optional unit of measurement.
        """
        if not self._initialized:
            return

        if self._otel_backend is not None:
            self._otel_backend.record_metric(
                name=name,
                value=value,
                labels=labels,
                metric_type=metric_type,
                unit=unit,
            )

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        kind: Literal["internal", "server", "client", "producer", "consumer"] = "internal",
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[SpanContext]:
        """Start a new tracing span.

        Args:
            name: Span name.
            kind: Span kind for categorization.
            attributes: Initial span attributes.

        Yields:
            SpanContext for setting attributes and status.
        """
        if not self._initialized:
            yield SpanContext(name)
            return

        otel_span = None
        sentry_span = None

        routing = self._config.routing.traces if self._config else "otel"

        # Start OTEL span if configured
        if routing in ("otel", "both") and self._otel_backend is not None:
            otel_span = self._otel_backend.start_span(name, kind=kind, attributes=attributes)
            otel_span.__enter__()

        # Start Sentry span if configured
        if routing in ("sentry", "both") and self._sentry_backend is not None:
            sentry_span = self._sentry_backend.start_span(name, attributes=attributes)
            if sentry_span is not None:
                sentry_span.__enter__()

        try:
            yield SpanContext(name, otel_span=otel_span, sentry_span=sentry_span)
        finally:
            if sentry_span is not None:
                sentry_span.__exit__(None, None, None)
            if otel_span is not None:
                otel_span.__exit__(None, None, None)

    def set_user(self, user_id: str | None, **extra: Any) -> None:
        """Set the current user context.

        Args:
            user_id: User identifier.
            **extra: Additional user data (email, username, etc.).
        """
        if not self._initialized:
            return

        if self._sentry_backend is not None:
            self._sentry_backend.set_user(user_id, **extra)

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag on the current scope.

        Args:
            key: Tag key.
            value: Tag value.
        """
        if not self._initialized:
            return

        if self._sentry_backend is not None:
            self._sentry_backend.set_tag(key, value)

    def set_context(self, name: str, context: dict[str, Any]) -> None:
        """Set a context block on the current scope.

        Args:
            name: Context name.
            context: Context data.
        """
        if not self._initialized:
            return

        if self._sentry_backend is not None:
            self._sentry_backend.set_context(name, context)

    def flush(self, timeout: float = 2.0) -> None:
        """Flush pending events to backends.

        Args:
            timeout: Maximum time to wait for flush.
        """
        if not self._initialized:
            return

        if self._sentry_backend is not None:
            self._sentry_backend.flush(timeout)

        if self._otel_backend is not None:
            self._otel_backend.flush(timeout)

    def shutdown(self) -> None:
        """Shutdown observability backends gracefully."""
        if not self._initialized:
            return

        if self._sentry_backend is not None:
            self._sentry_backend.shutdown()

        if self._otel_backend is not None:
            self._otel_backend.shutdown()

        self._initialized = False
