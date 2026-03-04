"""Answer leakage audit for the question pool.

Detects active questions where correct_answer appears verbatim (case-insensitive)
in question_text and deactivates them. Designed to run as a post-generation step
so leaking questions are caught before they reach users.

Safe to re-run: only targets currently-active questions; a clean pool produces 0 hits.
"""

import logging
from collections import defaultdict
from typing import Callable

from sqlalchemy.orm import Session

from app.data.database import QuestionModel

logger = logging.getLogger(__name__)

MIN_ACTIVE_PER_BUCKET = 10


def _label(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def run_answer_leakage_audit(
    session_factory: Callable[[], Session], dry_run: bool = False
) -> dict:
    """Scan the active question pool for answer leakage and deactivate offenders.

    Args:
        session_factory: A callable that returns a SQLAlchemy Session
                         (e.g. DatabaseService.SessionLocal).
        dry_run: If True, log findings but do not modify the database.

    Returns:
        dict with keys: leaking_count, deactivated_count, low_buckets (list of str).
    """
    result: dict = {"leaking_count": 0, "deactivated_count": 0, "low_buckets": []}

    session: Session = session_factory()
    try:
        active = (
            session.query(QuestionModel).filter(QuestionModel.is_active.is_(True)).all()
        )

        leaking = [
            q
            for q in active
            if q.correct_answer and q.correct_answer.lower() in q.question_text.lower()
        ]

        result["leaking_count"] = len(leaking)

        if not leaking:
            logger.info(
                "[answer-leakage-audit] No leaking questions found. Pool is clean."
            )
        else:
            by_type: dict = defaultdict(int)
            for q in leaking:
                by_type[_label(q.question_type)] += 1

            logger.warning(
                f"[answer-leakage-audit] Found {len(leaking)} answer-leaking question(s): "
                + ", ".join(f"{qt}={cnt}" for qt, cnt in sorted(by_type.items()))
            )
            logger.info(
                "[answer-leakage-audit] Affected IDs: %s",
                [q.id for q in leaking],
            )

            if dry_run:
                logger.info("[answer-leakage-audit] DRY RUN — no changes made.")
            else:
                for q in leaking:
                    q.is_active = False  # type: ignore[assignment]
                    session.add(q)
                session.commit()
                result["deactivated_count"] = len(leaking)
                logger.info(
                    f"[answer-leakage-audit] Deactivated {len(leaking)} question(s)."
                )

        # Pool health check
        active_after = (
            session.query(QuestionModel).filter(QuestionModel.is_active.is_(True)).all()
        )
        bucket_counts: dict = defaultdict(int)
        for q in active_after:
            bucket_counts[(_label(q.question_type), _label(q.difficulty_level))] += 1

        for (qt, dl), count in sorted(bucket_counts.items()):
            if count < MIN_ACTIVE_PER_BUCKET:
                msg = f"{qt}/{dl}={count}"
                result["low_buckets"].append(msg)
                logger.warning(
                    f"[answer-leakage-audit] LOW POOL: {msg} (min {MIN_ACTIVE_PER_BUCKET})"
                )

        if not result["low_buckets"]:
            logger.info(
                "[answer-leakage-audit] All type/difficulty buckets meet the minimum threshold."
            )

    except Exception:
        session.rollback()
        logger.exception("[answer-leakage-audit] Audit failed; rolled back.")
        raise
    finally:
        session.close()

    return result
