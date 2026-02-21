"""
Tests for CAT readiness admin endpoints (TASK-835).

Tests cover:
- Authentication requirements on both endpoints
- GET before any evaluation returns default state
- POST with insufficient items → not ready
- POST with sufficient items → enables CAT
- Re-evaluation can disable CAT if items removed
"""

from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.system_config import set_cat_readiness
from app.models.models import (
    DifficultyLevel,
    Question,
    QuestionType,
)


def _create_calibrated_question(
    db_session: Session,
    question_type: QuestionType,
    irt_difficulty: float,
    irt_se_difficulty: float = 0.20,
    irt_se_discrimination: float = 0.15,
    irt_discrimination: float = 1.0,
    is_active: bool = True,
    quality_flag: str = "normal",
) -> Question:
    """Helper to create a well-calibrated question."""
    q = Question(
        question_text=f"CAT test question ({question_type.value}, b={irt_difficulty})",
        question_type=question_type,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="A",
        answer_options=["A", "B", "C", "D"],
        is_active=is_active,
        quality_flag=quality_flag,
        irt_difficulty=irt_difficulty,
        irt_discrimination=irt_discrimination,
        irt_se_difficulty=irt_se_difficulty,
        irt_se_discrimination=irt_se_discrimination,
        irt_calibrated_at=datetime(2026, 1, 15, 12, 0, 0),
    )
    db_session.add(q)
    return q


def _populate_domain_ready(
    db_session: Session,
    question_type: QuestionType,
) -> None:
    """Helper to populate a domain with enough calibrated items to pass."""
    # Easy items: b < -1.0
    for i in range(10):
        _create_calibrated_question(
            db_session, question_type, irt_difficulty=-1.5 - i * 0.1
        )
    # Medium items: -1.0 <= b <= 1.0
    for i in range(15):
        _create_calibrated_question(
            db_session, question_type, irt_difficulty=-0.5 + i * 0.1
        )
    # Hard items: b > 1.0
    for i in range(10):
        _create_calibrated_question(
            db_session, question_type, irt_difficulty=1.5 + i * 0.1
        )


