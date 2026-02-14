"""
Tests for Prometheus metrics endpoint.
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from tests.conftest import create_test_app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(create_test_app())


def test_metrics_endpoint_disabled_by_default(client):
    """Test that metrics endpoint returns 503 when disabled."""
    # Metrics are disabled by default in test environment
    response = client.get("/v1/metrics")

    assert response.status_code == 503
    assert "not enabled" in response.text.lower()


@patch("app.core.config.settings.OTEL_ENABLED", True)
@patch("app.core.config.settings.OTEL_METRICS_ENABLED", True)
@patch("app.core.config.settings.PROMETHEUS_METRICS_ENABLED", True)
def test_metrics_endpoint_enabled(client):
    """Test that metrics endpoint returns metrics when enabled."""
    # Mock the Prometheus exporter to return sample metrics
    mock_metrics = """# HELP http_server_requests Total HTTP requests
# TYPE http_server_requests counter
http_server_requests{http_method="GET",http_route="/v1/health",http_status_code="200"} 1.0
"""

    with patch(
        "app.metrics.prometheus.get_prometheus_metrics_text"
    ) as mock_get_metrics:
        mock_get_metrics.return_value = mock_metrics

        response = client.get("/v1/metrics")

        assert response.status_code == 200
        assert (
            response.headers["content-type"]
            == "text/plain; version=0.0.4; charset=utf-8"
        )
        assert "http_server_requests" in response.text
        assert "# TYPE" in response.text
        assert "# HELP" in response.text


@patch("app.core.config.settings.OTEL_ENABLED", True)
@patch("app.core.config.settings.OTEL_METRICS_ENABLED", True)
@patch("app.core.config.settings.PROMETHEUS_METRICS_ENABLED", False)
def test_metrics_endpoint_prometheus_disabled(client):
    """Test that metrics endpoint returns 503 when only Prometheus is disabled."""
    response = client.get("/v1/metrics")

    assert response.status_code == 503
    assert "prometheus endpoint not enabled" in response.text.lower()


@patch("app.core.config.settings.OTEL_ENABLED", True)
@patch("app.core.config.settings.OTEL_METRICS_ENABLED", True)
@patch("app.core.config.settings.PROMETHEUS_METRICS_ENABLED", True)
def test_metrics_endpoint_error_handling(client):
    """Test that metrics endpoint handles errors gracefully."""
    with patch(
        "app.metrics.prometheus.get_prometheus_metrics_text"
    ) as mock_get_metrics:
        mock_get_metrics.side_effect = RuntimeError("Prometheus not initialized")

        response = client.get("/v1/metrics")

        assert response.status_code == 503
        assert "Error generating metrics" in response.text


def test_metrics_endpoint_not_in_openapi_schema(client):
    """Test that metrics endpoint is excluded from OpenAPI documentation."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    openapi_spec = response.json()
    paths = openapi_spec.get("paths", {})

    # Metrics endpoint should not appear in API docs
    assert "/v1/metrics" not in paths
    assert "/metrics" not in paths


def test_metrics_content_type_header(client):
    """Test that metrics endpoint returns correct content type."""
    response = client.get("/v1/metrics")

    # Even when disabled, should return text/plain
    assert "text/plain" in response.headers["content-type"]
    # Prometheus exposition format version
    assert "version=0.0.4" in response.headers["content-type"]


@patch("app.core.config.settings.OTEL_ENABLED", True)
@patch("app.core.config.settings.OTEL_METRICS_ENABLED", True)
@patch("app.core.config.settings.PROMETHEUS_METRICS_ENABLED", True)
def test_metrics_endpoint_includes_standard_metrics():
    """Test that standard OpenTelemetry metrics are included."""
    mock_metrics = """# HELP http_server_requests Total HTTP requests
# TYPE http_server_requests counter
http_server_requests{http_method="GET",http_route="/v1/health",http_status_code="200"} 10.0
# HELP http_server_request_duration HTTP request duration
# TYPE http_server_request_duration histogram
http_server_request_duration_bucket{http_method="GET",http_route="/v1/health",le="0.005"} 5.0
http_server_request_duration_bucket{http_method="GET",http_route="/v1/health",le="0.01"} 8.0
http_server_request_duration_bucket{http_method="GET",http_route="/v1/health",le="+Inf"} 10.0
http_server_request_duration_sum{http_method="GET",http_route="/v1/health"} 0.05
http_server_request_duration_count{http_method="GET",http_route="/v1/health"} 10.0
# HELP test_sessions_active Number of active test sessions
# TYPE test_sessions_active gauge
test_sessions_active 5.0
# HELP test_sessions_started Total test sessions started
# TYPE test_sessions_started counter
test_sessions_started{test_adaptive="false",test_question_count="25"} 100.0
"""

    with patch(
        "app.metrics.prometheus.get_prometheus_metrics_text"
    ) as mock_get_metrics:
        mock_get_metrics.return_value = mock_metrics

        client = TestClient(create_test_app())
        response = client.get("/v1/metrics")

        assert response.status_code == 200

        # Verify standard metrics are present
        assert "http_server_requests" in response.text
        assert "http_server_request_duration" in response.text

        # Verify business metrics are present
        assert "test_sessions_active" in response.text
        assert "test_sessions_started" in response.text

        # Verify Prometheus format
        assert "# HELP" in response.text
        assert "# TYPE" in response.text
        assert "counter" in response.text
        assert "histogram" in response.text
        assert "gauge" in response.text
