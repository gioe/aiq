"""
Tests for GET /v1/analytics/model-performance endpoint.

Covers:
- Unauthenticated access returns 401.
- Historical mode (no test_session_id) with 2+ providers.
- Per-test mode (test_session_id) for a known session.
- NULL source_model surfaces as "Unknown Model".
- Questions with NULL source_llm are excluded.
- test_session_id belonging to another user returns 404.
- Non-existent test_session_id returns 404.
- Empty result set (no responses) returns empty list.
- Pagination (limit / offset / has_more).
"""

import pytest

from app.models.models import (
    QuestionType,
    DifficultyLevel,
    TestStatus,
)
from app.models import (
    Question,
    TestSession,
    User,
)
from app.models.models import Response
from app.core.auth.security import hash_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_question(
    db_session,
    *,
    question_text: str,
    source_llm: str | None,
    source_model: str | None,
) -> Question:
    q = Question(
        question_text=question_text,
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="42",
        answer_options={"A": "42", "B": "0"},
        source_llm=source_llm,
        source_model=source_model,
        is_active=True,
    )
    db_session.add(q)
    db_session.flush()
    return q


def _make_session(db_session, *, user_id: int, status: TestStatus) -> TestSession:
    session = TestSession(user_id=user_id, status=status)
    db_session.add(session)
    db_session.flush()
    return session


