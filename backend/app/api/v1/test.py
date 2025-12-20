"""
Test session management endpoints.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import case, func
from sqlalchemy.exc import IntegrityError
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
from app.core.datetime_utils import ensure_timezone_aware
from app.core.validity_analysis import (
    calculate_person_fit_heuristic,
    check_response_time_plausibility,
    count_guttman_errors,
    assess_session_validity,
)

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
        raise HTTPException(
            status_code=403, detail="Not authorized to access this test session"
        )


def verify_session_in_progress(test_session: TestSession) -> None:
    """
    Verify that a test session is in progress.

    Args:
        test_session: Test session to verify

    Raises:
        HTTPException: If session is not in progress
    """
    if test_session.status != TestStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=400,
            detail=f"Test session is already {test_session.status.value}. "  # type: ignore[attr-defined]
            "Only in-progress sessions can be modified.",
        )


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
        response_time_flags=test_result.response_time_flags,  # type: ignore[arg-type]
        domain_scores=domain_scores,  # type: ignore[arg-type]
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
        completed_at = ensure_timezone_aware(recent_completed_session.completed_at)  # type: ignore[arg-type]
        next_eligible = completed_at + timedelta(days=settings.TEST_CADENCE_DAYS)
        days_remaining = (
            next_eligible - datetime.now(timezone.utc)
        ).days + 1  # Round up

        raise HTTPException(
            status_code=400,
            detail=f"You must wait {settings.TEST_CADENCE_DAYS} days (3 months) between tests. "
            f"Your last test was completed on {completed_at.strftime('%Y-%m-%d')}. "
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

    try:
        db.flush()  # Get the session ID without committing yet
    except IntegrityError:
        # BCQ-006: Race condition detected - another session was created concurrently
        # The partial unique index ix_test_sessions_user_active prevents duplicate
        # in_progress sessions for the same user at the database level.
        db.rollback()
        logger.warning(
            f"Race condition detected: user {current_user.id} attempted to start "
            "multiple test sessions concurrently"
        )
        raise HTTPException(
            status_code=409,
            detail="A test session is already in progress. "
            "Please complete or abandon the existing session before starting a new one.",
        )

    # Mark questions as seen for this user
    for question in unseen_questions:
        user_question = UserQuestion(
            user_id=current_user.id,
            question_id=question.id,
            test_session_id=test_session.id,
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
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Verify session belongs to current user
    verify_session_ownership(test_session, int(current_user.id))  # type: ignore

    # Count responses for this session
    questions_count = count_session_responses(db, session_id)

    # If session is in_progress, retrieve the questions for this session
    questions_response = None
    if test_session.status == TestStatus.IN_PROGRESS:
        questions_response = get_session_questions(
            db, int(current_user.id), session_id, include_explanation=False  # type: ignore
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
    questions_count = count_session_responses(db, int(active_session.id))  # type: ignore

    # Get questions for the active session
    questions_response = get_session_questions(
        db, int(current_user.id), int(active_session.id), include_explanation=False  # type: ignore
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
    # Fetch the test session
    test_session = db.query(TestSession).filter(TestSession.id == session_id).first()

    if not test_session:
        raise HTTPException(status_code=404, detail="Test session not found")

    # Verify session belongs to current user
    verify_session_ownership(test_session, int(current_user.id))  # type: ignore

    # Verify session is in progress
    verify_session_in_progress(test_session)

    # Count any responses that were saved during the test
    responses_saved = count_session_responses(db, session_id)

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
    verify_session_ownership(test_session, int(current_user.id))  # type: ignore

    # Verify session is still in progress
    verify_session_in_progress(test_session)

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
    response_objects: list[
        Response
    ] = []  # DW-003: Collect responses for domain scoring

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

        # Create Response record with optional time tracking (TS-003)
        response = Response(
            test_session_id=test_session.id,
            user_id=current_user.id,
            question_id=resp_item.question_id,
            user_answer=resp_item.user_answer.strip(),
            is_correct=is_correct,
            answered_at=datetime.now(timezone.utc),
            time_spent_seconds=resp_item.time_spent_seconds,  # TS-003: Store per-question time
        )
        db.add(response)
        response_objects.append(response)  # DW-003: Collect for domain scoring
        response_count += 1

        # DA-006: Update distractor statistics for multiple-choice questions
        # This tracks selection frequency for each answer option
        # Graceful degradation: failures are logged but don't block response recording
        try:
            update_distractor_stats(
                db=db,
                question_id=resp_item.question_id,
                selected_answer=resp_item.user_answer.strip(),
            )
        except Exception as e:
            logger.warning(
                f"Failed to update distractor stats for question {resp_item.question_id}: {e}"
            )

    # Update test session status to completed
    completion_time = datetime.now(timezone.utc)
    test_session.status = TestStatus.COMPLETED  # type: ignore[assignment]
    test_session.completed_at = completion_time  # type: ignore[assignment]

    # Calculate completion time in seconds
    started_at = ensure_timezone_aware(test_session.started_at)  # type: ignore[arg-type]
    time_delta = completion_time - started_at
    completion_time_seconds = int(time_delta.total_seconds())

    # TS-003/TS-010: Flag if time limit was exceeded
    # Accept client-reported flag OR detect server-side if total time exceeds limit
    # Using both ensures robustness: client knows about auto-submit, server validates
    TIME_LIMIT_SECONDS = 1800  # 30 minutes
    if submission.time_limit_exceeded or completion_time_seconds > TIME_LIMIT_SECONDS:
        test_session.time_limit_exceeded = True  # type: ignore[assignment]
        logger.info(
            f"Test session {test_session.id} exceeded time limit: "
            f"client_reported={submission.time_limit_exceeded}, "
            f"server_detected={completion_time_seconds > TIME_LIMIT_SECONDS} "
            f"({completion_time_seconds}s)"
        )

    # DW-003: Calculate domain-specific performance breakdown
    # This provides per-domain subscores for cognitive domain analysis
    # Calculated first as it's needed for weighted scoring
    domain_scores = calculate_domain_scores(response_objects, questions_dict)  # type: ignore[arg-type]

    # DW-014: Calculate IQ score using weighted or equal weights based on config
    # When weighted scoring is enabled and domain weights are configured,
    # use the weighted scoring function which applies domain-specific weights
    # reflecting each domain's correlation with general intelligence (g-loading)
    use_weighted = is_weighted_scoring_enabled(db)
    domain_weights = get_domain_weights(db) if use_weighted else None

    if use_weighted and domain_weights:
        # Use weighted scoring with configured domain weights
        score_result = calculate_weighted_iq_score(
            domain_scores=domain_scores,
            weights=domain_weights,
        )
        logger.info(
            f"Test session {test_session.id}: Using weighted scoring with weights={domain_weights}"
        )
    else:
        # Use standard equal-weight scoring
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

    # TS-005: Run response time anomaly detection
    # This analysis runs after scoring to detect timing patterns that may indicate
    # validity concerns (random clicking, external assistance, etc.)
    response_time_flags = None
    try:
        time_analysis = analyze_response_times(db, int(test_session.id))  # type: ignore
        response_time_flags = get_session_time_summary(time_analysis)

        if response_time_flags.get("validity_concern"):
            logger.info(
                f"Test session {test_session.id} has validity concerns: "
                f"flags={response_time_flags.get('flags')}"
            )
    except Exception as e:
        # Log error but don't fail the submission - anomaly detection is non-critical
        logger.error(
            f"Failed to analyze response times for session {test_session.id}: {e}"
        )

    # CD-007: Run validity analysis to detect aberrant response patterns
    # This combines person-fit, response time plausibility, and Guttman error checks
    # to identify potential cheating or invalid test-taking behavior
    validity_status = "valid"
    validity_flags = None
    validity_checked_at = None

    try:
        # Prepare data for validity analysis
        # Person-fit needs: (is_correct, difficulty_level) tuples
        person_fit_data = [
            (
                resp_item.user_answer.strip().lower()
                == questions_dict.get(resp_item.question_id).correct_answer.strip().lower(),  # type: ignore[call-overload,union-attr]
                questions_dict.get(resp_item.question_id).difficulty_level or "medium",  # type: ignore[call-overload,union-attr]
            )
            for resp_item in submission.responses
            if questions_dict.get(resp_item.question_id) is not None  # type: ignore[call-overload]
        ]

        # Time plausibility needs: dicts with time_seconds, is_correct, difficulty
        time_check_data = [
            {
                "time_seconds": resp_item.time_spent_seconds,
                "is_correct": (
                    resp_item.user_answer.strip().lower()
                    == questions_dict.get(resp_item.question_id).correct_answer.strip().lower()  # type: ignore[call-overload,union-attr]
                ),
                "difficulty": questions_dict.get(resp_item.question_id).difficulty_level or "medium",  # type: ignore[call-overload,union-attr]
            }
            for resp_item in submission.responses
            if questions_dict.get(resp_item.question_id) is not None  # type: ignore[call-overload]
        ]

        # Guttman check needs: (is_correct, empirical_difficulty) tuples
        # empirical_difficulty is p-value (proportion correct), higher = easier
        guttman_data = [
            (
                resp_item.user_answer.strip().lower()
                == questions_dict.get(resp_item.question_id).correct_answer.strip().lower(),  # type: ignore[call-overload,union-attr]
                questions_dict.get(resp_item.question_id).empirical_difficulty,  # type: ignore[call-overload,union-attr]
            )
            for resp_item in submission.responses
            if questions_dict.get(resp_item.question_id) is not None  # type: ignore[call-overload]
            and questions_dict.get(resp_item.question_id).empirical_difficulty is not None  # type: ignore[call-overload,union-attr]
        ]

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
        # Store flag_details instead of flags for richer diagnostics
        # flag_details includes type, severity, source, details, and additional context
        validity_status = validity_assessment["validity_status"]
        validity_flags = (
            validity_assessment["flag_details"]
            if validity_assessment["flag_details"]
            else None
        )
        validity_checked_at = datetime.now(timezone.utc)

        # Log validity assessment results
        if validity_status != "valid":
            logger.warning(
                f"Test session {test_session.id} validity assessment: "
                f"status={validity_status}, severity={validity_assessment['severity_score']}, "
                f"flags={[f['type'] for f in validity_assessment['flag_details']]}"
            )
        else:
            logger.info(
                f"Test session {test_session.id} passed validity checks: "
                f"confidence={validity_assessment['confidence']}"
            )

    except Exception as e:
        # Validity check failures should not block test submission (graceful degradation)
        # Log the error but continue with default "valid" status
        logger.error(
            f"Failed to run validity analysis for session {test_session.id}: {e}",
            exc_info=True,
        )

    # SEM-004: Calculate Standard Error of Measurement and Confidence Interval
    # This provides measurement precision information for the IQ score
    standard_error: Optional[float] = None
    ci_lower: Optional[int] = None
    ci_upper: Optional[int] = None

    try:
        # Get cached reliability coefficient (Cronbach's alpha)
        # Returns None if insufficient data or reliability < 0.60
        reliability = get_cached_reliability(db)

        if reliability is not None:
            # Calculate SEM using the reliability coefficient
            standard_error = calculate_sem(reliability)

            # Calculate 95% confidence interval for the IQ score
            ci_lower, ci_upper = calculate_confidence_interval(
                score=score_result.iq_score,
                sem=standard_error,
                confidence_level=CONFIDENCE_INTERVAL_LEVEL,
            )

            logger.info(
                f"Test session {test_session.id}: SEM calculation successful - "
                f"reliability={reliability:.3f}, SEM={standard_error:.2f}, "
                f"CI=[{ci_lower}, {ci_upper}]"
            )
        else:
            # Log why SEM calculation was skipped
            logger.info(
                f"Test session {test_session.id}: SEM calculation skipped - "
                "insufficient data or reliability below threshold (< 0.60)"
            )

    except Exception as e:
        # SEM calculation failures should not block test submission (graceful degradation)
        logger.warning(f"Test session {test_session.id}: Failed to calculate SEM - {e}")

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
        response_time_flags=response_time_flags,  # TS-005: Store anomaly flags
        domain_scores=domain_scores,  # DW-003: Store per-domain performance breakdown
        # CD-007: Store validity analysis results
        validity_status=validity_status,
        validity_flags=validity_flags,
        validity_checked_at=validity_checked_at,
        # SEM-004: Store measurement precision data
        standard_error=standard_error,
        ci_lower=ci_lower,
        ci_upper=ci_upper,
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

    # DA-007: Update quartile-based distractor stats after test completion
    # This enables discrimination analysis to identify which distractors attract
    # high-ability vs low-ability test-takers
    try:
        update_session_quartile_stats(
            db=db,
            test_session_id=int(test_session.id),  # type: ignore
            correct_answers=correct_count,
            total_questions=response_count,
        )
    except Exception as e:
        # Log error but don't fail the submission - quartile stats are non-critical
        logger.warning(
            f"Failed to update distractor quartile stats for session {test_session.id}: {e}"
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

    # RE-FI-031: Invalidate reliability report cache after test completion
    # New test data affects reliability metrics (Cronbach's alpha, test-retest, split-half)
    # so cached reports should be refreshed to include the new data
    invalidate_reliability_report_cache()

    # Build response with test result (pass db for domain percentile calculation)
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
        raise HTTPException(status_code=404, detail="Test result not found")

    # Verify result belongs to current user
    if test_result.user_id != current_user.id:
        raise HTTPException(
            status_code=403, detail="Not authorized to access this test result"
        )

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
