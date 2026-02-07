"""Question generation pipeline orchestrator.

This module provides the main pipeline for generating questions,
coordinating the generator, judge, and other components.
"""

import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .config import settings
from .generator import QuestionGenerator
from .models import (
    DifficultyLevel,
    GenerationBatch,
    QuestionType,
)

# Import observability facade for distributed tracing
try:
    from libs.observability import observability
except ImportError:
    # Fallback for environments where libs.observability isn't installed as a package
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from libs.observability import observability  # noqa: E402

logger = logging.getLogger(__name__)


class QuestionGenerationPipeline:
    """Orchestrates the complete question generation pipeline.

    This class coordinates question generation across multiple LLM providers
    and prepares questions for evaluation by the judge.
    """

    def __init__(
        self,
        openai_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        google_api_key: Optional[str] = None,
        xai_api_key: Optional[str] = None,
    ):
        """Initialize the question generation pipeline.

        Args:
            openai_api_key: OpenAI API key (uses settings if not provided)
            anthropic_api_key: Anthropic API key (uses settings if not provided)
            google_api_key: Google API key (uses settings if not provided)
            xai_api_key: xAI (Grok) API key (uses settings if not provided)
        """
        # Use provided keys or fall back to settings
        self.openai_key = openai_api_key or settings.openai_api_key
        self.anthropic_key = anthropic_api_key or settings.anthropic_api_key
        self.google_key = google_api_key or settings.google_api_key
        self.xai_key = xai_api_key or settings.xai_api_key

        # Initialize generator
        self.generator = QuestionGenerator(
            openai_api_key=self.openai_key,
            anthropic_api_key=self.anthropic_key,
            google_api_key=self.google_key,
            xai_api_key=self.xai_key,
        )

        logger.info("Question generation pipeline initialized")

    def generate_questions(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int = 10,
        distribute_providers: bool = True,
        provider_tier: Optional[str] = None,
    ) -> GenerationBatch:
        """Generate a batch of questions for a specific type and difficulty.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Number of questions to generate
            distribute_providers: Whether to distribute across providers
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Batch of generated questions

        Raises:
            Exception: If generation fails
        """
        with observability.start_span(
            "pipeline.generate_questions",
            attributes={
                "question_type": question_type.value,
                "difficulty": difficulty.value,
                "count": count,
            },
        ) as span:
            try:
                logger.info(
                    f"Pipeline: Generating {count} {question_type.value} questions "
                    f"at {difficulty.value} difficulty"
                )

                batch = self.generator.generate_batch(
                    question_type=question_type,
                    difficulty=difficulty,
                    count=count,
                    distribute_across_providers=distribute_providers,
                    provider_tier=provider_tier,
                )

                span.set_attribute("success", True)
                span.set_attribute("questions_generated", len(batch.questions))
                logger.info(
                    f"Pipeline: Generated {len(batch.questions)}/{count} questions successfully"
                )

                return batch
            except Exception as e:
                span.set_attribute("success", False)
                span.set_status("error", str(e))
                raise

    async def generate_questions_async(
        self,
        question_type: QuestionType,
        difficulty: DifficultyLevel,
        count: int = 10,
        distribute_providers: bool = True,
        provider_tier: Optional[str] = None,
    ) -> GenerationBatch:
        """Generate a batch of questions asynchronously for a specific type and difficulty.

        This method generates questions in parallel, significantly reducing total
        generation time compared to sequential generation.

        Args:
            question_type: Type of questions to generate
            difficulty: Difficulty level
            count: Number of questions to generate
            distribute_providers: Whether to distribute across providers
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Batch of generated questions

        Raises:
            Exception: If generation fails
        """
        with observability.start_span(
            "pipeline.generate_questions_async",
            attributes={
                "question_type": question_type.value,
                "difficulty": difficulty.value,
                "count": count,
            },
        ) as span:
            try:
                logger.info(
                    f"Pipeline (async): Generating {count} {question_type.value} questions "
                    f"at {difficulty.value} difficulty"
                )

                batch = await self.generator.generate_batch_async(
                    question_type=question_type,
                    difficulty=difficulty,
                    count=count,
                    distribute_across_providers=distribute_providers,
                    provider_tier=provider_tier,
                )

                span.set_attribute("success", True)
                span.set_attribute("questions_generated", len(batch.questions))
                logger.info(
                    f"Pipeline (async): Generated {len(batch.questions)}/{count} questions successfully"
                )

                return batch
            except Exception as e:
                span.set_attribute("success", False)
                span.set_status("error", str(e))
                raise

    def generate_full_question_set(
        self,
        questions_per_type: int = 10,
        provider_tier: Optional[str] = None,
    ) -> Dict[QuestionType, List[GenerationBatch]]:
        """Generate a complete set of questions across all types and difficulties.

        Args:
            questions_per_type: Number of questions to generate per type/difficulty combo
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Dictionary mapping question types to their generation batches

        Raises:
            Exception: If generation fails
        """
        logger.info(
            f"Pipeline: Generating full question set "
            f"({questions_per_type} questions per type/difficulty)"
        )

        results: Dict[QuestionType, List[GenerationBatch]] = {}

        for question_type in QuestionType:
            batches = []

            for difficulty in DifficultyLevel:
                logger.info(f"Generating {question_type.value} - {difficulty.value}")

                try:
                    batch = self.generate_questions(
                        question_type=question_type,
                        difficulty=difficulty,
                        count=questions_per_type,
                        distribute_providers=True,
                        provider_tier=provider_tier,
                    )
                    batches.append(batch)

                except Exception as e:
                    logger.error(
                        f"Failed to generate {question_type.value} - "
                        f"{difficulty.value}: {str(e)}"
                    )
                    # Continue with other types/difficulties
                    continue

            results[question_type] = batches

        # Calculate statistics
        total_questions = sum(
            len(batch.questions) for batches in results.values() for batch in batches
        )
        total_expected = len(QuestionType) * len(DifficultyLevel) * questions_per_type

        logger.info(
            f"Pipeline: Full question set generation complete. "
            f"Generated {total_questions}/{total_expected} questions "
            f"({total_questions/total_expected*100:.1f}% success rate)"
        )

        return results

    def run_generation_job(
        self,
        questions_per_run: Optional[int] = None,
        question_types: Optional[List[QuestionType]] = None,
        difficulty_distribution: Optional[Dict[DifficultyLevel, float]] = None,
        provider_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a complete question generation job.

        This is the main entry point for scheduled question generation runs.

        Args:
            questions_per_run: Total questions to generate (uses settings if None)
            question_types: Specific types to generate (None = all types)
            difficulty_distribution: Distribution of difficulties (None = equal)
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Dictionary with job statistics and results

        Raises:
            Exception: If job fails
        """
        questions_per_run = questions_per_run or settings.questions_per_run

        with observability.start_span(
            "pipeline.run_generation_job",
            attributes={"questions_per_run": questions_per_run},
        ) as span:
            start_time = datetime.now(timezone.utc)

            logger.info(
                f"Starting question generation job: {questions_per_run} questions"
            )

            # Determine which types to generate
            types_to_generate = question_types or list(QuestionType)

            # Default difficulty distribution
            if difficulty_distribution is None:
                difficulty_distribution = {
                    DifficultyLevel.EASY: 0.30,
                    DifficultyLevel.MEDIUM: 0.45,
                    DifficultyLevel.HARD: 0.25,
                }

            # Calculate questions per type
            questions_per_type = questions_per_run // len(types_to_generate)

            all_batches = []
            all_questions = []

            # Generate questions for each type
            for question_type in types_to_generate:
                logger.info(f"Job: Generating questions for {question_type.value}")

                for difficulty, proportion in difficulty_distribution.items():
                    count = max(1, int(questions_per_type * proportion))

                    try:
                        batch = self.generate_questions(
                            question_type=question_type,
                            difficulty=difficulty,
                            count=count,
                            distribute_providers=True,
                            provider_tier=provider_tier,
                        )
                        all_batches.append(batch)
                        all_questions.extend(batch.questions)

                    except Exception as e:
                        logger.error(
                            f"Job: Failed to generate {question_type.value} - "
                            f"{difficulty.value}: {str(e)}"
                        )
                        continue

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Compile statistics
            stats = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "target_questions": questions_per_run,
                "questions_generated": len(all_questions),
                "batches_created": len(all_batches),
                "success_rate": len(all_questions) / questions_per_run
                if questions_per_run > 0
                else 0,
                "providers_used": list(set(q.source_llm for q in all_questions)),
                "questions_by_type": {
                    qt.value: len([q for q in all_questions if q.question_type == qt])
                    for qt in QuestionType
                },
                "questions_by_difficulty": {
                    diff.value: len(
                        [q for q in all_questions if q.difficulty_level == diff]
                    )
                    for diff in DifficultyLevel
                },
            }

            span.set_attribute("success", True)
            span.set_attribute("questions_generated", len(all_questions))
            span.set_attribute("duration_seconds", duration)
            logger.info(
                f"Job complete: Generated {len(all_questions)}/{questions_per_run} "
                f"questions in {duration:.1f}s"
            )

            return {
                "statistics": stats,
                "batches": all_batches,
                "questions": all_questions,
            }

    async def run_generation_job_async(
        self,
        questions_per_run: Optional[int] = None,
        question_types: Optional[List[QuestionType]] = None,
        difficulty_distribution: Optional[Dict[DifficultyLevel, float]] = None,
        provider_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a complete question generation job asynchronously with parallel generation.

        This is the async entry point for scheduled question generation runs.
        All question generation within each batch happens in parallel, and batches
        for different type/difficulty combinations are also generated concurrently.

        Args:
            questions_per_run: Total questions to generate (uses settings if None)
            question_types: Specific types to generate (None = all types)
            difficulty_distribution: Distribution of difficulties (None = equal)
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Dictionary with job statistics and results

        Raises:
            Exception: If job fails
        """
        questions_per_run = questions_per_run or settings.questions_per_run

        with observability.start_span(
            "pipeline.run_generation_job_async",
            attributes={"questions_per_run": questions_per_run},
        ) as span:
            start_time = datetime.now(timezone.utc)

            logger.info(
                f"Starting async question generation job: {questions_per_run} questions"
            )

            # Determine which types to generate
            types_to_generate = question_types or list(QuestionType)

            # Default difficulty distribution
            if difficulty_distribution is None:
                difficulty_distribution = {
                    DifficultyLevel.EASY: 0.30,
                    DifficultyLevel.MEDIUM: 0.45,
                    DifficultyLevel.HARD: 0.25,
                }

            # Calculate questions per type
            questions_per_type = questions_per_run // len(types_to_generate)

            # Create tasks for all type/difficulty combinations
            tasks = []
            task_metadata = []

            for question_type in types_to_generate:
                for difficulty, proportion in difficulty_distribution.items():
                    count = max(1, int(questions_per_type * proportion))
                    task = self.generate_questions_async(
                        question_type=question_type,
                        difficulty=difficulty,
                        count=count,
                        distribute_providers=True,
                        provider_tier=provider_tier,
                    )
                    tasks.append(task)
                    task_metadata.append(
                        {
                            "question_type": question_type,
                            "difficulty": difficulty,
                            "count": count,
                        }
                    )

            logger.info(
                f"Job (async): Executing {len(tasks)} generation tasks in parallel"
            )

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            all_batches: List[GenerationBatch] = []
            all_questions = []

            for i, result in enumerate(results):
                metadata = task_metadata[i]
                if isinstance(result, BaseException):
                    logger.error(
                        f"Job (async): Failed to generate "
                        f"{metadata['question_type'].value} - "
                        f"{metadata['difficulty'].value}: {str(result)}"
                    )
                elif isinstance(result, GenerationBatch):
                    all_batches.append(result)
                    all_questions.extend(result.questions)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Compile statistics
            stats = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "target_questions": questions_per_run,
                "questions_generated": len(all_questions),
                "batches_created": len(all_batches),
                "success_rate": len(all_questions) / questions_per_run
                if questions_per_run > 0
                else 0,
                "providers_used": list(set(q.source_llm for q in all_questions)),
                "questions_by_type": {
                    qt.value: len([q for q in all_questions if q.question_type == qt])
                    for qt in QuestionType
                },
                "questions_by_difficulty": {
                    diff.value: len(
                        [q for q in all_questions if q.difficulty_level == diff]
                    )
                    for diff in DifficultyLevel
                },
                "async": True,
            }

            span.set_attribute("success", True)
            span.set_attribute("questions_generated", len(all_questions))
            span.set_attribute("duration_seconds", duration)
            logger.info(
                f"Job (async) complete: Generated {len(all_questions)}/{questions_per_run} "
                f"questions in {duration:.1f}s"
            )

            return {
                "statistics": stats,
                "batches": all_batches,
                "questions": all_questions,
            }

    def run_balanced_generation_job(
        self,
        stratum_allocations: Dict[Tuple[QuestionType, DifficultyLevel], int],
        provider_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a balanced question generation job with specific allocations per stratum.

        This method generates questions according to pre-computed allocations
        for each (question_type, difficulty) stratum, typically determined by
        inventory analysis.

        Args:
            stratum_allocations: Dictionary mapping (QuestionType, DifficultyLevel)
                tuples to the number of questions to generate for that stratum.
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Dictionary with job statistics and results

        Raises:
            Exception: If job fails
        """
        total_to_generate = sum(stratum_allocations.values())

        with observability.start_span(
            "pipeline.run_balanced_generation_job",
            attributes={"total_to_generate": total_to_generate},
        ) as span:
            start_time = datetime.now(timezone.utc)

            logger.info(
                f"Starting balanced generation job: {total_to_generate} questions "
                f"across {len([v for v in stratum_allocations.values() if v > 0])} strata"
            )

            all_batches = []
            all_questions = []

            for (question_type, difficulty), count in stratum_allocations.items():
                if count <= 0:
                    continue

                logger.info(
                    f"Job: Generating {count} questions for "
                    f"{question_type.value}/{difficulty.value}"
                )

                try:
                    batch = self.generate_questions(
                        question_type=question_type,
                        difficulty=difficulty,
                        count=count,
                        distribute_providers=True,
                        provider_tier=provider_tier,
                    )
                    all_batches.append(batch)
                    all_questions.extend(batch.questions)

                except Exception as e:
                    logger.error(
                        f"Job: Failed to generate {question_type.value} - "
                        f"{difficulty.value}: {str(e)}"
                    )
                    continue

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Compile statistics
            stats = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "target_questions": total_to_generate,
                "questions_generated": len(all_questions),
                "batches_created": len(all_batches),
                "success_rate": len(all_questions) / total_to_generate
                if total_to_generate > 0
                else 0,
                "providers_used": list(set(q.source_llm for q in all_questions)),
                "questions_by_type": {
                    qt.value: len([q for q in all_questions if q.question_type == qt])
                    for qt in QuestionType
                },
                "questions_by_difficulty": {
                    diff.value: len(
                        [q for q in all_questions if q.difficulty_level == diff]
                    )
                    for diff in DifficultyLevel
                },
                "balanced": True,
            }

            span.set_attribute("success", True)
            span.set_attribute("questions_generated", len(all_questions))
            span.set_attribute("duration_seconds", duration)
            logger.info(
                f"Balanced job complete: Generated {len(all_questions)}/{total_to_generate} "
                f"questions in {duration:.1f}s"
            )

            return {
                "statistics": stats,
                "batches": all_batches,
                "questions": all_questions,
            }

    async def run_balanced_generation_job_async(
        self,
        stratum_allocations: Dict[Tuple[QuestionType, DifficultyLevel], int],
        provider_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Run a balanced question generation job asynchronously with parallel generation.

        This method generates questions according to pre-computed allocations
        for each (question_type, difficulty) stratum, with all generations
        running in parallel.

        Args:
            stratum_allocations: Dictionary mapping (QuestionType, DifficultyLevel)
                tuples to the number of questions to generate for that stratum.
            provider_tier: Which tier to use - "primary" or "fallback" (None = "primary")

        Returns:
            Dictionary with job statistics and results

        Raises:
            Exception: If job fails
        """
        total_to_generate = sum(stratum_allocations.values())

        with observability.start_span(
            "pipeline.run_balanced_generation_job_async",
            attributes={"total_to_generate": total_to_generate},
        ) as span:
            start_time = datetime.now(timezone.utc)

            logger.info(
                f"Starting async balanced generation job: {total_to_generate} questions "
                f"across {len([v for v in stratum_allocations.values() if v > 0])} strata"
            )

            # Create tasks for all allocations
            tasks = []
            task_metadata = []

            for (question_type, difficulty), count in stratum_allocations.items():
                if count <= 0:
                    continue

                task = self.generate_questions_async(
                    question_type=question_type,
                    difficulty=difficulty,
                    count=count,
                    distribute_providers=True,
                    provider_tier=provider_tier,
                )
                tasks.append(task)
                task_metadata.append(
                    {
                        "question_type": question_type,
                        "difficulty": difficulty,
                        "count": count,
                    }
                )

            logger.info(
                f"Balanced job (async): Executing {len(tasks)} generation tasks in parallel"
            )

            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            all_batches: List[GenerationBatch] = []
            all_questions = []

            for i, result in enumerate(results):
                metadata = task_metadata[i]
                if isinstance(result, BaseException):
                    logger.error(
                        f"Balanced job (async): Failed to generate "
                        f"{metadata['question_type'].value} - "
                        f"{metadata['difficulty'].value}: {str(result)}"
                    )
                elif isinstance(result, GenerationBatch):
                    all_batches.append(result)
                    all_questions.extend(result.questions)

            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Compile statistics
            stats = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "target_questions": total_to_generate,
                "questions_generated": len(all_questions),
                "batches_created": len(all_batches),
                "success_rate": len(all_questions) / total_to_generate
                if total_to_generate > 0
                else 0,
                "providers_used": list(set(q.source_llm for q in all_questions)),
                "questions_by_type": {
                    qt.value: len([q for q in all_questions if q.question_type == qt])
                    for qt in QuestionType
                },
                "questions_by_difficulty": {
                    diff.value: len(
                        [q for q in all_questions if q.difficulty_level == diff]
                    )
                    for diff in DifficultyLevel
                },
                "async": True,
                "balanced": True,
            }

            span.set_attribute("success", True)
            span.set_attribute("questions_generated", len(all_questions))
            span.set_attribute("duration_seconds", duration)
            logger.info(
                f"Balanced job (async) complete: Generated "
                f"{len(all_questions)}/{total_to_generate} questions in {duration:.1f}s"
            )

            return {
                "statistics": stats,
                "batches": all_batches,
                "questions": all_questions,
            }

    def get_pipeline_info(self) -> Dict[str, Any]:
        """Get information about the pipeline configuration.

        Returns:
            Dictionary with pipeline configuration details
        """
        return {
            "generator_providers": self.generator.get_available_providers(),
            "provider_stats": self.generator.get_provider_stats(),
            "settings": {
                "questions_per_run": settings.questions_per_run,
                "min_judge_score": settings.min_judge_score,
                "judge_config_path": settings.judge_config_path,
            },
        }

    async def cleanup(self) -> None:
        """Clean up all pipeline resources.

        This should be called when the pipeline is no longer needed to ensure
        all async clients are properly closed and resources are released.
        """
        await self.generator.cleanup()

    async def __aenter__(self) -> "QuestionGenerationPipeline":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures cleanup is called."""
        await self.cleanup()


def create_pipeline(
    openai_key: Optional[str] = None,
    anthropic_key: Optional[str] = None,
    google_key: Optional[str] = None,
) -> QuestionGenerationPipeline:
    """Factory function to create a configured pipeline instance.

    Args:
        openai_key: OpenAI API key (optional)
        anthropic_key: Anthropic API key (optional)
        google_key: Google API key (optional)

    Returns:
        Configured QuestionGenerationPipeline instance

    Raises:
        ValueError: If no API keys are provided
    """
    pipeline = QuestionGenerationPipeline(
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
        google_api_key=google_key,
    )

    logger.info("Pipeline created successfully")
    return pipeline
