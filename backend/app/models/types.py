"""Custom SQLAlchemy types for cross-database compatibility.

This module provides custom column types that work across different
database backends (PostgreSQL, SQLite) used in production and testing.
"""

import json
from typing import Any, Optional, List

from sqlalchemy import TypeDecorator, Text
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy import Float


class FloatArray(TypeDecorator):
    """
    A float array type that works with both PostgreSQL and SQLite.

    - On PostgreSQL: Uses native ARRAY(Float) for efficient storage
    - On SQLite: Stores as JSON text for compatibility

    This allows tests to use SQLite while production uses PostgreSQL's
    native array type for better performance.

    Usage:
        question_embedding: Mapped[Optional[List[float]]] = mapped_column(
            FloatArray(), nullable=True
        )
    """

    impl = Text  # Default implementation (used for SQLite)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        """Choose implementation based on database dialect."""
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Float))
        else:
            # SQLite and others: use Text with JSON serialization
            return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Optional[List[float]], dialect) -> Any:
        """Convert Python list to database format."""
        if value is None:
            return None

        if dialect.name == "postgresql":
            # PostgreSQL handles array natively
            return value
        else:
            # SQLite: serialize to JSON string
            return json.dumps(value)

    def process_result_value(self, value: Any, dialect) -> Optional[List[float]]:
        """Convert database value to Python list."""
        if value is None:
            return None

        if dialect.name == "postgresql":
            # PostgreSQL returns array directly
            return value
        else:
            # SQLite: deserialize from JSON string
            if isinstance(value, str):
                return json.loads(value)
            return value
