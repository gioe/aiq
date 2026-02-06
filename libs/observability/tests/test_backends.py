"""Tests for backend implementations."""

import sys
from unittest import mock

import pytest

from libs.observability.config import OTELConfig, SentryConfig
from libs.observability.otel_backend import OTELBackend
from libs.observability.sentry_backend import SentryBackend

# Check if sentry_sdk is available
try:
    import sentry_sdk

    HAS_SENTRY_SDK = True
except ImportError:
    HAS_SENTRY_SDK = False

requires_sentry_sdk = pytest.mark.skipif(
    not HAS_SENTRY_SDK, reason="sentry_sdk not installed"
)


class TestSentryBackendInit:
    """Tests for Sentry backend initialization."""

    def test_disabled_backend_does_not_init(self) -> None:
        """Test disabled backend skips SDK initialization and returns False."""
        config = SentryConfig(enabled=False, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        result = backend.init()
        assert result is False
        assert backend._initialized is False

    def test_no_dsn_does_not_init(self) -> None:
        """Test backend without DSN skips initialization and returns False."""
        config = SentryConfig(enabled=True, dsn=None)
        backend = SentryBackend(config)
        result = backend.init()
        assert result is False
        assert backend._initialized is False

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.init")
    def test_init_calls_sentry_sdk(self, mock_init: mock.MagicMock) -> None:
        """Test init() calls sentry_sdk.init with correct params."""
        config = SentryConfig(
            enabled=True,
            dsn="https://test@sentry.io/123",
            environment="production",
            release="1.0.0",
            traces_sample_rate=0.5,
            profiles_sample_rate=0.1,
            send_default_pii=True,
        )
        backend = SentryBackend(config)
        result = backend.init()

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args[1]
        assert call_kwargs["dsn"] == "https://test@sentry.io/123"
        assert call_kwargs["environment"] == "production"
        assert call_kwargs["release"] == "1.0.0"
        assert call_kwargs["traces_sample_rate"] == 0.5
        assert call_kwargs["profiles_sample_rate"] == 0.1
        assert call_kwargs["send_default_pii"] is True
        assert result is True
        assert backend._initialized is True

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.init")
    def test_init_returns_true_on_success(self, mock_init: mock.MagicMock) -> None:
        """Test init() returns True on successful initialization."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        result = backend.init()

        assert result is True
        assert backend._initialized is True
        mock_init.assert_called_once()

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.init")
    def test_init_includes_fastapi_integration(self, mock_init: mock.MagicMock) -> None:
        """Test init() includes FastAPI integration when available."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend.init()

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args[1]
        integrations = call_kwargs["integrations"]

        # Check that FastApiIntegration is in the list
        integration_types = [type(i).__name__ for i in integrations]
        assert "FastApiIntegration" in integration_types

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.init")
    def test_init_includes_starlette_integration(self, mock_init: mock.MagicMock) -> None:
        """Test init() includes Starlette integration when available."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend.init()

        mock_init.assert_called_once()
        call_kwargs = mock_init.call_args[1]
        integrations = call_kwargs["integrations"]

        # Check that StarletteIntegration is in the list
        integration_types = [type(i).__name__ for i in integrations]
        assert "StarletteIntegration" in integration_types

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.init")
    def test_init_logs_success(self, mock_init: mock.MagicMock) -> None:
        """Test init() logs INFO message on successful initialization."""
        config = SentryConfig(
            enabled=True,
            dsn="https://test@sentry.io/123",
            environment="production",
            traces_sample_rate=0.5,
        )
        backend = SentryBackend(config)

        with mock.patch("libs.observability.sentry_backend.logger") as mock_logger:
            backend.init()
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "production" in log_message
            assert "50%" in log_message

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.init")
    def test_init_returns_false_on_error(self, mock_init: mock.MagicMock) -> None:
        """Test init() returns False and logs error when initialization fails."""
        mock_init.side_effect = RuntimeError("SDK init failed")
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)

        with mock.patch("libs.observability.sentry_backend.logger") as mock_logger:
            result = backend.init()

            assert result is False
            assert backend._initialized is False
            mock_logger.error.assert_called_once()

    def test_init_logs_debug_when_disabled(self) -> None:
        """Test init() logs DEBUG message when disabled."""
        config = SentryConfig(enabled=False, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)

        with mock.patch("libs.observability.sentry_backend.logger") as mock_logger:
            backend.init()
            mock_logger.debug.assert_called_once()


class TestSentryBackendCapture:
    """Tests for Sentry backend capture methods."""

    def test_capture_error_when_not_initialized(self) -> None:
        """Test capture_error returns None when not initialized."""
        config = SentryConfig(enabled=False)
        backend = SentryBackend(config)
        result = backend.capture_error(ValueError("test"))
        assert result is None

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.capture_exception")
    @mock.patch("sentry_sdk.push_scope")
    def test_capture_error_calls_sdk(
        self, mock_push_scope: mock.MagicMock, mock_capture: mock.MagicMock
    ) -> None:
        """Test capture_error calls SDK with correct parameters."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend._initialized = True

        mock_scope = mock.MagicMock()
        mock_push_scope.return_value.__enter__ = mock.MagicMock(return_value=mock_scope)
        mock_push_scope.return_value.__exit__ = mock.MagicMock(return_value=False)
        mock_capture.return_value = "event-id"

        exc = ValueError("test")
        result = backend.capture_error(
            exc,
            context={"key": "value"},
            level="warning",
            user={"id": "123"},
            tags={"tag": "val"},
            fingerprint=["custom"],
        )

        assert result == "event-id"
        mock_scope.set_context.assert_called_once_with("additional", {"key": "value"})
        mock_scope.set_user.assert_called_once_with({"id": "123"})
        mock_scope.set_tag.assert_called_once_with("tag", "val")
        assert mock_scope.fingerprint == ["custom"]
        assert mock_scope.level == "warning"

    def test_capture_message_when_not_initialized(self) -> None:
        """Test capture_message returns None when not initialized."""
        config = SentryConfig(enabled=False)
        backend = SentryBackend(config)
        result = backend.capture_message("test")
        assert result is None


class TestSentryBackendContext:
    """Tests for Sentry backend context methods."""

    def test_set_user_when_not_initialized(self) -> None:
        """Test set_user does nothing when not initialized."""
        config = SentryConfig(enabled=False)
        backend = SentryBackend(config)
        # Should not raise
        backend.set_user("user-123")

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.set_user")
    def test_set_user_calls_sdk(self, mock_set_user: mock.MagicMock) -> None:
        """Test set_user calls SDK."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend._initialized = True

        backend.set_user("user-123", email="test@example.com")
        mock_set_user.assert_called_once_with({"id": "user-123", "email": "test@example.com"})

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.set_user")
    def test_set_user_none_clears_user(self, mock_set_user: mock.MagicMock) -> None:
        """Test set_user(None) clears user context."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend._initialized = True

        backend.set_user(None)
        mock_set_user.assert_called_once_with(None)

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.set_tag")
    def test_set_tag_calls_sdk(self, mock_set_tag: mock.MagicMock) -> None:
        """Test set_tag calls SDK."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend._initialized = True

        backend.set_tag("key", "value")
        mock_set_tag.assert_called_once_with("key", "value")

    @requires_sentry_sdk
    @mock.patch("sentry_sdk.set_context")
    def test_set_context_calls_sdk(self, mock_set_context: mock.MagicMock) -> None:
        """Test set_context calls SDK."""
        config = SentryConfig(enabled=True, dsn="https://test@sentry.io/123")
        backend = SentryBackend(config)
        backend._initialized = True

        backend.set_context("request", {"url": "/test"})
        mock_set_context.assert_called_once_with("request", {"url": "/test"})


class TestOTELBackendInit:
    """Tests for OTEL backend initialization."""

    def test_disabled_backend_does_not_init(self) -> None:
        """Test disabled backend skips initialization."""
        config = OTELConfig(enabled=False)
        backend = OTELBackend(config)
        backend.init()
        assert backend._initialized is False

    def test_disabled_metrics_skips_meter(self) -> None:
        """Test disabled metrics skips meter provider setup."""
        config = OTELConfig(enabled=True, metrics_enabled=False, traces_enabled=False)
        backend = OTELBackend(config)
        backend.init()
        assert backend._meter_provider is None

    def test_disabled_traces_skips_tracer(self) -> None:
        """Test disabled traces skips tracer provider setup."""
        config = OTELConfig(enabled=True, metrics_enabled=False, traces_enabled=False)
        backend = OTELBackend(config)
        backend.init()
        assert backend._tracer_provider is None


class TestOTELBackendMetrics:
    """Tests for OTEL backend metrics recording."""

    def test_record_metric_when_not_initialized(self) -> None:
        """Test record_metric does nothing when not initialized."""
        config = OTELConfig(enabled=False)
        backend = OTELBackend(config)
        # Should not raise
        backend.record_metric("test.metric", 1)

    def test_record_metric_counter_creates_instrument(self) -> None:
        """Test record_metric creates counter instrument."""
        config = OTELConfig(enabled=True, metrics_enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter = mock.MagicMock()
        mock_counter = mock.MagicMock()
        backend._meter.create_counter.return_value = mock_counter

        backend.record_metric("test.counter", 5, metric_type="counter")

        backend._meter.create_counter.assert_called_once_with(
            name="test.counter",
            unit="1",
            description="Counter for test.counter",
        )
        mock_counter.add.assert_called_once_with(5, attributes={})

    def test_record_metric_reuses_counter(self) -> None:
        """Test record_metric reuses existing counter."""
        config = OTELConfig(enabled=True, metrics_enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter = mock.MagicMock()
        mock_counter = mock.MagicMock()
        backend._counters["test.counter"] = mock_counter

        backend.record_metric("test.counter", 5, metric_type="counter")

        # Should not create new counter
        backend._meter.create_counter.assert_not_called()
        mock_counter.add.assert_called_once_with(5, attributes={})

    def test_record_metric_histogram(self) -> None:
        """Test record_metric creates histogram instrument."""
        config = OTELConfig(enabled=True, metrics_enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter = mock.MagicMock()
        mock_histogram = mock.MagicMock()
        backend._meter.create_histogram.return_value = mock_histogram

        backend.record_metric("test.duration", 0.5, metric_type="histogram", unit="s")

        backend._meter.create_histogram.assert_called_once_with(
            name="test.duration",
            unit="s",
            description="Histogram for test.duration",
        )
        mock_histogram.record.assert_called_once_with(0.5, attributes={})

    def test_record_metric_with_labels(self) -> None:
        """Test record_metric passes labels as attributes."""
        config = OTELConfig(enabled=True, metrics_enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter = mock.MagicMock()
        mock_counter = mock.MagicMock()
        backend._meter.create_counter.return_value = mock_counter

        backend.record_metric(
            "test.counter",
            1,
            labels={"service": "api", "endpoint": "/test"},
            metric_type="counter",
        )

        mock_counter.add.assert_called_once_with(
            1, attributes={"service": "api", "endpoint": "/test"}
        )


class TestOTELBackendTracing:
    """Tests for OTEL backend tracing."""

    def test_start_span_when_not_initialized(self) -> None:
        """Test start_span yields None when not initialized."""
        config = OTELConfig(enabled=False)
        backend = OTELBackend(config)

        with backend.start_span("test") as span:
            assert span is None

    def test_start_span_when_no_tracer(self) -> None:
        """Test start_span yields None when tracer is None."""
        config = OTELConfig(enabled=True, traces_enabled=False)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._tracer = None

        with backend.start_span("test") as span:
            assert span is None


class TestOTELBackendLifecycle:
    """Tests for OTEL backend lifecycle methods."""

    def test_flush_when_not_initialized(self) -> None:
        """Test flush does nothing when not initialized."""
        config = OTELConfig(enabled=False)
        backend = OTELBackend(config)
        # Should not raise
        backend.flush()

    def test_flush_calls_providers(self) -> None:
        """Test flush calls force_flush on providers."""
        config = OTELConfig(enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter_provider = mock.MagicMock()
        backend._tracer_provider = mock.MagicMock()

        backend.flush(timeout=5.0)

        backend._meter_provider.force_flush.assert_called_once_with(timeout_millis=5000)
        backend._tracer_provider.force_flush.assert_called_once_with(timeout_millis=5000)

    def test_shutdown_when_not_initialized(self) -> None:
        """Test shutdown does nothing when not initialized."""
        config = OTELConfig(enabled=False)
        backend = OTELBackend(config)
        # Should not raise
        backend.shutdown()

    def test_shutdown_calls_providers(self) -> None:
        """Test shutdown calls shutdown on providers."""
        config = OTELConfig(enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter_provider = mock.MagicMock()
        backend._tracer_provider = mock.MagicMock()

        backend.shutdown()

        backend._meter_provider.shutdown.assert_called_once()
        backend._tracer_provider.shutdown.assert_called_once()
        assert backend._initialized is False

    def test_flush_logs_warning_on_error(self) -> None:
        """Test flush logs warning when provider flush fails."""
        config = OTELConfig(enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter_provider = mock.MagicMock()
        backend._meter_provider.force_flush.side_effect = RuntimeError("flush failed")

        # Should not raise, should log warning
        with mock.patch("libs.observability.otel_backend.logger") as mock_logger:
            backend.flush()
            mock_logger.warning.assert_called()

    def test_shutdown_logs_warning_on_error(self) -> None:
        """Test shutdown logs warning when provider shutdown fails."""
        config = OTELConfig(enabled=True)
        backend = OTELBackend(config)
        backend._initialized = True
        backend._meter_provider = mock.MagicMock()
        backend._meter_provider.shutdown.side_effect = RuntimeError("shutdown failed")

        # Should not raise, should log warning
        with mock.patch("libs.observability.otel_backend.logger") as mock_logger:
            backend.shutdown()
            mock_logger.warning.assert_called()
