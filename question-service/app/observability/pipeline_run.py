"""Persist pipeline run metadata to the pipeline_runs table.

Provides a single helper that any pipeline can call at the end of a run
to record timing, cost, and outcome data.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session, sessionmaker

from app.data.db_models import PipelineRunModel
from app.observability.cost_tracking import CostTracker

logger = logging.getLogger(__name__)


def record_pipeline_run(
    session_factory: sessionmaker,
    pipeline_type: str,
    started_at: datetime,
    completed_at: datetime,
    cost_tracker: Optional[CostTracker] = None,
    result_summary: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    """Persist a pipeline run record with cost and outcome data.

    Args:
        session_factory: SQLAlchemy sessionmaker bound to the question-service DB.
        pipeline_type: Identifier for the pipeline (e.g. "generation",
            "correctness_audit", "benchmark", "infer_sub_types", "reevaluate").
        started_at: When the pipeline run started.
        completed_at: When the pipeline run finished.
        cost_tracker: Optional CostTracker whose summary will be persisted.
            If None, cost columns are left NULL.
        result_summary: Optional dict of pipeline-specific outcome data
            (stored as JSONB).

    Returns:
        The inserted row ID, or None if persistence failed.
    """
    cost_summary: Dict[str, Any] = {}
    if cost_tracker is not None:
        cost_summary = cost_tracker.get_summary()

    duration = (completed_at - started_at).total_seconds()

    session: Session = session_factory()
    try:
        run = PipelineRunModel(
            pipeline_type=pipeline_type,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=round(duration, 2),
            total_cost_usd=cost_summary.get("total_cost_usd"),
            total_input_tokens=cost_summary.get("total_input_tokens"),
            total_output_tokens=cost_summary.get("total_output_tokens"),
            cost_by_provider=cost_summary.get("by_provider"),
            result_summary=result_summary,
        )
        session.add(run)
        session.commit()
        logger.info(
            "[pipeline-run] Persisted %s run (id=%s, cost=$%s).",
            pipeline_type,
            run.id,
            cost_summary.get("total_cost_usd", "N/A"),
        )
        return int(run.id)
    except Exception:
        session.rollback()
        logger.exception("[pipeline-run] Failed to persist %s run.", pipeline_type)
        return None
    finally:
        session.close()
