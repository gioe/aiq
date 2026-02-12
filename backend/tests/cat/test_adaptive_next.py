"""
Tests for POST /v1/test/next adaptive (CAT) endpoint (TASK-879).
"""


def _create_calibrated_item_pool(db_session, count_per_domain=3):
    """Create a pool of IRT-calibrated questions across all 6 domains.

    Returns list of created Question objects.
    """
    from app.models import Question
    from app.models.models import QuestionType, DifficultyLevel

    domains = [
        (QuestionType.PATTERN, DifficultyLevel.EASY, -1.0, 1.2),
        (QuestionType.LOGIC, DifficultyLevel.MEDIUM, 0.0, 1.5),
        (QuestionType.SPATIAL, DifficultyLevel.MEDIUM, 0.2, 1.3),
        (QuestionType.MATH, DifficultyLevel.HARD, 1.0, 1.8),
        (QuestionType.VERBAL, DifficultyLevel.EASY, -0.5, 1.1),
        (QuestionType.MEMORY, DifficultyLevel.MEDIUM, 0.3, 1.4),
    ]

    questions = []
    for idx, (qtype, difficulty, irt_b, irt_a) in enumerate(domains):
        for j in range(count_per_domain):
            q = Question(
                question_text=f"{qtype.value} question {j+1}",
                question_type=qtype,
                difficulty_level=difficulty,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                irt_difficulty=irt_b + (j * 0.3),
                irt_discrimination=irt_a,
                is_active=True,
            )
            db_session.add(q)
            questions.append(q)

    db_session.commit()
    for q in questions:
        db_session.refresh(q)

    return questions


def _start_adaptive_session(client, auth_headers):
    """Helper to start an adaptive session and return (session_id, first_question)."""
    response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    session_id = data["session"]["id"]
    first_question = data["questions"][0]
    return session_id, first_question


