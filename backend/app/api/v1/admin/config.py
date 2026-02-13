"""
Scoring configuration admin endpoints.

Endpoints for managing weighted scoring configuration, domain weights,
and A/B testing scoring methods.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.scoring import calculate_weighted_iq_score
from app.core.system_config import (
    async_get_domain_weights,
    async_is_weighted_scoring_enabled,
    async_set_domain_weights,
    async_set_weighted_scoring_enabled,
)
from app.models import TestResult, get_db
from app.schemas.scoring_config import (
    ABComparisonResult,
    ABComparisonScore,
    DomainWeightsRequest,
    DomainWeightsResponse,
    WeightedScoringStatus,
    WeightedScoringToggleRequest,
    WeightedScoringToggleResponse,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()

# Tolerance for checking if domain weights sum to 1.0
# Allows for small floating-point rounding differences
WEIGHT_SUM_TOLERANCE = 0.01


@router.get(
    "/config/weighted-scoring",
    response_model=WeightedScoringStatus,
)
async def get_weighted_scoring_status(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get the current weighted scoring configuration status.

    Returns whether weighted scoring is enabled and the current domain weights
    if configured.

    Requires X-Admin-Token header with valid admin token.

    Returns:
        WeightedScoringStatus with enabled flag and domain weights

    Example:
        ```
        curl "https://api.example.com/v1/admin/config/weighted-scoring" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        enabled = await async_is_weighted_scoring_enabled(db)
        weights = await async_get_domain_weights(db)

        # Get the updated_at timestamp if the config exists
        updated_at = None
        from app.models.models import SystemConfig

        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "use_weighted_scoring")
        )
        record = result.scalar_one_or_none()
        if record:
            updated_at = record.updated_at

        return WeightedScoringStatus(
            enabled=enabled,
            domain_weights=weights,
            updated_at=updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to get weighted scoring status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve weighted scoring status: {str(e)}",
        )


@router.post(
    "/config/weighted-scoring",
    response_model=WeightedScoringToggleResponse,
)
async def toggle_weighted_scoring(
    request: WeightedScoringToggleRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Enable or disable weighted scoring.

    When enabled, IQ scores are calculated using domain weights that reflect
    each domain's correlation with general intelligence (g-loading). When
    disabled, all domains are weighted equally.

    Requires X-Admin-Token header with valid admin token.

    Args:
        request: WeightedScoringToggleRequest with enabled flag

    Returns:
        WeightedScoringToggleResponse with new status and confirmation message

    Example:
        ```
        curl -X POST "https://api.example.com/v1/admin/config/weighted-scoring" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"enabled": true}'
        ```
    """
    try:
        result = await async_set_weighted_scoring_enabled(db, request.enabled)

        action = "enabled" if request.enabled else "disabled"
        message = f"Weighted scoring has been {action}. "
        if request.enabled:
            weights = await async_get_domain_weights(db)
            if weights:
                message += "Configured domain weights will be used for scoring."
            else:
                message += (
                    "Warning: No domain weights configured. "
                    "Equal weights will be used until domain weights are set."
                )
        else:
            message += "Equal weights will be used for all domains."

        return WeightedScoringToggleResponse(
            enabled=request.enabled,
            message=message,
            updated_at=result.updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to toggle weighted scoring: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to toggle weighted scoring: {str(e)}",
        )


