"""
Datetime utility functions for handling timezone-aware datetimes.
"""
from datetime import datetime, timezone
from typing import Optional


def ensure_timezone_aware(dt: Optional[datetime]) -> datetime:
    """
    Ensure a datetime object is timezone-aware (UTC).
    SQLite may return timezone-naive datetimes even when stored as timezone-aware.

    Args:
        dt: The datetime to ensure is timezone-aware

    Returns:
        A timezone-aware datetime object in UTC

    Raises:
        ValueError: If dt is None
    """
    if dt is None:
        raise ValueError("datetime cannot be None")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
