"""Phase 1 of the question generation pipeline: question generation."""

import asyncio
import logging
from typing import Optional, TypedDict

from gioe_libs.observability import observability

from app.generation.pipeline import QuestionGenerationPipeline
from app.inventory.inventory_analyzer import GenerationPlan
from app.data.models import GeneratedQuestion
from app.reporting.run_summary import RunSummary as PipelineRunSummary


class GenerationStats(TypedDict):
    questions_generated: int
    target_questions: int
    success_rate: float
    duration_seconds: float
    questions_by_type: dict[str, int]
    questions_by_difficulty: dict[str, int]


def run_optionally_async(async_fn, sync_fn, use_async: bool, cleanup_fn=None):
    """Dispatch to async_fn (via asyncio.run) or sync_fn based on use_async.

    If cleanup_fn is provided and use_async=True, it is awaited in a finally block.
    """
    if use_async:

        async def _wrapper():
            try:
                return await async_fn()
            finally:
                if cleanup_fn is not None:
                    await cleanup_fn()

        return asyncio.run(_wrapper())
    return sync_fn()


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
    from difflib import SequenceMatcher

    if len(questions) <= 1:
        return questions

    unique_questions = []
    seen_texts = []

    for question in questions:
        question_text = question.question_text.lower().strip()

        # Check similarity against all previously seen questions
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


def run_generation_phase(
    pipeline: QuestionGenerationPipeline,
    generation_plan: Optional[GenerationPlan],
    question_types: Optional[list],
    difficulty_distribution: Optional[dict],
    use_async: bool,
    max_concurrent: int,
    timeout: int,
    provider_tier: str,
    count: Optional[int],
    metrics: PipelineRunSummary,
    logger: logging.Logger,
) -> tuple[list[GeneratedQuestion], GenerationStats]:
    """Phase 1: Generate questions.

    Returns (generated_questions, statistics).
    """
    with observability.start_span(
        "phase1_generation",
        attributes={"provider_tier": provider_tier},
    ) as gen_span:
        if generation_plan is not None:
            logger.info("Using auto-balanced generation mode")
            gen_span.set_attribute("mode", "auto_balanced")
            if use_async:
                logger.info(
                    f"Using async parallel generation mode "
                    f"(max_concurrent={max_concurrent}, timeout={timeout}s)"
                )
                pipeline.generator._rate_limiter = asyncio.Semaphore(max_concurrent)
                pipeline.generator._async_timeout = timeout
            job_result = run_optionally_async(
                async_fn=lambda: pipeline.run_balanced_generation_job_async(
                    stratum_allocations=generation_plan.allocations,
                    provider_tier=provider_tier,
                ),
                sync_fn=lambda: pipeline.run_balanced_generation_job(
                    stratum_allocations=generation_plan.allocations,
                    provider_tier=provider_tier,
                ),
                use_async=use_async,
                cleanup_fn=pipeline.cleanup,
            )
        else:
            if use_async:
                logger.info(
                    f"Using async parallel generation mode "
                    f"(max_concurrent={max_concurrent}, timeout={timeout}s)"
                )
                gen_span.set_attribute("mode", "async")
                pipeline.generator._rate_limiter = asyncio.Semaphore(max_concurrent)
                pipeline.generator._async_timeout = timeout
            else:
                gen_span.set_attribute("mode", "sync")
            job_result = run_optionally_async(
                async_fn=lambda: pipeline.run_generation_job_async(
                    questions_per_run=count,
                    question_types=question_types,
                    difficulty_distribution=difficulty_distribution,
                    provider_tier=provider_tier,
                ),
                sync_fn=lambda: pipeline.run_generation_job(
                    questions_per_run=count,
                    question_types=question_types,
                    difficulty_distribution=difficulty_distribution,
                    provider_tier=provider_tier,
                ),
                use_async=use_async,
                cleanup_fn=pipeline.cleanup,
            )

        stats = job_result["statistics"]
        generated_questions = job_result["questions"]

        metrics.questions_requested = stats["target_questions"]
        metrics.questions_generated = stats["questions_generated"]
        metrics.generation_failures = (
            stats["target_questions"] - stats["questions_generated"]
        )
        metrics.questions_by_type = dict(stats.get("questions_by_type", {}))
        metrics.questions_by_difficulty = dict(stats.get("questions_by_difficulty", {}))

        gen_span.set_attribute("questions_generated", stats["questions_generated"])
        gen_span.set_attribute("target_questions", stats["target_questions"])
        gen_span.set_attribute("duration_seconds", stats["duration_seconds"])

        observability.record_metric(
            "generation.questions_produced",
            value=stats["questions_generated"],
            labels={"provider_tier": provider_tier},
            metric_type="counter",
        )
        observability.record_metric(
            "generation.duration",
            value=stats["duration_seconds"],
            labels={"provider_tier": provider_tier},
            metric_type="histogram",
            unit="s",
        )

        logger.info(
            f"Generated: {stats['questions_generated']}/{stats['target_questions']} "
            f"questions ({stats['success_rate']*100:.1f}% success rate)"
        )
        logger.info(f"Duration: {stats['duration_seconds']:.1f}s")

        if generated_questions and len(generated_questions) > 1:
            original_count = len(generated_questions)
            generated_questions = dedupe_within_batch(generated_questions)
            dupes_removed = original_count - len(generated_questions)
            if dupes_removed > 0:
                logger.info(
                    f"Within-batch dedup: Removed {dupes_removed} near-duplicate questions "
                    f"({len(generated_questions)} unique remaining)"
                )
                gen_span.set_attribute("batch_dupes_removed", dupes_removed)

    return generated_questions, stats
