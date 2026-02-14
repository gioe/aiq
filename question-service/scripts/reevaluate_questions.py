#!/usr/bin/env python3
"""Re-evaluate existing questions with updated judge logic.

This script re-evaluates all questions in the database using the current
judge configuration and scoring weights. Use this when evaluation criteria
have changed (e.g., difficulty moved from weighted scoring to placement).

The script:
1. Fetches all active questions from the database
2. Re-evaluates each through the appropriate judge model
3. Calculates new overall_score using current weights
4. Applies difficulty placement logic to potentially recategorize
5. Updates judge_score and difficulty_level in the database
6. Optionally deactivates questions that fall below threshold

Exit Codes:
    0 - Success (all questions re-evaluated)
    1 - Partial failure (some questions failed to re-evaluate)
    2 - Complete failure (no questions re-evaluated)
    3 - Configuration error
    4 - Database connection error
"""

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.config.config import settings  # noqa: E402
from app.data.database import DatabaseService, QuestionModel  # noqa: E402
from app.evaluation.judge import QuestionJudge  # noqa: E402
from app.config.judge_config import JudgeConfigLoader  # noqa: E402
from app.infrastructure.logging_config import setup_logging  # noqa: E402
from app.data.models import (  # noqa: E402
    DifficultyLevel,
    GeneratedQuestion,
    QuestionType,
)

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_COMPLETE_FAILURE = 2
EXIT_CONFIG_ERROR = 3
EXIT_DATABASE_ERROR = 4


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Re-evaluate existing questions with updated judge logic",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Re-evaluate all questions
  python reevaluate_questions.py

  # Re-evaluate only math questions
  python reevaluate_questions.py --types math

  # Re-evaluate only hard questions
  python reevaluate_questions.py --difficulties hard

  # Dry run (evaluate but don't update database)
  python reevaluate_questions.py --dry-run

  # Deactivate questions that now fall below threshold
  python reevaluate_questions.py --deactivate-below-threshold

  # Re-evaluate with async parallel processing
  python reevaluate_questions.py --async

  # Limit to first 100 questions (for testing)
  python reevaluate_questions.py --limit 100
        """,
    )

    parser.add_argument(
        "--types",
        nargs="+",
        choices=[qt.value for qt in QuestionType],
        default=None,
        help="Question types to re-evaluate (default: all types)",
    )

    parser.add_argument(
        "--difficulties",
        nargs="+",
        choices=[dl.value for dl in DifficultyLevel],
        default=None,
        help="Difficulty levels to re-evaluate (default: all levels)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Evaluate questions but don't update database",
    )

    parser.add_argument(
        "--deactivate-below-threshold",
        action="store_true",
        help="Deactivate questions that fall below the minimum score threshold",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=None,
        help=f"Minimum judge score for approval (default: {settings.min_judge_score})",
    )

    parser.add_argument(
        "--async",
        dest="use_async",
        action="store_true",
        help="Use async parallel evaluation for faster processing",
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
        "--limit",
        type=int,
        default=None,
        help="Limit number of questions to re-evaluate (for testing)",
    )

    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="Skip first N questions (for batch processing)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    parser.add_argument(
        "--only-recalculate",
        action="store_true",
        help="Only recalculate scores from stored individual scores in metadata "
        "(no API calls). Only works for questions that have individual scores stored.",
    )

    return parser.parse_args()


def db_question_to_generated(db_question: Dict[str, Any]) -> GeneratedQuestion:
    """Convert a database question dict to a GeneratedQuestion object.

    Args:
        db_question: Question dictionary from database

    Returns:
        GeneratedQuestion object
    """
    # Handle enum values that might be strings or enum objects
    question_type = db_question["question_type"]
    if isinstance(question_type, str):
        question_type = QuestionType(question_type)
    elif hasattr(question_type, "value"):
        question_type = QuestionType(question_type.value)

    difficulty_level = db_question["difficulty_level"]
    if isinstance(difficulty_level, str):
        difficulty_level = DifficultyLevel(difficulty_level)
    elif hasattr(difficulty_level, "value"):
        difficulty_level = DifficultyLevel(difficulty_level.value)

    return GeneratedQuestion(
        question_text=db_question["question_text"],
        question_type=question_type,
        difficulty_level=difficulty_level,
        correct_answer=db_question["correct_answer"],
        answer_options=db_question.get("answer_options"),
        explanation=db_question.get("explanation"),
        stimulus=db_question.get("stimulus"),
        sub_type=db_question.get("sub_type"),
        metadata=db_question.get("metadata") or {},
        source_llm=db_question.get("source_llm") or "unknown",
        source_model=db_question.get("source_model") or "unknown",
    )


def recalculate_from_metadata(
    db_question: Dict[str, Any],
    judge_config: JudgeConfigLoader,
    logger: logging.Logger,
) -> Optional[Dict[str, Any]]:
    """Recalculate overall score from stored individual scores in metadata.

    Args:
        db_question: Question dictionary from database
        judge_config: Judge configuration loader
        logger: Logger instance

    Returns:
        Dictionary with new scores if metadata has individual scores, None otherwise
    """
    metadata = db_question.get("metadata") or {}
    evaluation_scores = metadata.get("evaluation_scores")

    if not evaluation_scores:
        return None

    # Check for required individual scores
    required_scores = [
        "clarity_score",
        "validity_score",
        "formatting_score",
        "creativity_score",
    ]
    if not all(score in evaluation_scores for score in required_scores):
        return None

    # Get weights from config
    criteria = judge_config.get_evaluation_criteria()

    # Calculate new overall score using current weights
    new_overall = (
        evaluation_scores["clarity_score"] * criteria.clarity
        + evaluation_scores["validity_score"] * criteria.validity
        + evaluation_scores["formatting_score"] * criteria.formatting
        + evaluation_scores["creativity_score"] * criteria.creativity
    )

    # Ensure score is in valid range
    new_overall = max(0.0, min(1.0, new_overall))

    return {
        "overall_score": new_overall,
        "difficulty_score": evaluation_scores.get("difficulty_score", 0.5),
        "feedback": evaluation_scores.get("feedback"),
    }


async def reevaluate_question_async(
    db_question: Dict[str, Any],
    judge: QuestionJudge,
    logger: logging.Logger,
) -> Optional[Dict[str, Any]]:
    """Re-evaluate a single question asynchronously.

    Args:
        db_question: Question dictionary from database
        judge: QuestionJudge instance
        logger: Logger instance

    Returns:
        Dictionary with evaluation results, or None if failed
    """
    try:
        generated = db_question_to_generated(db_question)
        evaluated = await judge.evaluate_question_async(generated)

        return {
            "id": db_question["id"],
            "old_score": db_question.get("judge_score"),
            "new_score": evaluated.evaluation.overall_score,
            "old_difficulty": db_question["difficulty_level"],
            "evaluation": evaluated.evaluation,
            "approved": evaluated.approved,
            "generated_question": generated,
        }

    except Exception as e:
        logger.error(f"Failed to re-evaluate question {db_question['id']}: {e}")
        return None


def reevaluate_question_sync(
    db_question: Dict[str, Any],
    judge: QuestionJudge,
    logger: logging.Logger,
) -> Optional[Dict[str, Any]]:
    """Re-evaluate a single question synchronously.

    Args:
        db_question: Question dictionary from database
        judge: QuestionJudge instance
        logger: Logger instance

    Returns:
        Dictionary with evaluation results, or None if failed
    """
    try:
        generated = db_question_to_generated(db_question)
        evaluated = judge.evaluate_question(generated)

        return {
            "id": db_question["id"],
            "old_score": db_question.get("judge_score"),
            "new_score": evaluated.evaluation.overall_score,
            "old_difficulty": db_question["difficulty_level"],
            "evaluation": evaluated.evaluation,
            "approved": evaluated.approved,
            "generated_question": generated,
        }

    except Exception as e:
        logger.error(f"Failed to re-evaluate question {db_question['id']}: {e}")
        return None


def main() -> int:
    """Main entry point for re-evaluation script."""
    args = parse_arguments()

    # Setup logging
    log_level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("Question Re-Evaluation Script Starting")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info(
        f"Filters: types={args.types or 'all'}, difficulties={args.difficulties or 'all'}"
    )
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Deactivate below threshold: {args.deactivate_below_threshold}")
    logger.info("=" * 80)

    try:
        # Initialize database
        logger.info("Connecting to database...")
        db = DatabaseService(
            database_url=settings.database_url,
            openai_api_key=settings.openai_api_key,
        )

        if not db.test_connection():
            logger.error("Database connection failed!")
            return EXIT_DATABASE_ERROR

        logger.info("Database connected")

        # Fetch questions to re-evaluate
        logger.info("Fetching questions from database...")
        all_questions = db.get_all_questions()
        logger.info(f"Found {len(all_questions)} total questions")

        # Filter by active status
        questions = [q for q in all_questions if q.get("is_active", True)]
        logger.info(f"Active questions: {len(questions)}")

        # Filter by question type if specified
        if args.types:
            type_values = args.types
            questions = [
                q
                for q in questions
                if (
                    q["question_type"].value
                    if hasattr(q["question_type"], "value")
                    else q["question_type"]
                )
                in type_values
            ]
            logger.info(f"After type filter: {len(questions)}")

        # Filter by difficulty if specified
        if args.difficulties:
            diff_values = args.difficulties
            questions = [
                q
                for q in questions
                if (
                    q["difficulty_level"].value
                    if hasattr(q["difficulty_level"], "value")
                    else q["difficulty_level"]
                )
                in diff_values
            ]
            logger.info(f"After difficulty filter: {len(questions)}")

        # Apply offset and limit
        if args.offset > 0:
            questions = questions[args.offset :]
            logger.info(f"After offset ({args.offset}): {len(questions)}")

        if args.limit:
            questions = questions[: args.limit]
            logger.info(f"After limit ({args.limit}): {len(questions)}")

        if not questions:
            logger.info("No questions to re-evaluate")
            return EXIT_SUCCESS

        # Load judge configuration
        logger.info(f"Loading judge config from {settings.judge_config_path}...")
        judge_loader = JudgeConfigLoader(settings.judge_config_path)
        judge_loader.load()

        min_score = args.min_score or judge_loader.get_min_judge_score()
        logger.info(f"Minimum score threshold: {min_score}")

        # Check if we can use metadata-only recalculation
        if args.only_recalculate:
            logger.info("\n" + "=" * 80)
            logger.info("RECALCULATING FROM STORED METADATA (NO API CALLS)")
            logger.info("=" * 80)

            success_count = 0
            skip_count = 0
            score_changes = []
            difficulty_changes = []

            for i, q in enumerate(questions, 1):
                result = recalculate_from_metadata(q, judge_loader, logger)

                if result is None:
                    skip_count += 1
                    logger.debug(
                        f"[{i}/{len(questions)}] Skipped (no stored scores): ID={q['id']}"
                    )
                    continue

                old_score = q.get("judge_score") or 0.0
                new_score = result["overall_score"]
                score_diff = new_score - old_score

                if abs(score_diff) > 0.01:
                    score_changes.append(
                        {
                            "id": q["id"],
                            "old": old_score,
                            "new": new_score,
                            "diff": score_diff,
                        }
                    )

                # Check difficulty placement
                generated = db_question_to_generated(q)
                # Create a temporary judge just for placement logic
                temp_judge = QuestionJudge(
                    judge_config=judge_loader,
                    openai_api_key=settings.openai_api_key,
                    anthropic_api_key=settings.anthropic_api_key,
                    google_api_key=settings.google_api_key,
                    xai_api_key=settings.xai_api_key,
                )

                new_difficulty, reason = temp_judge.determine_difficulty_placement(
                    current_difficulty=generated.difficulty_level,
                    difficulty_score=result["difficulty_score"],
                    feedback=result.get("feedback"),
                )

                if reason:
                    difficulty_changes.append(
                        {
                            "id": q["id"],
                            "old": generated.difficulty_level.value,
                            "new": new_difficulty.value,
                            "reason": reason,
                        }
                    )

                success_count += 1

                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{len(questions)} questions processed")

            logger.info("\nRecalculation complete:")
            logger.info(f"  Processed: {success_count}")
            logger.info(f"  Skipped (no stored scores): {skip_count}")
            logger.info(f"  Score changes: {len(score_changes)}")
            logger.info(f"  Difficulty changes: {len(difficulty_changes)}")

            if score_changes:
                logger.info("\nSignificant score changes:")
                for change in score_changes[:20]:
                    direction = "+" if change["diff"] > 0 else ""
                    logger.info(
                        f"  ID={change['id']}: {change['old']:.3f} -> {change['new']:.3f} "
                        f"({direction}{change['diff']:.3f})"
                    )
                if len(score_changes) > 20:
                    logger.info(f"  ... and {len(score_changes) - 20} more")

            if difficulty_changes:
                logger.info("\nDifficulty changes:")
                for change in difficulty_changes[:20]:
                    logger.info(
                        f"  ID={change['id']}: {change['old']} -> {change['new']}"
                    )
                if len(difficulty_changes) > 20:
                    logger.info(f"  ... and {len(difficulty_changes) - 20} more")

            return EXIT_SUCCESS

        # Initialize judge for API-based re-evaluation
        logger.info("Initializing judge...")

        if not any(
            [
                settings.openai_api_key,
                settings.anthropic_api_key,
                settings.google_api_key,
                settings.xai_api_key,
            ]
        ):
            logger.error("No LLM API keys configured!")
            return EXIT_CONFIG_ERROR

        judge = QuestionJudge(
            judge_config=judge_loader,
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
            google_api_key=settings.google_api_key,
            xai_api_key=settings.xai_api_key,
            max_concurrent_evaluations=args.max_concurrent,
            async_timeout_seconds=args.timeout,
        )
        logger.info("Judge initialized")

        # Re-evaluate questions
        logger.info("\n" + "=" * 80)
        logger.info("RE-EVALUATION PHASE")
        logger.info("=" * 80)

        results: List[Dict[str, Any]] = []
        errors = 0

        if args.use_async:
            logger.info(
                f"Using async parallel mode (max_concurrent={args.max_concurrent})"
            )

            async def run_async_evaluation():
                nonlocal errors
                tasks = [reevaluate_question_async(q, judge, logger) for q in questions]

                all_results = await asyncio.gather(*tasks, return_exceptions=True)

                for i, result in enumerate(all_results):
                    if isinstance(result, Exception):
                        logger.error(f"Question {questions[i]['id']}: {result}")
                        errors += 1
                    elif result is None:
                        errors += 1
                    else:
                        results.append(result)

                await judge.cleanup()

            asyncio.run(run_async_evaluation())

        else:
            # Sequential evaluation
            for i, q in enumerate(questions, 1):
                logger.info(
                    f"Re-evaluating question {i}/{len(questions)} (ID={q['id']})..."
                )

                result = reevaluate_question_sync(q, judge, logger)

                if result:
                    results.append(result)
                    score_diff = result["new_score"] - (result["old_score"] or 0)
                    direction = "+" if score_diff > 0 else ""
                    logger.info(
                        f"  Score: {result['old_score']:.3f} -> {result['new_score']:.3f} "
                        f"({direction}{score_diff:.3f})"
                    )
                else:
                    errors += 1

        logger.info("\nRe-evaluation complete:")
        logger.info(f"  Successful: {len(results)}")
        logger.info(f"  Errors: {errors}")

        if not results:
            logger.error("No questions were successfully re-evaluated!")
            return EXIT_COMPLETE_FAILURE

        # Analyze results
        logger.info("\n" + "=" * 80)
        logger.info("ANALYSIS")
        logger.info("=" * 80)

        score_increases = [r for r in results if r["new_score"] > (r["old_score"] or 0)]
        score_decreases = [r for r in results if r["new_score"] < (r["old_score"] or 0)]
        now_below_threshold = [r for r in results if not r["approved"]]
        difficulty_changes = []

        # Apply difficulty placement logic
        for result in results:
            new_difficulty, reason = judge.determine_difficulty_placement(
                current_difficulty=result["generated_question"].difficulty_level,
                difficulty_score=result["evaluation"].difficulty_score,
                feedback=result["evaluation"].feedback,
            )

            if reason:
                result["new_difficulty"] = new_difficulty
                result["difficulty_reason"] = reason
                difficulty_changes.append(result)

        logger.info(f"Score increases: {len(score_increases)}")
        logger.info(f"Score decreases: {len(score_decreases)}")
        logger.info(f"Now below threshold ({min_score}): {len(now_below_threshold)}")
        logger.info(f"Difficulty changes needed: {len(difficulty_changes)}")

        # Show samples
        if score_decreases:
            logger.info("\nSample score decreases:")
            for r in score_decreases[:5]:
                logger.info(
                    f"  ID={r['id']}: {r['old_score']:.3f} -> {r['new_score']:.3f}"
                )

        if now_below_threshold:
            logger.info(f"\nQuestions now below threshold ({min_score}):")
            for r in now_below_threshold[:10]:
                logger.info(f"  ID={r['id']}: score={r['new_score']:.3f}")

        if difficulty_changes:
            logger.info("\nDifficulty placement changes:")
            for r in difficulty_changes[:10]:
                old_diff = r["old_difficulty"]
                if hasattr(old_diff, "value"):
                    old_diff = old_diff.value
                logger.info(
                    f"  ID={r['id']}: {old_diff} -> {r['new_difficulty'].value}"
                )

        # Database updates
        if not args.dry_run:
            logger.info("\n" + "=" * 80)
            logger.info("DATABASE UPDATE PHASE")
            logger.info("=" * 80)

            session = db.get_session()
            update_count = 0
            deactivate_count = 0

            try:
                for result in results:
                    question_id = result["id"]

                    # Build update data
                    update_data = {
                        "judge_score": result["new_score"],
                    }

                    # Update difficulty if changed
                    if "new_difficulty" in result:
                        update_data["difficulty_level"] = result["new_difficulty"].value

                    # Store individual scores in metadata for future recalculations
                    existing_metadata = {}
                    db_question = (
                        session.query(QuestionModel)
                        .filter(QuestionModel.id == question_id)
                        .first()
                    )

                    if db_question:
                        existing_metadata = db_question.question_metadata or {}

                    existing_metadata["evaluation_scores"] = {
                        "clarity_score": result["evaluation"].clarity_score,
                        "difficulty_score": result["evaluation"].difficulty_score,
                        "validity_score": result["evaluation"].validity_score,
                        "formatting_score": result["evaluation"].formatting_score,
                        "creativity_score": result["evaluation"].creativity_score,
                        "feedback": result["evaluation"].feedback,
                    }
                    existing_metadata["last_reevaluated"] = datetime.now(
                        timezone.utc
                    ).isoformat()

                    update_data["question_metadata"] = existing_metadata

                    # Deactivate if below threshold and flag is set
                    if args.deactivate_below_threshold and not result["approved"]:
                        update_data["is_active"] = False
                        deactivate_count += 1

                    # Perform update
                    if db_question:
                        for key, value in update_data.items():
                            setattr(db_question, key, value)
                        update_count += 1

                session.commit()
                logger.info(f"Updated {update_count} questions")

                if deactivate_count > 0:
                    logger.info(
                        f"Deactivated {deactivate_count} questions below threshold"
                    )

            except Exception as e:
                session.rollback()
                logger.error(f"Database update failed: {e}")
                return EXIT_PARTIAL_FAILURE

            finally:
                db.close_session(session)

        else:
            logger.info("\n[DRY RUN] No database updates performed")

        # Final summary
        logger.info("\n" + "=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Questions processed: {len(results)}")
        logger.info(f"Errors: {errors}")
        logger.info(f"Score changes: {len(score_increases) + len(score_decreases)}")
        logger.info(f"Difficulty changes: {len(difficulty_changes)}")
        if args.deactivate_below_threshold:
            logger.info(f"Deactivated: {len(now_below_threshold)}")

        if errors > 0:
            return EXIT_PARTIAL_FAILURE

        return EXIT_SUCCESS

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return EXIT_COMPLETE_FAILURE


if __name__ == "__main__":
    sys.exit(main())
