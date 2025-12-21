"""
Tests for graceful_failure module (BCQ-017).

This module tests the graceful_failure context manager and decorator
for handling non-critical operations that should not block execution.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from app.core.graceful_failure import (
    GracefulFailureDecorator,
    graceful_failure,
    graceful_failure_decorator,
)


@pytest.fixture
def mock_logger():
    """Create a mock logger for testing."""
    return MagicMock(spec=logging.Logger)


class TestGracefulFailureContextManager:
    """Tests for the graceful_failure context manager."""

    def test_success_case_no_exception(self, mock_logger):
        """Test that code executes normally when no exception occurs."""
        result = []

        with graceful_failure("test operation", mock_logger):
            result.append("executed")

        assert result == ["executed"]
        mock_logger.log.assert_not_called()

    def test_exception_is_swallowed(self, mock_logger):
        """Test that exceptions are swallowed and don't propagate."""
        result = []

        with graceful_failure("failing operation", mock_logger):
            raise ValueError("test error")

        # Should continue execution after the context manager
        result.append("continued")
        assert result == ["continued"]

    def test_logs_exception_with_default_warning_level(self, mock_logger):
        """Test that exceptions are logged at WARNING level by default."""
        with graceful_failure("test operation", mock_logger):
            raise ValueError("something went wrong")

        mock_logger.log.assert_called_once()
        call_args = mock_logger.log.call_args
        assert call_args[0][0] == logging.WARNING
        assert "Failed to test operation" in call_args[0][1]
        assert "something went wrong" in call_args[0][1]

    def test_custom_log_level(self, mock_logger):
        """Test custom logging level."""
        with graceful_failure(
            "important operation", mock_logger, log_level=logging.ERROR
        ):
            raise ValueError("critical issue")

        call_args = mock_logger.log.call_args
        assert call_args[0][0] == logging.ERROR

    def test_exc_info_disabled_by_default(self, mock_logger):
        """Test that exc_info is False by default."""
        with graceful_failure("test operation", mock_logger):
            raise ValueError("error")

        call_args = mock_logger.log.call_args
        assert call_args[1]["exc_info"] is False

    def test_exc_info_enabled(self, mock_logger):
        """Test that exc_info can be enabled for stack traces."""
        with graceful_failure("test operation", mock_logger, exc_info=True):
            raise ValueError("error with trace")

        call_args = mock_logger.log.call_args
        assert call_args[1]["exc_info"] is True

    def test_context_in_log_message(self, mock_logger):
        """Test that context is included in log message."""
        with graceful_failure(
            "update stats",
            mock_logger,
            context={"session_id": 123, "question_id": 456},
        ):
            raise ValueError("database error")

        call_args = mock_logger.log.call_args
        log_message = call_args[0][1]
        assert "session_id=123" in log_message
        assert "question_id=456" in log_message
        assert "Failed to update stats" in log_message

    def test_context_without_exception(self, mock_logger):
        """Test that context doesn't affect normal execution."""
        result = []

        with graceful_failure(
            "test operation",
            mock_logger,
            context={"key": "value"},
        ):
            result.append("executed")

        assert result == ["executed"]
        mock_logger.log.assert_not_called()

    def test_multiple_exceptions_in_sequence(self, mock_logger):
        """Test multiple graceful failures in sequence."""
        results = []

        with graceful_failure("first operation", mock_logger):
            raise ValueError("first error")

        results.append("after first")

        with graceful_failure("second operation", mock_logger):
            raise ValueError("second error")

        results.append("after second")

        assert results == ["after first", "after second"]
        assert mock_logger.log.call_count == 2

    def test_different_exception_types(self, mock_logger):
        """Test various exception types are handled."""
        exception_types = [
            ValueError("value error"),
            TypeError("type error"),
            RuntimeError("runtime error"),
            KeyError("missing key"),
        ]

        for exc in exception_types:
            with graceful_failure("test operation", mock_logger):
                raise exc

        assert mock_logger.log.call_count == len(exception_types)


