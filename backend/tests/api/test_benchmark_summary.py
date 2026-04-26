"""
Tests for GET /v1/benchmark/summary — public benchmark summary endpoint.
"""

from datetime import datetime, timezone

import pytest

from app.core.cache import get_cache
from app.models.llm_benchmark import LLMResponse, LLMTestResult, LLMTestSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_benchmark_run(
    db,
    *,
    vendor="openai",
    model_id="gpt-4o",
    iq_score=110,
    total_questions=20,
    correct_answers=15,
    domain_scores=None,
    response_errors=None,
    question_ids=None,
):
    """Create a completed benchmark session + result pair."""
    ts = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    session = LLMTestSession(
        vendor=vendor,
        model_id=model_id,
        status="completed",
        started_at=ts,
        completed_at=ts,
        total_prompt_tokens=500,
        total_completion_tokens=200,
        total_cost_usd=0.05,
        temperature=0.0,
        triggered_by="admin_api",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    result = LLMTestResult(
        session_id=session.id,
        vendor=vendor,
        model_id=model_id,
        iq_score=iq_score,
        percentile_rank=75.0,
        total_questions=total_questions,
        correct_answers=correct_answers,
        domain_scores=domain_scores
        or {
            "pattern": {"correct": 8, "total": 10},
            "logic": {"correct": 7, "total": 10},
        },
        completed_at=ts,
    )
    db.add(result)
    db.commit()
    db.refresh(result)

    if response_errors is not None:
        if question_ids is None:
            raise ValueError("question_ids are required when creating responses")
        for index, question_id in enumerate(question_ids):
            has_error = index < response_errors
            response = LLMResponse(
                session_id=session.id,
                question_id=question_id,
                raw_answer=None if has_error else "B",
                normalized_answer=None if has_error else "B",
                is_correct=False if has_error else index < correct_answers,
                prompt_tokens=0,
                completion_tokens=0,
                cost_usd=0.0,
                latency_ms=100,
                error="provider compatibility error" if has_error else None,
            )
            db.add(response)
        db.commit()

    return session, result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestBenchmarkSummary:
    """Tests for GET /v1/benchmark/summary."""

    def setup_method(self):
        get_cache().clear()

    def test_requires_auth(self, client):
        """Endpoint rejects unauthenticated requests."""
        resp = client.get("/v1/benchmark/summary")
        assert resp.status_code == 403

    def test_empty_results(self, client, auth_headers):
        """Returns empty models list when no benchmark data exists."""
        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["models"] == []
        assert data["min_runs"] == 3

    def test_filters_by_min_runs(self, client, db_session, auth_headers):
        """Models with fewer than min_runs are excluded."""
        # Create 2 runs (below default threshold of 3)
        for _ in range(2):
            _create_benchmark_run(db_session, vendor="openai", model_id="gpt-4o")

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()["models"]) == 0

        # With min_runs=2, should appear
        resp = client.get(
            "/v1/benchmark/summary", headers=auth_headers, params={"min_runs": 2}
        )
        assert resp.status_code == 200
        assert len(resp.json()["models"]) == 1

    def test_returns_model_data(self, client, db_session, auth_headers):
        """Returns correct model performance data."""
        for iq in [100, 110, 120]:
            _create_benchmark_run(
                db_session,
                vendor="anthropic",
                model_id="claude-sonnet-4-5-20250929",
                iq_score=iq,
            )

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) == 1

        model = data["models"][0]
        assert model["display_name"] == "Claude Sonnet 4.5"
        assert model["vendor"] == "anthropic"
        assert model["mean_iq"] == pytest.approx(110.0)
        assert model["runs"] == 3
        assert model["accuracy_pct"] == pytest.approx(75.0)  # 15/20

    def test_domain_accuracy_breakdown(self, client, db_session, auth_headers):
        """Returns per-domain accuracy breakdown per model."""
        for _ in range(3):
            _create_benchmark_run(
                db_session,
                vendor="openai",
                model_id="gpt-4o",
                domain_scores={
                    "pattern": {"correct": 8, "total": 10},
                    "logic": {"correct": 6, "total": 10},
                },
            )

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200
        model = resp.json()["models"][0]
        domains = {d["domain"]: d for d in model["domain_accuracy"]}
        assert "pattern" in domains
        assert "logic" in domains
        assert domains["pattern"]["accuracy_pct"] == pytest.approx(80.0)
        assert domains["logic"]["accuracy_pct"] == pytest.approx(60.0)

    def test_no_sensitive_fields(self, client, db_session, auth_headers):
        """Response does not contain cost, token, or session detail fields."""
        for _ in range(3):
            _create_benchmark_run(db_session)

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        model = data["models"][0]

        # These fields exist on the admin endpoint but must not appear here
        for field in [
            "total_questions",
            "correct_answers",
            "iq_score",
            "percentile_rank",
            "iq_ci",
            "model_id",
            "latest_run",
        ]:
            assert field not in model

    def test_display_names(self, client, db_session, auth_headers):
        """Models use human-friendly display names."""
        for _ in range(3):
            _create_benchmark_run(db_session, vendor="openai", model_id="gpt-4o")

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        model = resp.json()["models"][0]
        assert model["display_name"] == "GPT-4o"

    def test_sorted_by_mean_iq_desc(self, client, db_session, auth_headers):
        """Models are sorted by mean IQ descending."""
        for _ in range(3):
            _create_benchmark_run(
                db_session, vendor="openai", model_id="gpt-4o", iq_score=100
            )
        for _ in range(3):
            _create_benchmark_run(
                db_session,
                vendor="anthropic",
                model_id="claude-sonnet-4-5-20250929",
                iq_score=120,
            )

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        models = resp.json()["models"]
        assert len(models) == 2
        assert models[0]["display_name"] == "Claude Sonnet 4.5"
        assert models[1]["display_name"] == "GPT-4o"

    def test_caching(self, client, db_session, auth_headers):
        """Response is cached on subsequent requests."""
        for _ in range(3):
            _create_benchmark_run(db_session)

        resp1 = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp1.status_code == 200

        # Add more data — cached response should still be returned
        for _ in range(3):
            _create_benchmark_run(
                db_session,
                vendor="anthropic",
                model_id="claude-opus-4-6",
                iq_score=130,
            )

        resp2 = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp2.status_code == 200
        # Should still show only 1 model (cached)
        assert len(resp2.json()["models"]) == 1

    def test_excludes_all_error_benchmark_sessions(
        self, client, db_session, auth_headers, test_questions
    ):
        """All-error compatibility-failure sessions do not contribute to summary."""
        question_ids = [q.id for q in test_questions[:3]]

        for _ in range(3):
            _create_benchmark_run(
                db_session,
                vendor="openai",
                model_id="gpt-5.5",
                iq_score=114,
                total_questions=3,
                correct_answers=3,
                domain_scores={"pattern": {"correct": 3, "total": 3}},
                response_errors=0,
                question_ids=question_ids,
            )

        for _ in range(2):
            _create_benchmark_run(
                db_session,
                vendor="openai",
                model_id="gpt-5.5",
                iq_score=85,
                total_questions=3,
                correct_answers=0,
                domain_scores={"pattern": {"correct": 0, "total": 3}},
                response_errors=3,
                question_ids=question_ids,
            )

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200

        model = resp.json()["models"][0]
        assert model["display_name"] == "GPT-5.5"
        assert model["runs"] == 3
        assert model["mean_iq"] == pytest.approx(114.0)
        assert model["accuracy_pct"] == pytest.approx(100.0)
        assert model["domain_accuracy"][0]["accuracy_pct"] == pytest.approx(100.0)
        assert model["domain_accuracy"][0]["total_questions"] == 9

    def test_all_invalid_sessions_do_not_satisfy_min_runs(
        self, client, db_session, auth_headers, test_questions
    ):
        """A model with only provider-error sessions is hidden from the app."""
        question_ids = [q.id for q in test_questions[:3]]

        for _ in range(3):
            _create_benchmark_run(
                db_session,
                vendor="anthropic",
                model_id="claude-opus-4-7",
                iq_score=85,
                total_questions=3,
                correct_answers=0,
                response_errors=3,
                question_ids=question_ids,
            )

        resp = client.get(
            "/v1/benchmark/summary", headers=auth_headers, params={"min_runs": 1}
        )
        assert resp.status_code == 200
        assert resp.json()["models"] == []

    def test_partial_error_session_is_excluded_from_mixed_history(
        self, client, db_session, auth_headers, test_questions
    ):
        """Only zero-error completed sessions contribute to public model averages."""
        question_ids = [q.id for q in test_questions[:3]]

        for _ in range(3):
            _create_benchmark_run(
                db_session,
                vendor="anthropic",
                model_id="claude-opus-4-7",
                iq_score=115,
                total_questions=3,
                correct_answers=3,
                domain_scores={"logic": {"correct": 3, "total": 3}},
                response_errors=0,
                question_ids=question_ids,
            )

        _create_benchmark_run(
            db_session,
            vendor="anthropic",
            model_id="claude-opus-4-7",
            iq_score=95,
            total_questions=3,
            correct_answers=1,
            domain_scores={"logic": {"correct": 1, "total": 3}},
            response_errors=1,
            question_ids=question_ids,
        )

        resp = client.get("/v1/benchmark/summary", headers=auth_headers)
        assert resp.status_code == 200

        model = resp.json()["models"][0]
        assert model["display_name"] == "Claude Opus 4.7"
        assert model["runs"] == 3
        assert model["mean_iq"] == pytest.approx(115.0)
        assert model["accuracy_pct"] == pytest.approx(100.0)
        assert model["domain_accuracy"] == [
            {"domain": "logic", "accuracy_pct": 100.0, "total_questions": 9}
        ]
