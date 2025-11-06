"""
Pytest configuration and shared fixtures for testing.
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.models import Base, get_db, User, Question, UserQuestion
from app.models.models import QuestionType, DifficultyLevel
from app.main import app
from app.core.security import hash_password, create_access_token

# Use SQLite in-memory database for tests
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """
    Create a fresh database session for each test.
    """
    # Create all tables
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        # Drop all tables after test
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    """
    Create a test client with database dependency override.
    """

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db_session):
    """
    Create a test user in the database.
    """
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="Test",
        last_name="User",
        notification_enabled=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user):
    """
    Create authentication headers for test user.
    """
    access_token = create_access_token({"user_id": test_user.id})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def test_questions(db_session):
    """
    Create a set of test questions in the database.
    """
    questions = [
        Question(
            question_text="What comes next in the sequence: 2, 4, 6, 8, ?",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="10",
            answer_options=["8", "10", "12", "14"],
            explanation="This is a simple arithmetic sequence increasing by 2.",
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
        ),
        Question(
            question_text="If all roses are flowers and some flowers fade quickly, "
            "can we conclude that some roses fade quickly?",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="No",
            answer_options=["Yes", "No", "Cannot be determined"],
            explanation="This is a logical fallacy - we cannot make this conclusion.",
            source_llm="test-llm",
            arbiter_score=0.92,
            is_active=True,
        ),
        Question(
            question_text="What is 15 * 12?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="180",
            answer_options=["150", "180", "200", "210"],
            explanation="15 * 12 = 180",
            source_llm="test-llm",
            arbiter_score=0.98,
            is_active=True,
        ),
        Question(
            question_text="Which word is the antonym of 'abundant'?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="scarce",
            answer_options=["plentiful", "scarce", "numerous", "ample"],
            explanation="Scarce means insufficient or in short supply.",
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
        ),
        Question(
            question_text="Inactive question - should not appear",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="N/A",
            answer_options=None,
            explanation="This is inactive",
            source_llm="test-llm",
            arbiter_score=0.50,
            is_active=False,  # This question is inactive
        ),
    ]

    for question in questions:
        db_session.add(question)

    db_session.commit()

    # Refresh all to get IDs
    for question in questions:
        db_session.refresh(question)

    return questions


@pytest.fixture
def mark_questions_seen(db_session, test_user, test_questions):
    """
    Helper fixture to mark specific questions as seen by the test user.
    Returns a function that can be called with question indices to mark as seen.
    """

    def _mark_seen(question_indices):
        for idx in question_indices:
            user_question = UserQuestion(
                user_id=test_user.id, question_id=test_questions[idx].id
            )
            db_session.add(user_question)
        db_session.commit()

    return _mark_seen