class TestAdaptiveNextEndpoint:
    """Tests for POST /v1/test/next endpoint."""

    def test_submit_response_and_get_next_question(
        self, client, auth_headers, db_session
    ):
        """Test submitting a correct answer returns the next question."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "A",  # Correct answer
                "time_spent_seconds": 30,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Test should continue
        assert data["test_complete"] is False
        assert data["next_question"] is not None
        assert data["items_administered"] == 1
        assert isinstance(data["current_theta"], float)
        assert isinstance(data["current_se"], float)
        assert data["result"] is None
        assert data["stopping_reason"] is None

        # Next question should be different from first
        assert data["next_question"]["id"] != first_question["id"]

    def test_submit_incorrect_answer(self, client, auth_headers, db_session):
        """Test submitting an incorrect answer still returns next question."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "B",  # Wrong answer (correct is A)
                "time_spent_seconds": 15,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["test_complete"] is False
        assert data["next_question"] is not None
        assert data["items_administered"] == 1

    def test_theta_history_updated(self, client, auth_headers, db_session, test_user):
        """Test that theta_history is updated in the database after each response."""
        from app.models import TestSession

        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        # Submit first response
        client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "A",
                "time_spent_seconds": 20,
            },
            headers=auth_headers,
        )

        # Check theta_history in database
        db_session.expire_all()
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )

        assert session.theta_history is not None
        assert len(session.theta_history) == 1
        assert isinstance(session.theta_history[0], float)

    def test_response_stored_in_database(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that Response record is stored correctly."""
        from app.models.models import Response

        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "A",
                "time_spent_seconds": 45,
            },
            headers=auth_headers,
        )

        db_session.expire_all()
        stored = (
            db_session.query(Response)
            .filter(
                Response.test_session_id == session_id,
                Response.question_id == first_question["id"],
            )
            .first()
        )

        assert stored is not None
        assert stored.user_answer == "A"
        assert stored.is_correct is True
        assert stored.time_spent_seconds == 45
        assert stored.user_id == test_user.id

    def test_multiple_responses_advance_test(self, client, auth_headers, db_session):
        """Test submitting multiple responses advances items_administered."""
        _create_calibrated_item_pool(db_session)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        for i in range(3):
            response = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": "A",
                    "time_spent_seconds": 20,
                },
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["items_administered"] == i + 1

            if data["test_complete"]:
                break

            current_question = data["next_question"]


class TestAdaptiveNextValidation:
    """Tests for validation logic in POST /v1/test/next."""

    def test_session_not_found(self, client, auth_headers, db_session):
        """Test 404 when session doesn't exist."""
        _create_calibrated_item_pool(db_session)

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": 99999,
                "question_id": 1,
                "user_answer": "A",
            },
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Test session not found" in response.json()["detail"]

    def test_session_not_owned_by_user(self, client, auth_headers, db_session):
        """Test 403 when session belongs to different user."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from app.core.datetime_utils import utc_now

        _create_calibrated_item_pool(db_session)

        # Create another user's session
        other_user = User(
            email="other@example.com",
            password_hash="hash",  # pragma: allowlist secret
            first_name="Other",
            last_name="User",
        )
        db_session.add(other_user)
        db_session.commit()

        other_session = TestSession(
            user_id=other_user.id,
            status=TestStatus.IN_PROGRESS,
            started_at=utc_now(),
            is_adaptive=True,
            theta_history=[],
        )
        db_session.add(other_session)
        db_session.commit()

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": other_session.id,
                "question_id": 1,
                "user_answer": "A",
            },
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_session_not_adaptive(
        self, client, auth_headers, db_session, test_user, test_questions
    ):
        """Test 400 when session is not adaptive (fixed-form)."""
        # Start a fixed-form session
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        question_id = start_response.json()["questions"][0]["id"]

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": question_id,
                "user_answer": "A",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "adaptive" in response.json()["detail"].lower()

    def test_session_already_completed(
        self, client, auth_headers, db_session, test_user
    ):
        """Test 400 when session is already completed."""
        from app.models import TestSession
        from app.models.models import TestStatus
        from app.core.datetime_utils import utc_now

        _create_calibrated_item_pool(db_session)

        session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=utc_now(),
            completed_at=utc_now(),
            is_adaptive=True,
            theta_history=[0.5],
        )
        db_session.add(session)
        db_session.commit()

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session.id,
                "question_id": 1,
                "user_answer": "A",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"].lower()

    def test_question_not_served(self, client, auth_headers, db_session):
        """Test 400 when question was not served in this session."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        # Try to answer a question that wasn't served
        # Use a question ID that exists but wasn't selected
        from app.models import Question

        all_questions = db_session.query(Question).all()
        unserved_id = None
        for q in all_questions:
            if q.id != first_question["id"]:
                unserved_id = q.id
                break

        assert unserved_id is not None

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": unserved_id,
                "user_answer": "A",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "not served" in response.json()["detail"].lower()

    def test_duplicate_response_rejected(self, client, auth_headers, db_session):
        """Test 409 when answering the same question twice."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        # Submit first response (succeeds)
        response1 = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "A",
            },
            headers=auth_headers,
        )
        assert response1.status_code == 200

        # Submit duplicate response (should fail)
        response2 = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "B",
            },
            headers=auth_headers,
        )

        assert response2.status_code == 409
        assert "already been submitted" in response2.json()["detail"].lower()

    def test_empty_answer_rejected(self, client, auth_headers, db_session):
        """Test 400 when user_answer is empty."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_unauthenticated_request(self, client, db_session):
        """Test error when no auth headers provided."""
        response = client.post(
            "/v1/test/next",
            json={
                "session_id": 1,
                "question_id": 1,
                "user_answer": "A",
            },
        )

        assert response.status_code in (401, 403)


