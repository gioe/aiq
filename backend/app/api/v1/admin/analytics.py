"""
Analytics admin endpoints.

Endpoints for aggregate response time analytics and factor analysis.
"""
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.analytics import (
    InsufficientSampleError,
    build_response_matrix,
    calculate_g_loadings,
)
from app.core.datetime_utils import utc_now
from app.core.time_analysis import get_aggregate_response_time_analytics
from app.models import get_db
from app.schemas.factor_analysis import (
    FactorAnalysisRecommendation,
    FactorAnalysisResponse,
    InsufficientSampleResponse,
    ReliabilityMetrics,
)
from app.schemas.response_time_analytics import (
    AnomalySummary,
    ByDifficultyStats,
    ByQuestionTypeStats,
    DifficultyTimeStats,
    OverallTimeStats,
    QuestionTypeTimeStats,
    ResponseTimeAnalyticsResponse,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()

# =============================================================================
# Psychometric Constants for Factor Analysis
# =============================================================================

MINIMUM_SAMPLE_SIZE_FOR_FACTOR_ANALYSIS = 500

# Psychometric thresholds for factor analysis recommendations
# Based on commonly accepted standards in psychometric literature
ALPHA_POOR_THRESHOLD = 0.6  # Below this is unacceptable reliability
ALPHA_QUESTIONABLE_THRESHOLD = 0.7  # Below this is questionable reliability
ALPHA_GOOD_THRESHOLD = 0.8  # At or above this is good reliability
VARIANCE_LOW_THRESHOLD = 0.20  # Below this suggests weak g-factor
VARIANCE_STRONG_THRESHOLD = 0.40  # At or above this suggests strong g-factor
LOW_G_LOADING_THRESHOLD = (
    0.3  # Domains with loadings below this may measure distinct constructs
)


# =============================================================================
# Response Time Analytics Endpoint
# =============================================================================


@router.get(
    "/analytics/response-times",
    response_model=ResponseTimeAnalyticsResponse,
)
async def get_response_time_analytics(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get aggregate response time analytics across all completed test sessions.

    Returns comprehensive timing statistics including overall test duration,
    breakdown by difficulty level and question type, and a summary of
    timing anomalies (rapid responses, extended times, validity concerns).

    Requires X-Admin-Token header with valid admin token.

    **Overall Statistics:**
    - Mean and median total test duration in seconds
    - Mean time per question across all responses

    **By Difficulty:**
    - Mean and median response time for easy, medium, and hard questions

    **By Question Type:**
    - Mean response time for each question type (pattern, logic, spatial, math, verbal, memory)

    **Anomaly Summary:**
    - Count of sessions with rapid responses (< 3 seconds per question)
    - Count of sessions with extended response times (> 5 minutes per question)
    - Percentage of sessions flagged with validity concerns

    Args:
        db: Database session
        _: Admin token validation dependency

    Returns:
        ResponseTimeAnalyticsResponse with aggregate timing statistics

    Example:
        ```
        curl "https://api.example.com/v1/admin/analytics/response-times" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get aggregate analytics from time_analysis module
        analytics = get_aggregate_response_time_analytics(db)

        # Build response using Pydantic models
        overall = OverallTimeStats(
            mean_test_duration_seconds=analytics["overall"][
                "mean_test_duration_seconds"
            ],
            median_test_duration_seconds=analytics["overall"][
                "median_test_duration_seconds"
            ],
            mean_per_question_seconds=analytics["overall"]["mean_per_question_seconds"],
        )

        by_difficulty = ByDifficultyStats(
            easy=DifficultyTimeStats(
                mean_seconds=analytics["by_difficulty"]["easy"]["mean_seconds"],
                median_seconds=analytics["by_difficulty"]["easy"]["median_seconds"],
            ),
            medium=DifficultyTimeStats(
                mean_seconds=analytics["by_difficulty"]["medium"]["mean_seconds"],
                median_seconds=analytics["by_difficulty"]["medium"]["median_seconds"],
            ),
            hard=DifficultyTimeStats(
                mean_seconds=analytics["by_difficulty"]["hard"]["mean_seconds"],
                median_seconds=analytics["by_difficulty"]["hard"]["median_seconds"],
            ),
        )

        by_question_type = ByQuestionTypeStats(
            pattern=QuestionTypeTimeStats(
                mean_seconds=analytics["by_question_type"]["pattern"]["mean_seconds"],
            ),
            logic=QuestionTypeTimeStats(
                mean_seconds=analytics["by_question_type"]["logic"]["mean_seconds"],
            ),
            spatial=QuestionTypeTimeStats(
                mean_seconds=analytics["by_question_type"]["spatial"]["mean_seconds"],
            ),
            math=QuestionTypeTimeStats(
                mean_seconds=analytics["by_question_type"]["math"]["mean_seconds"],
            ),
            verbal=QuestionTypeTimeStats(
                mean_seconds=analytics["by_question_type"]["verbal"]["mean_seconds"],
            ),
            memory=QuestionTypeTimeStats(
                mean_seconds=analytics["by_question_type"]["memory"]["mean_seconds"],
            ),
        )

        anomaly_summary = AnomalySummary(
            sessions_with_rapid_responses=analytics["anomaly_summary"][
                "sessions_with_rapid_responses"
            ],
            sessions_with_extended_times=analytics["anomaly_summary"][
                "sessions_with_extended_times"
            ],
            pct_flagged=analytics["anomaly_summary"]["pct_flagged"],
        )

        return ResponseTimeAnalyticsResponse(
            overall=overall,
            by_difficulty=by_difficulty,
            by_question_type=by_question_type,
            anomaly_summary=anomaly_summary,
            total_sessions_analyzed=analytics["total_sessions_analyzed"],
            total_responses_analyzed=analytics["total_responses_analyzed"],
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve response time analytics: {str(e)}",
        )


# =============================================================================
# Factor Analysis Helper
# =============================================================================


def _generate_recommendations(
    g_loadings: Dict[str, float],
    variance_explained: float,
    cronbachs_alpha: float,
    sample_size: int,
) -> List[FactorAnalysisRecommendation]:
    """
    Generate recommendations based on factor analysis results.

    Args:
        g_loadings: Dictionary mapping domain names to g-loading values.
        variance_explained: Proportion of variance explained by g-factor.
        cronbachs_alpha: Cronbach's alpha reliability coefficient.
        sample_size: Number of sessions used in analysis.

    Returns:
        List of recommendations.
    """
    recommendations: List[FactorAnalysisRecommendation] = []

    # Sample size recommendations
    if sample_size < 1000:
        recommendations.append(
            FactorAnalysisRecommendation(
                category="sample_size",
                message=f"Current sample size ({sample_size}) is adequate but larger samples "
                "provide more stable factor loading estimates. Consider rerunning after "
                "reaching 1000+ sessions.",
                severity="info",
            )
        )

    # Reliability recommendations
    if cronbachs_alpha < ALPHA_POOR_THRESHOLD:
        recommendations.append(
            FactorAnalysisRecommendation(
                category="reliability",
                message=f"Cronbach's alpha ({cronbachs_alpha:.2f}) is below acceptable threshold. "
                "This suggests the items may not be measuring a coherent construct. "
                "Review question quality and consider removing poorly-performing items.",
                severity="critical",
            )
        )
    elif cronbachs_alpha < ALPHA_QUESTIONABLE_THRESHOLD:
        recommendations.append(
            FactorAnalysisRecommendation(
                category="reliability",
                message=f"Cronbach's alpha ({cronbachs_alpha:.2f}) is questionable. "
                "Consider reviewing items with low item-total correlations.",
                severity="warning",
            )
        )
    elif cronbachs_alpha >= ALPHA_GOOD_THRESHOLD:
        recommendations.append(
            FactorAnalysisRecommendation(
                category="reliability",
                message=f"Cronbach's alpha ({cronbachs_alpha:.2f}) indicates good internal consistency.",
                severity="info",
            )
        )

    # Variance explained recommendations
    if variance_explained < VARIANCE_LOW_THRESHOLD:
        recommendations.append(
            FactorAnalysisRecommendation(
                category="variance",
                message=f"Variance explained ({variance_explained:.1%}) is low. "
                "A single g-factor may not adequately capture the test's structure. "
                "Consider a multi-factor model.",
                severity="warning",
            )
        )
    elif variance_explained >= VARIANCE_STRONG_THRESHOLD:
        recommendations.append(
            FactorAnalysisRecommendation(
                category="variance",
                message=f"Variance explained ({variance_explained:.1%}) indicates a strong g-factor. "
                "The test items are well-suited for measuring general cognitive ability.",
                severity="info",
            )
        )

    # Loading-based recommendations
    if g_loadings:
        sorted_loadings = sorted(g_loadings.items(), key=lambda x: x[1], reverse=True)
        highest_domain, highest_loading = sorted_loadings[0]
        lowest_domain, lowest_loading = sorted_loadings[-1]

        recommendations.append(
            FactorAnalysisRecommendation(
                category="loadings",
                message=f"Highest g-loading: {highest_domain} ({highest_loading:.2f}). "
                f"Lowest g-loading: {lowest_domain} ({lowest_loading:.2f}). "
                "Consider weighting domains proportionally to their g-loadings for IQ scoring.",
                severity="info",
            )
        )

        # Flag domains with very low loadings
        low_loading_domains = [
            domain
            for domain, loading in g_loadings.items()
            if loading < LOW_G_LOADING_THRESHOLD
        ]
        if low_loading_domains:
            recommendations.append(
                FactorAnalysisRecommendation(
                    category="loadings",
                    message=f"Domains with low g-loadings (<{LOW_G_LOADING_THRESHOLD:.2f}): "
                    f"{', '.join(low_loading_domains)}. "
                    "These domains may be measuring something distinct from general intelligence. "
                    "Consider reviewing or reducing their weight in composite scoring.",
                    severity="warning",
                )
            )

    return recommendations


# =============================================================================
# Factor Analysis Endpoint
# =============================================================================


@router.get(
    "/analytics/factor-analysis",
    response_model=FactorAnalysisResponse,
    responses={
        400: {"model": InsufficientSampleResponse},
        401: {"description": "Invalid admin token"},
    },
)
async def get_factor_analysis(
    _: bool = Depends(verify_admin_token),
    db: Session = Depends(get_db),
    min_responses_per_question: int = Query(
        default=30,
        ge=10,
        le=200,
        description="Minimum responses per question for inclusion",
    ),
    max_responses: int = Query(
        default=10000,
        ge=0,
        le=1000000,
        description="Maximum responses to fetch. Set to 0 for no limit (use with caution).",
    ),
):
    """
    Perform factor analysis to calculate empirical g-loadings per domain.

    This endpoint runs a factor analysis on all completed test sessions to
    determine how strongly each cognitive domain correlates with general
    intelligence (g). Results can be used to inform weighted scoring.

    **Requirements:**
    - Minimum 500 completed test sessions
    - Questions must have at least min_responses_per_question responses

    **Returns:**
    - g_loadings: Correlation of each domain with the g-factor (0-1)
    - variance_explained: How much variance the g-factor explains
    - reliability: Cronbach's alpha for internal consistency
    - recommendations: Actionable insights based on the results

    **Interpretation:**
    - Higher g-loadings indicate stronger correlation with general intelligence
    - Variance explained > 40% suggests a strong general factor
    - Cronbach's alpha >= 0.7 indicates acceptable reliability

    Requires X-Admin-Token header with valid admin token.
    """
    try:
        # Build the response matrix from completed test sessions
        response_matrix = build_response_matrix(
            db=db,
            min_responses_per_question=min_responses_per_question,
            min_questions_per_session=10,
            max_responses=max_responses,
        )

        # Check if we have enough data
        if response_matrix is None:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "insufficient_sample",
                    "message": "No completed test sessions with sufficient data found.",
                    "sample_size": 0,
                    "minimum_required": MINIMUM_SAMPLE_SIZE_FOR_FACTOR_ANALYSIS,
                    "recommendation": "At least 500 completed test sessions are needed "
                    "before factor analysis can be performed.",
                },
            )

        # Check if sample size meets minimum requirement
        if response_matrix.n_users < MINIMUM_SAMPLE_SIZE_FOR_FACTOR_ANALYSIS:
            shortfall = (
                MINIMUM_SAMPLE_SIZE_FOR_FACTOR_ANALYSIS - response_matrix.n_users
            )
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "insufficient_sample",
                    "message": f"Sample size ({response_matrix.n_users}) is below minimum "
                    f"({MINIMUM_SAMPLE_SIZE_FOR_FACTOR_ANALYSIS}) required for reliable factor analysis.",
                    "sample_size": response_matrix.n_users,
                    "minimum_required": MINIMUM_SAMPLE_SIZE_FOR_FACTOR_ANALYSIS,
                    "recommendation": f"Approximately {shortfall} more completed test sessions "
                    "are needed before factor analysis can be performed.",
                },
            )

        # Calculate g-loadings
        g_result = calculate_g_loadings(
            response_matrix=response_matrix,
            min_sample_size=100,  # Internal check, we've already verified 500+
            min_variance_per_item=0.01,
        )

        # Generate recommendations
        recommendations = _generate_recommendations(
            g_loadings=g_result.domain_loadings,
            variance_explained=g_result.variance_explained,
            cronbachs_alpha=g_result.cronbachs_alpha,
            sample_size=g_result.sample_size,
        )

        return FactorAnalysisResponse(
            analysis_date=utc_now(),
            sample_size=g_result.sample_size,
            n_items=g_result.n_items,
            g_loadings=g_result.domain_loadings,
            variance_explained=g_result.variance_explained,
            reliability=ReliabilityMetrics(
                cronbachs_alpha=g_result.cronbachs_alpha,
            ),
            recommendations=recommendations,
            warnings=g_result.analysis_warnings,
        )

    except InsufficientSampleError as e:
        shortfall = e.minimum_required - e.sample_size
        raise HTTPException(
            status_code=400,
            detail={
                "error": "insufficient_sample",
                "message": str(e),
                "sample_size": e.sample_size,
                "minimum_required": e.minimum_required,
                "recommendation": f"Approximately {shortfall} more valid items are needed "
                "before factor analysis can be performed.",
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Factor analysis failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to perform factor analysis: {str(e)}",
        )
