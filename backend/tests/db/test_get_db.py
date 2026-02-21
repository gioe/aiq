"""
Tests for the get_db() async database session dependency.

Verifies proper rollback behavior when exceptions occur during database operations.
"""

import pytest
from unittest.mock import AsyncMock, patch
from sqlalchemy.ext.asyncio import AsyncSession


class TestGetDbRollbackBehavior:
    """Tests for get_db() exception handling and rollback behavior."""

    @pytest.mark.asyncio
    async def test_rollback_called_on_exception(self):
        """Verify that rollback is called when an exception occurs in the session."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.models.base.AsyncSessionLocal", return_value=mock_cm):
            from app.models.base import get_db

            gen = get_db()
            db = await gen.__anext__()

            # Verify we got the mock session
            assert db is mock_session

            # Simulate an exception being thrown
            with pytest.raises(ValueError):
                await gen.athrow(ValueError("Test exception"))

            # Verify rollback was called
            mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_exception_is_re_raised_after_rollback(self):
        """Verify that the original exception is re-raised after rollback."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.models.base.AsyncSessionLocal", return_value=mock_cm):
            from app.models.base import get_db

            gen = get_db()
            await gen.__anext__()

            # The exception should be re-raised
            with pytest.raises(RuntimeError) as exc_info:
                await gen.athrow(RuntimeError("Original error message"))

            assert str(exc_info.value) == "Original error message"

    @pytest.mark.asyncio
    async def test_session_yields_from_async_session_local(self):
        """Verify that get_db yields a session from AsyncSessionLocal."""
        mock_session = AsyncMock(spec=AsyncSession)

        mock_cm = AsyncMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_session)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        with patch("app.models.base.AsyncSessionLocal", return_value=mock_cm):
            from app.models.base import get_db

            gen = get_db()
            db = await gen.__anext__()

            assert db is mock_session

            # Clean close
            await gen.aclose()
