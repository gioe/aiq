"""Integration tests for shadow CAT validation endpoint (TASK-877).

Tests cover:
- GET /admin/shadow-cat/validation with data passing all criteria
- GET /admin/shadow-cat/validation with no data
- GET /admin/shadow-cat/validation with data failing criteria
- Auth requirement (422 without admin token)
"""

import random

import pytest
import pytest_asyncio

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.core.security import hash_password
from app.models import Base
from app.models.models import (
    ShadowCATResult,
    TestSession,
    TestStatus,
    User,
)

from tests.conftest import TestingSessionLocal, engine  # noqa: F401


@pytest_asyncio.fixture(scope="function")
async def db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def user(db):
    u = User(
        email="validation-test@test.com",
        password_hash=hash_password("testpass123"),
        first_name="Validation",
        last_name="Tester",
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


@pytest.fixture
def admin_headers():
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


async def _create_passing_shadow_results(db, user, n=30):
    """Create n shadow CAT results that should pass all validation criteria."""
    rng = random.Random(42)
    results = []

    for i in range(n):
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            is_adaptive=False,
            completed_at=utc_now(),
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)

        actual_iq = 80 + int(i * (60 / n))
        noise = rng.gauss(0, 2)
        shadow_iq_val = int(round(actual_iq + noise))
        theta = (shadow_iq_val - 100) / 15.0
        se = round(rng.uniform(0.20, 0.29), 3)
        items = rng.choice([9, 10, 10, 11, 11, 12])

        shadow = ShadowCATResult(
            test_session_id=session.id,
            shadow_theta=theta,
            shadow_se=se,
            shadow_iq=shadow_iq_val,
            items_administered=items,
            administered_question_ids=list(range(items)),
            stopping_reason="se_threshold",
            actual_iq=actual_iq,
            theta_iq_delta=float(shadow_iq_val - actual_iq),
            domain_coverage={
                "pattern": 2,
                "logic": 2,
                "spatial": 1,
                "math": 2,
                "verbal": 2,
                "memory": 1,
            },
            executed_at=utc_now(),
            execution_time_ms=rng.randint(40, 100),
        )
        db.add(shadow)
        results.append(shadow)

    await db.commit()
    for r in results:
        await db.refresh(r)
    return results


class TestShadowCATValidation:
    """Tests for GET /admin/shadow-cat/validation (TASK-877)."""

    async def test_validation_with_passing_data(self, db, client, user, admin_headers):
        await _create_passing_shadow_results(db, user, n=30)

        resp = await client.get(
            "/v1/admin/shadow-cat/validation",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_sessions"] == 30
        assert data["recommendation"] in ("PROCEED_TO_PHASE_4", "ITERATE")

        # Structure checks
        assert "pearson_r" in data
        assert "pearson_r_ci_lower" in data
        assert "pearson_r_ci_upper" in data
        assert "pearson_r_squared" in data
        assert "criterion_1_pass" in data

        assert "mean_bias" in data
        assert "std_actual_iq" in data
        assert "bias_ratio" in data
        assert "criterion_2_pass" in data

        assert "content_violations_count" in data
        assert "content_violation_rate" in data
        assert "criterion_3_pass" in data

        assert "median_test_length" in data
        assert "criterion_4_pass" in data

        assert "bland_altman_mean" in data
        assert "bland_altman_sd" in data
        assert "loa_lower" in data
        assert "loa_upper" in data

        assert "rmse" in data
        assert "mae" in data

        assert "mean_items_administered" in data
        assert "se_convergence_rate" in data
        assert "stopping_reason_distribution" in data

        assert "quintile_analysis" in data
        assert "mean_domain_coverage" in data
        assert "criteria_results" in data
        assert "all_criteria_pass" in data
        assert "notes" in data

    async def test_validation_criteria_results_structure(
        self, db, client, user, admin_headers
    ):
        await _create_passing_shadow_results(db, user, n=30)

        resp = await client.get(
            "/v1/admin/shadow-cat/validation",
            headers=admin_headers,
        )
        data = resp.json()

        assert len(data["criteria_results"]) == 4
        for cr in data["criteria_results"]:
            assert "criterion" in cr
            assert "description" in cr
            assert "threshold" in cr
            assert "observed_value" in cr
            assert "passed" in cr

    async def test_validation_empty(self, client, admin_headers):
        resp = await client.get(
            "/v1/admin/shadow-cat/validation",
            headers=admin_headers,
        )
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_sessions"] == 0
        assert data["all_criteria_pass"] is False
        assert data["recommendation"] == "ITERATE"

    async def test_validation_content_violations(self, db, client, user, admin_headers):
        """Create results where some sessions have missing domains."""
        rng = random.Random(99)

        for i in range(20):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                is_adaptive=False,
                completed_at=utc_now(),
            )
            db.add(session)
            await db.commit()
            await db.refresh(session)

            actual_iq = 90 + i * 2
            shadow_iq_val = actual_iq + rng.randint(-2, 2)

            # 4 out of 20 sessions missing domains (20% violation rate)
            if i < 4:
                domain_cov = {
                    "pattern": 3,
                    "logic": 3,
                    "spatial": 2,
                    "math": 2,
                }  # Missing verbal and memory
            else:
                domain_cov = {
                    "pattern": 2,
                    "logic": 2,
                    "spatial": 1,
                    "math": 2,
                    "verbal": 2,
                    "memory": 1,
                }

            shadow = ShadowCATResult(
                test_session_id=session.id,
                shadow_theta=(shadow_iq_val - 100) / 15.0,
                shadow_se=0.25,
                shadow_iq=shadow_iq_val,
                items_administered=10,
                administered_question_ids=list(range(10)),
                stopping_reason="se_threshold",
                actual_iq=actual_iq,
                theta_iq_delta=float(shadow_iq_val - actual_iq),
                domain_coverage=domain_cov,
                executed_at=utc_now(),
            )
            db.add(shadow)
        await db.commit()

        resp = await client.get(
            "/v1/admin/shadow-cat/validation",
            headers=admin_headers,
        )
        data = resp.json()
        assert data["content_violations_count"] == 4
        assert data["content_violation_rate"] == pytest.approx(0.2, abs=0.01)
        assert data["criterion_3_pass"] is False

    async def test_validation_quintile_analysis(self, db, client, user, admin_headers):
        await _create_passing_shadow_results(db, user, n=30)

        resp = await client.get(
            "/v1/admin/shadow-cat/validation",
            headers=admin_headers,
        )
        data = resp.json()

        quintiles = data["quintile_analysis"]
        assert len(quintiles) > 0
        for q in quintiles:
            assert "quintile_label" in q
            assert "n" in q
            assert "mean_actual_iq" in q
            assert "mean_shadow_iq" in q
            assert "mean_bias" in q
            assert "rmse" in q

    async def test_validation_test_length_distribution(
        self, db, client, user, admin_headers
    ):
        await _create_passing_shadow_results(db, user, n=30)

        resp = await client.get(
            "/v1/admin/shadow-cat/validation",
            headers=admin_headers,
        )
        data = resp.json()

        assert data["test_length_p25"] is not None
        assert data["test_length_p75"] is not None
        assert data["test_length_min"] is not None
        assert data["test_length_max"] is not None
        assert data["test_length_min"] <= data["median_test_length"]
        assert data["test_length_max"] >= data["median_test_length"]

    async def test_requires_auth(self, client):
        resp = await client.get("/v1/admin/shadow-cat/validation")
        assert resp.status_code == 422
