"""
Test session management endpoints.
"""
import logging
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from typing import Optional, TypedDict, TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.models import Response as ResponseModel

from app.core.datetime_utils import ensure_timezone_aware, utc_now

from app.models import get_db, User, Question, TestSession, UserQuestion
from app.models.models import TestStatus
from app.core.error_responses import (
    ErrorMessages,
    raise_bad_request,
    raise_forbidden,
    raise_not_found,
    raise_conflict,
)
from app.schemas.test_sessions import (
    StartTestResponse,
    TestSessionResponse,
    TestSessionStatusResponse,
    TestSessionAbandonResponse,
)
from app.schemas.responses import (
    ResponseSubmission,
    SubmitTestResponse,
    TestResultResponse,
    ConfidenceIntervalSchema,
    PaginatedTestHistoryResponse,
    DEFAULT_HISTORY_PAGE_SIZE,
    MAX_HISTORY_PAGE_SIZE,
)
from app.core.auth import get_current_user
from app.core.scoring import (
    calculate_iq_score,
    calculate_weighted_iq_score,
    iq_to_percentile,
    calculate_domain_scores,
    calculate_all_domain_percentiles,
    get_strongest_weakest_domains,
    get_cached_reliability,
    calculate_sem,
    calculate_confidence_interval,
)
from app.core.system_config import (
    is_weighted_scoring_enabled,
    get_domain_weights,
    get_domain_population_stats,
)
from app.core.time_analysis import analyze_response_times, get_session_time_summary
from app.core.config import settings
from app.core.cache import invalidate_user_cache
from app.core.reliability import invalidate_reliability_report_cache
from app.core.analytics import AnalyticsTracker
from app.core.question_analytics import update_question_statistics
from app.core.test_composition import select_stratified_questions
from app.core.distractor_analysis import (
    update_distractor_stats,
    update_session_quartile_stats,
)
from app.core.question_utils import question_to_response
from app.core.validity_analysis import (
    calculate_person_fit_heuristic,
    check_response_time_plausibility,
    count_guttman_errors,
    assess_session_validity,
)
from app.core.graceful_failure import graceful_failure

router = APIRouter()
logger = logging.getLogger(__name__)

# Standard confidence level used for all IQ score confidence intervals
# 95% is the psychometric standard for reporting measurement uncertainty
CONFIDENCE_INTERVAL_LEVEL = 0.95


def get_session_questions(
    db: Session, user_id: int, session_id: int, include_explanation: bool = False
) -> list:
    """
    Fetch questions for a specific test session.

    Args:
        db: Database session
        user_id: User ID
        session_id: Test session ID
        include_explanation: Whether to include explanations in response

    Returns:
        List of questions in response format
    """
    session_question_ids = (
        db.query(UserQuestion.question_id)
        .filter(
            UserQuestion.user_id == user_id,
            UserQuestion.test_session_id == session_id,
        )
        .all()
    )
    question_ids = [q_id for (q_id,) in session_question_ids]

    if not question_ids:
        return []

    # Fetch questions in the order they were saved
    ordering = case(
        {id: index for index, id in enumerate(question_ids)}, value=Question.id
    )
    questions = (
        db.query(Question)
        .filter(Question.id.in_(question_ids))
        .order_by(ordering)
        .all()
    )

    return [
        question_to_response(q, include_explanation=include_explanation)
        for q in questions
    ]


def count_session_responses(db: Session, session_id: int) -> int:
    """
    Count the number of responses for a test session.

    Args:
        db: Database session
        session_id: Test session ID

    Returns:
        Number of responses
    """
    from app.models.models import Response

    return db.query(Response).filter(Response.test_session_id == session_id).count()


def verify_session_ownership(test_session: TestSession, user_id: int) -> None:
    """
    Verify that a test session belongs to the specified user.

    Args:
        test_session: Test session to verify
        user_id: Expected user ID

    Raises:
        HTTPException: If session doesn't belong to user
    """
    if test_session.user_id != user_id:
        raise_forbidden(ErrorMessages.SESSION_ACCESS_DENIED)


