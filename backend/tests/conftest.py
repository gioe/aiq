"""
Pytest configuration and shared fixtures for testing.
"""
from unittest.mock import patch, AsyncMock

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from app.models import Base, get_db, User, Question, UserQuestion
from app.models.models import QuestionType, DifficultyLevel
from app.main import app
from app.core.security import hash_password, create_access_token
from app.core.config import settings

# Use async SQLite in-memory database for tests
SQLALCHEMY_DATABASE_URL = "sqlite+aiosqlite:///./test.db"

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
)
TestingSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """
    Create a fresh database session for each test.
    """
    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

    # Drop all tables after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session):
    """
    Create a test client with database dependency override.
    """

    async def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_user(db_session):
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
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user):
    """
    Create authentication headers for test user.
    """
    access_token = create_access_token({"user_id": test_user.id})
    return {"Authorization": f"Bearer {access_token}"}


@pytest_asyncio.fixture
async def test_questions(db_session):
    """
    Create a set of test questions in the database.
    """
    questions = [
        Question(
            question_text="What comes next in the sequence: 2, 4, 6, 8, ?",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="10",
            answer_options={"A": "8", "B": "10", "C": "12", "D": "14"},
            explanation="This is a simple arithmetic sequence increasing by 2.",
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
        ),
        Question(
            question_text="If all roses are flowers and some flowers fade quickly, "
            "can we conclude that some roses fade quickly?",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="No",
            answer_options={"A": "Yes", "B": "No", "C": "Cannot be determined"},
            explanation="This is a logical fallacy - we cannot make this conclusion.",
            source_llm="test-llm",
            judge_score=0.92,
            is_active=True,
        ),
        Question(
            question_text="What is 15 * 12?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="180",
            answer_options={"A": "150", "B": "180", "C": "200", "D": "210"},
            explanation="15 * 12 = 180",
            source_llm="test-llm",
            judge_score=0.98,
            is_active=True,
        ),
        Question(
            question_text="Which word is the antonym of 'abundant'?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="scarce",
            answer_options={
                "A": "plentiful",
                "B": "scarce",
                "C": "numerous",
                "D": "ample",
            },
            explanation="Scarce means insufficient or in short supply.",
            source_llm="test-llm",
            judge_score=0.90,
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
            judge_score=0.50,
            is_active=False,  # This question is inactive
        ),
    ]

    for question in questions:
        db_session.add(question)

    await db_session.commit()

    # Refresh all to get IDs
    for question in questions:
        await db_session.refresh(question)

    return questions


@pytest.fixture
def admin_headers():
    """
    Create headers with valid admin token for admin endpoints.
    """
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


@pytest_asyncio.fixture
async def mark_questions_seen(db_session, test_user, test_questions):
    """
    Helper fixture to mark specific questions as seen by the test user.
    Returns a function that can be called with question indices to mark as seen.
    """

    async def _mark_seen(question_indices):
        for idx in question_indices:
            user_question = UserQuestion(
                user_id=test_user.id, question_id=test_questions[idx].id
            )
            db_session.add(user_question)
        await db_session.commit()

    return _mark_seen


@pytest.fixture
def mock_apns_setup(tmp_path):
    """
    Shared fixture for APNs convenience function tests.

    Provides a pre-configured mock APNs environment with:
    - A temporary key file
    - Patched settings with standard test values
    - A mock APNs client instance

    Yields a dict with 'settings', 'apns_class', and 'apns_instance' keys.
    """
    key_file = tmp_path / "test_key.p8"
    key_file.write_text("fake key content")

    with patch("app.services.apns_service.settings") as mock_settings:
        mock_settings.APNS_KEY_ID = "KEY"
        mock_settings.APNS_TEAM_ID = "TEAM"
        mock_settings.APNS_BUNDLE_ID = "com.app"
        mock_settings.APNS_KEY_PATH = str(key_file)
        mock_settings.APNS_USE_SANDBOX = True

        with patch("app.services.apns_service.APNs") as mock_apns:
            mock_apns_instance = AsyncMock()
            mock_apns.return_value = mock_apns_instance

            yield {
                "settings": mock_settings,
                "apns_class": mock_apns,
                "apns_instance": mock_apns_instance,
            }
