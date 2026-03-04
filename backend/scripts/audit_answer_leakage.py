"""Audit production questions for answer leakage and deactivate offenders (TASK-1352).

Detects questions where correct_answer appears verbatim (case-insensitive) in
question_text and soft-deletes them (sets is_active=False). Logs all affected
IDs before making changes and verifies pool health afterward.

Usage:
    python scripts/audit_answer_leakage.py [--dry-run]

Requirements:
    - DATABASE_URL environment variable must be set

Safety Features:
    - Dry-run mode to preview changes without modifying database
    - Logs all affected question IDs before making any changes
    - Idempotent: only targets currently-active questions; re-running finds 0
    - Verifies at least 10 active questions remain per type/difficulty bucket
"""

import argparse
import logging
import os
import sys
from collections import defaultdict
from typing import List

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.models import Question  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MIN_ACTIVE_PER_BUCKET = 10
MIN_ANSWER_LENGTH_FOR_LEAKAGE_CHECK = 5


class AnswerLeakageAuditor:
    """Detects and deactivates questions where the answer leaks into the question text."""

    def __init__(self, database_url: str, dry_run: bool = False):
        """Initialize auditor with database connection and dry-run flag."""
        self.dry_run = dry_run

        # Strip asyncpg driver prefix so sync psycopg2 is used
        sync_url = database_url
        if "+asyncpg" in sync_url:
            sync_url = sync_url.replace("+asyncpg", "")

        self.engine = create_engine(sync_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )
        logger.info(f"AnswerLeakageAuditor initialized (dry_run={dry_run})")

    def _question_type_label(self, question: Question) -> str:
        qt = question.question_type
        return qt.value if hasattr(qt, "value") else str(qt)

    def _difficulty_label(self, question: Question) -> str:
        dl = question.difficulty_level
        return dl.value if hasattr(dl, "value") else str(dl)

    def detect_leaking_questions(self, session: Session) -> List[Question]:
        """Return active questions whose correct_answer appears in question_text."""
        active_questions = (
            session.query(Question).filter(Question.is_active.is_(True)).all()
        )
        leaking = [
            q
            for q in active_questions
            if q.correct_answer
            and len(q.correct_answer) >= MIN_ANSWER_LENGTH_FOR_LEAKAGE_CHECK
            and q.correct_answer.lower() in q.question_text.lower()
        ]
        return leaking

    def verify_pool_health(self, session: Session) -> None:
        """Log warnings for any type/difficulty bucket with fewer than MIN_ACTIVE_PER_BUCKET."""
        active_questions = (
            session.query(Question).filter(Question.is_active.is_(True)).all()
        )

        bucket_counts: dict = defaultdict(int)
        for q in active_questions:
            bucket = (self._question_type_label(q), self._difficulty_label(q))
            bucket_counts[bucket] += 1

        logger.info("--- Pool health after cleanup ---")
        any_warning = False
        for (qt, dl), count in sorted(bucket_counts.items()):
            if count < MIN_ACTIVE_PER_BUCKET:
                logger.warning(
                    f"  LOW POOL: {qt}/{dl} has only {count} active questions "
                    f"(minimum recommended: {MIN_ACTIVE_PER_BUCKET})"
                )
                any_warning = True
            else:
                logger.info(f"  OK: {qt}/{dl} — {count} active questions")

        if not any_warning:
            logger.info("All type/difficulty buckets meet the minimum threshold.")

    def run(self) -> None:
        """Run the audit: detect, log, deactivate, verify."""
        session = self.SessionLocal()
        try:
            # Step 1: Detect leaking questions
            logger.info("Scanning for answer-leaking questions...")
            leaking = self.detect_leaking_questions(session)

            if not leaking:
                logger.info("No answer-leaking questions found. Pool is clean.")
                self.verify_pool_health(session)
                return

            # Step 2: Log all affected IDs before making any changes
            affected_ids = [q.id for q in leaking]
            logger.info(f"Found {len(leaking)} answer-leaking question(s)")
            logger.info(f"Affected question IDs: {affected_ids}")

            # Step 3: Log count per question_type
            by_type: dict = defaultdict(int)
            for q in leaking:
                by_type[self._question_type_label(q)] += 1

            logger.info("Breakdown by question_type:")
            for qt, count in sorted(by_type.items()):
                logger.info(f"  {qt}: {count} question(s) to deactivate")

            if self.dry_run:
                logger.info("DRY RUN — No changes were made to the database.")
                return

            # Step 4: Soft-delete (is_active=False) — NOT hard-delete
            for q in leaking:
                q.is_active = False
                session.add(q)

            session.commit()
            logger.info(
                f"Deactivated {len(leaking)} question(s) (is_active set to False)."
            )

            # Step 5: Verify pool health
            self.verify_pool_health(session)

        except Exception as e:
            session.rollback()
            logger.error(f"Audit failed: {str(e)}")
            raise

        finally:
            session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit and deactivate questions with answer leakage"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview affected questions without modifying the database",
    )
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required")
        sys.exit(1)

    try:
        auditor = AnswerLeakageAuditor(database_url=database_url, dry_run=args.dry_run)
        auditor.run()
    except KeyboardInterrupt:
        logger.info("Audit interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Audit failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
