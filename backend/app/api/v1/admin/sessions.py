"""
Session admin endpoints.

Endpoints for managing individual test sessions, including hard-deletion
with optional dry-run preview, and bulk deletion by email.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.security_audit import get_client_ip_from_request
from app.core.error_responses import ErrorMessages, raise_not_found
from app.models import get_db
from app.models.models import Response as ResponseModel
from app.models.models import TestResult, TestSession, User, UserQuestion

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()


class SessionDeletionPreview(BaseModel):
    """Preview of what would be deleted by a session deletion."""

    session_id: int
    responses_count: int
    user_questions_count: int
    has_test_result: bool
    dry_run: bool


class BulkSessionDeletionPreview(BaseModel):
    """Preview/result of bulk session deletion by email."""

    email: str
    user_id: int
    sessions_deleted: int
    total_responses: int
    total_user_questions: int
    total_test_results: int
    session_ids: List[int]
    dry_run: bool


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    responses={
        204: {"description": "Session deleted successfully"},
        404: {"description": "Session not found"},
        200: {"description": "Dry-run preview (when ?dry_run=true)"},
    },
)
async def delete_session(
    request: Request,
    session_id: int,
    dry_run: bool = Query(
        False, description="Preview what would be deleted without committing"
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Hard-delete a test session and all associated data.

    Cascades automatically to responses, test results, and user questions.
    Returns 204 on success, 404 if session not found.

    Use ?dry_run=true to preview what would be deleted without committing.

    Requires X-Admin-Token header with valid admin token.

    Args:
        session_id: ID of the test session to delete
        dry_run: If True, return a preview without deleting anything
        db: Database session
        _: Admin token validation dependency

    Returns:
        204 No Content on successful deletion, or SessionDeletionPreview on dry run

    Raises:
        404: If the session does not exist
    """
    result = await db.execute(select(TestSession).where(TestSession.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise_not_found(ErrorMessages.TEST_SESSION_NOT_FOUND)

    if dry_run:
        # Count associated records only for the dry-run preview
        responses_count_result = await db.execute(
            select(func.count(ResponseModel.id)).where(
                ResponseModel.test_session_id == session_id
            )
        )
        responses_count = responses_count_result.scalar_one()

        user_questions_count_result = await db.execute(
            select(func.count(UserQuestion.id)).where(
                UserQuestion.test_session_id == session_id
            )
        )
        user_questions_count = user_questions_count_result.scalar_one()

        test_result_result = await db.execute(
            select(TestResult).where(TestResult.test_session_id == session_id)
        )
        has_test_result = test_result_result.scalar_one_or_none() is not None

        preview = SessionDeletionPreview(
            session_id=session_id,
            responses_count=responses_count,
            user_questions_count=user_questions_count,
            has_test_result=has_test_result,
            dry_run=True,
        )
        return JSONResponse(status_code=200, content=preview.model_dump())

    await db.delete(session)
    await db.commit()

    client_ip = get_client_ip_from_request(request)
    logger.info(f"Admin hard-deleted test session {session_id} (ip={client_ip})")

    return Response(status_code=204)


@router.delete(
    "/sessions/by-email/{email}",
    response_model=BulkSessionDeletionPreview,
    responses={
        200: {"description": "Preview or result of bulk session deletion"},
        404: {"description": "User not found or session not found"},
    },
)
async def delete_sessions_by_email(
    request: Request,
    email: str,
    session_id: Optional[int] = Query(
        None, description="Scope deletion to a single session ID"
    ),
    dry_run: bool = Query(
        True, description="Preview what would be deleted without committing"
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Hard-delete test sessions for a user identified by email.

    By default operates in dry-run mode (dry_run=true) for safe preview.
    Pass ?dry_run=false to actually delete. Optionally scope to a single
    session with ?session_id=N.

    Cascades automatically to responses, test results, and user questions.
    Requires X-Admin-Token header.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    # Build session query
    session_query = select(TestSession).where(TestSession.user_id == user.id)
    if session_id is not None:
        session_query = session_query.where(TestSession.id == session_id)

    sessions_result = await db.execute(session_query)
    sessions = list(sessions_result.scalars().all())

    if session_id is not None and not sessions:
        raise_not_found(ErrorMessages.TEST_SESSION_NOT_FOUND)

    # Count cascade children across all matched sessions
    matched_ids = [s.id for s in sessions]
    total_responses = 0
    total_user_questions = 0
    total_test_results = 0

    if matched_ids:
        resp_count = await db.execute(
            select(func.count(ResponseModel.id)).where(
                ResponseModel.test_session_id.in_(matched_ids)
            )
        )
        total_responses = resp_count.scalar_one()

        uq_count = await db.execute(
            select(func.count(UserQuestion.id)).where(
                UserQuestion.test_session_id.in_(matched_ids)
            )
        )
        total_user_questions = uq_count.scalar_one()

        tr_count = await db.execute(
            select(func.count(TestResult.id)).where(
                TestResult.test_session_id.in_(matched_ids)
            )
        )
        total_test_results = tr_count.scalar_one()

    preview = BulkSessionDeletionPreview(
        email=email,
        user_id=user.id,
        sessions_deleted=len(sessions),
        total_responses=total_responses,
        total_user_questions=total_user_questions,
        total_test_results=total_test_results,
        session_ids=matched_ids,
        dry_run=dry_run,
    )

    if dry_run:
        return preview

    # Perform deletion
    for session in sessions:
        await db.delete(session)
    await db.commit()

    client_ip = get_client_ip_from_request(request)
    logger.info(
        f"Admin hard-deleted {len(sessions)} test session(s) for "
        f"user {user.id} ({email}) (ip={client_ip})"
    )

    return preview
