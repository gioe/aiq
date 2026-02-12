"""
Tests for GET /v1/test/progress adaptive test progress endpoint (TASK-880).
"""
import pytest

from app.core.cat.engine import CATSessionManager

CAT_MAX_ITEMS = CATSessionManager.MAX_ITEMS


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


def _submit_response(client, auth_headers, session_id, question_id, answer="A"):
    """Helper to submit a single adaptive response and return response data."""
    response = client.post(
        "/v1/test/next",
        json={
            "session_id": session_id,
            "question_id": question_id,
            "user_answer": answer,
            "time_spent_seconds": 10,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    return response.json()


class TestGetProgressEndpoint:
    """Tests for GET /v1/test/progress endpoint."""

    def test_returns_correct_fields_after_one_item(
        self, client, auth_headers, db_session
    ):
        """Test progress endpoint returns all expected fields after one response."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        # Submit one response
        _submit_response(client, auth_headers, session_id, first_question["id"])

        response = client.get(
            f"/v1/test/progress?session_id={session_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify all expected fields
        assert data["session_id"] == session_id
        assert data["items_administered"] == 1
        assert data["total_items_max"] == CAT_MAX_ITEMS
        assert data["estimated_items_remaining"] == CAT_MAX_ITEMS - 1
        assert isinstance(data["domain_coverage"], dict)
        assert data["total_domains_covered"] >= 1
        assert data["elapsed_seconds"] >= 0
        # SE should be positive and decreased from prior (1.0)
        assert isinstance(data["current_se"], float)
        assert data["current_se"] > 0.0
        assert data["current_se"] < 1.0

    def test_progress_with_zero_items(self, client, auth_headers, db_session):
        """Test progress before any responses are submitted."""
        _create_calibrated_item_pool(db_session)
        session_id, _ = _start_adaptive_session(client, auth_headers)

        response = client.get(
            f"/v1/test/progress?session_id={session_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == session_id
        assert data["items_administered"] == 0
        assert data["total_items_max"] == CAT_MAX_ITEMS
        assert data["estimated_items_remaining"] == CAT_MAX_ITEMS
        assert data["total_domains_covered"] == 0
        assert data["elapsed_seconds"] >= 0

    def test_items_administered_increments(self, client, auth_headers, db_session):
        """Test that items_administered increments with each submitted response."""
        _create_calibrated_item_pool(db_session, count_per_domain=5)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        for expected_count in range(1, 4):
            next_data = _submit_response(
                client, auth_headers, session_id, current_question["id"]
            )

            progress = client.get(
                f"/v1/test/progress?session_id={session_id}",
                headers=auth_headers,
            )
            assert progress.status_code == 200
            pdata = progress.json()
            assert pdata["items_administered"] == expected_count
            assert pdata["estimated_items_remaining"] == CAT_MAX_ITEMS - expected_count

            if next_data["test_complete"]:
                break
            current_question = next_data["next_question"]

    def test_domain_coverage_tracks_correctly(self, client, auth_headers, db_session):
        """Test that domain_coverage accumulates items per domain."""
        _create_calibrated_item_pool(db_session, count_per_domain=5)
        session_id, current_question = _start_adaptive_session(client, auth_headers)

        # Submit 3 responses
        for _ in range(3):
            next_data = _submit_response(
                client, auth_headers, session_id, current_question["id"]
            )
            if next_data["test_complete"]:
                break
            current_question = next_data["next_question"]

        response = client.get(
            f"/v1/test/progress?session_id={session_id}",
            headers=auth_headers,
        )
        data = response.json()

        # Total across all domains should equal items_administered
        assert sum(data["domain_coverage"].values()) == data["items_administered"]
        # At least 1 domain covered
        assert data["total_domains_covered"] >= 1
        # total_domains_covered matches domain_coverage
        covered = sum(1 for v in data["domain_coverage"].values() if v > 0)
        assert data["total_domains_covered"] == covered

    def test_does_not_expose_raw_theta(self, client, auth_headers, db_session):
        """Test that raw theta (ability estimate) is NOT in the response."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)

        _submit_response(client, auth_headers, session_id, first_question["id"])

        response = client.get(
            f"/v1/test/progress?session_id={session_id}",
            headers=auth_headers,
        )

        data = response.json()

        # Verify the complete set of response keys matches the schema
        expected_keys = {
            "session_id",
            "items_administered",
            "total_items_max",
            "estimated_items_remaining",
            "domain_coverage",
            "total_domains_covered",
            "elapsed_seconds",
            "current_se",
        }
        assert (
            set(data.keys()) == expected_keys
        ), f"Unexpected keys in progress response: {set(data.keys()) - expected_keys}"

        # Explicit theta checks
        assert "theta" not in data
        assert "theta_estimate" not in data
        assert "current_theta" not in data

    def test_elapsed_seconds_is_non_negative(self, client, auth_headers, db_session):
        """Test that elapsed_seconds is a non-negative integer."""
        _create_calibrated_item_pool(db_session)
        session_id, _ = _start_adaptive_session(client, auth_headers)

        response = client.get(
            f"/v1/test/progress?session_id={session_id}",
            headers=auth_headers,
        )

        data = response.json()
        assert isinstance(data["elapsed_seconds"], int)
        assert data["elapsed_seconds"] >= 0

    def test_progress_is_idempotent(self, client, auth_headers, db_session):
        """Test that consecutive calls without state changes return identical results."""
        _create_calibrated_item_pool(db_session)
        session_id, first_question = _start_adaptive_session(client, auth_headers)
        _submit_response(client, auth_headers, session_id, first_question["id"])

        resp1 = client.get(
            f"/v1/test/progress?session_id={session_id}", headers=auth_headers
        )
        resp2 = client.get(
            f"/v1/test/progress?session_id={session_id}", headers=auth_headers
        )

        data1 = resp1.json()
        data2 = resp2.json()

        assert data1["items_administered"] == data2["items_administered"]
        assert data1["domain_coverage"] == data2["domain_coverage"]
        assert data1["total_domains_covered"] == data2["total_domains_covered"]
        assert data1["current_se"] == pytest.approx(data2["current_se"])
        # elapsed_seconds may differ slightly, so skip that


class TestGetProgressValidation:
    """Tests for validation and error handling in GET /v1/test/progress."""

    def test_session_not_found(self, client, auth_headers):
        """Test 404 when session doesn't exist."""
        response = client.get(
            "/v1/test/progress?session_id=99999",
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_session_not_owned_by_user(self, client, auth_headers, db_session):
        """Test 403 when session belongs to another user."""
        from app.models import User, TestSession
        from app.models.models import TestStatus
        from app.core.datetime_utils import utc_now

        # Create another user's adaptive session
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

        response = client.get(
            f"/v1/test/progress?session_id={other_session.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403

    def test_session_not_in_progress(self, client, auth_headers, db_session, test_user):
        """Test 400 when session is completed."""
        from app.models import TestSession
        from app.models.models import TestStatus
        from app.core.datetime_utils import utc_now

        completed_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=utc_now(),
            completed_at=utc_now(),
            is_adaptive=True,
            theta_history=[0.5],
        )
        db_session.add(completed_session)
        db_session.commit()

        response = client.get(
            f"/v1/test/progress?session_id={completed_session.id}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "already completed" in response.json()["detail"].lower()

    def test_session_abandoned(self, client, auth_headers, db_session, test_user):
        """Test 400 when session is abandoned."""
        from app.models import TestSession
        from app.models.models import TestStatus
        from app.core.datetime_utils import utc_now

        abandoned_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.ABANDONED,
            started_at=utc_now(),
            is_adaptive=True,
            theta_history=[],
        )
        db_session.add(abandoned_session)
        db_session.commit()

        response = client.get(
            f"/v1/test/progress?session_id={abandoned_session.id}",
            headers=auth_headers,
        )

        assert response.status_code == 400

    def test_session_not_adaptive(
        self, client, auth_headers, db_session, test_questions
    ):
        """Test 400 when session is fixed-form (not adaptive)."""
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]

        response = client.get(
            f"/v1/test/progress?session_id={session_id}",
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "adaptive" in response.json()["detail"].lower()

    def test_unauthenticated_request(self, client, db_session):
        """Test error when no auth headers provided."""
        response = client.get("/v1/test/progress?session_id=1")
        assert response.status_code in (401, 403)

    def test_missing_session_id_parameter(self, client, auth_headers):
        """Test 422 when session_id query param is missing."""
        response = client.get(
            "/v1/test/progress",
            headers=auth_headers,
        )

        assert response.status_code == 422
