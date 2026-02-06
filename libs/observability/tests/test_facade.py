"""Tests for observability facade."""

from unittest import mock

import pytest

from libs.observability.config import ObservabilityConfig, OTELConfig, SentryConfig
from libs.observability.facade import ObservabilityFacade, SpanContext


class TestObservabilityFacadeInit:
    """Tests for facade initialization."""

    def test_not_initialized_by_default(self) -> None:
        """Test facade is not initialized by default."""
        facade = ObservabilityFacade()
        assert facade.is_initialized is False

    def test_init_sets_initialized(self) -> None:
        """Test init() sets initialized flag."""
        facade = ObservabilityFacade()
        # Patch at the config module since that's where load_config is defined
        with mock.patch("libs.observability.config.load_config") as mock_load:
            mock_config = ObservabilityConfig(
                sentry=SentryConfig(enabled=False),
                otel=OTELConfig(enabled=False),
            )
            mock_load.return_value = mock_config
            facade.init()
            assert facade.is_initialized is True

    def test_init_with_disabled_backends(self) -> None:
        """Test init() with both backends disabled."""
        facade = ObservabilityFacade()
        with mock.patch("libs.observability.config.load_config") as mock_load:
            mock_config = ObservabilityConfig(
                sentry=SentryConfig(enabled=False),
                otel=OTELConfig(enabled=False),
            )
            mock_load.return_value = mock_config
            facade.init()
            # Backends should be None when disabled
            assert facade._sentry_backend is None
            assert facade._otel_backend is None


class TestFacadeWithoutInit:
    """Tests for facade methods when not initialized."""

    def test_capture_error_returns_none(self) -> None:
        """Test capture_error returns None when not initialized."""
        facade = ObservabilityFacade()
        result = facade.capture_error(ValueError("test"))
        assert result is None

    def test_capture_message_returns_none(self) -> None:
        """Test capture_message returns None when not initialized."""
        facade = ObservabilityFacade()
        result = facade.capture_message("test message")
        assert result is None

    def test_record_metric_does_nothing(self) -> None:
        """Test record_metric does nothing when not initialized."""
        facade = ObservabilityFacade()
        # Should not raise
        facade.record_metric("test.metric", 1)

    def test_start_span_yields_empty_context(self) -> None:
        """Test start_span yields empty SpanContext when not initialized."""
        facade = ObservabilityFacade()
        with facade.start_span("test") as span:
            assert isinstance(span, SpanContext)
            assert span._otel_span is None
            assert span._sentry_span is None

    def test_set_user_does_nothing(self) -> None:
        """Test set_user does nothing when not initialized."""
        facade = ObservabilityFacade()
        # Should not raise
        facade.set_user("user-123")

    def test_set_tag_does_nothing(self) -> None:
        """Test set_tag does nothing when not initialized."""
        facade = ObservabilityFacade()
        # Should not raise
        facade.set_tag("key", "value")

    def test_set_context_does_nothing(self) -> None:
        """Test set_context does nothing when not initialized."""
        facade = ObservabilityFacade()
        # Should not raise
        facade.set_context("name", {"key": "value"})

    def test_record_event_returns_none(self) -> None:
        """Test record_event returns None when not initialized."""
        facade = ObservabilityFacade()
        result = facade.record_event("test.event", data={"key": "value"})
        assert result is None

    def test_flush_does_nothing(self) -> None:
        """Test flush does nothing when not initialized."""
        facade = ObservabilityFacade()
        # Should not raise
        facade.flush()

    def test_shutdown_does_nothing(self) -> None:
        """Test shutdown does nothing when not initialized."""
        facade = ObservabilityFacade()
        # Should not raise
        facade.shutdown()


