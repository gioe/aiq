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


class TestGetTestSession:
    """Tests for GET /v1/test/session/{session_id} endpoint."""

    def test_get_test_session_success(self, client, auth_headers, test_questions):
        """Test successfully getting a test session."""
        # Start a test first
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]

        # Get the session
        response = client.get(f"/v1/test/session/{session_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "session" in data
        assert "questions_count" in data
        assert data["session"]["id"] == session_id
        assert data["session"]["status"] == "in_progress"
        assert data["questions_count"] == 0  # No responses yet

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
