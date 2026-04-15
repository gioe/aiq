"""
Admin data-query endpoints.

Read-only endpoints mirroring the aiq-data CLI subcommands, providing
production database access through the admin API. All endpoints require
X-Admin-Token authentication.
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_responses import raise_bad_request, raise_not_found
from app.models import get_db
from app.models.models import (
    Question,
    QuestionGenerationRun,
    TestResult,
    TestSession,
    User,
)

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()

_READ_ONLY_PATTERN = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class UserRow(BaseModel):
    id: int
    email: str
    first_name: Optional[str]
    created_at: Optional[datetime]
    last_login_at: Optional[datetime]


class InventoryRow(BaseModel):
    question_type: str
    difficulty_level: str
    is_active: bool
    count: int


class SessionRow(BaseModel):
    id: int
    user_id: int
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    is_adaptive: bool


class ScoreRow(BaseModel):
    id: int
    user_id: int
    iq_score: int
    percentile_rank: Optional[float]
    total_questions: int
    correct_answers: int
    completed_at: Optional[datetime]
    validity_status: Optional[str]


class GenerationRow(BaseModel):
    id: int
    started_at: Optional[datetime]
    status: str
    questions_requested: int
    questions_generated: int
    questions_approved: int
    questions_inserted: int
    avg_judge_score: Optional[float]
    duration_seconds: Optional[float]


class ActivityRow(BaseModel):
    day: str
    sessions: int
    unique_users: int


class SqlRequest(BaseModel):
    query: str


class SqlResponse(BaseModel):
    columns: list[str]
    rows: list[list[Any]]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/data/users", response_model=list[UserRow])
async def data_users(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """List all users with basic info."""
    result = await db.execute(
        select(
            User.id,
            User.email,
            User.first_name,
            User.created_at,
            User.last_login_at,
        ).order_by(User.created_at.desc())
    )
    return [
        UserRow(
            id=r.id,
            email=r.email,
            first_name=r.first_name,
            created_at=r.created_at,
            last_login_at=r.last_login_at,
        )
        for r in result.all()
    ]


@router.get("/data/inventory", response_model=list[InventoryRow])
async def data_inventory(
    type: Optional[str] = Query(None, description="Filter by question_type"),
    difficulty: Optional[str] = Query(None, description="Filter by difficulty_level"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Show question inventory breakdown by type, difficulty, and active status."""
    stmt = select(
        Question.question_type,
        Question.difficulty_level,
        Question.is_active,
        func.count().label("row_count"),
    ).group_by(
        Question.question_type,
        Question.difficulty_level,
        Question.is_active,
    )
    if type:
        stmt = stmt.where(Question.question_type == type)
    if difficulty:
        stmt = stmt.where(Question.difficulty_level == difficulty)
    stmt = stmt.order_by(Question.question_type, Question.difficulty_level)

    result = await db.execute(stmt)
    return [
        InventoryRow(
            question_type=str(r.question_type),
            difficulty_level=str(r.difficulty_level),
            is_active=r.is_active,
            count=r.row_count,
        )
        for r in result.all()
    ]


