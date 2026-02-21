"""
SQLAlchemy database query metrics instrumentation.

This module provides instrumentation for tracking database query performance
using SQLAlchemy event listeners. It integrates with the application's
observability metrics to record query duration by operation and table.

Usage:
    from app.db.instrumentation import setup_db_instrumentation
    from app.models import engine

    # During application startup
    setup_db_instrumentation(engine)
"""

import logging
import re
import time
from typing import Any, Optional

from sqlalchemy import event
from sqlalchemy.engine import Connection, Engine

from app.observability import metrics

logger = logging.getLogger(__name__)

# Maximum number of characters to log from SQL statements for debugging
MAX_SQL_LOG_LENGTH = 200

# Regex patterns for extracting SQL operation and table name
# These handle common SQLAlchemy-generated queries and edge cases
OPERATION_PATTERN = re.compile(
    r"^\s*(SELECT|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|TRUNCATE)\b",
    re.IGNORECASE,
)

# Match table name from various SQL patterns:
# - FROM table_name
# - INSERT INTO table_name
# - UPDATE table_name
# - DELETE FROM table_name
# - JOIN table_name
TABLE_PATTERN = re.compile(
    r"\b(?:FROM|INTO|UPDATE|JOIN)\s+([a-z_][a-z0-9_]*)",
    re.IGNORECASE,
)


def _parse_sql_operation(sql: str) -> str:
    """
    Extract the SQL operation (SELECT, INSERT, etc.) from a SQL statement.

    Args:
        sql: SQL statement to parse

    Returns:
        Operation type in uppercase (e.g., "SELECT", "INSERT")
        Returns "UNKNOWN" if operation cannot be determined
    """
    match = OPERATION_PATTERN.match(sql)
    if match:
        return match.group(1).upper()
    return "UNKNOWN"


def _parse_table_name(sql: str) -> str:
    """
    Extract the primary table name from a SQL statement.

    Args:
        sql: SQL statement to parse

    Returns:
        Table name (e.g., "users", "questions")
        Returns "unknown" if table cannot be determined

    Note:
        For queries with multiple tables (JOINs), returns the first table found.
        For subqueries, returns the outermost table.
    """
    match = TABLE_PATTERN.search(sql)
    if match:
        return match.group(1).lower()
    return "unknown"


def _should_instrument_query(sql: str) -> bool:
    """
    Determine if a query should be instrumented.

    Args:
        sql: SQL statement to check

    Returns:
        True if query should be instrumented, False otherwise

    Note:
        Filters out internal SQLAlchemy queries like PRAGMA statements,
        information_schema queries, and other non-application queries.
    """
    # Skip empty or whitespace-only queries
    if not sql or not sql.strip():
        return False

    sql_lower = sql.lower().strip()

    # Skip internal database queries
    # Use startswith for most patterns, but check anywhere for catalog queries
    if sql_lower.startswith("pragma "):  # SQLite internal
        return False
    if sql_lower.startswith("show "):  # Database metadata queries
        return False
    if sql_lower.startswith("set "):  # Session configuration (at start only)
        return False

    # Check anywhere in query for catalog patterns
    if "pg_catalog." in sql_lower:  # PostgreSQL internal
        return False
    if "information_schema." in sql_lower:  # Database metadata
        return False

    return True


class QueryInstrumentationContext:
    """
    Context object for tracking query timing between before/after events.

    Stores the start time and parsed query metadata to be used when
    the query completes.
    """

    def __init__(self, operation: str, table: str, start_time: float):
        """Initialize context with operation, table, and start time."""
        self.operation = operation
        self.table = table
        self.start_time = start_time