def _make_response(
    db_session,
    *,
    session_id: int,
    user_id: int,
    question_id: int,
    is_correct: bool,
) -> Response:
    resp = Response(
        test_session_id=session_id,
        user_id=user_id,
        question_id=question_id,
        user_answer="42" if is_correct else "0",
        is_correct=is_correct,
    )
    db_session.add(resp)
    db_session.flush()
    return resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def two_provider_data(db_session, test_user):
    """
    Populate two completed sessions with responses from two vendors
    ('openai' and 'anthropic') and some NULL source_model entries.

    Session A (completed):
      - openai / gpt-4-turbo: 2 correct out of 3
      - openai / NULL (Unknown Model): 1 correct out of 2

    Session B (completed):
      - anthropic / claude-3-opus: 3 correct out of 4

    Also creates one IN_PROGRESS session whose responses must NOT appear
    in the historical aggregate.
    """
    uid = test_user.id

    # --- questions ---
    q_openai_known_1 = _make_question(
        db_session,
        question_text="OpenAI known 1",
        source_llm="openai",
        source_model="gpt-4-turbo",
    )
    q_openai_known_2 = _make_question(
        db_session,
        question_text="OpenAI known 2",
        source_llm="openai",
        source_model="gpt-4-turbo",
    )
    q_openai_known_3 = _make_question(
        db_session,
        question_text="OpenAI known 3",
        source_llm="openai",
        source_model="gpt-4-turbo",
    )
    q_openai_unknown_1 = _make_question(
        db_session,
        question_text="OpenAI unknown model 1",
        source_llm="openai",
        source_model=None,
    )
    q_openai_unknown_2 = _make_question(
        db_session,
        question_text="OpenAI unknown model 2",
        source_llm="openai",
        source_model=None,
    )
    q_anthropic_1 = _make_question(
        db_session,
        question_text="Anthropic 1",
        source_llm="anthropic",
        source_model="claude-3-opus",
    )
    q_anthropic_2 = _make_question(
        db_session,
        question_text="Anthropic 2",
        source_llm="anthropic",
        source_model="claude-3-opus",
    )
    q_anthropic_3 = _make_question(
        db_session,
        question_text="Anthropic 3",
        source_llm="anthropic",
        source_model="claude-3-opus",
    )
    q_anthropic_4 = _make_question(
        db_session,
        question_text="Anthropic 4",
        source_llm="anthropic",
        source_model="claude-3-opus",
    )
    # NULL source_llm — must be excluded entirely
    q_no_vendor = _make_question(
        db_session,
        question_text="No vendor",
        source_llm=None,
        source_model=None,
    )

    # --- session A (completed) ---
    session_a = _make_session(db_session, user_id=uid, status=TestStatus.COMPLETED)
    _make_response(
        db_session,
        session_id=session_a.id,
        user_id=uid,
        question_id=q_openai_known_1.id,
        is_correct=True,
    )
    _make_response(
        db_session,
        session_id=session_a.id,
        user_id=uid,
        question_id=q_openai_known_2.id,
        is_correct=True,
    )
    _make_response(
        db_session,
        session_id=session_a.id,
        user_id=uid,
        question_id=q_openai_known_3.id,
        is_correct=False,
    )
    _make_response(
        db_session,
        session_id=session_a.id,
        user_id=uid,
        question_id=q_openai_unknown_1.id,
        is_correct=True,
    )
    _make_response(
        db_session,
        session_id=session_a.id,
        user_id=uid,
        question_id=q_openai_unknown_2.id,
        is_correct=False,
    )

    # --- session B (completed) ---
    session_b = _make_session(db_session, user_id=uid, status=TestStatus.COMPLETED)
    _make_response(
        db_session,
        session_id=session_b.id,
        user_id=uid,
        question_id=q_anthropic_1.id,
        is_correct=True,
    )
    _make_response(
        db_session,
        session_id=session_b.id,
        user_id=uid,
        question_id=q_anthropic_2.id,
        is_correct=True,
    )
    _make_response(
        db_session,
        session_id=session_b.id,
        user_id=uid,
        question_id=q_anthropic_3.id,
        is_correct=True,
    )
    _make_response(
        db_session,
        session_id=session_b.id,
        user_id=uid,
        question_id=q_anthropic_4.id,
        is_correct=False,
    )

    # --- session C (IN_PROGRESS) — must NOT appear in historical aggregate ---
    session_c = _make_session(db_session, user_id=uid, status=TestStatus.IN_PROGRESS)
    _make_response(
        db_session,
        session_id=session_c.id,
        user_id=uid,
        question_id=q_no_vendor.id,
        is_correct=True,
    )
    # Add a response with a valid source_llm to session C so the test
    # validates session-status filtering, not just the source_llm IS NOT NULL filter.
    q_google_in_progress = _make_question(
        db_session,
        question_text="Google in-progress",
        source_llm="google",
        source_model="gemini-pro",
    )
    _make_response(
        db_session,
        session_id=session_c.id,
        user_id=uid,
        question_id=q_google_in_progress.id,
        is_correct=True,
    )

    db_session.commit()

    return {
        "session_a": session_a,
        "session_b": session_b,
        "session_c": session_c,
        "questions": {
            "openai_known": [q_openai_known_1, q_openai_known_2, q_openai_known_3],
            "openai_unknown": [q_openai_unknown_1, q_openai_unknown_2],
            "anthropic": [q_anthropic_1, q_anthropic_2, q_anthropic_3, q_anthropic_4],
            "no_vendor": q_no_vendor,
        },
    }


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestModelPerformance:
    """Tests for GET /v1/analytics/model-performance."""

    # --- Authentication ---

    def test_unauthenticated_returns_403(self, client):
        """Endpoint must require authentication (HTTPBearer returns 403 for missing credentials)."""
        response = client.get("/v1/analytics/model-performance")
        # FastAPI's HTTPBearer scheme returns 403 when no Authorization header is present.
        assert response.status_code == 403

    # --- Historical mode ---

    def test_historical_two_providers_structure(
        self, client, auth_headers, two_provider_data
    ):
        """Historical mode returns both vendors with correct structure."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert "results" in data
        assert "total_count" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data

        assert data["total_count"] == 2
        assert data["has_more"] is False
        assert data["offset"] == 0

        vendors = {row["vendor"]: row for row in data["results"]}
        assert "openai" in vendors
        assert "anthropic" in vendors

    def test_historical_openai_vendor_accuracy(
        self, client, auth_headers, two_provider_data
    ):
        """Verify openai vendor: 3 correct out of 5 total = 60%."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        vendors = {row["vendor"]: row for row in response.json()["results"]}
        openai = vendors["openai"]

        assert openai["correct"] == 3
        assert openai["total"] == 5
        assert openai["accuracy_pct"] == pytest.approx(60.0)

    def test_historical_anthropic_vendor_accuracy(
        self, client, auth_headers, two_provider_data
    ):
        """Anthropic vendor: 3 correct out of 4 total = 75%."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        vendors = {row["vendor"]: row for row in response.json()["results"]}
        anthropic = vendors["anthropic"]

        assert anthropic["correct"] == 3
        assert anthropic["total"] == 4
        assert anthropic["accuracy_pct"] == pytest.approx(75.0)

    def test_historical_null_source_model_shown_as_unknown(
        self, client, auth_headers, two_provider_data
    ):
        """Questions with NULL source_model appear as 'Unknown Model' under their vendor."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        vendors = {row["vendor"]: row for row in response.json()["results"]}
        openai_models = {m["model"]: m for m in vendors["openai"]["models"]}

        assert "Unknown Model" in openai_models
        unknown = openai_models["Unknown Model"]
        # 1 correct out of 2 for the NULL-source_model openai questions
        assert unknown["correct"] == 1
        assert unknown["total"] == 2
        assert unknown["accuracy_pct"] == pytest.approx(50.0)

    def test_historical_known_model_accuracy(
        self, client, auth_headers, two_provider_data
    ):
        """gpt-4-turbo model: 2 correct out of 3 = 66.7%."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        vendors = {row["vendor"]: row for row in response.json()["results"]}
        openai_models = {m["model"]: m for m in vendors["openai"]["models"]}

        assert "gpt-4-turbo" in openai_models
        gpt4 = openai_models["gpt-4-turbo"]
        assert gpt4["correct"] == 2
        assert gpt4["total"] == 3
        assert gpt4["accuracy_pct"] == pytest.approx(66.7)

    def test_historical_null_source_llm_excluded(
        self, client, auth_headers, two_provider_data
    ):
        """Questions with NULL source_llm must not appear in any vendor row."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        vendor_names = [row["vendor"] for row in response.json()["results"]]
        # 'None' or empty string must not appear
        assert None not in vendor_names
        assert "" not in vendor_names

    def test_historical_in_progress_sessions_excluded(
        self, client, auth_headers, two_provider_data
    ):
        """Responses from IN_PROGRESS sessions must not be included."""
        # session_c is IN_PROGRESS and contains a google/gemini-pro response.
        # If the status filter is broken, "google" would appear in the results.
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        vendor_names = {row["vendor"] for row in response.json()["results"]}
        assert "google" not in vendor_names
        assert response.json()["total_count"] == 2

    def test_historical_empty_when_no_responses(self, client, auth_headers, test_user):
        """User with no responses gets an empty result list."""
        response = client.get(
            "/v1/analytics/model-performance",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total_count"] == 0
        assert data["has_more"] is False

    # --- Pagination ---

    def test_pagination_limit_and_offset(self, client, auth_headers, two_provider_data):
        """Limit and offset correctly page the vendor list."""
        # Fetch only 1 vendor
        response = client.get(
            "/v1/analytics/model-performance?limit=1&offset=0",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["results"]) == 1
        assert data["total_count"] == 2
        assert data["has_more"] is True
        assert data["limit"] == 1
        assert data["offset"] == 0

        # Fetch the second vendor
        response2 = client.get(
            "/v1/analytics/model-performance?limit=1&offset=1",
            headers=auth_headers,
        )
        assert response2.status_code == 200
        data2 = response2.json()
        assert len(data2["results"]) == 1
        assert data2["total_count"] == 2
        assert data2["has_more"] is False

        # The two pages together cover both vendors without overlap
        vendors_page1 = {r["vendor"] for r in data["results"]}
        vendors_page2 = {r["vendor"] for r in data2["results"]}
        assert vendors_page1.isdisjoint(vendors_page2)
        assert vendors_page1 | vendors_page2 == {"openai", "anthropic"}

    def test_pagination_offset_beyond_total(
        self, client, auth_headers, two_provider_data
    ):
        """Offset beyond total_count returns empty results but correct total_count."""
        response = client.get(
            "/v1/analytics/model-performance?limit=50&offset=100",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["results"] == []
        assert data["total_count"] == 2
        assert data["has_more"] is False

    # --- Per-test mode ---

    def test_per_test_session_a(self, client, auth_headers, two_provider_data):
        """Per-test mode returns only openai data from session A."""
        session_id = two_provider_data["session_a"].id
        response = client.get(
            f"/v1/analytics/model-performance?test_session_id={session_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        vendor_names = {row["vendor"] for row in data["results"]}
        assert vendor_names == {"openai"}
        assert data["total_count"] == 1
        assert data["has_more"] is False

        openai_row = data["results"][0]
        assert openai_row["correct"] == 3
        assert openai_row["total"] == 5

    def test_per_test_session_b(self, client, auth_headers, two_provider_data):
        """Per-test mode returns only anthropic data from session B."""
        session_id = two_provider_data["session_b"].id
        response = client.get(
            f"/v1/analytics/model-performance?test_session_id={session_id}",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()

        vendor_names = {row["vendor"] for row in data["results"]}
        assert vendor_names == {"anthropic"}

        anthropic_row = data["results"][0]
        assert anthropic_row["correct"] == 3
        assert anthropic_row["total"] == 4

    def test_per_test_unknown_session_returns_404(self, client, auth_headers):
        """Non-existent test_session_id returns 404."""
        response = client.get(
            "/v1/analytics/model-performance?test_session_id=999999",
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Test session not found."

    def test_per_test_other_users_session_returns_404(
        self, client, auth_headers, db_session, two_provider_data
    ):
        """A test_session_id belonging to another user returns 404 (not 403)."""
        # Create a second user and a session for them
        other_user = User(
            email="other@example.com",
            password_hash=hash_password("password123"),
            first_name="Other",
            last_name="User",
        )
        db_session.add(other_user)
        db_session.commit()
        db_session.refresh(other_user)

        other_session = _make_session(
            db_session, user_id=other_user.id, status=TestStatus.COMPLETED
        )
        db_session.commit()

        response = client.get(
            f"/v1/analytics/model-performance?test_session_id={other_session.id}",
            headers=auth_headers,
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Test session not found."

    def test_per_test_pagination_params_echoed(
        self, client, auth_headers, two_provider_data
    ):
        """In per-test mode, limit/offset are echoed back even though pagination is not applied."""
        session_id = two_provider_data["session_a"].id
        response = client.get(
            f"/v1/analytics/model-performance?test_session_id={session_id}&limit=10&offset=5",
            headers=auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 5
        # has_more is always False for per-test mode
        assert data["has_more"] is False
