"""Pytest configuration and shared fixtures for question service tests."""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    """Set a dummy OPENAI_API_KEY when none is present so Settings() can be instantiated in unit tests without real credentials."""
    if not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = (
            "sk-dummy-key-for-unit-testing-only"  # pragma: allowlist secret
        )


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command-line options for pytest."""
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that make real API calls",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip integration tests unless --run-integration is passed."""
    if config.getoption("--run-integration"):
        # --run-integration given: do not skip integration tests
        return
    skip_integration = pytest.mark.skip(reason="need --run-integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


@pytest.fixture
def mock_openai_api_key() -> str:
    """Fixture providing a mock OpenAI API key for testing."""
    return "sk-test-mock-api-key-12345"


@pytest.fixture
def sample_prompt() -> str:
    """Fixture providing a sample prompt for testing."""
    return "Generate a pattern recognition IQ test question."


@pytest.fixture
def sample_json_schema() -> dict:
    """Fixture providing a sample JSON schema for structured responses."""
    return {
        "question_text": "string",
        "question_type": "string",
        "difficulty": "string",
        "correct_answer": "string",
        "answer_options": ["string"],
    }


@pytest.fixture
def mock_completion_response() -> str:
    """Fixture providing a mock completion response."""
    return "This is a sample IQ test question about pattern recognition."


@pytest.fixture
def mock_json_response() -> dict:
    """Fixture providing a mock JSON response."""
    return {
        "question_text": "What comes next in the sequence: 2, 4, 8, 16, ?",
        "question_type": "pattern_recognition",
        "difficulty": "medium",
        "correct_answer": "32",
        "answer_options": ["24", "30", "32", "64"],
    }


@pytest.fixture
def mock_anthropic_api_key() -> str:
    """Fixture providing a mock Anthropic API key for testing."""
    return "sk-ant-test-mock-api-key-12345"


@pytest.fixture
def mock_google_api_key() -> str:
    """Fixture providing a mock Google API key for testing."""
    return "google-test-mock-api-key-12345"


@pytest.fixture
def mock_xai_api_key() -> str:
    """Fixture providing a mock xAI API key for testing."""
    return "xai-test-mock-api-key-12345"
