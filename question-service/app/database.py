"""Database operations for question storage.

This module provides functionality to insert approved questions into the
PostgreSQL database using SQLAlchemy.
"""

import enum
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .models import EvaluatedQuestion, GeneratedQuestion

logger = logging.getLogger(__name__)

# Prompt version for tracking which prompt templates were used
PROMPT_VERSION = "2.0"  # Enhanced prompts with IQ testing context and examples


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
    question_metadata = Column(JSON)
    source_llm = Column(String(100))
    arbiter_score = Column(Float)
    prompt_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)


class DatabaseService:
    """Service for database operations related to question storage."""

    def __init__(self, database_url: str):
        """Initialize database service.

        Args:
            database_url: PostgreSQL connection URL

        Raises:
            Exception: If database connection fails
        """
        self.database_url = database_url
        self.engine = create_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        logger.info("DatabaseService initialized")

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
                arbiter_score=arbiter_score,
                prompt_version=PROMPT_VERSION,
                is_active=True,
            )

            session.add(db_question)
            session.commit()
            session.refresh(db_question)

            question_id = db_question.id
            logger.info(f"Inserted question with ID: {question_id}")

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

        try:
            # Note: No mapping needed - QuestionType enum values now match backend directly
            for i, question in enumerate(questions):
                arbiter_score = arbiter_scores[i] if arbiter_scores else None

                db_question = QuestionModel(
                    question_text=question.question_text,
                    question_type=question.question_type.value,
                    difficulty_level=question.difficulty_level.value,
                    correct_answer=question.correct_answer,
                    answer_options=question.answer_options,
                    explanation=question.explanation,
                    question_metadata=question.metadata,
                    source_llm=question.source_llm,
                    arbiter_score=arbiter_score,
                    prompt_version=PROMPT_VERSION,
                    is_active=True,
                )

                session.add(db_question)

            session.commit()

            # Get IDs of inserted questions
            for db_question in session.new:
                if isinstance(db_question, QuestionModel):
                    question_ids.append(db_question.id)

            logger.info(f"Inserted {len(question_ids)} questions in batch")

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
            List of question dictionaries

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
                        "question_metadata": q.question_metadata,
                        "source_llm": q.source_llm,
                        "arbiter_score": q.arbiter_score,
                        "prompt_version": q.prompt_version,
                        "created_at": q.created_at,
                        "is_active": q.is_active,
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
