"""
Tests for test session management endpoints.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock  # noqa: F401 (used by patch new_callable)


class TestStartTest:
    """Tests for POST /v1/test/start endpoint."""

    def test_start_test_success(self, client, auth_headers, test_questions):
        """Test successfully starting a new test session."""
        response = client.post("/v1/test/start?question_count=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session" in data
        assert "questions" in data
        assert "total_questions" in data

        # Verify session details with specific expected values
        session = data["session"]
        assert "id" in session
        assert isinstance(session["id"], int)
        assert session["id"] > 0  # Session ID should be positive
        assert session["status"] == "in_progress"  # Exact enum value
        assert "started_at" in session
        assert session["started_at"] is not None  # Should have a timestamp
        assert session["completed_at"] is None

        # Verify questions count matches expected
        assert len(data["questions"]) == 3
        assert data["total_questions"] == 3

        # Verify each question has required fields with correct types
        for question in data["questions"]:
            # Required fields exist
            assert "id" in question
            assert "question_text" in question
            assert "question_type" in question
            assert "difficulty_level" in question
            assert "answer_options" in question

            # Type verification
            assert isinstance(question["id"], int)
            assert isinstance(question["question_text"], str)
            assert len(question["question_text"]) > 0
            assert question["question_type"] in [
                "pattern",
                "logic",
                "spatial",
                "math",
                "verbal",
                "memory",
            ]
            assert question["difficulty_level"] in ["easy", "medium", "hard"]
            assert isinstance(question["answer_options"], list)
            assert len(question["answer_options"]) >= 2  # At least 2 options

            # Sensitive info verification
            assert "correct_answer" not in question
            assert question["explanation"] is None

        # Verify questions returned are from the active question pool
        active_question_ids = {q.id for q in test_questions if q.is_active}
        returned_question_ids = {q["id"] for q in data["questions"]}
        assert returned_question_ids.issubset(
            active_question_ids
        ), "All returned questions should be from active question pool"

    def test_start_test_default_count(self, client, auth_headers, test_questions):
        """Test starting test with default question count."""
        response = client.post("/v1/test/start", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return 4 questions (all available active questions)
        assert data["total_questions"] == 4
        assert len(data["questions"]) == 4

    def test_start_test_marks_questions_as_seen(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that starting a test marks questions as seen."""
        from app.models import UserQuestion, User

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Initially no questions are seen
        seen_count = (
            db_session.query(UserQuestion)
            .filter(UserQuestion.user_id == test_user.id)
            .count()
        )
        assert seen_count == 0

        # Start test with 3 questions
        response = client.post("/v1/test/start?question_count=3", headers=auth_headers)
        assert response.status_code == 200

        # Now 3 questions should be marked as seen
        seen_count = (
            db_session.query(UserQuestion)
            .filter(UserQuestion.user_id == test_user.id)
            .count()
        )
        assert seen_count == 3

    def test_start_test_prevents_duplicate_active_session(
        self, client, auth_headers, test_questions
    ):
        """Test that user cannot start multiple active test sessions."""
        # Start first test
        response1 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response1.status_code == 200
        session1_id = response1.json()["session"]["id"]

        # Try to start second test while first is still active
        response2 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response2.status_code == 400
        assert "already has an active test session" in response2.json()["detail"]
        assert str(session1_id) in response2.json()["detail"]

    def test_start_test_no_questions_available(
        self, client, auth_headers, test_questions, mark_questions_seen
    ):
        """Test starting test when all questions have been seen."""
        # Mark all active questions as seen (indices 0, 1, 2, 3)
        mark_questions_seen([0, 1, 2, 3])

        response = client.post("/v1/test/start", headers=auth_headers)

        assert response.status_code == 404
        assert "No unseen questions available" in response.json()["detail"]

    def test_start_test_requires_authentication(self, client, test_questions):
        """Test that endpoint requires authentication."""
        response = client.post("/v1/test/start")
        assert response.status_code in [401, 403]

    def test_start_test_count_validation(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test question_count parameter validation."""
        # Test count = 0 (below minimum)
        response = client.post("/v1/test/start?question_count=0", headers=auth_headers)
        assert response.status_code == 422  # Validation error

        # Test count = 101 (above maximum)
        response = client.post(
            "/v1/test/start?question_count=101", headers=auth_headers
        )
        assert response.status_code == 422  # Validation error

        # Test count = 1 (valid minimum)
        response = client.post("/v1/test/start?question_count=1", headers=auth_headers)
        assert response.status_code == 200
        session_id = response.json()["session"]["id"]

        # Complete the session to allow starting a new one
        from app.models import TestSession
        from app.models.models import TestStatus

        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        session.status = TestStatus.COMPLETED
        db_session.commit()

        # Test count = 100 (valid maximum, but only 4 questions available)
        # Note: 1 question already seen from previous test
        response = client.post(
            "/v1/test/start?question_count=100", headers=auth_headers
        )
        assert response.status_code == 200
        # Should return 3 questions (4 active - 1 already seen)
        assert response.json()["total_questions"] == 3

    def test_start_test_creates_session_in_database(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that starting test creates TestSession record."""
        from app.models import TestSession, User

        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Initially no sessions
        session_count = (
            db_session.query(TestSession)
            .filter(TestSession.user_id == test_user.id)
            .count()
        )
        assert session_count == 0

        # Start test
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response.status_code == 200
        session_id = response.json()["session"]["id"]

        # Session should exist in database
        test_session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert test_session is not None
        assert test_session.user_id == test_user.id
        assert test_session.status.value == "in_progress"

    def test_start_test_enforces_three_month_cadence(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that users cannot start a new test within 3 months of last completed test."""
        from app.models import TestSession, User
        from app.models.models import TestStatus
        from datetime import datetime, timedelta

        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create a completed test session from 30 days ago (within 3-month window)
        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=30, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=30),
        )
        db_session.add(completed_session)
        db_session.commit()

        # Try to start a new test
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        # Should be blocked
        assert response.status_code == 400
        detail = response.json()["detail"]
        assert "90 days" in detail or "3 months" in detail
        assert "days remaining" in detail

    def test_start_test_allows_test_after_three_months(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that users CAN start a new test after 3 months have passed."""
        from app.models import TestSession, User, UserQuestion
        from app.models.models import TestStatus
        from datetime import datetime, timedelta

        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Mark 2 questions as seen (simulate previous test from 91 days ago)
        old_seen_at = datetime.utcnow() - timedelta(days=91)
        user_question_1 = UserQuestion(
            user_id=test_user.id,
            question_id=test_questions[0].id,
            seen_at=old_seen_at,
        )
        user_question_2 = UserQuestion(
            user_id=test_user.id,
            question_id=test_questions[1].id,
            seen_at=old_seen_at,
        )
        db_session.add(user_question_1)
        db_session.add(user_question_2)

        # Create a completed test session from 181 days ago (outside 6-month window)
        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow() - timedelta(days=181, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=181),
        )
        db_session.add(completed_session)
        db_session.commit()

        # Try to start a new test (should succeed and get questions 2 and 3)
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        # Should succeed
        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        assert data["session"]["status"] == "in_progress"
        assert data["total_questions"] == 2  # Should get 2 unseen questions

    def test_start_test_ignores_abandoned_sessions_for_cadence(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that abandoned sessions don't count toward 6-month cadence."""
        from app.models import TestSession, User
        from app.models.models import TestStatus
        from datetime import datetime, timedelta

        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create an abandoned test session from 30 days ago
        abandoned_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.ABANDONED,
            started_at=datetime.utcnow() - timedelta(days=30, hours=1),
            completed_at=datetime.utcnow() - timedelta(days=30),
        )
        db_session.add(abandoned_session)
        db_session.commit()

        # Try to start a new test
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        # Should succeed (abandoned sessions don't count)
        assert response.status_code == 200
        data = response.json()
        assert "session" in data
        assert data["session"]["status"] == "in_progress"

    pass  # test_concurrent_session_creation_returns_409 moved to standalone async test below


async def test_concurrent_session_creation_returns_409(
    async_client, async_auth_headers, async_db_session, async_test_user
):
    """
    Test that concurrent session creation attempts return 409 Conflict.

    BCQ-006: This test verifies the IntegrityError handling when the
    database-level partial unique index prevents duplicate in_progress
    sessions. The actual race condition is prevented by the partial
    unique index ix_test_sessions_user_active in PostgreSQL.

    BCQ-044: Also verifies that a warning log is written when a concurrent
    session creation is detected, including the user_id for debugging.

    Note: This test uses mocking since SQLite (used in tests) doesn't
    have the same partial unique index enforcement as PostgreSQL.
    The production PostgreSQL database has the index that triggers
    IntegrityError on duplicate in_progress sessions.

    This test uses async fixtures because the endpoint uses AsyncSession
    and we need to mock flush() on the exact session instance.
    """
    from unittest.mock import patch
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy import select
    from app.models import TestSession, Question
    from app.models.models import (
        TestStatus,
        QuestionType,
        DifficultyLevel,
    )

    # Create test questions in async session
    for i, (qtype, diff) in enumerate(
        [
            (QuestionType.PATTERN, DifficultyLevel.EASY),
            (QuestionType.LOGIC, DifficultyLevel.MEDIUM),
            (QuestionType.MATH, DifficultyLevel.HARD),
            (QuestionType.VERBAL, DifficultyLevel.MEDIUM),
        ]
    ):
        q = Question(
            question_text=f"Test question {i}",
            question_type=qtype,
            difficulty_level=diff,
            correct_answer="A",
            answer_options={"A": "a", "B": "b", "C": "c", "D": "d"},
            source_llm="test",
            judge_score=0.9,
            is_active=True,
        )
        async_db_session.add(q)
    await async_db_session.commit()

    # Start a test session first to verify normal operation
    response1 = await async_client.post(
        "/v1/test/start?question_count=2", headers=async_auth_headers
    )
    assert response1.status_code == 200

    # Complete the first session so the user can start another
    session_id = response1.json()["session"]["id"]
    result = await async_db_session.execute(
        select(TestSession).where(TestSession.id == session_id)
    )
    session = result.scalar_one()
    session.status = TestStatus.COMPLETED
    await async_db_session.commit()

    user_id = async_test_user.id

    # Now mock db.flush() to raise IntegrityError, simulating what
    # PostgreSQL's partial unique index would do on a race condition.
    # We patch flush on the specific async_db_session instance that the
    # endpoint receives via the dependency override.
    original_flush = async_db_session.flush

    async def mock_flush(objects=None):
        raise IntegrityError(
            statement="INSERT INTO test_sessions",
            params={},
            orig=Exception("duplicate key value violates unique constraint"),
        )

    async_db_session.flush = mock_flush

    # BCQ-044: Also mock the logger to verify warning is logged
    try:
        with patch("app.api.v1.test.logger") as mock_logger:
            response2 = await async_client.post(
                "/v1/test/start?question_count=2", headers=async_auth_headers
            )
    finally:
        async_db_session.flush = original_flush

    # Should return 409 Conflict with appropriate message
    assert response2.status_code == 409
    assert "already in progress" in response2.json()["detail"]

    # BCQ-044: Verify warning was logged with user_id context
    assert mock_logger.warning.called, "Expected warning log on race condition"
    warning_call_args = mock_logger.warning.call_args[0][0]
    assert "Race condition detected" in warning_call_args
    assert (
        str(user_id) in warning_call_args
    ), f"Expected user_id {user_id} in log message: {warning_call_args}"


class TestGetTestSession:
    """Tests for GET /v1/test/session/{session_id} endpoint."""

    def test_get_test_session_success(self, client, auth_headers, test_questions):
        """Test successfully getting a test session."""
        # Start a test first
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        start_questions = start_response.json()["questions"]
        started_at = start_response.json()["session"]["started_at"]

        # Get the session
        response = client.get(f"/v1/test/session/{session_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session" in data
        assert "questions_count" in data
        assert "questions" in data

        # Verify session field values are correct
        session = data["session"]
        assert session["id"] == session_id  # Exact ID match
        assert session["status"] == "in_progress"  # Exact enum value
        assert session["started_at"] == started_at  # Timestamp should match
        assert session["completed_at"] is None  # Not completed yet

        # Verify questions_count reflects the actual number of responses
        # For a fresh session with no responses yet, this should be 0
        assert data["questions_count"] == 0
        assert isinstance(data["questions_count"], int)

        # Verify questions are returned for in_progress sessions
        assert data["questions"] is not None
        assert len(data["questions"]) == 2

        # Verify question IDs match exactly those from start_test
        retrieved_q_ids = {q["id"] for q in data["questions"]}
        start_q_ids = {q["id"] for q in start_questions}
        assert retrieved_q_ids == start_q_ids

        # Verify question data matches what was returned at start
        for start_q in start_questions:
            matching_q = next(
                (q for q in data["questions"] if q["id"] == start_q["id"]), None
            )
            assert matching_q is not None
            assert matching_q["question_text"] == start_q["question_text"]
            assert matching_q["question_type"] == start_q["question_type"]
            assert matching_q["difficulty_level"] == start_q["difficulty_level"]

    def test_get_test_session_not_found(self, client, auth_headers):
        """Test getting non-existent session."""
        response = client.get("/v1/test/session/99999", headers=auth_headers)
        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_test_session_unauthorized_access(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that users cannot access other users' sessions."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from app.core.security import hash_password

        # Create second user
        user2 = User(
            email="user2@example.com",
            password_hash=hash_password("password123"),
            first_name="User",
            last_name="Two",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # Create session for user2
        session = TestSession(
            user_id=user2.id,
            status=TestStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Try to access user2's session with user1's credentials
        response = client.get(f"/v1/test/session/{session.id}", headers=auth_headers)

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]

    def test_get_test_session_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/v1/test/session/1")
        assert response.status_code in [401, 403]


class TestGetActiveTestSession:
    """Tests for GET /v1/test/active endpoint."""

    def test_get_active_session_exists(self, client, auth_headers, test_questions):
        """Test getting active session when one exists."""
        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]

        # Get active session
        response = client.get("/v1/test/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data is not None
        assert data["session"]["id"] == session_id
        assert data["session"]["status"] == "in_progress"

    def test_get_active_session_none(self, client, auth_headers):
        """Test getting active session when none exists."""
        response = client.get("/v1/test/active", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data is None

    def test_get_active_session_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        response = client.get("/v1/test/active")
        assert response.status_code in [401, 403]

    def test_get_active_session_ignores_completed(
        self, client, auth_headers, db_session, test_questions
    ):
        """Test that completed sessions are not returned as active."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from datetime import datetime

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create a completed session
        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(completed_session)
        db_session.commit()

        # Get active session (should be None)
        response = client.get("/v1/test/active", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() is None

    def test_get_active_session_ignores_abandoned(
        self, client, auth_headers, db_session, test_questions
    ):
        """Test that abandoned sessions are not returned as active."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from datetime import datetime

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create an abandoned session
        db_session.add(
            TestSession(
                user_id=test_user.id,
                status=TestStatus.ABANDONED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
        )
        db_session.commit()

        # Get active session (should be None)
        response = client.get("/v1/test/active", headers=auth_headers)

        assert response.status_code == 200
        assert response.json() is None


class TestAbandonTest:
    """Tests for POST /v1/test/{session_id}/abandon endpoint."""

    def test_abandon_test_success(self, client, auth_headers, test_questions):
        """Test successfully abandoning an in-progress test session."""
        # Start a test first
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        started_at = start_response.json()["session"]["started_at"]

        # Abandon the test
        response = client.post(f"/v1/test/{session_id}/abandon", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session" in data
        assert "message" in data
        assert "responses_saved" in data

        # Verify session field values are correct
        session = data["session"]
        assert session["id"] == session_id  # Exact ID match
        assert session["status"] == "abandoned"  # Exact enum value
        assert (
            session["started_at"] == started_at
        )  # Should preserve original start time
        assert session["completed_at"] is not None  # Should have completion timestamp

        # Verify completed_at is a valid timestamp (ISO format)
        from datetime import datetime

        completed_at = session["completed_at"]
        try:
            datetime.fromisoformat(completed_at.replace("Z", "+00:00"))
        except ValueError:
            raise AssertionError(
                f"completed_at '{completed_at}' is not a valid ISO timestamp"
            )

        # Verify message contains the action
        assert "abandoned successfully" in data["message"]

        # No responses saved for a fresh session with no answers
        assert data["responses_saved"] == 0
        assert isinstance(data["responses_saved"], int)

    def test_abandon_test_with_responses_saved(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test abandoning test with some responses already saved."""
        from app.models import User, TestSession
        from app.models.models import Response, TestStatus
        from datetime import datetime

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create a test session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Add some responses (simulating partial test completion)
        response1 = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=test_questions[0].id,
            user_answer="A",
            is_correct=True,
            answered_at=datetime.utcnow(),
        )
        response2 = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=test_questions[1].id,
            user_answer="B",
            is_correct=False,
            answered_at=datetime.utcnow(),
        )
        db_session.add(response1)
        db_session.add(response2)
        db_session.commit()

        # Abandon the test
        response = client.post(f"/v1/test/{session.id}/abandon", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should report 2 responses saved
        assert data["responses_saved"] == 2
        assert data["session"]["status"] == "abandoned"

    def test_abandon_test_not_found(self, client, auth_headers):
        """Test abandoning non-existent session."""
        response = client.post("/v1/test/99999/abandon", headers=auth_headers)

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_abandon_test_unauthorized_access(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that users cannot abandon other users' sessions."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from app.core.security import hash_password

        # Create second user
        user2 = User(
            email="user2@example.com",
            password_hash=hash_password("password123"),
            first_name="User",
            last_name="Two",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # Create session for user2
        session = TestSession(
            user_id=user2.id,
            status=TestStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Try to abandon user2's session with user1's credentials
        response = client.post(f"/v1/test/{session.id}/abandon", headers=auth_headers)

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]

    def test_abandon_test_already_completed(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that completed sessions cannot be abandoned."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from datetime import datetime

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create a completed session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Try to abandon completed session
        response = client.post(f"/v1/test/{session.id}/abandon", headers=auth_headers)

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"]

    def test_abandon_test_already_abandoned(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that abandoned sessions cannot be abandoned again."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from datetime import datetime

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create an abandoned session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.ABANDONED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Try to abandon already abandoned session
        response = client.post(f"/v1/test/{session.id}/abandon", headers=auth_headers)

        assert response.status_code == 400
        assert "already abandoned" in response.json()["detail"]

    def test_abandon_test_requires_authentication(self, client, test_questions):
        """Test that endpoint requires authentication."""
        response = client.post("/v1/test/1/abandon")
        assert response.status_code in [401, 403]

    def test_abandon_test_allows_new_session(
        self, client, auth_headers, test_questions
    ):
        """Test that user can start new test after abandoning."""
        # Start first test
        start_response1 = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response1.status_code == 200
        session_id1 = start_response1.json()["session"]["id"]

        # Abandon the test
        abandon_response = client.post(
            f"/v1/test/{session_id1}/abandon", headers=auth_headers
        )
        assert abandon_response.status_code == 200

        # Should be able to start a new test now
        start_response2 = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response2.status_code == 200
        session_id2 = start_response2.json()["session"]["id"]

        # Should be a different session
        assert session_id2 != session_id1


class TestSubmitTestWithTimeData:
    """Integration tests for test submission with time data (TS-013)."""

    def test_submit_with_time_data_stores_correctly(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that time_spent_seconds is stored correctly for each response."""
        from app.models.models import Response

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Build a map of question_id to correct_answer from test_questions fixture
        correct_answers = {q.id: q.correct_answer for q in test_questions}

        # Submit test with time data for each question
        # answer_options is a list like ["8", "10", "12", "14"]
        responses = [
            {
                "question_id": questions[0]["id"],
                "user_answer": questions[0]["answer_options"][0],  # First option
                "time_spent_seconds": 45,  # 45 seconds on question 1
            },
            {
                "question_id": questions[1]["id"],
                "user_answer": questions[1]["answer_options"][1],  # Second option
                "time_spent_seconds": 120,  # 2 minutes on question 2
            },
            {
                "question_id": questions[2]["id"],
                "user_answer": questions[2]["answer_options"][2],  # Third option
                "time_spent_seconds": 30,  # 30 seconds on question 3
            },
        ]

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "completed"  # Exact enum value
        assert data["responses_count"] == 3
        assert isinstance(data["responses_count"], int)

        # Verify time data was stored in the database
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )

        assert len(stored_responses) == 3

        # Create maps for verification
        expected_times = {r["question_id"]: r["time_spent_seconds"] for r in responses}
        expected_answers = {r["question_id"]: r["user_answer"] for r in responses}

        for resp in stored_responses:
            # Verify time_spent_seconds
            assert resp.time_spent_seconds == expected_times[resp.question_id]

            # Verify user_answer was stored correctly
            assert resp.user_answer == expected_answers[resp.question_id]

            # Verify is_correct is calculated based on correct_answer
            expected_correct = resp.user_answer == correct_answers[resp.question_id]
            assert resp.is_correct == expected_correct, (
                f"Question {resp.question_id}: expected is_correct={expected_correct}, "
                f"got {resp.is_correct}. user_answer={resp.user_answer}, "
                f"correct_answer={correct_answers[resp.question_id]}"
            )

            # Verify answered_at timestamp is set
            assert resp.answered_at is not None

    def test_submit_over_time_limit_sets_flag(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that time_limit_exceeded flag is set correctly when client reports it."""
        from app.models import TestSession

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test with time_limit_exceeded flag set (simulating auto-submit)
        # answer_options is a list like ["8", "10", "12", "14"]
        responses = [
            {
                "question_id": questions[0]["id"],
                "user_answer": questions[0]["answer_options"][0],  # First option
                "time_spent_seconds": 1000,  # About 16 minutes on question 1
            },
            {
                "question_id": questions[1]["id"],
                "user_answer": questions[1]["answer_options"][1],  # Second option
                "time_spent_seconds": 900,  # 15 minutes on question 2
            },
        ]

        submission = {
            "session_id": session_id,
            "responses": responses,
            "time_limit_exceeded": True,  # Client reports time limit exceeded
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "completed"

        # Verify time_limit_exceeded flag was set in the database
        test_session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert test_session.time_limit_exceeded is True

    def test_submit_with_anomalies_generates_flags(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that response time anomalies are detected and stored in response_time_flags."""
        from app.models.models import TestResult

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test with anomalous times:
        # - Question 1: Very fast (< 3 seconds) - should be flagged as "too_fast"
        # - Question 2: Normal time
        # - Question 3: Normal time
        # - Question 4: Very slow (> 300 seconds) - should be flagged as "too_slow"
        # answer_options is a list like ["8", "10", "12", "14"]
        responses = [
            {
                "question_id": questions[0]["id"],
                "user_answer": questions[0]["answer_options"][0],  # First option
                "time_spent_seconds": 1,  # Too fast - random clicking
            },
            {
                "question_id": questions[1]["id"],
                "user_answer": questions[1]["answer_options"][1],  # Second option
                "time_spent_seconds": 45,  # Normal
            },
            {
                "question_id": questions[2]["id"],
                "user_answer": questions[2]["answer_options"][2],  # Third option
                "time_spent_seconds": 60,  # Normal
            },
            {
                "question_id": questions[3]["id"],
                "user_answer": questions[3]["answer_options"][0],  # First option
                "time_spent_seconds": 350,  # Too slow - possible lookup
            },
        ]

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "completed"

        # Verify response_time_flags were stored in the test result
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        assert test_result is not None
        assert test_result.response_time_flags is not None

        # The flags should contain timing information
        flags = test_result.response_time_flags
        assert flags is not None
        assert isinstance(flags, dict)

        # Verify the structure contains expected fields from get_session_time_summary()
        # The summary format includes: rapid_responses, extended_times, rushed_session,
        # validity_concern, mean_time, flags
        expected_keys = [
            "flags",
            "rapid_responses",
            "extended_times",
            "validity_concern",
        ]
        for key in expected_keys:
            assert key in flags, f"Expected key '{key}' in response_time_flags"

        # flags["flags"] is a list of string flags like ["multiple_rapid_responses"]
        assert isinstance(flags["flags"], list)

        # Verify integer types for counts
        assert isinstance(flags["rapid_responses"], int)
        assert isinstance(flags["extended_times"], int)
        assert isinstance(flags["validity_concern"], bool)

        # The response should also include the flags with matching content
        assert data["result"]["response_time_flags"] is not None
        api_flags = data["result"]["response_time_flags"]
        assert api_flags == flags  # Database and API response should match

    def test_submit_without_time_data_backward_compatible(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that test submission works without time data (backward compatibility)."""
        from app.models.models import Response, TestResult

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test WITHOUT time_spent_seconds (old client behavior)
        # answer_options is a list like ["8", "10", "12", "14"]
        responses = [
            {
                "question_id": questions[0]["id"],
                "user_answer": questions[0]["answer_options"][0],  # First option
                # No time_spent_seconds
            },
            {
                "question_id": questions[1]["id"],
                "user_answer": questions[1]["answer_options"][1],  # Second option
                # No time_spent_seconds
            },
        ]

        submission = {
            "session_id": session_id,
            "responses": responses,
            # No time_limit_exceeded
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        # Submission should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "completed"
        assert data["responses_count"] == 2

        # Verify responses were stored with NULL time_spent_seconds
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )

        assert len(stored_responses) == 2
        for resp in stored_responses:
            assert resp.time_spent_seconds is None

        # Verify TestSession doesn't have time_limit_exceeded set
        from app.models import TestSession

        test_session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert test_session.time_limit_exceeded is False

        # Verify TestResult was created (scoring should work without time data)
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert test_result.iq_score is not None

    def test_submit_mixed_time_data_handles_partial(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test submission with some questions having time data and some without."""
        from app.models.models import Response

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test with mixed time data
        # answer_options is a list like ["8", "10", "12", "14"]
        responses = [
            {
                "question_id": questions[0]["id"],
                "user_answer": questions[0]["answer_options"][0],  # First option
                "time_spent_seconds": 45,  # Has time data
            },
            {
                "question_id": questions[1]["id"],
                "user_answer": questions[1]["answer_options"][1],  # Second option
                # No time_spent_seconds
            },
            {
                "question_id": questions[2]["id"],
                "user_answer": questions[2]["answer_options"][2],  # Third option
                "time_spent_seconds": 30,  # Has time data
            },
        ]

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        # Submission should succeed
        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "completed"

        # Verify responses were stored with correct time data
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .order_by(Response.question_id)
            .all()
        )

        assert len(stored_responses) == 3

        # Create map for verification
        response_times = {r.question_id: r.time_spent_seconds for r in stored_responses}

        # Question 0 and 2 have time data, question 1 doesn't
        assert response_times[questions[0]["id"]] == 45
        assert response_times[questions[1]["id"]] is None
        assert response_times[questions[2]["id"]] == 30


class TestSubmitTestWithDomainScores:
    """Integration tests for test submission with domain score calculation (DW-003)."""

    def test_submit_calculates_and_stores_domain_scores(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that domain scores are calculated and persisted in TestResult."""
        from app.models.models import TestResult

        # Start a test with 4 questions (covers 4 domains: pattern, logic, math, verbal)
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Map questions to their domains for verification
        # Based on conftest.py: pattern, logic, math, verbal
        question_domains = {}
        for q in questions:
            # Find the matching question in test_questions to get the domain
            for tq in test_questions:
                if tq.id == q["id"]:
                    question_domains[q["id"]] = tq.question_type.value
                    break

        # Submit test with known correct/incorrect answers
        # We need to find which answer is correct for each question
        responses = []
        for i, q in enumerate(questions):
            # Get the correct answer from test_questions
            correct_answer = None
            for tq in test_questions:
                if tq.id == q["id"]:
                    correct_answer = tq.correct_answer
                    break

            # Alternate: answer correctly for first two, incorrectly for last two
            if i < 2:
                # Answer correctly
                responses.append(
                    {"question_id": q["id"], "user_answer": correct_answer}
                )
            else:
                # Answer incorrectly (use first option which may or may not be correct)
                # Use a wrong answer by picking an option that's not the correct one
                wrong_answer = None
                for opt in q["answer_options"]:
                    if opt != correct_answer:
                        wrong_answer = opt
                        break
                responses.append(
                    {"question_id": q["id"], "user_answer": wrong_answer or "wrong"}
                )

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["session"]["status"] == "completed"

        # Verify domain scores were stored in the database
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        assert test_result is not None
        assert test_result.domain_scores is not None

        domain_scores = test_result.domain_scores

        # Verify structure: should have all 6 question types as keys
        expected_domains = [
            "pattern",
            "logic",
            "spatial",
            "math",
            "verbal",
            "memory",
        ]
        for domain in expected_domains:
            assert domain in domain_scores, f"Domain '{domain}' not in domain_scores"
            assert "correct" in domain_scores[domain]
            assert "total" in domain_scores[domain]
            assert "pct" in domain_scores[domain]

        # Verify domains that had questions have proper counts
        # The test has 4 questions covering 4 domains, each domain has 1 question
        domains_with_questions = set(question_domains.values())
        for domain in domains_with_questions:
            assert (
                domain_scores[domain]["total"] == 1
            ), f"Domain {domain} should have 1 question"

        # Verify domains without questions have zero total
        for domain in expected_domains:
            if domain not in domains_with_questions:
                assert (
                    domain_scores[domain]["total"] == 0
                ), f"Domain {domain} should have 0 questions"
                assert (
                    domain_scores[domain]["pct"] is None
                ), f"Domain {domain} should have pct=None"

    def test_submit_with_varying_question_distribution(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test domain scores work correctly with varying question distribution."""
        from app.models.models import TestResult

        # Start a test with just 2 questions (only 2 domains will be covered)
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Answer both correctly
        responses = []
        for q in questions:
            # Get correct answer
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200

        # Verify domain scores
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        assert test_result.domain_scores is not None
        domain_scores = test_result.domain_scores

        # Count how many domains have questions
        domains_with_questions = sum(
            1 for d in domain_scores.values() if d["total"] > 0
        )
        assert domains_with_questions == 2, "Only 2 domains should have questions"

        # Verify domains with questions have 100% correct (answered correctly)
        for domain_data in domain_scores.values():
            if domain_data["total"] > 0:
                assert domain_data["pct"] == pytest.approx(
                    100.0
                ), "All answered questions should be correct"


class TestDomainPercentilesInAPIResponse:
    """Integration tests for domain percentiles in API response (DW-016)."""

    def test_response_includes_strongest_weakest_domains(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that API response includes strongest and weakest domain identification."""
        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit with varying correctness to create clear strongest/weakest
        responses = []
        for i, q in enumerate(questions):
            # Get correct answer
            correct_answer = None
            for tq in test_questions:
                if tq.id == q["id"]:
                    correct_answer = tq.correct_answer
                    break

            # Answer first 2 correctly, last 2 incorrectly
            if i < 2:
                responses.append(
                    {"question_id": q["id"], "user_answer": correct_answer}
                )
            else:
                wrong_answer = None
                for opt in q["answer_options"]:
                    if opt != correct_answer:
                        wrong_answer = opt
                        break
                responses.append(
                    {"question_id": q["id"], "user_answer": wrong_answer or "wrong"}
                )

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify new API fields are present in the result
        result = data["result"]
        assert "strongest_domain" in result
        assert "weakest_domain" in result

        # With 4 questions across different domains, we should have identified domains
        # (unless all domains had same performance, in which case they could be same)
        assert (
            result["strongest_domain"] is not None
            or result["weakest_domain"] is not None
        )

    def test_response_domain_scores_includes_percentile_when_stats_configured(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that domain percentiles are included when population stats are configured."""
        from app.core.system_config import set_domain_population_stats

        # Configure population stats for domains
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
            "spatial": {"mean_accuracy": 0.55, "sd_accuracy": 0.22},
            "math": {"mean_accuracy": 0.62, "sd_accuracy": 0.19},
            "verbal": {"mean_accuracy": 0.68, "sd_accuracy": 0.17},
            "memory": {"mean_accuracy": 0.58, "sd_accuracy": 0.21},
        }
        set_domain_population_stats(db_session, population_stats)

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit all correct answers
        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Check domain_scores in result includes percentile field
        result = data["result"]
        domain_scores = result["domain_scores"]

        # Find domains that had questions
        for domain, scores in domain_scores.items():
            if scores["total"] > 0:
                # Should have percentile when population stats are configured
                assert "percentile" in scores, f"Domain {domain} should have percentile"
                # Percentile should be a valid number (0-100)
                assert scores["percentile"] is not None
                assert 0 <= scores["percentile"] <= 100

    def test_response_domain_percentiles_graceful_fallback_no_stats(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that domain percentiles gracefully fall back when no population stats."""
        from app.core.system_config import delete_config

        # Ensure no population stats are configured
        delete_config(db_session, "domain_population_stats")

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit answers
        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Request should succeed even without population stats
        result = data["result"]
        assert "domain_scores" in result
        assert "strongest_domain" in result
        assert "weakest_domain" in result

    def test_get_result_includes_domain_percentiles(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that GET /test/results/{id} includes domain percentiles."""
        from app.core.system_config import set_domain_population_stats

        # Configure population stats
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
            "spatial": {"mean_accuracy": 0.55, "sd_accuracy": 0.22},
            "math": {"mean_accuracy": 0.62, "sd_accuracy": 0.19},
            "verbal": {"mean_accuracy": 0.68, "sd_accuracy": 0.17},
            "memory": {"mean_accuracy": 0.58, "sd_accuracy": 0.21},
        }
        set_domain_population_stats(db_session, population_stats)

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        submit_response = client.post(
            "/v1/test/submit", json=submission, headers=auth_headers
        )
        assert submit_response.status_code == 200
        result_id = submit_response.json()["result"]["id"]

        # Now retrieve the result via GET endpoint
        get_response = client.get(f"/v1/test/results/{result_id}", headers=auth_headers)
        assert get_response.status_code == 200
        result = get_response.json()

        # Should include domain percentiles, strongest/weakest
        assert "domain_scores" in result
        assert "strongest_domain" in result
        assert "weakest_domain" in result

        # Domains with questions should have percentiles
        for domain, scores in result["domain_scores"].items():
            if scores["total"] > 0:
                assert "percentile" in scores

    def test_get_history_includes_domain_percentiles(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that GET /test/history includes domain percentiles for each result."""
        from app.core.system_config import set_domain_population_stats

        # Configure population stats
        population_stats = {
            "pattern": {"mean_accuracy": 0.65, "sd_accuracy": 0.18},
            "logic": {"mean_accuracy": 0.60, "sd_accuracy": 0.20},
            "spatial": {"mean_accuracy": 0.55, "sd_accuracy": 0.22},
            "math": {"mean_accuracy": 0.62, "sd_accuracy": 0.19},
            "verbal": {"mean_accuracy": 0.68, "sd_accuracy": 0.17},
            "memory": {"mean_accuracy": 0.58, "sd_accuracy": 0.21},
        }
        set_domain_population_stats(db_session, population_stats)

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        submit_response = client.post(
            "/v1/test/submit", json=submission, headers=auth_headers
        )
        assert submit_response.status_code == 200

        # Get history
        history_response = client.get("/v1/test/history", headers=auth_headers)
        assert history_response.status_code == 200
        history_data = history_response.json()
        history = history_data["results"]

        assert len(history) > 0

        # Each result should have domain info
        for result in history:
            assert "domain_scores" in result
            assert "strongest_domain" in result
            assert "weakest_domain" in result


class TestConfidenceIntervalIntegration:
    """Integration tests for SEM/CI calculation and storage in test submission flow (SEM-008).

    These tests verify the end-to-end behavior of confidence interval calculation,
    from test submission through API response and database storage.
    """

    def test_submit_with_reliability_data_populates_ci(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI is populated when reliability data is available and meets threshold.

        When Cronbach's alpha is >= 0.60, the submission should calculate and store
        SEM, ci_lower, and ci_upper values.
        """
        import pytest
        from unittest.mock import patch

        from app.models.models import TestResult

        # Start a test first (before mocking)
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test with correct answers (with mock active)
        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        # Mock get_cached_reliability to return the mock reliability value
        # This mocks at the API endpoint level where the function is called
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.85,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()

        # Verify CI is populated in the API response
        result = data["result"]
        assert "confidence_interval" in result
        ci = result["confidence_interval"]
        assert ci is not None
        assert "lower" in ci
        assert "upper" in ci
        assert "confidence_level" in ci
        assert "standard_error" in ci

        # Verify values are reasonable
        assert ci["confidence_level"] == pytest.approx(0.95)
        assert ci["standard_error"] > 0
        assert ci["lower"] < result["iq_score"]
        assert ci["upper"] > result["iq_score"]
        assert ci["lower"] < ci["upper"]

        # Verify database storage
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert test_result.standard_error is not None
        assert test_result.ci_lower is not None
        assert test_result.ci_upper is not None
        assert test_result.ci_lower == ci["lower"]
        assert test_result.ci_upper == ci["upper"]

    def test_submit_without_reliability_data_ci_is_null(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI is null when reliability data is unavailable.

        When there's insufficient data to calculate reliability (e.g., not enough
        test sessions), the submission should proceed but CI fields should be null.
        """
        from unittest.mock import patch

        from app.models.models import TestResult

        # Start a test first (before mocking)
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test
        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        # Mock get_cached_reliability to return None (insufficient data)
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        # Submission should succeed
        assert response.status_code == 200
        data = response.json()

        # CI should be null in response
        result = data["result"]
        assert result["confidence_interval"] is None

        # Database fields should be null
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert test_result.standard_error is None
        assert test_result.ci_lower is None
        assert test_result.ci_upper is None

    def test_submit_with_low_reliability_ci_is_null(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI is null when reliability is below threshold (< 0.60).

        When Cronbach's alpha is below 0.60, confidence intervals would be too
        wide to be meaningful, so they should not be calculated.

        Note: The MIN_RELIABILITY_FOR_SEM threshold check happens inside
        get_cached_reliability, so when reliability is too low, it returns None.
        """
        from unittest.mock import patch

        from app.models.models import TestResult

        # Start a test first (before mocking)
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit test
        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        # Mock get_cached_reliability to return None (simulating alpha < 0.60)
        # The actual threshold check happens inside get_cached_reliability
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=None,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        # Submission should succeed
        assert response.status_code == 200
        data = response.json()

        # CI should be null due to low reliability
        result = data["result"]
        assert result["confidence_interval"] is None

        # Database fields should be null
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert test_result.standard_error is None
        assert test_result.ci_lower is None
        assert test_result.ci_upper is None

    def test_api_response_ci_structure(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that API response includes correct CI structure with all required fields.

        Verifies the complete structure of the confidence_interval object in the
        API response matches the ConfidenceIntervalSchema specification.
        """
        import pytest
        from unittest.mock import patch

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        # Mock get_cached_reliability to return a good reliability value
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.80,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        assert response.status_code == 200
        data = response.json()

        # Verify complete CI structure
        ci = data["result"]["confidence_interval"]
        assert ci is not None

        # Check all required fields exist and have correct types
        assert isinstance(ci["lower"], int)
        assert isinstance(ci["upper"], int)
        assert isinstance(ci["confidence_level"], float)
        assert isinstance(ci["standard_error"], float)

        # Verify confidence_level is the standard 95%
        assert ci["confidence_level"] == pytest.approx(0.95)

        # Verify bounds are within reasonable IQ range (40-160 per schema)
        assert ci["lower"] >= 40
        assert ci["upper"] <= 160

    def test_ci_values_stored_correctly_in_database(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI values are correctly stored in the database.

        Verifies that standard_error, ci_lower, and ci_upper are persisted
        and match the expected calculated values.
        """
        import pytest
        from unittest.mock import patch

        from app.models.models import TestResult

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {
            "session_id": session_id,
            "responses": responses,
        }

        # Mock get_cached_reliability to return alpha = 0.80
        # Expected SEM = 15 * sqrt(1 - 0.80) = 15 * sqrt(0.20) ≈ 6.71
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.80,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        assert response.status_code == 200

        # Query database directly to verify storage
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        assert test_result is not None

        # Verify standard_error is approximately 6.71 (SEM for alpha=0.80)
        assert test_result.standard_error == pytest.approx(6.71, rel=0.01)

        # Verify CI bounds are integers
        assert isinstance(test_result.ci_lower, int)
        assert isinstance(test_result.ci_upper, int)

        # Verify CI bounds are symmetric around the score (within rounding)
        score = test_result.iq_score
        lower_margin = score - test_result.ci_lower
        upper_margin = test_result.ci_upper - score
        # Margins should be approximately equal (may differ by 1 due to rounding)
        assert abs(lower_margin - upper_margin) <= 1

        # Verify 95% CI margin is approximately 1.96 * SEM ≈ 13.15
        expected_margin = 1.96 * test_result.standard_error
        actual_margin = (upper_margin + lower_margin) / 2
        assert actual_margin == pytest.approx(expected_margin, abs=1)

    def test_submit_endpoint_returns_ci(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that POST /v1/test/submit returns CI in the response."""
        from unittest.mock import patch

        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {"session_id": session_id, "responses": responses}

        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.85,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        assert response.status_code == 200
        result = response.json()["result"]

        # Verify CI is present in submit response
        assert "confidence_interval" in result
        assert result["confidence_interval"] is not None
        assert result["confidence_interval"]["lower"] is not None
        assert result["confidence_interval"]["upper"] is not None

    def test_results_endpoint_returns_ci(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that GET /v1/test/results/{id} returns CI in the response."""
        from unittest.mock import patch

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {"session_id": session_id, "responses": responses}

        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.85,
        ):
            submit_response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )
        result_id = submit_response.json()["result"]["id"]

        # Get result by ID
        response = client.get(f"/v1/test/results/{result_id}", headers=auth_headers)

        assert response.status_code == 200
        result = response.json()

        # Verify CI is present
        assert "confidence_interval" in result
        assert result["confidence_interval"] is not None
        assert result["confidence_interval"]["lower"] is not None
        assert result["confidence_interval"]["upper"] is not None

    def test_history_endpoint_returns_ci(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that GET /v1/test/history returns CI for each result."""
        import pytest
        from unittest.mock import patch

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {"session_id": session_id, "responses": responses}

        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.85,
        ):
            client.post("/v1/test/submit", json=submission, headers=auth_headers)

        # Get history
        response = client.get("/v1/test/history", headers=auth_headers)

        assert response.status_code == 200
        history_data = response.json()
        history = history_data["results"]

        assert len(history) >= 1

        # Verify each result in history has CI
        for result in history:
            assert "confidence_interval" in result
            # CI may be null for older results without reliability data
            if result["confidence_interval"] is not None:
                assert result["confidence_interval"]["lower"] is not None
                assert result["confidence_interval"]["upper"] is not None
                assert result["confidence_interval"][
                    "confidence_level"
                ] == pytest.approx(0.95)

    def test_ci_null_in_all_endpoints_when_reliability_unavailable(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI is null across all endpoints when reliability is unavailable."""
        import pytest
        from unittest.mock import patch

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {"session_id": session_id, "responses": responses}

        # 1. Check /submit endpoint - mock no reliability data
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=None,
        ):
            submit_response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )
        assert submit_response.status_code == 200
        assert submit_response.json()["result"]["confidence_interval"] is None
        result_id = submit_response.json()["result"]["id"]

        # 2. Check /results/{id} endpoint
        results_response = client.get(
            f"/v1/test/results/{result_id}", headers=auth_headers
        )
        assert results_response.status_code == 200
        assert results_response.json()["confidence_interval"] is None

        # 3. Check /history endpoint
        history_response = client.get("/v1/test/history", headers=auth_headers)
        assert history_response.status_code == 200
        history_data = history_response.json()
        assert len(history_data["results"]) >= 1
        # Find our result in history
        for result in history_data["results"]:
            if result["id"] == result_id:
                assert result["confidence_interval"] is None
                break
        else:
            pytest.fail(f"Result {result_id} not found in history")

    def test_ci_boundary_values_respected(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI bounds respect the schema boundary values (40-160).

        While the schema enforces 40-160 bounds, this test verifies the calculation
        doesn't produce values outside this range even for extreme scores.
        """
        from unittest.mock import patch

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {"session_id": session_id, "responses": responses}

        # Mock high reliability for narrow CI
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.90,
        ):
            response = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        assert response.status_code == 200
        ci = response.json()["result"]["confidence_interval"]

        # Verify bounds are within schema limits
        assert ci["lower"] >= 40, f"Lower bound {ci['lower']} is below minimum 40"
        assert ci["upper"] <= 160, f"Upper bound {ci['upper']} is above maximum 160"

    def test_ci_width_decreases_with_higher_reliability(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that CI width is narrower with higher reliability.

        This test verifies the mathematical relationship between reliability
        and CI width without needing multiple test submissions.
        """
        import pytest
        from unittest.mock import patch

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        responses = []
        for q in questions:
            for tq in test_questions:
                if tq.id == q["id"]:
                    responses.append(
                        {"question_id": q["id"], "user_answer": tq.correct_answer}
                    )
                    break

        submission = {"session_id": session_id, "responses": responses}

        # Test with low reliability (0.60) - should have wider CI
        with patch(
            "app.api.v1.test.async_get_cached_reliability",
            new_callable=AsyncMock,
            return_value=0.60,
        ):
            response_low = client.post(
                "/v1/test/submit", json=submission, headers=auth_headers
            )

        assert response_low.status_code == 200
        ci_low = response_low.json()["result"]["confidence_interval"]
        assert ci_low is not None
        width_low = ci_low["upper"] - ci_low["lower"]

        # Calculate expected width for high reliability
        # For alpha=0.60: SEM = 15 * sqrt(1 - 0.60) = 9.49
        # For alpha=0.90: SEM = 15 * sqrt(1 - 0.90) = 4.74
        # Expected CI width ratio should be approximately 9.49/4.74 = 2.0

        # Verify SEM is correct for low reliability
        sem_low = ci_low["standard_error"]
        expected_sem_low = 15 * (0.40**0.5)  # 9.49
        assert sem_low == pytest.approx(expected_sem_low, rel=0.01)

        # Verify CI width is proportional to SEM
        # 95% CI width = 2 * 1.96 * SEM ≈ 3.92 * SEM
        expected_width_low = 2 * 1.96 * sem_low
        # Allow for rounding (CI bounds are integers)
        assert width_low == pytest.approx(expected_width_low, abs=2)

        # Test mathematical relationship: higher reliability = narrower CI
        # We can't submit another test in the same test run, but we can verify
        # the relationship mathematically
        expected_sem_high = 15 * (0.10**0.5)  # 4.74 for alpha=0.90
        expected_width_high = 2 * 1.96 * expected_sem_high

        # Verify high reliability produces narrower CI than low reliability
        assert expected_width_high < width_low, (
            f"Higher reliability should produce narrower CI: "
            f"expected_width_high={expected_width_high:.1f} should be < "
            f"width_low={width_low}"
        )


class TestGetTestSessionOr404:
    """Unit tests for get_test_session_or_404 helper function."""

    async def test_returns_session_when_found(self, async_db_session, async_test_user):
        """Test that helper returns session when it exists."""
        from app.api.v1.test import get_test_session_or_404
        from app.models import TestSession
        from app.models.models import TestStatus

        # Create a test session
        session = TestSession(
            user_id=async_test_user.id,
            status=TestStatus.IN_PROGRESS,
        )
        async_db_session.add(session)
        await async_db_session.commit()
        await async_db_session.refresh(session)

        # Call helper - should return the session
        result = await get_test_session_or_404(async_db_session, session.id)

        assert result is not None
        assert result.id == session.id
        assert result.user_id == async_test_user.id
        assert result.status == TestStatus.IN_PROGRESS

    async def test_raises_404_when_session_not_found(self, async_db_session):
        """Test that helper raises HTTPException with 404 when session doesn't exist."""
        from app.api.v1.test import get_test_session_or_404
        from fastapi import HTTPException
        import pytest

        # Call helper with non-existent session ID
        with pytest.raises(HTTPException) as exc_info:
            await get_test_session_or_404(async_db_session, 99999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Test session not found."

    async def test_error_message_is_consistent(self, async_db_session):
        """Test that error message format is consistent."""
        from app.api.v1.test import get_test_session_or_404
        from fastapi import HTTPException
        import pytest

        # Try multiple non-existent IDs to verify consistent error message
        for session_id in [1, 100, 99999]:
            with pytest.raises(HTTPException) as exc_info:
                await get_test_session_or_404(async_db_session, session_id)

            # Verify consistent error format
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Test session not found."

    async def test_returns_session_regardless_of_status(
        self, async_db_session, async_test_user
    ):
        """Test that helper returns sessions in any status (not just in_progress)."""
        from app.api.v1.test import get_test_session_or_404
        from app.models import TestSession
        from app.models.models import TestStatus
        from app.core.datetime_utils import utc_now

        # Test with each status
        statuses = [
            TestStatus.IN_PROGRESS,
            TestStatus.COMPLETED,
            TestStatus.ABANDONED,
        ]

        for status in statuses:
            session = TestSession(
                user_id=async_test_user.id,
                status=status,
                completed_at=utc_now() if status != TestStatus.IN_PROGRESS else None,
            )
            async_db_session.add(session)
            await async_db_session.commit()
            await async_db_session.refresh(session)

            # Helper should return session regardless of status
            result = await get_test_session_or_404(async_db_session, session.id)

            assert result is not None
            assert result.id == session.id
            assert result.status == status


class TestBoundaryConditions:
    """Tests for boundary conditions and edge cases (BCQ-031).

    These tests verify behavior at exact boundary values for:
    - Test cadence (exactly at 90 days vs 89 days)
    - Empty response submissions
    - Maximum concurrent sessions
    """

    def test_start_test_exactly_at_cadence_boundary_succeeds(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that starting a test exactly 90 days after last completed test succeeds.

        This tests the boundary condition where completed_at is exactly TEST_CADENCE_DAYS
        ago. The user should be allowed to start a new test.

        Boundary: completed_at == utc_now() - timedelta(days=90) should succeed.
        """
        from datetime import timedelta

        from app.core.config import settings
        from app.core.datetime_utils import utc_now
        from app.models import TestSession, User
        from app.models.models import TestStatus

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create a completed test session exactly TEST_CADENCE_DAYS (90 days) ago
        # Using exactly 90 days, no extra hours
        completed_time = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=completed_time - timedelta(hours=1),
            completed_at=completed_time,
        )
        db_session.add(completed_session)
        db_session.commit()

        # Try to start a new test - should succeed
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        assert response.status_code == 200, (
            f"Expected 200 OK at exactly {settings.TEST_CADENCE_DAYS} days, "
            f"got {response.status_code}: {response.json()}"
        )
        data = response.json()
        assert "session" in data
        assert data["session"]["status"] == "in_progress"

    def test_start_test_one_day_before_cadence_fails(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that starting a test 89 days after last completed test fails.

        This tests the boundary condition where completed_at is one day short of
        TEST_CADENCE_DAYS. The user should NOT be allowed to start a new test.

        Boundary: completed_at == utc_now() - timedelta(days=89) should fail.
        """
        from datetime import timedelta

        from app.core.config import settings
        from app.core.datetime_utils import utc_now
        from app.models import TestSession, User
        from app.models.models import TestStatus

        # Get test user
        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create a completed test session exactly (TEST_CADENCE_DAYS - 1) days ago
        days_since_last = settings.TEST_CADENCE_DAYS - 1  # 89 days
        completed_time = utc_now() - timedelta(days=days_since_last)
        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=completed_time - timedelta(hours=1),
            completed_at=completed_time,
        )
        db_session.add(completed_session)
        db_session.commit()

        # Try to start a new test - should fail with 400
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        assert response.status_code == 400, (
            f"Expected 400 Bad Request at {days_since_last} days, "
            f"got {response.status_code}"
        )
        detail = response.json()["detail"]
        # Verify the error message mentions the cadence period
        assert (
            f"{settings.TEST_CADENCE_DAYS} days" in detail or "3 months" in detail
        ), f"Error should mention cadence period: {detail}"
        # Verify remaining days is mentioned (should be 1 day remaining)
        assert (
            "1 day" in detail or "days remaining" in detail
        ), f"Error should mention days remaining: {detail}"

    def test_submit_with_empty_response_list(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that submitting a test with empty response list fails validation.

        Empty response lists should be rejected - a test must have at least one response.
        This tests the edge case where the client submits without answering any questions.
        """
        # Start a test first
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]

        # Submit with empty responses list
        submission = {
            "session_id": session_id,
            "responses": [],  # Empty list
        }

        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        # Empty response list should be rejected with 422 (validation error)
        # or 400 (bad request)
        assert response.status_code in [
            400,
            422,
        ], f"Expected 400 or 422 for empty responses, got {response.status_code}"

    def test_maximum_concurrent_sessions_is_one(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that maximum concurrent in_progress sessions is exactly 1.

        The system should enforce that a user can only have ONE in_progress session
        at any time. This is enforced by:
        1. Application-level check (returns 400 with session_id)
        2. Database-level partial unique index (returns 409 on race condition)

        This test verifies the application-level enforcement.
        """
        # Start first session
        response1 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response1.status_code == 200
        session1_id = response1.json()["session"]["id"]

        # Attempt to start second session - should be blocked
        response2 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response2.status_code == 400
        assert "already has an active test session" in response2.json()["detail"]
        assert str(session1_id) in response2.json()["detail"]

        # Attempt to start third session - still blocked (same session active)
        response3 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response3.status_code == 400
        assert str(session1_id) in response3.json()["detail"]

        # Complete the first session
        from app.models import TestSession
        from app.models.models import TestStatus

        session = (
            db_session.query(TestSession).filter(TestSession.id == session1_id).first()
        )
        session.status = TestStatus.COMPLETED
        db_session.commit()

        # Now we can start a new session
        response4 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response4.status_code == 200
        session2_id = response4.json()["session"]["id"]
        assert session2_id != session1_id

    def test_cadence_boundary_with_timezone_edge_case(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test cadence boundary when completed_at is exactly at the cutoff with timezone.

        This tests a subtle edge case: if the completed_at timestamp is exactly
        at the cadence cutoff point, the comparison should correctly allow the test.
        The cadence check uses: completed_at > cadence_cutoff
        So completed_at == cadence_cutoff should NOT block (since > not >=).

        Verifies that the boundary is handled correctly: exactly 90 days is allowed.
        """
        from datetime import timedelta

        from app.core.config import settings
        from app.core.datetime_utils import utc_now
        from app.models import TestSession, User
        from app.models.models import TestStatus

        test_user = (
            db_session.query(User).filter(User.email == "test@example.com").first()
        )

        # Create session completed exactly at the cadence cutoff
        # The query is: TestSession.completed_at > cadence_cutoff
        # Where cadence_cutoff = utc_now() - timedelta(days=TEST_CADENCE_DAYS)
        # So if completed_at == cadence_cutoff, the condition is False (not >)
        # meaning no recent session is found, and test is allowed
        now = utc_now()
        cadence_cutoff = now - timedelta(days=settings.TEST_CADENCE_DAYS)

        # Set completed_at exactly at the cutoff
        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=cadence_cutoff - timedelta(hours=1),
            completed_at=cadence_cutoff,  # Exactly at cutoff
        )
        db_session.add(completed_session)
        db_session.commit()

        # The query checks: completed_at > cadence_cutoff
        # Since completed_at == cadence_cutoff, the condition is False
        # So no "recent" completed session is found, and test should be allowed
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        assert response.status_code == 200, (
            f"Test at exactly cadence cutoff should succeed, "
            f"got {response.status_code}: {response.json()}"
        )


class TestValueCorrectness:
    """Tests verifying that calculated values are correct, not just structure (BCQ-032).

    These tests go beyond structure verification to ensure:
    - Correct scoring calculations
    - Accurate response tracking
    - Proper enum value propagation
    - Correct relationship between stored and returned values
    """

    def test_correct_answers_scored_correctly(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that correct answers result in is_correct=True and proper scoring."""
        from app.models.models import Response, TestResult

        # Start a test with 4 questions
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Build correct answer map
        correct_answers = {q.id: q.correct_answer for q in test_questions}

        # Submit ALL correct answers
        responses = []
        for q in questions:
            correct_answer = correct_answers.get(q["id"])
            assert (
                correct_answer is not None
            ), f"Question {q['id']} not in test_questions"
            responses.append({"question_id": q["id"], "user_answer": correct_answer})

        submission = {"session_id": session_id, "responses": responses}
        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200

        # Verify all responses are marked correct in database
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )
        assert len(stored_responses) == 4

        for resp in stored_responses:
            assert resp.is_correct is True, (
                f"Response for question {resp.question_id} should be correct. "
                f"user_answer={resp.user_answer}, "
                f"correct_answer={correct_answers[resp.question_id]}"
            )

        # Verify result has all answers correct
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert (
            test_result.correct_answers == 4
        ), f"Expected 4 correct answers, got {test_result.correct_answers}"
        assert test_result.total_questions == 4

    def test_incorrect_answers_scored_correctly(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that incorrect answers result in is_correct=False and proper scoring."""
        from app.models.models import Response, TestResult

        # Start a test with 4 questions
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Build correct answer map
        correct_answers = {q.id: q.correct_answer for q in test_questions}

        # Submit ALL incorrect answers
        responses = []
        for q in questions:
            correct_answer = correct_answers.get(q["id"])
            # Find a wrong answer
            wrong_answer = None
            for opt in q["answer_options"]:
                if opt != correct_answer:
                    wrong_answer = opt
                    break
            assert wrong_answer is not None
            responses.append({"question_id": q["id"], "user_answer": wrong_answer})

        submission = {"session_id": session_id, "responses": responses}
        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200

        # Verify all responses are marked incorrect in database
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )
        assert len(stored_responses) == 4

        for resp in stored_responses:
            assert resp.is_correct is False, (
                f"Response for question {resp.question_id} should be incorrect. "
                f"user_answer={resp.user_answer}, "
                f"correct_answer={correct_answers[resp.question_id]}"
            )

        # Verify result has no correct answers
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert (
            test_result.correct_answers == 0
        ), f"Expected 0 correct answers, got {test_result.correct_answers}"
        assert test_result.total_questions == 4

    def test_mixed_answers_scored_proportionally(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that mixed correct/incorrect answers result in proportional scoring."""
        from app.models.models import Response, TestResult

        # Start a test with 4 questions
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Build correct answer map
        correct_answers = {q.id: q.correct_answer for q in test_questions}

        # Submit 2 correct, 2 incorrect (50%)
        responses = []
        for i, q in enumerate(questions):
            correct_answer = correct_answers.get(q["id"])
            if i < 2:
                # Correct
                responses.append(
                    {"question_id": q["id"], "user_answer": correct_answer}
                )
            else:
                # Incorrect
                wrong_answer = next(
                    opt for opt in q["answer_options"] if opt != correct_answer
                )
                responses.append({"question_id": q["id"], "user_answer": wrong_answer})

        submission = {"session_id": session_id, "responses": responses}
        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200

        # Verify is_correct matches our expectations
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )

        # Count correct/incorrect
        correct_count = sum(1 for r in stored_responses if r.is_correct)
        incorrect_count = sum(1 for r in stored_responses if not r.is_correct)

        assert correct_count == 2, f"Expected 2 correct, got {correct_count}"
        assert incorrect_count == 2, f"Expected 2 incorrect, got {incorrect_count}"

        # Verify result has 2 correct answers (50%)
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert (
            test_result.correct_answers == 2
        ), f"Expected 2 correct answers, got {test_result.correct_answers}"
        assert test_result.total_questions == 4

    def test_response_count_matches_submitted_count(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that responses_count in API matches actual stored responses."""
        from app.models.models import Response

        # Start a test with 3 questions
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit all 3 answers
        responses = [
            {"question_id": q["id"], "user_answer": q["answer_options"][0]}
            for q in questions
        ]

        submission = {"session_id": session_id, "responses": responses}
        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify responses_count in API matches
        assert data["responses_count"] == 3

        # Verify database count matches
        db_count = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .count()
        )
        assert db_count == 3
        assert db_count == data["responses_count"]

    def test_session_status_enum_values_correct(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that session status enum values are correctly represented in API."""
        from app.models import TestSession
        from app.models.models import TestStatus

        # Start a test - should be "in_progress"
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]

        # Verify status is exact string "in_progress"
        assert start_response.json()["session"]["status"] == "in_progress"

        # Verify database has matching enum
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert session.status == TestStatus.IN_PROGRESS
        assert session.status.value == "in_progress"

        # Submit test - should become "completed"
        questions = start_response.json()["questions"]
        responses = [
            {"question_id": q["id"], "user_answer": q["answer_options"][0]}
            for q in questions
        ]
        submission = {"session_id": session_id, "responses": responses}
        submit_response = client.post(
            "/v1/test/submit", json=submission, headers=auth_headers
        )

        assert submit_response.status_code == 200
        assert submit_response.json()["session"]["status"] == "completed"

        # Verify database has matching enum
        db_session.refresh(session)
        assert session.status == TestStatus.COMPLETED
        assert session.status.value == "completed"

    def test_result_iq_score_within_valid_range(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that IQ score is within the valid schema range (40-160)."""
        from app.models.models import TestResult

        # Start and complete a test
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit answers
        responses = [
            {"question_id": q["id"], "user_answer": q["answer_options"][0]}
            for q in questions
        ]
        submission = {"session_id": session_id, "responses": responses}
        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify IQ score is within valid range
        iq_score = data["result"]["iq_score"]
        assert 40 <= iq_score <= 160, f"IQ score {iq_score} outside valid range 40-160"

        # Verify database value matches
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result.iq_score == iq_score

    def test_domain_scores_sum_to_expected_totals(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that domain scores correct+incorrect equals total for each domain."""
        import pytest

        # Start a test with all 4 questions
        start_response = client.post(
            "/v1/test/start?question_count=4", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Build correct answer map
        correct_answers = {q.id: q.correct_answer for q in test_questions}

        # Submit with known correct/incorrect pattern
        responses = []
        for i, q in enumerate(questions):
            correct_answer = correct_answers.get(q["id"])
            if i % 2 == 0:
                responses.append(
                    {"question_id": q["id"], "user_answer": correct_answer}
                )
            else:
                wrong_answer = next(
                    opt for opt in q["answer_options"] if opt != correct_answer
                )
                responses.append({"question_id": q["id"], "user_answer": wrong_answer})

        submission = {"session_id": session_id, "responses": responses}
        response = client.post("/v1/test/submit", json=submission, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify domain scores are internally consistent
        domain_scores = data["result"]["domain_scores"]

        total_questions = 0
        total_correct = 0

        for domain, scores in domain_scores.items():
            # Each domain should have consistent data
            assert isinstance(scores["total"], int)
            assert isinstance(scores["correct"], int)
            assert scores["correct"] <= scores["total"]

            # If there are questions, pct should be calculable
            if scores["total"] > 0:
                expected_pct = (scores["correct"] / scores["total"]) * 100
                assert scores["pct"] == pytest.approx(
                    expected_pct
                ), f"Domain {domain} pct mismatch"

            total_questions += scores["total"]
            total_correct += scores["correct"]

        # Total across all domains should equal questions answered
        assert (
            total_questions == 4
        ), f"Expected 4 total questions, got {total_questions}"


class TestAdaptiveSession:
    """Tests for is_adaptive flag on test sessions (TASK-835)."""

    def test_default_session_not_adaptive(self, client, auth_headers, test_questions):
        """Default session (no CAT config) has is_adaptive=False."""
        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response.status_code == 200
        session = response.json()["session"]
        assert session["is_adaptive"] is False

    def test_cat_enabled_session_is_adaptive(
        self, client, auth_headers, test_questions, db_session
    ):
        """Session has is_adaptive=True when CAT is enabled in SystemConfig."""
        from app.core.system_config import set_cat_readiness

        set_cat_readiness(db_session, {"enabled": True})

        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response.status_code == 200
        session = response.json()["session"]
        assert session["is_adaptive"] is True

    def test_is_adaptive_persisted_in_database(
        self, client, auth_headers, test_questions, db_session
    ):
        """is_adaptive flag is persisted in the database."""
        from app.models import TestSession
        from app.core.system_config import set_cat_readiness

        set_cat_readiness(db_session, {"enabled": True})

        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response.status_code == 200
        session_id = response.json()["session"]["id"]

        db_session.expire_all()
        test_session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert test_session.is_adaptive is True


class TestAdaptiveParameter:
    """Tests for adaptive parameter on POST /v1/test/start endpoint (TASK-878)."""

    def test_adaptive_false_returns_all_questions(
        self, client, auth_headers, test_questions
    ):
        """Test adaptive=false returns all questions (fixed-form behavior)."""
        response = client.post(
            "/v1/test/start?question_count=3&adaptive=false", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Should return all requested questions
        assert len(data["questions"]) == 3
        assert data["total_questions"] == 3

        # CAT fields should not be populated
        assert data.get("current_theta") is None
        assert data.get("current_se") is None

        # Session should not be adaptive
        assert data["session"]["is_adaptive"] is False

    def test_adaptive_default_is_false(self, client, auth_headers, test_questions):
        """Test that adaptive parameter defaults to false when not specified."""
        response = client.post("/v1/test/start?question_count=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should behave like fixed-form
        assert len(data["questions"]) == 3
        assert data["total_questions"] == 3
        assert data.get("current_theta") is None
        assert data.get("current_se") is None
        assert data["session"]["is_adaptive"] is False

    def test_adaptive_true_returns_single_question(
        self, client, auth_headers, db_session
    ):
        """Test adaptive=true returns single question with CAT fields."""
        from app.models import Question
        from app.models.models import QuestionType, DifficultyLevel

        # Create calibrated questions with IRT parameters
        calibrated_questions = [
            Question(
                question_text="Easy pattern question",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                irt_difficulty=-1.0,
                irt_discrimination=1.2,
                is_active=True,
            ),
            Question(
                question_text="Medium logic question",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="B",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                irt_difficulty=0.0,
                irt_discrimination=1.5,
                is_active=True,
            ),
            Question(
                question_text="Hard math question",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.HARD,
                correct_answer="C",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                irt_difficulty=1.0,
                irt_discrimination=1.8,
                is_active=True,
            ),
        ]

        for q in calibrated_questions:
            db_session.add(q)
        db_session.commit()

        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return single question
        assert len(data["questions"]) == 1
        assert data["total_questions"] == 1

        # CAT fields should be populated
        assert data["current_theta"] is not None
        assert data["current_se"] is not None
        assert isinstance(data["current_theta"], float)
        assert isinstance(data["current_se"], float)

        # Session should be adaptive
        assert data["session"]["is_adaptive"] is True

    def test_adaptive_true_initializes_theta_history(
        self, client, auth_headers, db_session, test_user
    ):
        """Test adaptive=true initializes theta_history as empty array."""
        from app.models import Question, TestSession
        from app.models.models import QuestionType, DifficultyLevel

        # Create calibrated question
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            irt_difficulty=0.0,
            irt_discrimination=1.0,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)

        assert response.status_code == 200
        session_id = response.json()["session"]["id"]

        # Check database for theta_history initialization
        db_session.expire_all()
        test_session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )

        assert test_session.theta_history is not None
        assert test_session.theta_history == []
        assert test_session.is_adaptive is True

    def test_adaptive_true_uses_prior_theta(
        self, client, auth_headers, db_session, test_user
    ):
        """Test adaptive=true uses prior theta from previous session."""
        from app.models import Question, TestSession
        from app.models.models import QuestionType, DifficultyLevel, TestStatus

        # Create calibrated questions
        for i in range(3):
            question = Question(
                question_text=f"Test question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options={"A": "1", "B": "2"},
                irt_difficulty=0.0,
                irt_discrimination=1.0,
                is_active=True,
            )
            db_session.add(question)

        # Create a previous completed adaptive session with final_theta
        # Set completed_at to be > 180 days ago to avoid test cadence check
        old_date = datetime.utcnow() - timedelta(days=200)
        previous_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=True,
            final_theta=0.75,
            final_se=0.25,
            started_at=old_date - timedelta(minutes=30),
            completed_at=old_date,
        )
        db_session.add(previous_session)
        db_session.commit()

        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Current theta should be the prior from previous session
        assert data["current_theta"] == pytest.approx(0.75, abs=0.01)

    def test_adaptive_true_no_calibrated_questions(
        self, client, auth_headers, test_questions
    ):
        """Test adaptive=true returns 404 when no calibrated questions available."""
        # test_questions fixture doesn't have IRT parameters
        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)

        assert response.status_code == 404
        data = response.json()
        assert "No unseen questions available" in data["detail"]

    def test_adaptive_independent_of_system_cat_flag(
        self, client, auth_headers, db_session, test_user
    ):
        """Test adaptive parameter works independently of is_cat_enabled system flag."""
        from app.models import Question
        from app.models.models import QuestionType, DifficultyLevel
        from app.core.system_config import set_cat_readiness

        # Set system CAT flag to False
        set_cat_readiness(db_session, {"enabled": False})

        # Create calibrated question
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            irt_difficulty=0.0,
            irt_discrimination=1.0,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        # Should still work with adaptive=true even though system CAT is disabled
        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["questions"]) == 1
        assert data["session"]["is_adaptive"] is True

    def test_adaptive_true_marks_question_as_seen(
        self, client, auth_headers, db_session, test_user
    ):
        """Test adaptive=true marks the selected question as seen."""
        from app.models import Question, UserQuestion
        from app.models.models import QuestionType, DifficultyLevel

        # Create calibrated question
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            irt_difficulty=0.0,
            irt_discrimination=1.0,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)

        assert response.status_code == 200
        question_id = response.json()["questions"][0]["id"]

        # Check that question is marked as seen
        user_question = (
            db_session.query(UserQuestion)
            .filter(
                UserQuestion.user_id == test_user.id,
                UserQuestion.question_id == question_id,
            )
            .first()
        )

        assert user_question is not None
        assert user_question.seen_at is not None
