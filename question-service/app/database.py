"""Database operations for question storage.

This module provides functionality to insert approved questions into the
PostgreSQL database using SQLAlchemy.
"""

import enum
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    text,
)
from openai import OpenAI
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .models import EvaluatedQuestion, GeneratedQuestion

logger = logging.getLogger(__name__)

# Prompt version for tracking which prompt templates were used
PROMPT_VERSION = "2.0"  # Enhanced prompts with IQ testing context and examples

# Embedding configuration (TASK-433)
EMBEDDING_MODEL = "text-embedding-3-small"  # OpenAI model for generating embeddings
EMBEDDING_DIMENSION = 1536  # Dimension of text-embedding-3-small embeddings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


# Database models (mirror backend models)
class QuestionTypeEnum(str, enum.Enum):
    """Question type enumeration for database."""

    PATTERN = "pattern"
    LOGIC = "logic"
    SPATIAL = "spatial"
    MATH = "math"
    VERBAL = "verbal"
    MEMORY = "memory"


class DifficultyLevelEnum(str, enum.Enum):
    """Difficulty level enumeration for database."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionModel(Base):
    """SQLAlchemy model for questions table."""

    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(Enum(QuestionTypeEnum), nullable=False)
    difficulty_level = Column(Enum(DifficultyLevelEnum), nullable=False)
    correct_answer = Column(String(500), nullable=False)
    answer_options = Column(JSON)
    explanation = Column(Text)
    question_metadata = Column(
        "metadata", JSON
    )  # Maps to 'metadata' DB column (TASK-445)
    source_llm = Column(String(100))
    source_model = Column(String(100))
    arbiter_score = Column(Float)
    prompt_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    question_embedding = Column(
        ARRAY(Float), nullable=True
    )  # TASK-433: Pre-computed embedding


class DatabaseService:
    """Service for database operations related to question storage."""

    def __init__(self, database_url: str, openai_api_key: Optional[str] = None):
        """Initialize database service.

        Args:
            database_url: PostgreSQL connection URL
            openai_api_key: Optional OpenAI API key for embedding generation.
                           If not provided, embeddings will not be computed.

        Raises:
            Exception: If database connection fails
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        # Initialize OpenAI client for embedding generation (TASK-433)
        self.openai_client = None
        if openai_api_key:
            self.openai_client = OpenAI(api_key=openai_api_key)
            logger.info("DatabaseService initialized with embedding support")
        else:
            logger.warning(
                "DatabaseService initialized without OpenAI API key - "
                "embeddings will not be computed"
            )

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy session

        Yields:
            Session: Database session
        """
        session = self.SessionLocal()
        try:
            return session
        except Exception as e:
            logger.error(f"Failed to create database session: {str(e)}")
            raise

    def close_session(self, session: Session) -> None:
        """Close a database session.

        Args:
            session: Session to close
        """
        try:
            session.close()
        except Exception as e:
            logger.error(f"Error closing session: {str(e)}")

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text using OpenAI API.

        This method computes a semantic embedding for the given text using
        the text-embedding-3-small model. Embeddings are used for efficient
        semantic similarity comparison during deduplication.

        Args:
            text: Text to generate embedding for (typically question_text)

        Returns:
            List of 1536 floats representing the embedding, or None if
            OpenAI client is not configured or API call fails.

        Note:
            - Returns None gracefully on failure to allow question insertion
              to proceed without embeddings (can be backfilled later)
            - Logs errors at DEBUG level to avoid cluttering logs with
              expected failures (e.g., missing API key in dev environments)
        """
        if not self.openai_client:
            logger.debug("Skipping embedding generation - OpenAI client not configured")
            return None

        try:
            response = self.openai_client.embeddings.create(
                input=text,
                model=EMBEDDING_MODEL,
            )
            embedding = response.data[0].embedding

            # Validate embedding dimension
            if len(embedding) != EMBEDDING_DIMENSION:
                logger.warning(
                    f"Expected {EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
                )

            logger.debug(f"Generated embedding for text: {text[:50]}...")
            return embedding

        except Exception as e:
            logger.debug(f"Failed to generate embedding: {str(e)}")
            return None

    def insert_question(
        self,
        question: GeneratedQuestion,
        arbiter_score: Optional[float] = None,
    ) -> int:
        """Insert a single approved question into the database.

        Args:
            question: Generated question to insert
            arbiter_score: Optional arbiter score

        Returns:
            ID of inserted question

        Raises:
            Exception: If insertion fails
        """
        session = self.get_session()
        try:
            # Generate embedding for the question (TASK-433)
            # This is computed once at insertion time to avoid repeated API calls
            # during deduplication. Falls back to None if OpenAI client is unavailable.
            embedding = self._generate_embedding(question.question_text)

            # Create database model
            # Note: No mapping needed - QuestionType enum values now match backend directly
            db_question = QuestionModel(
                question_text=question.question_text,
                question_type=question.question_type.value,
                difficulty_level=question.difficulty_level.value,
                correct_answer=question.correct_answer,
                answer_options=question.answer_options,
                explanation=question.explanation,
                question_metadata=question.metadata,
                source_llm=question.source_llm,
                source_model=question.source_model,
                arbiter_score=arbiter_score,
                prompt_version=PROMPT_VERSION,
                is_active=True,
                question_embedding=embedding,  # TASK-433: Store pre-computed embedding
            )

            session.add(db_question)
            session.commit()
            session.refresh(db_question)

            question_id = db_question.id
            embedding_status = "with embedding" if embedding else "without embedding"
            logger.info(
                f"Inserted question with ID: {question_id} ({embedding_status})"
            )

            return question_id  # type: ignore[return-value]

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to insert question: {str(e)}")
            raise
        finally:
            self.close_session(session)

    def insert_evaluated_question(
        self,
        evaluated_question: EvaluatedQuestion,
    ) -> int:
        """Insert an evaluated question into the database.

        Args:
            evaluated_question: Evaluated question with score

        Returns:
            ID of inserted question

        Raises:
            Exception: If insertion fails
        """
        return self.insert_question(
            question=evaluated_question.question,
            arbiter_score=evaluated_question.evaluation.overall_score,
        )

    def insert_questions_batch(
        self,
        questions: List[GeneratedQuestion],
        arbiter_scores: Optional[List[float]] = None,
    ) -> List[int]:
        """Insert multiple questions in a batch.

        Args:
            questions: List of generated questions to insert
            arbiter_scores: Optional list of arbiter scores (must match length of questions)

        Returns:
            List of inserted question IDs

        Raises:
            ValueError: If arbiter_scores length doesn't match questions
            Exception: If insertion fails
        """
        if arbiter_scores and len(arbiter_scores) != len(questions):
            raise ValueError(
                f"Length of arbiter_scores ({len(arbiter_scores)}) must match "
                f"length of questions ({len(questions)})"
            )

        session = self.get_session()
        question_ids = []
        embeddings_computed = 0

        try:
            # Note: No mapping needed - QuestionType enum values now match backend directly
            for i, question in enumerate(questions):
                arbiter_score = arbiter_scores[i] if arbiter_scores else None

                # Generate embedding for each question (TASK-433)
                embedding = self._generate_embedding(question.question_text)
                if embedding:
                    embeddings_computed += 1

                db_question = QuestionModel(
                    question_text=question.question_text,
                    question_type=question.question_type.value,
                    difficulty_level=question.difficulty_level.value,
                    correct_answer=question.correct_answer,
                    answer_options=question.answer_options,
                    explanation=question.explanation,
                    question_metadata=question.metadata,
                    source_llm=question.source_llm,
                    source_model=question.source_model,
                    arbiter_score=arbiter_score,
                    prompt_version=PROMPT_VERSION,
                    is_active=True,
                    question_embedding=embedding,  # TASK-433: Store pre-computed embedding
                )

                session.add(db_question)

            session.commit()

            # Get IDs of inserted questions
            for db_question in session.new:
                if isinstance(db_question, QuestionModel):
                    question_ids.append(db_question.id)

            logger.info(
                f"Inserted {len(question_ids)} questions in batch "
                f"({embeddings_computed} with embeddings)"
            )

            return question_ids  # type: ignore[return-value]

        except Exception as e:
            session.rollback()
            logger.error(f"Failed to insert batch of questions: {str(e)}")
            raise
        finally:
            self.close_session(session)

    def insert_evaluated_questions_batch(
        self,
        evaluated_questions: List[EvaluatedQuestion],
    ) -> List[int]:
        """Insert multiple evaluated questions in a batch.

        Args:
            evaluated_questions: List of evaluated questions with scores

        Returns:
            List of inserted question IDs

        Raises:
            Exception: If insertion fails
        """
        questions = [eq.question for eq in evaluated_questions]
        scores = [eq.evaluation.overall_score for eq in evaluated_questions]

        return self.insert_questions_batch(questions=questions, arbiter_scores=scores)

    def get_all_questions(self) -> List[Dict[str, Any]]:
        """Retrieve all questions from database.

        Returns:
            List of question dictionaries including embeddings (TASK-433)

        Raises:
            Exception: If query fails
        """
        session = self.get_session()
        try:
            questions = session.query(QuestionModel).all()

            result = []
            for q in questions:
                result.append(
                    {
                        "id": q.id,
                        "question_text": q.question_text,
                        "question_type": q.question_type,
                        "difficulty_level": q.difficulty_level,
                        "correct_answer": q.correct_answer,
                        "answer_options": q.answer_options,
                        "explanation": q.explanation,
                        "metadata": q.question_metadata,  # TASK-445: Standardized key name
                        "source_llm": q.source_llm,
                        "source_model": q.source_model,
                        "arbiter_score": q.arbiter_score,
                        "prompt_version": q.prompt_version,
                        "created_at": q.created_at,
                        "is_active": q.is_active,
                        "question_embedding": q.question_embedding,  # TASK-433: Include pre-computed embedding
                    }
                )

            logger.info(f"Retrieved {len(result)} questions from database")
            return result

        except Exception as e:
            logger.error(f"Failed to retrieve questions: {str(e)}")
            raise
        finally:
            self.close_session(session)

    def get_question_count(self) -> int:
        """Get total count of questions in database.

        Returns:
            Number of questions

        Raises:
            Exception: If query fails
        """
        session = self.get_session()
        try:
            count = session.query(QuestionModel).count()
            logger.info(f"Total questions in database: {count}")
            return count

        except Exception as e:
            logger.error(f"Failed to count questions: {str(e)}")
            raise
        finally:
            self.close_session(session)

    def test_connection(self) -> bool:
        """Test database connection.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            session = self.get_session()
            session.execute(text("SELECT 1"))
            self.close_session(session)
            logger.info("Database connection test successful")
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            return False
