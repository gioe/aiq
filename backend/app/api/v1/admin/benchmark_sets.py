"""
Admin endpoints for benchmark set management.

Provides creation, listing, and retrieval of named, frozen question sets
used for standardized LLM benchmarking.
"""

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.error_responses import raise_bad_request, raise_not_found
from app.models import get_db
from app.models.llm_benchmark import BenchmarkSet, BenchmarkSetQuestion
from app.models.models import Question
from app.schemas.benchmark_set import (
    BenchmarkSetDetailResponse,
    BenchmarkSetListResponse,
    BenchmarkSetQuestionDetail,
    BenchmarkSetResponse,
    CreateBenchmarkSetRequest,
)

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/benchmark-sets")


def _build_set_response(benchmark_set: BenchmarkSet) -> BenchmarkSetResponse:
    """Build a BenchmarkSetResponse from a loaded BenchmarkSet ORM object.

    Computes domain and difficulty distributions from the eagerly loaded
    questions relationship. Expects questions and their Question relationship
    to already be loaded to avoid N+1 queries.
    """
    domain_dist: dict[str, int] = defaultdict(int)
    difficulty_dist: dict[str, int] = defaultdict(int)

    for bsq in benchmark_set.questions:
        q = bsq.question
        domain_dist[str(q.question_type)] += 1
        difficulty_dist[str(q.difficulty_level)] += 1

    return BenchmarkSetResponse(
        id=benchmark_set.id,
        name=benchmark_set.name,
        description=benchmark_set.description,
        is_active=benchmark_set.is_active,
        total_questions=len(benchmark_set.questions),
        domain_distribution=dict(domain_dist),
        difficulty_distribution=dict(difficulty_dist),
        created_at=benchmark_set.created_at,
        updated_at=benchmark_set.updated_at,
    )


def _build_detail_response(benchmark_set: BenchmarkSet) -> BenchmarkSetDetailResponse:
    """Build a BenchmarkSetDetailResponse from a loaded BenchmarkSet.

    Expects questions and their Question relationship to already be loaded.
    """
    domain_dist: dict[str, int] = defaultdict(int)
    difficulty_dist: dict[str, int] = defaultdict(int)
    question_details = []
    for bsq in benchmark_set.questions:
        q = bsq.question
        domain_dist[str(q.question_type)] += 1
        difficulty_dist[str(q.difficulty_level)] += 1
        question_details.append(
            BenchmarkSetQuestionDetail(
                position=bsq.position,
                question_id=bsq.question_id,
                question_type=str(q.question_type),
                difficulty_level=str(q.difficulty_level),
                question_text=q.question_text,
            )
        )

    return BenchmarkSetDetailResponse(
        id=benchmark_set.id,
        name=benchmark_set.name,
        description=benchmark_set.description,
        is_active=benchmark_set.is_active,
        total_questions=len(benchmark_set.questions),
        domain_distribution=dict(domain_dist),
        difficulty_distribution=dict(difficulty_dist),
        created_at=benchmark_set.created_at,
        updated_at=benchmark_set.updated_at,
        questions=question_details,
    )


@router.post(
    "",
    response_model=BenchmarkSetDetailResponse,
    status_code=201,
)
async def create_benchmark_set(
    body: CreateBenchmarkSetRequest,
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSetDetailResponse:
    """Create a new benchmark set.

    Validates that all supplied question IDs exist and are active, then
    creates the set with positions matching the order of question_ids.
    """
    # Check name uniqueness.
    existing_q = select(BenchmarkSet).where(BenchmarkSet.name == body.name)
    existing = (await db.execute(existing_q)).scalar_one_or_none()
    if existing is not None:
        raise_bad_request(
            f"A benchmark set named '{body.name}' already exists (ID: {existing.id})."
        )

    # Reject duplicate question IDs.
    if len(body.question_ids) != len(set(body.question_ids)):
        raise_bad_request("Duplicate question IDs are not allowed.")

    # Validate all question IDs exist and are active.
    questions_q = select(Question).where(
        Question.id.in_(body.question_ids),
        Question.is_active.is_(True),
    )
    found_questions = (await db.execute(questions_q)).scalars().all()
    found_ids = {q.id for q in found_questions}

    missing_ids = set(body.question_ids) - found_ids
    if missing_ids:
        sorted_missing = sorted(missing_ids)
        raise_bad_request(
            f"The following question IDs were not found or are inactive: "
            f"{', '.join(str(i) for i in sorted_missing)}."
        )

    # Build the set and its ordered junction rows.
    benchmark_set = BenchmarkSet(
        name=body.name,
        description=body.description,
    )
    db.add(benchmark_set)
    await db.flush()  # Populate benchmark_set.id before inserting children.

    for position, question_id in enumerate(body.question_ids):
        db.add(
            BenchmarkSetQuestion(
                benchmark_set_id=benchmark_set.id,
                question_id=question_id,
                position=position,
            )
        )

    await db.commit()

    # Reload with relationships for the response.
    reload_q = (
        select(BenchmarkSet)
        .where(BenchmarkSet.id == benchmark_set.id)
        .options(
            selectinload(BenchmarkSet.questions).selectinload(
                BenchmarkSetQuestion.question
            )
        )
    )
    loaded = (await db.execute(reload_q)).scalar_one()

    logger.info(
        "Created benchmark set '%s' (ID: %d) with %d questions.",
        loaded.name,
        loaded.id,
        len(loaded.questions),
    )

    return _build_detail_response(loaded)


@router.get(
    "",
    response_model=BenchmarkSetListResponse,
)
async def list_benchmark_sets(
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSetListResponse:
    """Return all benchmark sets with domain and difficulty distribution summaries."""
    sets_q = (
        select(BenchmarkSet)
        .options(
            selectinload(BenchmarkSet.questions).selectinload(
                BenchmarkSetQuestion.question
            )
        )
        .order_by(BenchmarkSet.created_at.desc())
    )
    rows = (await db.execute(sets_q)).scalars().all()

    return BenchmarkSetListResponse(
        sets=[_build_set_response(bs) for bs in rows],
        total_count=len(rows),
    )


@router.get(
    "/{name}",
    response_model=BenchmarkSetDetailResponse,
)
async def get_benchmark_set(
    name: str,
    _: bool = Depends(verify_admin_token),
    db: AsyncSession = Depends(get_db),
) -> BenchmarkSetDetailResponse:
    """Return a benchmark set by name, including its full ordered question list."""
    set_q = (
        select(BenchmarkSet)
        .where(BenchmarkSet.name == name)
        .options(
            selectinload(BenchmarkSet.questions).selectinload(
                BenchmarkSetQuestion.question
            )
        )
    )
    benchmark_set = (await db.execute(set_q)).scalar_one_or_none()
    if benchmark_set is None:
        raise_not_found(f"Benchmark set '{name}' not found.")

    return _build_detail_response(benchmark_set)
