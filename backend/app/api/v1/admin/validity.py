"""
Session validity admin endpoints.

Endpoints for viewing and managing test session validity assessments,
including individual session validity, aggregate reports, and manual overrides.
"""
from datetime import timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.core.datetime_utils import utc_now
from app.core.db_error_handling import handle_db_error
from app.core.validity_analysis import (
    assess_session_validity,
    calculate_person_fit_heuristic,
    check_response_time_plausibility,
    count_guttman_errors,
)
from app.models import Question, Response, TestResult, TestSession, get_db
from app.schemas.validity import (
    FlagSource,
    FlagTypeBreakdown,
    GuttmanCheckDetails,
    PersonFitDetails,
    SessionNeedingReview,
    SessionValidityResponse,
    SeverityLevel as ValiditySeverityLevel,
    TimeCheckDetails,
    TimeCheckStatistics,
    ValidityDetails,
    ValidityFlag,
    ValidityOverrideRequest,
    ValidityOverrideResponse,
    ValidityStatus,
    ValidityStatusCounts,
    ValiditySummaryResponse,
    ValidityTrend,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()

# Number of days used for trend comparison in validity reports
VALIDITY_TREND_COMPARISON_DAYS = 7


def _build_validity_response_from_stored_data(
    session_id: int,
    user_id: int,
    test_result: TestResult,
    test_session: TestSession,
) -> SessionValidityResponse:
    """
    Build SessionValidityResponse from stored validity data in TestResult.

    Args:
        session_id: The test session ID
        user_id: The user ID who took the test
        test_result: The TestResult record containing stored validity data
        test_session: The TestSession record

    Returns:
        SessionValidityResponse built from stored data
    """
    # Extract stored values
    validity_status = test_result.validity_status or "valid"
    stored_flags: list[dict[str, Any]] = test_result.validity_flags or []

    # Convert stored flag details to ValidityFlag objects
    flag_details: list[ValidityFlag] = []
    flag_types: list[str] = []

    for flag_data in stored_flags:
        flag_type = flag_data.get("type", "unknown")
        flag_types.append(flag_type)

        # Map severity string to enum
        severity_str = flag_data.get("severity", "medium")
        severity = ValiditySeverityLevel.MEDIUM
        if severity_str == "high":
            severity = ValiditySeverityLevel.HIGH
        elif severity_str == "low":
            severity = ValiditySeverityLevel.LOW

        # Map source string to enum
        source_str = flag_data.get("source", "time_check")
        source = FlagSource.TIME_CHECK
        if source_str == "person_fit":
            source = FlagSource.PERSON_FIT
        elif source_str == "guttman_check":
            source = FlagSource.GUTTMAN_CHECK

        flag_details.append(
            ValidityFlag(
                type=flag_type,
                severity=severity,
                source=source,
                details=flag_data.get("details", ""),
                count=flag_data.get("count"),
                error_rate=flag_data.get("error_rate"),
            )
        )

    # Calculate severity score from flags
    severity_score = 0
    for flag in flag_details:
        if flag.severity == ValiditySeverityLevel.HIGH:
            severity_score += 2
        elif flag.severity == ValiditySeverityLevel.MEDIUM:
            severity_score += 1

    # Calculate confidence (inverse of severity)
    confidence = max(0.0, 1.0 - (severity_score * 0.15))

    return SessionValidityResponse(
        session_id=session_id,
        user_id=user_id,
        validity_status=ValidityStatus(validity_status),
        severity_score=severity_score,
        confidence=round(confidence, 2),
        flags=flag_types,
        flag_details=flag_details,
        details=None,  # Full details require re-running analysis
        completed_at=test_session.completed_at,
        validity_checked_at=test_result.validity_checked_at,
    )


def _run_validity_analysis_on_demand(
    session_id: int,
    test_session: TestSession,
    test_result: Optional[TestResult],
    db: Session,
) -> SessionValidityResponse:
    """
    Run validity analysis on-demand for sessions without stored validity data.

    This handles sessions completed before CD-007 was implemented, running
    the full validity analysis pipeline and returning the results.

    Args:
        session_id: The test session ID
        test_session: The TestSession record
        test_result: The TestResult record (may be None for abandoned sessions)
        db: Database session

    Returns:
        SessionValidityResponse with fresh analysis results
    """
    # Get responses for this session
    responses = db.query(Response).filter(Response.test_session_id == session_id).all()

    if not responses:
        # Session with no responses - return empty validity
        return SessionValidityResponse(
            session_id=session_id,
            user_id=test_session.user_id,
            validity_status=ValidityStatus.VALID,
            severity_score=0,
            confidence=1.0,
            flags=[],
            flag_details=[],
            details=None,
            completed_at=test_session.completed_at,
            validity_checked_at=None,
        )

    # Get questions for difficulty data
    question_ids = [r.question_id for r in responses]
    questions = db.query(Question).filter(Question.id.in_(question_ids)).all()
    questions_dict = {q.id: q for q in questions}

    # Calculate correct count for person-fit analysis
    correct_count = sum(1 for r in responses if r.is_correct)

    # Prepare data for validity analysis using an explicit loop for better typing
    person_fit_data: list[tuple[bool, str]] = []
    time_check_data: list[dict[str, object]] = []
    guttman_data: list[tuple[bool, float]] = []

    for r in responses:
        if r.question_id not in questions_dict:
            continue

        question = questions_dict[r.question_id]
        difficulty = (
            question.difficulty_level.value
            if question.difficulty_level is not None
            else "medium"
        )

        person_fit_data.append((r.is_correct, difficulty))
        time_check_data.append(
            {
                "time_seconds": r.time_spent_seconds,
                "is_correct": r.is_correct,
                "difficulty": difficulty,
            }
        )

        if question.empirical_difficulty is not None:
            guttman_data.append((r.is_correct, question.empirical_difficulty))

    # Run validity checks
    person_fit_result = calculate_person_fit_heuristic(
        responses=person_fit_data, total_score=correct_count
    )
    time_check_result = check_response_time_plausibility(responses=time_check_data)
    guttman_result = count_guttman_errors(responses=guttman_data)

    # Combine into overall assessment
    validity_assessment = assess_session_validity(
        person_fit=person_fit_result,
        time_check=time_check_result,
        guttman_check=guttman_result,
    )

    # Build ValidityFlag objects from assessment
    flag_details: list[ValidityFlag] = []
    for flag_data in validity_assessment["flag_details"]:
        flag_type = flag_data.get("type", "unknown")

        # Map severity string to enum
        severity_str = flag_data.get("severity", "medium")
        severity = ValiditySeverityLevel.MEDIUM
        if severity_str == "high":
            severity = ValiditySeverityLevel.HIGH
        elif severity_str == "low":
            severity = ValiditySeverityLevel.LOW

        # Map source string to enum
        source_str = flag_data.get("source", "time_check")
        source = FlagSource.TIME_CHECK
        if source_str == "person_fit":
            source = FlagSource.PERSON_FIT
        elif source_str == "guttman_check":
            source = FlagSource.GUTTMAN_CHECK

        flag_details.append(
            ValidityFlag(
                type=flag_type,
                severity=severity,
                source=source,
                details=flag_data.get("details", ""),
                count=flag_data.get("count"),
                error_rate=flag_data.get("error_rate"),
            )
        )

    # Build ValidityDetails with full breakdown from all three checks
    details = ValidityDetails(
        person_fit=PersonFitDetails(
            fit_ratio=person_fit_result["fit_ratio"],
            fit_flag=person_fit_result["fit_flag"],
            unexpected_correct=person_fit_result["unexpected_correct"],
            unexpected_incorrect=person_fit_result["unexpected_incorrect"],
            total_responses=person_fit_result["total_responses"],
            score_percentile=person_fit_result["score_percentile"],
            details=person_fit_result["details"],
        ),
        time_check=TimeCheckDetails(
            validity_concern=time_check_result["validity_concern"],
            total_time_seconds=time_check_result["total_time_seconds"],
            rapid_response_count=time_check_result["rapid_response_count"],
            extended_pause_count=time_check_result["extended_pause_count"],
            fast_hard_correct_count=time_check_result["fast_hard_correct_count"],
            statistics=TimeCheckStatistics(
                mean_time=time_check_result["statistics"]["mean_time"],
                min_time=time_check_result["statistics"]["min_time"],
                max_time=time_check_result["statistics"]["max_time"],
                total_responses=time_check_result["statistics"]["total_responses"],
            ),
            details=time_check_result["details"],
        ),
        guttman_check=GuttmanCheckDetails(
            error_count=guttman_result["error_count"],
            max_possible_errors=guttman_result["max_possible_errors"],
            error_rate=guttman_result["error_rate"],
            interpretation=guttman_result["interpretation"],
            total_responses=guttman_result["total_responses"],
            correct_count=guttman_result["correct_count"],
            incorrect_count=guttman_result["incorrect_count"],
            details=guttman_result["details"],
        ),
    )

    return SessionValidityResponse(
        session_id=session_id,
        user_id=test_session.user_id,
        validity_status=ValidityStatus(validity_assessment["validity_status"]),
        severity_score=validity_assessment["severity_score"],
        confidence=validity_assessment["confidence"],
        flags=validity_assessment["flags"],
        flag_details=flag_details,
        details=details,
        completed_at=test_session.completed_at,
        validity_checked_at=None,  # Not stored since this is on-demand
    )


@router.get(
    "/sessions/{session_id}/validity",
    response_model=SessionValidityResponse,
    responses={
        404: {"description": "Test session not found"},
    },
)
async def get_session_validity(
    session_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get detailed validity analysis for a single test session.

    Returns the validity assessment for a specific test session, including
    the overall validity status, severity score, confidence level, and
    detailed breakdown of each validity check component.

    Requires X-Admin-Token header with valid admin token.

    **Validity Status:**
    - `valid`: No significant concerns, session is valid
    - `suspect`: Moderate concerns, may need manual review
    - `invalid`: Strong concerns, requires admin review

    **Severity Score:**
    Combined score from all validity checks:
    - Aberrant person-fit: +2 points
    - High-severity time flags: +2 points each
    - High Guttman errors: +2 points
    - Elevated Guttman errors: +1 point

    **Confidence:**
    Inverse of severity (1.0 = fully confident, decreases by 0.15 per severity point)

    **On-Demand Analysis:**
    If the session has not been validity-checked yet (sessions from before CD-007),
    validity analysis will be performed on-demand and the result will be returned
    (but not stored).

    Args:
        session_id: The test session ID to analyze
        db: Database session
        _: Admin token validation dependency

    Returns:
        SessionValidityResponse with full validity breakdown

    Raises:
        HTTPException 404: If the test session is not found

    Example:
        ```
        curl "https://api.example.com/v1/admin/sessions/123/validity" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get test session
        test_session = (
            db.query(TestSession).filter(TestSession.id == session_id).first()
        )

        if test_session is None:
            raise HTTPException(
                status_code=404,
                detail=f"Test session with ID {session_id} not found",
            )

        # Get test result (which contains stored validity data)
        test_result = (
            db.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        # Check if we need to run validity analysis on-demand
        # This handles sessions completed before CD-007 was implemented
        if test_result is not None and test_result.validity_checked_at is not None:
            # Use stored validity data
            return _build_validity_response_from_stored_data(
                session_id=session_id,
                user_id=test_session.user_id,
                test_result=test_result,
                test_session=test_session,
            )
        else:
            # Run validity analysis on-demand
            return _run_validity_analysis_on_demand(
                session_id=session_id,
                test_session=test_session,
                test_result=test_result,
                db=db,
            )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve session validity: {str(e)}",
        )


@router.get(
    "/validity-report",
    response_model=ValiditySummaryResponse,
)
async def get_validity_report(
    days: int = Query(
        30,
        ge=1,
        le=365,
        description="Number of days to analyze (default: 30)",
    ),
    status: Optional[ValidityStatus] = Query(
        None,
        description="Filter by validity status (valid, suspect, invalid)",
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get aggregate validity statistics across all test sessions.

    Returns a comprehensive summary of validity analysis results including
    status breakdowns, flag type counts, trend comparisons, and a list of
    sessions requiring admin review.

    Requires X-Admin-Token header with valid admin token.

    **Summary Statistics:**
    - Total sessions analyzed in the period
    - Count by validity status (valid, suspect, invalid)

    **Flag Type Breakdown:**
    - Count of each flag type detected across sessions
    - Helps identify most common validity concerns

    **Trend Analysis:**
    - Compares invalid/suspect rates between last 7 days and full period
    - Trend indicator: "improving", "stable", or "worsening"

    **Action Needed:**
    - List of sessions with invalid or suspect status needing review
    - Sorted by severity score (most severe first)
    - Limited to top 50 sessions to keep response manageable

    Args:
        days: Number of days to analyze (default: 30, max: 365)
        status: Optional filter by validity status
        db: Database session
        _: Admin token validation dependency

    Returns:
        ValiditySummaryResponse with aggregate validity statistics

    Example:
        ```
        # Get 30-day validity report
        curl "https://api.example.com/v1/admin/validity-report" \
          -H "X-Admin-Token: your-admin-token"

        # Get 7-day report for invalid sessions only
        curl "https://api.example.com/v1/admin/validity-report?days=7&status=invalid" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        now = utc_now()
        period_start = now - timedelta(days=days)
        seven_days_ago = now - timedelta(days=7)

        # Build base query for test results with validity data in the period
        # Use joinedload to eagerly load TestSession for in-memory filtering
        base_query = (
            db.query(TestResult)
            .options(joinedload(TestResult.test_session))
            .join(TestSession, TestResult.test_session_id == TestSession.id)
            .filter(TestSession.completed_at >= period_start)
            .filter(TestSession.completed_at <= now)
        )

        # Apply status filter if provided
        if status is not None:
            base_query = base_query.filter(TestResult.validity_status == status.value)

        # Get all test results in the period
        results = base_query.all()

        # Calculate status counts
        total_sessions = len(results)
        valid_count = sum(1 for r in results if r.validity_status == "valid")
        suspect_count = sum(1 for r in results if r.validity_status == "suspect")
        invalid_count = sum(1 for r in results if r.validity_status == "invalid")

        # Build status counts
        summary = ValidityStatusCounts(
            total_sessions_analyzed=total_sessions,
            valid=valid_count,
            suspect=suspect_count,
            invalid=invalid_count,
        )

        # Count flag types from validity_flags JSON field
        flag_counts: Dict[str, int] = {
            "aberrant_response_pattern": 0,
            "multiple_rapid_responses": 0,
            "suspiciously_fast_on_hard": 0,
            "extended_pauses": 0,
            "total_time_too_fast": 0,
            "total_time_excessive": 0,
            "high_guttman_errors": 0,
            "elevated_guttman_errors": 0,
        }

        for result in results:
            flags_list: list[dict[str, Any]] = result.validity_flags or []
            for flag_data in flags_list:
                flag_type = flag_data.get("type", "")
                if flag_type in flag_counts:
                    flag_counts[flag_type] += 1

        by_flag_type = FlagTypeBreakdown(
            aberrant_response_pattern=flag_counts["aberrant_response_pattern"],
            multiple_rapid_responses=flag_counts["multiple_rapid_responses"],
            suspiciously_fast_on_hard=flag_counts["suspiciously_fast_on_hard"],
            extended_pauses=flag_counts["extended_pauses"],
            total_time_too_fast=flag_counts["total_time_too_fast"],
            total_time_excessive=flag_counts["total_time_excessive"],
            high_guttman_errors=flag_counts["high_guttman_errors"],
            elevated_guttman_errors=flag_counts["elevated_guttman_errors"],
        )

        # Calculate trend data (7-day vs full period)
        # Filter from already-fetched results to avoid redundant database query
        if days <= VALIDITY_TREND_COMPARISON_DAYS:
            # If period is equal to or less than trend window, they are the same
            seven_day_results = results
        else:
            # Filter in memory using the eagerly-loaded test_session relationship
            # Normalize to naive UTC for comparison (handles SQLite naive vs PostgreSQL aware)
            seven_days_ago_naive = seven_days_ago.replace(tzinfo=None)
            seven_day_results = [
                r
                for r in results
                if r.test_session
                and r.test_session.completed_at
                and (
                    r.test_session.completed_at.replace(tzinfo=None)
                    >= seven_days_ago_naive
                )
            ]

        seven_day_total = len(seven_day_results)
        seven_day_invalid = sum(
            1 for r in seven_day_results if r.validity_status == "invalid"
        )
        seven_day_suspect = sum(
            1 for r in seven_day_results if r.validity_status == "suspect"
        )

        # Calculate rates
        invalid_rate_7d = (
            round(seven_day_invalid / seven_day_total, 4)
            if seven_day_total > 0
            else 0.0
        )
        invalid_rate_30d = (
            round(invalid_count / total_sessions, 4) if total_sessions > 0 else 0.0
        )
        suspect_rate_7d = (
            round(seven_day_suspect / seven_day_total, 4)
            if seven_day_total > 0
            else 0.0
        )
        suspect_rate_30d = (
            round(suspect_count / total_sessions, 4) if total_sessions > 0 else 0.0
        )

        # Determine trend direction based on combined invalid + suspect rates
        # Lower rates = improving, higher rates = worsening
        combined_rate_7d = invalid_rate_7d + suspect_rate_7d
        combined_rate_30d = invalid_rate_30d + suspect_rate_30d

        # Use 2% threshold for meaningful change
        threshold = 0.02
        if combined_rate_7d < combined_rate_30d - threshold:
            trend = "improving"
        elif combined_rate_7d > combined_rate_30d + threshold:
            trend = "worsening"
        else:
            trend = "stable"

        trends = ValidityTrend(
            invalid_rate_7d=invalid_rate_7d,
            invalid_rate_30d=invalid_rate_30d,
            suspect_rate_7d=suspect_rate_7d,
            suspect_rate_30d=suspect_rate_30d,
            trend=trend,
        )

        # Get sessions needing review (invalid or suspect)
        sessions_needing_review = [
            r for r in results if r.validity_status in ["invalid", "suspect"]
        ]

        # Build action_needed list with severity scores
        action_needed: List[SessionNeedingReview] = []
        for test_result in sessions_needing_review:
            flags_list_review: list[dict[str, Any]] = test_result.validity_flags or []
            flag_types = [f.get("type", "") for f in flags_list_review]

            # Calculate severity score from flags
            severity_score = 0
            for flag_data in flags_list_review:
                flag_severity = flag_data.get("severity", "medium")
                if flag_severity == "high":
                    severity_score += 2
                elif flag_severity == "medium":
                    severity_score += 1

            # Use eagerly-loaded test_session relationship
            test_session = test_result.test_session
            action_needed.append(
                SessionNeedingReview(
                    session_id=test_session.id,
                    user_id=test_session.user_id,
                    validity_status=ValidityStatus(
                        test_result.validity_status or "valid"
                    ),
                    severity_score=severity_score,
                    flags=flag_types,
                    completed_at=test_session.completed_at,
                )
            )

        # Sort by severity_score descending, then limit to 50
        action_needed.sort(key=lambda x: x.severity_score, reverse=True)
        action_needed = action_needed[:50]

        return ValiditySummaryResponse(
            summary=summary,
            by_flag_type=by_flag_type,
            trends=trends,
            action_needed=action_needed,
            period_days=days,
            generated_at=now,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate validity report: {str(e)}",
        )


@router.patch(
    "/sessions/{session_id}/validity",
    response_model=ValidityOverrideResponse,
    responses={
        404: {"description": "Test session not found"},
    },
)
async def override_session_validity(
    session_id: int,
    request: ValidityOverrideRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Override the validity status of a test session after admin review.

    Allows administrators to manually change the validity assessment for a
    session after investigating the flags. This is essential for handling
    false positives (legitimate sessions incorrectly flagged) and false
    negatives (invalid sessions that passed automatic checks).

    Requires X-Admin-Token header with valid admin token.

    **Important Notes:**
    - A reason must be provided (minimum 10 characters) for audit purposes
    - The previous validity status is preserved for audit trail
    - Override timestamp and admin placeholder are recorded
    - All override actions are logged for security monitoring

    **Use Cases:**
    - Clearing a false positive: User was flagged for rapid responses but
      review confirms they're a fast reader with consistent test history
    - Marking a false negative: Session passed checks but investigation
      reveals the account was shared or test was taken inappropriately
    - Downgrading after investigation: Session was flagged as "invalid"
      but evidence suggests only moderate concern ("suspect")

    Args:
        session_id: The test session ID to update
        request: Override request with new status and reason
        db: Database session
        _: Admin token validation dependency

    Returns:
        ValidityOverrideResponse confirming the update

    Raises:
        HTTPException 404: If the test session is not found

    Example:
        ```
        curl -X PATCH "https://api.example.com/v1/admin/sessions/123/validity" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{
            "validity_status": "valid",
            "override_reason": "Manual review confirmed legitimate pattern. User has consistent test history and rapid responses were on very easy questions."
          }'
        ```
    """
    with handle_db_error(db, "override session validity"):
        # Get test session
        test_session = (
            db.query(TestSession).filter(TestSession.id == session_id).first()
        )

        if test_session is None:
            raise HTTPException(
                status_code=404,
                detail=f"Test session with ID {session_id} not found",
            )

        # Get test result
        test_result = (
            db.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )

        if test_result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Test result for session {session_id} not found. "
                "Cannot override validity for sessions without results.",
            )

        # Store previous status for response and logging
        previous_status = test_result.validity_status or "valid"

        # Set override timestamp
        override_time = utc_now()

        # Update the test result
        # Note: Using placeholder admin_id since current auth is token-based
        # In future, when admin user management is added, this would be the admin user ID
        admin_placeholder_id = 0

        test_result.validity_status = request.validity_status.value
        test_result.validity_override_reason = request.override_reason
        test_result.validity_overridden_at = override_time
        test_result.validity_overridden_by = admin_placeholder_id

        # Commit changes
        db.commit()
        db.refresh(test_result)

        # Log the override action for security monitoring
        logger.info(
            "Admin validity override performed: "
            f"session_id={session_id}, "
            f"user_id={test_session.user_id}, "
            f"previous_status={previous_status}, "
            f"new_status={request.validity_status.value}, "
            f"reason_length={len(request.override_reason)}"
        )

        return ValidityOverrideResponse(
            session_id=session_id,
            previous_status=ValidityStatus(previous_status),
            new_status=request.validity_status,
            override_reason=request.override_reason,
            overridden_by=admin_placeholder_id,
            overridden_at=override_time,
        )