@router.get(
    "/config/domain-weights",
    response_model=Optional[DomainWeightsResponse],
)
async def get_domain_weights_config(
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get the current domain weights configuration.

    Returns the configured domain weights used for weighted scoring calculations.

    Requires X-Admin-Token header with valid admin token.

    Returns:
        DomainWeightsResponse with weights, or None if not configured

    Example:
        ```
        curl "https://api.example.com/v1/admin/config/domain-weights" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        weights = await async_get_domain_weights(db)

        if weights is None:
            return None

        # Get the updated_at timestamp
        from app.models.models import SystemConfig

        result = await db.execute(
            select(SystemConfig).where(SystemConfig.key == "domain_weights")
        )
        record = result.scalar_one_or_none()
        updated_at = record.updated_at if record else utc_now()

        return DomainWeightsResponse(
            weights=weights,
            message="Domain weights retrieved successfully.",
            updated_at=updated_at,
        )

    except Exception as e:
        logger.error(f"Failed to get domain weights: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve domain weights: {str(e)}",
        )


@router.post(
    "/config/domain-weights",
    response_model=DomainWeightsResponse,
)
async def set_domain_weights_config(
    request: DomainWeightsRequest,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Set the domain weights for weighted scoring.

    Domain weights determine how much each cognitive domain contributes to the
    final IQ score. Weights should reflect each domain's g-loading (correlation
    with general intelligence).

    The weights should ideally sum to 1.0, but will be normalized during
    scoring calculations if they don't.

    Requires X-Admin-Token header with valid admin token.

    Args:
        request: DomainWeightsRequest with weights dictionary

    Returns:
        DomainWeightsResponse with confirmation

    Example:
        ```
        curl -X POST "https://api.example.com/v1/admin/config/domain-weights" \
          -H "X-Admin-Token: your-admin-token" \
          -H "Content-Type: application/json" \
          -d '{"weights": {"pattern": 0.20, "logic": 0.18, "spatial": 0.16, "math": 0.17, "verbal": 0.15, "memory": 0.14}}'
        ```
    """
    try:
        # Validate that all domain keys are valid
        valid_domains = {"pattern", "logic", "spatial", "math", "verbal", "memory"}
        provided_domains = set(request.weights.keys())

        invalid_domains = provided_domains - valid_domains
        if invalid_domains:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid domain names: {invalid_domains}. "
                f"Valid domains are: {valid_domains}",
            )

        # Validate that weights are positive
        negative_weights = {k: v for k, v in request.weights.items() if v < 0}
        if negative_weights:
            raise HTTPException(
                status_code=400,
                detail=f"Weights must be non-negative. Negative weights found: {negative_weights}",
            )

        # Warn if weights don't sum to 1.0 (but allow it, scoring normalizes)
        weight_sum = sum(request.weights.values())
        message = "Domain weights updated successfully."
        if abs(weight_sum - 1.0) > WEIGHT_SUM_TOLERANCE:
            message += (
                f" Note: Weights sum to {weight_sum:.3f}, not 1.0. "
                "They will be normalized during scoring calculations."
            )

        result = await async_set_domain_weights(db, request.weights)

        return DomainWeightsResponse(
            weights=request.weights,
            message=message,
            updated_at=result.updated_at,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to set domain weights: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to set domain weights: {str(e)}",
        )


@router.get(
    "/scoring/compare/{session_id}",
    response_model=ABComparisonResult,
)
async def compare_scoring_methods(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Calculate and compare both equal-weight and weighted IQ scores for a test session.

    This endpoint is useful for A/B testing weighted scoring before enabling it.
    It recalculates both scores from the stored domain_scores and allows comparison
    without affecting the stored result.

    Requires X-Admin-Token header with valid admin token.

    Args:
        session_id: The test session ID to calculate comparison for

    Returns:
        ABComparisonResult with both scores, difference, and details

    Example:
        ```
        curl "https://api.example.com/v1/admin/scoring/compare/123" \
          -H "X-Admin-Token: your-admin-token"
        ```
    """
    try:
        # Get the test result for this session
        result = await db.execute(
            select(TestResult).where(TestResult.test_session_id == session_id)
        )
        test_result = result.scalar_one_or_none()

        if test_result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Test result for session {session_id} not found",
            )

        # Get domain scores from the test result
        domain_scores = test_result.domain_scores
        if domain_scores is None:
            raise HTTPException(
                status_code=400,
                detail=f"Test session {session_id} does not have domain scores. "
                "Domain scores are required for A/B comparison.",
            )

        # Calculate equal-weight score
        equal_score = calculate_weighted_iq_score(
            domain_scores=domain_scores,
            weights=None,  # Equal weights
        )

        equal_weights_result = ABComparisonScore(
            iq_score=equal_score.iq_score,
            accuracy_percentage=equal_score.accuracy_percentage,
            method="equal_weights",
        )

        # Get configured weights
        weights = await async_get_domain_weights(db)

        # Calculate weighted score if weights are configured
        weighted_score_result: Optional[ABComparisonScore] = None
        score_difference: Optional[int] = None

        if weights:
            weighted_score = calculate_weighted_iq_score(
                domain_scores=domain_scores,
                weights=weights,
            )
            weighted_score_result = ABComparisonScore(
                iq_score=weighted_score.iq_score,
                accuracy_percentage=weighted_score.accuracy_percentage,
                method="weighted",
            )
            score_difference = weighted_score.iq_score - equal_score.iq_score

        return ABComparisonResult(
            equal_weights_score=equal_weights_result,
            weighted_score=weighted_score_result,
            score_difference=score_difference,
            domain_scores=domain_scores,
            weights_used=weights,
            session_id=session_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to compare scoring methods for session {session_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compare scoring methods: {str(e)}",
        )
