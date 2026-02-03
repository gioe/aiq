"""Tests for shadow CAT admin endpoints (TASK-875, TASK-876).

Tests cover:
- GET /admin/shadow-cat/results (list with filtering)
- GET /admin/shadow-cat/results/{session_id} (detail)
- GET /admin/shadow-cat/statistics (aggregate metrics)
- GET /admin/shadow-cat/collection-progress (TASK-876)
- GET /admin/shadow-cat/analysis (TASK-876)
- GET /admin/shadow-cat/health (TASK-876)
- Auth requirement (401 without admin token)
"""
import pytest
from datetime import datetime, timezone

from app.core.datetime_utils import utc_now
from app.core.security import hash_password
from app.core.config import settings
from app.models.models import (
    ShadowCATResult,
    TestSession,
    TestStatus,
    User,
)
from app.models import Base

from tests.conftest import TestingSessionLocal, engine  # noqa: F401


@pytest.fixture(scope="function")
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def user(db):
    u = User(
        email="admin-shadow@test.com",
        password_hash=hash_password("testpass123"),
        first_name="Admin",
        last_name="Tester",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def shadow_results(db, user):
    """Create several shadow CAT results for testing."""
    results = []
    for i in range(5):
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
            completed_at=datetime.now(timezone.utc),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        shadow = ShadowCATResult(
            test_session_id=session.id,
            shadow_theta=0.1 * i,
            shadow_se=0.3 - (i * 0.02),
            shadow_iq=100 + (i * 3),
            items_administered=8 + i,
            administered_question_ids=list(range(8 + i)),
            stopping_reason="se_threshold" if i < 3 else "max_items",
            actual_iq=100,
            theta_iq_delta=float(i * 3),
            theta_history=[0.0 + 0.05 * j for j in range(8 + i)],
            se_history=[1.0 - 0.05 * j for j in range(8 + i)],
            domain_coverage={
                "pattern": 2,
                "logic": 2,
                "verbal": 1,
                "spatial": 1,
                "math": 1,
                "memory": 1,
            },
            executed_at=utc_now(),
            execution_time_ms=50 + i * 10,
        )
        db.add(shadow)
        results.append(shadow)

    db.commit()
    for r in results:
        db.refresh(r)
    return results


@pytest.fixture
def admin_headers():
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


class TestListShadowCATResults:
    """Tests for GET /admin/shadow-cat/results."""

    def test_list_returns_results(self, client, shadow_results, admin_headers):
        resp = client.get("/v1/admin/shadow-cat/results", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 5
        assert len(data["results"]) == 5
        assert data["limit"] == 50
        assert data["offset"] == 0

    def test_list_pagination(self, client, shadow_results, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/results?limit=2&offset=0",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) == 2
        assert data["total_count"] == 5

    def test_list_filter_by_min_delta(self, client, shadow_results, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/results?min_delta=6",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        # deltas are 0, 3, 6, 9, 12 — those >= 6 are 6, 9, 12
        assert data["total_count"] == 3

    def test_list_filter_by_stopping_reason(
        self, client, shadow_results, admin_headers
    ):
        resp = client.get(
            "/v1/admin/shadow-cat/results?stopping_reason=max_items",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 2

    def test_list_empty(self, client, admin_headers):
        resp = client.get("/v1/admin/shadow-cat/results", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 0
        assert data["results"] == []

    def test_requires_auth(self, client, shadow_results):
        resp = client.get("/v1/admin/shadow-cat/results")
        assert resp.status_code == 422  # Missing required header


class TestGetShadowCATResult:
    """Tests for GET /admin/shadow-cat/results/{session_id}."""

    def test_get_detail(self, client, shadow_results, admin_headers):
        session_id = shadow_results[0].test_session_id
        resp = client.get(
            f"/v1/admin/shadow-cat/results/{session_id}",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["test_session_id"] == session_id
        assert "theta_history" in data
        assert "se_history" in data
        assert "domain_coverage" in data
        assert "administered_question_ids" in data

    def test_not_found(self, client, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/results/99999",
            headers=admin_headers,
        )
        assert resp.status_code == 404


class TestShadowCATStatistics:
    """Tests for GET /admin/shadow-cat/statistics."""

    def test_statistics_with_data(self, client, shadow_results, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/statistics",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_shadow_tests"] == 5
        assert data["mean_delta"] is not None
        assert data["median_delta"] is not None
        assert data["std_delta"] is not None
        assert data["min_delta"] is not None
        assert data["max_delta"] is not None
        assert data["mean_items_administered"] is not None
        assert data["mean_shadow_se"] is not None
        assert "se_threshold" in data["stopping_reason_distribution"]
        assert "max_items" in data["stopping_reason_distribution"]
        assert data["stopping_reason_distribution"]["se_threshold"] == 3
        assert data["stopping_reason_distribution"]["max_items"] == 2

    def test_statistics_empty(self, client, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/statistics",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_shadow_tests"] == 0
        assert data["stopping_reason_distribution"] == {}


class TestCollectionProgress:
    """Tests for GET /admin/shadow-cat/collection-progress (TASK-876)."""

    def test_progress_with_data(self, client, shadow_results, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/collection-progress",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 5
        assert data["milestone_target"] == 100
        assert data["milestone_reached"] is False
        assert data["first_result_at"] is not None
        assert data["latest_result_at"] is not None

    def test_progress_empty(self, client, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/collection-progress",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["milestone_reached"] is False
        assert data["first_result_at"] is None
        assert data["latest_result_at"] is None

    def test_requires_auth(self, client, shadow_results):
        resp = client.get("/v1/admin/shadow-cat/collection-progress")
        assert resp.status_code == 422


class TestShadowCATAnalysis:
    """Tests for GET /admin/shadow-cat/analysis (TASK-876)."""

    def test_analysis_with_data(self, client, shadow_results, admin_headers):
        # Fixture data: thetas=[0.0, 0.1, 0.2, 0.3, 0.4], SEs=[0.30, 0.28, 0.26, 0.24, 0.22]
        # shadow_iqs=[100,103,106,109,112], actual_iqs=all 100, deltas=[0,3,6,9,12]
        # items=[8,9,10,11,12], exec_times=[50,60,70,80,90]
        resp = client.get(
            "/v1/admin/shadow-cat/analysis",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_sessions"] == 5

        # Theta statistics: mean([0.0,0.1,0.2,0.3,0.4]) = 0.2
        assert data["mean_theta"] == pytest.approx(0.2, abs=0.001)
        assert data["median_theta"] == pytest.approx(0.2, abs=0.001)
        assert data["std_theta"] is not None

        # SE statistics: mean([0.30,0.28,0.26,0.24,0.22]) = 0.26
        assert data["mean_se"] == pytest.approx(0.26, abs=0.001)
        assert data["median_se"] == pytest.approx(0.26, abs=0.001)

        # Pearson r is None: actual_iq is constant (100), zero variance
        assert data["pearson_r"] is None

        # Delta statistics: mean([0,3,6,9,12]) = 6.0
        assert data["mean_delta"] == pytest.approx(6.0, abs=0.01)
        assert data["median_delta"] == pytest.approx(6.0, abs=0.01)
        assert data["std_delta"] is not None

        # Bland-Altman: mean_difference = 6.0, LOA symmetric around it
        assert data["bland_altman"]["mean_difference"] == pytest.approx(6.0, abs=0.01)
        assert data["bland_altman"]["upper_limit_of_agreement"] > 6.0
        assert data["bland_altman"]["lower_limit_of_agreement"] < 6.0

        # Items: mean([8,9,10,11,12]) = 10.0
        assert data["mean_items_administered"] == pytest.approx(10.0, abs=0.1)

        # Stopping reasons
        assert data["stopping_reason_distribution"]["se_threshold"] == 3
        assert data["stopping_reason_distribution"]["max_items"] == 2

        # Domain coverage (all sessions have same coverage: pattern=2, logic=2, etc.)
        assert data["mean_domain_coverage"] is not None
        assert data["mean_domain_coverage"]["pattern"] == pytest.approx(2.0, abs=0.1)
        assert data["mean_domain_coverage"]["logic"] == pytest.approx(2.0, abs=0.1)

        # Execution time: mean([50,60,70,80,90]) = 70.0
        assert data["mean_execution_time_ms"] == pytest.approx(70.0, abs=0.1)

    def test_analysis_empty(self, client, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/analysis",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["mean_theta"] is None
        assert data["pearson_r"] is None
        assert data["stopping_reason_distribution"] == {}

    def test_analysis_single_result(self, db, client, admin_headers):
        """Verify analysis handles single result: no stdev, no correlation, no Bland-Altman."""
        user_obj = User(
            email="single-analysis@test.com",
            password_hash=hash_password("testpass123"),
            first_name="Single",
            last_name="Tester",
        )
        db.add(user_obj)
        db.commit()
        db.refresh(user_obj)

        session = TestSession(
            user_id=user_obj.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
            completed_at=utc_now(),
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        shadow = ShadowCATResult(
            test_session_id=session.id,
            shadow_theta=0.5,
            shadow_se=0.28,
            shadow_iq=108,
            items_administered=10,
            administered_question_ids=list(range(10)),
            stopping_reason="se_threshold",
            actual_iq=105,
            theta_iq_delta=3.0,
            executed_at=utc_now(),
            execution_time_ms=80,
        )
        db.add(shadow)
        db.commit()

        resp = client.get("/v1/admin/shadow-cat/analysis", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_sessions"] == 1
        assert data["mean_theta"] == pytest.approx(0.5, abs=0.001)
        assert data["std_theta"] is None  # n < 2
        assert data["pearson_r"] is None  # n < 2
        assert data["bland_altman"]["mean_difference"] is None  # n < 2

    def test_requires_auth(self, client, shadow_results):
        resp = client.get("/v1/admin/shadow-cat/analysis")
        assert resp.status_code == 422


class TestShadowCATAnalysisCorrelation:
    """Test Pearson correlation with varying actual_iq values."""

    def test_correlation_with_varying_iqs(self, db, client, admin_headers):
        """Create results where shadow_iq and actual_iq both vary to get a valid r."""
        user_obj = User(
            email="corr-test@test.com",
            password_hash=hash_password("testpass123"),
            first_name="Corr",
            last_name="Tester",
        )
        db.add(user_obj)
        db.commit()
        db.refresh(user_obj)

        # Create pairs with known correlation: shadow_iq tracks actual_iq linearly
        pairs = [
            (90, 88),
            (100, 98),
            (110, 112),
            (120, 118),
            (130, 132),
        ]
        for actual, shadow in pairs:
            session = TestSession(
                user_id=user_obj.id,
                status=TestStatus.COMPLETED,
                is_adaptive=False,
                completed_at=utc_now(),
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            theta = (shadow - 100) / 15.0
            result = ShadowCATResult(
                test_session_id=session.id,
                shadow_theta=theta,
                shadow_se=0.25,
                shadow_iq=shadow,
                items_administered=10,
                administered_question_ids=list(range(10)),
                stopping_reason="se_threshold",
                actual_iq=actual,
                theta_iq_delta=float(shadow - actual),
                executed_at=utc_now(),
                execution_time_ms=100,
            )
            db.add(result)
        db.commit()

        resp = client.get(
            "/v1/admin/shadow-cat/analysis",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_sessions"] == 5
        assert data["pearson_r"] is not None
        # For pairs [(90,88),(100,98),(110,112),(120,118),(130,132)], r ≈ 0.9946
        assert data["pearson_r"] == pytest.approx(0.9946, abs=0.001)
        assert data["pearson_r_squared"] is not None
        assert data["pearson_r_squared"] == pytest.approx(0.9892, abs=0.002)


class TestShadowCATHealth:
    """Tests for GET /admin/shadow-cat/health (TASK-876)."""

    def test_health_with_data(self, client, shadow_results, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/health",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        # We have 5 completed fixed-form sessions, each with a shadow result
        assert data["total_fixed_form_sessions"] == 5
        assert data["total_shadow_results"] == 5
        assert data["coverage_rate"] == pytest.approx(1.0)

        # Execution times: [50, 60, 70, 80, 90] ms
        assert data["mean_execution_time_ms"] == pytest.approx(70.0, abs=0.1)
        assert data["p50_execution_time_ms"] == pytest.approx(70.0, abs=0.1)
        assert data["p95_execution_time_ms"] == pytest.approx(88.0, abs=2.0)
        assert data["p99_execution_time_ms"] == pytest.approx(89.6, abs=2.0)

        # Recent activity (all created just now, within 7 days)
        assert data["sessions_last_7d"] == 5
        assert data["shadow_results_last_7d"] == 5
        assert data["coverage_rate_last_7d"] == pytest.approx(1.0)

        assert data["sessions_without_shadow"] == 0

    def test_health_empty(self, client, admin_headers):
        resp = client.get(
            "/v1/admin/shadow-cat/health",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_fixed_form_sessions"] == 0
        assert data["total_shadow_results"] == 0
        assert data["coverage_rate"] is None
        assert data["sessions_without_shadow"] == 0

    def test_health_with_missing_shadow(self, db, client, admin_headers):
        """Test health reporting when some sessions lack shadow results."""
        user_obj = User(
            email="health-test@test.com",
            password_hash=hash_password("testpass123"),
            first_name="Health",
            last_name="Tester",
        )
        db.add(user_obj)
        db.commit()
        db.refresh(user_obj)

        # Create 3 completed fixed-form sessions, but only 1 with shadow result
        for i in range(3):
            session = TestSession(
                user_id=user_obj.id,
                status=TestStatus.COMPLETED,
                is_adaptive=False,
                completed_at=utc_now(),
            )
            db.add(session)
            db.commit()
            db.refresh(session)

            if i == 0:
                shadow = ShadowCATResult(
                    test_session_id=session.id,
                    shadow_theta=0.5,
                    shadow_se=0.28,
                    shadow_iq=108,
                    items_administered=10,
                    administered_question_ids=list(range(10)),
                    stopping_reason="se_threshold",
                    actual_iq=105,
                    theta_iq_delta=3.0,
                    executed_at=utc_now(),
                    execution_time_ms=75,
                )
                db.add(shadow)
        db.commit()

        resp = client.get(
            "/v1/admin/shadow-cat/health",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_fixed_form_sessions"] == 3
        assert data["total_shadow_results"] == 1
        assert data["sessions_without_shadow"] == 2
        assert data["coverage_rate"] is not None
        assert data["coverage_rate"] == pytest.approx(0.3333, abs=0.01)

    def test_requires_auth(self, client, shadow_results):
        resp = client.get("/v1/admin/shadow-cat/health")
        assert resp.status_code == 422
