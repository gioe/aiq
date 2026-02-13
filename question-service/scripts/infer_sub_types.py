#!/usr/bin/env python3
"""Infer sub-types for existing questions using LLM classification.

This script classifies existing questions (which lack sub_type) by sending
their content to an LLM and picking the best match from QUESTION_SUBTYPES.
Results are stored in the inferred_sub_type column, keeping the recorded
sub_type field clean for values assigned at generation time.

The script:
1. Fetches active questions where inferred_sub_type IS NULL
2. Groups by question_type
3. For each question, sends to the LLM with the valid subtypes list
4. Validates the response is in the known subtypes list
5. Updates inferred_sub_type in the database (skip in dry-run)
6. Prints distribution summary table

Exit Codes:
    0 - Success (all questions classified)
    1 - Partial failure (some questions failed to classify)
    2 - Complete failure (no questions classified)
    3 - Configuration error
    4 - Database connection error
"""

import argparse
import asyncio
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from openai import AsyncOpenAI  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import DatabaseService, QuestionModel  # noqa: E402
from app.logging_config import setup_logging  # noqa: E402
from app.models import QuestionType  # noqa: E402
from app.prompts import QUESTION_SUBTYPES  # noqa: E402

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_COMPLETE_FAILURE = 2
EXIT_CONFIG_ERROR = 3
EXIT_DATABASE_ERROR = 4


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Infer sub-types for existing questions using LLM classification",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry run (classify but don't update database)
  python infer_sub_types.py --dry-run --limit 10

  # Classify all questions missing inferred_sub_type
  python infer_sub_types.py

  # Classify only pattern and logic questions
  python infer_sub_types.py --types pattern logic

  # Limit to 50 questions for testing
  python infer_sub_types.py --limit 50

  # Use a specific model
  python infer_sub_types.py --model gpt-4o-mini

  # Verbose output
  python infer_sub_types.py --verbose
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Classify questions but don't update database",
    )

    parser.add_argument(
        "--types",
        nargs="+",
        choices=[qt.value for qt in QuestionType],
        default=None,
        help="Question types to classify (default: all types)",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of questions to classify (for testing)",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use for classification (default: gpt-4o-mini)",
    )

    parser.add_argument(
        "--max-concurrent",
        type=int,
        default=20,
        help="Maximum concurrent API requests (default: 20)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose (DEBUG) logging",
    )

    return parser.parse_args()


def build_classification_prompt(
    question_type: str,
    subtypes: List[str],
    question_text: str,
    answer_options: Optional[List[str]],
) -> str:
    """Build a prompt to classify a question into a sub-type.

    Args:
        question_type: The question's type category
        subtypes: Valid sub-types for this question type
        question_text: The question text
        answer_options: The answer options (if any)

    Returns:
        Classification prompt string
    """
    subtypes_list = "\n".join(f"{i+1}. {st}" for i, st in enumerate(subtypes))

    options_text = ""
    if answer_options:
        if isinstance(answer_options, dict):
            options_text = (
                f"\nAnswer options: {json.dumps(list(answer_options.values()))}"
            )
        elif isinstance(answer_options, list):
            options_text = f"\nAnswer options: {json.dumps(answer_options)}"

    return f"""Classify this IQ test question into exactly one sub-type.

Category: {question_type}
Valid sub-types:
{subtypes_list}

Question: {question_text}{options_text}

Respond with ONLY the exact sub-type string from the list above."""


