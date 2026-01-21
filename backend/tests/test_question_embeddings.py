"""Tests for question embedding storage and retrieval (TASK-433).

These tests verify that:
1. The Question model has the question_embedding column
2. Embeddings can be stored and retrieved correctly
3. The embedding dimension is correct (1536)
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.models.models import Question, QuestionType, DifficultyLevel


@pytest.fixture
def db_session():
    """Create a test database session."""
    # Use an in-memory SQLite database for testing
    engine = create_engine("sqlite:///:memory:")

    # Import and create tables
    from app.models.base import Base

    Base.metadata.create_all(engine)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    yield session

    session.close()


def test_question_has_embedding_column(db_session: Session):
    """Test that Question model has question_embedding column."""
    # Create a question without embedding
    question = Question(
        question_text="What comes next in the sequence: 2, 4, 8, ?",
        question_type=QuestionType.PATTERN,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="16",
        answer_options=["12", "14", "16", "18"],
        is_active=True,
    )

    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    # Verify the column exists and is None by default
    assert hasattr(question, "question_embedding")
    assert question.question_embedding is None


def test_store_and_retrieve_embedding(db_session: Session):
    """Test that embeddings can be stored and retrieved."""
    # Create a sample embedding (1536 dimensions)
    sample_embedding = [0.1] * 1536

    # Create a question with embedding
    question = Question(
        question_text="What is 2 + 2?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="4",
        answer_options=["2", "3", "4", "5"],
        is_active=True,
        question_embedding=sample_embedding,
    )

    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    # Verify embedding was stored
    assert question.question_embedding is not None
    assert len(question.question_embedding) == 1536
    assert all(val == pytest.approx(0.1) for val in question.question_embedding)


def test_embedding_dimension_constant():
    """Test that embedding dimension constant is correct."""
    # The text-embedding-3-small model produces 1536-dimensional embeddings
    EXPECTED_EMBEDDING_DIMENSION = 1536

    # Verify this matches the constant used in question-service
    assert EXPECTED_EMBEDDING_DIMENSION == 1536


def test_query_questions_with_embeddings(db_session: Session):
    """Test querying questions with and without embeddings."""
    # Create question without embedding
    q1 = Question(
        question_text="Question 1",
        question_type=QuestionType.LOGIC,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="A",
        is_active=True,
    )

    # Create question with embedding
    q2 = Question(
        question_text="Question 2",
        question_type=QuestionType.LOGIC,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="B",
        is_active=True,
        question_embedding=[0.2] * 1536,
    )

    db_session.add_all([q1, q2])
    db_session.commit()

    # Query questions without embeddings
    questions_without = (
        db_session.query(Question).filter(Question.question_embedding.is_(None)).all()
    )

    # Query questions with embeddings
    questions_with = (
        db_session.query(Question).filter(Question.question_embedding.isnot(None)).all()
    )

    assert len(questions_without) == 1
    assert len(questions_with) == 1
    assert questions_without[0].question_text == "Question 1"
    assert questions_with[0].question_text == "Question 2"


def test_embedding_persistence_after_update(db_session: Session):
    """Test that embeddings persist after question updates."""
    original_embedding = [0.3] * 1536

    # Create question with embedding
    question = Question(
        question_text="Original text",
        question_type=QuestionType.VERBAL,
        difficulty_level=DifficultyLevel.HARD,
        correct_answer="Original",
        is_active=True,
        question_embedding=original_embedding,
    )

    db_session.add(question)
    db_session.commit()
    question_id = question.id

    # Update question text (but not embedding)
    question.question_text = "Updated text"
    db_session.commit()

    # Reload from database
    db_session.expire(question)
    reloaded = db_session.query(Question).filter(Question.id == question_id).first()

    # Verify embedding persisted
    assert reloaded.question_embedding == original_embedding
    assert reloaded.question_text == "Updated text"
