"""
Admin endpoints for LLM benchmark management.

Provides run triggering, result browsing, and human-vs-model comparison.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.error_responses import raise_bad_request, raise_not_found
from app.models import get_db
from app.models.llm_benchmark import LLMTestResult, LLMTestSession
from app.models.models import Question, TestResult
from app.schemas.llm_benchmark import (
    BenchmarkDetailResponse,
    BenchmarkResultsListResponse,
    BenchmarkSessionSummary,
    CompareResponse,
    GenerateQuestionSetResponse,
    ModelComparison,
    QuestionBreakdown,
    RunBenchmarkRequest,
    RunBenchmarkResponse,
)
from app.services.llm_benchmark.runner import run_llm_benchmark

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/llm-benchmark")

_VALID_VENDORS = {"openai", "anthropic", "google"}


_DOMAINS = list(settings.TEST_DOMAIN_WEIGHTS.keys())
_DIFFICULTIES = list(settings.TEST_DIFFICULTY_DISTRIBUTION.keys())


@router.get(
    "/question-set",
    response_model=GenerateQuestionSetResponse,
)
async def generate_question_set(
    total: int = Query(
        100,
        ge=6,
        le=500,
        description="Target number of questions. Distributed evenly across domains and difficulties.",
    ),
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> GenerateQuestionSetResponse:
    """Generate a balanced set of question IDs across all domains and difficulties.

    Selects questions evenly across each (domain, difficulty) cell, preferring
    questions with higher discrimination.  The resulting IDs can be passed to
    the ``POST /run`` endpoint via the ``question_ids`` field or used to create
    a named BenchmarkSet via ``POST /v1/admin/benchmark-sets``.
    """
    per_cell = total // (len(_DOMAINS) * len(_DIFFICULTIES))
    remainder = total - per_cell * len(_DOMAINS) * len(_DIFFICULTIES)

    question_ids: list[int] = []
    domain_dist: dict[str, int] = defaultdict(int)
    difficulty_dist: dict[str, int] = defaultdict(int)

    for domain in _DOMAINS:
        for difficulty in _DIFFICULTIES:
            limit = per_cell + (1 if remainder > 0 else 0)
            if remainder > 0:
                remainder -= 1

            q = (
                select(Question.id)
                .where(
                    Question.question_type == domain,
                    Question.difficulty_level == difficulty,
                    Question.is_active.is_(True),
                )
                .order_by(Question.discrimination.desc().nulls_last())
                .limit(limit)
            )
            rows = (await db.execute(q)).scalars().all()
            question_ids.extend(rows)
            domain_dist[domain] += len(rows)
            difficulty_dist[difficulty] += len(rows)

    return GenerateQuestionSetResponse(
        question_ids=question_ids,
        total_questions=len(question_ids),
        domain_distribution=dict(domain_dist),
        difficulty_distribution=dict(difficulty_dist),
    )


@router.post(
    "/run",
    response_model=RunBenchmarkResponse,
)
async def trigger_benchmark_run(
    body: RunBenchmarkRequest,
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> RunBenchmarkResponse:
    """Trigger a new LLM benchmark run.

    Runs the benchmark synchronously and returns the session ID on completion.
    """
    if body.vendor not in _VALID_VENDORS:
        raise_bad_request(
            f"Unknown vendor '{body.vendor}'. "
            f"Must be one of: {', '.join(sorted(_VALID_VENDORS))}."
        )

    try:
        session_id = await run_llm_benchmark(
            db,
            body.vendor,
            body.model_id,
            total_questions=body.question_count,
            question_ids=body.question_ids,
            triggered_by="admin_api",
        )
    except ValueError as exc:
        raise_bad_request(str(exc))

    return RunBenchmarkResponse(
        session_id=session_id,
        status="completed",
        message=f"Benchmark run completed for {body.vendor}/{body.model_id}.",
    )


@router.get(
    "/results",
    response_model=BenchmarkResultsListResponse,
)
async def list_benchmark_results(
    vendor: str | None = Query(None, description="Filter by vendor."),
    model_id: str | None = Query(None, description="Filter by model identifier."),
    limit: int = Query(20, ge=1, le=100, description="Page size."),
    offset: int = Query(0, ge=0, description="Page offset."),
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkResultsListResponse:
    """Return a paginated list of benchmark sessions with scores."""
    base = select(LLMTestSession).options(selectinload(LLMTestSession.test_result))

    if vendor:
        base = base.where(LLMTestSession.vendor == vendor)
    if model_id:
        base = base.where(LLMTestSession.model_id == model_id)

    # Total count.
    count_q = select(func.count()).select_from(base.subquery())
    total_count = (await db.execute(count_q)).scalar_one()

    # Fetch page.
    rows_q = base.order_by(LLMTestSession.started_at.desc()).offset(offset).limit(limit)
    rows = (await db.execute(rows_q)).scalars().all()

    summaries = [
        BenchmarkSessionSummary(
            id=s.id,
            vendor=s.vendor,
            model_id=s.model_id,
            status=s.status,
            started_at=s.started_at,
            completed_at=s.completed_at,
            iq_score=s.test_result.iq_score if s.test_result else None,
            percentile_rank=s.test_result.percentile_rank if s.test_result else None,
            total_questions=s.test_result.total_questions if s.test_result else None,
            correct_answers=s.test_result.correct_answers if s.test_result else None,
            total_cost_usd=s.total_cost_usd,
        )
        for s in rows
    ]

    return BenchmarkResultsListResponse(
        results=summaries,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total_count,
    )


@router.get(
    "/results/{session_id}",
    response_model=BenchmarkDetailResponse,
)
async def get_benchmark_detail(
    session_id: int,
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkDetailResponse:
    """Return detailed results for a single benchmark session."""
    q = (
        select(LLMTestSession)
        .where(LLMTestSession.id == session_id)
        .options(
            selectinload(LLMTestSession.test_result),
            selectinload(LLMTestSession.responses),
        )
    )
    session = (await db.execute(q)).scalar_one_or_none()
    if session is None:
        raise_not_found(f"Benchmark session not found (ID: {session_id}).")

    result = session.test_result
    questions = [
        QuestionBreakdown(
            question_id=r.question_id,
            is_correct=r.is_correct,
            normalized_answer=r.normalized_answer,
            latency_ms=r.latency_ms,
            cost_usd=r.cost_usd,
            error=r.error,
        )
        for r in session.responses
    ]

    return BenchmarkDetailResponse(
        id=session.id,
        vendor=session.vendor,
        model_id=session.model_id,
        status=session.status,
        started_at=session.started_at,
        completed_at=session.completed_at,
        temperature=session.temperature,
        triggered_by=session.triggered_by,
        total_prompt_tokens=session.total_prompt_tokens,
        total_completion_tokens=session.total_completion_tokens,
        total_cost_usd=session.total_cost_usd,
        iq_score=result.iq_score if result else None,
        percentile_rank=result.percentile_rank if result else None,
        total_questions=result.total_questions if result else None,
        correct_answers=result.correct_answers if result else None,
        domain_scores=result.domain_scores if result else None,
        questions=questions,
    )


@router.get(
    "/compare",
    response_model=CompareResponse,
)
async def compare_human_vs_models(
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> CompareResponse:
    """Compare human average IQ against all tested LLM models."""
    # Human average IQ.
    human_q = select(
        func.avg(TestResult.iq_score),
        func.count(TestResult.id),
    )
    human_row = (await db.execute(human_q)).one()
    human_avg_iq = float(human_row[0]) if human_row[0] is not None else None
    human_test_count = human_row[1]

    # Per-model aggregation from completed results.
    model_q = (
        select(
            LLMTestResult.vendor,
            LLMTestResult.model_id,
            func.count(LLMTestResult.id).label("sessions_count"),
            func.sum(LLMTestResult.total_questions).label("total_questions"),
            func.sum(LLMTestResult.correct_answers).label("correct_answers"),
            func.max(LLMTestResult.completed_at).label("latest_run"),
        )
        .where(LLMTestResult.iq_score.isnot(None))
        .group_by(LLMTestResult.vendor, LLMTestResult.model_id)
        .order_by(func.max(LLMTestResult.completed_at).desc())
    )
    model_rows = (await db.execute(model_q)).all()

    models = []
    for row in model_rows:
        # Fetch most-recent IQ score and percentile for this model.
        latest_q = (
            select(LLMTestResult.iq_score, LLMTestResult.percentile_rank)
            .where(
                LLMTestResult.vendor == row.vendor,
                LLMTestResult.model_id == row.model_id,
                LLMTestResult.iq_score.isnot(None),
            )
            .order_by(LLMTestResult.completed_at.desc())
            .limit(1)
        )
        latest = (await db.execute(latest_q)).one_or_none()

        models.append(
            ModelComparison(
                vendor=row.vendor,
                model_id=row.model_id,
                iq_score=latest[0] if latest else None,
                percentile_rank=latest[1] if latest else None,
                total_questions=row.total_questions,
                correct_answers=row.correct_answers,
                sessions_count=row.sessions_count,
                latest_run=row.latest_run,
            )
        )

    return CompareResponse(
        human_avg_iq=human_avg_iq,
        human_test_count=human_test_count,
        models=models,
    )
