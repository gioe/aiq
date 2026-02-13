"""
Inventory health admin endpoints.

Endpoints for monitoring question inventory levels across different
question types and difficulties to ensure sufficient questions are
available for test composition.
"""
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_responses import raise_server_error, ErrorMessages
from app.models import DifficultyLevel, Question, QuestionType, get_db
from app.schemas.inventory import (
    AlertSeverity,
    InventoryAlert,
    InventoryHealthResponse,
    InventoryStatus,
    InventoryStratum,
    InventoryThresholds,
)

from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)

router = APIRouter()

# Configurable thresholds for inventory health
# These represent minimum acceptable inventory levels per stratum
HEALTHY_THRESHOLD = 50  # Green status: plenty of questions
WARNING_THRESHOLD = 20  # Yellow status: low inventory, needs attention
# Below WARNING_THRESHOLD = Red status: critical, immediate action needed


def _determine_status(count: int, thresholds: InventoryThresholds) -> InventoryStatus:
    """
    Determine health status based on count and thresholds.

    Args:
        count: Number of questions in the stratum
        thresholds: Configured threshold values

    Returns:
        InventoryStatus based on count relative to thresholds
    """
    if count >= thresholds.healthy_min:
        return InventoryStatus.HEALTHY
    elif count >= thresholds.warning_min:
        return InventoryStatus.WARNING
    else:
        return InventoryStatus.CRITICAL


def _create_alert(
    question_type: str,
    difficulty: str,
    count: int,
    thresholds: InventoryThresholds,
) -> InventoryAlert:
    """
    Create an inventory alert for a stratum below healthy threshold.

    Args:
        question_type: Question type
        difficulty: Difficulty level
        count: Current count
        thresholds: Configured threshold values

    Returns:
        InventoryAlert with appropriate severity and message
    """
    # Determine severity and threshold violated
    if count < thresholds.warning_min:
        severity = AlertSeverity.CRITICAL
        threshold = thresholds.warning_min
        prefix = "Critical inventory"
    else:
        severity = AlertSeverity.WARNING
        threshold = thresholds.healthy_min
        prefix = "Low inventory"

    message = (
        f"{prefix}: {question_type}/{difficulty} has only {count} "
        f"questions (threshold: {threshold})"
    )

    return InventoryAlert(
        question_type=question_type,
        difficulty=difficulty,
        count=count,
        threshold=threshold,
        message=message,
        severity=severity,
    )


@router.get("/inventory-health", response_model=InventoryHealthResponse)
async def get_inventory_health(
    healthy_min: int = Query(
        HEALTHY_THRESHOLD,
        ge=0,
        description="Minimum count for healthy status (default: 50)",
    ),
    warning_min: int = Query(
        WARNING_THRESHOLD,
        ge=0,
        description="Minimum count for warning status (default: 20)",
    ),
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Get question inventory health status across all type/difficulty strata.

    Returns detailed inventory statistics with health indicators to help
    monitor question pool sufficiency. Useful for identifying which
    question types/difficulties need more generation.

    Requires X-Admin-Token header with valid admin token.

    **Health Status Thresholds:**
    - `healthy`: count >= healthy_min (default: 50)
    - `warning`: warning_min <= count < healthy_min (default: 20-49)
    - `critical`: count < warning_min (default: < 20)

    **Query Parameters:**
    - `healthy_min`: Minimum count for healthy status (configurable, default: 50)
    - `warning_min`: Minimum count for warning status (configurable, default: 20)

    **Response Structure:**
    - `total_active_questions`: Total count across all strata
    - `strata`: List of all type/difficulty combinations with counts and status
    - `alerts`: List of strata below healthy threshold requiring attention
    - `thresholds`: The threshold values used for this assessment
    - `summary`: Count of strata by status (healthy/warning/critical)

    Args:
        healthy_min: Minimum count for healthy status
        warning_min: Minimum count for warning status
        db: Database session
        _: Admin token validation dependency

    Returns:
        InventoryHealthResponse with complete inventory breakdown

    Example:
        ```
        # Use default thresholds
        curl "https://api.example.com/v1/admin/inventory-health" \
          -H "X-Admin-Token: your-admin-token"

        # Use custom thresholds
        curl "https://api.example.com/v1/admin/inventory-health?healthy_min=100&warning_min=30" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Validate threshold relationship
        if warning_min > healthy_min:
            raise ValueError(
                f"warning_min ({warning_min}) must be <= healthy_min ({healthy_min})"
            )

        thresholds = InventoryThresholds(
            healthy_min=healthy_min,
            warning_min=warning_min,
        )

        # Query database for active question counts grouped by type and difficulty
        # Only count questions with quality_flag='normal' (exclude under_review and deactivated)
        stratum_stmt = (
            select(
                Question.question_type,
                Question.difficulty_level,
                func.count(Question.id).label("count"),
            )
            .where(
                Question.is_active == True,  # noqa: E712
                Question.quality_flag == "normal",
            )
            .group_by(Question.question_type, Question.difficulty_level)
        )

        stratum_result = await db.execute(stratum_stmt)
        stratum_counts = stratum_result.all()

        # Build a map of (type, difficulty) -> count for quick lookup
        # Note: row[2] is the count from func.count().label("count")
        count_map: Dict[tuple, int] = {
            (str(row[0].value), str(row[1].value)): row[2] for row in stratum_counts
        }

        # Generate complete matrix of all possible strata
        # This ensures we show zero counts for missing combinations
        strata: List[InventoryStratum] = []
        alerts: List[InventoryAlert] = []
        status_counts = {"healthy": 0, "warning": 0, "critical": 0}

        for q_type in QuestionType:
            for difficulty in DifficultyLevel:
                type_str = q_type.value
                diff_str = difficulty.value
                count = count_map.get((type_str, diff_str), 0)

                # Determine health status
                status = _determine_status(count, thresholds)

                # Create stratum entry
                stratum = InventoryStratum(
                    question_type=type_str,
                    difficulty=diff_str,
                    count=count,
                    status=status,
                )
                strata.append(stratum)

                # Update status counts
                status_counts[status.value] += 1

                # Generate alert if below healthy threshold
                if count < thresholds.healthy_min:
                    alert = _create_alert(type_str, diff_str, count, thresholds)
                    alerts.append(alert)

        # Calculate total active questions
        total_active = sum(s.count for s in strata)

        # Sort strata by type then difficulty for consistent output
        strata.sort(key=lambda s: (s.question_type, s.difficulty))

        # Sort alerts by severity (critical first) then by count (ascending)
        alerts.sort(
            key=lambda a: (
                0 if a.severity == AlertSeverity.CRITICAL else 1,
                a.count,
            )
        )

        logger.info(
            f"Inventory health check completed: {total_active} total questions, "
            f"{len(alerts)} alerts generated"
        )

        return InventoryHealthResponse(
            total_active_questions=total_active,
            strata=strata,
            alerts=alerts,
            thresholds=thresholds,
            summary=status_counts,
        )

    except ValueError as e:
        # Validation errors from threshold checking
        logger.warning(f"Invalid threshold parameters: {e}")
        raise_server_error(str(e))
    except Exception as e:
        logger.error(f"Failed to retrieve inventory health: {e}")
        raise_server_error(
            ErrorMessages.database_operation_failed("retrieve inventory health")
        )
