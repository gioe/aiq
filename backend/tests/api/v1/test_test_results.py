"""
Tests for test results retrieval endpoints.
"""
import pytest


class TestGetTestResult:
    """Tests for GET /v1/test/results/{result_id} endpoint."""

    def test_get_test_result_success(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test successfully retrieving a specific test result."""
        from app.models import Question

        # Create a completed test by starting and submitting
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get the actual correct answers from the database
        question_ids = [q["id"] for q in questions]
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )
        questions_dict = {q.id: q for q in db_questions}

        # Submit responses (all correct)
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": questions_dict[questions[0]["id"]].correct_answer,
                },
                {
                    "question_id": questions[1]["id"],
                    "user_answer": questions_dict[questions[1]["id"]].correct_answer,
                },
                {
                    "question_id": questions[2]["id"],
                    "user_answer": questions_dict[questions[2]["id"]].correct_answer,
                },
            ],
        }
        submit_response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )
        assert submit_response.status_code == 200
        result_id = submit_response.json()["result"]["id"]

        # Retrieve the test result
        response = client.get(f"/v1/test/results/{result_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["id"] == result_id
        assert data["test_session_id"] == session_id
        assert data["iq_score"] == 115  # 100% correct
        assert data["total_questions"] == 3
        assert data["correct_answers"] == 3
        assert data["accuracy_percentage"] == pytest.approx(100.0)
        assert data["completion_time_seconds"] is not None
        assert data["completed_at"] is not None

    def test_get_test_result_not_found(self, client, auth_headers):
        """Test retrieving a non-existent test result."""
        response = client.get("/v1/test/results/99999", headers=auth_headers)

        assert response.status_code == 404
        assert response.json()["detail"] == "Test result not found."

    def test_get_test_result_unauthorized(
        self, client, auth_headers, test_questions, db_session, test_user
    ):
        """Test that users cannot access other users' test results."""
        from app.models.models import TestResult, User, TestSession, TestStatus
        from app.core.auth.security import hash_password
        from datetime import datetime

        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash=hash_password("password123"),
            first_name="Other",
            last_name="User",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        # Create a test session and result for the other user
        test_session = TestSession(
            user_id=other_user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        test_result = TestResult(
            test_session_id=test_session.id,
            user_id=other_user.id,
            iq_score=100,
            total_questions=3,
            correct_answers=2,
            completion_time_seconds=300,
            completed_at=datetime.utcnow(),
        )
        db_session.add(test_result)
        db_session.commit()
        db_session.refresh(test_result)

        # Try to access the other user's result with test_user's auth
        response = client.get(
            f"/v1/test/results/{test_result.id}", headers=auth_headers
        )

        assert response.status_code == 403
        assert response.json()["detail"] == "Not authorized to access this test result."

    def test_get_test_result_unauthenticated(self, client, test_questions, db_session):
        """Test that unauthenticated requests are rejected."""
        response = client.get("/v1/test/results/1")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_get_test_result_with_partial_score(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test retrieving a test result with partial correct answers."""
        from app.models import Question

        # Start test
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get the actual correct answers from the database
        question_ids = [q["id"] for q in questions]
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )
        questions_dict = {q.id: q for q in db_questions}

        # Submit with 2/3 correct (66.67%)
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": questions_dict[questions[0]["id"]].correct_answer,
                },  # Correct
                {
                    "question_id": questions[1]["id"],
                    "user_answer": "WRONG_ANSWER",
                },  # Wrong
                {
                    "question_id": questions[2]["id"],
                    "user_answer": questions_dict[questions[2]["id"]].correct_answer,
                },  # Correct
            ],
        }
        submit_response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )
        assert submit_response.status_code == 200
        result_id = submit_response.json()["result"]["id"]

        # Retrieve the result
        response = client.get(f"/v1/test/results/{result_id}", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert data["correct_answers"] == 2
        assert data["total_questions"] == 3
        assert abs(data["accuracy_percentage"] - 66.67) < 0.1  # Allow for rounding


class TestGetTestHistory:
    """Tests for GET /v1/test/history endpoint."""

    def test_get_test_history_success(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test successfully retrieving test history."""
        from app.models.models import TestSession
        from datetime import datetime, timedelta

        # Create three completed tests with 1 question each
        # (we have 4 active questions in the fixture, so 3 tests will work)
        test_results = []

        for i in range(3):
            # Start test with only 1 question
            start_response = client.post(
                "/v1/test/start?question_count=1", headers=auth_headers
            )
            assert start_response.status_code == 200
            session_id = start_response.json()["session"]["id"]
            questions = start_response.json()["questions"]

            # Submit the answer (use correct answer from first question)
            submission_data = {
                "session_id": session_id,
                "responses": [
                    {"question_id": questions[0]["id"], "user_answer": "10"},
                ],
            }
            submit_response = client.post(
                "/v1/test/submit", json=submission_data, headers=auth_headers
            )
            assert submit_response.status_code == 200
            test_results.append(submit_response.json()["result"])

            # Backdate each completed session to bypass 6-month cadence for next test
            # Each test is completed progressively further in the past
            session = (
                db_session.query(TestSession)
                .filter(TestSession.id == session_id)
                .first()
            )
            session.completed_at = datetime.utcnow() - timedelta(days=181 * (3 - i))
            db_session.commit()

        # Get history
        response = client.get("/v1/test/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify paginated response structure
        assert "results" in data
        assert "total_count" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data

        results = data["results"]

        # Verify we got all three results
        assert len(results) == 3
        assert data["total_count"] == 3
        assert data["offset"] == 0
        assert data["has_more"] is False

        # Verify they're ordered by completion date (newest first)
        # Since we created them in sequence, the last one should be first
        assert results[0]["id"] == test_results[2]["id"]
        assert results[1]["id"] == test_results[1]["id"]
        assert results[2]["id"] == test_results[0]["id"]

        # Verify each result has all required fields
        for result in results:
            assert "id" in result
            assert "test_session_id" in result
            assert "user_id" in result
            assert "iq_score" in result
            assert "total_questions" in result
            assert "correct_answers" in result
            assert "accuracy_percentage" in result
            assert "completion_time_seconds" in result
            assert "completed_at" in result

    def test_get_test_history_empty(self, client, auth_headers, test_questions):
        """Test retrieving test history when user has no completed tests."""
        response = client.get("/v1/test/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return empty results list with zero total_count
        assert data["results"] == []
        assert data["total_count"] == 0
        assert data["has_more"] is False

    def test_get_test_history_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.get("/v1/test/history")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_get_test_history_only_users_results(
        self, client, auth_headers, test_questions, db_session, test_user
    ):
        """Test that users only see their own test results."""
        from app.models.models import TestResult, User, TestSession, TestStatus
        from app.core.auth.security import hash_password
        from datetime import datetime

        # Create another user
        other_user = User(
            email="other@example.com",
            password_hash=hash_password("password123"),
            first_name="Other",
            last_name="User",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        # Create test results for the other user
        other_session = TestSession(
            user_id=other_user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        db_session.add(other_session)
        db_session.commit()
        db_session.refresh(other_session)

        other_result = TestResult(
            test_session_id=other_session.id,
            user_id=other_user.id,
            iq_score=100,
            total_questions=3,
            correct_answers=2,
            completion_time_seconds=300,
            completed_at=datetime.utcnow(),
        )
        db_session.add(other_result)
        db_session.commit()

        # Create one test result for test_user
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        submission_data = {
            "session_id": session_id,
            "responses": [
                {"question_id": questions[0]["id"], "user_answer": "10"},
                {"question_id": questions[1]["id"], "user_answer": "No"},
                {"question_id": questions[2]["id"], "user_answer": "180"},
            ],
        }
        submit_response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )
        assert submit_response.status_code == 200
        test_user_result_id = submit_response.json()["result"]["id"]

        # Get history for test_user
        response = client.get("/v1/test/history", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should only see test_user's result, not other_user's
        assert len(data["results"]) == 1
        assert data["total_count"] == 1
        assert data["results"][0]["id"] == test_user_result_id
        assert data["results"][0]["user_id"] == test_user.id


class TestGetTestHistoryPagination:
    """Tests for GET /v1/test/history pagination (BCQ-004)."""

    def test_pagination_with_limit_and_offset(
        self, client, auth_headers, test_questions, db_session, test_user
    ):
        """Test pagination returns correct results with limit and offset."""
        from app.models.models import TestSession, TestResult, TestStatus
        from datetime import datetime, timedelta

        # Create 5 test results directly in DB (bypasses question availability)
        test_result_ids = []
        for i in range(5):
            # Create a completed session with different completion dates
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.utcnow() - timedelta(days=181 * (5 - i)),
                completed_at=datetime.utcnow() - timedelta(days=181 * (5 - i)),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            # Create a result for this session
            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=100 + i,  # Different scores for ordering verification
                total_questions=10,
                correct_answers=5,
                completion_time_seconds=300,
                completed_at=session.completed_at,
            )
            db_session.add(result)
            db_session.commit()
            db_session.refresh(result)
            test_result_ids.append(result.id)

        # Test: Get first page (limit=2, offset=0)
        response = client.get("/v1/test/history?limit=2&offset=0", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) == 2
        assert data["total_count"] == 5
        assert data["limit"] == 2
        assert data["offset"] == 0
        assert data["has_more"] is True

        # Test: Get second page (limit=2, offset=2)
        response = client.get("/v1/test/history?limit=2&offset=2", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) == 2
        assert data["total_count"] == 5
        assert data["offset"] == 2
        assert data["has_more"] is True

        # Test: Get third page (limit=2, offset=4) - partial page
        response = client.get("/v1/test/history?limit=2&offset=4", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert len(data["results"]) == 1  # Only 1 result left
        assert data["total_count"] == 5
        assert data["offset"] == 4
        assert data["has_more"] is False

    def test_default_limit_value(self, client, auth_headers, test_questions):
        """Test that default limit is 50."""
        response = client.get("/v1/test/history", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["limit"] == 50

    def test_limit_validation_max_100(self, client, auth_headers, test_questions):
        """Test that limit cannot exceed 100."""
        response = client.get("/v1/test/history?limit=150", headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_limit_validation_min_1(self, client, auth_headers, test_questions):
        """Test that limit must be at least 1."""
        response = client.get("/v1/test/history?limit=0", headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_offset_validation_non_negative(self, client, auth_headers, test_questions):
        """Test that offset must be non-negative."""
        response = client.get("/v1/test/history?offset=-1", headers=auth_headers)
        assert response.status_code == 422  # Validation error

    def test_offset_beyond_results(
        self, client, auth_headers, test_questions, db_session, test_user
    ):
        """Test offset beyond available results returns empty list with correct total_count."""
        from app.models.models import TestSession, TestResult, TestStatus
        from datetime import datetime

        # Create 3 test results so we have a non-zero total_count
        for i in range(3):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.utcnow(),
                completed_at=datetime.utcnow(),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=100 + i,
                total_questions=10,
                correct_answers=5,
                completion_time_seconds=300,
                completed_at=session.completed_at,
            )
            db_session.add(result)
        db_session.commit()

        # Query with offset beyond available results
        response = client.get("/v1/test/history?offset=1000", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()

        # Should return empty results but total_count reflects actual count
        assert data["results"] == []
        assert data["total_count"] == 3  # User has 3 results, but none on this page
        assert data["has_more"] is False
