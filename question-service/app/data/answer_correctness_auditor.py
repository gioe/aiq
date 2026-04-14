"""Answer correctness audit for the question pool.

Uses the adversarial blind-solve verification approach (judge.verify_answer) to
validate that each active question's marked correct answer is actually correct.
Questions that fail verification are deactivated. Designed to run as a periodic
maintenance step so incorrectly-keyed questions are caught before they reach users.

Safe to re-run: only targets currently-active questions; a clean pool produces 0 hits.
"""

import logging
from collections import defaultdict
from typing import TYPE_CHECKING, Any, Callable, cast

from sqlalchemy.orm import Session

from app.data.answer_leakage_auditor import MIN_ACTIVE_PER_BUCKET, _label
from app.data.db_models import QuestionModel
from app.data.models import GeneratedQuestion
from aiq_types import QuestionType
from gioe_libs.domain_types import DifficultyLevel
from gioe_libs.observability import observability

if TYPE_CHECKING:
    from app.config.judge_config import JudgeConfigLoader
    from app.evaluation.judge import QuestionJudge

logger = logging.getLogger(__name__)


def _model_to_generated(q: QuestionModel) -> GeneratedQuestion:
    """Convert a QuestionModel ORM instance to a GeneratedQuestion dataclass."""
    question_type = q.question_type
    if isinstance(question_type, str):
        question_type = QuestionType(question_type)
    difficulty_level = q.difficulty_level
    if isinstance(difficulty_level, str):
        difficulty_level = DifficultyLevel(difficulty_level)
    return GeneratedQuestion(
        question_text=cast(str, q.question_text),
        question_type=question_type,
        difficulty_level=difficulty_level,
        correct_answer=cast(str, q.correct_answer),
        answer_options=cast(Any, q.answer_options),
        explanation=cast(Any, q.explanation),
        stimulus=cast(Any, q.stimulus),
        sub_type=cast(Any, q.sub_type),
        metadata=cast(Any, q.question_metadata) or {},
        source_llm=cast(str, q.source_llm) or "unknown",
        source_model=cast(str, q.source_model) or "unknown",
    )


