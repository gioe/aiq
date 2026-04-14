"""Phase 2 of the question generation pipeline: judge evaluation."""

import asyncio
import logging
import time
from typing import Optional

from gioe_libs.observability import observability

from app.data.models import EvaluatedQuestion, GeneratedQuestion
from app.evaluation.judge import QuestionJudge
from app.reporting.run_summary import RunSummary as PipelineRunSummary

# Max characters to display for question text in rejection logs
_MAX_DISPLAY_CHARS = 80
_TRUNCATED_DISPLAY_CHARS = 77  # 80 - len("...")

# Questions at or below this leakage score are auto-rejected (answer visible in question)
_LEAKAGE_REJECTION_THRESHOLD = 0.1


def log_rejection_details(
    evaluated_question: EvaluatedQuestion,
    logger: logging.Logger,
    index: Optional[int] = None,
) -> None:
    """Log detailed rejection information for a question.

    Args:
        evaluated_question: The EvaluatedQuestion that was rejected
        logger: Logger instance to use
        index: Optional question index for context
    """
    eval_scores = evaluated_question.evaluation
    question = evaluated_question.question

    # Truncate question text for display
    question_text = question.question_text
    if len(question_text) > _MAX_DISPLAY_CHARS:
        question_text = question_text[:_TRUNCATED_DISPLAY_CHARS] + "..."

    prefix = f"[{index}] " if index is not None else ""

    logger.info(
        f"  {prefix}✗ REJECTED (score: {eval_scores.overall_score:.2f}) - "
        f"{question.question_type.value}/{question.difficulty_level.value}"
    )
    logger.info(f"    Question: {question_text}")
    logger.info(
        f"    Scores: clarity={eval_scores.clarity_score:.2f}, "
        f"difficulty={eval_scores.difficulty_score:.2f}, "
        f"validity={eval_scores.validity_score:.2f}, "
        f"formatting={eval_scores.formatting_score:.2f}, "
        f"creativity={eval_scores.creativity_score:.2f}"
    )
    if eval_scores.feedback:
        logger.info(f"    Feedback: {eval_scores.feedback}")


def apply_difficulty_placement(
    evaluated_question: EvaluatedQuestion,
    judge: QuestionJudge,
    logger: logging.Logger,
):
    """Apply difficulty placement adjustment to an approved question.

    Uses the judge's difficulty score and feedback to determine if the question
    should be placed at a different difficulty level than originally targeted.

    Args:
        evaluated_question: The approved EvaluatedQuestion
        judge: The QuestionJudge instance
        logger: Logger instance for logging adjustments

    Returns:
        EvaluatedQuestion with adjusted difficulty (or original if no change)
    """
    question = evaluated_question.question
    evaluation = evaluated_question.evaluation

    # Determine appropriate difficulty placement
    new_difficulty, reason = judge.determine_difficulty_placement(
        current_difficulty=question.difficulty_level,
        difficulty_score=evaluation.difficulty_score,
        feedback=evaluation.feedback,
    )

    # If no change needed, return original
    if reason is None:
        return evaluated_question

    # Create new question with adjusted difficulty
    adjusted_question = GeneratedQuestion(
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty_level=new_difficulty,
        correct_answer=question.correct_answer,
        answer_options=question.answer_options,
        explanation=question.explanation,
        stimulus=question.stimulus,
        sub_type=question.sub_type,
        metadata={
            **question.metadata,
            "difficulty_adjusted": True,
            "original_difficulty": question.difficulty_level.value,
            "adjustment_reason": reason,
        },
        source_llm=question.source_llm,
        source_model=question.source_model,
    )

    # Create new EvaluatedQuestion with adjusted question
    adjusted_eval = EvaluatedQuestion(
        question=adjusted_question,
        evaluation=evaluation,
        judge_model=evaluated_question.judge_model,
        approved=evaluated_question.approved,
    )

    logger.info(f"    ↳ {reason}")

    return adjusted_eval


