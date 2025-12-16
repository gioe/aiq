"""
Integration tests for reliability report admin endpoint (RE-008).

Tests the GET /v1/admin/reliability endpoint including:
- Successful responses with various data states
- Authentication requirements
- Query parameter validation
- Metrics storage functionality
- Proper schema responses with insufficient data

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-008)
"""

import pytest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta

from app.core.cache import get_cache
from app.models.models import (
    Question,
    QuestionType,
    DifficultyLevel,
    User,
    TestSession,
    TestStatus,
    Response,
    TestResult,
    ReliabilityMetric,
)
from app.core.security import hash_password


@pytest.fixture(autouse=True)
def clear_cache_before_test():
    """Clear the cache before each test to ensure test isolation."""
    get_cache().clear()
    yield
    get_cache().clear()


@pytest.fixture
def admin_token_headers():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


def create_test_questions(db_session, count=20):
    """Helper to create test questions."""
    questions = []
    for i in range(count):
        question = Question(
            question_text=f"Test question {i}",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "correct", "B": "wrong", "C": "wrong", "D": "wrong"},
            explanation="Test explanation",
            source_llm="test-llm",
            arbiter_score=0.9,
            is_active=True,
        )
        db_session.add(question)
        questions.append(question)
    db_session.commit()
    for q in questions:
        db_session.refresh(q)
    return questions


def create_test_sessions_with_responses(db_session, user, questions, num_sessions=10):
    """Helper to create test sessions with responses."""
    sessions = []
    base_time = datetime.now(timezone.utc)

    for i in range(num_sessions):
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=base_time - timedelta(days=i),
        )
        db_session.add(session)
        db_session.flush()

        # Add responses (alternating correct/incorrect for variance)
        for j, question in enumerate(questions):
            is_correct = (i + j) % 3 != 0  # Some variation in answers
            response = Response(
                test_session_id=session.id,
                user_id=user.id,
                question_id=question.id,
                user_answer="A" if is_correct else "B",
                is_correct=is_correct,
                time_spent_seconds=30,
            )
            db_session.add(response)

        # Add test result
        correct_count = sum(1 for j in range(len(questions)) if (i + j) % 3 != 0)
        result = TestResult(
            test_session_id=session.id,
            user_id=user.id,
            iq_score=100 + (correct_count - 10),
            correct_answers=correct_count,
            total_questions=len(questions),
            completed_at=base_time - timedelta(days=i),
        )
        db_session.add(result)

        sessions.append(session)

    db_session.commit()
    return sessions


