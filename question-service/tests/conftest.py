"""Pytest configuration and shared fixtures for question service tests."""

import pytest


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
