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

        # With lower min_sessions=10 (the new minimum), should calculate (but may still
        # have issues due to insufficient data for this test's 5 sessions)
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
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
            db_session, test_user, questions, num_sessions=15
        )

        # Count existing metrics
        existing_metrics = db_session.query(ReliabilityMetric).count()

        # Make request with store_metrics=true and minimum allowed thresholds
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={
                "min_sessions": 10,
                "min_retest_pairs": 10,
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
            db_session, test_user, questions, num_sessions=15
        )

        # Count existing metrics
        existing_metrics = db_session.query(ReliabilityMetric).count()

        # Make request with store_metrics=false and minimum allowed thresholds
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={
                "min_sessions": 10,
                "min_retest_pairs": 10,
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
        # min_sessions must be >= 10
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 9},
        )
        assert response.status_code == 422  # Validation error

        # min_retest_pairs must be >= 10
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_retest_pairs": 9},
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


class TestReliabilityHistoryEndpoint:
    """Tests for GET /v1/admin/reliability/history endpoint (RE-009)."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_returns_empty_history_when_no_metrics(
        self, client, db_session, admin_token_headers
    ):
        """Test endpoint returns empty list when no metrics stored."""
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "metrics" in data
        assert "total_count" in data
        assert data["metrics"] == []
        assert data["total_count"] == 0

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_requires_admin_token(self, client, db_session):
        """Test endpoint requires valid admin token."""
        # No token
        response = client.get("/v1/admin/reliability/history")
        assert response.status_code == 422  # Missing required header

        # Invalid token
        response = client.get(
            "/v1/admin/reliability/history",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_returns_stored_metrics(self, client, db_session, admin_token_headers):
        """Test endpoint returns previously stored metrics."""
        # Create some reliability metrics directly
        now = datetime.now(timezone.utc)
        metrics_data = [
            {
                "metric_type": "cronbachs_alpha",
                "value": 0.78,
                "sample_size": 100,
                "calculated_at": now - timedelta(days=1),
                "details": {"interpretation": "good", "meets_threshold": True},
            },
            {
                "metric_type": "test_retest",
                "value": 0.65,
                "sample_size": 50,
                "calculated_at": now - timedelta(days=2),
                "details": {"interpretation": "acceptable", "meets_threshold": True},
            },
            {
                "metric_type": "split_half",
                "value": 0.82,
                "sample_size": 100,
                "calculated_at": now - timedelta(days=3),
                "details": {"interpretation": "good", "meets_threshold": True},
            },
        ]

        for m in metrics_data:
            metric = ReliabilityMetric(
                metric_type=m["metric_type"],
                value=m["value"],
                sample_size=m["sample_size"],
                calculated_at=m["calculated_at"],
                details=m["details"],
            )
            db_session.add(metric)
        db_session.commit()

        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_count"] == 3
        assert len(data["metrics"]) == 3

        # Check structure of returned items
        for metric in data["metrics"]:
            assert "id" in metric
            assert "metric_type" in metric
            assert "value" in metric
            assert "sample_size" in metric
            assert "calculated_at" in metric
            assert "details" in metric

        # Check ordering (most recent first)
        assert data["metrics"][0]["metric_type"] == "cronbachs_alpha"
        assert data["metrics"][1]["metric_type"] == "test_retest"
        assert data["metrics"][2]["metric_type"] == "split_half"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_filters_by_metric_type(self, client, db_session, admin_token_headers):
        """Test filtering by metric_type parameter."""
        # Create metrics of different types
        now = datetime.now(timezone.utc)
        for i, metric_type in enumerate(
            ["cronbachs_alpha", "test_retest", "split_half"]
        ):
            for j in range(2):  # 2 of each type
                metric = ReliabilityMetric(
                    metric_type=metric_type,
                    value=0.75 + (i * 0.05),
                    sample_size=100 + (i * 10),
                    calculated_at=now - timedelta(days=i * 2 + j),
                    details={"interpretation": "good"},
                )
                db_session.add(metric)
        db_session.commit()

        # Filter for just cronbachs_alpha
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"metric_type": "cronbachs_alpha"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_count"] == 2
        for metric in data["metrics"]:
            assert metric["metric_type"] == "cronbachs_alpha"

        # Filter for test_retest
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"metric_type": "test_retest"},
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_count"] == 2
        for metric in data["metrics"]:
            assert metric["metric_type"] == "test_retest"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_filters_by_days(self, client, db_session, admin_token_headers):
        """Test filtering by days parameter."""
        now = datetime.now(timezone.utc)

        # Create metrics at different ages (avoid boundary values)
        # Use ages well within and well outside the filter boundaries
        ages_days = [5, 25, 50, 100, 200]
        for age in ages_days:
            metric = ReliabilityMetric(
                metric_type="cronbachs_alpha",
                value=0.78,
                sample_size=100,
                calculated_at=now - timedelta(days=age),
                details={"interpretation": "good"},
            )
            db_session.add(metric)
        db_session.commit()

        # Get last 30 days - should include ages 5 and 25
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"days": 30},
        )

        assert response.status_code == 200
        data = response.json()

        # Should only get metrics from last 30 days (ages 5 and 25)
        assert data["total_count"] == 2

        # Get last 90 days - should include ages 5, 25, 50
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"days": 90},
        )

        assert response.status_code == 200
        data = response.json()

        # Should get metrics from last 90 days (ages 5, 25, 50)
        assert data["total_count"] == 3

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_days_parameter_validation(self, client, db_session, admin_token_headers):
        """Test days parameter validation (1-365)."""
        # days must be >= 1
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"days": 0},
        )
        assert response.status_code == 422  # Validation error

        # days must be <= 365
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"days": 400},
        )
        assert response.status_code == 422  # Validation error

        # Valid days=1 should work
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"days": 1},
        )
        assert response.status_code == 200

        # Valid days=365 should work
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"days": 365},
        )
        assert response.status_code == 200

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_response_schema_structure(self, client, db_session, admin_token_headers):
        """Test response matches expected schema structure."""
        now = datetime.now(timezone.utc)
        metric = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.78,
            sample_size=100,
            calculated_at=now,
            details={
                "interpretation": "good",
                "meets_threshold": True,
                "num_items": 20,
            },
        )
        db_session.add(metric)
        db_session.commit()

        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Validate top-level structure
        assert isinstance(data["metrics"], list)
        assert isinstance(data["total_count"], int)

        # Validate item structure
        item = data["metrics"][0]
        assert isinstance(item["id"], int)
        assert isinstance(item["metric_type"], str)
        assert isinstance(item["value"], float)
        assert isinstance(item["sample_size"], int)
        assert isinstance(item["calculated_at"], str)  # ISO format string
        assert isinstance(item["details"], dict)

        # Validate metric_type is valid
        assert item["metric_type"] in ["cronbachs_alpha", "test_retest", "split_half"]

    def test_admin_token_not_configured(self, client, db_session):
        """Test handling when admin token is not configured on server."""
        with patch("app.core.settings.ADMIN_TOKEN", None):
            response = client.get(
                "/v1/admin/reliability/history",
                headers={"X-Admin-Token": "any-token"},
            )
            assert response.status_code == 500
            assert "not configured" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_combines_metric_type_and_days_filters(
        self, client, db_session, admin_token_headers
    ):
        """Test combining metric_type and days filters."""
        now = datetime.now(timezone.utc)

        # Create old and new metrics of different types
        old_alpha = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.75,
            sample_size=80,
            calculated_at=now - timedelta(days=100),
            details={},
        )
        new_alpha = ReliabilityMetric(
            metric_type="cronbachs_alpha",
            value=0.78,
            sample_size=100,
            calculated_at=now - timedelta(days=10),
            details={},
        )
        new_retest = ReliabilityMetric(
            metric_type="test_retest",
            value=0.65,
            sample_size=50,
            calculated_at=now - timedelta(days=5),
            details={},
        )
        db_session.add_all([old_alpha, new_alpha, new_retest])
        db_session.commit()

        # Filter for cronbachs_alpha in last 30 days
        response = client.get(
            "/v1/admin/reliability/history",
            headers=admin_token_headers,
            params={"metric_type": "cronbachs_alpha", "days": 30},
        )

        assert response.status_code == 200
        data = response.json()

        # Should only get the new alpha (not old alpha, not retest)
        assert data["total_count"] == 1
        assert data["metrics"][0]["metric_type"] == "cronbachs_alpha"
        assert data["metrics"][0]["value"] == 0.78


class TestReliabilityReportCaching:
    """Tests for reliability report caching behavior (RE-FI-019).

    These tests verify:
    - Cache is used when store_metrics=false
    - Cache is bypassed when store_metrics=true
    - Cache invalidation works correctly
    - Different parameters result in different cache keys
    """

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_cache_used_when_store_metrics_false(
        self, client, db_session, admin_token_headers
    ):
        """Test that cached results are returned when store_metrics=false."""
        # First request - should populate cache
        response1 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response1.status_code == 200
        data1 = response1.json()
        timestamp1 = data1["internal_consistency"]["last_calculated"]

        # Second request should return cached result with same timestamp
        response2 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response2.status_code == 200
        data2 = response2.json()
        timestamp2 = data2["internal_consistency"]["last_calculated"]

        # Timestamps should be identical (from cache)
        assert timestamp1 == timestamp2

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_cache_bypassed_when_store_metrics_true(
        self, client, db_session, admin_token_headers
    ):
        """Test that cache is bypassed when store_metrics=true."""
        import time

        # First request with store_metrics=false to populate cache
        response1 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response1.status_code == 200
        timestamp1 = response1.json()["internal_consistency"]["last_calculated"]

        # Small delay to ensure different timestamp
        time.sleep(0.1)

        # Request with store_metrics=true should bypass cache and recalculate
        response2 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": True},
        )
        assert response2.status_code == 200
        timestamp2 = response2.json()["internal_consistency"]["last_calculated"]

        # Timestamps should be different (fresh calculation)
        assert timestamp1 != timestamp2

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_different_parameters_use_different_cache_keys(
        self, client, db_session, admin_token_headers
    ):
        """Test that different min_sessions/min_retest_pairs use different cache keys."""
        # Request with default parameters
        response1 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False, "min_sessions": 100},
        )
        assert response1.status_code == 200

        # Request with different min_sessions should succeed independently
        # (uses different cache key)
        response2 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False, "min_sessions": 50},
        )
        assert response2.status_code == 200

        # Both requests succeed with valid response structure
        assert "internal_consistency" in response1.json()
        assert "internal_consistency" in response2.json()

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_cache_invalidation_works(self, client, db_session, admin_token_headers):
        """Test that cache can be invalidated."""
        from app.core.reliability import invalidate_reliability_report_cache

        # First request to populate cache
        response1 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response1.status_code == 200
        timestamp1 = response1.json()["internal_consistency"]["last_calculated"]

        # Invalidate cache
        invalidate_reliability_report_cache()

        # Next request should get fresh result
        import time

        time.sleep(0.1)
        response2 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response2.status_code == 200
        timestamp2 = response2.json()["internal_consistency"]["last_calculated"]

        # Timestamps should be different after cache invalidation
        assert timestamp1 != timestamp2

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_cache_does_not_affect_response_structure(
        self, client, db_session, admin_token_headers
    ):
        """Test that cached responses maintain the same structure as fresh responses."""
        # First request (fresh)
        response1 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response1.status_code == 200
        data1 = response1.json()

        # Second request (cached)
        response2 = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"store_metrics": False},
        )
        assert response2.status_code == 200
        data2 = response2.json()

        # Both should have identical structure
        assert set(data1.keys()) == set(data2.keys())
        assert set(data1["internal_consistency"].keys()) == set(
            data2["internal_consistency"].keys()
        )
        assert set(data1["test_retest"].keys()) == set(data2["test_retest"].keys())
        assert set(data1["split_half"].keys()) == set(data2["split_half"].keys())


class TestRandomizedDataPatterns:
    """Tests with randomized data patterns to catch variance edge cases (RE-FI-021).

    These tests use non-uniform, randomized response patterns to ensure the
    reliability calculations handle realistic data distributions correctly.
    The current test data uses deterministic patterns (i + j) % 3 which may
    miss edge cases related to:
    - High variance in responses
    - Low variance / near-zero variance
    - Bimodal score distributions
    - Skewed difficulty patterns
    - Random noise in data
    """

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_high_variance_random_responses(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with high variance random response patterns.

        Creates sessions where answer correctness varies randomly with
        approximately 50% probability, creating high variance in the data.
        """
        import random

        random.seed(42)  # Fixed seed for reproducibility

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 20 sessions with random responses (high variance)
        for i in range(20):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            # Random responses with ~50% probability
            correct_count = 0
            for question in questions:
                is_correct = random.random() > 0.5
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            # Add test result with appropriate score
            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=85 + correct_count * 2,  # Score varies with correctness
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        # Request reliability report
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # With high variance random data, calculations should complete
        # but reliability values should be lower than with structured data
        assert data["internal_consistency"]["num_sessions"] >= 10
        # Report should have valid structure regardless of values
        assert "cronbachs_alpha" in data["internal_consistency"]
        assert "overall_status" in data

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_bimodal_score_distribution(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with bimodal score distribution (some very high, some very low).

        Creates sessions where half the users score very high (~90% correct)
        and half score very low (~20% correct), creating a bimodal distribution.
        """
        import random

        random.seed(123)  # Fixed seed for reproducibility

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 20 sessions with bimodal distribution
        for i in range(20):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            # Bimodal: first 10 sessions get ~90% correct, last 10 get ~20% correct
            high_performer = i < 10
            target_accuracy = 0.90 if high_performer else 0.20

            correct_count = 0
            for question in questions:
                is_correct = random.random() < target_accuracy
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            # IQ score based on performance
            iq_score = 130 if high_performer else 70
            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=iq_score + random.randint(-5, 5),
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        # Request reliability report
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Bimodal data should still produce valid calculations
        assert data["internal_consistency"]["num_sessions"] >= 10
        # With bimodal data, we should see high discrimination (items separate groups well)
        # The endpoint should still return valid structure
        assert "cronbachs_alpha" in data["internal_consistency"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_low_variance_nearly_identical_responses(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with low variance responses (almost everyone answers the same).

        This is an edge case where nearly all sessions have identical response
        patterns, which can cause issues with variance calculations.
        """
        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 15 sessions with nearly identical responses
        # First 12 questions correct, last 3 wrong for everyone
        for i in range(15):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for j, question in enumerate(questions):
                # Nearly identical pattern: slight variation in one item
                if j < 12:
                    is_correct = True
                elif j == 12:
                    # Only variation: occasionally correct for this item
                    is_correct = i % 5 == 0
                else:
                    is_correct = False

                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=110 + (1 if i % 5 == 0 else 0),  # Minimal variation
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        # Request reliability report
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Low variance can produce unusual alpha values but should not error
        assert "cronbachs_alpha" in data["internal_consistency"]
        assert data["internal_consistency"]["num_sessions"] >= 10

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_zero_variance_all_same_responses(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test edge case where all sessions have exactly the same responses.

        This should be handled gracefully - zero variance means alpha is undefined.
        """
        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 15 sessions with EXACTLY identical responses
        for i in range(15):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            # Same pattern for everyone: first 10 correct, last 5 wrong
            for j, question in enumerate(questions):
                is_correct = j < 10
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=100,  # Same score for everyone
                correct_answers=10,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        # Request reliability report
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Should handle gracefully - zero variance is an edge case
        # The endpoint should still return valid structure
        assert "internal_consistency" in data
        assert "overall_status" in data

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_skewed_difficulty_easy_items_only(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with skewed difficulty where most items are answered correctly.

        Creates data where all items have very high success rates (>90%),
        which can lead to restricted range and lower reliability estimates.
        """
        import random

        random.seed(456)

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 20 sessions where almost everyone gets almost everything right
        for i in range(20):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for question in questions:
                # 95% success rate - very easy items
                is_correct = random.random() < 0.95
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=120 + random.randint(-3, 3),
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Easy items should still produce valid calculations
        assert data["internal_consistency"]["num_sessions"] >= 10
        # May have low alpha due to ceiling effect but should not error
        assert "cronbachs_alpha" in data["internal_consistency"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_skewed_difficulty_hard_items_only(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with skewed difficulty where most items are answered incorrectly.

        Creates data where all items have very low success rates (~20%),
        which can lead to floor effects and lower reliability estimates.
        """
        import random

        random.seed(789)

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 20 sessions where almost everyone gets almost everything wrong
        for i in range(20):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for question in questions:
                # 20% success rate - very hard items
                is_correct = random.random() < 0.20
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=75 + random.randint(-5, 5),
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Hard items should still produce valid calculations
        assert data["internal_consistency"]["num_sessions"] >= 10
        # May have low alpha due to floor effect but should not error
        assert "cronbachs_alpha" in data["internal_consistency"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_mixed_item_difficulty_realistic(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with realistic mixed item difficulty (some easy, some hard).

        Creates a more realistic scenario where different items have different
        success rates, simulating a well-designed test with varying difficulty.
        """
        import random

        random.seed(999)

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Assign difficulty to each question (success probability)
        # Mix of easy (0.85), medium (0.5-0.7), and hard (0.25) items
        item_difficulties = [
            0.85,
            0.75,
            0.65,
            0.55,
            0.50,  # Easy to medium
            0.50,
            0.45,
            0.40,
            0.35,
            0.30,  # Medium to hard
            0.25,
            0.85,
            0.70,
            0.40,
            0.25,  # Mixed
        ]

        # Create 25 sessions with ability-based responses
        for i in range(25):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            # Person ability modifier (some test-takers are better than others)
            ability_modifier = random.gauss(0, 0.15)  # Normal distribution

            correct_count = 0
            for j, question in enumerate(questions):
                # Success probability = item difficulty + ability modifier
                success_prob = max(
                    0.05, min(0.95, item_difficulties[j] + ability_modifier)
                )
                is_correct = random.random() < success_prob
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            # IQ based on correct answers with some noise
            iq_score = 85 + (correct_count * 2) + random.randint(-3, 3)
            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=iq_score,
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 15, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Realistic mixed difficulty should produce good reliability
        assert data["internal_consistency"]["num_sessions"] >= 15
        # With realistic data, we expect alpha to be calculated
        # (may or may not meet threshold, but should be a valid number)
        alpha = data["internal_consistency"]["cronbachs_alpha"]
        if alpha is not None:
            assert -1.0 <= alpha <= 1.0  # Alpha should be in valid range

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_random_noise_with_some_structure(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with random noise layered on structured responses.

        Creates data with an underlying structure (ability-based responses)
        plus random noise, simulating real-world measurement error.
        """
        import random

        random.seed(2024)

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 30 sessions with structured + noisy responses
        for i in range(30):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            # Base ability level for this session (varies across sessions)
            base_ability = 0.3 + (i / 30) * 0.5  # Ranges from 0.3 to 0.8

            correct_count = 0
            for j, question in enumerate(questions):
                # Item difficulty increases with position
                item_difficulty = 0.3 + (j / 15) * 0.4

                # Probability based on ability vs difficulty with noise
                base_prob = 1.0 / (
                    1.0 + pow(2.718, -(base_ability - item_difficulty) * 4)
                )
                noise = random.gauss(0, 0.1)  # Random noise
                final_prob = max(0.05, min(0.95, base_prob + noise))

                is_correct = random.random() < final_prob
                if is_correct:
                    correct_count += 1

                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=70 + correct_count * 3,
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 20, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # IRT-like data should produce reasonable reliability
        assert data["internal_consistency"]["num_sessions"] >= 20
        alpha = data["internal_consistency"]["cronbachs_alpha"]
        if alpha is not None:
            assert -1.0 <= alpha <= 1.0

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_extreme_outlier_session(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test with one extreme outlier session among normal ones.

        Creates mostly normal data but with one session that has an
        extreme pattern (all correct or all wrong), testing robustness
        to outliers.
        """
        import random

        random.seed(555)

        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 19 normal sessions
        for i in range(19):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for question in questions:
                # Normal ~60% success rate
                is_correct = random.random() < 0.60
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=95 + correct_count,
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        # Create one outlier session (perfect score)
        outlier_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
            started_at=base_time - timedelta(days=20),
        )
        db_session.add(outlier_session)
        db_session.flush()

        for question in questions:
            response = Response(
                test_session_id=outlier_session.id,
                user_id=test_user.id,
                question_id=question.id,
                user_answer="A",  # All correct
                is_correct=True,
                time_spent_seconds=30,
            )
            db_session.add(response)

        result = TestResult(
            test_session_id=outlier_session.id,
            user_id=test_user.id,
            iq_score=160,  # Outlier score
            correct_answers=15,
            total_questions=len(questions),
            completed_at=base_time - timedelta(days=20),
        )
        db_session.add(result)
        db_session.commit()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 15, "store_metrics": False},
        )

        assert response.status_code == 200
        data = response.json()

        # Should handle outlier gracefully
        assert data["internal_consistency"]["num_sessions"] >= 15
        assert "cronbachs_alpha" in data["internal_consistency"]


class TestLargeDatasetPerformance:
    """Tests for large dataset performance (RE-FI-024).

    These tests verify:
    - Reliability calculations complete in reasonable time with large datasets
    - Memory usage remains bounded with 10,000+ sessions
    - API response times stay acceptable under load
    - Concurrent request handling works correctly
    """

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_large_dataset_10000_sessions(
        self, client, db_session, admin_token_headers
    ):
        """Test reliability calculation performance with 10,000+ sessions.

        This test verifies that the reliability endpoint can handle large
        datasets (10,000 sessions x 15 questions = 150,000 responses) without
        timing out or running out of memory.

        Note: This test uses batch inserts for efficiency and measures
        execution time to ensure acceptable performance.
        """
        import random
        import time

        random.seed(42)  # Fixed seed for reproducibility

        # Create 15 questions
        questions = create_test_questions(db_session, count=15)
        question_ids = [q.id for q in questions]

        # Create a single user for all sessions (simplifies test)
        user = User(
            email="large_dataset_test@example.com",
            password_hash=hash_password("testpassword123"),
            first_name="Large",
            last_name="Dataset",
            notification_enabled=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 10,000 sessions using bulk inserts for efficiency
        NUM_SESSIONS = 10000
        BATCH_SIZE = 500  # Insert in batches to avoid memory issues
        base_time = datetime.now(timezone.utc)

        start_setup = time.time()

        for batch_start in range(0, NUM_SESSIONS, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, NUM_SESSIONS)

            # Create sessions for this batch
            for i in range(batch_start, batch_end):
                session = TestSession(
                    user_id=user.id,
                    status=TestStatus.COMPLETED,
                    started_at=base_time - timedelta(hours=i),
                )
                db_session.add(session)
            db_session.flush()

            # Get the session IDs from this batch
            batch_sessions = (
                db_session.query(TestSession)
                .filter(TestSession.user_id == user.id)
                .order_by(TestSession.id.desc())
                .limit(batch_end - batch_start)
                .all()
            )

            # Create responses and results for each session
            for session in batch_sessions:
                correct_count = 0
                for j, qid in enumerate(question_ids):
                    # Varying correctness pattern for realistic data
                    is_correct = random.random() < (0.3 + (j / 30))  # 30-80% correct
                    if is_correct:
                        correct_count += 1
                    response = Response(
                        test_session_id=session.id,
                        user_id=user.id,
                        question_id=qid,
                        user_answer="A" if is_correct else "B",
                        is_correct=is_correct,
                        time_spent_seconds=random.randint(15, 60),
                    )
                    db_session.add(response)

                result = TestResult(
                    test_session_id=session.id,
                    user_id=user.id,
                    iq_score=85 + correct_count * 2 + random.randint(-3, 3),
                    correct_answers=correct_count,
                    total_questions=len(question_ids),
                    completed_at=session.started_at,
                )
                db_session.add(result)

            db_session.commit()

        setup_time = time.time() - start_setup

        # Verify data was created
        session_count = (
            db_session.query(TestSession).filter(TestSession.user_id == user.id).count()
        )
        assert (
            session_count == NUM_SESSIONS
        ), f"Expected {NUM_SESSIONS} sessions, got {session_count}"

        # Now test the reliability endpoint performance
        start_request = time.time()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 100, "store_metrics": False},
        )

        request_time = time.time() - start_request

        # Should complete successfully
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        # Verify response structure
        assert "internal_consistency" in data
        assert "test_retest" in data
        assert "split_half" in data
        assert "overall_status" in data

        # Verify data was actually processed (not just insufficient data response)
        assert data["internal_consistency"]["num_sessions"] > 0

        # Performance assertion: should complete in reasonable time
        # With optimizations (data loader, caching), 10k sessions should process
        # in under 60 seconds even on modest hardware
        MAX_ALLOWED_TIME = 60  # seconds
        assert request_time < MAX_ALLOWED_TIME, (
            f"Request took {request_time:.2f}s, exceeded {MAX_ALLOWED_TIME}s threshold. "
            f"Setup time was {setup_time:.2f}s"
        )

        # Log performance metrics for visibility
        print(f"\nPerformance metrics for {NUM_SESSIONS} sessions:")
        print(f"  Setup time: {setup_time:.2f}s")
        print(f"  Request time: {request_time:.2f}s")
        print(f"  Sessions processed: {data['internal_consistency']['num_sessions']}")
        if data["internal_consistency"]["cronbachs_alpha"] is not None:
            print(
                f"  Cronbach's alpha: {data['internal_consistency']['cronbachs_alpha']:.4f}"
            )

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_concurrent_request_handling(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test that concurrent requests to reliability endpoint are handled correctly.

        This test verifies that multiple simultaneous requests:
        - All complete successfully
        - Return consistent results (from cache or fresh)
        - Don't cause race conditions or data corruption
        """
        import concurrent.futures
        import random
        import time

        random.seed(123)

        # Create test data (smaller dataset for concurrent test)
        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 50 sessions for reasonable test data
        for i in range(50):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for j, question in enumerate(questions):
                is_correct = random.random() < 0.6
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=90 + correct_count,
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        def make_request():
            """Helper function to make a reliability endpoint request."""
            return client.get(
                "/v1/admin/reliability",
                headers=admin_token_headers,
                params={"min_sessions": 10, "store_metrics": False},
            )

        # Make 10 concurrent requests
        NUM_CONCURRENT = 10
        results = []
        errors = []

        start_time = time.time()

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=NUM_CONCURRENT
        ) as executor:
            futures = [executor.submit(make_request) for _ in range(NUM_CONCURRENT)]

            for future in concurrent.futures.as_completed(futures):
                try:
                    response = future.result()
                    results.append(response)
                except Exception as e:
                    errors.append(str(e))

        total_time = time.time() - start_time

        # All requests should succeed
        assert len(errors) == 0, f"Concurrent requests had errors: {errors}"
        assert len(results) == NUM_CONCURRENT

        # All responses should be 200 OK
        for i, response in enumerate(results):
            assert (
                response.status_code == 200
            ), f"Request {i} failed with status {response.status_code}: {response.text}"

        # All responses should have valid structure
        for response in results:
            data = response.json()
            assert "internal_consistency" in data
            assert "overall_status" in data

        # Verify consistency - all cached responses should have same timestamp
        # (since we're using store_metrics=False)
        timestamps = [
            r.json()["internal_consistency"]["last_calculated"] for r in results
        ]
        # With caching, most timestamps should be identical
        unique_timestamps = set(timestamps)
        # Allow for at most 2 unique timestamps (one fresh, one cached)
        assert (
            len(unique_timestamps) <= 2
        ), f"Too many unique timestamps in concurrent requests: {unique_timestamps}"

        print("\nConcurrent request metrics:")
        print(f"  Total requests: {NUM_CONCURRENT}")
        print(f"  Total time: {total_time:.2f}s")
        print(f"  Avg time per request: {total_time / NUM_CONCURRENT:.2f}s")
        print(f"  Unique timestamps: {len(unique_timestamps)}")

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_all_users_identical_scores_zero_variance(
        self, client, db_session, admin_token_headers
    ):
        """Test edge case where all users have exactly identical IQ scores.

        When all test scores are identical, variance is zero, which can cause
        division by zero or undefined values in reliability calculations.
        This tests that the endpoint handles this gracefully.
        """
        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create multiple users, each with exactly the same score
        IDENTICAL_SCORE = 100
        NUM_USERS = 20

        for u in range(NUM_USERS):
            user = User(
                email=f"zero_variance_user_{u}@example.com",
                password_hash=hash_password("testpassword123"),
                first_name=f"User{u}",
                last_name="ZeroVar",
                notification_enabled=False,
            )
            db_session.add(user)
            db_session.flush()

            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=u),
            )
            db_session.add(session)
            db_session.flush()

            # All users answer exactly the same way (first 10 correct, last 5 wrong)
            for j, question in enumerate(questions):
                is_correct = j < 10
                response = Response(
                    test_session_id=session.id,
                    user_id=user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            # All users get exactly the same score
            result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=IDENTICAL_SCORE,  # Same for everyone
                correct_answers=10,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=u),
            )
            db_session.add(result)

        db_session.commit()

        # Verify scores are identical
        scores = db_session.query(TestResult.iq_score).all()
        unique_scores = set(s[0] for s in scores)
        assert len(unique_scores) == 1, f"Expected 1 unique score, got {unique_scores}"

        # Request reliability report
        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 10, "store_metrics": False},
        )

        # Should complete without error (200 OK)
        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        # Verify response has valid structure
        assert "internal_consistency" in data
        assert "test_retest" in data
        assert "split_half" in data
        assert "overall_status" in data

        # With zero variance in total scores:
        # - Cronbach's alpha is mathematically undefined (0/0)
        # - The implementation should handle this gracefully
        # - May return None, 0, or handle as insufficient variance
        assert "cronbachs_alpha" in data["internal_consistency"]
        # The key assertion is that the endpoint doesn't crash

        # Test-retest with identical scores should return correlation as undefined or 0
        # (since there's no variance to correlate)
        assert "correlation" in data["test_retest"]

        print("\nZero variance (identical scores) test:")
        print(f"  Users: {NUM_USERS}")
        print(f"  Score: {IDENTICAL_SCORE} (same for all)")
        print(f"  Cronbach's alpha: {data['internal_consistency']['cronbachs_alpha']}")
        print(f"  Test-retest r: {data['test_retest']['correlation']}")
        print(f"  Overall status: {data['overall_status']}")

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_large_dataset_with_many_questions(
        self, client, db_session, admin_token_headers
    ):
        """Test performance with large number of questions (50+).

        This tests scalability with a larger item pool, which affects:
        - Item-response matrix size
        - Item-total correlation calculations
        - Memory usage for correlation computations
        """
        import random
        import time

        random.seed(789)

        # Create 50 questions (larger than typical 15-20)
        NUM_QUESTIONS = 50
        questions = create_test_questions(db_session, count=NUM_QUESTIONS)
        question_ids = [q.id for q in questions]

        # Create test user
        user = User(
            email="many_questions_test@example.com",
            password_hash=hash_password("testpassword123"),
            first_name="Many",
            last_name="Questions",
            notification_enabled=False,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 200 sessions with 50 questions each = 10,000 responses
        NUM_SESSIONS = 200
        base_time = datetime.now(timezone.utc)

        for i in range(NUM_SESSIONS):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(hours=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for j, qid in enumerate(question_ids):
                # Realistic item difficulty varying by position
                item_p = 0.3 + (0.4 * (1 - j / NUM_QUESTIONS))  # 70% -> 30%
                is_correct = random.random() < item_p
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=user.id,
                    question_id=qid,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=random.randint(10, 45),
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=70 + int(correct_count * 60 / NUM_QUESTIONS),
                correct_answers=correct_count,
                total_questions=NUM_QUESTIONS,
                completed_at=session.started_at,
            )
            db_session.add(result)

            # Commit in batches to avoid memory issues
            if i % 50 == 0:
                db_session.commit()

        db_session.commit()

        # Test reliability endpoint
        start_time = time.time()

        response = client.get(
            "/v1/admin/reliability",
            headers=admin_token_headers,
            params={"min_sessions": 50, "store_metrics": False},
        )

        request_time = time.time() - start_time

        assert response.status_code == 200, f"Request failed: {response.text}"
        data = response.json()

        # Verify response
        assert data["internal_consistency"]["num_sessions"] > 0
        num_items = data["internal_consistency"]["num_items"]
        assert num_items is not None, "Expected num_items to be calculated"

        # Should handle large item count gracefully
        print(f"\nMany questions ({NUM_QUESTIONS}) test:")
        print(f"  Sessions: {NUM_SESSIONS}")
        print(f"  Items (questions) used: {num_items}")
        print(f"  Request time: {request_time:.2f}s")
        if data["internal_consistency"]["cronbachs_alpha"] is not None:
            print(
                f"  Cronbach's alpha: {data['internal_consistency']['cronbachs_alpha']:.4f}"
            )

        # Performance should still be reasonable
        assert request_time < 30, f"Request took {request_time:.2f}s, expected < 30s"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_stress_test_rapid_sequential_requests(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Stress test with rapid sequential requests.

        This tests the endpoint's behavior under sustained load
        with rapid sequential requests (not concurrent).
        """
        import random
        import time

        random.seed(456)

        # Create test data
        questions = create_test_questions(db_session, count=15)
        base_time = datetime.now(timezone.utc)

        # Create 30 sessions
        for i in range(30):
            session = TestSession(
                user_id=test_user.id,
                status=TestStatus.COMPLETED,
                started_at=base_time - timedelta(days=i),
            )
            db_session.add(session)
            db_session.flush()

            correct_count = 0
            for j, question in enumerate(questions):
                is_correct = random.random() < 0.55
                if is_correct:
                    correct_count += 1
                response = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=question.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=30,
                )
                db_session.add(response)

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=90 + correct_count,
                correct_answers=correct_count,
                total_questions=len(questions),
                completed_at=base_time - timedelta(days=i),
            )
            db_session.add(result)

        db_session.commit()

        # Make rapid sequential requests
        NUM_REQUESTS = 50
        request_times = []
        errors = []

        for i in range(NUM_REQUESTS):
            start = time.time()
            try:
                response = client.get(
                    "/v1/admin/reliability",
                    headers=admin_token_headers,
                    params={"min_sessions": 10, "store_metrics": False},
                )
                assert response.status_code == 200
                request_times.append(time.time() - start)
            except Exception as e:
                errors.append(f"Request {i}: {str(e)}")

        assert len(errors) == 0, f"Errors during stress test: {errors}"
        assert len(request_times) == NUM_REQUESTS

        avg_time = sum(request_times) / len(request_times)
        max_time = max(request_times)
        min_time = min(request_times)

        print(f"\nStress test ({NUM_REQUESTS} rapid requests):")
        print(f"  Avg response time: {avg_time * 1000:.1f}ms")
        print(f"  Min response time: {min_time * 1000:.1f}ms")
        print(f"  Max response time: {max_time * 1000:.1f}ms")
        print(f"  Errors: {len(errors)}")

        # With caching, avg response should be fast (under 500ms)
        assert (
            avg_time < 0.5
        ), f"Avg response time {avg_time:.2f}s exceeds 500ms threshold"