class TestGetCATReadiness:
    """Tests for GET /v1/admin/cat-readiness."""

    def test_requires_admin_token(self, client: TestClient):
        """Endpoint requires admin token."""
        response = client.get("/v1/admin/cat-readiness")
        assert response.status_code == 422

        response = client.get(
            "/v1/admin/cat-readiness",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_default_state_before_evaluation(
        self, client: TestClient, admin_headers: dict
    ):
        """GET before any evaluation returns default state."""
        response = client.get("/v1/admin/cat-readiness", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["is_globally_ready"] is False
        assert data["cat_enabled"] is False
        assert data["evaluated_at"] is None
        assert data["domains"] == []
        assert data["summary"] == "Never evaluated"
        assert "thresholds" in data

    def test_returns_persisted_result(
        self,
        client: TestClient,
        admin_headers: dict,
        db_session: Session,
    ):
        """GET returns previously persisted evaluation result."""
        set_cat_readiness(
            db_session,
            {
                "enabled": False,
                "is_globally_ready": False,
                "evaluated_at": "2026-01-15T12:00:00",
                "thresholds": {
                    "min_calibrated_items_per_domain": 30,
                    "max_se_difficulty": 0.50,
                    "max_se_discrimination": 0.30,
                    "min_items_per_difficulty_band": 5,
                },
                "domains": [
                    {
                        "domain": "pattern",
                        "is_ready": False,
                        "total_calibrated": 5,
                        "well_calibrated": 3,
                        "easy_count": 1,
                        "medium_count": 1,
                        "hard_count": 1,
                        "reasons": ["Insufficient well-calibrated items: 3/30"],
                    }
                ],
                "summary": "1/6 domains ready for CAT",
            },
        )

        response = client.get("/v1/admin/cat-readiness", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert data["is_globally_ready"] is False
        assert data["cat_enabled"] is False
        assert data["evaluated_at"] is not None
        assert len(data["domains"]) == 1
        assert data["domains"][0]["domain"] == "pattern"

    def test_response_structure(self, client: TestClient, admin_headers: dict):
        """Response contains all expected fields."""
        response = client.get("/v1/admin/cat-readiness", headers=admin_headers)
        assert response.status_code == 200
        data = response.json()

        assert "is_globally_ready" in data
        assert "cat_enabled" in data
        assert "evaluated_at" in data
        assert "thresholds" in data
        assert "domains" in data
        assert "summary" in data

        thresholds = data["thresholds"]
        assert "min_calibrated_items_per_domain" in thresholds
        assert "max_se_difficulty" in thresholds
        assert "max_se_discrimination" in thresholds
        assert "min_items_per_difficulty_band" in thresholds


class TestEvaluateCATReadiness:
    """Tests for POST /v1/admin/cat-readiness/evaluate."""

    def test_requires_admin_token(self, client: TestClient):
        """Endpoint requires admin token."""
        response = client.post("/v1/admin/cat-readiness/evaluate")
        assert response.status_code == 422

        response = client.post(
            "/v1/admin/cat-readiness/evaluate",
            headers={"X-Admin-Token": "invalid-token"},
        )
        assert response.status_code == 401

    def test_insufficient_items_not_ready(
        self, client: TestClient, admin_headers: dict
    ):
        """POST with no calibrated items → not ready, CAT not enabled."""
        response = client.post(
            "/v1/admin/cat-readiness/evaluate", headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()

        assert data["is_globally_ready"] is False
        assert data["cat_enabled"] is False
        assert data["evaluated_at"] is not None
        assert len(data["domains"]) == 6

        # All domains should be not ready
        for domain in data["domains"]:
            assert domain["is_ready"] is False
            assert domain["total_calibrated"] == 0

    def test_sufficient_items_enables_cat(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """POST with all domains passing → globally ready, CAT enabled."""
        for q_type in QuestionType:
            _populate_domain_ready(db_session, q_type)
        db_session.commit()

        response = client.post(
            "/v1/admin/cat-readiness/evaluate", headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()

        assert data["is_globally_ready"] is True
        assert data["cat_enabled"] is True
        assert "6/6" in data["summary"]

        # All domains should be ready
        for domain in data["domains"]:
            assert domain["is_ready"] is True
            assert domain["well_calibrated"] >= 30

    def test_reevaluation_can_disable_cat(
        self, client: TestClient, admin_headers: dict, db_session: Session
    ):
        """Re-evaluation can disable CAT if items are removed."""
        # First, enable CAT
        for q_type in QuestionType:
            _populate_domain_ready(db_session, q_type)
        db_session.commit()

        response = client.post(
            "/v1/admin/cat-readiness/evaluate", headers=admin_headers
        )
        assert response.json()["cat_enabled"] is True

        # Deactivate all pattern questions
        pattern_questions = (
            db_session.query(Question)
            .filter(Question.question_type == QuestionType.PATTERN)
            .all()
        )
        for q in pattern_questions:
            q.is_active = False
        db_session.commit()

        # Re-evaluate
        response = client.post(
            "/v1/admin/cat-readiness/evaluate", headers=admin_headers
        )
        data = response.json()

        assert data["is_globally_ready"] is False
        assert data["cat_enabled"] is False

        # Pattern should be not ready, others still ready
        pattern_domain = next(d for d in data["domains"] if d["domain"] == "pattern")
        assert pattern_domain["is_ready"] is False

    def test_persists_to_system_config(self, client: TestClient, admin_headers: dict):
        """POST evaluation persists result, retrievable via GET."""
        # Evaluate (empty → not ready)
        client.post("/v1/admin/cat-readiness/evaluate", headers=admin_headers)

        # GET should now return the persisted result
        response = client.get("/v1/admin/cat-readiness", headers=admin_headers)
        data = response.json()

        assert data["evaluated_at"] is not None
        assert data["is_globally_ready"] is False
        assert len(data["domains"]) == 6

    def test_response_structure(self, client: TestClient, admin_headers: dict):
        """Response contains all expected fields."""
        response = client.post(
            "/v1/admin/cat-readiness/evaluate", headers=admin_headers
        )
        assert response.status_code == 200
        data = response.json()

        assert "is_globally_ready" in data
        assert "cat_enabled" in data
        assert "evaluated_at" in data
        assert "thresholds" in data
        assert "domains" in data
        assert "summary" in data

        # Should have results for all 6 domains
        assert len(data["domains"]) == 6
        domain_names = {d["domain"] for d in data["domains"]}
        assert domain_names == {
            "pattern",
            "logic",
            "spatial",
            "math",
            "verbal",
            "memory",
        }

        # Each domain should have full structure
        for domain in data["domains"]:
            assert "is_ready" in domain
            assert "total_calibrated" in domain
            assert "well_calibrated" in domain
            assert "easy_count" in domain
            assert "medium_count" in domain
            assert "hard_count" in domain
            assert "reasons" in domain
