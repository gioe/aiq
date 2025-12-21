"""
Datetime utility functions for handling timezone-aware datetimes.
"""
from datetime import datetime, timezone
from typing import Optional


def utc_now() -> datetime:
    """
    Return the current datetime in UTC timezone.

    This utility provides a consistent, mockable way to get the current UTC time
    throughout the codebase. Using this function instead of datetime.now(timezone.utc)
    directly enables easier testing through mocking.

    Returns:
        A timezone-aware datetime object representing the current time in UTC.

    Example:
        >>> from app.core.datetime_utils import utc_now
        >>> current_time = utc_now()
        >>> current_time.tzinfo == timezone.utc
        True
    """
    return datetime.now(timezone.utc)


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
