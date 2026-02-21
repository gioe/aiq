"""
Tests for get_current_user_optional dependency.

Validates that optional auth degrades gracefully on database errors,
returning None instead of raising 503.

TASK-1169: Review get_current_user_optional error handling for availability.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth.dependencies import get_current_user_optional
from app.core.auth.security import create_access_token
from app.core.auth.token_blacklist import init_token_blacklist, get_token_blacklist


@pytest.fixture(scope="session", autouse=True)
def init_blacklist():
    """Initialize token blacklist for testing."""
    init_token_blacklist(redis_url=None)
    yield
    try:
        blacklist = get_token_blacklist()
        blacklist.clear_all()
    except RuntimeError:
        pass


class TestGetCurrentUserOptionalDatabaseError:
    """get_current_user_optional returns None on transient DB errors."""

    async def test_db_error_returns_none(self, async_test_user):
        """DB error during user lookup returns None instead of raising 503."""
        access_token = create_access_token({"user_id": async_test_user.id})

        mock_credentials = MagicMock()
        mock_credentials.credentials = access_token

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(side_effect=SQLAlchemyError("connection lost"))

        mock_request = MagicMock()
        mock_request.client = MagicMock()
        mock_request.client.host = "127.0.0.1"
        mock_request.headers = {}

        result = await get_current_user_optional(
            request=mock_request,
            credentials=mock_credentials,
            db=mock_db,
        )

        assert result is None

    async def test_no_credentials_returns_none(self):
        """No credentials returns None (baseline, not affected by this change)."""
        mock_request = MagicMock()
        mock_db = AsyncMock()

        result = await get_current_user_optional(
            request=mock_request,
            credentials=None,
            db=mock_db,
        )

        assert result is None
