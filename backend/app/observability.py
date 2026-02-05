"""
Custom application metrics instrumentation for OpenTelemetry.

This module provides custom metrics for monitoring application behavior:
- HTTP request counts and latency
- Database query performance
- Active sessions
- Error rates

Usage:
    from app.observability import metrics

    # Record HTTP request
    metrics.record_http_request("GET", "/v1/users", 200, 0.15)

    # Record database query
    metrics.record_db_query("SELECT", "users", 0.02)

    # Update active sessions gauge
    metrics.set_active_sessions(42)
"""
import logging
from typing import TYPE_CHECKING, Optional

from app.core.config import settings

if TYPE_CHECKING:
    from opentelemetry.metrics import Counter, Histogram, Meter, UpDownCounter

logger = logging.getLogger(__name__)


class ApplicationMetrics:
    """
    Application-level metrics using OpenTelemetry.

    Provides helper methods for recording custom metrics throughout the application.
    All methods are no-ops if metrics are not enabled.
    """

    def __init__(self) -> None:
        """Initialize ApplicationMetrics with empty instruments."""
        self._meter: Optional["Meter"] = None
        self._http_request_counter: Optional["Counter"] = None
        self._http_request_duration: Optional["Histogram"] = None
        self._db_query_duration: Optional["Histogram"] = None
        self._active_sessions_gauge: Optional["UpDownCounter"] = None
        self._error_counter: Optional["Counter"] = None
        self._initialized = False
        self._last_session_count: int = 0

    def initialize(self) -> None:
        """
        Initialize OpenTelemetry metrics.

        Should be called during application startup after OpenTelemetry is configured.
        """
        if not settings.OTEL_ENABLED or not settings.OTEL_METRICS_ENABLED:
            logger.info("Application metrics not enabled (OTEL_METRICS_ENABLED=False)")
            return

        if self._initialized:
            logger.warning("Application metrics already initialized")
            return

        try:
            from opentelemetry import metrics as otel_metrics

            meter_provider = otel_metrics.get_meter_provider()
            self._meter = meter_provider.get_meter(
                "aiq.backend",
                version=settings.APP_VERSION,
            )

            # HTTP Request Counter
            # Tracks total number of HTTP requests by method, endpoint, and status
            self._http_request_counter = self._meter.create_counter(
                name="http.server.requests",
                description="Total HTTP requests",
                unit="1",
            )

            # HTTP Request Duration Histogram
            # Tracks request latency distribution by method and endpoint
            self._http_request_duration = self._meter.create_histogram(
                name="http.server.request.duration",
                description="HTTP request duration",
                unit="s",
            )

            # Database Query Duration Histogram
            # Tracks database query performance by operation and table
            self._db_query_duration = self._meter.create_histogram(
                name="db.query.duration",
                description="Database query duration",
                unit="s",
            )

            # Active Sessions Gauge
            # Current number of active test sessions (in_progress status)
            self._active_sessions_gauge = self._meter.create_up_down_counter(
                name="test.sessions.active",
                description="Number of active test sessions",
                unit="1",
            )

            # Error Counter
            # Tracks application errors by type and endpoint
            self._error_counter = self._meter.create_counter(
                name="app.errors",
                description="Application errors",
                unit="1",
            )

            self._initialized = True
            logger.info("Application metrics initialized successfully")

        except ImportError:
            logger.warning(
                "OpenTelemetry metrics packages not available. "
                "Custom metrics will be disabled."
            )
        except Exception as e:
            logger.error(f"Failed to initialize application metrics: {e}")

    def record_http_request(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
    ) -> None:
        """
        Record an HTTP request.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: Request path (e.g., "/v1/users")
            status_code: HTTP status code (200, 404, etc.)
            duration: Request duration in seconds
        """
        if not self._initialized:
            return

        if self._http_request_counter is None or self._http_request_duration is None:
            return

        try:
            attributes: dict[str, str | int] = {
                "http.method": method,
                "http.route": path,
                "http.status_code": status_code,
            }

            self._http_request_counter.add(1, attributes)
            self._http_request_duration.record(duration, attributes)
        except Exception as e:
            logger.debug(f"Failed to record HTTP request metric: {e}")

    def record_db_query(
        self,
        operation: str,
        table: str,
        duration: float,
    ) -> None:
        """
        Record a database query.

        Args:
            operation: SQL operation (SELECT, INSERT, UPDATE, DELETE)
            table: Database table name
            duration: Query duration in seconds
        """
        if not self._initialized:
            return

        if self._db_query_duration is None:
            return

        try:
            attributes = {
                "db.operation": operation,
                "db.table": table,
            }
            self._db_query_duration.record(duration, attributes)
        except Exception as e:
            logger.debug(f"Failed to record database query metric: {e}")

    def set_active_sessions(self, count: int) -> None:
        """
        Update the active sessions gauge.

        Args:
            count: Current number of active test sessions
        """
        if not self._initialized:
            return

        if self._active_sessions_gauge is None:
            return

        try:
            # UpDownCounter uses add(), not set()
            # Track the delta from the last count
            delta = count - self._last_session_count
            self._active_sessions_gauge.add(delta)
            self._last_session_count = count
        except Exception as e:
            logger.debug(f"Failed to update active sessions metric: {e}")

    def record_error(
        self,
        error_type: str,
        path: Optional[str] = None,
    ) -> None:
        """
        Record an application error.

        Args:
            error_type: Type of error (e.g., "ValidationError", "DatabaseError")
            path: Optional request path where error occurred
        """
        if not self._initialized:
            return

        if self._error_counter is None:
            return

        try:
            attributes: dict[str, str] = {"error.type": error_type}
            if path:
                attributes["http.route"] = path

            self._error_counter.add(1, attributes)
        except Exception as e:
            logger.debug(f"Failed to record error metric: {e}")


# Global metrics instance
metrics = ApplicationMetrics()
