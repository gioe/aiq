"""Database operations for question storage.

This module provides functionality to insert approved questions into the
PostgreSQL database using SQLAlchemy.
"""

import enum
import logging
import sys
from datetime import datetime
from pathlib import Path
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

from .embedding_utils import (
    DEFAULT_EMBEDDING_MODEL as EMBEDDING_MODEL,
    generate_embedding_safe,
    generate_embeddings_batch,
)
from .models import EvaluatedQuestion, GeneratedQuestion

# Import observability facade for distributed tracing
try:
    from libs.observability import observability
except ImportError:
    # Fallback for environments where libs.observability isn't installed as a package
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from libs.observability import observability  # noqa: E402

logger = logging.getLogger(__name__)

# Prompt version for tracking which prompt templates were used
# - 2.0: Enhanced prompts with IQ testing context and examples
# - 2.1: Added stimulus field for memory questions (TASK-732-736)
PROMPT_VERSION = "2.1"


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
    judge_score = Column(Float)
    prompt_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    question_embedding = Column(
        ARRAY(Float), nullable=True
    )  # TASK-433: Pre-computed embedding
    stimulus = Column(
        Text, nullable=True
    )  # TASK-727: Content to memorize (memory questions)
    sub_type = Column(
        String(200), nullable=True
    )  # Generation sub-type (e.g., "cube rotations", "cross-section")
    inferred_sub_type = Column(
        String(200), nullable=True
    )  # Inferred sub-type from LLM classification of existing questions


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

        Delegates to the shared ``generate_embedding_safe`` utility.

        Args:
            text: Text to generate embedding for (typically question_text)

        Returns:
            List of 1536 floats representing the embedding, or None if
            OpenAI client is not configured or API call fails.
        """
        return generate_embedding_safe(self.openai_client, text, EMBEDDING_MODEL)

    def insert_question(
        self,
        question: GeneratedQuestion,
        judge_score: Optional[float] = None,
    ) -> int:
        """Insert a single approved question into the database.

        Args:
            question: Generated question to insert
            judge_score: Optional judge score

        Returns:
            ID of inserted question

        Raises:
            Exception: If insertion fails
        """
        with observability.start_span(
            "database.insert_question",
            attributes={
                "question_type": question.question_type.value,
                "difficulty": question.difficulty_level.value,
            },
        ) as span:
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
                    stimulus=question.stimulus,  # TASK-727: Content to memorize
                    sub_type=question.sub_type,
                    question_metadata=question.metadata,
                    source_llm=question.source_llm,
                    source_model=question.source_model,
                    judge_score=judge_score,
                    prompt_version=PROMPT_VERSION,
                    is_active=True,
                    question_embedding=embedding,  # TASK-433: Store pre-computed embedding
                )

                session.add(db_question)
                session.commit()
                session.refresh(db_question)

                question_id = db_question.id
                embedding_status = (
                    "with embedding" if embedding else "without embedding"
                )
                span.set_attribute("success", True)
                span.set_attribute("question_id", question_id)
                logger.info(
                    f"Inserted question with ID: {question_id} ({embedding_status})"
                )

                return question_id  # type: ignore[return-value]

            except Exception as e:
                session.rollback()
                span.set_attribute("success", False)
                span.set_status("error", str(e))
                logger.error(f"Failed to insert question: {str(e)}")
                raise
            finally:
                self.close_session(session)

    def insert_evaluated_question(
        self,
        evaluated_question: EvaluatedQuestion,
    ) -> int:
        """Insert an evaluated question into the database.

        Stores individual evaluation scores in metadata to enable future
        recalculation without re-calling the judge API.

        Args:
            evaluated_question: Evaluated question with score

        Returns:
            ID of inserted question

        Raises:
            Exception: If insertion fails
        """
        with observability.start_span(
            "database.insert_evaluated_question",
            attributes={
                "question_type": evaluated_question.question.question_type.value,
                "difficulty": evaluated_question.question.difficulty_level.value,
                "approved": evaluated_question.approved,
            },
        ) as span:
            # Merge individual scores into question metadata for future recalculation
            question = evaluated_question.question
            evaluation = evaluated_question.evaluation

            enriched_metadata = {
                **(question.metadata or {}),
                "evaluation_scores": {
                    "clarity_score": evaluation.clarity_score,
                    "difficulty_score": evaluation.difficulty_score,
                    "validity_score": evaluation.validity_score,
                    "formatting_score": evaluation.formatting_score,
                    "creativity_score": evaluation.creativity_score,
                    "feedback": evaluation.feedback,
                },
                "judge_model": evaluated_question.judge_model,
            }

            # Create a new question with enriched metadata
            enriched_question = GeneratedQuestion(
                question_text=question.question_text,
                question_type=question.question_type,
                difficulty_level=question.difficulty_level,
                correct_answer=question.correct_answer,
                answer_options=question.answer_options,
                explanation=question.explanation,
                stimulus=question.stimulus,  # TASK-727: Preserve stimulus field
                sub_type=question.sub_type,
                metadata=enriched_metadata,
                source_llm=question.source_llm,
                source_model=question.source_model,
            )

            question_id = self.insert_question(
                question=enriched_question,
                judge_score=evaluation.overall_score,
            )
            span.set_attribute("question_id", question_id)
            return question_id

    def insert_questions_batch(
        self,
        questions: List[GeneratedQuestion],
        judge_scores: Optional[List[float]] = None,
    ) -> List[int]:
        """Insert multiple questions in a batch.

        Args:
            questions: List of generated questions to insert
            judge_scores: Optional list of judge scores (must match length of questions)

        Returns:
            List of inserted question IDs

        Raises:
            ValueError: If judge_scores length doesn't match questions
            Exception: If insertion fails
        """
        if judge_scores and len(judge_scores) != len(questions):
            raise ValueError(
                f"Length of judge_scores ({len(judge_scores)}) must match "
                f"length of questions ({len(questions)})"
            )

        with observability.start_span(
            "database.insert_questions_batch",
            attributes={"count": len(questions)},
        ) as span:
            session = self.get_session()
            db_questions = []
            embeddings_computed = 0

            try:
                # Generate embeddings in a single batch API call for efficiency
                embeddings: List[Optional[List[float]]] = [None] * len(questions)
                if self.openai_client:
                    try:
                        texts = [q.question_text for q in questions]
                        batch_results = generate_embeddings_batch(
                            self.openai_client, texts, EMBEDDING_MODEL
                        )
                        for i, emb in enumerate(batch_results):
                            embeddings[i] = emb.tolist()
                            embeddings_computed += 1
                    except Exception as e:
                        logger.debug(
                            f"Batch embedding generation failed, proceeding without: {e}"
                        )

                for i, question in enumerate(questions):
                    judge_score = judge_scores[i] if judge_scores else None

                    db_question = QuestionModel(
                        question_text=question.question_text,
                        question_type=question.question_type.value,
                        difficulty_level=question.difficulty_level.value,
                        correct_answer=question.correct_answer,
                        answer_options=question.answer_options,
                        explanation=question.explanation,
                        stimulus=question.stimulus,  # TASK-727: Content to memorize
                        sub_type=question.sub_type,
                        question_metadata=question.metadata,
                        source_llm=question.source_llm,
                        source_model=question.source_model,
                        judge_score=judge_score,
                        prompt_version=PROMPT_VERSION,
                        is_active=True,
                        question_embedding=embeddings[i],
                    )

                    session.add(db_question)
                    db_questions.append(db_question)

                session.commit()

                # IDs are populated by SQLAlchemy after commit
                question_ids = [q.id for q in db_questions]

                span.set_attribute("success", True)
                span.set_attribute("questions_inserted", len(question_ids))
                logger.info(
                    f"Inserted {len(question_ids)} questions in batch "
                    f"({embeddings_computed} with embeddings)"
                )

                return question_ids  # type: ignore[return-value]

            except Exception as e:
                session.rollback()
                span.set_attribute("success", False)
                span.set_status("error", str(e))
                logger.error(f"Failed to insert batch of questions: {str(e)}")
                raise
            finally:
                self.close_session(session)

    def insert_evaluated_questions_batch(
        self,
        evaluated_questions: List[EvaluatedQuestion],
    ) -> List[int]:
        """Insert multiple evaluated questions in a batch.

        Stores individual evaluation scores in metadata to enable future
        recalculation without re-calling the judge API.

        Args:
            evaluated_questions: List of evaluated questions with scores

        Returns:
            List of inserted question IDs

        Raises:
            Exception: If insertion fails
        """
        with observability.start_span(
            "database.insert_evaluated_questions_batch",
            attributes={"count": len(evaluated_questions)},
        ) as span:
            # Enrich each question with individual evaluation scores
            enriched_questions = []
            scores = []

            for eq in evaluated_questions:
                question = eq.question
                evaluation = eq.evaluation

                enriched_metadata = {
                    **(question.metadata or {}),
                    "evaluation_scores": {
                        "clarity_score": evaluation.clarity_score,
                        "difficulty_score": evaluation.difficulty_score,
                        "validity_score": evaluation.validity_score,
                        "formatting_score": evaluation.formatting_score,
                        "creativity_score": evaluation.creativity_score,
                        "feedback": evaluation.feedback,
                    },
                    "judge_model": eq.judge_model,
                }

                enriched_question = GeneratedQuestion(
                    question_text=question.question_text,
                    question_type=question.question_type,
                    difficulty_level=question.difficulty_level,
                    correct_answer=question.correct_answer,
                    answer_options=question.answer_options,
                    explanation=question.explanation,
                    stimulus=question.stimulus,  # TASK-727: Preserve stimulus field
                    sub_type=question.sub_type,
                    metadata=enriched_metadata,
                    source_llm=question.source_llm,
                    source_model=question.source_model,
                )

                enriched_questions.append(enriched_question)
                scores.append(evaluation.overall_score)

            question_ids = self.insert_questions_batch(
                questions=enriched_questions, judge_scores=scores
            )
            span.set_attribute("questions_inserted", len(question_ids))
            return question_ids

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
                        "stimulus": q.stimulus,  # TASK-727: Content to memorize
                        "sub_type": q.sub_type,
                        "inferred_sub_type": q.inferred_sub_type,
                        "metadata": q.question_metadata,  # TASK-445: Standardized key name
                        "source_llm": q.source_llm,
                        "source_model": q.source_model,
                        "judge_score": q.judge_score,
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
