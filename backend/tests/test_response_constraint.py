"""
Tests for database-level unique constraint on Response(test_session_id, question_id).

This test verifies that the database constraint prevents duplicate responses
even if the app-level check is bypassed (e.g., due to race conditions).
"""
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.models import (
    Response,
    TestSession,
    User,
    Question,
    TestStatus,
    QuestionType,
    DifficultyLevel,
)
from app.core.datetime_utils import utc_now


class TestResponseUniqueConstraint:
    """Test database-level duplicate response prevention."""

    async def test_database_constraint_prevents_duplicate_response(self, db_session):
        """
        Test that the database constraint catches duplicate responses
        even if the application-level check is bypassed.

        This simulates a race condition where two requests try to insert
        the same response simultaneously.
        """
        # Create a user
        user = User(
            email="test@example.com",
            password_hash="hashed",  # pragma: allowlist secret
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        await db_session.flush()

        # Create a question
        question = Question(
            question_text="Test question?",
            correct_answer="A",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            is_active=True,
        )
        db_session.add(question)
        await db_session.flush()

        # Create a test session
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.IN_PROGRESS,
            started_at=utc_now(),
            is_adaptive=False,
        )
        db_session.add(test_session)
        await db_session.flush()

        # Create first response (should succeed)
        response1 = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
            answered_at=utc_now(),
            time_spent_seconds=10,
        )
        db_session.add(response1)
        await db_session.commit()

        # Attempt to create duplicate response (should fail at database level)
        response2 = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="B",  # Different answer, but same session + question
            is_correct=False,
            answered_at=utc_now(),
            time_spent_seconds=5,
        )
        db_session.add(response2)

        # The database constraint should raise IntegrityError on commit
        with pytest.raises(IntegrityError):
            await db_session.commit()

        # Rollback to clean up
        await db_session.rollback()

    async def test_different_sessions_same_question_allowed(self, db_session):
        """
        Test that the same question can be answered in different sessions
        by the same user (constraint is per-session).
        """
        # Create a user
        user = User(
            email="test2@example.com",
            password_hash="hashed",  # pragma: allowlist secret
            first_name="Test",
            last_name="User2",
        )
        db_session.add(user)
        await db_session.flush()

        # Create a question
        question = Question(
            question_text="Test question?",
            correct_answer="A",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            is_active=True,
        )
        db_session.add(question)
        await db_session.flush()

        # Create two test sessions
        session1 = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=utc_now(),
            is_adaptive=False,
        )
        session2 = TestSession(
            user_id=user.id,
            status=TestStatus.IN_PROGRESS,
            started_at=utc_now(),
            is_adaptive=False,
        )
        db_session.add(session1)
        db_session.add(session2)
        await db_session.flush()

        # Answer the same question in both sessions (should succeed)
        response1 = Response(
            test_session_id=session1.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
            answered_at=utc_now(),
            time_spent_seconds=10,
        )
        response2 = Response(
            test_session_id=session2.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="B",
            is_correct=False,
            answered_at=utc_now(),
            time_spent_seconds=5,
        )
        db_session.add(response1)
        db_session.add(response2)
        await db_session.commit()  # Should succeed - different sessions

        # Verify both responses were created
        _qresult = await db_session.execute(
            select(Response).filter(Response.question_id == question.id)
        )
        responses = _qresult.scalars().all()
        assert len(responses) == 2

    async def test_same_session_different_questions_allowed(self, db_session):
        """
        Test that different questions can be answered in the same session
        (constraint is per-question per-session).
        """
        # Create a user
        user = User(
            email="test3@example.com",
            password_hash="hashed",  # pragma: allowlist secret
            first_name="Test",
            last_name="User3",
        )
        db_session.add(user)
        await db_session.flush()

        # Create two questions
        question1 = Question(
            question_text="Test question 1?",
            correct_answer="A",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            is_active=True,
        )
        question2 = Question(
            question_text="Test question 2?",
            correct_answer="B",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.HARD,
            is_active=True,
        )
        db_session.add(question1)
        db_session.add(question2)
        await db_session.flush()

        # Create a test session
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.IN_PROGRESS,
            started_at=utc_now(),
            is_adaptive=False,
        )
        db_session.add(test_session)
        await db_session.flush()

        # Answer both questions in the same session (should succeed)
        response1 = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question1.id,
            user_answer="A",
            is_correct=True,
            answered_at=utc_now(),
            time_spent_seconds=10,
        )
        response2 = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question2.id,
            user_answer="B",
            is_correct=True,
            answered_at=utc_now(),
            time_spent_seconds=15,
        )
        db_session.add(response1)
        db_session.add(response2)
        await db_session.commit()  # Should succeed - different questions

        # Verify both responses were created
        _qresult = await db_session.execute(
            select(Response).filter(Response.test_session_id == test_session.id)
        )
        responses = _qresult.scalars().all()
        assert len(responses) == 2