class TestGracefulFailureDecorator:
    """Tests for the GracefulFailureDecorator class."""

    def test_decorator_success(self):
        """Test decorated function executes successfully."""
        logger = MagicMock(spec=logging.Logger)

        @graceful_failure_decorator("test operation", logger=logger)
        def my_function():
            return "success"

        result = my_function()
        assert result == "success"
        logger.log.assert_not_called()

    def test_decorator_returns_default_on_error(self):
        """Test decorated function returns default value on error."""
        logger = MagicMock(spec=logging.Logger)

        @graceful_failure_decorator("failing operation", logger=logger)
        def failing_function():
            raise ValueError("error")

        result = failing_function()
        assert result is None  # Default is None
        logger.log.assert_called_once()

    def test_decorator_custom_default_value(self):
        """Test decorator with custom default return value."""
        logger = MagicMock(spec=logging.Logger)

        @graceful_failure_decorator("operation with default", logger=logger, default={})
        def get_data():
            raise ValueError("error")

        result = get_data()
        assert result == {}

    def test_decorator_custom_log_level(self):
        """Test decorator with custom log level."""
        logger = MagicMock(spec=logging.Logger)

        @graceful_failure_decorator(
            "important operation",
            logger=logger,
            log_level=logging.ERROR,
        )
        def important_function():
            raise ValueError("critical error")

        important_function()

        call_args = logger.log.call_args
        assert call_args[0][0] == logging.ERROR

    def test_decorator_with_exc_info(self):
        """Test decorator with exc_info enabled."""
        logger = MagicMock(spec=logging.Logger)

        @graceful_failure_decorator(
            "debug operation",
            logger=logger,
            exc_info=True,
        )
        def debug_function():
            raise ValueError("error for debugging")

        debug_function()

        call_args = logger.log.call_args
        assert call_args[1]["exc_info"] is True

    def test_decorator_uses_module_logger_when_not_provided(self):
        """Test decorator uses module logger when none is provided."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = MagicMock(spec=logging.Logger)
            mock_get_logger.return_value = mock_logger

            @graceful_failure_decorator("test operation")
            def my_function():
                raise ValueError("error")

            my_function()

            mock_get_logger.assert_called_once()
            mock_logger.log.assert_called_once()

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @graceful_failure_decorator("test operation")
        def documented_function():
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."

    def test_decorator_with_arguments(self):
        """Test decorator with function that has arguments."""
        logger = MagicMock(spec=logging.Logger)

        @graceful_failure_decorator("operation with args", logger=logger)
        def function_with_args(a, b, c=None):
            return (a, b, c)

        result = function_with_args("x", "y", c="z")
        assert result == ("x", "y", "z")

    def test_decorator_with_arguments_on_failure(self):
        """Test decorator passes args correctly even when failing."""
        logger = MagicMock(spec=logging.Logger)
        received_args = []

        @graceful_failure_decorator(
            "operation with args", logger=logger, default="failed"
        )
        def function_with_args(a, b):
            received_args.extend([a, b])
            raise ValueError("error")

        result = function_with_args("arg1", "arg2")
        assert result == "failed"
        assert received_args == ["arg1", "arg2"]

    def test_alias_exists(self):
        """Test that graceful_failure_decorator alias exists and works."""
        assert graceful_failure_decorator is GracefulFailureDecorator


class TestGracefulFailureIntegration:
    """Integration tests for graceful_failure in realistic scenarios."""

    def test_variables_set_inside_context_persist(self, mock_logger):
        """Test that variables set before an exception are preserved."""
        result = None

        with graceful_failure("set and fail", mock_logger):
            result = "partial value"
            raise ValueError("error after setting")

        assert result == "partial value"

    def test_variables_not_set_on_early_exception(self, mock_logger):
        """Test that variables not set before exception remain unset."""
        result = None

        with graceful_failure("fail before set", mock_logger):
            raise ValueError("error before setting")
            result = "should not reach"  # noqa: F841

        assert result is None

    def test_nested_graceful_failures(self, mock_logger):
        """Test nested graceful failure contexts."""
        results = []

        with graceful_failure("outer operation", mock_logger):
            results.append("outer start")
            with graceful_failure("inner operation", mock_logger):
                results.append("inner start")
                raise ValueError("inner error")
            results.append("after inner")

        results.append("after outer")

        assert results == ["outer start", "inner start", "after inner", "after outer"]
        assert mock_logger.log.call_count == 1  # Only inner logged

    def test_outer_fails_with_nested(self, mock_logger):
        """Test outer context fails with nested context."""
        results = []

        with graceful_failure("outer operation", mock_logger):
            results.append("outer start")
            with graceful_failure("inner operation", mock_logger):
                results.append("inner")
            raise ValueError("outer error")

        results.append("after outer")

        assert results == ["outer start", "inner", "after outer"]
        assert mock_logger.log.call_count == 1  # Only outer logged