class TestAdaptiveNextCompletion:
    """Tests for test completion flow in POST /v1/test/next."""

    def test_test_completes_at_max_items(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that the test completes when max items (15) is reached."""
        # Create a large item pool (need > 15 items)
        _create_calibrated_item_pool(db_session, count_per_domain=5)

        session_id, current_question = _start_adaptive_session(client, auth_headers)

        completed = False
        items_answered = 0

        for _ in range(20):  # Safety limit
            response = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": "A",
                    "time_spent_seconds": 10,
                },
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()
            items_answered += 1

            if data["test_complete"]:
                completed = True
                # Verify completion response structure
                assert data["result"] is not None
                assert data["stopping_reason"] is not None
                assert data["next_question"] is None
                assert data["items_administered"] <= 15

                # Verify result has expected fields
                result = data["result"]
                assert "iq_score" in result
                assert "percentile_rank" in result
                assert "domain_scores" in result
                assert "total_questions" in result
                assert "correct_answers" in result
                break

            current_question = data["next_question"]

        assert completed, "Test should have completed within 15 items"
        assert items_answered <= 15

    def test_completion_creates_test_result(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that completing an adaptive test creates a TestResult record."""
        from app.models.models import TestResult, TestSession

        _create_calibrated_item_pool(db_session, count_per_domain=5)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        # Drive the test to completion
        for _ in range(20):
            response = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": "A",
                    "time_spent_seconds": 10,
                },
                headers=auth_headers,
            )
            data = response.json()
            if data["test_complete"]:
                break
            current_question = data["next_question"]

        # Verify TestResult in database
        db_session.expire_all()
        test_result = (
            db_session.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        assert test_result is not None
        assert test_result.iq_score > 0
        assert test_result.scoring_method == "irt"
        assert test_result.theta_estimate is not None
        assert test_result.theta_se is not None

        # Verify session is completed
        session = (
            db_session.query(TestSession).filter(TestSession.id == session_id).first()
        )
        assert session.status.value == "completed"
        assert session.completed_at is not None
        assert session.final_theta is not None
        assert session.final_se is not None
        assert session.stopping_reason is not None

    def test_completion_result_has_confidence_interval(
        self, client, auth_headers, db_session
    ):
        """Test that the completion result includes confidence interval data."""
        _create_calibrated_item_pool(db_session, count_per_domain=5)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        # Drive to completion
        final_data = None
        for _ in range(20):
            response = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": "A",
                    "time_spent_seconds": 10,
                },
                headers=auth_headers,
            )
            data = response.json()
            if data["test_complete"]:
                final_data = data
                break
            current_question = data["next_question"]

        assert final_data is not None
        result = final_data["result"]

        # IRT-based tests should always have CI data
        assert result.get("confidence_interval") is not None
        ci = result["confidence_interval"]
        assert ci["lower"] <= result["iq_score"]
        assert ci["upper"] >= result["iq_score"]
        assert ci["standard_error"] > 0

    def test_item_pool_exhausted_forces_completion(
        self, client, auth_headers, db_session
    ):
        """Test that test completes gracefully when item pool is exhausted."""
        # Create a very small pool (6 items = 1 per domain, fewer than MIN_ITEMS=8)
        _create_calibrated_item_pool(db_session, count_per_domain=1)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        final_data = None
        for _ in range(10):  # Safety limit
            response = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": "A",
                    "time_spent_seconds": 10,
                },
                headers=auth_headers,
            )
            assert response.status_code == 200
            data = response.json()
            if data["test_complete"]:
                final_data = data
                break
            current_question = data["next_question"]

        assert final_data is not None
        assert final_data["stopping_reason"] == "item_pool_exhausted"
        assert final_data["result"] is not None
        assert final_data["result"]["iq_score"] > 0

    def test_cannot_submit_after_completion(self, client, auth_headers, db_session):
        """Test that submitting after test completion returns error."""
        _create_calibrated_item_pool(db_session, count_per_domain=5)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        # Drive to completion, capturing last question before completion
        last_question_before = None
        for _ in range(20):
            response = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": "A",
                    "time_spent_seconds": 10,
                },
                headers=auth_headers,
            )
            data = response.json()
            if data["test_complete"]:
                break
            last_question_before = current_question
            current_question = data["next_question"]

        # Try to submit another response after completion
        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": current_question["id"]
                if last_question_before is None
                else last_question_before["id"],
                "user_answer": "A",
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"].lower()


class TestAdaptiveNextTimeSpent:
    """Tests for time_spent_seconds handling."""

    def test_time_spent_optional(self, client, auth_headers, db_session):
        """Test that time_spent_seconds is optional."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        response = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "A",
                # No time_spent_seconds
            },
            headers=auth_headers,
        )

        assert response.status_code == 200

    def test_time_spent_stored(self, client, auth_headers, db_session, test_user):
        """Test that time_spent_seconds is stored in the Response record."""
        from app.models.models import Response

        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": first_question["id"],
                "user_answer": "A",
                "time_spent_seconds": 42,
            },
            headers=auth_headers,
        )

        db_session.expire_all()
        stored = (
            db_session.query(Response)
            .filter(
                Response.test_session_id == session_id,
            )
            .first()
        )

        assert stored is not None
        assert stored.time_spent_seconds == 42