class TestSpanContext:
    """Tests for SpanContext."""

    def test_set_attribute_with_no_spans(self) -> None:
        """Test set_attribute does nothing with no spans."""
        ctx = SpanContext("test")
        # Should not raise
        ctx.set_attribute("key", "value")

    def test_set_status_with_no_spans(self) -> None:
        """Test set_status does nothing with no spans."""
        ctx = SpanContext("test")
        # Should not raise
        ctx.set_status("ok")
        ctx.set_status("error", "description")

    def test_record_exception_with_no_spans(self) -> None:
        """Test record_exception does nothing with no spans."""
        ctx = SpanContext("test")
        # Should not raise
        ctx.record_exception(ValueError("test"))

    def test_context_manager_protocol(self) -> None:
        """Test SpanContext implements context manager protocol."""
        ctx = SpanContext("test")
        with ctx as span:
            assert span is ctx

    def test_context_manager_with_exception(self) -> None:
        """Test SpanContext handles exceptions in context manager."""
        ctx = SpanContext("test")
        with pytest.raises(ValueError):
            with ctx:
                raise ValueError("test error")

    def test_add_event_with_no_spans(self) -> None:
        """Test add_event does nothing with no spans."""
        ctx = SpanContext("test")
        # Should not raise
        ctx.add_event("cache_hit")
        ctx.add_event("cache_miss", {"key": "value"})

    def test_set_attribute_with_otel_span(self) -> None:
        """Test set_attribute calls OTEL span."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        ctx.set_attribute("key", "value")

        mock_otel_span.set_attribute.assert_called_once_with("key", "value")

    def test_set_attribute_with_sentry_span(self) -> None:
        """Test set_attribute calls Sentry span."""
        mock_sentry_span = mock.MagicMock()
        ctx = SpanContext("test", sentry_span=mock_sentry_span)

        ctx.set_attribute("key", "value")

        mock_sentry_span.set_data.assert_called_once_with("key", "value")

    def test_set_attribute_with_both_spans(self) -> None:
        """Test set_attribute calls both OTEL and Sentry spans."""
        mock_otel_span = mock.MagicMock()
        mock_sentry_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span, sentry_span=mock_sentry_span)

        ctx.set_attribute("key", "value")

        mock_otel_span.set_attribute.assert_called_once_with("key", "value")
        mock_sentry_span.set_data.assert_called_once_with("key", "value")

    def test_set_status_ok_with_otel_span(self) -> None:
        """Test set_status 'ok' calls OTEL span with OK status."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        # Mock the opentelemetry.trace module that gets imported inside set_status
        mock_status_code = mock.MagicMock()
        mock_status_code.OK = "OK"
        mock_status_code.ERROR = "ERROR"

        with mock.patch.dict(
            "sys.modules",
            {"opentelemetry": mock.MagicMock(), "opentelemetry.trace": mock.MagicMock(StatusCode=mock_status_code)},
        ):
            ctx.set_status("ok")

        mock_otel_span.set_status.assert_called_once()
        call_args = mock_otel_span.set_status.call_args[0]
        assert call_args[0] == "OK"

    def test_set_status_error_with_otel_span(self) -> None:
        """Test set_status 'error' calls OTEL span with ERROR status."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        # Mock the opentelemetry.trace module that gets imported inside set_status
        mock_status_code = mock.MagicMock()
        mock_status_code.OK = "OK"
        mock_status_code.ERROR = "ERROR"

        with mock.patch.dict(
            "sys.modules",
            {"opentelemetry": mock.MagicMock(), "opentelemetry.trace": mock.MagicMock(StatusCode=mock_status_code)},
        ):
            ctx.set_status("error", "Something went wrong")

        mock_otel_span.set_status.assert_called_once()
        call_args = mock_otel_span.set_status.call_args[0]
        assert call_args[0] == "ERROR"
        assert call_args[1] == "Something went wrong"

    def test_record_exception_with_otel_span(self) -> None:
        """Test record_exception calls OTEL span."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        exc = ValueError("test error")
        ctx.record_exception(exc)

        mock_otel_span.record_exception.assert_called_once_with(exc)

    def test_add_event_with_otel_span(self) -> None:
        """Test add_event calls OTEL span."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        ctx.add_event("cache_hit", {"key": "user:123"})

        mock_otel_span.add_event.assert_called_once_with("cache_hit", attributes={"key": "user:123"})

    def test_add_event_without_attributes(self) -> None:
        """Test add_event with no attributes."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        ctx.add_event("retry_attempt")

        mock_otel_span.add_event.assert_called_once_with("retry_attempt", attributes=None)

    def test_context_manager_records_exception_on_error(self) -> None:
        """Test context manager records exception when error occurs."""
        mock_otel_span = mock.MagicMock()
        ctx = SpanContext("test", otel_span=mock_otel_span)

        with pytest.raises(ValueError):
            with ctx:
                raise ValueError("test error")

        mock_otel_span.record_exception.assert_called_once()
        mock_otel_span.set_status.assert_called_once()


