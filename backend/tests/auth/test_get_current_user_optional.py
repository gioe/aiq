"""
Tests for get_current_user_optional dependency.

Validates that optional auth degrades gracefully on database errors,
returning None instead of raising 503.

TASK-1169: Review get_current_user_optional error handling for availability.
"""
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.core.auth import get_current_user_optional
from app.core.security import create_access_token
from app.core.token_blacklist import init_token_blacklist, get_token_blacklist


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

    async def test_db_error_during_user_lookup_returns_none(
        self, async_client, async_db_session, async_test_user
    ):
        """When the DB fails during user lookup, the endpoint still succeeds
        with current_user=None instead of returning 503.
        """
        access_token = create_access_token({"user_id": async_test_user.id})
        headers = {"Authorization": f"Bearer {access_token}"}

        with patch.object(
            async_db_session,
            "execute",
            side_effect=SQLAlchemyError("connection reset"),
        ):
            # Use feedback endpoint (uses get_current_user_optional)
            feedback_data = {
                "name": "DB Error User",
                "email": "dberror@example.com",
                "category": "other",
                "description": "Testing DB error graceful degradation.",
            }
            response = await async_client.post(
                "/v1/feedback/submit", json=feedback_data, headers=headers
            )

        # Endpoint should succeed — auth degraded to anonymous
        assert response.status_code == 201

    async def test_db_error_returns_none_directly(self, async_test_user):
        """Unit test: get_current_user_optional returns None on SQLAlchemyError."""
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

    async def test_no_credentials_still_returns_none(self):
        """Baseline: no credentials returns None (not affected by this change)."""
        mock_request = MagicMock()
        mock_db = AsyncMock()

        result = await get_current_user_optional(
            request=mock_request,
            credentials=None,
            db=mock_db,
        )

        assert result is None
