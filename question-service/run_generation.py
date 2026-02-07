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
import os
import sys
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
from app.alerting import (  # noqa: E402
    AlertManager,
    AlertingConfig,
    InventoryAlertManager,
)
from app.config import settings  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.metrics import MetricsTracker  # noqa: E402
from app.models import DifficultyLevel, QuestionType  # noqa: E402
from app.reporter import RunReporter  # noqa: E402

# Add repo root to path for libs.observability import
sys.path.insert(0, str(Path(__file__).parent.parent))
from libs.observability import observability  # noqa: E402

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_COMPLETE_FAILURE = 2
EXIT_CONFIG_ERROR = 3
EXIT_DATABASE_ERROR = 4
EXIT_BILLING_ERROR = 5  # New: Critical billing/quota issue
EXIT_AUTH_ERROR = 6  # New: Authentication failure


def write_heartbeat(
    status: str,
    exit_code: Optional[int] = None,
    error_message: Optional[str] = None,
    stats: Optional[dict] = None,
) -> None:
    """Write heartbeat to track cron execution and health.

    This creates a simple file that monitoring systems can check to verify
    the cron is running on schedule. Also logs to stdout for Railway visibility.

    Args:
        status: Current status ("started", "completed", "failed")
        exit_code: Script exit code (if completed)
        error_message: Error message (if failed)
        stats: Run statistics (if completed successfully)
    """
    heartbeat_file = Path("./logs/heartbeat.json")
    heartbeat_file.parent.mkdir(parents=True, exist_ok=True)

    from typing import Any, Dict

    data: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "hostname": os.uname().nodename if hasattr(os, "uname") else "unknown",
    }

    if exit_code is not None:
        data["exit_code"] = exit_code

    if error_message:
        data["error_message"] = error_message

    if stats:
        data["stats"] = stats

    # Write to file for filesystem monitoring
    with open(heartbeat_file, "w") as f:
        json.dump(data, f, indent=2)

    # IMPORTANT: Also log to stdout for Railway/cloud platform visibility
    # This ensures the heartbeat is captured in Railway logs
    print(f"HEARTBEAT: {json.dumps(data)}", flush=True)


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
    from app.models import EvaluatedQuestion, GeneratedQuestion

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
    from app.models import GeneratedQuestion

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
    from app.models import DifficultyLevel, GeneratedQuestion

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


