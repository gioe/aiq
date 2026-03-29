#!/usr/bin/env python3
"""Standalone question generation script.

This script runs the complete question generation pipeline including:
- Question generation across multiple LLM providers
- Judge evaluation of question quality
- Deduplication checking against existing questions
- Database insertion of approved questions
- Metrics tracking and logging

Can be invoked by any scheduler (cron, cloud scheduler, manual).

Exit Codes:
    0 - Success (questions generated and inserted)
    1 - Partial failure (some questions generated, but errors occurred)
    2 - Complete failure (no questions generated)
    3 - Configuration error
    4 - Database connection error
"""

import argparse
import asyncio
import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app import (  # noqa: E402
    QuestionJudge,
    QuestionDatabase,
    QuestionDeduplicator,
    QuestionGenerationPipeline,
    InventoryAnalyzer,
)
from gioe_libs.alerting.alerting import (  # noqa: E402
    AlertManager,
    AlertingConfig,
    ResourceMonitor,
    ResourceStatus,
)
from app.reporting.alerting_adapter import to_run_summary  # noqa: E402
from app.config.config import settings  # noqa: E402
from app.inventory.inventory_config import (  # noqa: E402
    DEFAULT_HEALTHY_THRESHOLD,
    DEFAULT_TARGET_QUESTIONS_PER_STRATUM,
    DEFAULT_WARNING_THRESHOLD,
)
from app.inventory.inventory_analyzer import GenerationPlan  # noqa: E402
from app.infrastructure.circuit_breaker import (  # noqa: E402
    get_circuit_breaker_registry,
)
from app.infrastructure.error_classifier import (  # noqa: E402
    ClassifiedError,
    ErrorCategory,
    ErrorSeverity,
)
from gioe_libs.alerting.alerting import RunSummary  # noqa: E402
from gioe_libs.structured_logging import setup_logging  # noqa: E402
from gioe_libs.cron_runner import CronJob  # noqa: E402
from app.reporting.run_summary import RunSummary as PipelineRunSummary  # noqa: E402
from app.data.models import (  # noqa: E402
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    QuestionType,
)
from app.reporting.reporter import RunReporter  # noqa: E402

# Add repo root to path for libs.observability import
sys.path.insert(0, str(Path(__file__).parent.parent))
from gioe_libs.observability import observability  # noqa: E402

# Exit codes
EXIT_SUCCESS = 0
EXIT_COMPLETE_FAILURE = 2
EXIT_PARTIAL_FAILURE = 3  # Matches reporter.py EXIT_CODE_PARTIAL_FAILURE
EXIT_DATABASE_ERROR = 4
EXIT_BILLING_ERROR = 5  # Critical billing/quota issue
EXIT_AUTH_ERROR = 6  # Authentication failure


class InsertionError(RuntimeError):
    """Raised when database insertion fails after a successful generation run.

    Carries a typed run_summary so callers (e.g. gioe_libs CronJob) can
    report partial metrics without resorting to duck-typing.
    """

    def __init__(self, message: str, run_summary: RunSummary) -> None:
        """Initialize with a message and the run summary captured at failure time."""
        super().__init__(message)
        self.run_summary: RunSummary = run_summary


