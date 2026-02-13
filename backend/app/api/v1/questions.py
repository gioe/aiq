"""
Question serving endpoints for IQ tests.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import get_db, User, Question, UserQuestion
from app.schemas.questions import UnseenQuestionsResponse
from app.core.auth import get_current_user
from app.core.question_utils import question_to_response
from app.core.config import settings
from app.core.error_responses import ErrorMessages, raise_not_found

router = APIRouter()


@router.get("/unseen", response_model=UnseenQuestionsResponse)
async def get_unseen_questions(
    count: int = Query(
        default=settings.TEST_TOTAL_QUESTIONS,
        ge=1,
        le=100,
        description="Number of unseen questions to fetch (1-100)",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get unseen questions for the current user.

    This endpoint returns questions that the user has never seen before,
    filtered from the active question pool. Questions are selected to ensure
    no repetition for the user.

    Args:
        count: Number of questions to return (default: 25, max: 100)
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of unseen questions with metadata

    Raises:
        HTTPException: If insufficient questions are available
    """
    # Subquery to get question IDs the user has already seen
    seen_question_ids = (
        select(UserQuestion.question_id)
        .where(UserQuestion.user_id == current_user.id)
        .scalar_subquery()
    )

    # Query for active questions the user hasn't seen
    stmt = (
        select(Question)
        .where(
            and_(
                Question.is_active == True,  # noqa: E712
                ~Question.id.in_(seen_question_ids),
            )
        )
        .limit(count)
    )
    result = await db.execute(stmt)
    unseen_questions = result.scalars().all()

    # Check if we have enough questions
    if len(unseen_questions) < count:
        # This is a warning condition but not necessarily an error
        # We'll return what we have but log it
        # In a production app, you might want to alert if this happens
        pass

    if len(unseen_questions) == 0:
        raise_not_found(ErrorMessages.NO_QUESTIONS_AVAILABLE)

    # Convert to response schema (which excludes correct_answer and sensitive fields)
    questions_response = [
        question_to_response(q, include_explanation=False) for q in unseen_questions
    ]

    return UnseenQuestionsResponse(
        questions=questions_response,
        total_count=len(questions_response),
        requested_count=count,
    )