def _before_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    """
    Handle before cursor execute event.

    Parses the SQL statement and stores timing context for later use.

    Args:
        conn: SQLAlchemy database connection
        cursor: Database cursor
        statement: SQL statement to execute
        parameters: Query parameters
        context: SQLAlchemy execution context
        executemany: Whether this is an executemany() call
    """
    # Check if we should instrument this query
    if not _should_instrument_query(statement):
        return

    try:
        # Parse SQL to extract operation and table
        operation = _parse_sql_operation(statement)
        table = _parse_table_name(statement)

        # Store context for use in after_cursor_execute
        # Using context._query_instrumentation to avoid conflicts
        context._query_instrumentation = QueryInstrumentationContext(
            operation=operation,
            table=table,
            start_time=time.perf_counter(),
        )

        # Debug logging for development
        logger.debug(
            f"DB query starting: {operation} on {table} | "
            f"SQL: {statement[:MAX_SQL_LOG_LENGTH]}..."
        )

    except Exception as e:
        # Don't let instrumentation errors break the application
        logger.debug(f"Failed to instrument query start: {e}")


def _after_cursor_execute(
    conn: Connection,
    cursor: Any,
    statement: str,
    parameters: Any,
    context: Any,
    executemany: bool,
) -> None:
    """
    Handle after cursor execute event.

    Calculates query duration and records metrics.

    Args:
        conn: SQLAlchemy database connection
        cursor: Database cursor
        statement: SQL statement that was executed
        parameters: Query parameters
        context: SQLAlchemy execution context
        executemany: Whether this was an executemany() call
    """
    try:
        # Retrieve the context stored by before_cursor_execute
        instrumentation_ctx: Optional[QueryInstrumentationContext] = getattr(
            context, "_query_instrumentation", None
        )

        if instrumentation_ctx is None:
            # Query was not instrumented (e.g., filtered out)
            return

        # Calculate duration
        duration = time.perf_counter() - instrumentation_ctx.start_time

        # Record metric
        metrics.record_db_query(
            operation=instrumentation_ctx.operation,
            table=instrumentation_ctx.table,
            duration=duration,
        )

        # Debug logging
        logger.debug(
            f"DB query completed: {instrumentation_ctx.operation} on "
            f"{instrumentation_ctx.table} in {duration*1000:.2f}ms"
        )

        # Clean up context to avoid memory leaks
        delattr(context, "_query_instrumentation")

    except Exception as e:
        # Don't let instrumentation errors break the application
        logger.debug(f"Failed to instrument query completion: {e}")


def setup_db_instrumentation(engine: Engine) -> None:
    """
    Set up database query instrumentation for an SQLAlchemy engine.

    Registers event listeners that track query performance and record
    metrics for each database operation.

    Args:
        engine: SQLAlchemy engine to instrument

    Note:
        This function is idempotent - calling it multiple times on the same
        engine will not register duplicate listeners.
    """
    # Check if already instrumented to avoid duplicate listeners
    if hasattr(engine, "_aiq_instrumented"):
        logger.warning("Database query instrumentation already set up")
        return

    try:
        # Register event listeners
        event.listen(
            engine,
            "before_cursor_execute",
            _before_cursor_execute,
            named=True,
        )
        event.listen(
            engine,
            "after_cursor_execute",
            _after_cursor_execute,
            named=True,
        )

        # Mark engine as instrumented
        engine._aiq_instrumented = True  # type: ignore

        logger.info(
            "Database query instrumentation initialized successfully "
            "(metrics will be recorded for SELECT, INSERT, UPDATE, DELETE)"
        )

    except Exception as e:
        logger.error(f"Failed to set up database query instrumentation: {e}")
        raise


def teardown_db_instrumentation(engine: Engine) -> None:
    """
    Remove database query instrumentation from an SQLAlchemy engine.

    Unregisters event listeners. Useful for testing or cleanup.

    Args:
        engine: SQLAlchemy engine to uninstrument
    """
    if not hasattr(engine, "_aiq_instrumented"):
        logger.debug("Database query instrumentation not set up, nothing to teardown")
        return

    try:
        # Remove event listeners
        event.remove(
            engine,
            "before_cursor_execute",
            _before_cursor_execute,
        )
        event.remove(
            engine,
            "after_cursor_execute",
            _after_cursor_execute,
        )

        # Remove marker
        delattr(engine, "_aiq_instrumented")

        logger.info("Database query instrumentation removed")

    except Exception as e:
        logger.warning(f"Failed to teardown database query instrumentation: {e}")