class TestStartSpanWithBackends:
    """Tests for start_span with mocked backends."""

    def test_start_span_with_otel_backend_only(self) -> None:
        """Test start_span with only OTEL backend enabled."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = mock.MagicMock()
        facade._sentry_backend = None

        mock_otel_context = mock.MagicMock()
        facade._otel_backend.start_span.return_value = mock_otel_context

        mock_config = mock.MagicMock()
        mock_config.routing.traces = "otel"
        facade._config = mock_config

        with facade.start_span("test_span", attributes={"key": "value"}) as span:
            assert isinstance(span, SpanContext)

        facade._otel_backend.start_span.assert_called_once_with(
            "test_span", kind="internal", attributes={"key": "value"}
        )

    def test_start_span_with_sentry_backend_only(self) -> None:
        """Test start_span with only Sentry backend enabled."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = None
        facade._sentry_backend = mock.MagicMock()

        mock_sentry_context = mock.MagicMock()
        facade._sentry_backend.start_span.return_value = mock_sentry_context

        mock_config = mock.MagicMock()
        mock_config.routing.traces = "sentry"
        facade._config = mock_config

        with facade.start_span("test_span", attributes={"key": "value"}) as span:
            assert isinstance(span, SpanContext)

        facade._sentry_backend.start_span.assert_called_once_with(
            "test_span", attributes={"key": "value"}
        )

    def test_start_span_with_both_backends(self) -> None:
        """Test start_span with both backends enabled (routing=both)."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = mock.MagicMock()
        facade._sentry_backend = mock.MagicMock()

        mock_otel_context = mock.MagicMock()
        mock_sentry_context = mock.MagicMock()
        facade._otel_backend.start_span.return_value = mock_otel_context
        facade._sentry_backend.start_span.return_value = mock_sentry_context

        mock_config = mock.MagicMock()
        mock_config.routing.traces = "both"
        facade._config = mock_config

        with facade.start_span("test_span", kind="server", attributes={"key": "value"}) as span:
            assert isinstance(span, SpanContext)

        facade._otel_backend.start_span.assert_called_once_with(
            "test_span", kind="server", attributes={"key": "value"}
        )
        facade._sentry_backend.start_span.assert_called_once_with(
            "test_span", attributes={"key": "value"}
        )

    def test_start_span_with_different_kinds(self) -> None:
        """Test start_span with different span kinds."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = mock.MagicMock()
        facade._otel_backend.start_span.return_value = mock.MagicMock()

        mock_config = mock.MagicMock()
        mock_config.routing.traces = "otel"
        facade._config = mock_config

        for kind in ["internal", "server", "client", "producer", "consumer"]:
            with facade.start_span("test_span", kind=kind):  # type: ignore[arg-type]
                pass

            facade._otel_backend.start_span.assert_called_with(
                "test_span", kind=kind, attributes=None
            )

    def test_nested_spans(self) -> None:
        """Test nested spans work correctly."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = mock.MagicMock()

        outer_context = mock.MagicMock()
        inner_context = mock.MagicMock()
        facade._otel_backend.start_span.side_effect = [outer_context, inner_context]

        mock_config = mock.MagicMock()
        mock_config.routing.traces = "otel"
        facade._config = mock_config

        with facade.start_span("outer") as outer_span:
            assert isinstance(outer_span, SpanContext)
            with facade.start_span("inner") as inner_span:
                assert isinstance(inner_span, SpanContext)

        assert facade._otel_backend.start_span.call_count == 2


class TestFacadeCaptureMethods:
    """Tests for facade capture methods with mocked backends."""

    def test_capture_error_calls_sentry_backend(self) -> None:
        """Test capture_error delegates to Sentry backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._sentry_backend.capture_error.return_value = "event-id-123"

        exc = ValueError("test error")
        result = facade.capture_error(
            exc,
            context={"key": "value"},
            level="error",
            user={"id": "user-123"},
            tags={"tag": "value"},
            fingerprint=["custom"],
        )

        assert result == "event-id-123"
        facade._sentry_backend.capture_error.assert_called_once_with(
            exception=exc,
            context={"key": "value"},
            level="error",
            user={"id": "user-123"},
            tags={"tag": "value"},
            fingerprint=["custom"],
        )

    def test_capture_message_calls_sentry_backend(self) -> None:
        """Test capture_message delegates to Sentry backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._sentry_backend.capture_message.return_value = "event-id-456"

        result = facade.capture_message(
            "test message",
            level="warning",
            context={"key": "value"},
            tags={"tag": "value"},
        )

        assert result == "event-id-456"
        facade._sentry_backend.capture_message.assert_called_once_with(
            message="test message",
            level="warning",
            context={"key": "value"},
            tags={"tag": "value"},
        )

    def test_record_event_calls_sentry_backend(self) -> None:
        """Test record_event delegates to Sentry backend via capture_message."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._sentry_backend.capture_message.return_value = "event-id-789"

        result = facade.record_event(
            "user.signup",
            data={"user_id": "123", "method": "oauth"},
            level="info",
            tags={"source": "web"},
        )

        assert result == "event-id-789"
        facade._sentry_backend.capture_message.assert_called_once_with(
            message="Event: user.signup",
            level="info",
            context={"user_id": "123", "method": "oauth"},
            tags={"source": "web"},
        )

    def test_record_event_without_data(self) -> None:
        """Test record_event works with no data provided."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._sentry_backend.capture_message.return_value = "event-id-000"

        result = facade.record_event("test.event")

        assert result == "event-id-000"
        facade._sentry_backend.capture_message.assert_called_once_with(
            message="Event: test.event",
            level="info",
            context=None,
            tags=None,
        )

    def test_record_event_returns_none_without_sentry(self) -> None:
        """Test record_event returns None when Sentry backend is not configured."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = None

        result = facade.record_event("test.event", data={"key": "value"})

        assert result is None


