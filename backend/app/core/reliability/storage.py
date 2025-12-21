"""
Reliability metrics persistence (RE-007).

This module handles storing and retrieving reliability metrics from the database
for historical tracking and trend analysis.

Usage Example:
    from app.core.reliability import store_reliability_metric, get_reliability_history

    # Store a calculated metric
    metric = store_reliability_metric(
        db,
        metric_type="cronbachs_alpha",
        value=0.85,
        sample_size=150,
        details={"interpretation": "good"}
    )

    # Get historical metrics
    history = get_reliability_history(db, metric_type="cronbachs_alpha", days=90)
    for item in history:
        print(f"{item['calculated_at']}: {item['value']:.4f}")

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-007)
"""

import logging
from datetime import timedelta
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now
from app.models.models import ReliabilityMetric
from ._constants import MetricTypeLiteral, VALID_METRIC_TYPES

logger = logging.getLogger(__name__)


def store_reliability_metric(
    db: Session,
    metric_type: MetricTypeLiteral,
    value: float,
    sample_size: int,
    details: Optional[Dict] = None,
    commit: bool = True,
) -> ReliabilityMetric:
    """
    Store a reliability metric to the database for historical tracking.

    This function persists calculated reliability metrics to enable:
    - Historical trend analysis
    - Avoiding recalculation on every request
    - Audit trail of reliability over time

    Args:
        db: Database session
        metric_type: Type of metric - "cronbachs_alpha", "test_retest", or "split_half".
            Uses Literal type for IDE support and mypy type checking.
        value: The calculated reliability coefficient (must be between -1.0 and 1.0)
        sample_size: Number of sessions/pairs used in the calculation (must be >= 1)
        details: Optional additional context (interpretation, thresholds, etc.)
        commit: Whether to commit the transaction immediately. Defaults to True for
            backward compatibility. Set to False when batching multiple metric stores
            in a single transaction (caller must commit).

    Returns:
        Created ReliabilityMetric instance

    Raises:
        ValueError: If metric_type is invalid, value is out of range, or sample_size < 1

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-007)
    """
    # Validate metric type (runtime validation for defense in depth,
    # even though Literal type provides static checking)
    if metric_type not in VALID_METRIC_TYPES:
        raise ValueError(
            f"Invalid metric_type: {metric_type}. "
            f"Must be one of: {', '.join(sorted(VALID_METRIC_TYPES))}"
        )

    # Validate value range (reliability coefficients are between -1.0 and 1.0)
    if not -1.0 <= value <= 1.0:
        raise ValueError(
            f"Invalid value: {value}. "
            "Reliability coefficients must be between -1.0 and 1.0"
        )

    # Validate sample size
    if sample_size < 1:
        raise ValueError(f"Invalid sample_size: {sample_size}. Must be at least 1")

    metric = ReliabilityMetric(
        metric_type=metric_type,
        value=value,
        sample_size=sample_size,
        details=details,
    )

    db.add(metric)

    if commit:
        db.commit()
        db.refresh(metric)
        logger.info(
            f"Stored reliability metric: type={metric_type}, value={value:.4f}, "
            f"sample_size={sample_size}, id={metric.id}"
        )
    else:
        # Flush to get the id without committing the transaction
        db.flush()
        logger.info(
            f"Added reliability metric (uncommitted): type={metric_type}, "
            f"value={value:.4f}, sample_size={sample_size}, id={metric.id}"
        )

    return metric


def get_reliability_history(
    db: Session,
    metric_type: Optional[MetricTypeLiteral] = None,
    days: int = 90,
) -> List[Dict]:
    """
    Get historical reliability metrics for trend analysis.

    Retrieves stored reliability metrics from the database, optionally
    filtered by metric type and time period.

    Args:
        db: Database session
        metric_type: Optional filter for specific metric type
                     ("cronbachs_alpha", "test_retest", "split_half").
                     Uses Literal type for IDE support and mypy type checking.
        days: Number of days of history to retrieve (default: 90)

    Returns:
        List of metrics ordered by calculated_at DESC:
        [
            {
                "id": int,
                "metric_type": str,
                "value": float,
                "sample_size": int,
                "calculated_at": datetime,
                "details": dict or None
            },
            ...
        ]

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-007)
    """
    # Calculate the cutoff date
    cutoff_date = utc_now() - timedelta(days=days)

    # Build query
    query = db.query(ReliabilityMetric).filter(
        ReliabilityMetric.calculated_at >= cutoff_date
    )

    # Apply metric type filter if specified
    if metric_type is not None:
        query = query.filter(ReliabilityMetric.metric_type == metric_type)

    # Order by most recent first
    query = query.order_by(ReliabilityMetric.calculated_at.desc())

    # Execute query and transform to dicts
    metrics = query.all()

    result = [
        {
            "id": m.id,
            "metric_type": m.metric_type,
            "value": m.value,
            "sample_size": m.sample_size,
            "calculated_at": m.calculated_at,
            "details": m.details,
        }
        for m in metrics
    ]

    logger.info(
        f"Retrieved {len(result)} reliability metrics "
        f"(type={metric_type}, days={days})"
    )

    return result
