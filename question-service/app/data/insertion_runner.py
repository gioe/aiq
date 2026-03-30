"""Phase 4 of the question generation pipeline: database insertion."""

import logging
import time
from typing import Optional

from gioe_libs.observability import observability

from app.data.database import DatabaseService
from app.reporting.run_summary import RunSummary as PipelineRunSummary


def run_insertion_phase(
    unique_questions: list,
    db: Optional[DatabaseService],
    metrics: PipelineRunSummary,
    logger: logging.Logger,
) -> int:
    """Phase 4: Insert unique questions to the database.

    Returns number of successfully inserted questions.
    """
    if db is None:
        raise ValueError("db is required for insertion phase")

    inserted_count = 0
    storage_start = time.perf_counter()

    with observability.start_span(
        "phase4_db_insertion",
        attributes={"questions_to_insert": len(unique_questions)},
    ) as insert_span:
        for i, evaluated_question in enumerate(unique_questions, 1):
            try:
                question_id = db.insert_evaluated_question(evaluated_question)
                inserted_count += 1
                logger.debug(
                    f"✓ Inserted question {i}/{len(unique_questions)} "
                    f"(ID: {question_id}, score: {evaluated_question.evaluation.overall_score:.2f})"
                )
                metrics.record_insertion_success(
                    count=1,
                    question_type=evaluated_question.question.question_type.value,
                )
            except Exception as e:
                logger.error(f"✗ Failed to insert question {i}: {e}")
                observability.capture_error(
                    e,
                    context={
                        "phase": "db_insertion",
                        "question_index": i,
                        "question_type": evaluated_question.question.question_type.value,
                    },
                )
                metrics.record_insertion_failure(count=1)
                continue

        insert_span.set_attribute("inserted_count", inserted_count)
        insert_span.set_attribute(
            "failed_count", len(unique_questions) - inserted_count
        )

        observability.record_metric(
            "db.questions_inserted", value=inserted_count, metric_type="counter"
        )
        observability.record_metric(
            "pipeline.stage.duration",
            value=time.perf_counter() - storage_start,
            labels={"stage": "storage"},
            metric_type="histogram",
            unit="s",
        )

    logger.info(f"\nInserted: {inserted_count}/{len(unique_questions)} questions")

    return inserted_count
