"""
Tests for LLM benchmark admin API endpoints.

Covers POST /run, GET /results, GET /results/{session_id}, and GET /compare.
"""

import math
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from fastapi.testclient import TestClient

from app.core.config import settings
from app.models import get_db
from app.models.llm_benchmark import LLMResponse, LLMTestResult, LLMTestSession
from app.models.models import TestResult, TestSession, TestStatus
from tests.conftest import AsyncTestingSessionLocal, create_test_app


@pytest.fixture
def admin_headers():
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_session(
    db,
    *,
    vendor="openai",
    model_id="gpt-4o",
    status="completed",
    cost=0.05,
):
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    session = LLMTestSession(
        vendor=vendor,
        model_id=model_id,
        status=status,
        started_at=ts,
        completed_at=ts if status == "completed" else None,
        total_prompt_tokens=500,
        total_completion_tokens=200,
        total_cost_usd=cost,
        temperature=0.0,
        triggered_by="admin_api",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def _create_result(
    db,
    session,
    *,
    iq_score=110,
    percentile=75.0,
    total_questions=20,
    correct_answers=15,
    domain_scores=None,
):
    result = LLMTestResult(
        session_id=session.id,
        vendor=session.vendor,
        model_id=session.model_id,
        iq_score=iq_score,
        percentile_rank=percentile,
        total_questions=total_questions,
        correct_answers=correct_answers,
        domain_scores=(
            domain_scores
            if domain_scores is not None
            else {"pattern": 0.8, "logic": 0.7}
        ),
        completed_at=session.started_at,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def _create_response(db, session, question_id, *, is_correct=True):
    resp = LLMResponse(
        session_id=session.id,
        question_id=question_id,
        raw_answer="B",
        normalized_answer="B",
        is_correct=is_correct,
        prompt_tokens=100,
        completion_tokens=20,
        cost_usd=0.002,
        latency_ms=350,
        error=None,
    )
    db.add(resp)
    db.commit()
    db.refresh(resp)
    return resp


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------


class TestTriggerBenchmarkRun:
    """Tests for POST /v1/admin/llm-benchmark/run."""

    @patch("app.api.v1.admin.llm_benchmark.run_llm_benchmark", new_callable=AsyncMock)
    def test_trigger_success(self, mock_run, client, db_session, admin_headers):
        mock_run.return_value = 42

        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "openai", "model_id": "gpt-4o"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == 42
        assert data["status"] == "completed"
        assert "openai/gpt-4o" in data["message"]
        mock_run.assert_awaited_once()

    @patch("app.api.v1.admin.llm_benchmark.run_llm_benchmark", new_callable=AsyncMock)
    def test_trigger_with_question_count(
        self, mock_run, client, db_session, admin_headers
    ):
        mock_run.return_value = 7

        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "anthropic", "model_id": "claude-3", "question_count": 5},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        _, kwargs = mock_run.call_args
        assert kwargs["total_questions"] == 5

    def test_trigger_invalid_vendor(self, client, db_session, admin_headers):
        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "invalid_vendor", "model_id": "some-model"},
            headers=admin_headers,
        )

        assert resp.status_code == 400
        assert "Unknown vendor" in resp.json()["detail"]

    @patch("app.api.v1.admin.llm_benchmark.run_llm_benchmark", new_callable=AsyncMock)
    def test_trigger_with_question_ids(
        self, mock_run, client, db_session, admin_headers
    ):
        mock_run.return_value = 99

        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={
                "vendor": "openai",
                "model_id": "gpt-4o",
                "question_ids": [1, 2, 3],
            },
            headers=admin_headers,
        )

        assert resp.status_code == 200
        _, kwargs = mock_run.call_args
        assert kwargs["question_ids"] == [1, 2, 3]
        assert kwargs["total_questions"] is None

    def test_trigger_question_ids_and_count_mutually_exclusive(
        self, client, db_session, admin_headers
    ):
        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={
                "vendor": "openai",
                "model_id": "gpt-4o",
                "question_ids": [1, 2],
                "question_count": 5,
            },
            headers=admin_headers,
        )

        assert resp.status_code == 422

    def test_trigger_missing_token(self, client, db_session):
        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "openai", "model_id": "gpt-4o"},
        )

        assert resp.status_code == 422

    def test_trigger_invalid_token(self, client, db_session):
        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "openai", "model_id": "gpt-4o"},
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert resp.status_code == 401

    @patch("app.api.v1.admin.llm_benchmark.run_llm_benchmark", new_callable=AsyncMock)
    def test_trigger_runner_error(self, mock_run, db_session, admin_headers):
        mock_run.side_effect = RuntimeError("LLM API unavailable")

        test_app = create_test_app()

        async def override_get_db():
            async with AsyncTestingSessionLocal() as session:
                yield session

        test_app.dependency_overrides[get_db] = override_get_db
        with TestClient(test_app, raise_server_exceptions=False) as c:
            resp = c.post(
                "/v1/admin/llm-benchmark/run",
                json={"vendor": "openai", "model_id": "gpt-4o"},
                headers=admin_headers,
            )

        assert resp.status_code == 500


