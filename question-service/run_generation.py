#!/usr/bin/env python3
"""Standalone question generation script.

This script runs the complete question generation pipeline including:
- Question generation across multiple LLM providers
- Arbiter evaluation of question quality
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
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app import (  # noqa: E402
    QuestionArbiter,
    QuestionDatabase,
    QuestionDeduplicator,
    QuestionGenerationPipeline,
)
from app.config import settings  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.metrics import GenerationMetrics  # noqa: E402
from app.models import QuestionType  # noqa: E402

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_COMPLETE_FAILURE = 2
EXIT_CONFIG_ERROR = 3
EXIT_DATABASE_ERROR = 4


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

  # Generate only mathematical and logical reasoning questions
  python run_generation.py --types mathematical logical_reasoning

  # Dry run (generate but don't insert to database)
  python run_generation.py --dry-run

  # Verbose logging
  python run_generation.py --verbose
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
        help=f"Minimum arbiter score for approval (default: {settings.min_arbiter_score})",
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

    return parser.parse_args()


def main() -> int:
    """Main entry point for question generation script.

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
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
    import logging

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
        metrics = GenerationMetrics()
        metrics.start_run()

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
            ]
        ):
            logger.error("No LLM API keys configured!")
            logger.error("Set OPENAI_API_KEY, ANTHROPIC_API_KEY, or GOOGLE_API_KEY")
            return EXIT_CONFIG_ERROR

        # Initialize pipeline
        pipeline = QuestionGenerationPipeline(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
        )
        logger.info("✓ Pipeline initialized")

        # Initialize arbiter
        arbiter = QuestionArbiter(
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
        )
        logger.info("✓ Arbiter initialized")

        # Initialize database and deduplicator
        db = None
        deduplicator = None

        if not args.dry_run:
            try:
                db = QuestionDatabase(settings.database_url)
                logger.info("✓ Database connected")

                deduplicator = QuestionDeduplicator(db)
                logger.info("✓ Deduplicator initialized")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                return EXIT_DATABASE_ERROR

        # Run generation job
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 1: Question Generation")
        logger.info("=" * 80)

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

        metrics.record_generation(
            generated_count=stats["questions_generated"],
            target_count=stats["target_questions"],
            duration=stats["duration_seconds"],
        )

        if not generated_questions:
            logger.error("No questions generated!")
            return EXIT_COMPLETE_FAILURE

        # Evaluate with arbiter
        logger.info("\n" + "=" * 80)
        logger.info("PHASE 2: Arbiter Evaluation")
        logger.info("=" * 80)

        min_score = args.min_score or settings.min_arbiter_score
        logger.info(f"Minimum approval score: {min_score}")

        approved_questions = []
        rejected_questions = []

        for i, question in enumerate(generated_questions, 1):
            logger.info(f"Evaluating question {i}/{len(generated_questions)}...")

            try:
                evaluation = arbiter.evaluate_question(question)

                if evaluation.overall_score >= min_score:
                    approved_questions.append(question)
                    logger.info(f"  ✓ APPROVED (score: {evaluation.overall_score:.2f})")
                else:
                    rejected_questions.append(question)
                    logger.info(f"  ✗ REJECTED (score: {evaluation.overall_score:.2f})")

                metrics.record_evaluation(
                    question_type=question.question_type.value,
                    approved=evaluation.overall_score >= min_score,
                    score=evaluation.overall_score,
                )

            except Exception as e:
                logger.error(f"  ✗ Evaluation failed: {e}")
                rejected_questions.append(question)
                continue

        approval_rate = len(approved_questions) / len(generated_questions) * 100
        logger.info(
            f"\nApproved: {len(approved_questions)}/{len(generated_questions)} "
            f"({approval_rate:.1f}%)"
        )
        logger.info(f"Rejected: {len(rejected_questions)}")

        if not approved_questions:
            logger.warning("No questions passed arbiter evaluation!")
            return EXIT_COMPLETE_FAILURE

        # Deduplication
        unique_questions = approved_questions

        if not args.skip_deduplication and not args.dry_run:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 3: Deduplication")
            logger.info("=" * 80)

            unique_questions = []
            duplicate_count = 0

            for question in approved_questions:
                try:
                    # Type assertion: deduplicator is guaranteed to be initialized here
                    assert deduplicator is not None
                    is_duplicate = deduplicator.is_duplicate(question)

                    if not is_duplicate:
                        unique_questions.append(question)
                        logger.debug(f"✓ Unique: {question.question_text[:60]}...")
                    else:
                        duplicate_count += 1
                        logger.info(f"✗ Duplicate: {question.question_text[:60]}...")

                    metrics.record_deduplication(
                        question_type=question.question_type.value,
                        is_duplicate=is_duplicate,
                    )

                except Exception as e:
                    logger.error(f"Deduplication check failed: {e}")
                    # Include question if deduplication check fails (fail open)
                    unique_questions.append(question)
                    continue

            logger.info(f"\nUnique questions: {len(unique_questions)}")
            logger.info(f"Duplicates removed: {duplicate_count}")

        # Database insertion
        inserted_count = 0

        if not args.dry_run and unique_questions:
            logger.info("\n" + "=" * 80)
            logger.info("PHASE 4: Database Insertion")
            logger.info("=" * 80)

            for i, question in enumerate(unique_questions, 1):
                try:
                    # Type assertion: db is guaranteed to be initialized here
                    assert db is not None
                    question_id = db.insert_question(question)
                    inserted_count += 1
                    logger.debug(
                        f"✓ Inserted question {i}/{len(unique_questions)} "
                        f"(ID: {question_id})"
                    )

                    metrics.record_insertion(
                        question_type=question.question_type.value,
                        success=True,
                    )

                except Exception as e:
                    logger.error(f"✗ Failed to insert question {i}: {e}")
                    metrics.record_insertion(
                        question_type=question.question_type.value,
                        success=False,
                    )
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
        logger.info(f"Total duration: {summary['duration_seconds']:.1f}s")
        logger.info(f"Generated: {stats['questions_generated']}")
        logger.info(f"Approved by arbiter: {len(approved_questions)}")
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
            exit_code = EXIT_COMPLETE_FAILURE
        elif inserted_count < len(unique_questions):
            logger.warning("Some questions failed to insert")
            exit_code = EXIT_PARTIAL_FAILURE
        else:
            logger.info("✓ All unique questions inserted successfully")
            exit_code = EXIT_SUCCESS

        logger.info("=" * 80)
        logger.info(f"Script completed with exit code: {exit_code}")
        logger.info("=" * 80)

        return exit_code

    except KeyboardInterrupt:
        logger.warning("\nScript interrupted by user")
        return EXIT_PARTIAL_FAILURE

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return EXIT_COMPLETE_FAILURE

    finally:
        # Clean up database connection
        if db:
            try:
                db.close()
                logger.info("Database connection closed")
            except Exception:
                pass


if __name__ == "__main__":
    sys.exit(main())
