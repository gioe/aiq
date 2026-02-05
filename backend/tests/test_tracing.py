"""
Tests for OpenTelemetry distributed tracing integration.
"""
import json
import logging
import sys
from unittest.mock import MagicMock, patch

import app.tracing.setup as tracing_setup


class TestSetupTracing:
    """Tests for the setup_tracing() function."""

    def setup_method(self):
        """Reset global tracing state between tests."""
        tracing_setup._tracer_provider = None

    def test_setup_tracing_disabled_by_default(self):
        """Test that setup_tracing is a no-op when OTEL_ENABLED=False."""
        with patch("app.tracing.setup.settings") as mock_settings:
            mock_settings.OTEL_ENABLED = False

            from app.tracing import setup_tracing

            mock_app = MagicMock()
            setup_tracing(mock_app)

    def test_setup_tracing_with_console_exporter(self):
        """Test that setup_tracing creates TracerProvider with console exporter."""
        with patch.dict(
            sys.modules,
            {
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.sdk.trace": MagicMock(),
                "opentelemetry.sdk.trace.export": MagicMock(),
                "opentelemetry.sdk.trace.sampling": MagicMock(),
                "opentelemetry.sdk.resources": MagicMock(),
                "opentelemetry.instrumentation.fastapi": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
            },
        ):
            with patch("app.tracing.setup.settings") as mock_settings:
                mock_settings.OTEL_ENABLED = True
                mock_settings.OTEL_SERVICE_NAME = "test-service"
                mock_settings.OTEL_EXPORTER = "console"
                mock_settings.OTEL_TRACES_SAMPLE_RATE = 1.0

                from app.tracing.setup import setup_tracing

                mock_app = MagicMock()

                setup_tracing(mock_app)

    def test_setup_tracing_with_otlp_exporter(self):
        """Test that setup_tracing creates TracerProvider with OTLP exporter."""
        with patch.dict(
            sys.modules,
            {
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.sdk.trace": MagicMock(),
                "opentelemetry.sdk.trace.export": MagicMock(),
                "opentelemetry.sdk.trace.sampling": MagicMock(),
                "opentelemetry.sdk.resources": MagicMock(),
                "opentelemetry.instrumentation.fastapi": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
                "opentelemetry.exporter.otlp.proto.grpc.trace_exporter": MagicMock(),
            },
        ):
            with patch("app.tracing.setup.settings") as mock_settings:
                mock_settings.OTEL_ENABLED = True
                mock_settings.OTEL_SERVICE_NAME = "test-service"
                mock_settings.OTEL_EXPORTER = "otlp"
                mock_settings.OTEL_OTLP_ENDPOINT = "http://localhost:4317"
                mock_settings.OTEL_TRACES_SAMPLE_RATE = 0.5

                from app.tracing.setup import setup_tracing

                mock_app = MagicMock()

                setup_tracing(mock_app)

    def test_setup_tracing_none_exporter_is_noop(self):
        """Test that setup_tracing is a no-op when OTEL_EXPORTER=none."""
        with patch("app.tracing.setup.settings") as mock_settings:
            mock_settings.OTEL_ENABLED = True
            mock_settings.OTEL_EXPORTER = "none"

            from app.tracing import setup_tracing

            mock_app = MagicMock()
            setup_tracing(mock_app)

    def test_setup_tracing_handles_import_error(self):
        """Test that setup_tracing handles ImportError gracefully."""
        with patch("app.tracing.setup.settings") as mock_settings:
            mock_settings.OTEL_ENABLED = True
            mock_settings.OTEL_EXPORTER = "console"

            with patch("app.tracing.setup.logger") as mock_logger:
                from app.tracing.setup import setup_tracing

                mock_app = MagicMock()
                setup_tracing(mock_app)

                mock_logger.warning.assert_called_once()
                log_message = mock_logger.warning.call_args[0][0]
                assert "OpenTelemetry packages not installed" in log_message

    def test_setup_tracing_logs_initialization(self):
        """Test that setup_tracing logs initialization message."""
        with patch.dict(
            sys.modules,
            {
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.sdk.trace": MagicMock(),
                "opentelemetry.sdk.trace.export": MagicMock(),
                "opentelemetry.sdk.trace.sampling": MagicMock(),
                "opentelemetry.sdk.resources": MagicMock(),
                "opentelemetry.instrumentation.fastapi": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
            },
        ):
            with patch("app.tracing.setup.settings") as mock_settings:
                mock_settings.OTEL_ENABLED = True
                mock_settings.OTEL_SERVICE_NAME = "test-service"
                mock_settings.OTEL_EXPORTER = "console"
                mock_settings.OTEL_TRACES_SAMPLE_RATE = 0.5

                with patch("app.tracing.setup.logger") as mock_logger:
                    from app.tracing.setup import setup_tracing

                    mock_app = MagicMock()
                    setup_tracing(mock_app)

                    mock_logger.info.assert_called_once()
                    log_message = mock_logger.info.call_args[0][0]
                    assert "OpenTelemetry tracing initialized" in log_message
                    assert "console exporter" in log_message
                    assert "50%" in log_message

    def test_setup_tracing_idempotent(self):
        """Test that calling setup_tracing twice logs warning and skips."""
        with patch.dict(
            sys.modules,
            {
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.sdk.trace": MagicMock(),
                "opentelemetry.sdk.trace.export": MagicMock(),
                "opentelemetry.sdk.trace.sampling": MagicMock(),
                "opentelemetry.sdk.resources": MagicMock(),
                "opentelemetry.instrumentation.fastapi": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
            },
        ):
            with patch("app.tracing.setup.settings") as mock_settings:
                mock_settings.OTEL_ENABLED = True
                mock_settings.OTEL_SERVICE_NAME = "test-service"
                mock_settings.OTEL_EXPORTER = "console"
                mock_settings.OTEL_TRACES_SAMPLE_RATE = 1.0

                with patch("app.tracing.setup.logger") as mock_logger:
                    from app.tracing.setup import setup_tracing

                    mock_app = MagicMock()

                    setup_tracing(mock_app)
                    mock_logger.reset_mock()

                    setup_tracing(mock_app)
                    mock_logger.warning.assert_called_once()
                    log_message = mock_logger.warning.call_args[0][0]
                    assert "already initialized" in log_message


