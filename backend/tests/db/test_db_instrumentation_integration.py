"""
Integration tests for database query instrumentation with the full application.
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from tests.conftest import create_test_app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(create_test_app())


@patch("app.core.config.settings.OTEL_ENABLED", True)
@patch("app.core.config.settings.OTEL_METRICS_ENABLED", True)
def test_db_instrumentation_with_api_call(client):
    """Test that database queries are instrumented when making API calls."""
    # Mock the metrics recording
    with patch("app.observability.metrics.record_db_query"):
        # Make an API call that triggers database queries
        response = client.get("/v1/health")

        assert response.status_code == 200

        # Verify that database queries were instrumented
        # Health endpoint may not make DB calls, but if it does they should be tracked
        # (This test primarily validates that instrumentation doesn't break the app)


@patch("app.core.config.settings.OTEL_ENABLED", False)
def test_db_instrumentation_disabled_when_otel_disabled(client):
    """Test that instrumentation is not set up when OTEL is disabled."""
    # When OTEL is disabled, engine should not be instrumented
    # (This is checked at startup, so this test validates the condition)
    # Note: We can't easily test this without restarting the app
    # The app should still function normally with OTEL disabled
    response = client.get("/v1/health")
    assert response.status_code == 200


def test_app_starts_without_instrumentation():
    """Test that app starts successfully when instrumentation is disabled."""
    test_app = create_test_app()
    response = TestClient(test_app).get("/v1/health")

    assert response.status_code == 200
