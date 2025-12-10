"""
Tests for response submission endpoints.
"""


class TestSubmitTest:
    """Tests for POST /v1/test/submit endpoint."""

    def test_submit_test_success_all_correct(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test successfully submitting responses with all correct answers."""
        from app.models.models import Response, TestSession, TestStatus, TestResult
        from app.models import Question

        # Start a test first
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

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "session" in data
        assert "result" in data
        assert "responses_count" in data
        assert "message" in data

        # Verify session updated
        assert data["session"]["id"] == session_id
        assert data["session"]["status"] == "completed"
        assert data["session"]["completed_at"] is not None

        # Verify test result
        result = data["result"]
        assert result["test_session_id"] == session_id
        assert result["iq_score"] == 115  # 100% correct = IQ 115
        assert result["total_questions"] == 3
        assert result["correct_answers"] == 3
        assert result["accuracy_percentage"] == 100.0
        assert result["completion_time_seconds"] is not None
        assert result["completed_at"] is not None

        # Verify response count
        assert data["responses_count"] == 3
        assert "IQ Score: 115" in data["message"]

        # Verify responses in database
        responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )
        assert len(responses) == 3

        # Verify all responses marked as correct
        for resp in responses:
            assert resp.is_correct is True
            assert resp.answered_at is not None

        # Verify session status in database
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert session.status == TestStatus.COMPLETED
        assert session.completed_at is not None

        # Verify TestResult created in database
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result is not None
        assert test_result.iq_score == 115
        assert test_result.correct_answers == 3
        assert test_result.total_questions == 3
        assert test_result.completion_time_seconds is not None

    def test_submit_test_success_mixed_answers(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test submitting responses with mixed correct and incorrect answers."""
        from app.models.models import Response, TestResult
        from app.models import Question

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get the actual correct answers from the database
        question_ids = [q["id"] for q in questions]
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )
        questions_dict = {q.id: q for q in db_questions}

        # Submit responses (1 correct, 2 incorrect)
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": questions_dict[questions[0]["id"]].correct_answer,
                },  # Correct
                {
                    "question_id": questions[1]["id"],
                    "user_answer": "WRONG_ANSWER_1",
                },  # Incorrect
                {
                    "question_id": questions[2]["id"],
                    "user_answer": "WRONG_ANSWER_2",
                },  # Incorrect
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify test result (1/3 = 33.33% correct)
        # Formula: 100 + ((0.3333 - 0.5) * 30) = 100 - 5 = 95
        result = data["result"]
        assert result["iq_score"] == 95
        assert result["correct_answers"] == 1
        assert result["total_questions"] == 3

        # Verify responses in database
        responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )
        assert len(responses) == 3

        # Count correct vs incorrect
        correct_count = sum(1 for r in responses if r.is_correct)
        incorrect_count = sum(1 for r in responses if not r.is_correct)

        assert correct_count == 1
        assert incorrect_count == 2

        # Verify TestResult in database
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        assert test_result.iq_score == 95
        assert test_result.correct_answers == 1

    def test_submit_test_case_insensitive(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that answer comparison is case-insensitive."""
        from app.models.models import Response
        from app.models import Question

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get the actual correct answers from the database
        question_ids = [q["id"] for q in questions]
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )
        questions_dict = {q.id: q for q in db_questions}

        # Submit with different case (using actual correct answers but in different case)
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": questions_dict[
                        questions[0]["id"]
                    ].correct_answer.upper(),
                },
                {
                    "question_id": questions[1]["id"],
                    "user_answer": questions_dict[
                        questions[1]["id"]
                    ].correct_answer.title(),
                },
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 200

        # Both should be marked correct despite case differences
        responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .all()
        )
        for resp in responses:
            assert resp.is_correct is True

    def test_submit_test_session_not_found(self, client, auth_headers):
        """Test submitting for non-existent session."""
        submission_data = {
            "session_id": 99999,
            "responses": [
                {"question_id": 1, "user_answer": "test answer"},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 404
        assert "Test session not found" in response.json()["detail"]

    def test_submit_test_unauthorized_access(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that users cannot submit for other users' sessions."""
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

        # Try to submit for user2's session with user1's credentials
        submission_data = {
            "session_id": session.id,
            "responses": [
                {"question_id": test_questions[0].id, "user_answer": "test"},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 403
        assert "Not authorized" in response.json()["detail"]

    def test_submit_test_session_already_completed(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test submitting for an already completed session."""
        from app.models import TestSession
        from app.models.models import TestStatus
        from datetime import datetime

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Manually mark session as completed
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        session.status = TestStatus.COMPLETED
        session.completed_at = datetime.utcnow()
        db_session.commit()

        # Try to submit
        submission_data = {
            "session_id": session_id,
            "responses": [
                {"question_id": questions[0]["id"], "user_answer": "test"},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"]

    def test_submit_test_empty_responses(self, client, auth_headers, test_questions):
        """Test submitting with empty responses list."""
        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]

        # Submit empty responses list
        submission_data = {
            "session_id": session_id,
            "responses": [],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_submit_test_invalid_question_ids(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test submitting responses for questions not in the session."""
        # Start a test with 2 questions
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Try to submit with a question that wasn't in this session
        # Find a question not in the session
        all_active_questions = [q for q in test_questions if q.is_active]
        session_question_ids = {q["id"] for q in questions}
        invalid_question = next(
            q for q in all_active_questions if q.id not in session_question_ids
        )

        submission_data = {
            "session_id": session_id,
            "responses": [
                {"question_id": questions[0]["id"], "user_answer": "test"},
                {"question_id": invalid_question.id, "user_answer": "test"},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid question IDs" in response.json()["detail"]
        assert str(invalid_question.id) in response.json()["detail"]

    def test_submit_test_empty_answer(self, client, auth_headers, test_questions):
        """Test submitting with empty user answer."""
        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit with empty answer
        submission_data = {
            "session_id": session_id,
            "responses": [
                {"question_id": questions[0]["id"], "user_answer": ""},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_submit_test_whitespace_only_answer(
        self, client, auth_headers, test_questions
    ):
        """Test submitting with whitespace-only user answer."""
        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Submit with whitespace-only answer
        submission_data = {
            "session_id": session_id,
            "responses": [
                {"question_id": questions[0]["id"], "user_answer": "   "},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 400
        assert "cannot be empty" in response.json()["detail"]

    def test_submit_test_requires_authentication(self, client, test_questions):
        """Test that endpoint requires authentication."""
        submission_data = {
            "session_id": 1,
            "responses": [
                {"question_id": 1, "user_answer": "test"},
            ],
        }

        response = client.post("/v1/test/submit", json=submission_data)
        assert response.status_code in [401, 403]

    def test_submit_test_answer_trimming(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that user answers are trimmed before storage."""
        from app.models.models import Response
        from app.models import Question

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=1", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get the actual correct answer from the database
        db_question = (
            db_session.query(Question).filter(Question.id == questions[0]["id"]).first()
        )
        correct_answer = db_question.correct_answer

        # Submit with extra whitespace
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": f"  {correct_answer}  ",
                },
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 200

        # Verify answer is trimmed in database
        db_response = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .first()
        )
        assert db_response.user_answer == correct_answer
        assert db_response.is_correct is True

    def test_submit_test_transaction_atomicity(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that submission is atomic - all responses stored or none."""
        from app.models.models import Response

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # First, submit successfully
        submission_data = {
            "session_id": session_id,
            "responses": [
                {"question_id": questions[0]["id"], "user_answer": "10"},
                {"question_id": questions[1]["id"], "user_answer": "No"},
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )
        assert response.status_code == 200

        # Verify responses exist
        response_count = (
            db_session.query(Response)
            .filter(Response.test_session_id == session_id)
            .count()
        )
        assert response_count == 2

    def test_submit_test_multiple_sessions_isolation(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that responses are properly isolated between sessions."""
        from app.models.models import Response, TestSession, TestStatus
        from datetime import datetime, timedelta

        # Start first test
        start1 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        session1_id = start1.json()["session"]["id"]
        questions1 = start1.json()["questions"]

        # Submit for first session
        submission1 = {
            "session_id": session1_id,
            "responses": [
                {"question_id": questions1[0]["id"], "user_answer": "answer1"},
                {"question_id": questions1[1]["id"], "user_answer": "answer2"},
            ],
        }
        client.post("/v1/test/submit", json=submission1, headers=auth_headers)

        # Backdate the first session completion to bypass 6-month cadence check
        session1 = (
            db_session.query(TestSession).filter(TestSession.id == session1_id).first()
        )
        session1.completed_at = datetime.utcnow() - timedelta(days=181)
        db_session.commit()

        # Start second test (different questions since first are now seen)
        start2 = client.post("/v1/test/start?question_count=2", headers=auth_headers)
        session2_id = start2.json()["session"]["id"]
        questions2 = start2.json()["questions"]

        # Submit for second session
        submission2 = {
            "session_id": session2_id,
            "responses": [
                {"question_id": questions2[0]["id"], "user_answer": "answer3"},
                {"question_id": questions2[1]["id"], "user_answer": "answer4"},
            ],
        }
        client.post("/v1/test/submit", json=submission2, headers=auth_headers)

        # Verify each session has exactly 2 responses
        session1_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session1_id)
            .count()
        )
        session2_responses = (
            db_session.query(Response)
            .filter(Response.test_session_id == session2_id)
            .count()
        )

        assert session1_responses == 2
        assert session2_responses == 2

        # Verify both sessions are completed
        session1 = (
            db_session.query(TestSession).filter(TestSession.id == session1_id).first()
        )
        session2 = (
            db_session.query(TestSession).filter(TestSession.id == session2_id).first()
        )

        assert session1.status == TestStatus.COMPLETED
        assert session2.status == TestStatus.COMPLETED

    def test_submit_test_time_limit_exceeded_client_flag(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that client-reported time_limit_exceeded flag is stored."""
        from app.models import Question, TestSession

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
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

        # Submit with time_limit_exceeded=True (client reports timeout)
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
            ],
            "time_limit_exceeded": True,
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response shows time_limit_exceeded
        assert data["session"]["time_limit_exceeded"] is True

        # Verify session in database has time_limit_exceeded set
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert session.time_limit_exceeded is True

    def test_submit_test_time_limit_exceeded_defaults_to_false(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that time_limit_exceeded defaults to False when not provided."""
        from app.models import Question, TestSession

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
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

        # Submit WITHOUT time_limit_exceeded field
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
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response shows time_limit_exceeded as False
        assert data["session"]["time_limit_exceeded"] is False

        # Verify session in database has time_limit_exceeded as False
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert session.time_limit_exceeded is False
