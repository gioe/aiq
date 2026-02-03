"""
CAT readiness evaluation admin endpoints (TASK-835).

Provides endpoints for evaluating and querying whether the question bank
has enough well-calibrated IRT items to support Computerized Adaptive Testing.
CAT activates only when all 6 domains meet the configured thresholds.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.cat.readiness import evaluate_cat_readiness, serialize_readiness_result
from app.core.datetime_utils import utc_now
from app.core.system_config import (
    get_cat_readiness_status,
    set_cat_readiness,
)
from app.models import get_db
from app.schemas.cat_readiness import (
    CATReadinessResponse,
    CATReadinessThresholds,
    DomainReadinessResponse,
)

from ._dependencies import logger, verify_admin_token

router = APIRouter()


def _build_response_from_config(config: dict) -> CATReadinessResponse:
    """Build a CATReadinessResponse from a stored config dict."""
    return CATReadinessResponse(
        is_globally_ready=config.get("is_globally_ready", False),
        cat_enabled=config.get("enabled", False),
        evaluated_at=config.get("evaluated_at"),
        thresholds=CATReadinessThresholds(**config["thresholds"]),
        domains=[DomainReadinessResponse(**d) for d in config.get("domains", [])],
        summary=config.get("summary", "Never evaluated"),
    )


@router.get(
    "/cat-readiness",
    response_model=CATReadinessResponse,
)
async def get_cat_readiness(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get current CAT readiness status from SystemConfig.

    Returns the most recently persisted readiness evaluation result.
    This is a cheap read from the system_config table — no computation.

    Requires X-Admin-Token header.

    Example:
        ```
        curl "https://api.example.com/v1/admin/cat-readiness" \
          -H "X-Admin-Token: token"
        ```
    """
    config = get_cat_readiness_status(db)

    if config is None:
        # Never evaluated — return default state
        from app.core.config import settings

        return CATReadinessResponse(
            is_globally_ready=False,
            cat_enabled=False,
            evaluated_at=None,
            thresholds=CATReadinessThresholds(
                min_calibrated_items_per_domain=settings.CAT_MIN_CALIBRATED_ITEMS_PER_DOMAIN,
                max_se_difficulty=settings.CAT_MAX_SE_DIFFICULTY,
                max_se_discrimination=settings.CAT_MAX_SE_DISCRIMINATION,
                min_items_per_difficulty_band=settings.CAT_MIN_ITEMS_PER_DIFFICULTY_BAND,
            ),
            domains=[],
            summary="Never evaluated",
        )

    return _build_response_from_config(config)


@router.post(
    "/cat-readiness/evaluate",
    response_model=CATReadinessResponse,
)
async def evaluate_readiness(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    r"""
    Run CAT readiness evaluation and persist result.

    Queries the question bank to evaluate IRT calibration readiness across
    all 6 domains. Enables or disables CAT based on whether all domains
    meet thresholds. The result is persisted to SystemConfig.

    Requires X-Admin-Token header.

    Example:
        ```
        curl -X POST "https://api.example.com/v1/admin/cat-readiness/evaluate" \
          -H "X-Admin-Token: token"
        ```
    """
    result = evaluate_cat_readiness(db)

    now = utc_now()

    config_value = serialize_readiness_result(result, now)
    set_cat_readiness(db, config_value)

    logger.info(
        f"CAT readiness evaluation completed: "
        f"globally_ready={result.is_globally_ready}, "
        f"cat_enabled={result.is_globally_ready}"
    )

    return CATReadinessResponse(
        is_globally_ready=result.is_globally_ready,
        cat_enabled=result.is_globally_ready,
        evaluated_at=now,
        thresholds=CATReadinessThresholds(**result.thresholds),
        domains=[
            DomainReadinessResponse(
                domain=d.domain,
                is_ready=d.is_ready,
                total_calibrated=d.total_calibrated,
                well_calibrated=d.well_calibrated,
                easy_count=d.easy_count,
                medium_count=d.medium_count,
                hard_count=d.hard_count,
                reasons=d.reasons,
            )
            for d in result.domains
        ],
        summary=result.summary,
    )