async def classify_question(
    client: AsyncOpenAI,
    model: str,
    question: Dict[str, Any],
    subtypes: List[str],
    semaphore: asyncio.Semaphore,
    logger: logging.Logger,
) -> Optional[Dict[str, Any]]:
    """Classify a single question's sub-type via the LLM.

    Args:
        client: AsyncOpenAI client
        model: Model to use
        question: Question dictionary from database
        subtypes: Valid sub-types for this question type
        semaphore: Concurrency limiter
        logger: Logger instance

    Returns:
        Dict with question id and inferred sub-type, or None if failed
    """
    question_type_raw = question["question_type"]
    question_type_str = (
        question_type_raw.value
        if hasattr(question_type_raw, "value")
        else str(question_type_raw)
    )

    prompt = build_classification_prompt(
        question_type=question_type_str,
        subtypes=subtypes,
        question_text=question["question_text"],
        answer_options=question.get("answer_options"),
    )

    max_retries = 3
    async with semaphore:
        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=200,
                )

                raw_result = response.choices[0].message.content.strip()

                # Strip numbered prefix (e.g., "3. letter patterns..." -> "letter patterns...")
                result = re.sub(r"^\d+\.\s*", "", raw_result)

                # Validate the response is a known sub-type
                if result in subtypes:
                    logger.debug(f"Question {question['id']}: classified as '{result}'")
                    return {"id": question["id"], "inferred_sub_type": result}

                # Try case-insensitive match
                result_lower = result.lower()
                for st in subtypes:
                    if st.lower() == result_lower:
                        logger.debug(
                            f"Question {question['id']}: classified as '{st}' "
                            f"(case-corrected from '{result}')"
                        )
                        return {"id": question["id"], "inferred_sub_type": st}

                logger.warning(
                    f"Question {question['id']}: invalid response '{raw_result}' "
                    f"(not in known subtypes for {question_type_str})"
                )
                return None

            except Exception as e:
                error_str = str(e)
                if "rate_limit" in error_str.lower() and attempt < max_retries - 1:
                    wait = 2 ** (attempt + 1)
                    logger.debug(
                        f"Question {question['id']}: rate limited, "
                        f"retrying in {wait}s (attempt {attempt + 1}/{max_retries})"
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.error(f"Question {question['id']}: API error: {e}")
                return None


def print_distribution_table(
    results: List[Dict[str, Any]],
    questions: List[Dict[str, Any]],
    logger: logging.Logger,
) -> None:
    """Print a summary table of inferred sub-type distribution.

    Args:
        results: List of classification results
        questions: Original question list (for type lookup)
        logger: Logger instance
    """
    # Build a lookup from question id to type
    id_to_type = {}
    for q in questions:
        qt = q["question_type"]
        id_to_type[q["id"]] = qt.value if hasattr(qt, "value") else str(qt)

    # Count by type and sub-type
    distribution: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in results:
        qtype = id_to_type.get(r["id"], "unknown")
        distribution[qtype][r["inferred_sub_type"]] += 1

    logger.info("\n" + "=" * 80)
    logger.info("INFERRED SUB-TYPE DISTRIBUTION")
    logger.info("=" * 80)

    for qtype in sorted(distribution.keys()):
        subtypes = distribution[qtype]
        total = sum(subtypes.values())
        logger.info(f"\n  {qtype.upper()} ({total} questions):")
        for st, count in sorted(subtypes.items(), key=lambda x: -x[1]):
            pct = (count / total) * 100 if total > 0 else 0
            logger.info(f"    {st}: {count} ({pct:.1f}%)")


def main() -> int:
    """Main entry point for sub-type inference script."""
    args = parse_arguments()

    # Setup logging
    log_level = "DEBUG" if args.verbose else settings.log_level
    setup_logging(log_level=log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 80)
    logger.info("Sub-Type Inference Script Starting")
    logger.info(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    logger.info(f"Model: {args.model}")
    logger.info(f"Max concurrent: {args.max_concurrent}")
    logger.info(f"Filters: types={args.types or 'all'}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info("=" * 80)

    # Validate OpenAI API key
    if not settings.openai_api_key:
        logger.error("OpenAI API key is required for classification")
        return EXIT_CONFIG_ERROR

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

        # Fetch questions
        logger.info("Fetching questions from database...")
        all_questions = db.get_all_questions()
        logger.info(f"Found {len(all_questions)} total questions")

        # Filter: active only
        questions = [q for q in all_questions if q.get("is_active", True)]
        logger.info(f"Active questions: {len(questions)}")

        # Filter: only those missing inferred_sub_type
        questions = [q for q in questions if not q.get("inferred_sub_type")]
        logger.info(f"Questions without inferred_sub_type: {len(questions)}")

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

        # Apply limit
        if args.limit:
            questions = questions[: args.limit]
            logger.info(f"After limit ({args.limit}): {len(questions)}")

        if not questions:
            logger.info("No questions to classify")
            return EXIT_SUCCESS

        # Group by question type for logging
        type_counts: Dict[str, int] = defaultdict(int)
        for q in questions:
            qt = q["question_type"]
            type_counts[qt.value if hasattr(qt, "value") else str(qt)] += 1

        logger.info("\nQuestions to classify by type:")
        for qt, count in sorted(type_counts.items()):
            logger.info(f"  {qt}: {count}")

        # Run async classification
        logger.info("\n" + "=" * 80)
        logger.info("CLASSIFICATION PHASE")
        logger.info("=" * 80)

        client = AsyncOpenAI(api_key=settings.openai_api_key)
        semaphore = asyncio.Semaphore(args.max_concurrent)

        async def run_classification() -> List[Optional[Dict[str, Any]]]:
            tasks = []
            for q in questions:
                qt = q["question_type"]
                qt_str = qt.value if hasattr(qt, "value") else str(qt)

                # Look up the valid subtypes for this question type
                try:
                    qt_enum = QuestionType(qt_str)
                    subtypes = QUESTION_SUBTYPES[qt_enum]
                except (ValueError, KeyError):
                    logger.warning(
                        f"Question {q['id']}: unknown type '{qt_str}', skipping"
                    )
                    continue

                tasks.append(
                    classify_question(
                        client=client,
                        model=args.model,
                        question=q,
                        subtypes=subtypes,
                        semaphore=semaphore,
                        logger=logger,
                    )
                )

            return await asyncio.gather(*tasks)

        raw_results = asyncio.run(run_classification())

        # Separate successes and failures
        results = [r for r in raw_results if r is not None]
        errors = len(raw_results) - len(results)

        logger.info("\nClassification complete:")
        logger.info(f"  Successful: {len(results)}")
        logger.info(f"  Errors: {errors}")

        if not results:
            logger.error("No questions were successfully classified!")
            return EXIT_COMPLETE_FAILURE

        # Print distribution
        print_distribution_table(results, questions, logger)

        # Database updates
        if not args.dry_run:
            logger.info("\n" + "=" * 80)
            logger.info("DATABASE UPDATE PHASE")
            logger.info("=" * 80)

            session = db.get_session()
            update_count = 0

            try:
                for r in results:
                    db_question = (
                        session.query(QuestionModel)
                        .filter(QuestionModel.id == r["id"])
                        .first()
                    )
                    if db_question:
                        db_question.inferred_sub_type = r["inferred_sub_type"]
                        update_count += 1

                session.commit()
                logger.info(f"Updated {update_count} questions")

            except Exception as e:
                session.rollback()
                logger.error(f"Database update failed: {e}")
                return EXIT_DATABASE_ERROR
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
        logger.info(f"Dry run: {args.dry_run}")

        if errors > 0:
            return EXIT_PARTIAL_FAILURE

        return EXIT_SUCCESS

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        return EXIT_COMPLETE_FAILURE


if __name__ == "__main__":
    sys.exit(main())
