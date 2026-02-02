"""
Calibration monitoring dashboard admin endpoint.

Provides a comprehensive view of IRT calibration readiness, tracking response
counts per item, per-domain statistics, and progress toward the 500-test
threshold needed for IRT parameter estimation.
"""
import logging
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.error_responses import raise_server_error, ErrorMessages
from app.models import (
    Question,
    Response,
    TestSession,
    TestStatus,
    get_db,
)
from app.schemas.calibration_monitoring import (
    AlertSeverity,
    CalibrationAlert,
    CalibrationMonitoringResponse,
    CalibrationReadiness,
    DomainCalibrationStats,
    ExitCriteria,
    ItemCalibrationStats,
)
from ._dependencies import verify_admin_token

logger = logging.getLogger(__name__)
router = APIRouter()

# Thresholds
CALIBRATION_READY_THRESHOLD = 50  # Min responses per item for calibration
TARGET_COMPLETED_TESTS = 500  # Exit criterion: total completed tests
DOMAIN_LOW_RESPONSE_THRESHOLD = 5  # Alert if avg responses per item < 5
LOW_TEST_COUNT_WARNING = 100  # Warn when fewer than this many completed tests

# Readiness thresholds
READINESS_READY_THRESHOLD = 80.0  # >= 80% items ready = "ready"
READINESS_APPROACHING_THRESHOLD = 40.0  # >= 40% items ready = "approaching"

# Safety bound for question pool query to prevent unbounded memory usage
MAX_ITEMS_LIMIT = 10_000

# Response count bucket boundaries
BUCKET_LOW = 9  # Upper bound for "1-9" bucket
BUCKET_MID_LOW = 24  # Upper bound for "10-24" bucket
BUCKET_MID = 49  # Upper bound for "25-49" bucket
BUCKET_MID_HIGH = 99  # Upper bound for "50-99" bucket


def _determine_readiness(readiness_pct: float) -> CalibrationReadiness:
    """
    Determine calibration readiness status based on percentage.

    Args:
        readiness_pct: Percentage of items ready for calibration

    Returns:
        CalibrationReadiness enum value
    """
    if readiness_pct >= READINESS_READY_THRESHOLD:
        return CalibrationReadiness.READY
    elif readiness_pct >= READINESS_APPROACHING_THRESHOLD:
        return CalibrationReadiness.APPROACHING
    else:
        return CalibrationReadiness.NOT_READY


def _bucket_response_count(count: int) -> str:
    """
    Categorize response count into a bucket.

    Args:
        count: Number of responses

    Returns:
        Bucket label as string
    """
    if count == 0:
        return "0"
    elif count <= BUCKET_LOW:
        return "1-9"
    elif count <= BUCKET_MID_LOW:
        return "10-24"
    elif count <= BUCKET_MID:
        return "25-49"
    elif count <= BUCKET_MID_HIGH:
        return "50-99"
    else:
        return "100+"


