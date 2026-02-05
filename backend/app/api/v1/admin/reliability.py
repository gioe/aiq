"""
Reliability metrics admin endpoints.

Endpoints for generating and viewing test reliability reports including
Cronbach's alpha, test-retest reliability, and split-half reliability.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.error_responses import ErrorMessages, raise_server_error
from app.core.reliability import (
    MetricTypeLiteral,
    get_reliability_history,
    get_reliability_report,
    store_reliability_metric,
)
from app.models import get_db
from app.schemas.reliability import (
    InternalConsistencyMetrics,
    ReliabilityHistoryItem,
    ReliabilityHistoryResponse,
    ReliabilityRecommendation,
    ReliabilityReportResponse,
    SplitHalfMetrics,
    TestRetestMetrics,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()


@router.get(
    "/reliability",
    response_model=ReliabilityReportResponse,
    responses={
        401: {"description": "Invalid admin token"},
    },
)
async def get_reliability_report_endpoint(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
    min_sessions: int = Query(
        default=100,
        ge=10,
        description="Minimum sessions required for alpha/split-half calculations",
    ),
    min_retest_pairs: int = Query(
        default=30,
        ge=10,
        description="Minimum retest pairs required for test-retest calculation",
    ),
    store_metrics: bool = Query(
        default=True,
        description="Whether to persist calculated metrics to the database",
    ),
) -> ReliabilityReportResponse:
    """
    Get reliability metrics report for admin dashboard.

    Returns comprehensive reliability metrics including:
    - **Cronbach's alpha**: Measures internal consistency (how well items measure
      the same construct). Target: >= 0.70 for acceptable reliability.
    - **Test-retest reliability**: Measures score stability over time using Pearson
      correlation between consecutive tests. Target: > 0.50 for acceptable reliability.
    - **Split-half reliability**: Measures internal consistency by splitting tests
      into odd/even halves with Spearman-Brown correction. Target: >= 0.70.

    **Interpretation thresholds:**
    - Excellent: alpha/r >= 0.90
    - Good: alpha/r >= 0.80
    - Acceptable: alpha/r >= 0.70 (alpha/split-half) or r > 0.50 (test-retest)
    - Poor: Below acceptable thresholds

    **Data requirements:**
    - Cronbach's alpha and split-half: Minimum 100 completed test sessions
    - Test-retest: Minimum 30 users who have taken the test multiple times

    When `store_metrics=true` (default), calculated metrics are persisted to the
    database for historical trend analysis via the `/reliability/history` endpoint.

    Requires X-Admin-Token header with valid admin token.

    **Caching (RE-FI-019):**
    Results are cached for 5 minutes when `store_metrics=false` to avoid
    recalculating expensive metrics on every request. When `store_metrics=true`,
    fresh calculations are performed to ensure accurate data is stored.
    """
    try:
        # Generate the reliability report (RE-FI-019)
        # When store_metrics=True, bypass cache to ensure fresh data is stored
        # When store_metrics=False, use cache to avoid expensive recalculation
        report = await get_reliability_report(
            db=db,
            min_sessions=min_sessions,
            min_retest_pairs=min_retest_pairs,
            use_cache=not store_metrics,  # Bypass cache when storing metrics
        )

        # Optionally store metrics to database for historical tracking
        # Wrap in try-except to ensure partial writes don't corrupt data
        if store_metrics:
            try:
                # Store Cronbach's alpha if calculated
                alpha = report["internal_consistency"].get("cronbachs_alpha")
                if alpha is not None:
                    await store_reliability_metric(
                        db=db,
                        metric_type="cronbachs_alpha",
                        value=alpha,
                        sample_size=report["internal_consistency"]["num_sessions"],
                        details={
                            "interpretation": report["internal_consistency"].get(
                                "interpretation"
                            ),
                            "meets_threshold": report["internal_consistency"].get(
                                "meets_threshold"
                            ),
                            "num_items": report["internal_consistency"].get(
                                "num_items"
                            ),
                        },
                    )

                # Store test-retest reliability if calculated
                test_retest_r = report["test_retest"].get("correlation")
                if test_retest_r is not None:
                    await store_reliability_metric(
                        db=db,
                        metric_type="test_retest",
                        value=test_retest_r,
                        sample_size=report["test_retest"]["num_pairs"],
                        details={
                            "interpretation": report["test_retest"].get(
                                "interpretation"
                            ),
                            "meets_threshold": report["test_retest"].get(
                                "meets_threshold"
                            ),
                            "mean_interval_days": report["test_retest"].get(
                                "mean_interval_days"
                            ),
                            "practice_effect": report["test_retest"].get(
                                "practice_effect"
                            ),
                        },
                    )

                # Store split-half reliability if calculated
                spearman_brown = report["split_half"].get("spearman_brown")
                if spearman_brown is not None:
                    await store_reliability_metric(
                        db=db,
                        metric_type="split_half",
                        value=spearman_brown,
                        sample_size=report["split_half"]["num_sessions"],
                        details={
                            "interpretation": report["split_half"].get(
                                "interpretation"
                            ),
                            "meets_threshold": report["split_half"].get(
                                "meets_threshold"
                            ),
                            "raw_correlation": report["split_half"].get(
                                "raw_correlation"
                            ),
                        },
                    )
            except Exception as e:
                # Log error but don't fail the request - still return the calculated report
                await db.rollback()
                logger.error(f"Failed to store reliability metrics: {str(e)}")

        # Build response using Pydantic models
        return ReliabilityReportResponse(
            internal_consistency=InternalConsistencyMetrics(
                cronbachs_alpha=report["internal_consistency"].get("cronbachs_alpha"),
                interpretation=report["internal_consistency"].get("interpretation"),
                meets_threshold=report["internal_consistency"]["meets_threshold"],
                num_sessions=report["internal_consistency"]["num_sessions"],
                num_items=report["internal_consistency"].get("num_items"),
                last_calculated=report["internal_consistency"].get("last_calculated"),
                item_total_correlations=report["internal_consistency"].get(
                    "item_total_correlations"
                ),
            ),
            test_retest=TestRetestMetrics(
                correlation=report["test_retest"].get("correlation"),
                interpretation=report["test_retest"].get("interpretation"),
                meets_threshold=report["test_retest"]["meets_threshold"],
                num_pairs=report["test_retest"]["num_pairs"],
                mean_interval_days=report["test_retest"].get("mean_interval_days"),
                practice_effect=report["test_retest"].get("practice_effect"),
                last_calculated=report["test_retest"].get("last_calculated"),
            ),
            split_half=SplitHalfMetrics(
                raw_correlation=report["split_half"].get("raw_correlation"),
                spearman_brown=report["split_half"].get("spearman_brown"),
                meets_threshold=report["split_half"]["meets_threshold"],
                num_sessions=report["split_half"]["num_sessions"],
                last_calculated=report["split_half"].get("last_calculated"),
            ),
            overall_status=report["overall_status"],
            recommendations=[
                ReliabilityRecommendation(
                    category=rec["category"],
                    message=rec["message"],
                    priority=rec["priority"],
                )
                for rec in report["recommendations"]
            ],
        )

    except ValueError as e:
        # Known validation errors - safe to expose
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log full error details but return generic message to client
        logger.error(f"Failed to generate reliability report: {str(e)}", exc_info=True)
        raise_server_error(ErrorMessages.RELIABILITY_REPORT_FAILED)


@router.get(
    "/reliability/history",
    response_model=ReliabilityHistoryResponse,
    responses={
        401: {"description": "Invalid admin token"},
    },
)
async def get_reliability_history_endpoint(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
    metric_type: Optional[MetricTypeLiteral] = Query(
        default=None,
        description="Filter by metric type: cronbachs_alpha, test_retest, split_half",
    ),
    days: int = Query(
        default=90,
        ge=1,
        le=365,
        description="Number of days of history to retrieve (1-365)",
    ),
) -> ReliabilityHistoryResponse:
    """
    Get historical reliability metrics for trend analysis.

    Returns stored reliability metrics from the database, optionally filtered
    by metric type and time period. Metrics are ordered by calculated_at DESC
    (most recent first).

    **Use cases:**
    - Track how reliability metrics change over time as more data is collected
    - Compare reliability across different time periods
    - Monitor the impact of item removals or additions on reliability

    **Query parameters:**
    - `metric_type`: Optional filter to retrieve only one type of metric
      (cronbachs_alpha, test_retest, or split_half)
    - `days`: Number of days of history to retrieve (default: 90, max: 365)

    Requires X-Admin-Token header with valid admin token.
    """
    try:
        # Get historical metrics using the core function.
        # metric_type is already validated by FastAPI via Literal type annotation.
        metrics = await get_reliability_history(
            db=db,
            metric_type=metric_type,
            days=days,
        )

        # Transform to response schema
        history_items = [
            ReliabilityHistoryItem(
                id=m["id"],
                metric_type=m["metric_type"],
                value=m["value"],
                sample_size=m["sample_size"],
                calculated_at=m["calculated_at"],
                details=m["details"],
            )
            for m in metrics
        ]

        return ReliabilityHistoryResponse(
            metrics=history_items,
            total_count=len(history_items),
        )

    except ValueError as e:
        # Known validation errors - safe to expose
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log full error details but return generic message to client
        logger.error(f"Failed to retrieve reliability history: {str(e)}", exc_info=True)
        raise_server_error(ErrorMessages.RELIABILITY_HISTORY_FAILED)
