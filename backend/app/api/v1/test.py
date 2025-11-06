"""
Test session management endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from typing import Optional

from app.models import get_db, User, Question, TestSession, UserQuestion
from app.models.models import TestStatus
from app.schemas.test_sessions import (
    StartTestResponse,
    TestSessionResponse,
    TestSessionStatusResponse,
)
from app.schemas.questions import QuestionResponse
from app.core.auth import get_current_user

router = APIRouter()


@router.post("/start", response_model=StartTestResponse)
def start_test(
    question_count: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Number of questions for this test (1-100)",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Start a new test session for the current user.

    Creates a new test session, fetches unseen questions, and marks them
    as seen for the user. Returns the session details and questions.

    Args:
        question_count: Number of questions to include in test
        current_user: Current authenticated user
        db: Database session

    Returns:
        Test session and questions

    Raises:
        HTTPException: If user has active test or insufficient questions
    """
    # Check if user already has an active (in_progress) test session
    active_session = (
        db.query(TestSession)
        .filter(
            TestSession.user_id == current_user.id,
            TestSession.status == TestStatus.IN_PROGRESS,
        )
        .first()
    )

    if active_session:
        raise HTTPException(
            status_code=400,
            detail=f"User already has an active test session (ID: {active_session.id}). "
            "Please complete or abandon the existing session before starting a new one.",
        )

    # Fetch unseen questions
    seen_question_ids = (
        select(UserQuestion.question_id)  # type: ignore[arg-type]
        .where(UserQuestion.user_id == current_user.id)
        .scalar_subquery()
    )

    unseen_questions = (
        db.query(Question)
        .filter(
            Question.is_active == True,  # noqa: E712
            ~Question.id.in_(seen_question_ids),
        )
        .limit(question_count)
        .all()
    )

    if len(unseen_questions) == 0:
        raise HTTPException(
            status_code=404,
            detail="No unseen questions available. Question pool may be exhausted.",
        )

    if len(unseen_questions) < question_count:
        # Warning: fewer questions available than requested
        # For MVP, we'll proceed with whatever questions we have
        pass

    # Create new test session
    test_session = TestSession(
        user_id=current_user.id,
        status=TestStatus.IN_PROGRESS,
        started_at=datetime.utcnow(),
    )
    db.add(test_session)
    db.flush()  # Get the session ID without committing yet

    # Mark questions as seen for this user
    for question in unseen_questions:
        user_question = UserQuestion(
            user_id=current_user.id,
            question_id=question.id,
            seen_at=datetime.utcnow(),
        )
        db.add(user_question)

    db.commit()
    db.refresh(test_session)

    # Convert questions to response format
    questions_response = [
        QuestionResponse.model_validate(q).model_copy(update={"explanation": None})
        for q in unseen_questions
    ]

    return StartTestResponse(
        session=TestSessionResponse.model_validate(test_session),
        questions=questions_response,
        total_questions=len(questions_response),
    )


@router.get("/session/{session_id}", response_model=TestSessionStatusResponse)
def get_test_session(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get details for a specific test session.

    Args:
        session_id: Test session ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Test session details

    Raises:
        HTTPException: If session not found or doesn't belong to user
    """
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Verify session belongs to current user
    if test_session.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this test session"
        )

    # Count responses for this session
    from app.models.models import Response

    questions_count = (
        db.query(Response).filter(Response.test_session_id == session_id).count()
    )

    return TestSessionStatusResponse(
        session=TestSessionResponse.model_validate(test_session),
        questions_count=questions_count,
    )


@router.get("/active", response_model=Optional[TestSessionStatusResponse])
def get_active_test_session(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the user's active (in_progress) test session if any.

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        Active test session or None
    """
    active_session = (
        db.query(TestSession)
        .filter(
            TestSession.user_id == current_user.id,
            TestSession.status == TestStatus.IN_PROGRESS,
        )
        .first()
    )

    if not active_session:
        return None

    # Count responses for this session
    from app.models.models import Response

    questions_count = (
        db.query(Response).filter(Response.test_session_id == active_session.id).count()
    )

    return TestSessionStatusResponse(
        session=TestSessionResponse.model_validate(active_session),
        questions_count=questions_count,
    )
