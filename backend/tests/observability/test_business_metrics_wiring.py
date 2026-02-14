"""
Tests that business metrics (from app.observability) are emitted at their
correct endpoint call sites.

Each test patches the metrics singleton and verifies the expected method
is called with correct arguments when the corresponding endpoint executes.
"""

from unittest.mock import patch

from app.models import Question
from app.models.models import QuestionType, DifficultyLevel


def _create_calibrated_item_pool(db_session, count_per_domain=3):
    """Create IRT-calibrated questions for adaptive test paths."""
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
                question_text=f"{qtype.value} calibrated {j+1}",
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


class TestStartTestMetrics:
    """Metrics emitted by POST /v1/test/start."""

    @patch("app.api.v1.test.metrics")
    def test_fixed_form_emits_test_started_and_questions_served(
        self, mock_metrics, client, auth_headers, test_questions
    ):
        """Fixed-form start_test records test_started and questions_served."""
        response = client.post("/v1/test/start?question_count=3", headers=auth_headers)
        assert response.status_code == 200

        mock_metrics.record_test_started.assert_called_once_with(
            adaptive=False, question_count=3
        )
        mock_metrics.record_questions_served.assert_called_once_with(
            count=3, adaptive=False
        )

    @patch("app.api.v1.test.metrics")
    def test_adaptive_emits_test_started_and_questions_served(
        self, mock_metrics, client, auth_headers, db_session
    ):
        """Adaptive start_test records test_started and questions_served."""
        _create_calibrated_item_pool(db_session)

        response = client.post("/v1/test/start?adaptive=true", headers=auth_headers)
        assert response.status_code == 200

        mock_metrics.record_test_started.assert_called_once_with(
            adaptive=True, question_count=1
        )
        mock_metrics.record_questions_served.assert_called_once_with(
            count=1, adaptive=True
        )


class TestSubmitTestMetrics:
    """Metrics emitted by POST /v1/test/submit."""

    @patch("app.api.v1.test.metrics")
    def test_submit_emits_test_completed(
        self, mock_metrics, client, auth_headers, test_questions
    ):
        """submit_test records test_completed with correct args."""
        start_resp = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        session_id = start_data["session"]["id"]
        questions = start_data["questions"]

        responses = [
            {
                "question_id": q["id"],
                "user_answer": q["answer_options"][0],
                "time_spent_seconds": 10,
            }
            for q in questions
        ]

        mock_metrics.reset_mock()

        submit_resp = client.post(
            "/v1/test/submit",
            json={"session_id": session_id, "responses": responses},
            headers=auth_headers,
        )
        assert submit_resp.status_code == 200

        mock_metrics.record_test_completed.assert_called_once()
        call_kwargs = mock_metrics.record_test_completed.call_args.kwargs
        assert call_kwargs["adaptive"] is False
        assert call_kwargs["question_count"] == 3
        assert isinstance(call_kwargs["duration_seconds"], float)


class TestAbandonTestMetrics:
    """Metrics emitted by POST /v1/test/{session_id}/abandon."""

    @patch("app.api.v1.test.metrics")
    def test_abandon_emits_test_abandoned(
        self, mock_metrics, client, auth_headers, test_questions
    ):
        """abandon_test records test_abandoned with correct args."""
        start_resp = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_resp.status_code == 200
        session_id = start_resp.json()["session"]["id"]

        mock_metrics.reset_mock()

        abandon_resp = client.post(
            f"/v1/test/{session_id}/abandon", headers=auth_headers
        )
        assert abandon_resp.status_code == 200

        mock_metrics.record_test_abandoned.assert_called_once()
        call_kwargs = mock_metrics.record_test_abandoned.call_args.kwargs
        assert call_kwargs["questions_answered"] == 0


