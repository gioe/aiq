"""
Tests for admin API endpoints.
"""
import pytest
from unittest.mock import patch

from app.models import QuestionGenerationRun, GenerationRunStatus


@pytest.fixture
def service_key_headers():
    """
    Create service key headers for authentication.
    """
    return {"X-Service-Key": "test-service-key"}


@pytest.fixture
def valid_generation_run_data():
    """
    Create valid generation run data for testing.
    """
    return {
        "started_at": "2024-12-05T10:00:00Z",
        "completed_at": "2024-12-05T10:05:00Z",
        "duration_seconds": 300.5,
        "status": "success",
        "exit_code": 0,
        "questions_requested": 50,
        "questions_generated": 48,
        "generation_failures": 2,
        "generation_success_rate": 0.96,
        "questions_evaluated": 48,
        "questions_approved": 45,
        "questions_rejected": 3,
        "approval_rate": 0.9375,
        "avg_arbiter_score": 0.85,
        "min_arbiter_score": 0.65,
        "max_arbiter_score": 0.98,
        "duplicates_found": 2,
        "exact_duplicates": 1,
        "semantic_duplicates": 1,
        "duplicate_rate": 0.04,
        "questions_inserted": 43,
        "insertion_failures": 2,
        "overall_success_rate": 0.86,
        "total_errors": 4,
        "total_api_calls": 120,
        "provider_metrics": {
            "openai": {"generated": 25, "api_calls": 60, "failures": 1},
            "anthropic": {"generated": 23, "api_calls": 60, "failures": 1},
        },
        "type_metrics": {
            "pattern_recognition": 10,
            "logical_reasoning": 12,
            "mathematical": 8,
            "verbal_reasoning": 10,
            "spatial_reasoning": 5,
            "memory": 3,
        },
        "difficulty_metrics": {"easy": 15, "medium": 22, "hard": 11},
        "error_summary": {
            "by_category": {"rate_limit": 2, "api_error": 2},
            "by_severity": {"high": 1, "medium": 3},
            "critical_count": 0,
        },
        "prompt_version": "v2.1",
        "arbiter_config_version": "v1.0",
        "min_arbiter_score_threshold": 0.7,
        "environment": "production",
        "triggered_by": "scheduler",
    }


