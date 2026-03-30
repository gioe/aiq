"""Phase 3 of the question generation pipeline: deduplication."""

import logging
import time
from difflib import SequenceMatcher

from gioe_libs.observability import observability

from app.data.database import DatabaseService as QuestionDatabase
from app.data.deduplicator import QuestionDeduplicator
from app.data.models import EvaluatedQuestion
from app.reporting.run_summary import RunSummary as PipelineRunSummary


def dedupe_within_batch(
    questions: list,
    similarity_threshold: float = 0.85,
) -> list:
    """Remove near-duplicate questions within a batch before judge evaluation.

    Uses simple text similarity to identify questions that are too similar,
    saving API calls to the judge for redundant questions.

    Args:
        questions: List of GeneratedQuestion objects
        similarity_threshold: Similarity ratio above which questions are considered duplicates

    Returns:
        Filtered list with duplicates removed (keeps first occurrence)
    """
    if len(questions) <= 1:
        return questions

    unique_questions = []
    seen_texts = []

    for question in questions:
        question_text = question.question_text.lower().strip()

        is_duplicate = False
        for seen_text in seen_texts:
            similarity = SequenceMatcher(None, question_text, seen_text).ratio()
            if similarity >= similarity_threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            unique_questions.append(question)
            seen_texts.append(question_text)

    return unique_questions


def run_dedup_phase(
    approved_questions: list,
    db: QuestionDatabase,
    deduplicator: QuestionDeduplicator,
    metrics: PipelineRunSummary,
    logger: logging.Logger,
) -> list[EvaluatedQuestion]:
    """Phase 3: Deduplicate approved questions against the database.

    Returns list of unique questions.
    """
    if db is None:
        raise ValueError("db must not be None")
    if deduplicator is None:
        raise ValueError("deduplicator must not be None")

    dedup_start = time.perf_counter()
    with observability.start_span(
        "phase3_deduplication",
        attributes={"approved_count": len(approved_questions)},
    ) as dedup_span:
        try:
            existing_questions = db.get_all_questions()
            logger.info(
                f"Loaded {len(existing_questions)} existing questions for deduplication"
            )
            dedup_span.set_attribute("existing_questions", len(existing_questions))
        except Exception as e:
            logger.error(f"Failed to load existing questions: {e}")
            observability.capture_error(
                e, context={"phase": "deduplication", "step": "load_existing"}
            )
            existing_questions = []

        unique_questions = []
        duplicate_count = 0

        for evaluated_question in approved_questions:
            try:
                q_difficulty = str(
                    evaluated_question.question.difficulty_level.value
                ).lower()
                same_difficulty_questions = [
                    eq
                    for eq in existing_questions
                    if str(
                        getattr(
                            eq.get("difficulty_level", ""),
                            "value",
                            eq.get("difficulty_level", ""),
                        )
                    ).lower()
                    == q_difficulty
                ]
                result = deduplicator.check_duplicate(
                    evaluated_question.question, same_difficulty_questions
                )

                if not result.is_duplicate:
                    unique_questions.append(evaluated_question)
                    logger.debug(
                        f"✓ Unique: {evaluated_question.question.question_text[:60]}..."
                    )
                else:
                    duplicate_count += 1
                    logger.info(
                        f"✗ Duplicate ({result.duplicate_type}, score={result.similarity_score:.3f}): "
                        f"{evaluated_question.question.question_text[:60]}..."
                    )

                metrics.record_duplicate_check(
                    is_duplicate=result.is_duplicate,
                    duplicate_type=result.duplicate_type,
                )

                if result.is_duplicate:
                    observability.record_metric(
                        "dedup.by_type",
                        value=1,
                        labels={"duplicate_type": result.duplicate_type or "unknown"},
                        metric_type="counter",
                    )

            except Exception as e:
                logger.error(f"Deduplication check failed: {e}")
                observability.capture_error(
                    e, context={"phase": "deduplication", "step": "check"}
                )
                unique_questions.append(evaluated_question)
                continue

        dedup_span.set_attribute("unique_count", len(unique_questions))
        dedup_span.set_attribute("duplicate_count", duplicate_count)

        observability.record_metric(
            "dedup.duplicates_removed", value=duplicate_count, metric_type="counter"
        )

        logger.info(f"\nUnique questions: {len(unique_questions)}")
        logger.info(f"Duplicates removed: {duplicate_count}")

        observability.record_metric(
            "pipeline.stage.duration",
            value=time.perf_counter() - dedup_start,
            labels={"stage": "dedup"},
            metric_type="histogram",
            unit="s",
        )

        cache_stats = deduplicator.get_stats()["cache"]
        observability.record_metric(
            "embedding.cache.hit",
            value=cache_stats.get("hits", 0),
            metric_type="counter",
        )
        observability.record_metric(
            "embedding.cache.miss",
            value=cache_stats.get("misses", 0),
            metric_type="counter",
        )

    return unique_questions
