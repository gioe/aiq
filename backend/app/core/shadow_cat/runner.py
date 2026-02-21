"""Shadow CAT executor for retrospective adaptive testing validation (TASK-875).

Runs the CAT algorithm on completed fixed-form test responses to compare
theta-based IQ estimates with CTT-based scores. Results are stored in the
shadow_cat_results table for admin analysis.

This module never raises exceptions to callers - all errors are logged
and handled gracefully since shadow testing is instrumentation-only.
"""

import logging
import time
from typing import Any, List, Optional

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.cat.engine import CATSessionManager
from app.core.datetime_utils import utc_now
from app.models.models import (
    Question,
    Response,
    ShadowCATResult,
    TestResult,
    TestSession,
)

# Minimum number of calibrated items required to run shadow CAT.
# Derived from CATSessionManager.MIN_ITEMS to stay in sync.
MIN_CALIBRATED_ITEMS = CATSessionManager.MIN_ITEMS

logger = logging.getLogger(__name__)


def run_shadow_cat(db: Session, session_id: int) -> Optional[ShadowCATResult]:
    """Run shadow CAT retrospectively on a completed fixed-form test.

    Fetches the test session's responses with their IRT parameters,
    processes them through the CAT engine sequentially, and stores
    the shadow result for comparison with the actual CTT-based score.

    Args:
        db: Database session (caller is responsible for closing)
        session_id: ID of the completed test session

    Returns:
        ShadowCATResult if successful, None if skipped or failed.
        Never raises exceptions.
    """
    start_time = time.perf_counter()

    try:
        # 1. Fetch and validate test session
        test_session = db.get(TestSession, session_id)
        if test_session is None:
            logger.warning(f"Shadow CAT: session {session_id} not found")
            return None

        if test_session.is_adaptive:
            logger.debug(
                f"Shadow CAT: skipping session {session_id} (already adaptive)"
            )
            return None

        # 2. Check for existing shadow result (idempotency)
        existing = (
            db.query(ShadowCATResult)
            .filter(ShadowCATResult.test_session_id == session_id)
            .first()
        )
        if existing is not None:
            logger.debug(f"Shadow CAT: session {session_id} already has shadow result")
            return existing

        # 3. Fetch actual IQ from test result
        test_result = (
            db.query(TestResult)
            .filter(TestResult.test_session_id == session_id)
            .first()
        )
        if test_result is None:
            logger.warning(f"Shadow CAT: no test result for session {session_id}")
            return None

        actual_iq = test_result.iq_score

        # 4. Fetch responses with IRT parameters, ordered by answered_at
        responses_with_irt = _fetch_calibrated_responses(db, session_id)

        if len(responses_with_irt) < MIN_CALIBRATED_ITEMS:
            logger.info(
                f"Shadow CAT: session {session_id} has only "
                f"{len(responses_with_irt)} calibrated items "
                f"(need {MIN_CALIBRATED_ITEMS}), skipping"
            )
            return None

        # 5. Run CAT retrospectively
        shadow_result = _execute_shadow_cat(
            responses_with_irt=responses_with_irt,
            session_id=session_id,
            user_id=test_session.user_id,
            actual_iq=actual_iq,
        )

        # 6. Calculate execution time
        execution_time_ms = int((time.perf_counter() - start_time) * 1000)
        shadow_result.execution_time_ms = execution_time_ms

        # 7. Store result
        db.add(shadow_result)
        db.commit()

        logger.info(
            f"Shadow CAT: session {session_id} completed - "
            f"shadow_iq={shadow_result.shadow_iq}, actual_iq={actual_iq}, "
            f"delta={shadow_result.theta_iq_delta:+.1f}, "
            f"items={shadow_result.items_administered}, "
            f"stop={shadow_result.stopping_reason}, "
            f"time={execution_time_ms}ms"
        )

        return shadow_result

    except Exception as e:
        logger.error(
            f"Shadow CAT failed for session {session_id}: {e}",
            exc_info=True,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return None


def _fetch_calibrated_responses(db: Session, session_id: int) -> List[Any]:
    """Fetch responses with calibrated IRT parameters, ordered by answered_at.

    Returns only responses whose questions have both irt_difficulty and
    irt_discrimination set (i.e., have been calibrated).

    Each result is a Row of (Response, Question).
    """
    return (
        db.query(Response, Question)
        .join(Question, Response.question_id == Question.id)
        .filter(
            and_(
                Response.test_session_id == session_id,
                Question.irt_difficulty.isnot(None),
                Question.irt_discrimination.isnot(None),
            )
        )
        .order_by(Response.answered_at)
        .all()
    )


def _execute_shadow_cat(
    responses_with_irt: List[Any],
    session_id: int,
    user_id: int,
    actual_iq: int,
) -> ShadowCATResult:
    """Run the CAT engine on the given responses and build a ShadowCATResult.

    Processes responses sequentially through CATSessionManager, tracking
    theta and SE progression. The CAT may "stop" before all items are
    processed if stopping criteria are met.
    """
    manager = CATSessionManager()
    cat_session = manager.initialize(user_id=user_id, session_id=session_id)

    theta_history: List[float] = []
    se_history: List[float] = []
    administered_ids: List[int] = []
    stop_reason: Optional[str] = None

    for response, question in responses_with_irt:
        # irt_difficulty and irt_discrimination are guaranteed non-None
        # by the _fetch_calibrated_responses filter
        assert question.irt_difficulty is not None
        assert question.irt_discrimination is not None

        step_result = manager.process_response(
            session=cat_session,
            question_id=question.id,
            is_correct=response.is_correct,
            question_type=question.question_type.value,
            irt_difficulty=question.irt_difficulty,
            irt_discrimination=question.irt_discrimination,
        )

        theta_history.append(step_result.theta_estimate)
        se_history.append(step_result.theta_se)
        administered_ids.append(question.id)

        if step_result.should_stop:
            stop_reason = step_result.stop_reason
            break

    # If we exhausted all items without triggering a stop, record that
    if stop_reason is None:
        stop_reason = "all_items_exhausted"

    # Finalize and get IQ conversion
    cat_result = manager.finalize(cat_session, stop_reason)

    # Calculate delta
    theta_iq_delta = float(cat_result.iq_score - actual_iq)

    return ShadowCATResult(
        test_session_id=session_id,
        shadow_theta=cat_result.theta_estimate,
        shadow_se=cat_result.theta_se,
        shadow_iq=cat_result.iq_score,
        items_administered=cat_result.items_administered,
        administered_question_ids=administered_ids,
        stopping_reason=stop_reason,
        actual_iq=actual_iq,
        theta_iq_delta=theta_iq_delta,
        theta_history=theta_history,
        se_history=se_history,
        domain_coverage=dict(cat_session.domain_coverage),
        executed_at=utc_now(),
    )
