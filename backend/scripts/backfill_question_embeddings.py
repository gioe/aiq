"""Backfill embeddings for existing questions (TASK-433).

This script populates the question_embedding column for questions that were
created before the embedding storage feature was implemented. It processes
questions in batches to avoid memory issues and API rate limits.

Usage:
    python scripts/backfill_question_embeddings.py [--batch-size BATCH_SIZE] [--dry-run]

Requirements:
    - OPENAI_API_KEY environment variable must be set
    - DATABASE_URL environment variable must be set
    - Alembic migration w0825k5ogsiy must be applied first

Safety Features:
    - Batch processing to handle large question pools
    - Dry-run mode to preview changes without modifying database
    - Progress tracking and logging
    - Graceful error handling with partial success reporting
    - Rate limit handling with exponential backoff

Performance:
    - Default batch size: 100 questions
    - Estimated time: ~1 second per question (API latency)
    - For 10,000 questions: ~3 hours at default settings
"""

import argparse
import logging
import os
import sys
import time
from typing import List, Optional

from openai import OpenAI
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.models.models import Question  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Embedding configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536
DEFAULT_BATCH_SIZE = 100

# Rate limit handling
MAX_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1.0


class EmbeddingBackfiller:
    """Service for backfilling embeddings for existing questions."""

    def __init__(
        self,
        database_url: str,
        openai_api_key: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        dry_run: bool = False,
    ):
        """Initialize the embedding backfiller.

        Args:
            database_url: PostgreSQL connection URL
            openai_api_key: OpenAI API key for generating embeddings
            batch_size: Number of questions to process in each batch
            dry_run: If True, preview changes without modifying database
        """
        self.database_url = database_url
        self.batch_size = batch_size
        self.dry_run = dry_run

        # Initialize database connection
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Initialize OpenAI client
        self.openai_client = OpenAI(api_key=openai_api_key)

        logger.info(
            f"EmbeddingBackfiller initialized (batch_size={batch_size}, dry_run={dry_run})"
        )

    def get_questions_without_embeddings(
        self, session: Session, limit: int
    ) -> List[Question]:
        """Fetch questions that don't have embeddings yet.

        Args:
            session: Database session
            limit: Maximum number of questions to fetch

        Returns:
            List of Question objects without embeddings
        """
        return (
            session.query(Question)
            .filter(Question.question_embedding.is_(None))
            .order_by(Question.id)
            .limit(limit)
            .all()
        )

    def generate_embedding(
        self, text: str, retry_count: int = 0
    ) -> Optional[List[float]]:
        """Generate embedding for text with retry logic.

        Args:
            text: Text to generate embedding for
            retry_count: Current retry attempt number

        Returns:
            List of floats representing the embedding, or None on failure
        """
        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model=EMBEDDING_MODEL,
            )
            embedding = response.data[0].embedding

            # Validate dimension
            if len(embedding) != EMBEDDING_DIMENSION:
                logger.warning(
                    f"Expected {EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
                )

            return embedding

        except Exception as e:
            error_msg = str(e)

            # Check for rate limit error
            if "rate_limit" in error_msg.lower() and retry_count < MAX_RETRIES:
                # Exponential backoff
                wait_time = INITIAL_BACKOFF_SECONDS * (2**retry_count)
                logger.warning(
                    f"Rate limit hit, retrying in {wait_time} seconds (attempt {retry_count + 1}/{MAX_RETRIES})"
                )
                time.sleep(wait_time)
                return self.generate_embedding(text, retry_count + 1)

            logger.error(f"Failed to generate embedding: {error_msg}")
            return None

    def backfill_batch(self, session: Session, questions: List[Question]) -> int:
        """Backfill embeddings for a batch of questions.

        Args:
            session: Database session
            questions: List of questions to process

        Returns:
            Number of questions successfully updated
        """
        success_count = 0

        for question in questions:
            try:
                # Generate embedding
                embedding = self.generate_embedding(question.question_text)

                if embedding is None:
                    logger.warning(
                        f"Skipping question {question.id} - embedding generation failed"
                    )
                    continue

                # Update question with embedding
                if not self.dry_run:
                    question.question_embedding = embedding
                    session.add(question)

                success_count += 1
                logger.debug(f"Updated question {question.id} with embedding")

            except Exception as e:
                logger.error(f"Failed to process question {question.id}: {str(e)}")
                continue

        # Commit batch
        if not self.dry_run:
            try:
                session.commit()
                logger.info(f"Committed batch of {success_count} questions")
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to commit batch: {str(e)}")
                return 0

        return success_count

    def run(self) -> None:
        """Run the backfill process."""
        session = self.SessionLocal()

        try:
            # Get total count of questions without embeddings
            total_count = (
                session.query(Question)
                .filter(Question.question_embedding.is_(None))
                .count()
            )

            logger.info(f"Found {total_count} questions without embeddings")

            if total_count == 0:
                logger.info("No questions need backfilling")
                return

            if self.dry_run:
                logger.info("DRY RUN MODE - No changes will be made to database")

            # Process in batches
            processed_count = 0
            success_count = 0
            batch_num = 0

            while processed_count < total_count:
                batch_num += 1
                end_question = min(processed_count + self.batch_size, total_count)
                logger.info(
                    f"Processing batch {batch_num} "
                    f"(questions {processed_count + 1}-{end_question} of {total_count})"
                )

                # Fetch batch
                questions = self.get_questions_without_embeddings(
                    session, self.batch_size
                )

                if not questions:
                    break

                # Process batch
                batch_success = self.backfill_batch(session, questions)
                success_count += batch_success
                processed_count += len(questions)

                logger.info(
                    f"Batch {batch_num} complete: {batch_success}/{len(questions)} successful"
                )

                # Add small delay between batches to avoid rate limits
                if processed_count < total_count:
                    time.sleep(1.0)

            # Summary
            logger.info("=" * 60)
            logger.info("Backfill complete!")
            logger.info(f"Total questions processed: {processed_count}")
            logger.info(f"Successfully updated: {success_count}")
            logger.info(f"Failed: {processed_count - success_count}")

            if self.dry_run:
                logger.info("DRY RUN - No changes were made to database")

        except Exception as e:
            logger.error(f"Backfill failed: {str(e)}")
            raise

        finally:
            session.close()


def main():
    """Main entry point for the backfill script."""
    parser = argparse.ArgumentParser(
        description="Backfill embeddings for existing questions"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Number of questions to process in each batch (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database",
    )

    args = parser.parse_args()

    # Validate environment variables
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL environment variable is required")
        sys.exit(1)

    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        logger.error("OPENAI_API_KEY environment variable is required")
        sys.exit(1)

    # Run backfill
    try:
        backfiller = EmbeddingBackfiller(
            database_url=database_url,
            openai_api_key=openai_api_key,
            batch_size=args.batch_size,
            dry_run=args.dry_run,
        )
        backfiller.run()

    except KeyboardInterrupt:
        logger.info("Backfill interrupted by user")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Backfill failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
