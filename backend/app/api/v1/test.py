"""
Test session management endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.models import get_db, User, Question, TestSession, UserQuestion
from app.models.models import TestStatus
from app.schemas.test_sessions import (
    StartTestResponse,
    TestSessionResponse,
    TestSessionStatusResponse,
    TestSessionAbandonResponse,
)
from app.schemas.questions import QuestionResponse
from app.schemas.responses import (
    ResponseSubmission,
    SubmitTestResponse,
    TestResultResponse,
)
from app.core.auth import get_current_user
from app.core.scoring import calculate_iq_score, iq_to_percentile
from app.core.config import settings
from app.core.cache import invalidate_user_cache
from app.core.analytics import AnalyticsTracker
from app.core.question_analytics import update_question_statistics
from app.core.test_composition import select_stratified_questions

router = APIRouter()
logger = logging.getLogger(__name__)


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

    # Check 6-month test cadence: user cannot take another test within 180 days
    # of their last completed test
    cadence_cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.TEST_CADENCE_DAYS
    )
    recent_completed_session = (
        db.query(TestSession)
        .filter(
            TestSession.user_id == current_user.id,
            TestSession.status == TestStatus.COMPLETED,
            TestSession.completed_at > cadence_cutoff,
        )
        .order_by(TestSession.completed_at.desc())
        .first()
    )

    if recent_completed_session:
        # Calculate next eligible date
        next_eligible = recent_completed_session.completed_at + timedelta(
            days=settings.TEST_CADENCE_DAYS
        )
        days_remaining = (
            next_eligible - datetime.now(timezone.utc)
        ).days + 1  # Round up

        raise HTTPException(
            status_code=400,
            detail=f"You must wait {settings.TEST_CADENCE_DAYS} days (3 months) between tests. "
            f"Your last test was completed on {recent_completed_session.completed_at.strftime('%Y-%m-%d')}. "
            f"You can take your next test on {next_eligible.strftime('%Y-%m-%d')} "
            f"({days_remaining} days remaining).",
        )

    # P11-005: Use stratified question selection for balanced test composition
    unseen_questions, composition_metadata = select_stratified_questions(
        db=db,
        user_id=int(current_user.id),  # type: ignore
        total_count=question_count,
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

    # P11-006: Create new test session with composition metadata
    test_session = TestSession(
        user_id=current_user.id,
        status=TestStatus.IN_PROGRESS,
        started_at=datetime.now(timezone.utc),
        composition_metadata=composition_metadata,
    )
    db.add(test_session)
    db.flush()  # Get the session ID without committing yet

    # Mark questions as seen for this user
    for question in unseen_questions:
        user_question = UserQuestion(
            user_id=current_user.id,
            question_id=question.id,
            seen_at=datetime.now(timezone.utc),
        )
        db.add(user_question)

    db.commit()
    db.refresh(test_session)

    # Track analytics event
    AnalyticsTracker.track_test_started(
        user_id=int(current_user.id),  # type: ignore
        session_id=int(test_session.id),  # type: ignore
        question_count=len(unseen_questions),
    )

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


@router.post("/{session_id}/abandon", response_model=TestSessionAbandonResponse)
def abandon_test(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Abandon an in-progress test session.

    Marks the test session as abandoned without calculating results.
    Any responses saved during the test will be preserved but no
    test result will be created.

    Args:
        session_id: Test session ID to abandon
        current_user: Current authenticated user
        db: Database session

    Returns:
        Abandoned session details with response count

    Raises:
        HTTPException: If session not found, not authorized, or already completed
    """
    from app.models.models import Response

    # Fetch the test session
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Verify session belongs to current user
    if test_session.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to abandon this test session"
        )

    # Verify session is in progress
    if test_session.status != TestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Test session is already {test_session.status.value}. "  # type: ignore[attr-defined]
            "Only in-progress sessions can be abandoned.",
        )

    # Count any responses that were saved during the test
    responses_saved = (
        db.query(Response).filter(Response.test_session_id == session_id).count()
    )

    # Mark session as abandoned
    test_session.status = TestStatus.ABANDONED  # type: ignore[assignment]
    test_session.completed_at = datetime.now(timezone.utc)  # type: ignore[assignment]

    db.commit()
    db.refresh(test_session)

    # Track analytics event
    AnalyticsTracker.track_test_abandoned(
        user_id=int(current_user.id),  # type: ignore
        session_id=session_id,
        answered_count=responses_saved,
    )

    return TestSessionAbandonResponse(
        session=TestSessionResponse.model_validate(test_session),
        message="Test session abandoned successfully",
        responses_saved=responses_saved,
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
            detail=f"Test session is already {test_session.status.value}. "  # type: ignore[attr-defined]
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

    # Process each response and track correct answers
    response_count = 0
    correct_count = 0

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

        if is_correct:
            correct_count += 1

        # Create Response record
        response = Response(
            test_session_id=test_session.id,
            user_id=current_user.id,
            question_id=resp_item.question_id,
            user_answer=resp_item.user_answer.strip(),
            is_correct=is_correct,
            answered_at=datetime.now(timezone.utc),
        )
        db.add(response)
        response_count += 1

    # Update test session status to completed
    completion_time = datetime.now(timezone.utc)
    test_session.status = TestStatus.COMPLETED  # type: ignore[assignment]
    test_session.completed_at = completion_time  # type: ignore[assignment]

    # Calculate completion time in seconds
    time_delta = completion_time - test_session.started_at
    completion_time_seconds = int(time_delta.total_seconds())

    # Calculate IQ score using scoring module
    score_result = calculate_iq_score(
        correct_answers=correct_count, total_questions=response_count
    )

    # Calculate percentile rank
    percentile = iq_to_percentile(score_result.iq_score)

    # Create TestResult record
    from app.models.models import TestResult

    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=current_user.id,
        iq_score=score_result.iq_score,
        percentile_rank=percentile,
        total_questions=score_result.total_questions,
        correct_answers=score_result.correct_answers,
        completion_time_seconds=completion_time_seconds,
        completed_at=completion_time,
    )
    db.add(test_result)

    # Commit all changes in a single transaction
    db.commit()
    db.refresh(test_session)
    db.refresh(test_result)

    # Update question performance statistics (P11-009)
    # Track empirical difficulty and discrimination for each question
    try:
        update_question_statistics(db, int(test_session.id))  # type: ignore
    except Exception as e:
        # Log error but don't fail the submission
        logger.error(
            f"Failed to update question statistics for session {test_session.id}: {e}"
        )

    # Track analytics event
    AnalyticsTracker.track_test_completed(
        user_id=int(current_user.id),  # type: ignore
        session_id=int(test_session.id),  # type: ignore
        iq_score=score_result.iq_score,
        duration_seconds=completion_time_seconds,
        accuracy=score_result.accuracy_percentage,
    )

    # Invalidate user's cached data after test submission
    invalidate_user_cache(int(current_user.id))  # type: ignore[arg-type]

    # Build response with test result
    result_response = TestResultResponse(
        id=test_result.id,  # type: ignore[arg-type]
        test_session_id=test_result.test_session_id,  # type: ignore[arg-type]
        user_id=test_result.user_id,  # type: ignore[arg-type]
        iq_score=test_result.iq_score,  # type: ignore[arg-type]
        percentile_rank=test_result.percentile_rank,  # type: ignore[arg-type]
        total_questions=test_result.total_questions,  # type: ignore[arg-type]
        correct_answers=test_result.correct_answers,  # type: ignore[arg-type]
        accuracy_percentage=score_result.accuracy_percentage,
        completion_time_seconds=test_result.completion_time_seconds,  # type: ignore[arg-type]
        completed_at=test_result.completed_at,  # type: ignore[arg-type]
    )

    return SubmitTestResponse(
        session=TestSessionResponse.model_validate(test_session),
        result=result_response,
        responses_count=response_count,
        message=f"Test completed! IQ Score: {score_result.iq_score}",
    )