class TestCreateGenerationRun:
    """Tests for POST /v1/admin/generation-runs endpoint."""

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_success(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test successful creation of a generation run record."""
        response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["status"] == "success"
        assert "message" in data
        assert "recorded successfully" in data["message"]

        # Verify the record was created in the database
        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == data["id"])
            .first()
        )
        assert db_run is not None
        assert db_run.status == GenerationRunStatus.SUCCESS
        assert db_run.questions_requested == 50
        assert db_run.questions_generated == 48
        assert db_run.questions_inserted == 43
        assert db_run.overall_success_rate == 0.86
        assert db_run.environment == "production"
        assert db_run.triggered_by == "scheduler"
        assert db_run.prompt_version == "v2.1"
        assert db_run.provider_metrics is not None
        assert "openai" in db_run.provider_metrics

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_minimal_data(
        self, client, db_session, service_key_headers
    ):
        """Test creation with minimal required fields only."""
        minimal_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "status": "running",
            "questions_requested": 50,
        }

        response = client.post(
            "/v1/admin/generation-runs",
            json=minimal_data,
            headers=service_key_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "running"

        # Verify defaults were applied
        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == data["id"])
            .first()
        )
        assert db_run is not None
        assert db_run.status == GenerationRunStatus.RUNNING
        assert db_run.questions_generated == 0
        assert db_run.questions_inserted == 0
        assert db_run.total_errors == 0
        assert db_run.completed_at is None

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_failed_status(
        self, client, db_session, service_key_headers
    ):
        """Test creation with failed status."""
        failed_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "completed_at": "2024-12-05T10:01:00Z",
            "duration_seconds": 60.0,
            "status": "failed",
            "exit_code": 1,
            "questions_requested": 50,
            "questions_generated": 0,
            "total_errors": 5,
            "error_summary": {
                "by_category": {"api_error": 5},
                "critical_count": 1,
            },
        }

        response = client.post(
            "/v1/admin/generation-runs",
            json=failed_data,
            headers=service_key_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "failed"

        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == data["id"])
            .first()
        )
        assert db_run is not None
        assert db_run.status == GenerationRunStatus.FAILED
        assert db_run.exit_code == 1
        assert db_run.total_errors == 5

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_partial_failure_status(
        self, client, db_session, service_key_headers
    ):
        """Test creation with partial_failure status."""
        partial_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "completed_at": "2024-12-05T10:05:00Z",
            "duration_seconds": 300.0,
            "status": "partial_failure",
            "exit_code": 3,
            "questions_requested": 50,
            "questions_generated": 30,
            "questions_inserted": 25,
            "total_errors": 10,
        }

        response = client.post(
            "/v1/admin/generation-runs",
            json=partial_data,
            headers=service_key_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "partial_failure"

        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == data["id"])
            .first()
        )
        assert db_run is not None
        assert db_run.status == GenerationRunStatus.PARTIAL_FAILURE

    def test_create_generation_run_no_auth(self, client, valid_generation_run_data):
        """Test that request without service key is rejected."""
        response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
        )

        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_invalid_auth(
        self, client, valid_generation_run_data
    ):
        """Test that request with invalid service key is rejected."""
        response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers={"X-Service-Key": "wrong-key"},
        )

        assert response.status_code == 401
        assert "Invalid service API key" in response.json()["detail"]

    @patch("app.core.settings.SERVICE_API_KEY", "")
    def test_create_generation_run_key_not_configured(
        self, client, valid_generation_run_data, service_key_headers
    ):
        """Test error when service key is not configured on server."""
        response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_invalid_status(self, client, service_key_headers):
        """Test that invalid status value is rejected."""
        invalid_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "status": "invalid_status",
            "questions_requested": 50,
        }

        response = client.post(
            "/v1/admin/generation-runs",
            json=invalid_data,
            headers=service_key_headers,
        )

        assert response.status_code == 422  # Validation error

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_missing_required_field(
        self, client, service_key_headers
    ):
        """Test that missing required fields are rejected."""
        incomplete_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "status": "success",
            # Missing questions_requested
        }

        response = client.post(
            "/v1/admin/generation-runs",
            json=incomplete_data,
            headers=service_key_headers,
        )

        assert response.status_code == 422  # Validation error

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_jsonb_fields_stored_correctly(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test that JSONB fields are stored and retrieved correctly."""
        response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        assert response.status_code == 201
        data = response.json()

        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == data["id"])
            .first()
        )

        # Verify provider_metrics
        assert db_run.provider_metrics["openai"]["generated"] == 25
        assert db_run.provider_metrics["anthropic"]["api_calls"] == 60

        # Verify type_metrics
        assert db_run.type_metrics["pattern_recognition"] == 10
        assert db_run.type_metrics["logical_reasoning"] == 12

        # Verify difficulty_metrics
        assert db_run.difficulty_metrics["easy"] == 15
        assert db_run.difficulty_metrics["medium"] == 22
        assert db_run.difficulty_metrics["hard"] == 11

        # Verify error_summary
        assert db_run.error_summary["by_category"]["rate_limit"] == 2
        assert db_run.error_summary["critical_count"] == 0

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_create_generation_run_timestamps_stored_correctly(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test that timestamps are stored correctly."""
        response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        assert response.status_code == 201
        data = response.json()

        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == data["id"])
            .first()
        )

        assert db_run.started_at is not None
        assert db_run.completed_at is not None
        assert db_run.created_at is not None
        assert db_run.duration_seconds == 300.5