class TestAdaptiveNextMetrics:
    """Metrics emitted by POST /v1/test/next."""

    @patch("app.api.v1.test.metrics")
    def test_next_question_emits_questions_served(
        self, mock_metrics, client, auth_headers, db_session
    ):
        """submit_adaptive_response records questions_served when returning next question."""
        _create_calibrated_item_pool(db_session)

        start_resp = client.post("/v1/test/start?adaptive=true", headers=auth_headers)
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        session_id = start_data["session"]["id"]
        question = start_data["questions"][0]

        mock_metrics.reset_mock()

        next_resp = client.post(
            "/v1/test/next",
            json={
                "session_id": session_id,
                "question_id": question["id"],
                "user_answer": question["answer_options"][0],
                "time_spent_seconds": 10,
            },
            headers=auth_headers,
        )
        assert next_resp.status_code == 200
        data = next_resp.json()

        if not data.get("test_complete"):
            mock_metrics.record_questions_served.assert_called_once_with(
                count=1, adaptive=True
            )

    @patch("app.api.v1.test.metrics")
    def test_adaptive_finalize_emits_test_completed(
        self, mock_metrics, client, auth_headers, db_session
    ):
        """_finalize_adaptive_session records test_completed when test finishes."""
        # Create a small pool that will exhaust quickly
        _create_calibrated_item_pool(db_session, count_per_domain=1)

        start_resp = client.post("/v1/test/start?adaptive=true", headers=auth_headers)
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        session_id = start_data["session"]["id"]
        question = start_data["questions"][0]

        mock_metrics.reset_mock()

        # Keep answering until test completes
        completed = False
        current_question = question
        for _ in range(20):  # Safety limit
            resp = client.post(
                "/v1/test/next",
                json={
                    "session_id": session_id,
                    "question_id": current_question["id"],
                    "user_answer": current_question["answer_options"][0],
                    "time_spent_seconds": 5,
                },
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            if data.get("test_complete"):
                completed = True
                break
            current_question = data["next_question"]

        assert completed, "Adaptive test should complete with small item pool"
        mock_metrics.record_test_completed.assert_called_once()
        call_kwargs = mock_metrics.record_test_completed.call_args.kwargs
        assert call_kwargs["adaptive"] is True


class TestLoginMetrics:
    """Metrics emitted by POST /v1/auth/login."""

    @patch("app.api.v1.auth.metrics")
    def test_successful_login_emits_record_login_true(
        self, mock_metrics, client, db_session
    ):
        """Successful login records record_login(success=True)."""
        from app.core.auth.security import hash_password

        from app.models import User

        user = User(
            email="login_metrics@example.com",
            password_hash=hash_password("SecurePass123!"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/v1/auth/login",
            json={
                "email": "login_metrics@example.com",
                "password": "SecurePass123!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 200

        mock_metrics.record_login.assert_called_once_with(success=True)

    @patch("app.api.v1.auth.metrics")
    def test_user_not_found_emits_record_login_false(self, mock_metrics, client):
        """Login with non-existent user records record_login(success=False)."""
        response = client.post(
            "/v1/auth/login",
            json={
                "email": "nonexistent@example.com",
                "password": "SomePass123!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 401

        mock_metrics.record_login.assert_called_once_with(success=False)

    @patch("app.api.v1.auth.metrics")
    def test_wrong_password_emits_record_login_false(
        self, mock_metrics, client, db_session
    ):
        """Login with wrong password records record_login(success=False)."""
        from app.core.auth.security import hash_password

        from app.models import User

        user = User(
            email="wrong_pw_metrics@example.com",
            password_hash=hash_password("CorrectPass123!"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()

        response = client.post(
            "/v1/auth/login",
            json={
                "email": "wrong_pw_metrics@example.com",
                "password": "WrongPass123!",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 401

        mock_metrics.record_login.assert_called_once_with(success=False)


class TestRegisterUserMetrics:
    """Metrics emitted by POST /v1/auth/register."""

    @patch("app.api.v1.auth.metrics")
    def test_register_emits_user_registration(self, mock_metrics, client):
        """register_user records user_registration."""
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "metrics_test@example.com",
                "password": "SecurePass123!",  # pragma: allowlist secret
                "first_name": "Test",
                "last_name": "User",
            },
        )
        assert response.status_code == 201

        mock_metrics.record_user_registration.assert_called_once()


class TestGenerationRunMetrics:
    """Metrics emitted by POST /v1/admin/generation-runs."""

    @patch("app.core.config.settings.SERVICE_API_KEY", "test-service-key")
    @patch("app.api.v1.admin.generation.app_metrics")
    def test_create_run_emits_questions_generated(self, mock_metrics, client):
        """create_generation_run records questions_generated from type_metrics."""
        response = client.post(
            "/v1/admin/generation-runs",
            json={
                "started_at": "2025-01-01T00:00:00Z",
                "completed_at": "2025-01-01T00:05:00Z",
                "duration_seconds": 300.0,
                "status": "success",
                "exit_code": 0,
                "questions_requested": 50,
                "questions_generated": 50,
                "generation_failures": 0,
                "generation_success_rate": 1.0,
                "questions_evaluated": 50,
                "questions_approved": 48,
                "questions_rejected": 2,
                "approval_rate": 0.96,
                "avg_judge_score": 8.5,
                "min_judge_score": 6.0,
                "max_judge_score": 10.0,
                "duplicates_found": 3,
                "exact_duplicates": 1,
                "semantic_duplicates": 2,
                "duplicate_rate": 0.06,
                "questions_inserted": 45,
                "insertion_failures": 0,
                "overall_success_rate": 0.9,
                "total_errors": 0,
                "total_api_calls": 100,
                "type_metrics": {
                    "pattern": 10,
                    "logic": 15,
                },
                "difficulty_metrics": {
                    "easy": 5,
                    "medium": 12,
                    "hard": 8,
                },
                "environment": "test",
                "triggered_by": "test",
            },
            headers={"X-Service-Key": "test-service-key"},
        )
        assert response.status_code == 201

        # With 2 types × 3 difficulties = 6 calls (some may be 0 and skipped)
        assert mock_metrics.record_questions_generated.call_count > 0

    @patch("app.core.config.settings.SERVICE_API_KEY", "test-service-key")
    @patch("app.api.v1.admin.generation.app_metrics")
    def test_create_run_type_only_uses_medium_default(self, mock_metrics, client):
        """When only type_metrics is present, uses 'medium' as default difficulty."""
        response = client.post(
            "/v1/admin/generation-runs",
            json={
                "started_at": "2025-01-01T00:00:00Z",
                "completed_at": "2025-01-01T00:05:00Z",
                "duration_seconds": 300.0,
                "status": "success",
                "exit_code": 0,
                "questions_requested": 50,
                "questions_generated": 50,
                "generation_failures": 0,
                "generation_success_rate": 1.0,
                "questions_evaluated": 50,
                "questions_approved": 48,
                "questions_rejected": 2,
                "approval_rate": 0.96,
                "avg_judge_score": 8.5,
                "min_judge_score": 6.0,
                "max_judge_score": 10.0,
                "duplicates_found": 3,
                "exact_duplicates": 1,
                "semantic_duplicates": 2,
                "duplicate_rate": 0.06,
                "questions_inserted": 45,
                "insertion_failures": 0,
                "overall_success_rate": 0.9,
                "total_errors": 0,
                "total_api_calls": 100,
                "type_metrics": {
                    "pattern": 10,
                    "logic": 15,
                },
                "environment": "test",
                "triggered_by": "test",
            },
            headers={"X-Service-Key": "test-service-key"},
        )
        assert response.status_code == 201

        assert mock_metrics.record_questions_generated.call_count == 2
        for call in mock_metrics.record_questions_generated.call_args_list:
            assert call.kwargs["difficulty"] == "medium"

    @patch("app.core.config.settings.SERVICE_API_KEY", "test-service-key")
    @patch("app.api.v1.admin.generation.app_metrics")
    def test_create_run_no_type_metrics_skips_metric(self, mock_metrics, client):
        """create_generation_run skips questions_generated when type_metrics is null."""
        response = client.post(
            "/v1/admin/generation-runs",
            json={
                "started_at": "2025-01-01T00:00:00Z",
                "completed_at": "2025-01-01T00:05:00Z",
                "duration_seconds": 300.0,
                "status": "success",
                "exit_code": 0,
                "questions_requested": 50,
                "questions_generated": 50,
                "generation_failures": 0,
                "generation_success_rate": 1.0,
                "questions_evaluated": 50,
                "questions_approved": 48,
                "questions_rejected": 2,
                "approval_rate": 0.96,
                "avg_judge_score": 8.5,
                "min_judge_score": 6.0,
                "max_judge_score": 10.0,
                "duplicates_found": 3,
                "exact_duplicates": 1,
                "semantic_duplicates": 2,
                "duplicate_rate": 0.06,
                "questions_inserted": 45,
                "insertion_failures": 0,
                "overall_success_rate": 0.9,
                "total_errors": 0,
                "total_api_calls": 100,
                "environment": "test",
                "triggered_by": "test",
            },
            headers={"X-Service-Key": "test-service-key"},
        )
        assert response.status_code == 201

        mock_metrics.record_questions_generated.assert_not_called()
