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
)
from app.alerting import AlertManager  # noqa: E402
from app.config import settings  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.metrics import MetricsTracker  # noqa: E402
from app.models import QuestionType  # noqa: E402
from app.reporter import RunReporter  # noqa: E402

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
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info(
        f"Configuration: count={args.count or settings.questions_per_run}, "
        f"types={args.types or 'all'}"
    )
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
            logger.info(f"Generating only: {[qt.value for qt in question_types]}")

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
                )
                logger.info("✓ Deduplicator initialized")
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

        # Run generation job
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: Question Generation")
        logger.info("=" * 80)

        if args.use_async:
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
                    )
                finally:
                    await pipeline.cleanup()

            job_result = asyncio.run(run_async_with_cleanup())
        else:
            job_result = pipeline.run_generation_job(
                questions_per_run=args.count,
                question_types=question_types,
            )

        stats = job_result["statistics"]
        generated_questions = job_result["questions"]

        logger.info(
            f"Generated: {stats['questions_generated']}/{stats['target_questions']} "
            f"questions ({stats['success_rate']*100:.1f}% success rate)"
        )
        logger.info(f"Duration: {stats['duration_seconds']:.1f}s")

        # Note: Generation metrics are already tracked by the pipeline internally

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

            # Separate approved and rejected, record metrics
            for evaluated_question in all_evaluated:
                if evaluated_question.evaluation.overall_score >= min_score:
                    approved_questions.append(evaluated_question)
                    logger.info(
                        f"  ✓ APPROVED (score: {evaluated_question.evaluation.overall_score:.2f})"
                    )
                else:
                    rejected_questions.append(evaluated_question)
                    logger.info(
                        f"  ✗ REJECTED (score: {evaluated_question.evaluation.overall_score:.2f})"
                    )

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
                        approved_questions.append(
                            evaluated_question
                        )  # Store evaluated_question with score
                        logger.info(
                            f"  ✓ APPROVED (score: {evaluated_question.evaluation.overall_score:.2f})"
                        )
                    else:
                        rejected_questions.append(
                            evaluated_question
                        )  # Also store rejected with scores for metrics
                        logger.info(
                            f"  ✗ REJECTED (score: {evaluated_question.evaluation.overall_score:.2f})"
                        )

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
                    result = deduplicator.check_duplicate(
                        evaluated_question.question, existing_questions
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


if __name__ == "__main__":
    sys.exit(main())