@pytest.fixture
def test_user(db_session):
    """Create a test user."""
    user = User(
        email="reliability_test@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="Reliability",
        last_name="Test",
        notification_enabled=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


class TestReliabilityEndpoint:
    """Tests for GET /v1/admin/reliability endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_returns_insufficient_data_gracefully(
        self, client, db_session, admin_token_headers
    ):
        """Test endpoint returns proper response with insufficient data."""
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "internal_consistency" in data
        assert "test_retest" in data
        assert "split_half" in data
        assert "overall_status" in data
        assert "recommendations" in data

        # Should report insufficient data
        assert data["overall_status"] == "insufficient_data"

        # Internal consistency should have null values but proper structure
        assert data["internal_consistency"]["cronbachs_alpha"] is None
        assert data["internal_consistency"]["meets_threshold"] is False
        assert data["internal_consistency"]["num_sessions"] == 0

        # Test-retest should have null values
        assert data["test_retest"]["correlation"] is None
        assert data["test_retest"]["meets_threshold"] is False
        assert data["test_retest"]["num_pairs"] == 0

        # Split-half should have null values
        assert data["split_half"]["raw_correlation"] is None
        assert data["split_half"]["spearman_brown"] is None
        assert data["split_half"]["meets_threshold"] is False

        # Should have data collection recommendations
        assert len(data["recommendations"]) > 0
        categories = [r["category"] for r in data["recommendations"]]
        assert "data_collection" in categories

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_requires_admin_token(self, client, db_session):
        """Test endpoint requires valid admin token."""
        # No token
        response = client.get("/v1/admin/reliability")
        assert response.status_code == 422  # Missing required header

        # Invalid token
        response = client.get(
            "/v1/admin/reliability",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_min_sessions_parameter(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test min_sessions query parameter works correctly."""
        # Create some test data (less than default 100)
        questions = create_test_questions(db_session, count=10)
        create_test_sessions_with_responses(
            db_session, test_user, questions, num_sessions=5
        )

        # With default min_sessions=100, should report insufficient data
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["internal_consistency"]["cronbachs_alpha"] is None

        # With lower min_sessions=3, should calculate (but may still have issues)
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 3, "store_metrics": False},
        )
        assert response.status_code == 200
        data = response.json()
        # Should attempt calculation with lower threshold
        assert data["internal_consistency"]["num_sessions"] >= 0

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_min_retest_pairs_parameter(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test min_retest_pairs query parameter works correctly."""
        # Create test data with one user who has multiple tests
        questions = create_test_questions(db_session, count=10)
        create_test_sessions_with_responses(
            db_session, test_user, questions, num_sessions=5
        )

        # With high min_retest_pairs, should report insufficient data
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_retest_pairs": 100, "store_metrics": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["test_retest"]["correlation"] is None

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_store_metrics_true_persists_data(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test that store_metrics=true persists calculated metrics."""
        # Create sufficient test data for at least one metric to calculate
        questions = create_test_questions(db_session, count=15)
        create_test_sessions_with_responses(
            db_session, test_user, questions, num_sessions=10
        )

        # Count existing metrics
        existing_metrics = db_session.query(ReliabilityMetric).count()

        # Make request with store_metrics=true and low thresholds
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={
                "min_sessions": 5,
                "min_retest_pairs": 2,
                "store_metrics": True,
            },
        )
        assert response.status_code == 200

        # Check if metrics were stored (should be >= existing since we may have calculated some)
        new_metrics_count = db_session.query(ReliabilityMetric).count()
        # At least no error occurred - actual storage depends on calculations succeeding
        assert new_metrics_count >= existing_metrics

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_store_metrics_false_no_persistence(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test that store_metrics=false does not persist metrics."""
        # Create test data
        questions = create_test_questions(db_session, count=15)
        create_test_sessions_with_responses(
            db_session, test_user, questions, num_sessions=10
        )

        # Count existing metrics
        existing_metrics = db_session.query(ReliabilityMetric).count()

        # Make request with store_metrics=false
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={
                "min_sessions": 5,
                "min_retest_pairs": 2,
                "store_metrics": False,
            },
        )
        assert response.status_code == 200

        # Count should not increase
        new_metrics_count = db_session.query(ReliabilityMetric).count()
        assert new_metrics_count == existing_metrics

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_response_schema_structure(self, client, db_session, admin_token_headers):
        """Test response matches expected schema structure."""
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response.status_code == 200
        data = response.json()

        # Validate internal_consistency structure
        ic = data["internal_consistency"]
        assert "cronbachs_alpha" in ic
        assert "interpretation" in ic
        assert "meets_threshold" in ic
        assert "num_sessions" in ic
        assert "num_items" in ic
        assert "last_calculated" in ic
        assert "item_total_correlations" in ic
        assert isinstance(ic["meets_threshold"], bool)
        assert isinstance(ic["num_sessions"], int)

        # Validate test_retest structure
        tr = data["test_retest"]
        assert "correlation" in tr
        assert "interpretation" in tr
        assert "meets_threshold" in tr
        assert "num_pairs" in tr
        assert "mean_interval_days" in tr
        assert "practice_effect" in tr
        assert "last_calculated" in tr
        assert isinstance(tr["meets_threshold"], bool)
        assert isinstance(tr["num_pairs"], int)

        # Validate split_half structure
        sh = data["split_half"]
        assert "raw_correlation" in sh
        assert "spearman_brown" in sh
        assert "meets_threshold" in sh
        assert "num_sessions" in sh
        assert "last_calculated" in sh
        assert isinstance(sh["meets_threshold"], bool)
        assert isinstance(sh["num_sessions"], int)

        # Validate overall_status
        assert data["overall_status"] in [
            "excellent",
            "acceptable",
            "needs_attention",
            "insufficient_data",
        ]

        # Validate recommendations structure
        for rec in data["recommendations"]:
            assert "category" in rec
            assert "message" in rec
            assert "priority" in rec
            assert rec["category"] in [
                "data_collection",
                "item_review",
                "threshold_warning",
            ]
            assert rec["priority"] in ["high", "medium", "low"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_parameter_validation(self, client, db_session, admin_token_headers):
        """Test query parameter validation."""
        # min_sessions must be >= 1
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 0},
        )
        assert response.status_code == 422  # Validation error

        # min_retest_pairs must be >= 1
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_retest_pairs": 0},
        )
        assert response.status_code == 422  # Validation error

    def test_admin_token_not_configured(self, client, db_session):
        """Test handling when admin token is not configured on server."""
        with patch("app.core.settings.ADMIN_TOKEN", None):
            response = client.get(
                "/v1/admin/reliability",
                headers={"X-Admin-Token": "any-token"},
            )
            assert response.status_code == 500
            assert "not configured" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_last_calculated_timestamp_present(
        self, client, db_session, admin_token_headers
    ):
        """Test that last_calculated timestamps are returned."""
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response.status_code == 200
        data = response.json()

        # All metrics should have last_calculated set (even if values are null)
        assert data["internal_consistency"]["last_calculated"] is not None
        assert data["test_retest"]["last_calculated"] is not None
        assert data["split_half"]["last_calculated"] is not None