def log_rejection_details(
    evaluated_question,
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
    if len(question_text) > 80:
        question_text = question_text[:77] + "..."

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
    evaluated_question,
    judge,
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
    from app.data.models import EvaluatedQuestion, GeneratedQuestion

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


def attempt_answer_repair(
    evaluated_question,
    logger: logging.Logger,
) -> Optional[tuple]:
    """Attempt to repair a question with an incorrect answer key.

    Parses judge feedback to find the suggested correct answer and repairs
    the question if possible.

    Args:
        evaluated_question: The EvaluatedQuestion that was rejected
        logger: Logger instance

    Returns:
        Tuple of (repaired_question, repair_reason) if repairable, None otherwise
    """
    import re

    feedback = evaluated_question.evaluation.feedback
    if not feedback:
        return None

    question = evaluated_question.question
    answer_options = question.answer_options

    # Patterns that indicate wrong answer with suggested fix
    patterns = [
        r"answer should be ['\"]?([^'\",.]+)['\"]?",
        r"correct answer should be ['\"]?([^'\",.]+)['\"]?",
        r"actual answer should be ['\"]?([^'\",.]+)['\"]?",
        r"should be ['\"]?([^'\",.]+)['\"]? \(?(?:not|instead)",
        r"the actual answer is ['\"]?([^'\",.]+)['\"]?",
        r"correct answer is ['\"]?([^'\",.]+)['\"]?[^I]",  # Avoid "correct answer is INCORRECT"
        r"proper (?:answer|parallel)[^:]*[:is]+\s*['\"]?([^'\",.]+)['\"]?",
        r"better answer (?:would be|is) ['\"]?([^'\",.]+)['\"]?",
        r"more (?:valid|correct|appropriate) answer[^:]*[:is]+\s*['\"]?([^'\",.]+)['\"]?",
    ]

    suggested_answer = None
    for pattern in patterns:
        match = re.search(pattern, feedback, re.IGNORECASE)
        if match:
            suggested_answer = match.group(1).strip()
            break

    if not suggested_answer:
        return None

    # Check if suggested answer is in options (case-insensitive match)
    matching_option = None
    for option in answer_options:
        if option.lower() == suggested_answer.lower():
            matching_option = option
            break
        # Partial match for cases like "Horoscope" matching "Horoscope"
        if (
            suggested_answer.lower() in option.lower()
            or option.lower() in suggested_answer.lower()
        ):
            matching_option = option
            break

    if not matching_option:
        logger.debug(
            f"Could not find suggested answer '{suggested_answer}' in options: {answer_options}"
        )
        return None

    if matching_option == question.correct_answer:
        # Already correct, nothing to fix
        return None

    # Create repaired question by updating correct_answer
    from app.data.models import GeneratedQuestion

    repaired = GeneratedQuestion(
        question_text=question.question_text,
        question_type=question.question_type,
        difficulty_level=question.difficulty_level,
        correct_answer=matching_option,
        answer_options=question.answer_options,
        explanation=question.explanation,
        stimulus=question.stimulus,
        sub_type=question.sub_type,
        metadata={
            **question.metadata,
            "repaired": True,
            "original_answer": question.correct_answer,
        },
        source_llm=question.source_llm,
        source_model=question.source_model,
    )

    reason = f"Fixed answer from '{question.correct_answer}' to '{matching_option}'"
    return (repaired, reason)


def attempt_difficulty_reclassification(
    evaluated_question,
    logger: logging.Logger,
) -> Optional[tuple]:
    """Attempt to reclassify a question to a more appropriate difficulty.

    If a question was rejected primarily for difficulty mismatch (too easy/hard),
    reclassify it to the appropriate level instead of discarding.

    Args:
        evaluated_question: The EvaluatedQuestion that was rejected
        logger: Logger instance

    Returns:
        Tuple of (reclassified_question, new_difficulty, reason) if reclassifiable, None otherwise
    """
    from app.data.models import DifficultyLevel, GeneratedQuestion

    feedback = evaluated_question.evaluation.feedback
    eval_scores = evaluated_question.evaluation
    question = evaluated_question.question

    if not feedback:
        return None

    # Only reclassify if other scores are acceptable (validity, clarity, formatting >= 0.6)
    if eval_scores.validity_score < 0.6:
        return None
    if eval_scores.clarity_score < 0.6:
        return None
    if eval_scores.formatting_score < 0.6:
        return None

    feedback_lower = feedback.lower()
    current_difficulty = question.difficulty_level

    # Detect "too easy" patterns
    too_easy_patterns = [
        "too easy",
        "easier than",
        "success rate 70",
        "success rate 80",
        "easy range",
        "straightforward",
        "most test-takers will quickly",
    ]

    # Detect "too hard" patterns
    too_hard_patterns = [
        "too hard",
        "too difficult",
        "harder than",
        "success rate 10",
        "success rate 5",
        "hard range",
        "extremely challenging",
    ]

    new_difficulty = None
    reason = None

    # Check if too easy
    if any(pattern in feedback_lower for pattern in too_easy_patterns):
        if current_difficulty == DifficultyLevel.MEDIUM:
            new_difficulty = DifficultyLevel.EASY
            reason = "Reclassified from medium to easy (judge found it too easy)"
        elif current_difficulty == DifficultyLevel.HARD:
            new_difficulty = DifficultyLevel.MEDIUM
            reason = "Reclassified from hard to medium (judge found it too easy)"

    # Check if too hard
    elif any(pattern in feedback_lower for pattern in too_hard_patterns):
        if current_difficulty == DifficultyLevel.EASY:
            new_difficulty = DifficultyLevel.MEDIUM
            reason = "Reclassified from easy to medium (judge found it too hard)"
        elif current_difficulty == DifficultyLevel.MEDIUM:
            new_difficulty = DifficultyLevel.HARD
            reason = "Reclassified from medium to hard (judge found it too hard)"

    if not new_difficulty:
        return None

    # Create reclassified question
    reclassified = GeneratedQuestion(
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
            "reclassified": True,
            "original_difficulty": current_difficulty.value,
        },
        source_llm=question.source_llm,
        source_model=question.source_model,
    )

    return (reclassified, new_difficulty, reason)


async def attempt_regeneration_with_feedback(
    rejected_questions: list,
    generator,
    judge,
    min_score: float,
    logger: logging.Logger,
    max_regenerations: int = 5,
) -> tuple[list, list]:
    """Attempt to regenerate rejected questions using judge feedback.

    This function takes questions that were rejected by the judge and uses
    the feedback to generate improved versions. The regenerated questions
    are then re-evaluated by the judge.

    Args:
        rejected_questions: List of EvaluatedQuestion objects that were rejected
        generator: QuestionGenerator instance
        judge: QuestionJudge instance
        min_score: Minimum score threshold for approval
        logger: Logger instance
        max_regenerations: Maximum number of questions to attempt regenerating

    Returns:
        Tuple of (regenerated_and_approved, still_rejected) lists
    """
    regenerated_approved = []
    still_rejected = []

    # Limit regeneration attempts to avoid excessive API costs
    questions_to_regenerate = rejected_questions[:max_regenerations]
    skipped_count = len(rejected_questions) - len(questions_to_regenerate)

    if skipped_count > 0:
        logger.info(
            f"  Regenerating {len(questions_to_regenerate)} of {len(rejected_questions)} "
            f"rejected questions (skipping {skipped_count} to limit costs)"
        )

    for rejected in questions_to_regenerate:
        original_question = rejected.question
        evaluation = rejected.evaluation

        # Build scores dictionary
        scores = {
            "clarity": evaluation.clarity_score,
            "difficulty": evaluation.difficulty_score,
            "validity": evaluation.validity_score,
            "formatting": evaluation.formatting_score,
            "creativity": evaluation.creativity_score,
        }

        try:
            # Regenerate the question with feedback
            regenerated = await generator.regenerate_question_with_feedback_async(
                original_question=original_question,
                judge_feedback=evaluation.feedback or "No specific feedback provided",
                scores=scores,
            )

            logger.debug(f"  Regenerated: {regenerated.question_text[:60]}...")

            # Re-evaluate the regenerated question
            eval_result = await judge.evaluate_question_async(question=regenerated)

            if eval_result.approved:
                regenerated_approved.append(eval_result)
                logger.info(
                    f"  ✓ REGENERATED (score: {eval_result.evaluation.overall_score:.2f}): "
                    f"{regenerated.question_text[:50]}..."
                )
            else:
                logger.debug(
                    f"  ✗ Regenerated question still rejected "
                    f"(score: {eval_result.evaluation.overall_score:.2f})"
                )
                still_rejected.append(rejected)

        except Exception as e:
            logger.warning(
                f"  Failed to regenerate question: {e}\n"
                f"    Original: {original_question.question_text[:60]}...\n"
                f"    Type: {original_question.question_type.value}, "
                f"Difficulty: {original_question.difficulty_level.value}\n"
                f"    Scores: clarity={scores['clarity']:.2f}, validity={scores['validity']:.2f}, "
                f"creativity={scores['creativity']:.2f}"
            )
            still_rejected.append(rejected)

    # Add any questions that were skipped due to the limit
    still_rejected.extend(rejected_questions[max_regenerations:])

    return regenerated_approved, still_rejected


