"""
Curate and freeze a benchmark question set.

Selects ~108 questions (6 domains x 3 difficulties x 6 per cell) from
the active question pool, preferring high-discrimination items.
Creates a named benchmark set via the admin API.

Usage:
    python scripts/curate_benchmark_set.py --name "v1-standard"

Requires DATABASE_URL and ADMIN_TOKEN environment variables.
"""

import argparse
import asyncio
import os
import sys
from collections import defaultdict

from dotenv import load_dotenv

# Add backend to path for imports.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

load_dotenv()

from sqlalchemy import select, case  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.models.base import AsyncSessionLocal  # noqa: E402
from app.models.models import Question, QuestionType, DifficultyLevel  # noqa: E402
from app.models.llm_benchmark import BenchmarkSet, BenchmarkSetQuestion  # noqa: E402


# 6 per cell = 6 domains x 3 difficulties x 6 = 108 questions.
QUESTIONS_PER_CELL = 6


async def select_benchmark_questions(db: AsyncSession) -> list[int]:
    """Select balanced, high-quality questions across all domains and difficulties.

    Selection priority within each (domain, difficulty) cell:
    1. is_active = True and quality_flag = 'normal'
    2. discrimination >= 0.30 (good+) preferred
    3. Then discrimination >= 0.20 (acceptable)
    4. Fallback to any non-negative discrimination or NULL
    """
    all_types = list(QuestionType)
    all_difficulties = list(DifficultyLevel)

    selected_ids: list[int] = []
    distribution: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for qtype in all_types:
        for difficulty in all_difficulties:
            # Query best questions for this cell, ordered by discrimination.
            q = (
                select(Question.id, Question.discrimination)
                .where(
                    Question.question_type == qtype,
                    Question.difficulty_level == difficulty,
                    Question.is_active.is_(True),
                    Question.quality_flag == "normal",
                )
                .order_by(
                    # Prefer high discrimination; NULLs last.
                    case(
                        (Question.discrimination >= 0.30, 0),
                        (Question.discrimination >= 0.20, 1),
                        (Question.discrimination >= 0.0, 2),
                        (Question.discrimination.is_(None), 3),
                        else_=4,  # negative discrimination — least preferred
                    ),
                    Question.discrimination.desc().nulls_last(),
                )
                .limit(QUESTIONS_PER_CELL)
            )
            rows = (await db.execute(q)).all()
            cell_ids = [row[0] for row in rows]
            selected_ids.extend(cell_ids)

            cell_key = f"{qtype.name}/{difficulty.name}"
            distribution[qtype.name][difficulty.name] = len(cell_ids)

            if len(cell_ids) < QUESTIONS_PER_CELL:
                print(
                    f"  WARNING: {cell_key} has only {len(cell_ids)}/{QUESTIONS_PER_CELL} questions"
                )

    # Print distribution summary.
    print(f"\nSelected {len(selected_ids)} questions:")
    print(f"{'Domain':<12} {'Easy':>6} {'Medium':>8} {'Hard':>6} {'Total':>7}")
    print("-" * 42)
    for qtype in all_types:
        easy = distribution[qtype.name].get("EASY", 0)
        medium = distribution[qtype.name].get("MEDIUM", 0)
        hard = distribution[qtype.name].get("HARD", 0)
        total = easy + medium + hard
        print(f"{qtype.name:<12} {easy:>6} {medium:>8} {hard:>6} {total:>7}")
    print("-" * 42)
    print(
        f"{'Total':<12} {sum(distribution[t.name].get('EASY', 0) for t in all_types):>6} "
        f"{sum(distribution[t.name].get('MEDIUM', 0) for t in all_types):>8} "
        f"{sum(distribution[t.name].get('HARD', 0) for t in all_types):>6} "
        f"{len(selected_ids):>7}"
    )

    return selected_ids


async def create_benchmark_set(
    db: AsyncSession, name: str, description: str, question_ids: list[int]
) -> int:
    """Create the benchmark set directly in the database."""
    # Check name uniqueness.
    existing = (
        await db.execute(select(BenchmarkSet).where(BenchmarkSet.name == name))
    ).scalar_one_or_none()
    if existing:
        print(f"ERROR: Benchmark set '{name}' already exists (ID: {existing.id}).")
        sys.exit(1)

    benchmark_set = BenchmarkSet(name=name, description=description)
    db.add(benchmark_set)
    await db.flush()

    for position, qid in enumerate(question_ids):
        db.add(
            BenchmarkSetQuestion(
                benchmark_set_id=benchmark_set.id,
                question_id=qid,
                position=position,
            )
        )

    await db.commit()
    return benchmark_set.id


async def main(name: str, description: str, dry_run: bool) -> None:
    async with AsyncSessionLocal() as db:
        question_ids = await select_benchmark_questions(db)

        if not question_ids:
            print("ERROR: No questions found. Is the database populated?")
            sys.exit(1)

        # Check for duplicates (shouldn't happen, but validate).
        if len(question_ids) != len(set(question_ids)):
            print("ERROR: Duplicate question IDs detected in selection.")
            sys.exit(1)

        if dry_run:
            print(
                f"\nDry run — would create benchmark set '{name}' with {len(question_ids)} questions."
            )
            print(f"Question IDs: {question_ids[:10]}... (showing first 10)")
            return

        set_id = await create_benchmark_set(db, name, description, question_ids)
        print(
            f"\nCreated benchmark set '{name}' (ID: {set_id}) with {len(question_ids)} questions."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curate a benchmark question set.")
    parser.add_argument("--name", required=True, help="Name for the benchmark set.")
    parser.add_argument(
        "--description",
        default="Gold-standard benchmark set for standardized LLM cognitive testing.",
        help="Description for the benchmark set.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print selection without creating."
    )
    args = parser.parse_args()

    asyncio.run(main(args.name, args.description, args.dry_run))
