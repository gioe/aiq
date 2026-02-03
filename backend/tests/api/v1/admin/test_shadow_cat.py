"""Tests for shadow CAT admin endpoints (TASK-875).

Tests cover:
- GET /admin/shadow-cat/results (list with filtering)
- GET /admin/shadow-cat/results/{session_id} (detail)
- GET /admin/shadow-cat/statistics (aggregate metrics)
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

from tests.conftest import TestingSessionLocal, engine


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
