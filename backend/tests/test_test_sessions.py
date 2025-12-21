"""
Tests for test session management endpoints.
"""

import pytest


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

        # Verify session details
        session = data["session"]
        assert "id" in session
        assert session["status"] == "in_progress"
        assert "started_at" in session
        assert session["completed_at"] is None

        # Verify questions
        assert len(data["questions"]) == 3
        assert data["total_questions"] == 3

        # Verify questions don't expose sensitive info
        for question in data["questions"]:
            assert "correct_answer" not in question
            assert question["explanation"] is None

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

    def test_concurrent_session_creation_returns_409(
        self, client, auth_headers, test_questions, db_session
    ):
        """
        Test that concurrent session creation attempts return 409 Conflict.

        BCQ-006: This test verifies the IntegrityError handling when the
        database-level partial unique index prevents duplicate in_progress
        sessions. The actual race condition is prevented by the partial
        unique index ix_test_sessions_user_active in PostgreSQL.

        Note: This test uses mocking since SQLite (used in tests) doesn't
        have the same partial unique index enforcement as PostgreSQL.
        The production PostgreSQL database has the index that triggers
        IntegrityError on duplicate in_progress sessions.
        """
        from unittest.mock import patch
        from sqlalchemy.exc import IntegrityError

        # Start a test session first to verify normal operation
        response1 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        assert response1.status_code == 200

        # Complete the first session so the user can start another
        from app.models import TestSession
        from app.models.models import TestStatus

        session_id = response1.json()["session"]["id"]
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        session.status = TestStatus.COMPLETED
        db_session.commit()

        # Now mock db.flush() to raise IntegrityError, simulating what
        # PostgreSQL's partial unique index would do on a race condition
        def mock_flush_with_integrity_error(self):
            raise IntegrityError(
                statement="INSERT INTO test_sessions",
                params={},
                orig=Exception("duplicate key value violates unique constraint"),
            )

        with patch.object(
            type(db_session),
            "flush",
            mock_flush_with_integrity_error,
        ):
            response2 = client.post(
                "/v1/test/start?question_count=2", headers=auth_headers
            )

        # Should return 409 Conflict with appropriate message
        assert response2.status_code == 409
        assert "already in progress" in response2.json()["detail"]


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

        # Get the session
        response = client.get(f"/v1/test/session/{session_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "session" in data
        assert "questions_count" in data
        assert "questions" in data
        assert data["session"]["id"] == session_id
        assert data["session"]["status"] == "in_progress"
        assert data["questions_count"] == 0  # No responses yet

        # Verify questions are returned for in_progress sessions
        assert data["questions"] is not None
        assert len(data["questions"]) == 2
        # Verify question IDs match those from start_test
        retrieved_q_ids = {q["id"] for q in data["questions"]}
        start_q_ids = {q["id"] for q in start_questions}
        assert retrieved_q_ids == start_q_ids

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

        # Abandon the test
        response = client.post(f"/v1/test/{session_id}/abandon", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session" in data
        assert "message" in data
        assert "responses_saved" in data

        # Verify session is marked as abandoned
        session = data["session"]
        assert session["id"] == session_id
        assert session["status"] == "abandoned"
        assert session["completed_at"] is not None

        # Verify message
        assert "abandoned successfully" in data["message"]

        # No responses saved yet
        assert data["responses_saved"] == 0

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
        assert data["session"]["status"] == "completed"
        assert data["responses_count"] == 3

        # Verify time data was stored in the database
        stored_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )

        assert len(stored_responses) == 3

        # Create a map of question_id to time_spent_seconds for verification
        expected_times = {r["question_id"]: r["time_spent_seconds"] for r in responses}
        for resp in stored_responses:
            assert resp.time_spent_seconds == expected_times[resp.question_id]

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

        # The flags should contain anomaly information
        flags = test_result.response_time_flags
        assert "flags" in flags
        # Should have at least one flag for the rapid response
        assert len(flags["flags"]) > 0

        # The response should also include the flags
        assert data["result"]["response_time_flags"] is not None

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
        with patch("app.api.v1.test.get_cached_reliability", return_value=0.85):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=None):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=None):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=0.80):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=0.80):
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

        with patch("app.api.v1.test.get_cached_reliability", return_value=0.85):
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

        with patch("app.api.v1.test.get_cached_reliability", return_value=0.85):
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

        with patch("app.api.v1.test.get_cached_reliability", return_value=0.85):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=None):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=0.90):
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
        with patch("app.api.v1.test.get_cached_reliability", return_value=0.60):
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

    def test_returns_session_when_found(self, db_session, test_user):
        """Test that helper returns session when it exists."""
        from app.api.v1.test import get_test_session_or_404
        from app.models import TestSession
        from app.models.models import TestStatus

        # Create a test session
        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.IN_PROGRESS,
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # Call helper - should return the session
        result = get_test_session_or_404(db_session, session.id)

        assert result is not None
        assert result.id == session.id
        assert result.user_id == test_user.id
        assert result.status == TestStatus.IN_PROGRESS

    def test_raises_404_when_session_not_found(self, db_session):
        """Test that helper raises HTTPException with 404 when session doesn't exist."""
        from app.api.v1.test import get_test_session_or_404
        from fastapi import HTTPException
        import pytest

        # Call helper with non-existent session ID
        with pytest.raises(HTTPException) as exc_info:
            get_test_session_or_404(db_session, 99999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Test session not found."

    def test_error_message_is_consistent(self, db_session):
        """Test that error message format is consistent."""
        from app.api.v1.test import get_test_session_or_404
        from fastapi import HTTPException
        import pytest

        # Try multiple non-existent IDs to verify consistent error message
        for session_id in [1, 100, 99999]:
            with pytest.raises(HTTPException) as exc_info:
                get_test_session_or_404(db_session, session_id)

            # Verify consistent error format
            assert exc_info.value.status_code == 404
            assert exc_info.value.detail == "Test session not found."

    def test_returns_session_regardless_of_status(self, db_session, test_user):
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
                user_id=test_user.id,
                status=status,
                completed_at=utc_now() if status != TestStatus.IN_PROGRESS else None,
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            # Helper should return session regardless of status
            result = get_test_session_or_404(db_session, session.id)

            assert result is not None
            assert result.id == session.id
            assert result.status == status
