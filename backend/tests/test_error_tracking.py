"""
Tests for error tracking IDs in 500 responses.

These tests verify that internal server errors include a unique error_id
for tracing purposes.
"""
import re
import uuid
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_application


def remove_route(app: FastAPI, path: str) -> None:
    """Remove a route from the app by path."""
    app.router.routes = [
        r for r in app.router.routes if getattr(r, "path", None) != path
    ]


class TestErrorTracking:
    """Tests for error tracking ID functionality."""

    @pytest.fixture
    def test_app(self):
        """Create a fresh application instance for each test."""
        return create_application()

    @pytest.fixture
    def client(self, test_app):
        """Create a test client without raising server exceptions."""
        with TestClient(test_app, raise_server_exceptions=False) as test_client:
            yield test_client

    def test_500_response_includes_error_id(self, test_app, client):
        """Verify 500 responses include a unique error_id."""

        @test_app.get("/test-500-error")
        async def test_error_endpoint():
            raise RuntimeError("Test error for error_id verification")

        response = client.get("/test-500-error")

        assert response.status_code == 500
        data = response.json()
        assert "error_id" in data
        assert "detail" in data
        assert data["detail"] == "Internal server error"

        # Verify error_id is a valid UUID
        error_id = data["error_id"]
        assert error_id is not None
        # Check it's a valid UUID format
        uuid_obj = uuid.UUID(error_id)
        assert str(uuid_obj) == error_id

    def test_different_errors_get_unique_error_ids(self, test_app, client):
        """Verify each error gets a unique error_id."""
        call_count = 0

        @test_app.get("/test-unique-error-ids")
        async def test_unique_errors():
            nonlocal call_count
            call_count += 1
            raise RuntimeError(f"Test error {call_count}")

        response1 = client.get("/test-unique-error-ids")
        response2 = client.get("/test-unique-error-ids")

        assert response1.status_code == 500
        assert response2.status_code == 500

        error_id1 = response1.json()["error_id"]
        error_id2 = response2.json()["error_id"]

        # Each error should have a unique ID
        assert error_id1 != error_id2

    def test_error_id_is_logged_with_exception(self, test_app, client):
        """Verify error_id is included in log messages."""

        @test_app.get("/test-logged-error")
        async def test_logged_error():
            raise ValueError("Test error for logging")

        with patch("app.main.logger") as mock_logger:
            response = client.get("/test-logged-error")

            assert response.status_code == 500
            error_id = response.json()["error_id"]

            # Verify logger.exception was called
            mock_logger.exception.assert_called_once()

            # Get the call arguments
            call_args = mock_logger.exception.call_args

            # Check the log message contains the error_id
            log_message = call_args[0][0]
            assert f"error_id={error_id}" in log_message

            # Check extra contains error_id
            extra = call_args[1].get("extra", {})
            assert extra.get("error_id") == error_id

    def test_error_id_format_is_valid_uuid(self, test_app, client):
        """Verify error_id is a properly formatted UUID string."""

        @test_app.get("/test-uuid-format")
        async def test_uuid_format():
            raise Exception("Test exception")

        response = client.get("/test-uuid-format")
        error_id = response.json()["error_id"]

        # UUID format: 8-4-4-4-12 hex characters
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        )
        assert uuid_pattern.match(error_id), f"Invalid UUID format: {error_id}"
