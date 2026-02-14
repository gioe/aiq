"""Tests for logging configuration module."""

import json
import logging
import tempfile
from pathlib import Path

import pytest

from app.infrastructure.logging_config import (
    ColoredFormatter,
    JSONFormatter,
    LogContext,
    get_logger,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    def test_format_basic_record(self):
        """Test formatting a basic log record."""
        formatter = JSONFormatter()
        logger = logging.getLogger("test")
        logger.setLevel(logging.INFO)

        record = logger.makeRecord(
            name="test",
            level=logging.INFO,
            fn="test.py",
            lno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert parsed["message"] == "Test message"
        assert parsed["module"] == "test"
        assert parsed["line"] == 42
        assert "timestamp" in parsed

    def test_format_with_exception(self):
        """Test formatting a record with exception info."""
        import sys

        formatter = JSONFormatter()
        logger = logging.getLogger("test")

        try:
            raise ValueError("Test error")
        except ValueError:
            exc_info = sys.exc_info()
            record = logger.makeRecord(
                name="test",
                level=logging.ERROR,
                fn="test.py",
                lno=42,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )

        formatted = formatter.format(record)
        parsed = json.loads(formatted)

        assert parsed["level"] == "ERROR"
        assert parsed["message"] == "Error occurred"
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestColoredFormatter:
    """Tests for ColoredFormatter class."""

    def test_format_with_colors(self):
        """Test formatting with color codes."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        logger = logging.getLogger("test")

        record = logger.makeRecord(
            name="test",
            level=logging.INFO,
            fn="test.py",
            lno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        formatted = formatter.format(record)

        # Should contain ANSI color codes
        assert "\033[" in formatted
        assert "Test message" in formatted

    def test_format_preserves_levelname(self):
        """Test that levelname is preserved after formatting."""
        formatter = ColoredFormatter("%(levelname)s - %(message)s")
        logger = logging.getLogger("test")

        record = logger.makeRecord(
            name="test",
            level=logging.WARNING,
            fn="test.py",
            lno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        original_levelname = record.levelname
        formatter.format(record)

        # Levelname should be restored
        assert record.levelname == original_levelname


class TestSetupLogging:
    """Tests for setup_logging function."""

    def test_setup_logging_default(self):
        """Test setting up logging with default parameters."""
        # Clear existing handlers
        logging.getLogger().handlers.clear()

        setup_logging(
            log_level="INFO",
            enable_file_logging=False,
        )

        root_logger = logging.getLogger()
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) > 0

    def test_setup_logging_with_file(self):
        """Test setting up logging with file output."""
        logging.getLogger().handlers.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"

            setup_logging(
                log_level="DEBUG",
                log_file=str(log_file),
                enable_file_logging=True,
            )

            root_logger = logging.getLogger()
            assert root_logger.level == logging.DEBUG

            # Log a test message
            root_logger.info("Test message")

            # Check that log file was created
            assert log_file.exists()

            # Check that log file contains JSON
            content = log_file.read_text()
            assert len(content) > 0

    def test_setup_logging_json_format(self):
        """Test setting up logging with JSON format."""
        logging.getLogger().handlers.clear()

        setup_logging(
            log_level="INFO",
            json_format=True,
            enable_file_logging=False,
        )

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) > 0

        # Check that console handler has JSON formatter
        console_handler = root_logger.handlers[0]
        assert isinstance(console_handler.formatter, JSONFormatter)

    def test_setup_logging_invalid_level(self):
        """Test setup with invalid log level."""
        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logging(log_level="INVALID")

    def test_setup_logging_creates_log_directory(self):
        """Test that setup creates log directory if it doesn't exist."""
        logging.getLogger().handlers.clear()

        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "subdir" / "logs" / "test.log"

            setup_logging(
                log_level="INFO",
                log_file=str(log_file),
                enable_file_logging=True,
            )

            # Log a message to trigger file creation
            logging.info("Test")

            assert log_file.parent.exists()
            assert log_file.exists()


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a logger instance."""
        logger = get_logger("test_module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_different_names(self):
        """Test that different names return different loggers."""
        logger1 = get_logger("module1")
        logger2 = get_logger("module2")

        assert logger1.name == "module1"
        assert logger2.name == "module2"
        assert logger1 is not logger2


class TestLogContext:
    """Tests for LogContext class."""

    def test_log_context_adds_extra_fields(self):
        """Test that LogContext adds extra fields to log records."""
        logging.getLogger().handlers.clear()

        # Set up logging with JSON formatter to capture extra fields
        setup_logging(
            log_level="INFO",
            json_format=True,
            enable_file_logging=False,
        )

        logger = get_logger("test")

        with LogContext(request_id="123", user_id="456"):
            # Create a log record within context
            record = logger.makeRecord(
                name="test",
                level=logging.INFO,
                fn="test.py",
                lno=42,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            # Check that extra fields were added
            assert hasattr(record, "extra")
            assert record.extra["request_id"] == "123"
            assert record.extra["user_id"] == "456"

    def test_log_context_restores_factory(self):
        """Test that LogContext restores original factory on exit."""
        original_factory = logging.getLogRecordFactory()

        with LogContext(test_key="test_value"):
            # Factory should be different inside context
            current_factory = logging.getLogRecordFactory()
            assert current_factory != original_factory

        # Factory should be restored after context
        restored_factory = logging.getLogRecordFactory()
        assert restored_factory == original_factory

    def test_log_context_nested(self):
        """Test that LogContext can be nested."""
        original_factory = logging.getLogRecordFactory()

        with LogContext(outer="value1"):
            with LogContext(inner="value2"):
                # Inner context should be active
                pass

        # Original factory should be restored
        assert logging.getLogRecordFactory() == original_factory