class TestFacadeMetricMethods:
    """Tests for facade metric methods with mocked backends."""

    def test_record_metric_calls_otel_backend(self) -> None:
        """Test record_metric delegates to OTEL backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = mock.MagicMock()

        facade.record_metric(
            "test.metric",
            42,
            labels={"label": "value"},
            metric_type="counter",
            unit="requests",
        )

        facade._otel_backend.record_metric.assert_called_once_with(
            name="test.metric",
            value=42,
            labels={"label": "value"},
            metric_type="counter",
            unit="requests",
        )


class TestFacadeContextMethods:
    """Tests for facade context methods with mocked backends."""

    def test_set_user_calls_sentry_backend(self) -> None:
        """Test set_user delegates to Sentry backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        facade.set_user("user-123", email="test@example.com")

        facade._sentry_backend.set_user.assert_called_once_with(
            "user-123", email="test@example.com"
        )

    def test_set_user_with_all_fields(self) -> None:
        """Test set_user passes all fields to Sentry backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        facade.set_user(
            "user-123",
            username="alice",
            email="alice@example.com",
            ip_address="192.168.1.1",
        )

        facade._sentry_backend.set_user.assert_called_once_with(
            "user-123",
            username="alice",
            email="alice@example.com",
            ip_address="192.168.1.1",
        )

    def test_set_user_with_none_clears_user(self) -> None:
        """Test set_user with None clears user context."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        facade.set_user(None)

        facade._sentry_backend.set_user.assert_called_once_with(None)

    def test_set_tag_calls_sentry_backend(self) -> None:
        """Test set_tag delegates to Sentry backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        facade.set_tag("key", "value")

        facade._sentry_backend.set_tag.assert_called_once_with("key", "value")

    def test_set_context_calls_sentry_backend(self) -> None:
        """Test set_context delegates to Sentry backend."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        facade.set_context("request", {"url": "/test"})

        facade._sentry_backend.set_context.assert_called_once_with(
            "request", {"url": "/test"}
        )