class _RunIdFilter(logging.Filter):
    """Injects run_id into every log record's extra dict for JSON output."""

    def __init__(self, run_id: str) -> None:
        super().__init__()
        self._run_id = run_id

    def filter(self, record: logging.LogRecord) -> bool:
        existing = getattr(record, "extra", None) or {}
        record.extra = {**existing, "run_id": self._run_id}
        return True


def log_success_run(
    stats: dict,
    inserted_count: int,
    approval_rate: float,
    run_id: Optional[str] = None,
) -> None:
    """Log successful run to a separate success log for monitoring.

    This creates a JSONL file with one entry per successful run,
    making it easy to track historical success metrics. Also logs to stdout
    for Railway visibility.

    Args:
        stats: Run statistics dictionary
        inserted_count: Number of questions inserted
        approval_rate: Approval rate percentage
    """
    success_file = Path("./logs/success_runs.jsonl")
    success_file.parent.mkdir(parents=True, exist_ok=True)

    success_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "questions_generated": stats.get("questions_generated", 0),
        "questions_inserted": inserted_count,
        "duration_seconds": stats.get("duration_seconds", 0),
        "approval_rate": approval_rate,
        "providers_used": stats.get("providers_used", []),
    }

    # Write to file for filesystem monitoring
    with open(success_file, "a") as f:
        f.write(json.dumps(success_entry) + "\n")

    # IMPORTANT: Also log to stdout for Railway/cloud platform visibility
    print(f"SUCCESS_RUN: {json.dumps(success_entry)}", flush=True)


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Run question generation pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default number of questions (from config)
  python run_generation.py

  # Generate 100 questions
  python run_generation.py --count 100

  # Generate only math and logic questions
  python run_generation.py --types math logic

  # Generate only hard questions
  python run_generation.py --difficulties hard

  # Generate only easy and medium math questions
  python run_generation.py --types math --difficulties easy medium

  # Dry run (generate but don't insert to database)
  python run_generation.py --dry-run

  # Verbose logging
  python run_generation.py --verbose

  # Use async parallel generation for faster execution
  python run_generation.py --async

  # Use async parallel judge evaluation for faster execution
  python run_generation.py --async-judge

  # Use both async generation and async judge evaluation
  python run_generation.py --async --async-judge

  # Auto-balance generation based on inventory gaps
  python run_generation.py --auto-balance

  # Auto-balance with custom target per stratum
  python run_generation.py --auto-balance --target-per-stratum 100

  # Test fallback provider configuration
  python run_generation.py --provider-tier fallback
        """,
    )

    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help=f"Number of questions to generate (default: {settings.questions_per_run})",
    )

    parser.add_argument(
        "--types",
        nargs="+",
        choices=[qt.value for qt in QuestionType],
        default=None,
        help="Question types to generate (default: all types)",
    )

    parser.add_argument(
        "--difficulties",
        nargs="+",
        choices=[dl.value for dl in DifficultyLevel],
        default=None,
        help="Difficulty levels to generate (default: all levels)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate and evaluate questions but don't insert to database",
    )

    parser.add_argument(
        "--skip-deduplication",
        action="store_true",
        help="Skip deduplication check (use with caution)",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help=f"Minimum judge score for approval (default: {settings.min_judge_score})",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help=f"Log file path (default: {settings.log_file})",
    )

    parser.add_argument(
        "--no-console",
        action="store_true",
        help="Disable console logging (only log to file)",
    )

    parser.add_argument(
        "--triggered-by",
        type=str,
        default="manual",
        choices=["scheduler", "manual", "webhook"],
        help="Source that triggered this run (default: manual)",
    )

    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async parallel generation for improved performance",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=10,
        help="Maximum concurrent requests when using async mode (default: 10)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Timeout in seconds for async API calls (default: 60)",
    )

    parser.add_argument(
        "--async-judge",
        dest="use_async_judge",
        action="store_true",
        help="Use async parallel judge evaluation for improved performance",
    )

    parser.add_argument(
        "--max-concurrent-judge",
        type=int,
        default=10,
        help="Maximum concurrent judge requests when using async mode (default: 10)",
    )

    parser.add_argument(
        "--judge-timeout",
        type=int,
        default=60,
        help="Timeout in seconds for async judge API calls (default: 60)",
    )

    parser.add_argument(
        "--auto-balance",
        action="store_true",
        help="Automatically balance generation based on inventory gaps. "
        "Prioritizes strata with fewer questions to maintain even coverage.",
    )

    parser.add_argument(
        "--target-per-stratum",
        type=int,
        default=DEFAULT_TARGET_QUESTIONS_PER_STRATUM,
        help="Target number of questions per stratum when using --auto-balance "
        f"(default: {DEFAULT_TARGET_QUESTIONS_PER_STRATUM})",
    )

    parser.add_argument(
        "--healthy-threshold",
        type=int,
        default=DEFAULT_HEALTHY_THRESHOLD,
        help=f"Minimum count for healthy inventory status "
        f"(default: {DEFAULT_HEALTHY_THRESHOLD})",
    )

    parser.add_argument(
        "--warning-threshold",
        type=int,
        default=DEFAULT_WARNING_THRESHOLD,
        help=f"Minimum count for warning inventory status "
        f"(default: {DEFAULT_WARNING_THRESHOLD})",
    )

    parser.add_argument(
        "--alerting-config",
        type=str,
        default="./config/alerting.yaml",
        help="Path to alerting configuration file (default: ./config/alerting.yaml)",
    )

    parser.add_argument(
        "--skip-inventory-alerts",
        action="store_true",
        help="Skip inventory alerting even when using --auto-balance",
    )

    parser.add_argument(
        "--provider-tier",
        type=str,
        choices=["primary", "fallback"],
        default="primary",
        help="Provider tier to use for question generation. "
        "'primary' uses the primary provider from generators.yaml (default). "
        "'fallback' forces use of fallback provider to test fallback configuration.",
    )

    return parser.parse_args()


def create_run_reporter(
    logger: Optional[logging.Logger] = None,
) -> Optional[RunReporter]:
    """Create a RunReporter instance if reporting is enabled and configured.

    Args:
        logger: Logger instance for output

    Returns:
        RunReporter instance if enabled and configured, None otherwise
    """
    if not settings.enable_run_reporting:
        if logger:
            logger.info("Run reporting is disabled")
        return None

    if not settings.backend_api_url:
        if logger:
            logger.warning(
                "Run reporting enabled but BACKEND_API_URL not configured - skipping"
            )
        return None

    if not settings.backend_service_key:
        if logger:
            logger.warning(
                "Run reporting enabled but BACKEND_SERVICE_KEY not configured - skipping"
            )
        return None

    reporter = RunReporter(
        backend_url=settings.backend_api_url,
        service_key=settings.backend_service_key,
    )
    if logger:
        logger.info(f"Run reporter initialized (backend: {settings.backend_api_url})")
    return reporter


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


def send_phase_alert(
    alert_manager: AlertManager,
    category: ErrorCategory,
    severity: ErrorSeverity,
    provider: str,
    original_error: str,
    message: str,
    context: str,
    is_retryable: bool = True,
) -> None:
    """Construct a ClassifiedError and send it via alert_manager."""
    error = ClassifiedError(
        category=category,
        severity=severity,
        provider=provider,
        original_error=original_error,
        message=message,
        is_retryable=is_retryable,
    )
    alert_manager.send_alert(error, context=context)


def _build_run_stats(
    stats: dict,
    inserted_count: int,
    approval_rate: float,
    summary: dict,
) -> dict:
    """Build the run statistics dictionary for reporting."""
    requested = stats.get("target_questions", 0)
    generated = stats.get("questions_generated", 0)
    loss = requested - generated
    return {
        "questions_generated": generated,
        "questions_inserted": inserted_count,
        "approval_rate": approval_rate,
        "duration_seconds": stats.get("duration_seconds", 0),
        "by_type": summary.get("database", {}).get("inserted_by_type", {}),
        "by_difficulty": summary.get("generation", {}).get("by_difficulty", {}),
        "questions_requested": requested,
        "generation_loss": loss,
        "generation_loss_pct": (
            round(loss / requested * 100, 1) if requested > 0 else 0.0
        ),
        "questions_rejected": summary.get("evaluation", {}).get("rejected", 0),
        "duplicates_found": summary.get("deduplication", {}).get("duplicates_found", 0),
    }


def _init_components(
    args: argparse.Namespace,
    alert_manager: AlertManager,
    run_id: str,
    logger: logging.Logger,
) -> tuple[
    QuestionGenerationPipeline,
    QuestionJudge,
    Optional[QuestionDatabase],
    Optional[QuestionDeduplicator],
]:
    """Initialize all pipeline components.

    Returns (pipeline, judge, db, deduplicator). Raises RuntimeError on
    configuration or database errors and sends appropriate alerts.
    """
    if not any(
        [
            settings.openai_api_key,
            settings.anthropic_api_key,
            settings.google_api_key,
            settings.xai_api_key,
        ]
    ):
        logger.error("No LLM API keys configured!")
        logger.error(
            "Set OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, or XAI_API_KEY"
        )
        send_phase_alert(
            alert_manager=alert_manager,
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.CRITICAL,
            provider="system",
            original_error="ConfigurationError",
            message="No LLM API keys configured. Question generation cannot run.",
            context=(
                f"[run_id={run_id}] Question generation script failed to start due to missing API keys. "
                "Check environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY"
            ),
            is_retryable=False,
        )
        raise RuntimeError("No LLM API keys configured")

    pipeline = QuestionGenerationPipeline(
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        xai_api_key=settings.xai_api_key,
    )
    logger.info("✓ Pipeline initialized")

    from app.config.judge_config import JudgeConfigLoader  # noqa: PLC0415

    judge_loader = JudgeConfigLoader(settings.judge_config_path)
    judge_loader.load()
    logger.info(f"✓ Judge config loaded from {settings.judge_config_path}")

    from app.config.generator_config import initialize_generator_config  # noqa: PLC0415

    try:
        initialize_generator_config(settings.generator_config_path)
        logger.info(f"✓ Generator config loaded from {settings.generator_config_path}")
    except FileNotFoundError:
        logger.warning(
            f"Generator config not found at {settings.generator_config_path}. "
            "Using round-robin distribution instead of specialist routing."
        )

    judge = QuestionJudge(
        judge_config=judge_loader,
        openai_api_key=settings.openai_api_key,
        anthropic_api_key=settings.anthropic_api_key,
        google_api_key=settings.google_api_key,
        xai_api_key=settings.xai_api_key,
        max_concurrent_evaluations=args.max_concurrent_judge,
        async_timeout_seconds=args.judge_timeout,
    )
    logger.info("✓ Judge initialized")

    db = None
    deduplicator = None

    if not args.dry_run:
        try:
            db = QuestionDatabase(
                database_url=settings.database_url,
                openai_api_key=settings.openai_api_key,
                google_api_key=settings.google_api_key,
            )
            logger.info("✓ Database connected")

            if not settings.openai_api_key:
                logger.error("OpenAI API key required for deduplication")
                raise RuntimeError("OpenAI API key required for deduplication")

            deduplicator = QuestionDeduplicator(
                openai_api_key=settings.openai_api_key,
                similarity_threshold=settings.dedup_similarity_threshold,
                embedding_model=settings.dedup_embedding_model,
                redis_url=settings.redis_url,
                embedding_cache_ttl=settings.embedding_cache_ttl,
                google_api_key=settings.google_api_key,
            )
            cache_type = "Redis" if deduplicator.using_redis_cache else "in-memory"
            logger.info(f"✓ Deduplicator initialized (cache: {cache_type})")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            observability.capture_error(
                e, context={"phase": "init", "step": "database_connection"}
            )
            send_phase_alert(
                alert_manager=alert_manager,
                category=ErrorCategory.SERVER_ERROR,
                severity=ErrorSeverity.CRITICAL,
                provider="database",
                original_error=type(e).__name__,
                message=f"Database connection failed: {str(e)}",
                context=(
                    f"[run_id={run_id}] Question generation cannot connect to database. "
                    f"Check DATABASE_URL and database availability. Error: {str(e)}"
                ),
                is_retryable=False,
            )
            raise RuntimeError(f"Database connection failed: {str(e)}") from e

    return pipeline, judge, db, deduplicator


def run_inventory_analysis(
    db: Optional[QuestionDatabase],
    healthy_threshold: int,
    warning_threshold: int,
    target_per_stratum: int,
    target_count: int,
    alerting_config_path: str,
    skip_inventory_alerts: bool,
    alert_manager: AlertManager,
    logger: logging.Logger,
):
    """Phase 0: Analyze inventory and compute a balanced generation plan.

    Returns the generation plan, or None if all strata are at target (early exit).
    Raises RuntimeError if auto-balance is requested without a database connection.
    """
    if not db:
        logger.error("Auto-balance requires database connection (cannot use --dry-run)")
        raise RuntimeError("Auto-balance requires database connection")

    analyzer = InventoryAnalyzer(
        database_service=db,
        healthy_threshold=healthy_threshold,
        warning_threshold=warning_threshold,
        target_per_stratum=target_per_stratum,
    )

    analysis = analyzer.analyze_inventory()
    analyzer.log_inventory_summary(analysis)

    generation_plan = analyzer.compute_generation_plan(
        target_total=target_count,
        analysis=analysis,
    )
    logger.info("\n" + generation_plan.to_log_summary())

    if not skip_inventory_alerts:
        logger.info("\nChecking inventory levels for alerting...")
        alerting_config = AlertingConfig.from_yaml(alerting_config_path)
        strata_snapshot = analysis.strata

        def inventory_check_fn() -> list:
            return [
                ResourceStatus(
                    name=f"{s.question_type.value}/{s.difficulty.value}",
                    count=s.current_count,
                )
                for s in strata_snapshot
            ]

        resource_monitor = ResourceMonitor(
            check_fn=inventory_check_fn,
            alert_manager=alert_manager,
            config=alerting_config,
        )
        alert_result = resource_monitor.check_and_alert()

        if alert_result.alerts_sent > 0:
            logger.warning(
                f"Inventory alerts sent: {alert_result.alerts_sent} strata below threshold"
            )
        if alert_result.critical_resources:
            logger.warning(
                f"CRITICAL: {len(alert_result.critical_resources)} strata have "
                f"critically low inventory (< {alerting_config.critical_min})"
            )
        if alert_result.warning_resources:
            logger.info(
                f"WARNING: {len(alert_result.warning_resources)} strata have "
                f"low inventory (< {alerting_config.warning_min})"
            )
    else:
        logger.info("Inventory alerting skipped (--skip-inventory-alerts)")

    if generation_plan.total_questions == 0:
        logger.info("Auto-balance early exit: all strata at or above target")
        logger.info(
            f"  Thresholds: healthy={healthy_threshold}, "
            f"warning={warning_threshold}, "
            f"target_per_stratum={target_per_stratum}"
        )
        logger.info(
            f"  Analyzed {len(analysis.strata)} strata, "
            f"{analysis.total_questions} total active questions"
        )
        logger.info(
            f"  Below target: {len(analysis.strata_below_target)}, "
            f"Critical: {len(analysis.critical_strata)}"
        )
        return None

    return generation_plan


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
) -> tuple[list[GeneratedQuestion], dict]:
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
            if evaluated_question.evaluation.overall_score >= min_score:
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


def run_salvage_phase(
    rejected_questions: list,
    approved_questions: list,
    generated_questions: list,
    pipeline: QuestionGenerationPipeline,
    judge: QuestionJudge,
    min_score: float,
    logger: logging.Logger,
) -> tuple[list[EvaluatedQuestion], float]:
    """Salvage phase: attempt to repair, reclassify, or regenerate rejected questions.

    Returns (updated_approved_questions, updated_approval_rate).
    """
    salvaged_questions = []
    still_rejected = []

    for rejected in rejected_questions:
        repair_result = attempt_answer_repair(rejected, logger)
        if repair_result:
            repaired_question, reason = repair_result
            salvaged_questions.append(repaired_question)
            logger.info(f"  ✓ REPAIRED: {reason}")
            logger.info(f"    Question: {repaired_question.question_text[:60]}...")
            continue

        reclass_result = attempt_difficulty_reclassification(rejected, logger)
        if reclass_result:
            reclassified_question, new_difficulty, reason = reclass_result
            salvaged_questions.append(reclassified_question)
            logger.info(f"  ✓ RECLASSIFIED: {reason}")
            logger.info(f"    Question: {reclassified_question.question_text[:60]}...")
            continue

        still_rejected.append(rejected)

    regenerated_count = 0
    if still_rejected:
        logger.info(
            f"\n  Attempting regeneration with feedback for {len(still_rejected)} "
            "remaining rejected questions..."
        )

        async def run_regeneration():
            return await attempt_regeneration_with_feedback(
                rejected_questions=still_rejected,
                generator=pipeline.generator,
                judge=judge,
                min_score=min_score,
                logger=logger,
                max_regenerations=min(len(still_rejected), 5),
            )

        try:
            regenerated, final_rejected = asyncio.run(run_regeneration())
            for regen_eval in regenerated:
                approved_questions.append(regen_eval)
            regenerated_count = len(regenerated)
            still_rejected = final_rejected
            logger.info(
                f"  Regeneration complete: {regenerated_count} recovered, "
                f"{len(final_rejected)} still rejected"
            )
        except Exception as e:
            logger.warning(f"  Regeneration phase failed: {e}")

    total_salvaged = len(salvaged_questions) + regenerated_count
    new_approved = list(approved_questions)
    if total_salvaged > 0:
        logger.info(
            f"\nSalvaged: {total_salvaged} questions "
            f"(repaired/reclassified: {len(salvaged_questions)}, "
            f"regenerated: {regenerated_count}, "
            f"still rejected: {len(still_rejected)})"
        )
        for sq in salvaged_questions:
            salvaged_eval = EvaluatedQuestion(
                question=sq,
                evaluation=EvaluationScore(
                    clarity_score=0.8,
                    difficulty_score=0.8,
                    validity_score=0.8,
                    formatting_score=0.8,
                    creativity_score=0.6,
                    overall_score=0.75,
                    feedback="Salvaged question (repaired or reclassified)",
                ),
                judge_model="salvage",
                approved=True,
            )
            new_approved.append(salvaged_eval)

    approval_rate = (
        len(new_approved) / len(generated_questions) * 100
        if generated_questions
        else 0.0
    )
    logger.info(
        f"Updated approval: {len(new_approved)}/{len(generated_questions)} "
        f"({approval_rate:.1f}%)"
    )
    if total_salvaged == 0:
        logger.info("No questions could be salvaged")

    return new_approved, approval_rate


def run_dedup_phase(
    approved_questions: list,
    db: Optional[QuestionDatabase],
    deduplicator: Optional[QuestionDeduplicator],
    metrics: PipelineRunSummary,
    logger: logging.Logger,
) -> list[EvaluatedQuestion]:
    """Phase 3: Deduplicate approved questions against the database.

    Returns list of unique questions.
    """
    dedup_start = time.perf_counter()
    with observability.start_span(
        "phase3_deduplication",
        attributes={"approved_count": len(approved_questions)},
    ) as dedup_span:
        try:
            assert db is not None
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
                assert deduplicator is not None
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

        assert deduplicator is not None
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


def run_insertion_phase(
    unique_questions: list,
    db: Optional[QuestionDatabase],
    metrics: PipelineRunSummary,
    logger: logging.Logger,
) -> int:
    """Phase 4: Insert unique questions to the database.

    Returns number of successfully inserted questions.
    """
    inserted_count = 0
    storage_start = time.perf_counter()

    with observability.start_span(
        "phase4_db_insertion",
        attributes={"questions_to_insert": len(unique_questions)},
    ) as insert_span:
        for i, evaluated_question in enumerate(unique_questions, 1):
            try:
                assert db is not None
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


def main() -> int:
    """Main entry point for question generation script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    args = parse_arguments()

    # Initialize observability before any code that could raise exceptions
    observability.init(
        config_path="config/observability.yaml",
        service_name="aiq-question-service",
        environment=settings.env,
    )

    # Build alert manager (needed by CronJob and circuit breaker callback)
    alert_manager = AlertManager(
        alert_file_path=settings.alert_file_path,
        discord_webhook_url=settings.discord_webhook_url,
    )

    # Register circuit breaker callback so Discord alerts fire on CLOSED → OPEN transitions.
    get_circuit_breaker_registry().set_on_open_callback(
        alert_manager.send_circuit_breaker_alert
    )

    # NOTE: _work() captures alert_manager from main() scope. This is intentional
    # for run_once(): one AlertManager is created, registered with the circuit breaker
    # registry, and used throughout the single run. If run_loop() were ever adopted,
    # reconstruct alert_manager (and re-register the callback) inside _work() instead.
    def _work() -> dict:
        """Run the generation pipeline once; called by CronJob.run_once()."""
        log_level = "DEBUG" if args.verbose else settings.log_level
        log_file = args.log_file or settings.log_file
        setup_logging(
            log_level=log_level,
            log_file=log_file,
            enable_file_logging=not args.no_console,
        )

        run_id = (
            f"run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
            f"-{uuid.uuid4().hex[:6]}"
        )
        _run_id_filter = _RunIdFilter(run_id)
        logging.getLogger().addFilter(_run_id_filter)
        logger = logging.getLogger(__name__)

        logger.info("=" * 80)
        logger.info(f"Question Generation Script Starting  run_id={run_id}")
        logger.info(
            f"Observability initialized: service=aiq-question-service, env={settings.env}"
        )
        logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
        logger.info(
            f"Configuration: count={args.count or settings.questions_per_run}, "
            f"types={args.types or 'all'}, difficulties={args.difficulties or 'all'}"
        )
        logger.info(f"Provider tier: {args.provider_tier}")
        logger.info(f"Dry run: {args.dry_run}")
        logger.info("=" * 80)

        inserted_count = 0
        approval_rate = 0.0
        stats: dict = {}
        db = None
        run_reporter = None
        summary: dict = {}

        try:
            metrics = PipelineRunSummary()
            metrics.start_run()

            logger.info(
                f"Alert manager initialized (discord={'enabled' if settings.discord_webhook_url else 'disabled'})"
            )

            run_reporter = create_run_reporter(logger)

            question_types = None
            if args.types:
                question_types = [QuestionType(qt) for qt in args.types]
                logger.info(
                    f"Generating only types: {[qt.value for qt in question_types]}"
                )

            difficulty_distribution = None
            if args.difficulties:
                difficulties = [DifficultyLevel(d) for d in args.difficulties]
                weight = 1.0 / len(difficulties)
                difficulty_distribution = {d: weight for d in difficulties}
                logger.info(
                    f"Generating only difficulties: {[d.value for d in difficulties]}"
                )

            logger.info("Initializing pipeline components...")
            pipeline, judge, db, deduplicator = _init_components(
                args, alert_manager, run_id, logger
            )

            # Phase 0: Inventory Analysis
            generation_plan = None
            if args.auto_balance:
                logger.info("\n" + "=" * 80)
                logger.info("PHASE 0: Inventory Analysis (Auto-Balance)")
                logger.info("=" * 80)
                generation_plan = run_inventory_analysis(
                    db=db,
                    healthy_threshold=args.healthy_threshold,
                    warning_threshold=args.warning_threshold,
                    target_per_stratum=args.target_per_stratum,
                    target_count=args.count or settings.questions_per_run,
                    alerting_config_path=args.alerting_config,
                    skip_inventory_alerts=args.skip_inventory_alerts,
                    alert_manager=alert_manager,
                    logger=logger,
                )
                if generation_plan is None:
                    return to_run_summary(
                        {"questions_generated": 0, "reason": "inventory_balanced"}
                    )

            # Phase 1: Question Generation
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 1: Question Generation")
            logger.info("=" * 80)
            generated_questions, stats = run_generation_phase(
                pipeline=pipeline,
                generation_plan=generation_plan,
                question_types=question_types,
                difficulty_distribution=difficulty_distribution,
                use_async=args.use_async,
                max_concurrent=args.max_concurrent,
                timeout=args.timeout,
                provider_tier=args.provider_tier,
                count=args.count,
                metrics=metrics,
                logger=logger,
            )

            if not generated_questions:
                logger.error("No questions generated!")
                send_phase_alert(
                    alert_manager=alert_manager,
                    category=ErrorCategory.UNKNOWN,
                    severity=ErrorSeverity.CRITICAL,
                    provider="pipeline",
                    original_error="GenerationFailure",
                    message="Question generation produced zero questions. All generation attempts failed.",
                    context=(
                        f"[run_id={run_id}] Question generation job completed but produced no questions. "
                        f"Target: {stats['target_questions']}, Generated: 0. "
                        "Check logs for LLM API errors."
                    ),
                    is_retryable=True,
                )
                raise RuntimeError("No questions generated")

            # Phase 2: Judge Evaluation
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 2: Judge Evaluation")
            logger.info("=" * 80)
            min_score = args.min_score or settings.min_judge_score
            logger.info(f"Minimum approval score: {min_score}")

            approved_questions, rejected_questions, approval_rate = run_judge_phase(
                generated_questions=generated_questions,
                judge=judge,
                min_score=min_score,
                use_async_judge=args.use_async_judge,
                metrics=metrics,
                logger=logger,
            )

            # Salvage Phase
            if rejected_questions:
                logger.info("\n" + "-" * 40)
                logger.info("SALVAGE PHASE: Attempting to recover rejected questions")
                logger.info("-" * 40)
                approved_questions, approval_rate = run_salvage_phase(
                    rejected_questions=rejected_questions,
                    approved_questions=approved_questions,
                    generated_questions=generated_questions,
                    pipeline=pipeline,
                    judge=judge,
                    min_score=min_score,
                    logger=logger,
                )

            if not approved_questions:
                logger.warning("No questions passed judge evaluation!")
                send_phase_alert(
                    alert_manager=alert_manager,
                    category=ErrorCategory.INVALID_REQUEST,
                    severity=ErrorSeverity.HIGH,
                    provider="judge",
                    original_error="JudgeRejectionFailure",
                    message=f"All {len(generated_questions)} generated questions were rejected by judge evaluation.",
                    context=(
                        f"[run_id={run_id}] Question generation produced {len(generated_questions)} questions "
                        f"but judge rejected all of them. Minimum score threshold: {min_score}. "
                        "Consider reviewing judge configuration or lowering MIN_JUDGE_SCORE."
                    ),
                    is_retryable=True,
                )
                raise RuntimeError("No questions passed judge evaluation")

            # Phase 3: Deduplication
            unique_questions = approved_questions
            if not args.skip_deduplication and not args.dry_run:
                logger.info("\n" + "=" * 80)
                logger.info("PHASE 3: Deduplication")
                logger.info("=" * 80)
                unique_questions = run_dedup_phase(
                    approved_questions=approved_questions,
                    db=db,
                    deduplicator=deduplicator,
                    metrics=metrics,
                    logger=logger,
                )

            # Phase 4: Database Insertion
            inserted_count = 0
            if not args.dry_run and unique_questions:
                logger.info("\n" + "=" * 80)
                logger.info("PHASE 4: Database Insertion")
                logger.info("=" * 80)
                inserted_count = run_insertion_phase(
                    unique_questions=unique_questions,
                    db=db,
                    metrics=metrics,
                    logger=logger,
                )

            # Final Summary
            metrics.end_run()
            summary = metrics.to_summary_dict()

            logger.info("\n" + "=" * 80)
            logger.info("FINAL SUMMARY")
            logger.info("=" * 80)
            logger.info(
                f"Total duration: {summary['execution']['duration_seconds']:.1f}s"
            )
            logger.info(f"Generated: {stats['questions_generated']}")
            logger.info(f"Approved by judge: {len(approved_questions)}")
            logger.info(f"Unique: {len(unique_questions)}")
            logger.info(f"Inserted to database: {inserted_count}")
            logger.info(f"Approval rate: {approval_rate:.1f}%")

            if args.dry_run:
                logger.info("\n[DRY RUN] No questions were inserted to database")

            _run_stats = _build_run_stats(stats, inserted_count, approval_rate, summary)

            if not args.dry_run:
                if inserted_count == 0:
                    logger.error("No questions were inserted to database!")
                    send_phase_alert(
                        alert_manager=alert_manager,
                        category=ErrorCategory.SERVER_ERROR,
                        severity=ErrorSeverity.CRITICAL,
                        provider="database",
                        original_error="InsertionFailure",
                        message=f"Database insertion failed for all {len(unique_questions)} unique questions.",
                        context=(
                            f"[run_id={run_id}] Question generation completed successfully through judge evaluation, "
                            f"but all {len(unique_questions)} questions failed to insert to database. "
                            "Check database connection and logs."
                        ),
                        is_retryable=True,
                    )
                    raise InsertionError(
                        f"Database insertion failed: 0 of {len(unique_questions)} questions inserted",
                        run_summary=to_run_summary(_run_stats),
                    )
                elif inserted_count < len(unique_questions):
                    logger.warning("Some questions failed to insert")
                    raise InsertionError(
                        f"Partial insertion failure: {inserted_count} of {len(unique_questions)} questions inserted",
                        run_summary=to_run_summary(_run_stats),
                    )
                else:
                    logger.info("✓ All unique questions inserted successfully")

            if inserted_count > 0:
                log_success_run(
                    stats=stats,
                    inserted_count=inserted_count,
                    approval_rate=approval_rate,
                    run_id=run_id,
                )
                logger.info("Success metrics logged to logs/success_runs.jsonl")

            if run_reporter:
                min_score = args.min_score or settings.min_judge_score
                backend_run_id = run_reporter.report_run(
                    summary=summary,
                    exit_code=EXIT_SUCCESS,
                    environment=settings.env,
                    triggered_by=args.triggered_by,
                    prompt_version=settings.prompt_version,
                    judge_config_version=settings.judge_config_version,
                    min_judge_score_threshold=min_score,
                    client_run_id=run_id,
                )
                if backend_run_id:
                    logger.info(f"Run reported to backend API (ID: {backend_run_id})")
                else:
                    logger.warning("Failed to report run to backend API")

            # Post-run answer-leakage audit (always runs; respects args.dry_run for writes)
            if db is not None:
                try:
                    from app.data.answer_leakage_auditor import (
                        run_answer_leakage_audit,
                    )  # noqa: PLC0415

                    run_answer_leakage_audit(db.SessionLocal, dry_run=args.dry_run)
                except Exception as audit_err:
                    logger.warning(
                        "[answer-leakage-audit] Audit skipped due to error: %s",
                        audit_err,
                        exc_info=True,
                    )

            logger.info("=" * 80)
            logger.info("Script completed successfully")
            logger.info("=" * 80)

            run_summary = to_run_summary(
                _run_stats,
                loss_threshold=(
                    None if args.dry_run else settings.generation_loss_threshold_pct
                ),
            )

            logger.info(
                "RUN_COMPLETE run_id=%s exit_code=0 questions_requested=%d questions_generated=%d "
                "generation_loss=%d generation_loss_pct=%.1f questions_inserted=%d "
                "approval_rate=%.1f duration_seconds=%.1f",
                run_id,
                _run_stats["questions_requested"],
                _run_stats["questions_generated"],
                _run_stats["generation_loss"],
                _run_stats["generation_loss_pct"],
                inserted_count,
                approval_rate,
                stats.get("duration_seconds", 0.0),
            )

            if (
                not args.dry_run
                and _run_stats["generation_loss_pct"]
                > settings.generation_loss_threshold_pct
            ):
                logger.warning(
                    "GENERATION_LOSS_ALERT generation_loss_pct=%.1f exceeds threshold=%.1f "
                    "requested=%d generated=%d",
                    _run_stats["generation_loss_pct"],
                    settings.generation_loss_threshold_pct,
                    _run_stats["questions_requested"],
                    _run_stats["questions_generated"],
                )

            return run_summary

        except Exception as exc:
            # Report failed and partial_failure runs to the backend API so every
            # run — successful or not — appears in /v1/admin/generation-runs.
            if run_reporter:
                if isinstance(exc, InsertionError) and inserted_count > 0:
                    failure_exit_code = EXIT_PARTIAL_FAILURE
                else:
                    failure_exit_code = EXIT_COMPLETE_FAILURE
                min_score = args.min_score or settings.min_judge_score
                backend_run_id = run_reporter.report_run(
                    summary=summary,
                    exit_code=failure_exit_code,
                    environment=settings.env,
                    triggered_by=args.triggered_by,
                    prompt_version=settings.prompt_version,
                    judge_config_version=settings.judge_config_version,
                    min_judge_score_threshold=min_score,
                    client_run_id=run_id,
                )
                if backend_run_id:
                    logger.info(
                        f"Failed run reported to backend API (ID: {backend_run_id})"
                    )
                else:
                    logger.warning("Failed to report failed run to backend API")
            raise

        finally:
            # Remove run_id filter so it does not persist across runs
            logging.getLogger().removeFilter(_run_id_filter)
            # Always close the database connection, even if an exception is raised
            if db is not None:
                try:
                    db.close()
                    logger.info("Database connection closed")
                except Exception:
                    pass

    job = CronJob(
        name="question-generation",
        schedule="0 * * * *",
        work_fn=_work,
        observability=observability,
        alert_manager=alert_manager,
        heartbeat_path="./logs/heartbeat.json",
    )

    try:
        return job.run_once()
    finally:
        # Shutdown observability backends
        # Skip flush — metrics export on the periodic cycle to avoid
        # Grafana Cloud free tier rate limits (err-mimir-tenant-max-request-rate)
        try:
            observability.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