def verify_session_in_progress(test_session: TestSession) -> None:
    """
    Verify that a test session is in progress.

    Args:
        test_session: Test session to verify

    Raises:
        HTTPException: If session is not in progress
    """
    if test_session.status != TestStatus.IN_PROGRESS:
        raise_bad_request(
            ErrorMessages.session_already_completed(test_session.status.value)
        )


def get_test_session_or_404(db: Session, session_id: int) -> TestSession:
    """
    Fetch a test session by ID or raise 404 if not found.

    This helper centralizes the common pattern of fetching a test session
    and raising HTTPException with 404 status if the session doesn't exist.

    Args:
        db: Database session
        session_id: Test session ID to fetch

    Returns:
        TestSession if found

    Raises:
        HTTPException: 404 if test session not found
    """
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not test_session:
        raise_not_found(ErrorMessages.TEST_SESSION_NOT_FOUND)

    return test_session


def build_test_result_response(
    test_result,
    db: Optional[Session] = None,
    population_stats: Optional[dict[str, dict[str, float]]] = None,
) -> TestResultResponse:
    """
    Build a TestResultResponse from a TestResult model.

    Args:
        test_result: TestResult model instance
        db: Optional database session for fetching population stats.
            If provided and population_stats is None, stats will be fetched.
        population_stats: Optional pre-fetched population stats. Pass this when
            building multiple responses to avoid N+1 queries.

    Returns:
        TestResultResponse with calculated accuracy percentage, domain percentiles,
        and strongest/weakest domain identification.
    """
    accuracy_percentage: float = (
        (float(test_result.correct_answers) / float(test_result.total_questions))
        * 100.0
        if test_result.total_questions > 0
        else 0.0
    )

    # DW-016: Calculate domain percentiles and identify strongest/weakest domains
    domain_scores = test_result.domain_scores
    strongest_domain: Optional[str] = None
    weakest_domain: Optional[str] = None

    if domain_scores:
        # Get strongest and weakest domains based on accuracy
        domain_analysis = get_strongest_weakest_domains(domain_scores)
        strongest_domain = domain_analysis.get("strongest_domain")
        weakest_domain = domain_analysis.get("weakest_domain")

        # Fetch population stats if not provided and db is available
        if population_stats is None and db is not None:
            population_stats = get_domain_population_stats(db)

        # Calculate domain percentiles if we have population stats
        if population_stats:
            domain_percentiles = calculate_all_domain_percentiles(
                domain_scores, population_stats
            )
            # Enrich domain_scores with percentile data
            for domain, percentile in domain_percentiles.items():
                if domain in domain_scores:
                    domain_scores[domain]["percentile"] = percentile

    # SEM-005: Build confidence interval from stored SEM and CI bounds
    # CI is only populated when reliability data was sufficient (>= 0.60)
    confidence_interval: Optional[ConfidenceIntervalSchema] = None
    if (
        test_result.standard_error is not None
        and test_result.ci_lower is not None
        and test_result.ci_upper is not None
    ):
        confidence_interval = ConfidenceIntervalSchema(
            lower=test_result.ci_lower,
            upper=test_result.ci_upper,
            confidence_level=CONFIDENCE_INTERVAL_LEVEL,
            standard_error=test_result.standard_error,
        )

    return TestResultResponse(
        id=test_result.id,
        test_session_id=test_result.test_session_id,
        user_id=test_result.user_id,
        iq_score=test_result.iq_score,
        percentile_rank=test_result.percentile_rank,
        total_questions=test_result.total_questions,
        correct_answers=test_result.correct_answers,
        accuracy_percentage=accuracy_percentage,
        completion_time_seconds=test_result.completion_time_seconds,
        completed_at=test_result.completed_at,
        response_time_flags=test_result.response_time_flags,
        domain_scores=domain_scores,
        strongest_domain=strongest_domain,
        weakest_domain=weakest_domain,
        confidence_interval=confidence_interval,
    )


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

    Note:
        Active Session Prevention Strategy (BCQ-045):
        This endpoint uses a dual-check pattern to prevent duplicate active sessions:

        1. Application-level check (below): Queries for existing active session BEFORE
           creating a new one. Returns HTTP 400 with session_id in error message,
           allowing clients to offer "Resume existing session" functionality.

        2. Database-level check (in db.flush()): The partial unique index
           ix_test_sessions_user_active catches race conditions when two requests
           pass the app-level check simultaneously. Returns HTTP 409 without
           session_id (unavailable due to rollback).

        Both checks are intentionally kept because:
        - App-level provides better UX (session_id for recovery options)
        - DB-level is a last-resort safeguard for race conditions
        - The DB constraint guarantees correctness even if app logic is bypassed
    """
    # BCQ-045: Application-level active session check (provides session_id for UX)
    # See docstring "Active Session Prevention Strategy" for why both checks exist
    active_session = (
        db.query(TestSession)
        .filter(
            TestSession.user_id == current_user.id,
            TestSession.status == TestStatus.IN_PROGRESS,
        )
        .first()
    )

    if active_session:
        raise_bad_request(ErrorMessages.active_session_exists(active_session.id))

    # Check 6-month test cadence: user cannot take another test within 180 days
    # of their last completed test
    cadence_cutoff = utc_now() - timedelta(days=settings.TEST_CADENCE_DAYS)
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
        completed_at = ensure_timezone_aware(recent_completed_session.completed_at)
        next_eligible = completed_at + timedelta(days=settings.TEST_CADENCE_DAYS)
        days_remaining = (next_eligible - utc_now()).days + 1  # Round up

        raise_bad_request(
            ErrorMessages.test_cadence_not_met(
                cadence_days=settings.TEST_CADENCE_DAYS,
                last_completed=completed_at.strftime("%Y-%m-%d"),
                next_eligible=next_eligible.strftime("%Y-%m-%d"),
                days_remaining=days_remaining,
            )
        )

    # P11-005: Use stratified question selection for balanced test composition
    unseen_questions, composition_metadata = select_stratified_questions(
        db=db,
        user_id=current_user.id,
        total_count=question_count,
    )

    if len(unseen_questions) == 0:
        raise_not_found(ErrorMessages.NO_QUESTIONS_AVAILABLE)

    if len(unseen_questions) < question_count:
        # Warning: fewer questions available than requested
        # For MVP, we'll proceed with whatever questions we have
        pass

    # P11-006: Create new test session with composition metadata
    test_session = TestSession(
        user_id=current_user.id,
        status=TestStatus.IN_PROGRESS,
        started_at=utc_now(),
        composition_metadata=composition_metadata,
    )
    db.add(test_session)

    try:
        db.flush()  # Get the session ID without committing yet
    except IntegrityError:
        # BCQ-006/BCQ-045: Database-level race condition prevention
        # This catches the rare case where two requests pass the app-level check
        # simultaneously. Returns 409 without session_id (lost due to rollback).
        # See docstring "Active Session Prevention Strategy" for full explanation.
        db.rollback()
        logger.warning(
            f"Race condition detected: user {current_user.id} attempted to start "
            "multiple test sessions concurrently"
        )
        raise_conflict(ErrorMessages.SESSION_ALREADY_IN_PROGRESS)

    # Mark questions as seen for this user
    for question in unseen_questions:
        user_question = UserQuestion(
            user_id=current_user.id,
            question_id=question.id,
            test_session_id=test_session.id,
            seen_at=utc_now(),
        )
        db.add(user_question)

    db.commit()
    db.refresh(test_session)

    # Track analytics event
    AnalyticsTracker.track_test_started(
        user_id=current_user.id,
        session_id=test_session.id,
        question_count=len(unseen_questions),
    )

    # Convert questions to response format
    questions_response = [
        question_to_response(q, include_explanation=False) for q in unseen_questions
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
        Test session details with questions (if session is in_progress)

    Raises:
        HTTPException: If session not found or doesn't belong to user
    """
    test_session = get_test_session_or_404(db, session_id)

    # Verify session belongs to current user
    verify_session_ownership(test_session, current_user.id)

    # Count responses for this session
    questions_count = count_session_responses(db, session_id)

    # If session is in_progress, retrieve the questions for this session
    questions_response = None
    if test_session.status == TestStatus.IN_PROGRESS:
        questions_response = get_session_questions(
            db, current_user.id, session_id, include_explanation=False
        )

    return TestSessionStatusResponse(
        session=TestSessionResponse.model_validate(test_session),
        questions_count=questions_count,
        questions=questions_response,
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
    questions_count = count_session_responses(db, active_session.id)

    # Get questions for the active session
    questions_response = get_session_questions(
        db, current_user.id, active_session.id, include_explanation=False
    )

    return TestSessionStatusResponse(
        session=TestSessionResponse.model_validate(active_session),
        questions_count=questions_count,
        questions=questions_response,
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
    test_session = get_test_session_or_404(db, session_id)

    # Verify session belongs to current user
    verify_session_ownership(test_session, current_user.id)

    # Verify session is in progress
    verify_session_in_progress(test_session)

    # Count any responses that were saved during the test
    responses_saved = count_session_responses(db, session_id)

    # Mark session as abandoned
    test_session.status = TestStatus.ABANDONED
    test_session.completed_at = utc_now()

    db.commit()
    db.refresh(test_session)

    # Track analytics event
    AnalyticsTracker.track_test_abandoned(
        user_id=current_user.id,
        session_id=session_id,
        answered_count=responses_saved,
    )

    return TestSessionAbandonResponse(
        session=TestSessionResponse.model_validate(test_session),
        message="Test session abandoned successfully",
        responses_saved=responses_saved,
    )


# =============================================================================
# Submit Test Helper Functions (BCQ-020)
# =============================================================================
# The following helper functions extract logical sections from submit_test()
# to improve readability and maintainability. Each function handles one
# responsibility in the test submission flow.
# =============================================================================


class SubmissionValidationResult(TypedDict):
    """Result of validating a test submission."""

    test_session: TestSession
    questions_dict: dict
    submitted_question_ids: set


class ResponseProcessingResult(TypedDict):
    """Result of processing responses."""

    response_count: int
    correct_count: int
    response_objects: list


class ValidityAnalysisResult(TypedDict):
    """Result of validity analysis."""

    validity_status: str
    validity_flags: Optional[list]
    validity_checked_at: Optional[datetime]


class SEMCalculationResult(TypedDict):
    """Result of SEM and confidence interval calculation."""

    standard_error: Optional[float]
    ci_lower: Optional[int]
    ci_upper: Optional[int]


# Time limit for test completion in seconds (30 minutes)
TIME_LIMIT_SECONDS = 1800


def _validate_submission(
    db: Session,
    submission: ResponseSubmission,
    user_id: int,
) -> SubmissionValidationResult:
    """
    Validate a test submission request.

    Verifies the test session exists, belongs to the user, is in progress,
    has responses, and all question IDs are valid for this session.

    Args:
        db: Database session
        submission: Response submission with session_id and responses
        user_id: Current user's ID

    Returns:
        SubmissionValidationResult with session, questions dict, and question IDs

    Raises:
        HTTPException: If validation fails
    """
    test_session = get_test_session_or_404(db, submission.session_id)

    # Verify session belongs to current user
    verify_session_ownership(test_session, user_id)

    # Verify session is still in progress
    verify_session_in_progress(test_session)

    # Validate that responses list is not empty
    if not submission.responses:
        raise_bad_request(ErrorMessages.EMPTY_RESPONSE_LIST)

    # Fetch all questions that were part of this test session
    # (questions seen by user at the time of session start)
    session_question_ids = (
        db.query(UserQuestion.question_id)
        .filter(
            UserQuestion.user_id == user_id,
            UserQuestion.seen_at >= test_session.started_at,
        )
        .all()
    )
    valid_question_ids = {q_id for (q_id,) in session_question_ids}

    # Validate all question_ids in submission belong to this session
    submitted_question_ids = {resp.question_id for resp in submission.responses}
    invalid_questions = submitted_question_ids - valid_question_ids

    if invalid_questions:
        raise_bad_request(ErrorMessages.invalid_question_ids(invalid_questions))

    # Fetch questions to compare answers
    questions = db.query(Question).filter(Question.id.in_(submitted_question_ids)).all()
    questions_dict = {q.id: q for q in questions}

    return {
        "test_session": test_session,
        "questions_dict": questions_dict,
        "submitted_question_ids": submitted_question_ids,
    }


def _process_responses(
    db: Session,
    submission: ResponseSubmission,
    test_session: TestSession,
    user_id: int,
    questions_dict: dict[int, Question],
) -> ResponseProcessingResult:
    """
    Process and store all responses for a test submission.

    Validates each answer, determines correctness, creates Response records,
    and updates distractor statistics.

    Args:
        db: Database session
        submission: Response submission with responses list
        test_session: The test session being submitted
        user_id: Current user's ID
        questions_dict: Dictionary mapping question IDs to Question objects

    Returns:
        ResponseProcessingResult with counts and response objects

    Raises:
        HTTPException: If a response validation fails
    """
    from app.models.models import Response

    response_count = 0
    correct_count = 0
    response_objects: list[Response] = []

    for resp_item in submission.responses:
        # Validate user_answer is not empty
        if not resp_item.user_answer or not resp_item.user_answer.strip():
            raise_bad_request(ErrorMessages.empty_answer(resp_item.question_id))

        question = questions_dict.get(resp_item.question_id)
        if not question:
            raise_not_found(ErrorMessages.question_not_found(resp_item.question_id))

        # Compare user answer with correct answer (case-insensitive)
        is_correct = (
            resp_item.user_answer.strip().lower()
            == question.correct_answer.strip().lower()
        )

        if is_correct:
            correct_count += 1

        # Create Response record with optional time tracking (TS-003)
        response = Response(
            test_session_id=test_session.id,
            user_id=user_id,
            question_id=resp_item.question_id,
            user_answer=resp_item.user_answer.strip(),
            is_correct=is_correct,
            answered_at=utc_now(),
            time_spent_seconds=resp_item.time_spent_seconds,
        )
        db.add(response)
        response_objects.append(response)
        response_count += 1

        # DA-006: Update distractor statistics for multiple-choice questions
        # Graceful degradation: failures are logged but don't block response recording
        with graceful_failure(
            f"update distractor stats for question {resp_item.question_id}",
            logger,
        ):
            update_distractor_stats(
                db=db,
                question_id=resp_item.question_id,
                selected_answer=resp_item.user_answer.strip(),
            )

    return {
        "response_count": response_count,
        "correct_count": correct_count,
        "response_objects": response_objects,
    }


def _complete_session_and_calculate_score(
    db: Session,
    test_session: TestSession,
    submission: ResponseSubmission,
    response_objects: list["ResponseModel"],
    questions_dict: dict[int, Question],
    correct_count: int,
    response_count: int,
) -> tuple:
    """
    Mark session as complete and calculate IQ score.

    Updates session status, calculates completion time, checks time limit,
    calculates domain scores and IQ score (weighted or standard).

    Args:
        db: Database session
        test_session: Test session to complete
        submission: Original submission for time limit flag
        response_objects: List of Response objects for domain scoring
        questions_dict: Dictionary of questions for domain scoring
        correct_count: Number of correct answers
        response_count: Total number of responses

    Returns:
        Tuple of (completion_time, completion_time_seconds, domain_scores,
                  score_result, percentile)
    """
    # Update test session status to completed
    completion_time = utc_now()
    test_session.status = TestStatus.COMPLETED
    test_session.completed_at = completion_time

    # Calculate completion time in seconds
    started_at = ensure_timezone_aware(test_session.started_at)
    time_delta = completion_time - started_at
    completion_time_seconds = int(time_delta.total_seconds())

    # TS-003/TS-010: Flag if time limit was exceeded
    if submission.time_limit_exceeded or completion_time_seconds > TIME_LIMIT_SECONDS:
        test_session.time_limit_exceeded = True
        logger.info(
            f"Test session {test_session.id} exceeded time limit: "
            f"client_reported={submission.time_limit_exceeded}, "
            f"server_detected={completion_time_seconds > TIME_LIMIT_SECONDS} "
            f"({completion_time_seconds}s)"
        )

    # DW-003: Calculate domain-specific performance breakdown
    domain_scores = calculate_domain_scores(response_objects, questions_dict)

    # DW-014: Calculate IQ score using weighted or equal weights based on config
    use_weighted = is_weighted_scoring_enabled(db)
    domain_weights = get_domain_weights(db) if use_weighted else None

    if use_weighted and domain_weights:
        score_result = calculate_weighted_iq_score(
            domain_scores=domain_scores,
            weights=domain_weights,
        )
        logger.info(
            f"Test session {test_session.id}: Using weighted scoring with weights={domain_weights}"
        )
    else:
        score_result = calculate_iq_score(
            correct_answers=correct_count, total_questions=response_count
        )
        if use_weighted and not domain_weights:
            logger.warning(
                f"Test session {test_session.id}: Weighted scoring enabled but no weights configured, "
                "falling back to equal weights"
            )

    # Calculate percentile rank
    percentile = iq_to_percentile(score_result.iq_score)

    return (
        completion_time,
        completion_time_seconds,
        domain_scores,
        score_result,
        percentile,
    )


def _analyze_response_times(db: Session, session_id: int) -> Optional[dict]:
    """
    Analyze response times for anomaly detection.

    Args:
        db: Database session
        session_id: Test session ID

    Returns:
        Response time flags dictionary or None if analysis fails
    """
    response_time_flags = None
    with graceful_failure(
        f"analyze response times for session {session_id}",
        logger,
        log_level=logging.ERROR,
    ):
        time_analysis = analyze_response_times(db, session_id)
        response_time_flags = get_session_time_summary(time_analysis)

        if response_time_flags.get("validity_concern"):
            logger.info(
                f"Test session {session_id} has validity concerns: "
                f"flags={response_time_flags.get('flags')}"
            )

    return response_time_flags


def _run_validity_analysis(
    session_id: int,
    submission: ResponseSubmission,
    questions_dict: dict[int, Question],
    correct_count: int,
) -> ValidityAnalysisResult:
    """
    Run validity analysis to detect aberrant response patterns.

    Combines person-fit, response time plausibility, and Guttman error checks
    to identify potential cheating or invalid test-taking behavior.

    Args:
        session_id: Test session ID for logging
        submission: Response submission with responses
        questions_dict: Dictionary of questions
        correct_count: Number of correct answers

    Returns:
        ValidityAnalysisResult with status, flags, and timestamp
    """
    validity_status = "valid"
    validity_flags = None
    validity_checked_at = None

    with graceful_failure(
        f"run validity analysis for session {session_id}",
        logger,
        log_level=logging.ERROR,
        exc_info=True,
    ):
        # Prepare data for validity analysis
        # Person-fit needs: (is_correct, difficulty_level) tuples
        person_fit_data: list[tuple[bool, str]] = []
        time_check_data: list[dict[str, object]] = []
        guttman_data: list[tuple[bool, float]] = []

        for resp_item in submission.responses:
            question = questions_dict.get(resp_item.question_id)
            if question is None:
                continue

            is_correct = (
                resp_item.user_answer.strip().lower()
                == question.correct_answer.strip().lower()
            )
            difficulty = (
                question.difficulty_level.value
                if question.difficulty_level
                else "medium"
            )

            person_fit_data.append((is_correct, difficulty))
            time_check_data.append(
                {
                    "time_seconds": resp_item.time_spent_seconds,
                    "is_correct": is_correct,
                    "difficulty": difficulty,
                }
            )

            if question.empirical_difficulty is not None:
                guttman_data.append((is_correct, question.empirical_difficulty))

        # Run individual validity checks
        person_fit_result = calculate_person_fit_heuristic(
            responses=person_fit_data, total_score=correct_count
        )
        time_check_result = check_response_time_plausibility(responses=time_check_data)
        guttman_result = count_guttman_errors(responses=guttman_data)

        # Combine into overall validity assessment
        validity_assessment = assess_session_validity(
            person_fit=person_fit_result,
            time_check=time_check_result,
            guttman_check=guttman_result,
        )

        # Extract results for storage
        validity_status = validity_assessment["validity_status"]
        validity_flags = (
            validity_assessment["flag_details"]
            if validity_assessment["flag_details"]
            else None
        )
        validity_checked_at = utc_now()

        # Log validity assessment results
        if validity_status != "valid":
            logger.warning(
                f"Test session {session_id} validity assessment: "
                f"status={validity_status}, severity={validity_assessment['severity_score']}, "
                f"flags={[f['type'] for f in validity_assessment['flag_details']]}"
            )
        else:
            logger.info(
                f"Test session {session_id} passed validity checks: "
                f"confidence={validity_assessment['confidence']}"
            )

    return {
        "validity_status": validity_status,
        "validity_flags": validity_flags,
        "validity_checked_at": validity_checked_at,
    }


def _calculate_sem_and_ci(
    db: Session, session_id: int, iq_score: int
) -> SEMCalculationResult:
    """
    Calculate Standard Error of Measurement and confidence interval.

    Args:
        db: Database session
        session_id: Test session ID for logging
        iq_score: The calculated IQ score

    Returns:
        SEMCalculationResult with standard error and CI bounds
    """
    standard_error: Optional[float] = None
    ci_lower: Optional[int] = None
    ci_upper: Optional[int] = None

    with graceful_failure(
        f"calculate SEM for session {session_id}",
        logger,
    ):
        # Get cached reliability coefficient (Cronbach's alpha)
        reliability = get_cached_reliability(db)

        if reliability is not None:
            standard_error = calculate_sem(reliability)
            ci_lower, ci_upper = calculate_confidence_interval(
                score=iq_score,
                sem=standard_error,
                confidence_level=CONFIDENCE_INTERVAL_LEVEL,
            )

            logger.info(
                f"Test session {session_id}: SEM calculation successful - "
                f"reliability={reliability:.3f}, SEM={standard_error:.2f}, "
                f"CI=[{ci_lower}, {ci_upper}]"
            )
        else:
            logger.info(
                f"Test session {session_id}: SEM calculation skipped - "
                "insufficient data or reliability below threshold (< 0.60)"
            )

    return {
        "standard_error": standard_error,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }


def _run_post_submission_updates(
    db: Session,
    session_id: int,
    correct_count: int,
    response_count: int,
) -> None:
    """
    Run post-submission updates for question statistics and distractor analysis.

    These are non-critical operations that run after the main submission is committed.

    Args:
        db: Database session
        session_id: Test session ID
        correct_count: Number of correct answers
        response_count: Total number of responses
    """
    # Update question performance statistics (P11-009)
    with graceful_failure(
        f"update question statistics for session {session_id}",
        logger,
        log_level=logging.ERROR,
    ):
        update_question_statistics(db, session_id)

    # DA-007: Update quartile-based distractor stats after test completion
    with graceful_failure(
        f"update distractor quartile stats for session {session_id}",
        logger,
    ):
        update_session_quartile_stats(
            db=db,
            test_session_id=session_id,
            correct_answers=correct_count,
            total_questions=response_count,
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
    from app.models.models import TestResult

    user_id = current_user.id

    # Step 1: Validate submission
    validation_result = _validate_submission(db, submission, user_id)
    test_session = validation_result["test_session"]
    questions_dict = validation_result["questions_dict"]

    # Step 2: Process responses
    processing_result = _process_responses(
        db, submission, test_session, user_id, questions_dict
    )
    response_count = processing_result["response_count"]
    correct_count = processing_result["correct_count"]
    response_objects = processing_result["response_objects"]

    # Step 3: Complete session and calculate score
    (
        completion_time,
        completion_time_seconds,
        domain_scores,
        score_result,
        percentile,
    ) = _complete_session_and_calculate_score(
        db,
        test_session,
        submission,
        response_objects,
        questions_dict,
        correct_count,
        response_count,
    )

    # Step 4: Analyze response times
    response_time_flags = _analyze_response_times(db, test_session.id)

    # Step 5: Run validity analysis
    validity_result = _run_validity_analysis(
        test_session.id,
        submission,
        questions_dict,
        correct_count,
    )

    # Step 6: Calculate SEM and confidence interval
    sem_result = _calculate_sem_and_ci(db, test_session.id, score_result.iq_score)

    # Step 7: Create TestResult record
    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=user_id,
        iq_score=score_result.iq_score,
        percentile_rank=percentile,
        total_questions=score_result.total_questions,
        correct_answers=score_result.correct_answers,
        completion_time_seconds=completion_time_seconds,
        completed_at=completion_time,
        response_time_flags=response_time_flags,
        domain_scores=domain_scores,
        validity_status=validity_result["validity_status"],
        validity_flags=validity_result["validity_flags"],
        validity_checked_at=validity_result["validity_checked_at"],
        standard_error=sem_result["standard_error"],
        ci_lower=sem_result["ci_lower"],
        ci_upper=sem_result["ci_upper"],
    )
    db.add(test_result)

    # Step 8: Commit all changes
    db.commit()
    db.refresh(test_session)
    db.refresh(test_result)

    # Step 9: Run post-submission updates (non-critical)
    _run_post_submission_updates(
        db,
        test_session.id,
        correct_count,
        response_count,
    )

    # Step 10: Track analytics and invalidate caches
    AnalyticsTracker.track_test_completed(
        user_id=user_id,
        session_id=test_session.id,
        iq_score=score_result.iq_score,
        duration_seconds=completion_time_seconds,
        accuracy=score_result.accuracy_percentage,
    )
    invalidate_user_cache(user_id)
    invalidate_reliability_report_cache()

    # Step 11: Build and return response
    result_response = build_test_result_response(test_result, db=db)

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
        raise_not_found(ErrorMessages.TEST_RESULT_NOT_FOUND)

    # Verify result belongs to current user
    if test_result.user_id != current_user.id:
        raise_forbidden(ErrorMessages.RESULT_ACCESS_DENIED)

    return build_test_result_response(test_result, db=db)


@router.get("/history", response_model=PaginatedTestHistoryResponse)
def get_test_history(
    limit: int = Query(
        default=DEFAULT_HISTORY_PAGE_SIZE,
        ge=1,
        le=MAX_HISTORY_PAGE_SIZE,
        description=f"Maximum number of results to return (default {DEFAULT_HISTORY_PAGE_SIZE}, max {MAX_HISTORY_PAGE_SIZE})",
    ),
    offset: int = Query(
        default=0,
        ge=0,
        description="Number of results to skip for pagination",
    ),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get historical test results for the current user with pagination.

    Results are returned in reverse chronological order (most recent first).

    Args:
        limit: Maximum number of results per page (default 50, max 100)
        offset: Number of results to skip for pagination (default 0)
        current_user: Current authenticated user
        db: Database session

    Returns:
        Paginated test results with total count and pagination metadata
    """
    from app.models.models import TestResult

    # Get total count for pagination (single efficient count query)
    total_count = (
        db.query(func.count(TestResult.id))
        .filter(TestResult.user_id == current_user.id)
        .scalar()
    )

    # Fetch paginated test results for the user, ordered by completion date
    test_results = (
        db.query(TestResult)
        .filter(TestResult.user_id == current_user.id)
        .order_by(TestResult.completed_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )

    # Pre-fetch population stats once to avoid N+1 queries
    population_stats = get_domain_population_stats(db)

    # Convert to response format (pass pre-fetched stats to avoid N+1 queries)
    results = [
        build_test_result_response(test_result, population_stats=population_stats)
        for test_result in test_results
    ]

    return PaginatedTestHistoryResponse(
        results=results,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=(offset + len(results)) < total_count,
    )
