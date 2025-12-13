"""
Tests for test session management endpoints.
"""


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
                assert (
                    domain_data["pct"] == 100.0
                ), "All answered questions should be correct"
