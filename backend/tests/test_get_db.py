"""
Tests for the get_db() database session dependency.

Verifies proper rollback behavior when exceptions occur during database operations.
"""
import pytest
from unittest.mock import MagicMock, patch


class TestGetDbRollbackBehavior:
    """Tests for get_db() exception handling and rollback behavior."""

    def test_rollback_called_on_exception(self):
        """Verify that rollback is called when an exception occurs in the session."""
        mock_session = MagicMock()

        with patch("app.models.base.SessionLocal", return_value=mock_session):
            from app.models.base import get_db

            gen = get_db()
            db = next(gen)

            # Verify we got the mock session
            assert db is mock_session

            # Simulate an exception being thrown
            with pytest.raises(ValueError):
                gen.throw(ValueError("Test exception"))

            # Verify rollback was called
            mock_session.rollback.assert_called_once()
            # Verify close was called (in finally block)
            mock_session.close.assert_called_once()

    def test_exception_is_re_raised_after_rollback(self):
        """Verify that the original exception is re-raised after rollback."""
        mock_session = MagicMock()

        with patch("app.models.base.SessionLocal", return_value=mock_session):
            from app.models.base import get_db

            gen = get_db()
            next(gen)

            # The exception should be re-raised
            with pytest.raises(RuntimeError) as exc_info:
                gen.throw(RuntimeError("Original error message"))

            assert str(exc_info.value) == "Original error message"

    def test_close_called_on_normal_completion(self):
        """Verify that close is called on normal generator completion."""
        mock_session = MagicMock()

        with patch("app.models.base.SessionLocal", return_value=mock_session):
            from app.models.base import get_db

            gen = get_db()
            next(gen)

            # Close the generator normally
            try:
                gen.close()
            except GeneratorExit:
                pass

            # Verify close was called but rollback was NOT called
            mock_session.close.assert_called_once()
            # On normal completion, rollback should not be called
            mock_session.rollback.assert_not_called()

    def test_rollback_called_before_close_on_exception(self):
        """Verify rollback is called before close when exception occurs."""
        mock_session = MagicMock()
        call_order = []

        def track_rollback():
            call_order.append("rollback")

        def track_close():
            call_order.append("close")

        mock_session.rollback.side_effect = track_rollback
        mock_session.close.side_effect = track_close

        with patch("app.models.base.SessionLocal", return_value=mock_session):
            from app.models.base import get_db

            gen = get_db()
            next(gen)

            with pytest.raises(Exception):
                gen.throw(Exception("Test"))

            # Verify rollback was called before close
            assert call_order == ["rollback", "close"]

    def test_close_called_even_if_rollback_fails(self):
        """Verify close is still called even if rollback raises an exception."""
        mock_session = MagicMock()
        mock_session.rollback.side_effect = Exception("Rollback failed")

        with patch("app.models.base.SessionLocal", return_value=mock_session):
            from app.models.base import get_db

            gen = get_db()
            next(gen)

            # The rollback exception should propagate
            with pytest.raises(Exception) as exc_info:
                gen.throw(ValueError("Original error"))

            # Note: The rollback exception will propagate, not the original
            assert "Rollback failed" in str(exc_info.value)

            # Close should still be called (in finally block)
            mock_session.close.assert_called_once()