@router.get("/results/{result_id}", response_model=TestResultResponse)
def get_test_result(
    result_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get a specific test result by ID.

    Args:
        result_id: Test result ID
        current_user: Current authenticated user
        db: Database session

    Returns:
        Test result details with IQ score

    Raises:
        HTTPException: If result not found or doesn't belong to user
    """
    from app.models.models import TestResult

    # Fetch the test result
    test_result = db.query(TestResult).filter(TestResult.id == result_id).first()

    if not test_result:
        raise HTTPException(status_code=404, detail="Test result not found")

    # Verify result belongs to current user
    if test_result.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this test result"
        )

    # Calculate accuracy percentage
    accuracy_percentage: float = (
        (float(test_result.correct_answers) / float(test_result.total_questions))
        * 100.0
        if test_result.total_questions > 0
        else 0.0
    )

    return TestResultResponse(
        id=test_result.id,  # type: ignore[arg-type]
        test_session_id=test_result.test_session_id,  # type: ignore[arg-type]
        user_id=test_result.user_id,  # type: ignore[arg-type]
        iq_score=test_result.iq_score,  # type: ignore[arg-type]
        percentile_rank=test_result.percentile_rank,  # type: ignore[arg-type]
        total_questions=test_result.total_questions,  # type: ignore[arg-type]
        correct_answers=test_result.correct_answers,  # type: ignore[arg-type]
        accuracy_percentage=accuracy_percentage,
        completion_time_seconds=test_result.completion_time_seconds,  # type: ignore[arg-type]
        completed_at=test_result.completed_at,  # type: ignore[arg-type]
    )


@router.get("/history", response_model=list[TestResultResponse])
def get_test_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get all historical test results for the current user.

    Results are returned in reverse chronological order (most recent first).

    Args:
        current_user: Current authenticated user
        db: Database session

    Returns:
        List of test results ordered by completion date (newest first)
    """
    from app.models.models import TestResult

    # Fetch all test results for the user, ordered by completion date
    test_results = (
        db.query(TestResult)
        .filter(TestResult.user_id == current_user.id)
        .order_by(TestResult.completed_at.desc())
        .all()
    )

    # Convert to response format
    results_response = []
    for test_result in test_results:
        accuracy_percentage: float = (
            (float(test_result.correct_answers) / float(test_result.total_questions))
            * 100.0
            if test_result.total_questions > 0
            else 0.0
        )

        results_response.append(
            TestResultResponse(
                id=test_result.id,  # type: ignore[arg-type]
                test_session_id=test_result.test_session_id,  # type: ignore[arg-type]
                user_id=test_result.user_id,  # type: ignore[arg-type]
                iq_score=test_result.iq_score,  # type: ignore[arg-type]
                percentile_rank=test_result.percentile_rank,  # type: ignore[arg-type]
                total_questions=test_result.total_questions,  # type: ignore[arg-type]
                correct_answers=test_result.correct_answers,  # type: ignore[arg-type]
                accuracy_percentage=accuracy_percentage,
                completion_time_seconds=test_result.completion_time_seconds,  # type: ignore[arg-type]
                completed_at=test_result.completed_at,  # type: ignore[arg-type]
            )
        )

    return results_response