# ---------------------------------------------------------------------------
# GET /results
# ---------------------------------------------------------------------------


class TestListBenchmarkResults:
    """Tests for GET /v1/admin/llm-benchmark/results."""

    def test_list_empty(self, client, db_session, admin_headers):
        resp = client.get("/v1/admin/llm-benchmark/results", headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []
        assert data["total_count"] == 0
        assert data["has_more"] is False

    def test_list_with_data(self, client, db_session, admin_headers):
        session = _create_session(db_session)
        _create_result(db_session, session)

        resp = client.get("/v1/admin/llm-benchmark/results", headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 1
        assert len(data["results"]) == 1
        row = data["results"][0]
        assert row["vendor"] == "openai"
        assert row["model_id"] == "gpt-4o"
        assert row["iq_score"] == 110
        assert row["percentile_rank"] == pytest.approx(75.0)

    def test_filter_by_vendor(self, client, db_session, admin_headers):
        _create_session(db_session, vendor="openai", model_id="gpt-4o")
        _create_session(db_session, vendor="anthropic", model_id="claude-3")

        resp = client.get(
            "/v1/admin/llm-benchmark/results",
            params={"vendor": "anthropic"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 1
        assert data["results"][0]["vendor"] == "anthropic"

    def test_filter_by_model_id(self, client, db_session, admin_headers):
        _create_session(db_session, vendor="openai", model_id="gpt-4o")
        _create_session(db_session, vendor="openai", model_id="gpt-4o-mini")

        resp = client.get(
            "/v1/admin/llm-benchmark/results",
            params={"model_id": "gpt-4o-mini"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 1
        assert data["results"][0]["model_id"] == "gpt-4o-mini"

    def test_pagination(self, client, db_session, admin_headers):
        for i in range(5):
            _create_session(db_session, model_id=f"model-{i}")

        resp = client.get(
            "/v1/admin/llm-benchmark/results",
            params={"limit": 2, "offset": 0},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["total_count"] == 5
        assert len(data["results"]) == 2
        assert data["has_more"] is True

        resp2 = client.get(
            "/v1/admin/llm-benchmark/results",
            params={"limit": 2, "offset": 4},
            headers=admin_headers,
        )
        data2 = resp2.json()
        assert len(data2["results"]) == 1
        assert data2["has_more"] is False

    def test_list_unauthorized(self, client, db_session):
        resp = client.get(
            "/v1/admin/llm-benchmark/results",
            headers={"X-Admin-Token": "wrong"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /results/{session_id}
# ---------------------------------------------------------------------------


class TestGetBenchmarkDetail:
    """Tests for GET /v1/admin/llm-benchmark/results/{session_id}."""

    def test_detail_success(self, client, db_session, admin_headers, test_questions):
        session = _create_session(db_session)
        _create_result(db_session, session, total_questions=2, correct_answers=1)
        _create_response(db_session, session, test_questions[0].id, is_correct=True)
        _create_response(db_session, session, test_questions[1].id, is_correct=False)

        resp = client.get(
            f"/v1/admin/llm-benchmark/results/{session.id}",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == session.id
        assert data["vendor"] == "openai"
        assert data["model_id"] == "gpt-4o"
        assert data["iq_score"] == 110
        assert data["domain_scores"] == {"pattern": 0.8, "logic": 0.7}
        assert len(data["questions"]) == 2

    def test_detail_not_found(self, client, db_session, admin_headers):
        resp = client.get(
            "/v1/admin/llm-benchmark/results/99999",
            headers=admin_headers,
        )

        assert resp.status_code == 404

    def test_detail_no_result_yet(self, client, db_session, admin_headers):
        """Session exists but has no test_result (still in progress)."""
        session = _create_session(db_session, status="in_progress")

        resp = client.get(
            f"/v1/admin/llm-benchmark/results/{session.id}",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["iq_score"] is None
        assert data["percentile_rank"] is None
        assert data["questions"] == []

    def test_detail_unauthorized(self, client, db_session):
        resp = client.get(
            "/v1/admin/llm-benchmark/results/1",
            headers={"X-Admin-Token": "wrong"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /compare
# ---------------------------------------------------------------------------


class TestCompareHumanVsModels:
    """Tests for GET /v1/admin/llm-benchmark/compare."""

    def test_compare_no_data(self, client, db_session, admin_headers):
        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["human_avg_iq"] is None
        assert data["human_test_count"] == 0
        assert data["models"] == []

    def test_compare_with_human_and_model_data(
        self, client, db_session, admin_headers, test_user
    ):
        # Create a human test result
        from app.models.models import TestSession

        human_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(human_session)
        db_session.commit()
        db_session.refresh(human_session)

        human_result = TestResult(
            test_session_id=human_session.id,
            user_id=test_user.id,
            iq_score=105,
            total_questions=20,
            correct_answers=14,
        )
        db_session.add(human_result)
        db_session.commit()

        # Create LLM results
        llm_session = _create_session(db_session)
        _create_result(db_session, llm_session, iq_score=120, percentile=85.0)

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["human_avg_iq"] == pytest.approx(105.0)
        assert data["human_test_count"] == 1
        assert len(data["models"]) == 1
        model = data["models"][0]
        assert model["vendor"] == "openai"
        assert model["model_id"] == "gpt-4o"
        assert model["iq_score"] == 120
        assert model["sessions_count"] == 1

    def test_compare_no_human_results(self, client, db_session, admin_headers):
        """LLM data exists but no human results."""
        llm_session = _create_session(db_session)
        _create_result(db_session, llm_session)

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["human_avg_iq"] is None
        assert data["human_test_count"] == 0
        assert len(data["models"]) == 1

    def test_compare_no_llm_results(self, client, db_session, admin_headers, test_user):
        """Human data exists but no LLM results."""
        human_session = TestSession(
            user_id=test_user.id,
            status=TestStatus.COMPLETED,
        )
        db_session.add(human_session)
        db_session.commit()
        db_session.refresh(human_session)

        human_result = TestResult(
            test_session_id=human_session.id,
            user_id=test_user.id,
            iq_score=100,
            total_questions=20,
            correct_answers=12,
        )
        db_session.add(human_result)
        db_session.commit()

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)

        assert resp.status_code == 200
        data = resp.json()
        assert data["human_avg_iq"] == pytest.approx(100.0)
        assert data["human_test_count"] == 1
        assert data["models"] == []

    def test_compare_confidence_intervals(
        self, client, db_session, admin_headers, test_user
    ):
        """CI is computed when multiple human results exist."""
        from app.models.models import TestSession

        scores = [95, 100, 105, 110, 115]
        for score in scores:
            session = TestSession(user_id=test_user.id, status=TestStatus.COMPLETED)
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)
            db_session.add(
                TestResult(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    iq_score=score,
                    total_questions=20,
                    correct_answers=12,
                )
            )
        db_session.commit()

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)
        data = resp.json()

        assert data["human_avg_iq"] == pytest.approx(105.0)
        assert data["human_test_count"] == 5
        ci = data["human_ci"]
        assert ci is not None
        assert ci["lower"] < 105.0
        assert ci["upper"] > 105.0
        # n=5 < 30 → uses t-distribution: t(0.975, df=4) ≈ 2.776
        from scipy.stats import t as t_dist

        t_crit = t_dist.ppf(0.975, df=4)
        assert ci["lower"] == pytest.approx(
            105.0 - t_crit * math.sqrt(250 / 4) / math.sqrt(5), abs=0.05
        )

    def test_compare_low_sample_warning(
        self, client, db_session, admin_headers, test_user
    ):
        """Warning shown when human_test_count < 30."""
        from app.models.models import TestSession

        session = TestSession(user_id=test_user.id, status=TestStatus.COMPLETED)
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)
        db_session.add(
            TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=12,
            )
        )
        db_session.commit()

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)
        data = resp.json()

        assert data["low_sample_warning"] is not None
        assert "1 human" in data["low_sample_warning"]
        assert "30" in data["low_sample_warning"]

    def test_compare_domain_breakdown(
        self, client, db_session, admin_headers, test_user
    ):
        """Domain breakdown aggregates human and model domain_scores."""
        from app.models.models import TestSession

        human_session = TestSession(user_id=test_user.id, status=TestStatus.COMPLETED)
        db_session.add(human_session)
        db_session.commit()
        db_session.refresh(human_session)

        human_result = TestResult(
            test_session_id=human_session.id,
            user_id=test_user.id,
            iq_score=100,
            total_questions=20,
            correct_answers=12,
            domain_scores={
                "pattern": {"correct": 3, "total": 5, "pct": 60.0},
                "logic": {"correct": 4, "total": 5, "pct": 80.0},
            },
        )
        db_session.add(human_result)
        db_session.commit()

        llm_session = _create_session(db_session)
        _create_result(
            db_session,
            llm_session,
            iq_score=110,
            domain_scores={
                "pattern": {"correct": 4, "total": 5, "pct": 80.0},
                "logic": {"correct": 5, "total": 5, "pct": 100.0},
            },
        )

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)
        data = resp.json()

        breakdown = {d["domain"]: d for d in data["domain_breakdown"]}
        assert "pattern" in breakdown
        assert breakdown["pattern"]["human_pct"] == pytest.approx(60.0)
        assert breakdown["pattern"]["model_pct"] == pytest.approx(80.0)

    def test_compare_effect_size(self, client, db_session, admin_headers, test_user):
        """Cohen's d is computed when both groups have >= 2 observations."""
        from app.models.models import TestSession

        for score in [95, 105]:
            session = TestSession(user_id=test_user.id, status=TestStatus.COMPLETED)
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)
            db_session.add(
                TestResult(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    iq_score=score,
                    total_questions=20,
                    correct_answers=12,
                )
            )
        db_session.commit()

        for iq in [115, 125]:
            s = _create_session(db_session)
            _create_result(db_session, s, iq_score=iq)

        resp = client.get("/v1/admin/llm-benchmark/compare", headers=admin_headers)
        data = resp.json()

        assert data["effect_size"] is not None
        # Human mean=100, model mean=120, both std=~7.07 → d ≈ -2.83
        assert data["effect_size"] < 0  # models score higher

    def test_compare_unauthorized(self, client, db_session):
        resp = client.get(
            "/v1/admin/llm-benchmark/compare",
            headers={"X-Admin-Token": "wrong"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /question-set
# ---------------------------------------------------------------------------


class TestGenerateQuestionSet:
    """Tests for GET /v1/admin/llm-benchmark/question-set."""

    def test_question_set_returns_ids(
        self, client, db_session, admin_headers, test_questions
    ):
        resp = client.get(
            "/v1/admin/llm-benchmark/question-set",
            params={"total": 10},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "question_ids" in data
        assert data["total_questions"] == len(data["question_ids"])
        # Only active questions should be returned (test_questions has 4 active, 1 inactive)
        for qid in data["question_ids"]:
            assert qid != test_questions[4].id  # the inactive one

    def test_question_set_has_distributions(
        self, client, db_session, admin_headers, test_questions
    ):
        resp = client.get(
            "/v1/admin/llm-benchmark/question-set",
            params={"total": 10},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "domain_distribution" in data
        assert "difficulty_distribution" in data

    def test_question_set_unauthorized(self, client, db_session):
        resp = client.get(
            "/v1/admin/llm-benchmark/question-set",
            headers={"X-Admin-Token": "wrong"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Runner: fixed question set path
# ---------------------------------------------------------------------------


class TestRunnerFixedQuestionSet:
    """Tests for the fixed question_ids path in run_llm_benchmark."""

    @patch("app.api.v1.admin.llm_benchmark.run_llm_benchmark", new_callable=AsyncMock)
    def test_fixed_set_preserves_order(
        self, mock_run, client, db_session, admin_headers
    ):
        """question_ids should be forwarded to the runner in exact order."""
        mock_run.return_value = 50
        ids = [10, 5, 20, 1]

        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "openai", "model_id": "gpt-4o", "question_ids": ids},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        _, kwargs = mock_run.call_args
        assert kwargs["question_ids"] == ids

    @patch("app.api.v1.admin.llm_benchmark.run_llm_benchmark", new_callable=AsyncMock)
    def test_omitting_question_ids_uses_stratified(
        self, mock_run, client, db_session, admin_headers
    ):
        """When question_ids is omitted, question_ids kwarg should be None."""
        mock_run.return_value = 51

        resp = client.post(
            "/v1/admin/llm-benchmark/run",
            json={"vendor": "anthropic", "model_id": "claude-3"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        _, kwargs = mock_run.call_args
        assert kwargs["question_ids"] is None
        assert kwargs["total_questions"] is None