def run_judge_phase(
    generated_questions: list,
    judge: QuestionJudge,
    min_score: float,
    use_async_judge: bool,
    metrics: PipelineRunSummary,
    logger: logging.Logger,
) -> tuple[list[EvaluatedQuestion], list[EvaluatedQuestion], float]:
    """Phase 2: Evaluate questions with the judge.

    Returns (approved_questions, rejected_questions, approval_rate).
    """
    evaluation_start = time.perf_counter()
    approved_questions: list = []
    rejected_questions: list = []

    with observability.start_span(
        "phase2_judge_evaluation",
        attributes={
            "min_score": min_score,
            "questions_to_evaluate": len(generated_questions),
        },
    ) as judge_span:
        if use_async_judge:
            logger.info("Using async parallel judge evaluation mode")
            judge_span.set_attribute("mode", "async")

            async def _eval_async() -> list:
                try:
                    return await judge.evaluate_questions_list_async(
                        questions=generated_questions,
                    )
                finally:
                    await judge.cleanup()

            all_evaluated = asyncio.run(_eval_async())
        else:
            judge_span.set_attribute("mode", "sync")
            all_evaluated = []
            for i, question in enumerate(generated_questions, 1):
                logger.info(f"Evaluating question {i}/{len(generated_questions)}...")
                try:
                    all_evaluated.append(judge.evaluate_question(question))
                except Exception as e:
                    logger.error(f"  ✗ Evaluation failed: {e}")
                    observability.capture_error(
                        e,
                        context={"phase": "judge_evaluation", "question_index": i},
                    )

        for evaluated_question in all_evaluated:
            leakage = evaluated_question.evaluation.leakage_score
            if leakage is not None and leakage <= _LEAKAGE_REJECTION_THRESHOLD:
                rejected_questions.append(evaluated_question)
                logger.info(
                    f"  ✗ LEAKAGE REJECTED (leakage_score: {leakage:.2f}) - "
                    f"{evaluated_question.question.question_type.value}/"
                    f"{evaluated_question.question.difficulty_level.value}"
                )
                observability.record_metric(
                    "judge.leakage_rejection",
                    value=1,
                    labels={
                        "question_type": evaluated_question.question.question_type.value,
                        "difficulty": evaluated_question.question.difficulty_level.value,
                    },
                    metric_type="counter",
                )
            elif evaluated_question.evaluation.overall_score >= min_score:
                logger.info(
                    f"  ✓ APPROVED (score: {evaluated_question.evaluation.overall_score:.2f})"
                )
                approved_questions.append(
                    apply_difficulty_placement(evaluated_question, judge, logger)
                )
            else:
                rejected_questions.append(evaluated_question)
                log_rejection_details(evaluated_question, logger)

            metrics.record_evaluation_success(
                score=evaluated_question.evaluation.overall_score,
                approved=evaluated_question.evaluation.overall_score >= min_score,
                judge_model=evaluated_question.judge_model,
            )
            observability.record_metric(
                "judge.evaluation_score",
                value=evaluated_question.evaluation.overall_score,
                metric_type="histogram",
            )

        approval_rate = (
            len(approved_questions) / len(generated_questions) * 100
            if generated_questions
            else 0.0
        )

        judge_span.set_attribute("approved_count", len(approved_questions))
        judge_span.set_attribute("rejected_count", len(rejected_questions))
        judge_span.set_attribute("approval_rate", approval_rate)

        observability.record_metric(
            "judge.approved", value=len(approved_questions), metric_type="counter"
        )
        observability.record_metric(
            "judge.rejected", value=len(rejected_questions), metric_type="counter"
        )

        logger.info(
            f"\nApproved: {len(approved_questions)}/{len(generated_questions)} "
            f"({approval_rate:.1f}%)"
        )
        logger.info(f"Rejected: {len(rejected_questions)}")

        observability.record_metric(
            "pipeline.stage.duration",
            value=time.perf_counter() - evaluation_start,
            labels={"stage": "evaluation"},
            metric_type="histogram",
            unit="s",
        )

    return approved_questions, rejected_questions, approval_rate