@router.get("/calibration-status", response_model=CalibrationMonitoringResponse)
async def get_calibration_status(
    min_responses_threshold: int = Query(
        CALIBRATION_READY_THRESHOLD,
        ge=1,
        le=10000,
        description="Minimum responses per item for calibration readiness (default: 50)",
    ),
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get IRT calibration readiness dashboard with comprehensive metrics.

    Returns detailed calibration statistics to help monitor progress toward
    IRT parameter estimation. Tracks response counts per item, per-domain
    aggregates, and progress toward the 500-test threshold.

    Requires X-Admin-Token header with valid admin token.

    **Calibration Requirements:**
    - **Per-item threshold**: >= 50 responses (configurable via query param)
    - **Target tests**: 500 completed test sessions for stable IRT parameters
    - **Domain coverage**: All question types should have sufficient data

    **Response Count Buckets:**
    - `0`: Items with no responses yet
    - `1-9`: Very low response count
    - `10-24`: Low response count
    - `25-49`: Approaching threshold
    - `50-99`: Ready for calibration
    - `100+`: Well-calibrated

    **Readiness Levels:**
    - `ready`: >= 80% of items ready for calibration
    - `approaching`: >= 40% of items ready for calibration
    - `not_ready`: < 40% of items ready for calibration

    Args:
        min_responses_threshold: Minimum responses per item for calibration readiness
        db: Database session
        _: Admin token validation dependency

    Returns:
        CalibrationMonitoringResponse with complete calibration dashboard

    Example:
        ```
        curl "https://api.example.com/v1/admin/calibration-status" \\
          -H "X-Admin-Token: your-admin-token"

        # Use custom threshold
        curl "https://api.example.com/v1/admin/calibration-status?min_responses_threshold=100" \\
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # 1. Count total completed tests
        total_tests = (
            db.query(func.count(TestSession.id))
            .filter(TestSession.status == TestStatus.COMPLETED)
            .scalar()
            or 0
        )

        # 2. Count total responses from completed sessions
        total_responses = (
            db.query(func.count(Response.id))
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .scalar()
            or 0
        )

        # 3. Get per-item response counts (only active, normal quality items)
        # Use the response_count column already stored on the Question model
        item_stats_raw = (
            db.query(
                Question.id,
                Question.question_type,
                Question.difficulty_level,
                Question.response_count,
                Question.empirical_difficulty,
                Question.discrimination,
            )
            .filter(
                Question.is_active == True,  # noqa: E712
                Question.quality_flag == "normal",
            )
            .order_by(Question.id)
            .limit(MAX_ITEMS_LIMIT)
            .all()
        )

        # 4. Build item statistics list
        item_stats: List[ItemCalibrationStats] = []
        for row in item_stats_raw:
            response_count = row.response_count or 0
            item_stats.append(
                ItemCalibrationStats(
                    question_id=row.id,
                    question_type=row.question_type.value,
                    difficulty_level=row.difficulty_level.value,
                    response_count=response_count,
                    empirical_difficulty=row.empirical_difficulty,
                    discrimination=row.discrimination,
                    ready_for_calibration=(response_count >= min_responses_threshold),
                )
            )

        # 5. Calculate overall metrics
        total_active_items = len(item_stats)
        total_items_with_responses = sum(
            1 for item in item_stats if item.response_count > 0
        )
        items_ready = sum(1 for item in item_stats if item.ready_for_calibration)
        overall_readiness_pct = (
            (items_ready / total_active_items * 100) if total_active_items > 0 else 0.0
        )

        # 6. Build per-domain aggregates
        domain_map: Dict[str, List[ItemCalibrationStats]] = {}
        for item in item_stats:
            domain = item.question_type
            if domain not in domain_map:
                domain_map[domain] = []
            domain_map[domain].append(item)

        domains: List[DomainCalibrationStats] = []
        for domain_name, domain_items in domain_map.items():
            items_with_responses = [
                item for item in domain_items if item.response_count > 0
            ]
            total_domain_responses = sum(item.response_count for item in domain_items)
            avg_responses = (
                (total_domain_responses / len(items_with_responses))
                if len(items_with_responses) > 0
                else 0.0
            )
            domain_items_ready = sum(
                1 for item in domain_items if item.ready_for_calibration
            )
            domain_readiness_pct = (
                (domain_items_ready / len(domain_items) * 100)
                if len(domain_items) > 0
                else 0.0
            )

            domains.append(
                DomainCalibrationStats(
                    domain=domain_name,
                    items_with_responses=len(items_with_responses),
                    total_responses=total_domain_responses,
                    avg_responses_per_item=avg_responses,
                    items_ready=domain_items_ready,
                    items_total=len(domain_items),
                    readiness_pct=domain_readiness_pct,
                    readiness=_determine_readiness(domain_readiness_pct),
                )
            )

        # Sort domains by name for consistency
        domains.sort(key=lambda d: d.domain)

        # 7. Build top/bottom item lists
        # Top 20 items by response count
        top_items = sorted(item_stats, key=lambda x: x.response_count, reverse=True)[
            :20
        ]

        # Bottom 20 items by response count (only from items with > 0 responses)
        items_with_responses_list = [
            item for item in item_stats if item.response_count > 0
        ]
        bottom_items = sorted(
            items_with_responses_list, key=lambda x: x.response_count
        )[:20]

        # 8. Build response count distribution
        distribution: Dict[str, int] = {
            "0": 0,
            "1-9": 0,
            "10-24": 0,
            "25-49": 0,
            "50-99": 0,
            "100+": 0,
        }
        for item in item_stats:
            bucket = _bucket_response_count(item.response_count)
            distribution[bucket] += 1

        # 9. Generate alerts
        alerts: List[CalibrationAlert] = []

        # Critical: any domain with avg_responses_per_item < 5
        for domain_stat in domains:
            if domain_stat.avg_responses_per_item < DOMAIN_LOW_RESPONSE_THRESHOLD:
                alerts.append(
                    CalibrationAlert(
                        severity=AlertSeverity.CRITICAL,
                        domain=domain_stat.domain,
                        message=(
                            f"Domain '{domain_stat.domain}' has very low average responses per item "
                            f"({domain_stat.avg_responses_per_item:.1f}). Need more data collection."
                        ),
                    )
                )

        # Warning: low total test count
        if total_tests < LOW_TEST_COUNT_WARNING:
            alerts.append(
                CalibrationAlert(
                    severity=AlertSeverity.WARNING,
                    domain=None,
                    message=(
                        f"Only {total_tests} completed tests collected. "
                        f"Target is {TARGET_COMPLETED_TESTS} for stable IRT calibration."
                    ),
                )
            )

        # Warning: any domain with readiness < 40%
        for domain_stat in domains:
            if domain_stat.readiness == CalibrationReadiness.NOT_READY:
                alerts.append(
                    CalibrationAlert(
                        severity=AlertSeverity.WARNING,
                        domain=domain_stat.domain,
                        message=(
                            f"Domain '{domain_stat.domain}' has low calibration readiness "
                            f"({domain_stat.readiness_pct:.1f}%). Only {domain_stat.items_ready} of "
                            f"{domain_stat.items_total} items ready."
                        ),
                    )
                )

        # 10. Build exit criteria
        overall_avg_responses = (
            (total_responses / total_items_with_responses)
            if total_items_with_responses > 0
            else 0.0
        )
        exit_criteria = ExitCriteria(
            has_500_tests=(total_tests >= TARGET_COMPLETED_TESTS),
            completed_tests=total_tests,
            test_progress_pct=min(total_tests / TARGET_COMPLETED_TESTS * 100, 100.0),
            avg_responses_per_item_sufficient=(
                overall_avg_responses >= min_responses_threshold
            ),
            overall_avg_responses=overall_avg_responses,
        )

        logger.info(
            f"Calibration status retrieved: {total_tests} tests, "
            f"{items_ready}/{total_active_items} items ready, "
            f"{len(alerts)} alerts generated"
        )

        return CalibrationMonitoringResponse(
            total_completed_tests=total_tests,
            total_responses=total_responses,
            total_items_with_responses=total_items_with_responses,
            items_ready_for_calibration=items_ready,
            overall_readiness_pct=overall_readiness_pct,
            domains=domains,
            top_items=top_items,
            bottom_items=bottom_items,
            alerts=alerts,
            exit_criteria=exit_criteria,
            response_count_distribution=distribution,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve calibration status: {e}")
        raise_server_error(
            ErrorMessages.database_operation_failed("retrieve calibration status")
        )
