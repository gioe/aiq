"""
Tests for structured logging configuration and JSON formatter.
"""
import json
import logging
from unittest.mock import patch

import pytest

from app.core.logging_config import (
    JSONFormatter,
    request_id_context,
    setup_logging,
    get_logger,
)


class TestJSONFormatter:
    """Tests for the JSONFormatter class."""

    def test_basic_log_entry(self):
        """Test that basic log entry produces valid JSON with required fields."""
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

        assert "timestamp" in log_entry
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test_logger"
        assert log_entry["message"] == "Test message"

    def test_request_id_from_context(self):
        """Test that request_id is included when set in context."""
        formatter = JSONFormatter()

        # Set request_id in context
        token = request_id_context.set("test-request-123")
        try:
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

            assert log_entry["request_id"] == "test-request-123"
        finally:
            request_id_context.reset(token)

    def test_no_request_id_when_not_set(self):
        """Test that request_id is omitted when not set."""
        formatter = JSONFormatter()

        # Ensure context is clear
        token = request_id_context.set(None)
        try:
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

            assert "request_id" not in log_entry
        finally:
            request_id_context.reset(token)

    def test_structured_fields_from_extra(self):
        """Test that extra structured fields are included in log entry."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Request completed",
            args=(),
            exc_info=None,
        )
        # Add extra fields like the middleware does
        record.method = "GET"
        record.path = "/v1/health"
        record.status_code = 200
        record.duration_ms = 15.5
        record.client_host = "127.0.0.1"
        record.user_identifier = "anonymous"

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["method"] == "GET"
        assert log_entry["path"] == "/v1/health"
        assert log_entry["status_code"] == 200
        assert log_entry["duration_ms"] == pytest.approx(15.5)
        assert log_entry["client_host"] == "127.0.0.1"
        assert log_entry["user_identifier"] == "anonymous"

    def test_source_location_for_errors(self):
        """Test that source location is included for error-level logs."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="/app/api/endpoint.py",
            lineno=42,
            msg="An error occurred",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["source"] == "/app/api/endpoint.py:42"

    def test_no_source_location_for_info(self):
        """Test that source location is not included for info-level logs."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="/app/api/endpoint.py",
            lineno=42,
            msg="Info message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert "source" not in log_entry

    def test_exception_info_included(self):
        """Test that exception info is included when present."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=10,
                msg="An error occurred",
                args=(),
                exc_info=exc_info,
            )

            result = formatter.format(record)
            log_entry = json.loads(result)

            assert "exception" in log_entry
            assert "ValueError" in log_entry["exception"]
            assert "Test error" in log_entry["exception"]

    def test_timestamp_is_iso_format(self):
        """Test that timestamp is in ISO format with timezone."""
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

        # ISO format should contain date separator and have timezone
        assert "T" in log_entry["timestamp"]
        # UTC timestamps end with +00:00 or Z
        assert "+00:00" in log_entry["timestamp"] or log_entry["timestamp"].endswith(
            "Z"
        )


class TestSetupLogging:
    """Tests for the setup_logging function."""

    @patch("app.core.logging_config.settings")
    def test_production_uses_json_formatter(self, mock_settings):
        """Test that production environment uses JSON formatter."""
        mock_settings.ENV = "production"
        mock_settings.DEBUG = False
        mock_settings.LOG_LEVEL = "INFO"

        with patch("logging.config.dictConfig") as mock_dictconfig:
            setup_logging()

            call_args = mock_dictconfig.call_args[0][0]
            assert call_args["handlers"]["console"]["formatter"] == "json"

    @patch("app.core.logging_config.settings")
    def test_development_uses_default_formatter(self, mock_settings):
        """Test that development environment uses human-readable formatter."""
        mock_settings.ENV = "development"
        mock_settings.DEBUG = True
        mock_settings.LOG_LEVEL = "DEBUG"

        with patch("logging.config.dictConfig") as mock_dictconfig:
            setup_logging()

            call_args = mock_dictconfig.call_args[0][0]
            assert call_args["handlers"]["console"]["formatter"] == "default"


class TestGetLogger:
    """Tests for the get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_same_instance(self):
        """Test that get_logger returns the same instance for same name."""
        logger1 = get_logger("same_name")
        logger2 = get_logger("same_name")

        assert logger1 is logger2


class TestRequestIdContext:
    """Tests for the request_id context variable."""

    def test_default_is_none(self):
        """Test that default value is None."""
        # Reset to default
        token = request_id_context.set(None)
        request_id_context.reset(token)

        assert request_id_context.get() is None

    def test_set_and_get(self):
        """Test setting and getting request_id."""
        token = request_id_context.set("my-request-id")
        try:
            assert request_id_context.get() == "my-request-id"
        finally:
            request_id_context.reset(token)

    def test_context_isolation(self):
        """Test that context is isolated between resets."""
        original = request_id_context.get()

        token = request_id_context.set("temporary-id")
        assert request_id_context.get() == "temporary-id"

        request_id_context.reset(token)
        assert request_id_context.get() == original