def log_success_run(
    stats: dict,
    inserted_count: int,
    approval_rate: float,
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
        default=50,
        help="Target number of questions per stratum when using --auto-balance (default: 50)",
    )

    parser.add_argument(
        "--healthy-threshold",
        type=int,
        default=50,
        help="Minimum count for healthy inventory status (default: 50)",
    )

    parser.add_argument(
        "--warning-threshold",
        type=int,
        default=20,
        help="Minimum count for warning inventory status (default: 20)",
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


def main() -> int:
    """Main entry point for question generation script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Write initial heartbeat BEFORE anything else
    # This proves the cron triggered, even if it fails immediately
    write_heartbeat(status="started")

    # Initialize observability (Sentry + OTEL via unified facade)
    # Must happen before any code that could raise exceptions we want to capture
    observability.init(
        config_path="config/observability.yaml",
        service_name="aiq-question-service",
        environment=settings.env,
    )

    args = parse_arguments()

    # Setup logging
    log_level = "DEBUG" if args.verbose else settings.log_level
    log_file = args.log_file or settings.log_file

    setup_logging(
        log_level=log_level,
        log_file=log_file,
        enable_file_logging=not args.no_console,
    )

    # Get logger after setup
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("Question Generation Script Starting")
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

    try:
        # Initialize metrics
        metrics = MetricsTracker()
        metrics.start_run()

        # Initialize alert manager
        to_emails = []
        if settings.alert_to_emails:
            to_emails = [email.strip() for email in settings.alert_to_emails.split(",")]

        alert_manager = AlertManager(
            email_enabled=settings.enable_email_alerts,
            smtp_host=settings.smtp_host,
            smtp_port=settings.smtp_port,
            smtp_username=settings.smtp_username,
            smtp_password=settings.smtp_password,
            from_email=settings.alert_from_email,
            to_emails=to_emails,
            alert_file_path=settings.alert_file_path,
        )
        logger.info(
            f"Alert manager initialized (email={'enabled' if settings.enable_email_alerts else 'disabled'})"
        )

        # Initialize run reporter
        run_reporter = create_run_reporter(logger)

        # Parse question types
        question_types = None
        if args.types:
            question_types = [QuestionType(qt) for qt in args.types]
            logger.info(f"Generating only types: {[qt.value for qt in question_types]}")

        # Parse difficulty levels
        difficulty_distribution = None
        if args.difficulties:
            difficulties = [DifficultyLevel(d) for d in args.difficulties]
            # Equal distribution across selected difficulties
            weight = 1.0 / len(difficulties)
            difficulty_distribution = {d: weight for d in difficulties}
            logger.info(
                f"Generating only difficulties: {[d.value for d in difficulties]}"
            )

        # Initialize pipeline components
        logger.info("Initializing pipeline components...")

        # Check API keys
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

            # Send alert for configuration error
            from app.error_classifier import (
                ClassifiedError,
                ErrorCategory,
                ErrorSeverity,
            )

            config_error = ClassifiedError(
                category=ErrorCategory.AUTHENTICATION,
                severity=ErrorSeverity.CRITICAL,
                provider="system",
                original_error="ConfigurationError",
                message="No LLM API keys configured. Question generation cannot run.",
                is_retryable=False,
            )
            alert_manager.send_alert(
                config_error,
                context="Question generation script failed to start due to missing API keys. "
                "Check environment variables: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY",
            )

            write_heartbeat(
                status="failed",
                exit_code=EXIT_CONFIG_ERROR,
                error_message="No LLM API keys configured",
            )
            return EXIT_CONFIG_ERROR

        # Initialize pipeline
        pipeline = QuestionGenerationPipeline(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            xai_api_key=settings.xai_api_key,
        )
        logger.info("✓ Pipeline initialized")

        # Load judge configuration
        from app.judge_config import JudgeConfigLoader

        judge_loader = JudgeConfigLoader(settings.judge_config_path)
        judge_loader.load()  # Load the config into the loader
        logger.info(f"✓ Judge config loaded from {settings.judge_config_path}")

        # Load generator configuration (specialist routing)
        from app.generator_config import initialize_generator_config

        try:
            initialize_generator_config(settings.generator_config_path)
            logger.info(
                f"✓ Generator config loaded from {settings.generator_config_path}"
            )
        except FileNotFoundError:
            logger.warning(
                f"Generator config not found at {settings.generator_config_path}. "
                "Using round-robin distribution instead of specialist routing."
            )

        # Initialize judge (pass the loader, not the config)
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

        # Initialize database and deduplicator
        db = None
        deduplicator = None

        if not args.dry_run:
            try:
                # TASK-433: Pass OpenAI API key to database service for embedding generation
                db = QuestionDatabase(
                    database_url=settings.database_url,
                    openai_api_key=settings.openai_api_key,
                )
                logger.info("✓ Database connected")

                if not settings.openai_api_key:
                    logger.error("OpenAI API key required for deduplication")
                    return EXIT_CONFIG_ERROR

                deduplicator = QuestionDeduplicator(
                    openai_api_key=settings.openai_api_key,
                    similarity_threshold=settings.dedup_similarity_threshold,
                    embedding_model=settings.dedup_embedding_model,
                    redis_url=settings.redis_url,
                    embedding_cache_ttl=settings.embedding_cache_ttl,
                )
                cache_type = "Redis" if deduplicator.using_redis_cache else "in-memory"
                logger.info(f"✓ Deduplicator initialized (cache: {cache_type})")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")

                # Send alert for database error
                from app.error_classifier import (
                    ClassifiedError,
                    ErrorCategory,
                    ErrorSeverity,
                )

                db_error = ClassifiedError(
                    category=ErrorCategory.SERVER_ERROR,
                    severity=ErrorSeverity.CRITICAL,
                    provider="database",
                    original_error=type(e).__name__,
                    message=f"Database connection failed: {str(e)}",
                    is_retryable=False,
                )
                alert_manager.send_alert(
                    db_error,
                    context=f"Question generation cannot connect to database. "
                    f"Check DATABASE_URL and database availability. Error: {str(e)}",
                )

                write_heartbeat(
                    status="failed",
                    exit_code=EXIT_DATABASE_ERROR,
                    error_message=f"Database connection failed: {str(e)}",
                )
                return EXIT_DATABASE_ERROR

        # Auto-balance inventory analysis (if enabled)
        generation_plan = None
        if args.auto_balance:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 0: Inventory Analysis (Auto-Balance)")
            logger.info("=" * 80)

            if not db:
                logger.error(
                    "Auto-balance requires database connection (cannot use --dry-run)"
                )
                write_heartbeat(
                    status="failed",
                    exit_code=EXIT_CONFIG_ERROR,
                    error_message="Auto-balance requires database connection",
                )
                return EXIT_CONFIG_ERROR

            # Initialize inventory analyzer
            analyzer = InventoryAnalyzer(
                database_service=db,
                healthy_threshold=args.healthy_threshold,
                warning_threshold=args.warning_threshold,
                target_per_stratum=args.target_per_stratum,
            )

            # Analyze current inventory
            analysis = analyzer.analyze_inventory()
            analyzer.log_inventory_summary(analysis)

            # Compute generation plan
            target_count = args.count or settings.questions_per_run
            generation_plan = analyzer.compute_generation_plan(
                target_total=target_count,
                analysis=analysis,
            )

            logger.info("\n" + generation_plan.to_log_summary())

            # Check inventory levels and send alerts if needed
            if not args.skip_inventory_alerts:
                logger.info("\nChecking inventory levels for alerting...")
                alerting_config = AlertingConfig.from_yaml(args.alerting_config)
                inventory_alerter = InventoryAlertManager(
                    alert_manager=alert_manager,
                    config=alerting_config,
                )

                alert_result = inventory_alerter.check_and_alert(analysis.strata)

                if alert_result.alerts_sent > 0:
                    logger.warning(
                        f"Inventory alerts sent: {alert_result.alerts_sent} strata below threshold"
                    )
                if alert_result.critical_strata:
                    logger.warning(
                        f"CRITICAL: {len(alert_result.critical_strata)} strata have "
                        f"critically low inventory (< {alerting_config.critical_min})"
                    )
                if alert_result.warning_strata:
                    logger.info(
                        f"WARNING: {len(alert_result.warning_strata)} strata have "
                        f"low inventory (< {alerting_config.warning_min})"
                    )
            else:
                logger.info("Inventory alerting skipped (--skip-inventory-alerts)")

            # If no questions needed (all strata are at target), exit early
            if generation_plan.total_questions == 0:
                logger.info("All strata are at or above target - no generation needed")
                write_heartbeat(
                    status="completed",
                    exit_code=EXIT_SUCCESS,
                    stats={"questions_generated": 0, "reason": "inventory_balanced"},
                )
                return EXIT_SUCCESS

        # Run generation job
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: Question Generation")
        logger.info("=" * 80)

        # Choose generation mode based on auto-balance flag
        if args.auto_balance and generation_plan:
            # Use balanced generation with pre-computed allocations
            logger.info("Using auto-balanced generation mode")

            if args.use_async:
                logger.info(
                    f"Using async parallel generation mode "
                    f"(max_concurrent={args.max_concurrent}, timeout={args.timeout}s)"
                )

                # Reconfigure generator with CLI-specified async parameters
                pipeline.generator._rate_limiter = asyncio.Semaphore(
                    args.max_concurrent
                )
                pipeline.generator._async_timeout = args.timeout

                async def run_balanced_async_with_cleanup() -> dict:
                    try:
                        return await pipeline.run_balanced_generation_job_async(
                            stratum_allocations=generation_plan.allocations,
                            provider_tier=args.provider_tier,
                        )
                    finally:
                        await pipeline.cleanup()

                job_result = asyncio.run(run_balanced_async_with_cleanup())
            else:
                job_result = pipeline.run_balanced_generation_job(
                    stratum_allocations=generation_plan.allocations,
                    provider_tier=args.provider_tier,
                )
        elif args.use_async:
            logger.info(
                f"Using async parallel generation mode "
                f"(max_concurrent={args.max_concurrent}, timeout={args.timeout}s)"
            )

            # Reconfigure generator with CLI-specified async parameters
            pipeline.generator._rate_limiter = asyncio.Semaphore(args.max_concurrent)
            pipeline.generator._async_timeout = args.timeout

            async def run_async_with_cleanup() -> dict:
                try:
                    return await pipeline.run_generation_job_async(
                        questions_per_run=args.count,
                        question_types=question_types,
                        difficulty_distribution=difficulty_distribution,
                        provider_tier=args.provider_tier,
                    )
                finally:
                    await pipeline.cleanup()

            job_result = asyncio.run(run_async_with_cleanup())
        else:
            job_result = pipeline.run_generation_job(
                questions_per_run=args.count,
                question_types=question_types,
                difficulty_distribution=difficulty_distribution,
                provider_tier=args.provider_tier,
            )

        stats = job_result["statistics"]
        generated_questions = job_result["questions"]

        logger.info(
            f"Generated: {stats['questions_generated']}/{stats['target_questions']} "
            f"questions ({stats['success_rate']*100:.1f}% success rate)"
        )
        logger.info(f"Duration: {stats['duration_seconds']:.1f}s")

        # Note: Generation metrics are already tracked by the pipeline internally

        # Within-batch deduplication to remove near-identical questions before judge
        if generated_questions and len(generated_questions) > 1:
            original_count = len(generated_questions)
            generated_questions = dedupe_within_batch(generated_questions)
            dupes_removed = original_count - len(generated_questions)
            if dupes_removed > 0:
                logger.info(
                    f"Within-batch dedup: Removed {dupes_removed} near-duplicate questions "
                    f"({len(generated_questions)} unique remaining)"
                )

        if not generated_questions:
            logger.error("No questions generated!")

            # Send alert for complete generation failure
            from app.error_classifier import (
                ClassifiedError,
                ErrorCategory,
                ErrorSeverity,
            )

            generation_error = ClassifiedError(
                category=ErrorCategory.UNKNOWN,
                severity=ErrorSeverity.CRITICAL,
                provider="pipeline",
                original_error="GenerationFailure",
                message="Question generation produced zero questions. All generation attempts failed.",
                is_retryable=True,
            )
            alert_manager.send_alert(
                generation_error,
                context=f"Question generation job completed but produced no questions. "
                f"Target: {stats['target_questions']}, Generated: 0. Check logs for LLM API errors.",
            )

            write_heartbeat(
                status="failed",
                exit_code=EXIT_COMPLETE_FAILURE,
                error_message="No questions generated",
                stats=stats,
            )
            return EXIT_COMPLETE_FAILURE

        # Evaluate with judge
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: Judge Evaluation")
        logger.info("=" * 80)

        min_score = args.min_score or settings.min_judge_score
        logger.info(f"Minimum approval score: {min_score}")

        approved_questions = []
        rejected_questions = []

        if args.use_async_judge:
            logger.info(
                f"Using async parallel judge evaluation mode "
                f"(max_concurrent={args.max_concurrent_judge}, "
                f"timeout={args.judge_timeout}s)"
            )

            async def run_async_judge_with_cleanup() -> list:
                try:
                    return await judge.evaluate_questions_list_async(
                        questions=generated_questions,
                    )
                finally:
                    await judge.cleanup()

            all_evaluated = asyncio.run(run_async_judge_with_cleanup())

            # Separate approved and rejected, apply difficulty placement, record metrics
            for evaluated_question in all_evaluated:
                if evaluated_question.evaluation.overall_score >= min_score:
                    logger.info(
                        f"  ✓ APPROVED (score: {evaluated_question.evaluation.overall_score:.2f})"
                    )
                    # Apply difficulty placement adjustment if needed
                    adjusted_question = apply_difficulty_placement(
                        evaluated_question, judge, logger
                    )
                    approved_questions.append(adjusted_question)
                else:
                    rejected_questions.append(evaluated_question)
                    log_rejection_details(evaluated_question, logger)

                # Record evaluation metrics
                metrics.record_evaluation_success(
                    score=evaluated_question.evaluation.overall_score,
                    approved=evaluated_question.evaluation.overall_score >= min_score,
                    judge_model=evaluated_question.judge_model,
                )
        else:
            # Sequential evaluation
            for i, question in enumerate(generated_questions, 1):
                logger.info(f"Evaluating question {i}/{len(generated_questions)}...")

                try:
                    evaluated_question = judge.evaluate_question(question)

                    if evaluated_question.evaluation.overall_score >= min_score:
                        logger.info(
                            f"  ✓ APPROVED (score: {evaluated_question.evaluation.overall_score:.2f})"
                        )
                        # Apply difficulty placement adjustment if needed
                        adjusted_question = apply_difficulty_placement(
                            evaluated_question, judge, logger
                        )
                        approved_questions.append(adjusted_question)
                    else:
                        rejected_questions.append(evaluated_question)
                        log_rejection_details(evaluated_question, logger, index=i)

                    # Record evaluation metrics
                    metrics.record_evaluation_success(
                        score=evaluated_question.evaluation.overall_score,
                        approved=evaluated_question.evaluation.overall_score
                        >= min_score,
                        judge_model=evaluated_question.judge_model,
                    )

                except Exception as e:
                    logger.error(f"  ✗ Evaluation failed: {e}")
                    # Can't append to rejected_questions as we don't have an evaluation
                    continue

        approval_rate = len(approved_questions) / len(generated_questions) * 100
        logger.info(
            f"\nApproved: {len(approved_questions)}/{len(generated_questions)} "
            f"({approval_rate:.1f}%)"
        )
        logger.info(f"Rejected: {len(rejected_questions)}")

        # Salvage phase: attempt to repair or reclassify rejected questions
        if rejected_questions:
            logger.info("\n" + "-" * 40)
            logger.info("SALVAGE PHASE: Attempting to recover rejected questions")
            logger.info("-" * 40)

            salvaged_questions = []
            still_rejected = []

            for rejected in rejected_questions:
                # Try answer repair first
                repair_result = attempt_answer_repair(rejected, logger)
                if repair_result:
                    repaired_question, reason = repair_result
                    salvaged_questions.append(repaired_question)
                    logger.info(f"  ✓ REPAIRED: {reason}")
                    logger.info(
                        f"    Question: {repaired_question.question_text[:60]}..."
                    )
                    continue

                # Try difficulty reclassification
                reclass_result = attempt_difficulty_reclassification(rejected, logger)
                if reclass_result:
                    reclassified_question, new_difficulty, reason = reclass_result
                    salvaged_questions.append(reclassified_question)
                    logger.info(f"  ✓ RECLASSIFIED: {reason}")
                    logger.info(
                        f"    Question: {reclassified_question.question_text[:60]}..."
                    )
                    continue

                # Could not salvage with repair or reclassification
                still_rejected.append(rejected)

            # Attempt regeneration with feedback for remaining rejected questions
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

                    # Add regenerated questions directly to approved list
                    # (they're already EvaluatedQuestion objects with proper scores)
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
            if total_salvaged > 0:
                logger.info(
                    f"\nSalvaged: {total_salvaged} questions "
                    f"(repaired/reclassified: {len(salvaged_questions)}, "
                    f"regenerated: {regenerated_count}, "
                    f"still rejected: {len(still_rejected)})"
                )
                # Add salvaged questions to approved list (as GeneratedQuestion, not EvaluatedQuestion)
                # We wrap them in a simple container that has .question attribute for compatibility
                for sq in salvaged_questions:
                    # Create a minimal wrapper to match EvaluatedQuestion interface
                    from app.models import EvaluatedQuestion, EvaluationScore

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
                    approved_questions.append(salvaged_eval)

            # Update stats (accounts for both repaired/reclassified and regenerated)
            approval_rate = len(approved_questions) / len(generated_questions) * 100
            logger.info(
                f"Updated approval: {len(approved_questions)}/{len(generated_questions)} "
                f"({approval_rate:.1f}%)"
            )
            if total_salvaged == 0:
                logger.info("No questions could be salvaged")

        if not approved_questions:
            logger.warning("No questions passed judge evaluation!")

            # Send alert for judge rejection
            from app.error_classifier import (
                ClassifiedError,
                ErrorCategory,
                ErrorSeverity,
            )

            judge_error = ClassifiedError(
                category=ErrorCategory.INVALID_REQUEST,
                severity=ErrorSeverity.HIGH,
                provider="judge",
                original_error="JudgeRejectionFailure",
                message=f"All {len(generated_questions)} generated questions were rejected by judge evaluation.",
                is_retryable=True,
            )
            alert_manager.send_alert(
                judge_error,
                context=f"Question generation produced {len(generated_questions)} questions but judge "
                f"rejected all of them. Minimum score threshold: {min_score}. "
                f"Consider reviewing judge configuration or lowering MIN_JUDGE_SCORE.",
            )

            write_heartbeat(
                status="failed",
                exit_code=EXIT_COMPLETE_FAILURE,
                error_message="No questions passed judge evaluation",
                stats=stats,
            )
            return EXIT_COMPLETE_FAILURE

        # Deduplication
        unique_questions = approved_questions

        if not args.skip_deduplication and not args.dry_run:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 3: Deduplication")
            logger.info("=" * 80)

            # Fetch existing questions from database for deduplication
            try:
                assert db is not None
                existing_questions = db.get_all_questions()
                logger.info(
                    f"Loaded {len(existing_questions)} existing questions for deduplication"
                )
            except Exception as e:
                logger.error(f"Failed to load existing questions: {e}")
                existing_questions = []

            unique_questions = []
            duplicate_count = 0

            for evaluated_question in approved_questions:
                try:
                    # Type assertion: deduplicator is guaranteed to be initialized here
                    assert deduplicator is not None
                    # Scope dedup to same difficulty level — questions sharing a
                    # problem template across difficulties are intentionally distinct.
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

                except Exception as e:
                    logger.error(f"Deduplication check failed: {e}")
                    # Include question if deduplication check fails (fail open)
                    unique_questions.append(evaluated_question)
                    continue

            logger.info(f"\nUnique questions: {len(unique_questions)}")
            logger.info(f"Duplicates removed: {duplicate_count}")

        # Database insertion
        inserted_count = 0

        if not args.dry_run and unique_questions:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 4: Database Insertion")
            logger.info("=" * 80)

            for i, evaluated_question in enumerate(unique_questions, 1):
                try:
                    # Type assertion: db is guaranteed to be initialized here
                    assert db is not None
                    question_id = db.insert_evaluated_question(evaluated_question)
                    inserted_count += 1
                    logger.debug(
                        f"✓ Inserted question {i}/{len(unique_questions)} "
                        f"(ID: {question_id}, score: {evaluated_question.evaluation.overall_score:.2f})"
                    )

                    metrics.record_insertion_success(count=1)

                except Exception as e:
                    logger.error(f"✗ Failed to insert question {i}: {e}")
                    metrics.record_insertion_failure(error=str(e), count=1)
                    continue

            logger.info(
                f"\nInserted: {inserted_count}/{len(unique_questions)} questions"
            )

        # Final summary
        metrics.end_run()
        summary = metrics.get_summary()

        logger.info("\n" + "=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total duration: {summary['execution']['duration_seconds']:.1f}s")
        logger.info(f"Generated: {stats['questions_generated']}")
        logger.info(f"Approved by judge: {len(approved_questions)}")
        logger.info(f"Unique: {len(unique_questions)}")
        logger.info(f"Inserted to database: {inserted_count}")
        logger.info(f"Approval rate: {approval_rate:.1f}%")

        if args.dry_run:
            logger.info("\n[DRY RUN] No questions were inserted to database")

        # Determine exit code
        if args.dry_run:
            exit_code = EXIT_SUCCESS
        elif inserted_count == 0:
            logger.error("No questions were inserted to database!")

            # Send alert for insertion failure
            from app.error_classifier import (
                ClassifiedError,
                ErrorCategory,
                ErrorSeverity,
            )

            insertion_error = ClassifiedError(
                category=ErrorCategory.SERVER_ERROR,
                severity=ErrorSeverity.CRITICAL,
                provider="database",
                original_error="InsertionFailure",
                message=f"Database insertion failed for all {len(unique_questions)} unique questions.",
                is_retryable=True,
            )
            alert_manager.send_alert(
                insertion_error,
                context=f"Question generation completed successfully through judge evaluation, "
                f"but all {len(unique_questions)} questions failed to insert to database. Check database connection and logs.",
            )

            exit_code = EXIT_COMPLETE_FAILURE
        elif inserted_count < len(unique_questions):
            logger.warning("Some questions failed to insert")
            exit_code = EXIT_PARTIAL_FAILURE
        else:
            logger.info("✓ All unique questions inserted successfully")
            exit_code = EXIT_SUCCESS

        # Write success metrics for successful runs
        if exit_code == EXIT_SUCCESS and inserted_count > 0:
            log_success_run(
                stats=stats,
                inserted_count=inserted_count,
                approval_rate=approval_rate,
            )
            logger.info("Success metrics logged to logs/success_runs.jsonl")

        # Write final heartbeat with completion status
        write_heartbeat(
            status="completed" if exit_code == EXIT_SUCCESS else "failed",
            exit_code=exit_code,
            stats={
                "questions_generated": stats["questions_generated"],
                "questions_inserted": inserted_count,
                "approval_rate": approval_rate,
                "duration_seconds": stats["duration_seconds"],
            },
        )

        # Report run to backend API
        if run_reporter:
            min_score = args.min_score or settings.min_judge_score
            run_id = run_reporter.report_run(
                metrics_tracker=metrics,
                exit_code=exit_code,
                environment=settings.env,
                triggered_by=args.triggered_by,
                prompt_version=settings.prompt_version,
                judge_config_version=settings.judge_config_version,
                min_judge_score_threshold=min_score,
            )
            if run_id:
                logger.info(f"Run reported to backend API (ID: {run_id})")
            else:
                logger.warning("Failed to report run to backend API")

        logger.info("=" * 80)
        logger.info(f"Script completed with exit code: {exit_code}")
        logger.info("=" * 80)

        return exit_code

    except KeyboardInterrupt:
        logger.warning("\nScript interrupted by user")

        write_heartbeat(
            status="failed",
            exit_code=EXIT_PARTIAL_FAILURE,
            error_message="Script interrupted by user",
        )
        return EXIT_PARTIAL_FAILURE

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")

        # Try to send alert for unexpected errors
        try:
            from app.error_classifier import ErrorClassifier

            classified_error = ErrorClassifier.classify_error(e, "system")

            # Initialize alert manager if not already done
            if "alert_manager" not in locals():
                to_emails = []
                if settings.alert_to_emails:
                    to_emails = [
                        email.strip() for email in settings.alert_to_emails.split(",")
                    ]

                alert_manager = AlertManager(
                    email_enabled=settings.enable_email_alerts,
                    smtp_host=settings.smtp_host,
                    smtp_port=settings.smtp_port,
                    smtp_username=settings.smtp_username,
                    smtp_password=settings.smtp_password,
                    from_email=settings.alert_from_email,
                    to_emails=to_emails,
                    alert_file_path=settings.alert_file_path,
                )

            alert_manager.send_alert(
                classified_error,
                context=f"Question generation script encountered an unexpected error and crashed. "
                f"Error: {str(e)[:200]}. Check logs for full details.",
            )
        except Exception as alert_error:
            # Don't let alert failures prevent cleanup
            logger.error(f"Failed to send alert for unexpected error: {alert_error}")

        write_heartbeat(
            status="failed",
            exit_code=EXIT_COMPLETE_FAILURE,
            error_message=f"Unexpected error: {str(e)[:100]}",
        )
        return EXIT_COMPLETE_FAILURE

    finally:
        # Clean up database connection
        if "db" in locals() and db:
            try:
                db.close()
                logger.info("Database connection closed")
            except Exception:
                pass

        # Shutdown observability backends (flushes pending data to Sentry/OTEL)
        try:
            observability.flush(timeout=5.0)
            observability.shutdown()
        except Exception:
            pass


if __name__ == "__main__":
    sys.exit(main())
