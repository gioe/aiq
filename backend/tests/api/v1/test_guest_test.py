"""Tests for the guest test endpoints (POST /v1/test/guest/start)."""

import pytest

from app.api.v1 import guest_test as guest_test_module
from app.core.config import settings
from app.core.auth.security import create_access_token
from app.models import models
from app.models.models import (
    DifficultyLevel,
    Question,
    QuestionType,
    User,
    UserQuestion,
)


@pytest.fixture
def guest_user(db_session):
    """Create the sentinel guest user (GUEST_USER_ID = -1) in the test DB."""
    user = User(
        id=settings.GUEST_USER_ID,
        email="guest@aiq.local",
        password_hash="nologin",  # pragma: allowlist secret
        first_name="Guest",
        last_name="User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def many_questions(db_session):
    """Create enough active questions to satisfy TEST_TOTAL_QUESTIONS."""
    types = list(QuestionType)
    difficulties = list(DifficultyLevel)
    questions = []
    for i in range(settings.TEST_TOTAL_QUESTIONS + 5):
        q = Question(
            question_text=f"Test question {i}?",
            question_type=types[i % len(types)],
            difficulty_level=difficulties[i % len(difficulties)],
            correct_answer="A",
            answer_options={"A": "Correct", "B": "Wrong", "C": "Nope", "D": "No"},
            explanation=f"Explanation {i}",
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
        )
        questions.append(q)
    db_session.add_all(questions)
    db_session.commit()
    for q in questions:
        db_session.refresh(q)
    return questions


class TestGuestConcurrentStart:
    """Verify concurrent guest test starts no longer conflict."""

    def test_two_concurrent_guest_starts_succeed(
        self, client, db_session, guest_user, many_questions
    ):
        """Two guest starts with different device_ids should both return 200."""
        resp1 = client.post(
            "/v1/test/guest/start",
            headers={"X-Device-Id": "device-aaa"},
        )
        assert resp1.status_code == 200, resp1.json()

        resp2 = client.post(
            "/v1/test/guest/start",
            headers={"X-Device-Id": "device-bbb"},
        )
        assert resp2.status_code == 200, resp2.json()

        # Both should have distinct session IDs
        sid1 = resp1.json()["session"]["id"]
        sid2 = resp2.json()["session"]["id"]
        assert sid1 != sid2

    def test_authenticated_user_still_blocked_from_two_sessions(
        self, client, db_session, guest_user, many_questions, test_user, auth_headers
    ):
        """Authenticated users should still be limited to one IN_PROGRESS session."""
        # Start first test
        resp1 = client.post("/v1/test/start", headers=auth_headers)
        assert resp1.status_code == 200, resp1.json()

        # Second start should be blocked (400 — active session already exists)
        resp2 = client.post("/v1/test/start", headers=auth_headers)
        assert resp2.status_code == 400, resp2.json()
        assert "active test session" in resp2.json()["detail"].lower()


@pytest.fixture(autouse=True)
def reset_guest_token_store():
    """Use an isolated in-memory guest token store for each test."""
    guest_test_module.init_guest_token_store(None)


def _submit_completed_guest_test(client):
    start_response = client.post(
        "/v1/test/guest/start",
        headers={"X-Device-Id": "claim-device"},
    )
    assert start_response.status_code == 200, start_response.json()
    start_data = start_response.json()

    submission = {
        "guest_token": start_data["guest_token"],
        "responses": [
            {
                "question_id": question["id"],
                "user_answer": "A",
                "time_spent_seconds": 12,
            }
            for question in start_data["questions"]
        ],
    }
    submit_response = client.post("/v1/test/guest/submit", json=submission)
    assert submit_response.status_code == 200, submit_response.json()
    return submit_response.json()


class AtomicGuestTokenStore:
    def __init__(self, payload):
        """Initialize the fake store with a single consumable payload."""
        self.payload = payload
        self.get_and_delete_calls = 0

    def get_and_delete(self, token):
        self.get_and_delete_calls += 1
        payload = self.payload
        self.payload = None
        return payload

    def get(self, token):
        raise AssertionError("submit token consumption must use atomic get-and-delete")

    def delete(self, token):
        raise AssertionError("submit token consumption must use atomic get-and-delete")


class TestGuestTokenConsumption:
    def test_submit_token_consumption_uses_atomic_store_operation(self):
        payload = {
            "token_type": "submit",
            "session_id": 123,
            "device_id": "device-123",
            "question_ids": [1, 2, 3],
        }
        store = AtomicGuestTokenStore(payload)
        guest_test_module._token_store = store

        assert guest_test_module._consume_guest_token("token-123") == payload
        assert guest_test_module._consume_guest_token("token-123") is None
        assert store.get_and_delete_calls == 2

    def test_submit_token_consumption_rejects_non_submit_token_after_consume(self):
        store = AtomicGuestTokenStore(
            {
                "token_type": "claim",
                "session_id": 123,
                "device_id": "device-123",
                "question_ids": [1, 2, 3],
            }
        )
        guest_test_module._token_store = store

        assert guest_test_module._consume_guest_token("token-123") is None
        assert guest_test_module._consume_guest_token("token-123") is None


class TestGuestResultClaim:
    def test_guest_submit_returns_claim_token(self, client, guest_user, many_questions):
        submit_data = _submit_completed_guest_test(client)

        assert submit_data["claim_token"]

    def test_authenticated_user_claims_guest_result(
        self, client, db_session, guest_user, many_questions, test_user, auth_headers
    ):
        submit_data = _submit_completed_guest_test(client)
        claim_token = submit_data["claim_token"]
        session_id = submit_data["session"]["id"]
        result_id = submit_data["result"]["id"]

        response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": claim_token},
            headers=auth_headers,
        )

        assert response.status_code == 200, response.json()
        data = response.json()
        assert data["session"]["id"] == session_id
        assert data["result"]["id"] == result_id
        assert data["result"]["user_id"] == test_user.id

        db_session.expire_all()
        session = db_session.query(models.TestSession).filter_by(id=session_id).one()
        result = db_session.query(models.TestResult).filter_by(id=result_id).one()
        responses = (
            db_session.query(models.Response)
            .filter_by(test_session_id=session_id)
            .all()
        )
        assert session.user_id == test_user.id
        assert result.user_id == test_user.id
        assert responses
        assert {response.user_id for response in responses} == {test_user.id}
        seen_question_ids = {
            row.question_id
            for row in db_session.query(UserQuestion).filter_by(
                user_id=test_user.id, test_session_id=session_id
            )
        }
        response_question_ids = {response.question_id for response in responses}
        assert seen_question_ids == response_question_ids

        history_response = client.get("/v1/test/history", headers=auth_headers)
        assert history_response.status_code == 200, history_response.json()
        history_result_ids = {item["id"] for item in history_response.json()["results"]}
        assert result_id in history_result_ids

    def test_claim_rejects_invalid_token(self, client, auth_headers):
        response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": "not-a-real-token"},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "invalid or expired" in response.json()["detail"].lower()

    def test_claim_rejects_expired_token(
        self, client, guest_user, many_questions, auth_headers
    ):
        submit_data = _submit_completed_guest_test(client)
        claim_token = submit_data["claim_token"]
        guest_test_module._get_token_store().delete(claim_token)

        response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": claim_token},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "invalid or expired" in response.json()["detail"].lower()

    def test_claim_rejects_already_claimed_result(
        self, client, guest_user, many_questions, auth_headers
    ):
        submit_data = _submit_completed_guest_test(client)
        claim_token = submit_data["claim_token"]

        first_response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": claim_token},
            headers=auth_headers,
        )
        assert first_response.status_code == 200, first_response.json()

        second_response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": claim_token},
            headers=auth_headers,
        )

        assert second_response.status_code == 409
        assert "already claimed" in second_response.json()["detail"].lower()

    def test_claim_does_not_expose_result_to_other_user(
        self, client, db_session, guest_user, many_questions, test_user, auth_headers
    ):
        submit_data = _submit_completed_guest_test(client)
        claim_token = submit_data["claim_token"]
        result_id = submit_data["result"]["id"]

        first_response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": claim_token},
            headers=auth_headers,
        )
        assert first_response.status_code == 200, first_response.json()

        other_user = User(
            email="other@example.com",
            password_hash="hashed",  # pragma: allowlist secret
            first_name="Other",
            last_name="User",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)
        other_headers = {
            "Authorization": f"Bearer {create_access_token({'user_id': other_user.id})}"
        }

        second_response = client.post(
            "/v1/test/guest/claim",
            json={"claim_token": claim_token},
            headers=other_headers,
        )
        assert second_response.status_code == 409

        other_history = client.get("/v1/test/history", headers=other_headers)
        assert other_history.status_code == 200, other_history.json()
        other_result_ids = {item["id"] for item in other_history.json()["results"]}
        assert result_id not in other_result_ids
