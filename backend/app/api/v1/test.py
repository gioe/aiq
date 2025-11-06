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
from app.schemas.responses import ResponseSubmission, SubmitTestResponse
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
        .scalar_subquery()  # type: ignore[attr-defined]
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


@router.post("/submit", response_model=SubmitTestResponse)
def submit_test(
    submission: ResponseSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit responses for a test session.

    Validates and stores all user responses, compares them against correct
    answers, and marks the test session as completed.

    Args:
        submission: Response submission with session_id and responses
        current_user: Current authenticated user
        db: Database session

    Returns:
        Submission confirmation with updated session details

    Raises:
        HTTPException: If session not found, not authorized, already completed,
                      or validation fails
    """
    from app.models.models import Response

    # Fetch the test session
    test_session = (
        db.query(TestSession).filter(TestSession.id == submission.session_id).first()
    )

    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Verify session belongs to current user
    if test_session.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to submit for this test session"
        )

    # Verify session is still in progress
    if test_session.status != TestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Test session is already {test_session.status.value}. "
            "Cannot submit responses for a completed or abandoned session.",
        )

    # Validate that responses list is not empty
    if not submission.responses:
        raise HTTPException(status_code=400, detail="Response list cannot be empty")

    # Fetch all questions that were part of this test session
    # (questions seen by user at the time of session start)
    session_question_ids = (
        db.query(UserQuestion.question_id)
        .filter(
            UserQuestion.user_id == current_user.id,
            UserQuestion.seen_at >= test_session.started_at,
        )
        .all()
    )
    valid_question_ids = {q_id for (q_id,) in session_question_ids}

    # Validate all question_ids in submission belong to this session
    submitted_question_ids = {resp.question_id for resp in submission.responses}
    invalid_questions = submitted_question_ids - valid_question_ids

    if invalid_questions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid question IDs: {invalid_questions}. "
            "These questions do not belong to this test session.",
        )

    # Fetch questions to compare answers
    questions = db.query(Question).filter(Question.id.in_(submitted_question_ids)).all()
    questions_dict = {q.id: q for q in questions}

    # Process each response
    response_count = 0
    for resp_item in submission.responses:
        # Validate user_answer is not empty
        if not resp_item.user_answer or not resp_item.user_answer.strip():
            raise HTTPException(
                status_code=400,
                detail=f"User answer for question {resp_item.question_id} cannot be empty",
            )

        question = questions_dict.get(resp_item.question_id)  # type: ignore[call-overload]
        if not question:
            raise HTTPException(
                status_code=404,
                detail=f"Question {resp_item.question_id} not found",
            )

        # Compare user answer with correct answer (case-insensitive)
        is_correct = (
            resp_item.user_answer.strip().lower()
            == question.correct_answer.strip().lower()
        )

        # Create Response record
        response = Response(
            test_session_id=test_session.id,
            user_id=current_user.id,
            question_id=resp_item.question_id,
            user_answer=resp_item.user_answer.strip(),
            is_correct=is_correct,
            answered_at=datetime.utcnow(),
        )
        db.add(response)
        response_count += 1

    # Update test session status to completed
    test_session.status = TestStatus.COMPLETED  # type: ignore[assignment]
    test_session.completed_at = datetime.utcnow()  # type: ignore[assignment]

    # Commit all changes in a single transaction
    db.commit()
    db.refresh(test_session)

    return SubmitTestResponse(
        session=TestSessionResponse.model_validate(test_session),
        responses_count=response_count,
        message=f"Successfully submitted {response_count} responses",
    )
