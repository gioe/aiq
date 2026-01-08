"""
Question calibration admin endpoints.

AI-assigned difficulty labels (easy/medium/hard) may not match real user
performance. A question labeled "hard" might actually be easy for real users
(high empirical p-value). This module validates assigned labels against
observed performance and flags or recalibrates miscalibrated items.

Endpoints for validating and recalibrating question difficulty labels
based on empirical user performance data.

See docs/methodology/METHODOLOGY.md Section 5.3 for psychometric context.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.question_analytics import (
    recalibrate_questions,
    validate_difficulty_labels,
)
from app.models import get_db
from app.schemas.calibration import (
    CalibrationHealthResponse,
    CalibrationSummary,
    DifficultyBreakdown,
    DifficultyCalibrationStatus,
    MiscalibratedQuestion,
    RecalibrationRequest,
    RecalibrationResponse,
    RecalibratedQuestion,
    SeverityBreakdown,
    SeverityLevel,
    SkippedQuestion,
)

from ._dependencies import verify_admin_token

router = APIRouter()


@router.get(
    "/questions/calibration-health",
    response_model=CalibrationHealthResponse,
)
async def get_calibration_health(
    min_responses: int = Query(
        100,
        ge=1,
        le=1000,
        description="Minimum responses required for reliable validation",
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get calibration health summary for all questions.

    Returns a comprehensive overview of how well AI-assigned difficulty labels
    match empirical user performance data. Questions with empirical p-values
    outside the expected range for their assigned difficulty are flagged as
    miscalibrated.

    Requires X-Admin-Token header with valid admin token.

    **Expected p-value ranges by difficulty:**
    - Easy: 0.70 - 0.90 (70-90% correct)
    - Medium: 0.40 - 0.70 (40-70% correct)
    - Hard: 0.15 - 0.40 (15-40% correct)

    **Severity levels:**
    - Minor: Within 0.10 of expected range boundary
    - Major: 0.10-0.25 outside expected range
    - Severe: >0.25 outside expected range

    **Response includes:**
    - Summary statistics (total, calibrated, miscalibrated, rate)
    - Breakdown by severity level
    - Breakdown by difficulty level
    - Top 10 most severely miscalibrated questions

    Args:
        min_responses: Minimum response count for reliable validation (default: 100)
        db: Database session
        _: Admin token validation dependency

    Returns:
        CalibrationHealthResponse with comprehensive calibration status

    Example:
        ```
        curl "https://api.example.com/v1/admin/questions/calibration-health?min_responses=100" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get validation results from core function
        validation_results = validate_difficulty_labels(db, min_responses)

        # Extract lists
        miscalibrated = validation_results["miscalibrated"]
        correctly_calibrated = validation_results["correctly_calibrated"]

        # Calculate summary statistics
        total_with_data = len(miscalibrated) + len(correctly_calibrated)
        miscalibrated_count = len(miscalibrated)
        calibrated_count = len(correctly_calibrated)
        miscalibration_rate = (
            round(miscalibrated_count / total_with_data, 4)
            if total_with_data > 0
            else 0.0
        )

        summary = CalibrationSummary(
            total_questions_with_data=total_with_data,
            correctly_calibrated=calibrated_count,
            miscalibrated=miscalibrated_count,
            miscalibration_rate=miscalibration_rate,
        )

        # Calculate severity breakdown
        severity_counts = {"minor": 0, "major": 0, "severe": 0}
        for q in miscalibrated:
            severity = q.get("severity", "minor")
            if severity in severity_counts:
                severity_counts[severity] += 1

        by_severity = SeverityBreakdown(
            minor=severity_counts["minor"],
            major=severity_counts["major"],
            severe=severity_counts["severe"],
        )

        # Calculate difficulty breakdown
        difficulty_stats: Dict[str, Dict[str, int]] = {
            "easy": {"calibrated": 0, "miscalibrated": 0},
            "medium": {"calibrated": 0, "miscalibrated": 0},
            "hard": {"calibrated": 0, "miscalibrated": 0},
        }

        for q in correctly_calibrated:
            difficulty = q.get("assigned_difficulty", "").lower()
            if difficulty in difficulty_stats:
                difficulty_stats[difficulty]["calibrated"] += 1

        for q in miscalibrated:
            difficulty = q.get("assigned_difficulty", "").lower()
            if difficulty in difficulty_stats:
                difficulty_stats[difficulty]["miscalibrated"] += 1

        by_difficulty = DifficultyBreakdown(
            easy=DifficultyCalibrationStatus(
                calibrated=difficulty_stats["easy"]["calibrated"],
                miscalibrated=difficulty_stats["easy"]["miscalibrated"],
            ),
            medium=DifficultyCalibrationStatus(
                calibrated=difficulty_stats["medium"]["calibrated"],
                miscalibrated=difficulty_stats["medium"]["miscalibrated"],
            ),
            hard=DifficultyCalibrationStatus(
                calibrated=difficulty_stats["hard"]["calibrated"],
                miscalibrated=difficulty_stats["hard"]["miscalibrated"],
            ),
        )

        # Get worst offenders (top 10 most severely miscalibrated)
        # Sort by severity (severe > major > minor), then by distance from range
        severity_order = {"severe": 2, "major": 1, "minor": 0}

        def sort_key(q: Dict[str, Any]) -> tuple:
            """Sort by severity (desc), then by deviation from range (desc)."""
            severity_rank = severity_order.get(q.get("severity", "minor"), 0)
            # Calculate deviation from expected range
            empirical = q.get("empirical_difficulty", 0.5)
            expected_range = q.get("expected_range", [0.4, 0.7])
            if empirical < expected_range[0]:
                deviation = expected_range[0] - empirical
            elif empirical > expected_range[1]:
                deviation = empirical - expected_range[1]
            else:
                deviation = 0
            return (severity_rank, deviation)

        sorted_miscalibrated = sorted(miscalibrated, key=sort_key, reverse=True)
        top_10 = sorted_miscalibrated[:10]

        worst_offenders = [
            MiscalibratedQuestion(
                question_id=q["question_id"],
                assigned_difficulty=q["assigned_difficulty"],
                empirical_difficulty=q["empirical_difficulty"],
                expected_range=q["expected_range"],
                suggested_label=q["suggested_label"],
                response_count=q["response_count"],
                severity=SeverityLevel(q["severity"]),
            )
            for q in top_10
        ]

        return CalibrationHealthResponse(
            summary=summary,
            by_severity=by_severity,
            by_difficulty=by_difficulty,
            worst_offenders=worst_offenders,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve calibration health: {str(e)}",
        )


@router.post(
    "/questions/recalibrate",
    response_model=RecalibrationResponse,
)
async def recalibrate_difficulty_labels(
    request: RecalibrationRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Trigger recalibration of question difficulty labels based on empirical data.

    Updates difficulty labels for questions where the AI-assigned label
    doesn't match actual user performance. Preserves original labels for
    audit purposes.

    Requires X-Admin-Token header with valid admin token.

    **Expected p-value ranges by difficulty:**
    - Easy: 0.70 - 0.90 (70-90% correct)
    - Medium: 0.40 - 0.70 (40-70% correct)
    - Hard: 0.15 - 0.40 (15-40% correct)

    **Severity levels (determines threshold):**
    - Minor: Within 0.10 of expected range boundary
    - Major: 0.10-0.25 outside expected range
    - Severe: >0.25 outside expected range

    **Recalibration modes:**
    - dry_run=true: Preview changes without applying (default)
    - dry_run=false: Commit changes to database

    **Filtering options:**
    - question_ids: Limit to specific questions
    - severity_threshold: Only recalibrate questions at or above this severity
    - min_responses: Require minimum response count for reliability

    Args:
        request: Recalibration parameters
        db: Database session
        _: Admin token validation dependency

    Returns:
        RecalibrationResponse with recalibrated and skipped questions

    Example:
        ```
        # Dry run to preview changes
        curl -X POST "https://api.example.com/v1/admin/questions/recalibrate" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"dry_run": true, "min_responses": 100, "severity_threshold": "major"}'

        # Apply changes
        curl -X POST "https://api.example.com/v1/admin/questions/recalibrate" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"dry_run": false, "min_responses": 100, "severity_threshold": "major"}'
        ```
    """
    try:
        # Call core recalibration function
        results = recalibrate_questions(
            db=db,
            min_responses=request.min_responses,
            question_ids=request.question_ids,
            severity_threshold=request.severity_threshold.value,
            dry_run=request.dry_run,
        )

        # Convert recalibrated questions to schema
        recalibrated = [
            RecalibratedQuestion(
                question_id=q["question_id"],
                old_label=q["old_label"],
                new_label=q["new_label"],
                empirical_difficulty=q["empirical_difficulty"],
                response_count=q["response_count"],
                severity=SeverityLevel(q["severity"]),
            )
            for q in results["recalibrated"]
        ]

        # Convert skipped questions to schema
        skipped = [
            SkippedQuestion(
                question_id=q["question_id"],
                reason=q["reason"],
                assigned_difficulty=q["assigned_difficulty"],
                severity=SeverityLevel(q["severity"]) if q.get("severity") else None,
            )
            for q in results["skipped"]
        ]

        return RecalibrationResponse(
            recalibrated=recalibrated,
            skipped=skipped,
            total_recalibrated=results["total_recalibrated"],
            dry_run=results["dry_run"],
        )

    except ValueError as e:
        # Invalid severity_threshold
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )
    except RuntimeError as e:
        # Database commit failed
        raise HTTPException(
            status_code=500,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to recalibrate questions: {str(e)}",
        )
