"""
Graceful failure utilities (BCQ-017).

This module provides reusable context managers for handling non-critical
operations that should not block the main execution flow. It centralizes
the common "graceful degradation" pattern of:
1. Attempting an operation
2. Logging any exceptions with context
3. Continuing execution without raising

This is distinct from `db_error_handling.py` which handles critical errors
that require rollback and HTTP error responses.

Usage:
    from app.core.graceful_failure import graceful_failure

    # Using as a context manager:
    with graceful_failure("update distractor stats", logger):
        update_distractor_stats(db, question_id, answer)

    # With custom log level (default is WARNING):
    with graceful_failure("run validity analysis", logger, log_level=logging.ERROR):
        result = run_validity_checks(...)

    # With exception info (stack trace):
    with graceful_failure("calculate SEM", logger, exc_info=True):
        sem = calculate_sem(reliability)

Reference:
    docs/plans/in-progress/PLAN-BACKEND-CODE-QUALITY.md (BCQ-017)
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Generator, Optional, TypeVar

from app.observability import metrics


# Type variable for decorator return type preservation
T = TypeVar("T")


@contextmanager
def graceful_failure(
    operation_name: str,
    logger: logging.Logger,
    *,
    log_level: int = logging.WARNING,
    exc_info: bool = False,
    context: Optional[dict[str, Any]] = None,
) -> Generator[None, None, None]:
    """Context manager for non-critical operations that should not block execution.

    This context manager provides a standard pattern for graceful degradation:
    1. Execute the wrapped code
    2. On exception: log the error with context and continue

    Unlike `handle_db_error`, this does NOT:
    - Raise HTTPException
    - Rollback the database session
    - Stop execution

    Use this for operations where failure is acceptable and the main flow
    should continue (e.g., analytics, distractor stats, validity checks).

    Args:
        operation_name: Human-readable name of the operation for logging
            (e.g., "update distractor stats", "calculate SEM").
        logger: The logger instance to use for logging errors.
        log_level: Logging level for error messages. Defaults to WARNING.
            Use ERROR for more critical operations that warrant attention.
        exc_info: Whether to include exception traceback in log. Defaults to False.
            Set to True for operations where stack traces aid debugging.
        context: Optional dictionary of additional context to include in log message
            (e.g., {"session_id": 123, "question_id": 456}).

    Yields:
        None - the context manager is used for its side effects only.

    Example:
        >>> # Basic usage
        >>> with graceful_failure("update distractor stats", logger):
        ...     update_distractor_stats(db, question_id, answer)

        >>> # With custom log level and exception info
        >>> with graceful_failure(
        ...     "run validity analysis",
        ...     logger,
        ...     log_level=logging.ERROR,
        ...     exc_info=True
        ... ):
        ...     result = run_validity_checks(session_id)

        >>> # With additional context
        >>> with graceful_failure(
        ...     "update question statistics",
        ...     logger,
        ...     context={"session_id": session.id}
        ... ):
        ...     update_question_statistics(db, session.id)
    """
    try:
        yield
    except Exception as e:
        # Format the log message with optional context
        if context:
            context_str = ", ".join(f"{k}={v}" for k, v in context.items())
            message = f"Failed to {operation_name} ({context_str}): {e}"
        else:
            message = f"Failed to {operation_name}: {e}"

        logger.log(log_level, message, exc_info=exc_info)

        # Record error metric for observability (safe - won't break graceful failure)
        try:
            metrics.record_error(error_type="GracefulFailure")
        except Exception:
            pass  # Metrics recording should not break graceful failure handling


class GracefulFailureDecorator:
    """Decorator class for handling non-critical operations in functions.

    This provides a decorator alternative to the context manager for cases
    where the entire function body should be wrapped in graceful failure handling.

    Unlike `HandleDbErrorDecorator`, this:
    - Swallows exceptions instead of raising HTTPException
    - Returns a default value on failure (None by default)
    - Does not require or rollback a database session

    Usage:
        @graceful_failure_decorator("update analytics")
        def update_analytics(session_id: int) -> Optional[dict]:
            ...

        # With custom default return value:
        @graceful_failure_decorator("get cached value", default={})
        def get_cached_value(key: str) -> dict:
            ...
    """

    def __init__(
        self,
        operation_name: str,
        *,
        logger: Optional[logging.Logger] = None,
        log_level: int = logging.WARNING,
        exc_info: bool = False,
        default: Any = None,
    ):
        """Initialize the decorator.

        Args:
            operation_name: Human-readable name of the operation.
            logger: Logger to use. If None, uses the module's logger of the
                decorated function.
            log_level: Logging level for errors. Defaults to WARNING.
            exc_info: Whether to include stack trace. Defaults to False.
            default: Default value to return on failure. Defaults to None.
        """
        self.operation_name = operation_name
        self._logger = logger
        self.log_level = log_level
        self.exc_info = exc_info
        self.default = default

    def __call__(self, func: Callable[..., T]) -> Callable[..., Optional[T]]:
        """Decorate the function with graceful failure handling."""

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            # Use provided logger or get one from the function's module
            logger = self._logger or logging.getLogger(func.__module__)

            with graceful_failure(
                self.operation_name,
                logger,
                log_level=self.log_level,
                exc_info=self.exc_info,
            ):
                return func(*args, **kwargs)

            # If we get here, an exception occurred and was swallowed
            return self.default

        return wrapper


# Convenience alias for the decorator
graceful_failure_decorator = GracefulFailureDecorator
