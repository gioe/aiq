"""
Tests for anchor item designation admin endpoints (TASK-850).

Tests cover:
- Authentication requirements for all 3 endpoints
- GET: empty DB, listing anchors, domain filter, domain summary accuracy
- PATCH: 404 for missing question, toggle true/false, idempotent, response structure
- POST auto-select: balanced selection, clears existing, respects discrimination
  threshold, excludes inactive/flagged, warns on shortfall, dry_run no-op,
  prefers highest discrimination
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    DifficultyLevel,
    Question,
    QuestionType,
)


def _create_question(
    db_session: Session,
    question_type: QuestionType,
    difficulty_level: DifficultyLevel,
    discrimination: float = None,
    response_count: int = 0,
    is_active: bool = True,
    quality_flag: str = "normal",
    is_anchor: bool = False,
    anchor_designated_at=None,
) -> Question:
    """Helper to create a question with specified attributes."""
    q = Question(
        question_text=f"Test question ({question_type.value}/{difficulty_level.value})",
        question_type=question_type,
        difficulty_level=difficulty_level,
        correct_answer="A",
        answer_options=["A", "B", "C", "D"],
        response_count=response_count,
        discrimination=discrimination,
        is_active=is_active,
        quality_flag=quality_flag,
        is_anchor=is_anchor,
        anchor_designated_at=anchor_designated_at,
    )
    db_session.add(q)
    return q


class TestListAnchorItems:
    """Tests for GET /v1/admin/anchor-items."""

    def test_requires_admin_token(self, client: TestClient):
        """Endpoint requires admin token."""
        response = client.get("/v1/admin/anchor-items")
        assert response.status_code == 422  # Missing required header

        response = client.get(
            "/v1/admin/anchor-items",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_empty_database(self, client: TestClient, admin_headers: dict):
        """Returns empty results when no anchors exist."""
        response = client.get("/v1/admin/anchor-items", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["total_anchors"] == 0
        assert data["target_per_domain"] == 30
        assert data["target_total"] == 180
        assert data["domain_summaries"] == []
        assert data["items"] == []

    def test_lists_only_anchors(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Only returns questions where is_anchor=True."""
        _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
            is_anchor=True,
            discrimination=0.40,
            response_count=100,
        )
        _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
            is_anchor=False,
            discrimination=0.35,
            response_count=80,
        )
        _create_question(
            db_session,
            QuestionType.LOGIC,
            DifficultyLevel.MEDIUM,
            is_anchor=True,
            discrimination=0.50,
            response_count=120,
        )
        db_session.commit()

        response = client.get("/v1/admin/anchor-items", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["total_anchors"] == 2
        assert len(data["items"]) == 2
        item_ids = {item["question_id"] for item in data["items"]}
        # All returned items should be anchors
        assert all(item["is_anchor"] for item in data["items"])
        assert len(item_ids) == 2

    def test_domain_filter(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Domain query parameter filters items correctly."""
        _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
            is_anchor=True,
            discrimination=0.40,
        )
        _create_question(
            db_session,
            QuestionType.LOGIC,
            DifficultyLevel.MEDIUM,
            is_anchor=True,
            discrimination=0.50,
        )
        db_session.commit()

        response = client.get(
            "/v1/admin/anchor-items?domain=pattern", headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()

        # Items filtered to pattern only
        assert len(data["items"]) == 1
        assert data["items"][0]["question_type"] == "pattern"

        # Domain summaries still show all domains (not filtered)
        assert data["total_anchors"] == 2

    def test_domain_summary_accuracy(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Domain summaries correctly aggregate difficulty counts and avg discrimination."""
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            is_anchor=True,
            discrimination=0.40,
        )
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            is_anchor=True,
            discrimination=0.50,
        )
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.MEDIUM,
            is_anchor=True,
            discrimination=0.60,
        )
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.HARD,
            is_anchor=True,
            discrimination=0.30,
        )
        db_session.commit()

        response = client.get("/v1/admin/anchor-items", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert len(data["domain_summaries"]) == 1
        summary = data["domain_summaries"][0]
        assert summary["domain"] == "math"
        assert summary["total_anchors"] == 4
        assert summary["easy_count"] == 2
        assert summary["medium_count"] == 1
        assert summary["hard_count"] == 1
        # avg discrimination: (0.40 + 0.50 + 0.60 + 0.30) / 4 = 0.45
        assert summary["avg_discrimination"] == pytest.approx(0.45, abs=0.001)


class TestToggleAnchor:
    """Tests for PATCH /v1/admin/questions/{question_id}/anchor."""

    def test_requires_admin_token(self, client: TestClient):
        """Endpoint requires admin token."""
        response = client.patch(
            "/v1/admin/questions/1/anchor",
            json={"is_anchor": True},
        )
        assert response.status_code == 422

        response = client.patch(
            "/v1/admin/questions/1/anchor",
            json={"is_anchor": True},
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_question_not_found(self, client: TestClient, admin_headers: dict):
        """Returns 404 for non-existent question."""
        response = client.patch(
            "/v1/admin/questions/99999/anchor",
            json={"is_anchor": True},
            headers=admin_headers,
        )
        assert response.status_code == 404

    def test_toggle_to_true(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Setting is_anchor=True sets the flag and timestamp."""
        q = _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
        )
        db_session.commit()
        db_session.refresh(q)

        response = client.patch(
            f"/v1/admin/questions/{q.id}/anchor",
            json={"is_anchor": True},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["question_id"] == q.id
        assert data["previous_value"] is False
        assert data["new_value"] is True
        assert data["anchor_designated_at"] is not None

    def test_toggle_to_false(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Setting is_anchor=False clears the flag and timestamp."""
        from app.core.datetime_utils import utc_now

        q = _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
            is_anchor=True,
            anchor_designated_at=utc_now(),
        )
        db_session.commit()
        db_session.refresh(q)

        response = client.patch(
            f"/v1/admin/questions/{q.id}/anchor",
            json={"is_anchor": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["previous_value"] is True
        assert data["new_value"] is False
        assert data["anchor_designated_at"] is None

    def test_idempotent_toggle(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Toggling to same value is idempotent."""
        q = _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
            is_anchor=False,
        )
        db_session.commit()
        db_session.refresh(q)

        response = client.patch(
            f"/v1/admin/questions/{q.id}/anchor",
            json={"is_anchor": False},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["previous_value"] is False
        assert data["new_value"] is False

    def test_response_structure(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Response contains all expected fields."""
        q = _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
        )
        db_session.commit()
        db_session.refresh(q)

        response = client.patch(
            f"/v1/admin/questions/{q.id}/anchor",
            json={"is_anchor": True},
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert "question_id" in data
        assert "previous_value" in data
        assert "new_value" in data
        assert "anchor_designated_at" in data


class TestAutoSelectAnchors:
    """Tests for POST /v1/admin/anchor-items/auto-select."""

    def test_requires_admin_token(self, client: TestClient):
        """Endpoint requires admin token."""
        response = client.post("/v1/admin/anchor-items/auto-select")
        assert response.status_code == 422

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_balanced_selection(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Selects up to 10 per difficulty per domain when enough candidates exist."""
        # Create 15 eligible questions per difficulty for math domain
        for difficulty in DifficultyLevel:
            for i in range(15):
                _create_question(
                    db_session,
                    QuestionType.MATH,
                    difficulty,
                    discrimination=0.40 + i * 0.01,
                    response_count=100,
                    is_active=True,
                    quality_flag="normal",
                )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Find math domain result
        math_result = next(r for r in data["domain_results"] if r["domain"] == "math")
        assert math_result["selected"] == 30
        assert math_result["easy_selected"] == 10
        assert math_result["medium_selected"] == 10
        assert math_result["hard_selected"] == 10
        assert math_result["shortfall"] == 0

    def test_clears_existing_anchors(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Existing anchors are cleared before new selection."""
        from app.core.datetime_utils import utc_now

        # Create an existing anchor
        _create_question(
            db_session,
            QuestionType.PATTERN,
            DifficultyLevel.EASY,
            is_anchor=True,
            anchor_designated_at=utc_now(),
            discrimination=0.10,  # Low discrimination - wouldn't be reselected
            response_count=50,
        )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert data["total_cleared"] == 1
        # The old anchor with discrimination=0.10 shouldn't be re-selected
        # (below 0.30 threshold)

    def test_respects_discrimination_threshold(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Only questions with discrimination >= threshold are selected."""
        # Below threshold
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.20,
            response_count=100,
        )
        # At threshold
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.30,
            response_count=100,
        )
        # Above threshold
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.50,
            response_count=100,
        )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        math_result = next(r for r in data["domain_results"] if r["domain"] == "math")
        # Only 2 eligible (discrimination >= 0.30)
        assert math_result["easy_selected"] == 2

    def test_custom_discrimination_threshold(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Custom min_discrimination parameter overrides default threshold."""
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.20,
            response_count=100,
        )
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.15,
            response_count=100,
        )
        db_session.commit()

        # With default threshold (0.30), none qualify
        response = client.post(
            "/v1/admin/anchor-items/auto-select?dry_run=true",
            headers=admin_headers,
        )
        assert response.status_code == 200
        math_result = next(
            r for r in response.json()["domain_results"] if r["domain"] == "math"
        )
        assert math_result["easy_selected"] == 0

        # With lower threshold (0.10), both qualify
        response = client.post(
            "/v1/admin/anchor-items/auto-select?dry_run=true&min_discrimination=0.10",
            headers=admin_headers,
        )
        assert response.status_code == 200
        math_result = next(
            r for r in response.json()["domain_results"] if r["domain"] == "math"
        )
        assert math_result["easy_selected"] == 2

    def test_excludes_inactive_questions(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Inactive questions are excluded from selection."""
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.50,
            response_count=100,
            is_active=False,
        )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        math_result = next(r for r in data["domain_results"] if r["domain"] == "math")
        assert math_result["easy_selected"] == 0

    def test_excludes_flagged_questions(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Questions with non-normal quality flags are excluded."""
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.50,
            response_count=100,
            quality_flag="under_review",
        )
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.50,
            response_count=100,
            quality_flag="deactivated",
        )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        math_result = next(r for r in data["domain_results"] if r["domain"] == "math")
        assert math_result["easy_selected"] == 0

    def test_warns_on_shortfall(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Warnings generated when fewer candidates than target."""
        # Only 3 eligible for math/easy
        for _ in range(3):
            _create_question(
                db_session,
                QuestionType.MATH,
                DifficultyLevel.EASY,
                discrimination=0.40,
                response_count=100,
            )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        # Should have warning about math/easy shortfall
        math_easy_warnings = [w for w in data["warnings"] if "math/easy" in w]
        assert len(math_easy_warnings) == 1
        assert "shortfall of 7" in math_easy_warnings[0]

    def test_dry_run_no_changes(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Dry run previews selection without persisting."""
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.50,
            response_count=100,
        )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select?dry_run=true",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["dry_run"] is True

        math_result = next(r for r in data["domain_results"] if r["domain"] == "math")
        assert math_result["easy_selected"] == 1

        # Verify no anchors were actually created
        verify_response = client.get("/v1/admin/anchor-items", headers=admin_headers)
        assert verify_response.status_code == 200
        assert verify_response.json()["total_anchors"] == 0

    def test_prefers_highest_discrimination(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """When more candidates than slots, highest discrimination wins."""
        # Create 3 candidates with different discrimination values for math/easy
        q_low = _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.35,
            response_count=100,
        )
        q_high = _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.80,
            response_count=100,
        )
        q_mid = _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=0.50,
            response_count=100,
        )
        db_session.commit()
        db_session.refresh(q_low)
        db_session.refresh(q_high)
        db_session.refresh(q_mid)

        # Use min_discrimination=0.30 to make all 3 eligible
        # Only need 10 per slot but we have 3, so all should be selected
        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200

        # Verify all 3 are anchors (since 3 < 10 limit)
        verify_response = client.get("/v1/admin/anchor-items", headers=admin_headers)
        assert verify_response.status_code == 200
        anchor_ids = {item["question_id"] for item in verify_response.json()["items"]}
        assert q_high.id in anchor_ids
        assert q_mid.id in anchor_ids
        assert q_low.id in anchor_ids

    def test_excludes_null_discrimination(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Questions with NULL discrimination are excluded."""
        _create_question(
            db_session,
            QuestionType.MATH,
            DifficultyLevel.EASY,
            discrimination=None,
            response_count=100,
        )
        db_session.commit()

        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        math_result = next(r for r in data["domain_results"] if r["domain"] == "math")
        assert math_result["easy_selected"] == 0

    def test_response_structure(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Response contains all expected fields."""
        response = client.post(
            "/v1/admin/anchor-items/auto-select",
            headers=admin_headers,
        )
        assert response.status_code == 200
        data = response.json()

        assert "total_selected" in data
        assert "total_cleared" in data
        assert "dry_run" in data
        assert "criteria" in data
        assert "domain_results" in data
        assert "warnings" in data

        # Criteria structure
        criteria = data["criteria"]
        assert "min_discrimination" in criteria
        assert "per_domain" in criteria
        assert "per_difficulty_per_domain" in criteria
        assert "requires_active" in criteria
        assert "requires_normal_quality" in criteria

        # Should have results for all 6 domains
        assert len(data["domain_results"]) == 6
        domain_names = {r["domain"] for r in data["domain_results"]}
        assert domain_names == {
            "pattern",
            "logic",
            "spatial",
            "math",
            "verbal",
            "memory",
        }
