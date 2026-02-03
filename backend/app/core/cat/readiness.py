"""
CAT readiness evaluation service (TASK-835).

Evaluates whether the question bank has enough well-calibrated IRT items
across all 6 cognitive domains to support Computerized Adaptive Testing.
CAT activates only when every domain meets the configured thresholds.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.models import Question, QuestionType

logger = logging.getLogger(__name__)


@dataclass
class DomainReadiness:
    """Per-domain CAT readiness evaluation result."""

    domain: str
    is_ready: bool
    total_calibrated: int
    well_calibrated: int
    easy_count: int  # IRT b < -1.0
    medium_count: int  # -1.0 <= IRT b <= 1.0
    hard_count: int  # IRT b > 1.0
    reasons: List[str] = field(default_factory=list)


@dataclass
class CATReadinessResult:
    """Global CAT readiness evaluation result."""

    is_globally_ready: bool
    domains: List[DomainReadiness]
    summary: str
    thresholds: dict


def evaluate_cat_readiness(db: Session) -> CATReadinessResult:
    """
    Evaluate whether the question bank is ready for CAT across all domains.

    Per-domain evaluation:
    1. Query active, normal-quality questions with irt_calibrated_at IS NOT NULL
    2. Filter to items where irt_se_difficulty <= threshold AND
       irt_se_discrimination <= threshold
    3. Count items in 3 IRT difficulty bands: easy (b < -1.0),
       medium (-1.0 <= b <= 1.0), hard (b > 1.0)
    4. Domain passes if: total well-calibrated >= min AND each band has >= min items

    Global readiness: all domains must pass.

    Args:
        db: Database session

    Returns:
        CATReadinessResult with per-domain breakdown
    """
    min_items = settings.CAT_MIN_CALIBRATED_ITEMS_PER_DOMAIN
    max_se_diff = settings.CAT_MAX_SE_DIFFICULTY
    max_se_disc = settings.CAT_MAX_SE_DISCRIMINATION
    min_per_band = settings.CAT_MIN_ITEMS_PER_DIFFICULTY_BAND

    thresholds = {
        "min_calibrated_items_per_domain": min_items,
        "max_se_difficulty": max_se_diff,
        "max_se_discrimination": max_se_disc,
        "min_items_per_difficulty_band": min_per_band,
    }

    domain_results: List[DomainReadiness] = []

    for q_type in QuestionType:
        domain_name = q_type.value

        # Count all calibrated items (regardless of SE quality)
        total_calibrated = (
            db.query(func.count(Question.id))
            .filter(
                Question.question_type == q_type,
                Question.is_active.is_(True),
                Question.quality_flag == "normal",
                Question.irt_calibrated_at.isnot(None),
            )
            .scalar()
            or 0
        )

        # Query well-calibrated items (SE below thresholds)
        well_calibrated_query = db.query(Question).filter(
            Question.question_type == q_type,
            Question.is_active.is_(True),
            Question.quality_flag == "normal",
            Question.irt_calibrated_at.isnot(None),
            Question.irt_se_difficulty.isnot(None),
            Question.irt_se_discrimination.isnot(None),
            Question.irt_se_difficulty <= max_se_diff,
            Question.irt_se_discrimination <= max_se_disc,
            Question.irt_difficulty.isnot(None),
        )

        well_calibrated_items = well_calibrated_query.all()
        well_calibrated_count = len(well_calibrated_items)

        # Count items in IRT difficulty bands
        # irt_difficulty is guaranteed non-None by the query filter above
        easy_count = sum(
            1
            for q in well_calibrated_items
            if q.irt_difficulty is not None and q.irt_difficulty < -1.0
        )
        medium_count = sum(
            1
            for q in well_calibrated_items
            if q.irt_difficulty is not None and -1.0 <= q.irt_difficulty <= 1.0
        )
        hard_count = sum(
            1
            for q in well_calibrated_items
            if q.irt_difficulty is not None and q.irt_difficulty > 1.0
        )

        # Evaluate domain readiness
        reasons: List[str] = []
        is_ready = True

        if well_calibrated_count < min_items:
            is_ready = False
            reasons.append(
                f"Insufficient well-calibrated items: {well_calibrated_count}/{min_items}"
            )

        if easy_count < min_per_band:
            is_ready = False
            reasons.append(
                f"Insufficient easy items (b < -1.0): {easy_count}/{min_per_band}"
            )

        if medium_count < min_per_band:
            is_ready = False
            reasons.append(
                f"Insufficient medium items (-1.0 <= b <= 1.0): {medium_count}/{min_per_band}"
            )

        if hard_count < min_per_band:
            is_ready = False
            reasons.append(
                f"Insufficient hard items (b > 1.0): {hard_count}/{min_per_band}"
            )

        domain_results.append(
            DomainReadiness(
                domain=domain_name,
                is_ready=is_ready,
                total_calibrated=total_calibrated,
                well_calibrated=well_calibrated_count,
                easy_count=easy_count,
                medium_count=medium_count,
                hard_count=hard_count,
                reasons=reasons,
            )
        )

    is_globally_ready = all(d.is_ready for d in domain_results)

    ready_count = sum(1 for d in domain_results if d.is_ready)
    total_domains = len(domain_results)
    summary = f"{ready_count}/{total_domains} domains ready for CAT"

    logger.info(
        f"CAT readiness evaluation: globally_ready={is_globally_ready}, {summary}"
    )

    return CATReadinessResult(
        is_globally_ready=is_globally_ready,
        domains=domain_results,
        summary=summary,
        thresholds=thresholds,
    )


def serialize_readiness_result(
    result: CATReadinessResult, evaluated_at: datetime
) -> dict:
    """
    Serialize a CATReadinessResult into the dict format stored in SystemConfig.

    Args:
        result: The evaluation result to serialize
        evaluated_at: Timestamp of the evaluation

    Returns:
        Dictionary suitable for persisting via set_cat_readiness()
    """
    return {
        "enabled": result.is_globally_ready,
        "is_globally_ready": result.is_globally_ready,
        "evaluated_at": evaluated_at.isoformat(),
        "thresholds": result.thresholds,
        "domains": [
            {
                "domain": d.domain,
                "is_ready": d.is_ready,
                "total_calibrated": d.total_calibrated,
                "well_calibrated": d.well_calibrated,
                "easy_count": d.easy_count,
                "medium_count": d.medium_count,
                "hard_count": d.hard_count,
                "reasons": d.reasons,
            }
            for d in result.domains
        ],
        "summary": result.summary,
    }
