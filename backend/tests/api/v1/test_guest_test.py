"""Tests for the guest test endpoints (POST /v1/test/guest/start)."""

import pytest

from app.core.config import settings
from app.models.models import (
    DifficultyLevel,
    Question,
    QuestionType,
    User,
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