@router.get("/data/sessions", response_model=list[SessionRow])
async def data_sessions(
    user: Optional[str] = Query(None, description="Filter by user email"),
    limit: int = Query(50, ge=1, le=1000, description="Max rows"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """List test sessions, optionally filtered by user email."""
    stmt = select(
        TestSession.id,
        TestSession.user_id,
        TestSession.status,
        TestSession.started_at,
        TestSession.completed_at,
        TestSession.is_adaptive,
    )
    if user:
        user_result = await db.execute(select(User.id).where(User.email == user))
        user_row = user_result.scalar_one_or_none()
        if user_row is None:
            raise_not_found(f"User not found: {user}")
        stmt = stmt.where(TestSession.user_id == user_row)
    stmt = stmt.order_by(TestSession.started_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return [
        SessionRow(
            id=r.id,
            user_id=r.user_id,
            status=str(r.status),
            started_at=r.started_at,
            completed_at=r.completed_at,
            is_adaptive=r.is_adaptive,
        )
        for r in result.all()
    ]


@router.get("/data/scores", response_model=list[ScoreRow])
async def data_scores(
    user: Optional[str] = Query(None, description="Filter by user email"),
    limit: int = Query(50, ge=1, le=1000, description="Max rows"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """List test results / scores, optionally filtered by user email."""
    stmt = select(
        TestResult.id,
        TestResult.user_id,
        TestResult.iq_score,
        TestResult.percentile_rank,
        TestResult.total_questions,
        TestResult.correct_answers,
        TestResult.completed_at,
        TestResult.validity_status,
    )
    if user:
        user_result = await db.execute(select(User.id).where(User.email == user))
        user_row = user_result.scalar_one_or_none()
        if user_row is None:
            raise_not_found(f"User not found: {user}")
        stmt = stmt.where(TestResult.user_id == user_row)
    stmt = stmt.order_by(TestResult.completed_at.desc()).limit(limit)

    result = await db.execute(stmt)
    return [
        ScoreRow(
            id=r.id,
            user_id=r.user_id,
            iq_score=r.iq_score,
            percentile_rank=r.percentile_rank,
            total_questions=r.total_questions,
            correct_answers=r.correct_answers,
            completed_at=r.completed_at,
            validity_status=r.validity_status,
        )
        for r in result.all()
    ]


@router.get("/data/generation", response_model=list[GenerationRow])
async def data_generation(
    limit: int = Query(20, ge=1, le=500, description="Max rows"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Show question generation run history."""
    result = await db.execute(
        select(
            QuestionGenerationRun.id,
            QuestionGenerationRun.started_at,
            QuestionGenerationRun.status,
            QuestionGenerationRun.questions_requested,
            QuestionGenerationRun.questions_generated,
            QuestionGenerationRun.questions_approved,
            QuestionGenerationRun.questions_inserted,
            QuestionGenerationRun.avg_judge_score,
            QuestionGenerationRun.duration_seconds,
        )
        .order_by(QuestionGenerationRun.started_at.desc())
        .limit(limit)
    )
    return [
        GenerationRow(
            id=r.id,
            started_at=r.started_at,
            status=str(r.status),
            questions_requested=r.questions_requested,
            questions_generated=r.questions_generated,
            questions_approved=r.questions_approved,
            questions_inserted=r.questions_inserted,
            avg_judge_score=r.avg_judge_score,
            duration_seconds=r.duration_seconds,
        )
        for r in result.all()
    ]


@router.get("/data/activity", response_model=list[ActivityRow])
async def data_activity(
    days: int = Query(30, ge=1, le=365, description="Lookback days"),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Show recent user activity (test sessions started per day)."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        text(
            "SELECT DATE(started_at) as day, COUNT(*) as sessions, "
            "COUNT(DISTINCT user_id) as unique_users "
            "FROM test_sessions "
            "WHERE started_at >= :since "
            "GROUP BY DATE(started_at) "
            "ORDER BY day DESC"
        ),
        {"since": since},
    )
    return [
        ActivityRow(day=str(r.day), sessions=r.sessions, unique_users=r.unique_users)
        for r in result.all()
    ]


@router.post("/data/sql", response_model=SqlResponse)
async def data_sql(
    body: SqlRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """Run an arbitrary read-only SQL query. Only SELECT and WITH statements are allowed."""
    if not _READ_ONLY_PATTERN.match(body.query):
        raise_bad_request("Only SELECT and WITH statements are allowed.")

    result = await db.execute(text(body.query))
    if result.returns_rows:
        columns = list(result.keys())
        rows = [list(r) for r in result.fetchall()]
        return SqlResponse(columns=columns, rows=rows)
    return SqlResponse(columns=[], rows=[])