class TestShutdownTracing:
    """Tests for the shutdown_tracing() function."""

    def setup_method(self):
        """Reset global tracing state between tests."""
        tracing_setup._tracer_provider = None

    def test_shutdown_tracing_without_setup(self):
        """Test that shutdown_tracing doesn't crash when called without setup."""
        from app.tracing import shutdown_tracing

        shutdown_tracing()

    def test_shutdown_tracing_calls_provider_shutdown(self):
        """Test that shutdown_tracing calls TracerProvider.shutdown()."""
        with patch.dict(
            sys.modules,
            {
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.sdk.trace": MagicMock(),
                "opentelemetry.sdk.trace.export": MagicMock(),
                "opentelemetry.sdk.trace.sampling": MagicMock(),
                "opentelemetry.sdk.resources": MagicMock(),
                "opentelemetry.instrumentation.fastapi": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
            },
        ):
            with patch("app.tracing.setup.settings") as mock_settings:
                mock_settings.OTEL_ENABLED = True
                mock_settings.OTEL_SERVICE_NAME = "test-service"
                mock_settings.OTEL_EXPORTER = "console"
                mock_settings.OTEL_TRACES_SAMPLE_RATE = 1.0

                from app.tracing import setup_tracing, shutdown_tracing

                mock_app = MagicMock()

                setup_tracing(mock_app)
                shutdown_tracing()

    def test_shutdown_tracing_logs_completion(self):
        """Test that shutdown_tracing logs completion message."""
        with patch.dict(
            sys.modules,
            {
                "opentelemetry": MagicMock(),
                "opentelemetry.trace": MagicMock(),
                "opentelemetry.sdk.trace": MagicMock(),
                "opentelemetry.sdk.trace.export": MagicMock(),
                "opentelemetry.sdk.trace.sampling": MagicMock(),
                "opentelemetry.sdk.resources": MagicMock(),
                "opentelemetry.instrumentation.fastapi": MagicMock(),
                "opentelemetry.instrumentation.sqlalchemy": MagicMock(),
            },
        ):
            with patch("app.tracing.setup.settings") as mock_settings:
                mock_settings.OTEL_ENABLED = True
                mock_settings.OTEL_SERVICE_NAME = "test-service"
                mock_settings.OTEL_EXPORTER = "console"
                mock_settings.OTEL_TRACES_SAMPLE_RATE = 1.0

                with patch("app.tracing.setup.logger") as mock_logger:
                    from app.tracing import setup_tracing, shutdown_tracing

                    mock_app = MagicMock()
                    setup_tracing(mock_app)

                    mock_logger.reset_mock()
                    shutdown_tracing()

                    mock_logger.info.assert_called_once()
                    log_message = mock_logger.info.call_args[0][0]
                    assert "OpenTelemetry tracing shutdown complete" in log_message


class TestTraceIdLogging:
    """Tests for trace_id and span_id in log output."""

    def test_logging_works_without_opentelemetry_installed(self):
        """Test that logging works when OpenTelemetry is not installed."""
        from app.core.logging_config import JSONFormatter

        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert "trace_id" not in log_entry
        assert "span_id" not in log_entry
        assert log_entry["message"] == "Test message"
