"""
Tests for db_error_handling module (BCQ-013).

This module tests the handle_db_error context manager and related utilities
for consistent database error handling.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.db_error_handling import (
    DatabaseOperationError,
    HandleDbErrorDecorator,
    handle_db_error,
    handle_db_error_decorator,
)


def create_mock_db():
    """Create a MagicMock that passes isinstance(mock, Session) check."""
    return MagicMock(spec=Session)


class TestDatabaseOperationError:
    """Tests for the DatabaseOperationError exception class."""

    def test_basic_initialization(self):
        """Test basic exception initialization."""
        original = ValueError("original error")
        error = DatabaseOperationError(
            operation_name="create user",
            original_error=original,
        )

        assert error.operation_name == "create user"
        assert error.original_error is original
        assert "Failed to create user" in error.message
        assert "original error" in error.message

    def test_custom_message(self):
        """Test exception with custom message."""
        error = DatabaseOperationError(
            operation_name="update profile",
            original_error=ValueError("db error"),
            message="Custom error message",
        )

        assert error.message == "Custom error message"
        assert str(error) == "Custom error message"

    def test_default_message_format(self):
        """Test default message format."""
        error = DatabaseOperationError(
            operation_name="delete record",
            original_error=ValueError("constraint violation"),
        )

        assert error.message == "Failed to delete record: constraint violation"


class TestHandleDbErrorContextManager:
    """Tests for the handle_db_error context manager."""

    def test_success_case_no_exception(self):
        """Test that code executes normally when no exception occurs."""
        db = MagicMock()
        result = []

        with handle_db_error(db, "test operation"):
            result.append("executed")

        assert result == ["executed"]
        db.rollback.assert_not_called()

    def test_rollback_on_exception(self):
        """Test that rollback is called when an exception occurs."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(db, "test operation"):
                raise ValueError("test error")

        db.rollback.assert_called_once()
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to test operation" in exc_info.value.detail

    def test_rollback_on_sqlalchemy_error(self):
        """Test that rollback is called for SQLAlchemy errors."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(db, "database operation"):
                raise SQLAlchemyError("connection lost")

        db.rollback.assert_called_once()
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to database operation" in exc_info.value.detail

    def test_http_exception_reraise_by_default(self):
        """Test that HTTPExceptions are re-raised without modification by default."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(db, "test operation"):
                raise HTTPException(status_code=404, detail="Not found")

        # HTTPException should be re-raised without rollback
        db.rollback.assert_not_called()
        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Not found"

    def test_http_exception_not_reraised_when_disabled(self):
        """Test HTTPException handling when reraise_http_exceptions is False.

        When reraise_http_exceptions=False, the original HTTPException should be
        caught, rolled back, and wrapped in a NEW HTTPException with the configured
        status code (defaulting to 500).
        """
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(db, "test operation", reraise_http_exceptions=False):
                raise HTTPException(status_code=404, detail="Not found")

        # When reraise is disabled:
        # 1. Rollback should happen
        db.rollback.assert_called_once()
        # 2. Status code should be overridden to default 500
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        # 3. Detail should be wrapped with operation name
        assert "Failed to test operation" in exc_info.value.detail

    def test_http_exception_status_override_when_disabled(self):
        """Test that HTTPException status code is overridden when reraise is disabled."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(
                db,
                "test operation",
                reraise_http_exceptions=False,
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            ):
                raise HTTPException(status_code=404, detail="Original error")

        db.rollback.assert_called_once()
        # Status code should be the configured one, not the original
        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Failed to test operation" in exc_info.value.detail

    def test_custom_status_code(self):
        """Test custom HTTP status code."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(
                db, "test operation", status_code=status.HTTP_503_SERVICE_UNAVAILABLE
            ):
                raise ValueError("service error")

        assert exc_info.value.status_code == status.HTTP_503_SERVICE_UNAVAILABLE

    def test_custom_detail_template(self):
        """Test custom error detail template."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(
                db,
                "update user",
                detail_template="User service error: {error}",
            ):
                raise ValueError("database timeout")

        assert exc_info.value.detail == "User service error: database timeout"

    def test_detail_template_with_operation_name(self):
        """Test detail template with operation_name placeholder."""
        db = MagicMock()

        with pytest.raises(HTTPException) as exc_info:
            with handle_db_error(
                db,
                "save settings",
                detail_template="Could not {operation_name}: {error}",
            ):
                raise ValueError("disk full")

        assert exc_info.value.detail == "Could not save settings: disk full"

    def test_logging_on_error(self):
        """Test that errors are logged with context."""
        db = MagicMock()

        with patch("app.core.db_error_handling.logger") as mock_logger:
            with pytest.raises(HTTPException):
                with handle_db_error(db, "create record"):
                    raise ValueError("insertion failed")

            mock_logger.log.assert_called_once()
            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.ERROR
            assert "create record" in call_args[0][1]
            assert call_args[1]["exc_info"] is True

    def test_custom_log_level(self):
        """Test custom logging level."""
        db = MagicMock()

        with patch("app.core.db_error_handling.logger") as mock_logger:
            with pytest.raises(HTTPException):
                with handle_db_error(
                    db, "optional operation", log_level=logging.WARNING
                ):
                    raise ValueError("minor issue")

            call_args = mock_logger.log.call_args
            assert call_args[0][0] == logging.WARNING


class TestHandleDbErrorDecorator:
    """Tests for the HandleDbErrorDecorator class."""

    def test_decorator_success(self):
        """Test decorated function executes successfully."""
        db = create_mock_db()

        @handle_db_error_decorator("test operation")
        def my_function(db):
            return "success"

        result = my_function(db)
        assert result == "success"
        db.rollback.assert_not_called()

    def test_decorator_with_db_in_kwargs(self):
        """Test decorator finds db in keyword arguments."""
        db = create_mock_db()

        @handle_db_error_decorator("test operation")
        def my_function(db):
            return "success"

        result = my_function(db=db)
        assert result == "success"

    def test_decorator_error_handling(self):
        """Test decorator handles errors correctly."""
        db = create_mock_db()

        @handle_db_error_decorator("failing operation")
        def failing_function(db):
            raise ValueError("something went wrong")

        with pytest.raises(HTTPException) as exc_info:
            failing_function(db)

        db.rollback.assert_called_once()
        assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to failing operation" in exc_info.value.detail

    def test_decorator_custom_status_code(self):
        """Test decorator with custom status code."""
        db = create_mock_db()

        @handle_db_error_decorator(
            "test operation", status_code=status.HTTP_400_BAD_REQUEST
        )
        def my_function(db):
            raise ValueError("bad data")

        with pytest.raises(HTTPException) as exc_info:
            my_function(db)

        assert exc_info.value.status_code == status.HTTP_400_BAD_REQUEST

    def test_decorator_missing_db_parameter(self):
        """Test decorator raises error when db parameter is missing."""

        @handle_db_error_decorator("test operation")
        def no_db_function():
            pass

        with pytest.raises(ValueError) as exc_info:
            no_db_function()

        assert "Could not find 'db' Session parameter" in str(exc_info.value)

    def test_decorator_preserves_function_metadata(self):
        """Test that decorator preserves function name and docstring."""

        @handle_db_error_decorator("test operation")
        def documented_function(db):
            """This is the docstring."""
            pass

        assert documented_function.__name__ == "documented_function"
        assert documented_function.__doc__ == "This is the docstring."

    def test_decorator_with_multiple_arguments(self):
        """Test decorator with function that has multiple arguments."""
        db = create_mock_db()

        @handle_db_error_decorator("multi-arg operation")
        def multi_arg_function(arg1, db, arg2, kwarg1=None):
            return (arg1, arg2, kwarg1)

        result = multi_arg_function("a", db, "b", kwarg1="c")
        assert result == ("a", "b", "c")

    def test_alias_exists(self):
        """Test that handle_db_error_decorator alias exists and works."""
        assert handle_db_error_decorator is HandleDbErrorDecorator
