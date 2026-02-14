"""
Pytest configuration and shared fixtures for testing.
"""
import sys
from pathlib import Path

# Add project root to path so libs/ is importable (matches CI PYTHONPATH config)
# This must happen before importing from app/ which may import from libs/
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from typing import AsyncGenerator, Generator, Dict, Any  # noqa: E402
from unittest.mock import patch, AsyncMock  # noqa: E402

import pytest  # noqa: E402


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that require live external services",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-integration"):
        return
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.ext.asyncio import (  # noqa: E402
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.models import (  # noqa: E402
    Base,
    get_db,
    User,
    Question,
    UserQuestion,
)
from app.models.models import QuestionType, DifficultyLevel  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from app.main import app  # noqa: E402
from app.core.auth.security import hash_password, create_access_token  # noqa: E402
from app.core.config import settings  # noqa: E402


@asynccontextmanager
async def _test_lifespan(app):
    """No-op lifespan for tests.

    Skips production observability, tracing, token blacklist, and metrics
    initialization.
    """
    yield


# Neutralize the production lifespan on the singleton app.
# Many test files import `from app.main import app` directly and wrap it
# in TestClient — this prevents the production observability stack from
# booting during those tests.
app.router.lifespan_context = _test_lifespan


def create_test_application():
    """Create the production app with the lifespan disabled.

    Use this instead of ``create_application()`` from ``app.main`` when
    tests need a fresh app instance. Returns the full app (all routes,
    middleware, exception handlers) without the production observability
    stack.

    See also: ``tests/ratelimit/conftest.py::create_test_app_with_rate_limiting``
    for tests that need an even more minimal stub app.
    """
    from app.main import create_application

    test_app = create_application()
    test_app.router.lifespan_context = _test_lifespan
    return test_app


# Use SQLite for sync tests — path is relative to this file so the .db
# lands inside tests/ regardless of the working directory.
_TEST_DB = Path(__file__).parent / "test.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{_TEST_DB}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Async test engine (aiosqlite) — uses same DB file as sync engine so that
# sync fixtures can create data visible to async endpoint overrides.
ASYNC_SQLALCHEMY_DATABASE_URL = f"sqlite+aiosqlite:///{_TEST_DB}"

async_test_engine = create_async_engine(
    ASYNC_SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
AsyncTestingSessionLocal = async_sessionmaker(
    async_test_engine, class_=AsyncSession, expire_on_commit=False
)


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

    Overrides get_db (async) to use a test async session backed by
    the same test.db file where db_session creates data.
    """

    async def override_get_db():
        async with AsyncTestingSessionLocal() as session:
            yield session

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

    db_session.commit()

    # Refresh all to get IDs
    for question in questions:
        db_session.refresh(question)

    return questions


@pytest.fixture
def admin_headers():
    """
    Create headers with valid admin token for admin endpoints.
    """
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


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


@pytest.fixture
def mock_apns_setup(
    tmp_path,
) -> Generator[Dict[str, Any], None, None]:
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


# --- Async fixtures (TASK-1161) ---


@pytest.fixture(scope="function")
async def async_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Create a fresh async database session for each test.
    """
    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncTestingSessionLocal() as session:
        yield session

    async with async_test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
async def async_client(
    async_db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """
    Create an async test client with async database dependency override.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield async_db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
async def async_test_user(async_db_session):
    """Create a test user in the async database."""
    user = User(
        email="test@example.com",
        password_hash=hash_password("testpassword123"),
        first_name="Test",
        last_name="User",
        notification_enabled=True,
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)
    return user


@pytest.fixture
def async_auth_headers(async_test_user):
    """Create authentication headers for async test user."""
    access_token = create_access_token({"user_id": async_test_user.id})
    return {"Authorization": f"Bearer {access_token}"}


@pytest.fixture
def testing_session_local():
    """Expose TestingSessionLocal for tests that need raw session access."""
    return TestingSessionLocal


@pytest.fixture
def db_engine():
    """Expose the test database engine."""
    return engine