def run_answer_correctness_audit(
    session_factory: Callable[[], Session],
    judge: "QuestionJudge",
    judge_config: "JudgeConfigLoader",
) -> dict:
    """Scan the active question pool for answer correctness and deactivate failures.

    Uses the adversarial blind-solve verification flow (judge.verify_answer) to
    independently confirm each question's marked correct answer.

    Args:
        session_factory: A callable that returns a SQLAlchemy Session
                         (e.g. DatabaseService.SessionLocal).
        judge: An initialised QuestionJudge with at least one provider.
        judge_config: Loaded judge configuration for provider resolution.

    Returns:
        dict with keys: scanned, verified_correct, failed, deactivated, skipped,
        errors, low_buckets (list of str), details (list of per-question results).
    """
    result: dict = {
        "scanned": 0,
        "verified_correct": 0,
        "failed": 0,
        "deactivated": 0,
        "skipped": 0,
        "errors": 0,
        "low_buckets": [],
        "details": [],
    }

    session: Session = session_factory()
    try:
        active = (
            session.query(QuestionModel).filter(QuestionModel.is_active.is_(True)).all()
        )
        result["scanned"] = len(active)
        logger.info(
            f"[answer-correctness-audit] Scanning {len(active)} active question(s)."
        )

        failed_questions: list[QuestionModel] = []
        available = list(judge.providers.keys())

        for q in active:
            q_type = _label(q.question_type)
            q_diff = _label(q.difficulty_level)
            try:
                generated = _model_to_generated(q)
                j_provider, j_model = judge_config.resolve_judge_provider(
                    q_type, available
                )
                effective_model = j_model or judge.providers[j_provider].model

                verified, details = judge.verify_answer(
                    question=generated,
                    judge_provider_name=j_provider,
                    judge_model_name=effective_model,
                )

                outcome = details.get("outcome", "")

                if outcome == "skipped":
                    result["skipped"] += 1
                    result["details"].append(
                        {
                            "id": q.id,
                            "type": q_type,
                            "difficulty": q_diff,
                            "outcome": "skipped",
                            "details": details,
                        }
                    )
                elif verified:
                    result["verified_correct"] += 1
                else:
                    result["failed"] += 1
                    failed_questions.append(q)
                    result["details"].append(
                        {
                            "id": q.id,
                            "type": q_type,
                            "difficulty": q_diff,
                            "outcome": "fail",
                            "details": details,
                        }
                    )
                    logger.warning(
                        f"[answer-correctness-audit] Question {q.id} ({q_type}/{q_diff}) "
                        f"failed verification: {details}"
                    )

            except Exception:
                result["errors"] += 1
                result["details"].append(
                    {
                        "id": q.id,
                        "type": q_type,
                        "difficulty": q_diff,
                        "outcome": "error",
                    }
                )
                logger.exception(
                    f"[answer-correctness-audit] Error verifying question {q.id}; "
                    f"skipping (fail-open)."
                )

        # --- Apply MIN_ACTIVE_PER_BUCKET safety check before deactivating ---
        if failed_questions:
            # Count active questions per bucket (before deactivation)
            bucket_counts: dict[tuple[str, str], int] = defaultdict(int)
            for q in active:
                bucket_counts[
                    (_label(q.question_type), _label(q.difficulty_level))
                ] += 1

            to_deactivate: list[QuestionModel] = []
            for q in failed_questions:
                bucket = (_label(q.question_type), _label(q.difficulty_level))
                if bucket_counts[bucket] - 1 >= MIN_ACTIVE_PER_BUCKET:
                    to_deactivate.append(q)
                    bucket_counts[bucket] -= 1
                else:
                    logger.warning(
                        f"[answer-correctness-audit] Cannot deactivate question {q.id} "
                        f"({bucket[0]}/{bucket[1]}): would breach min pool threshold "
                        f"({bucket_counts[bucket]} active, min {MIN_ACTIVE_PER_BUCKET})."
                    )

            for q in to_deactivate:
                q.is_active = False  # type: ignore[assignment]
                session.add(q)
            session.commit()
            result["deactivated"] = len(to_deactivate)

            if to_deactivate:
                logger.info(
                    f"[answer-correctness-audit] Deactivated {len(to_deactivate)} "
                    f"question(s) with incorrect answers."
                )
                logger.info(
                    "[answer-correctness-audit] Deactivated IDs: %s",
                    [q.id for q in to_deactivate],
                )
        else:
            logger.info(
                "[answer-correctness-audit] All questions passed verification. "
                "Pool is clean."
            )

        # --- Pool health check ---
        active_after = (
            session.query(QuestionModel).filter(QuestionModel.is_active.is_(True)).all()
        )
        health_counts: dict[tuple[str, str], int] = defaultdict(int)
        for q in active_after:
            health_counts[(_label(q.question_type), _label(q.difficulty_level))] += 1

        for (qt, dl), count in sorted(health_counts.items()):
            if count < MIN_ACTIVE_PER_BUCKET:
                msg = f"{qt}/{dl}={count}"
                result["low_buckets"].append(msg)
                logger.warning(
                    f"[answer-correctness-audit] LOW POOL: {msg} "
                    f"(min {MIN_ACTIVE_PER_BUCKET})"
                )

        if not result["low_buckets"]:
            logger.info(
                "[answer-correctness-audit] All type/difficulty buckets meet "
                "the minimum threshold."
            )

        # --- Observability metrics ---
        try:
            if observability.is_initialized:
                observability.record_metric(
                    "audit.correctness.scanned",
                    value=result["scanned"],
                    metric_type="counter",
                )
                observability.record_metric(
                    "audit.correctness.failed",
                    value=result["failed"],
                    metric_type="counter",
                )
                observability.record_metric(
                    "audit.correctness.deactivated",
                    value=result["deactivated"],
                    metric_type="counter",
                )
        except Exception:
            logger.debug(
                "[answer-correctness-audit] Failed to record observability metrics.",
                exc_info=True,
            )

    except Exception:
        session.rollback()
        logger.exception("[answer-correctness-audit] Audit failed; rolled back.")
        raise
    finally:
        session.close()

    logger.info(
        f"[answer-correctness-audit] Complete: scanned={result['scanned']}, "
        f"correct={result['verified_correct']}, failed={result['failed']}, "
        f"deactivated={result['deactivated']}, skipped={result['skipped']}, "
        f"errors={result['errors']}"
    )

    return result