class TestFacadeLifecycleMethods:
    """Tests for facade flush and shutdown methods."""

    def test_flush_calls_both_backends(self) -> None:
        """Test flush calls both backends."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._otel_backend = mock.MagicMock()

        facade.flush(timeout=5.0)

        facade._sentry_backend.flush.assert_called_once_with(5.0)
        facade._otel_backend.flush.assert_called_once_with(5.0)

    def test_shutdown_calls_both_backends(self) -> None:
        """Test shutdown calls both backends and clears initialized flag."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._otel_backend = mock.MagicMock()

        facade.shutdown()

        facade._sentry_backend.shutdown.assert_called_once()
        facade._otel_backend.shutdown.assert_called_once()
        assert facade.is_initialized is False


class TestAPIContract:
    """Tests validating the public API contract."""

    def test_facade_has_all_required_methods(self) -> None:
        """Test ObservabilityFacade exposes all required API methods."""
        facade = ObservabilityFacade()

        # Core methods
        assert callable(getattr(facade, "init", None))
        assert callable(getattr(facade, "capture_error", None))
        assert callable(getattr(facade, "capture_message", None))
        assert callable(getattr(facade, "record_metric", None))
        assert callable(getattr(facade, "start_span", None))
        assert callable(getattr(facade, "get_trace_context", None))

        # Context methods
        assert callable(getattr(facade, "set_user", None))
        assert callable(getattr(facade, "set_tag", None))
        assert callable(getattr(facade, "set_context", None))
        assert callable(getattr(facade, "record_event", None))

        # Lifecycle methods
        assert callable(getattr(facade, "flush", None))
        assert callable(getattr(facade, "shutdown", None))

        # Properties
        assert hasattr(facade, "is_initialized")

    def test_span_context_has_all_required_methods(self) -> None:
        """Test SpanContext exposes all required methods."""
        ctx = SpanContext("test")

        assert callable(getattr(ctx, "set_attribute", None))
        assert callable(getattr(ctx, "set_status", None))
        assert callable(getattr(ctx, "record_exception", None))
        assert callable(getattr(ctx, "add_event", None))
        assert callable(getattr(ctx, "__enter__", None))
        assert callable(getattr(ctx, "__exit__", None))

    def test_module_exports_singleton(self) -> None:
        """Test the module exports a singleton observability instance."""
        from libs.observability import observability

        assert isinstance(observability, ObservabilityFacade)

    def test_module_exports_facade_class(self) -> None:
        """Test the module exports the ObservabilityFacade class."""
        from libs.observability import ObservabilityFacade as ExportedFacade

        assert ExportedFacade is ObservabilityFacade

    def test_init_accepts_required_parameters(self) -> None:
        """Test init() accepts the documented parameters."""
        facade = ObservabilityFacade()
        with mock.patch("libs.observability.config.load_config") as mock_load:
            from libs.observability.config import ObservabilityConfig, OTELConfig, SentryConfig

            mock_load.return_value = ObservabilityConfig(
                sentry=SentryConfig(enabled=False),
                otel=OTELConfig(enabled=False),
            )
            # Should not raise
            facade.init(
                config_path="config/test.yaml",
                service_name="test-service",
                environment="test",
            )

    def test_capture_error_accepts_required_parameters(self) -> None:
        """Test capture_error() accepts the documented parameters."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()
        facade._sentry_backend.capture_error.return_value = "event-id"

        # All parameters should be accepted without error
        facade.capture_error(
            ValueError("test"),
            context={"key": "value"},
            level="error",
            user={"id": "user-123"},
            tags={"tag": "value"},
            fingerprint=["custom", "fingerprint"],
        )

    def test_record_metric_accepts_required_parameters(self) -> None:
        """Test record_metric() accepts the documented parameters."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._otel_backend = mock.MagicMock()

        # All parameters should be accepted without error
        facade.record_metric(
            "test.metric",
            42.0,
            labels={"label": "value"},
            metric_type="histogram",
            unit="ms",
        )

    def test_start_span_accepts_required_parameters(self) -> None:
        """Test start_span() accepts the documented parameters."""
        facade = ObservabilityFacade()
        # Not initialized, but should accept parameters

        with facade.start_span(
            "test_span",
            kind="server",
            attributes={"key": "value"},
        ):
            pass  # Just testing parameter acceptance

    def test_set_user_accepts_required_parameters(self) -> None:
        """Test set_user() accepts the documented parameters."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        # All parameters should be accepted without error
        facade.set_user(
            "user-123",
            username="alice",
            email="alice@example.com",
        )

    def test_record_event_accepts_required_parameters(self) -> None:
        """Test record_event() accepts the documented parameters."""
        facade = ObservabilityFacade()
        facade._initialized = True
        facade._sentry_backend = mock.MagicMock()

        # All parameters should be accepted without error
        facade.record_event(
            "test.event",
            data={"key": "value"},
            level="info",
            tags={"tag": "value"},
        )


class TestTraceContextIntegration:
    """Tests for get_trace_context() method."""

    def test_get_trace_context_returns_none_when_not_initialized(self) -> None:
        """Test get_trace_context returns None values when not initialized."""
        facade = ObservabilityFacade()
        result = facade.get_trace_context()

        assert result == {"trace_id": None, "span_id": None}

    def test_get_trace_context_returns_none_when_no_active_span(self) -> None:
        """Test get_trace_context returns None when no active span."""
        facade = ObservabilityFacade()
        facade._initialized = True

        result = facade.get_trace_context()

        assert result == {"trace_id": None, "span_id": None}

    def test_get_trace_context_with_active_span(self) -> None:
        """Test get_trace_context returns trace and span IDs from active span."""
        import sys

        facade = ObservabilityFacade()
        facade._initialized = True

        # Create mock OTEL objects
        mock_span = mock.MagicMock()
        mock_span_context = mock.MagicMock()
        mock_span_context.trace_id = 0x12345678901234567890123456789012
        mock_span_context.span_id = 0x1234567890123456
        mock_span_context.is_valid = True
        mock_span.get_span_context.return_value = mock_span_context

        # Create mock trace module
        mock_trace_module = mock.MagicMock()
        mock_trace_module.get_current_span.return_value = mock_span

        # Create mock opentelemetry package
        mock_otel = mock.MagicMock()
        mock_otel.trace = mock_trace_module

        # Store original sys.modules state
        original_modules = sys.modules.copy()

        try:
            # Install mocks in sys.modules before the import happens
            sys.modules["opentelemetry"] = mock_otel
            sys.modules["opentelemetry.trace"] = mock_trace_module

            result = facade.get_trace_context()

            assert result["trace_id"] == "12345678901234567890123456789012"
            assert result["span_id"] == "1234567890123456"
        finally:
            # Restore original sys.modules
            sys.modules.clear()
            sys.modules.update(original_modules)

    def test_get_trace_context_handles_invalid_span_context(self) -> None:
        """Test get_trace_context returns None for invalid span context."""
        facade = ObservabilityFacade()
        facade._initialized = True

        # Mock the OTEL trace module with invalid span context
        mock_trace_module = mock.MagicMock()
        mock_span = mock.MagicMock()
        mock_span_context = mock.MagicMock()
        mock_span_context.is_valid = False
        mock_span.get_span_context.return_value = mock_span_context
        mock_trace_module.get_current_span.return_value = mock_span

        with mock.patch.dict("sys.modules", {"opentelemetry": mock.MagicMock(), "opentelemetry.trace": mock_trace_module}):
            result = facade.get_trace_context()

            assert result == {"trace_id": None, "span_id": None}

    def test_get_trace_context_handles_exception_gracefully(self) -> None:
        """Test get_trace_context handles exceptions gracefully."""
        facade = ObservabilityFacade()
        facade._initialized = True

        # Mock the OTEL trace module to raise an exception
        mock_trace_module = mock.MagicMock()
        mock_trace_module.get_current_span.side_effect = RuntimeError("OTEL not available")

        with mock.patch.dict("sys.modules", {"opentelemetry": mock.MagicMock(), "opentelemetry.trace": mock_trace_module}):
            result = facade.get_trace_context()

            assert result == {"trace_id": None, "span_id": None}
