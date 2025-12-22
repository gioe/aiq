"""
Database error handling utilities (BCQ-013).

This module provides reusable context managers and helpers for handling
database errors consistently across the codebase. It centralizes the
common pattern of:
1. Rolling back the database session on error
2. Logging the error with context
3. Raising an appropriate HTTPException

Usage:
    from app.core.db_error_handling import handle_db_error

    # Using as a context manager (recommended for complex operations):
    with handle_db_error(db, "update user preferences"):
        user.notification_enabled = True
        db.commit()
        db.refresh(user)

    # Using as a decorator (for simple operations):
    @handle_db_error.decorator("create user")
    def create_user(db: Session, user_data: dict):
        ...

Reference:
    docs/plans/in-progress/PLAN-BACKEND-CODE-QUALITY.md (BCQ-013)
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional, TypeVar

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session


logger = logging.getLogger(__name__)

# Type variable for decorator return type preservation
T = TypeVar("T")


class DatabaseOperationError(Exception):
    """Exception raised when a database operation fails.

    This exception wraps database errors with additional context about
    the operation that failed. It can be caught and converted to an
    appropriate HTTP response.

    Note:
        This exception is provided for use in non-HTTP contexts (background
        tasks, CLI commands, internal services) where HTTPException is not
        appropriate. The `handle_db_error` context manager uses HTTPException
        directly for FastAPI endpoint usage.

    Usage Example:
        >>> try:
        ...     user = db.query(User).filter(User.id == user_id).first()
        ...     if not user:
        ...         raise DatabaseOperationError("find user", ValueError("User not found"))
        ... except DatabaseOperationError as e:
        ...     logger.error(f"Operation failed: {e.operation_name}")

    Attributes:
        operation_name: Human-readable name of the operation that failed
        original_error: The underlying exception that caused the failure
        message: The formatted error message
    """

    def __init__(
        self,
        operation_name: str,
        original_error: Exception,
        message: Optional[str] = None,
    ):
        """Initialize the database operation error.

        Args:
            operation_name: Human-readable name of the failed operation
            original_error: The underlying exception that caused the failure
            message: Optional custom error message. If not provided, a default
                message is generated from the operation name and error.
        """
        self.operation_name = operation_name
        self.original_error = original_error
        self.message = message or f"Failed to {operation_name}: {str(original_error)}"
        super().__init__(self.message)


@contextmanager
def handle_db_error(
    db: Session,
    operation_name: str,
    *,
    reraise_http_exceptions: bool = True,
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail_template: Optional[str] = None,
    log_level: int = logging.ERROR,
) -> Generator[None, None, None]:
    """Context manager for handling database errors consistently.

    This context manager provides a standard pattern for database operations:
    1. Execute the wrapped code
    2. On exception: rollback the session, log the error, raise HTTPException

    Args:
        db: The SQLAlchemy database session to rollback on error.
        operation_name: Human-readable name of the operation for error messages
            and logging (e.g., "register device token", "update preferences").
        reraise_http_exceptions: If True (default), HTTPExceptions raised within
            the context are re-raised without modification. Set to False to
            wrap all exceptions.
        status_code: HTTP status code to use in the raised HTTPException.
            Defaults to 500 Internal Server Error.
        detail_template: Optional custom template for the error detail message.
            If provided, should contain {operation_name} and optionally {error}.
            Defaults to "Failed to {operation_name}: {error}".
        log_level: Logging level for error messages. Defaults to logging.ERROR.

    Yields:
        None - the context manager is used for its side effects only.

    Raises:
        HTTPException: On any exception (except HTTPException if reraise_http_exceptions
            is True), with the session rolled back.

    Example:
        >>> with handle_db_error(db, "update user settings"):
        ...     user.theme = "dark"
        ...     db.commit()
        ...     db.refresh(user)

        >>> # With custom error message:
        >>> with handle_db_error(
        ...     db,
        ...     "create notification",
        ...     detail_template="Notification service unavailable: {error}"
        ... ):
        ...     notification = Notification(user_id=user.id)
        ...     db.add(notification)
        ...     db.commit()

    Note on Return-Inside-Context-Manager Pattern:
        It is **intentional** that the return statement for the endpoint response
        should be placed **inside** the context manager block, not outside it.

        Example (recommended pattern)::

            @router.post("/items")
            def create_item(item_data: ItemCreate, db: Session = Depends(get_db)):
                with handle_db_error(db, "create item"):
                    item = Item(**item_data.dict())
                    db.add(item)
                    db.commit()
                    db.refresh(item)
                    return item  # Return INSIDE the context manager

        Trade-offs of this approach:

        **Pros:**
        - Response construction failures (e.g., Pydantic serialization errors during
          response model validation) are also caught and logged with context
        - Provides uniform error handling for the entire endpoint operation
        - Stack traces in logs include the full operation context

        **Cons:**
        - Response construction failures trigger a database rollback, which is
          unnecessary since the DB operation already succeeded
        - The rollback on a committed transaction is a no-op in most databases,
          so this is primarily a semantic concern rather than a functional issue

        The benefits of consistent error handling and logging outweigh the minor
        semantic concern of calling rollback after a successful commit.
    """
    try:
        yield
    except HTTPException as e:
        if reraise_http_exceptions:
            raise
        # When not reraising, treat HTTPException like any other error:
        # rollback, log, and wrap in new HTTPException with configured status
        db.rollback()

        # Format error detail using the original exception's detail
        if detail_template:
            detail = detail_template.format(
                operation_name=operation_name, error=e.detail
            )
        else:
            detail = f"Failed to {operation_name}: {e.detail}"

        # Log with context
        logger.log(
            log_level,
            f"Database error during {operation_name}: {e.detail}",
            exc_info=True,
        )

        # Raise new HTTPException with configured status code
        raise HTTPException(status_code=status_code, detail=detail)
    except (SQLAlchemyError, Exception) as e:
        db.rollback()

        # Format the error detail message
        if detail_template:
            detail = detail_template.format(operation_name=operation_name, error=str(e))
        else:
            detail = f"Failed to {operation_name}: {str(e)}"

        # Log the error with context
        logger.log(
            log_level,
            f"Database error during {operation_name}: {e}",
            exc_info=True,
        )

        raise HTTPException(status_code=status_code, detail=detail)


class HandleDbErrorDecorator:
    """Decorator class for handling database errors in functions.

    This provides a decorator alternative to the context manager for cases
    where the entire function body should be wrapped in error handling.

    Usage:
        @handle_db_error_decorator("create user")
        def create_user(db: Session, user_data: dict):
            ...

    Note:
        The decorated function must have a 'db' parameter (either positional
        or keyword argument) that is a SQLAlchemy Session.
    """

    def __init__(
        self,
        operation_name: str,
        *,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail_template: Optional[str] = None,
        log_level: int = logging.ERROR,
    ):
        """Initialize the decorator.

        Args:
            operation_name: Human-readable name of the operation.
            status_code: HTTP status code for errors. Defaults to 500.
            detail_template: Optional custom template for error details.
            log_level: Logging level for errors. Defaults to ERROR.
        """
        self.operation_name = operation_name
        self.status_code = status_code
        self.detail_template = detail_template
        self.log_level = log_level

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorate the function with error handling."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Try to find the db session in args/kwargs
            db = kwargs.get("db")
            if db is None:
                # Look for db in positional args - typically second arg after self
                # or first arg for non-method functions
                for arg in args:
                    if isinstance(arg, Session):
                        db = arg
                        break

            if db is None:
                raise ValueError(
                    f"Could not find 'db' Session parameter in {func.__name__}. "
                    "The function must have a 'db' parameter of type Session."
                )

            with handle_db_error(
                db,
                self.operation_name,
                status_code=self.status_code,
                detail_template=self.detail_template,
                log_level=self.log_level,
            ):
                return func(*args, **kwargs)

        return wrapper


# Convenience alias for the decorator
handle_db_error_decorator = HandleDbErrorDecorator
