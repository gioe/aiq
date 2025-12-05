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


class TestListGenerationRuns:
    """Tests for GET /v1/admin/generation-runs endpoint."""

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_empty(self, client, db_session, service_key_headers):
        """Test listing runs when no runs exist."""
        response = client.get(
            "/v1/admin/generation-runs",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["total"] == 0
        assert data["page"] == 1
        assert data["page_size"] == 20
        assert data["total_pages"] == 0

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_with_data(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test listing runs returns data correctly."""
        # Create a run first
        client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        response = client.get(
            "/v1/admin/generation-runs",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1
        assert data["total"] == 1
        assert data["total_pages"] == 1

        # Verify summary fields are present
        run = data["runs"][0]
        assert "id" in run
        assert run["status"] == "success"
        assert run["questions_requested"] == 50
        assert run["questions_inserted"] == 43
        assert run["overall_success_rate"] == 0.86
        assert run["environment"] == "production"
        assert run["triggered_by"] == "scheduler"

        # Verify JSONB fields are NOT present (summary only)
        assert "provider_metrics" not in run
        assert "type_metrics" not in run
        assert "difficulty_metrics" not in run
        assert "error_summary" not in run

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_pagination(
        self, client, db_session, service_key_headers
    ):
        """Test pagination works correctly."""
        # Create 5 runs
        for i in range(5):
            run_data = {
                "started_at": f"2024-12-05T10:0{i}:00Z",
                "status": "success",
                "questions_requested": 50 + i,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Test page 1 with page_size=2
        response = client.get(
            "/v1/admin/generation-runs?page=1&page_size=2",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 2
        assert data["total"] == 5
        assert data["page"] == 1
        assert data["page_size"] == 2
        assert data["total_pages"] == 3

        # Test page 3 with page_size=2 (should have 1 item)
        response = client.get(
            "/v1/admin/generation-runs?page=3&page_size=2",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 1
        assert data["page"] == 3

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_filter_by_status(
        self, client, db_session, service_key_headers
    ):
        """Test filtering by status."""
        # Create runs with different statuses
        for status in ["success", "failed", "partial_failure", "success"]:
            run_data = {
                "started_at": "2024-12-05T10:00:00Z",
                "status": status,
                "questions_requested": 50,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Filter by success
        response = client.get(
            "/v1/admin/generation-runs?status=success",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for run in data["runs"]:
            assert run["status"] == "success"

        # Filter by failed
        response = client.get(
            "/v1/admin/generation-runs?status=failed",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["runs"][0]["status"] == "failed"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_filter_by_environment(
        self, client, db_session, service_key_headers
    ):
        """Test filtering by environment."""
        # Create runs with different environments
        for env in ["production", "staging", "production", "development"]:
            run_data = {
                "started_at": "2024-12-05T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "environment": env,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Filter by production
        response = client.get(
            "/v1/admin/generation-runs?environment=production",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for run in data["runs"]:
            assert run["environment"] == "production"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_filter_by_date_range(
        self, client, db_session, service_key_headers
    ):
        """Test filtering by date range."""
        # Create runs on different dates
        dates = [
            "2024-12-01T10:00:00Z",
            "2024-12-03T10:00:00Z",
            "2024-12-05T10:00:00Z",
            "2024-12-07T10:00:00Z",
        ]
        for date in dates:
            run_data = {
                "started_at": date,
                "status": "success",
                "questions_requested": 50,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Filter by date range (should include Dec 3, 5)
        response = client.get(
            "/v1/admin/generation-runs?start_date=2024-12-02T00:00:00Z&end_date=2024-12-06T00:00:00Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_filter_by_success_rate(
        self, client, db_session, service_key_headers
    ):
        """Test filtering by success rate range."""
        # Create runs with different success rates
        for rate in [0.5, 0.7, 0.85, 0.95]:
            run_data = {
                "started_at": "2024-12-05T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": rate,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Filter by min success rate
        response = client.get(
            "/v1/admin/generation-runs?min_success_rate=0.8",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for run in data["runs"]:
            assert run["overall_success_rate"] >= 0.8

        # Filter by max success rate
        response = client.get(
            "/v1/admin/generation-runs?max_success_rate=0.7",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for run in data["runs"]:
            assert run["overall_success_rate"] <= 0.7

        # Filter by both min and max
        response = client.get(
            "/v1/admin/generation-runs?min_success_rate=0.6&max_success_rate=0.9",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        for run in data["runs"]:
            assert 0.6 <= run["overall_success_rate"] <= 0.9

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_sorting(
        self, client, db_session, service_key_headers
    ):
        """Test sorting by different fields."""
        # Create runs with different values
        runs_data = [
            {
                "started_at": "2024-12-01T10:00:00Z",
                "duration_seconds": 100.0,
                "overall_success_rate": 0.9,
            },
            {
                "started_at": "2024-12-03T10:00:00Z",
                "duration_seconds": 300.0,
                "overall_success_rate": 0.5,
            },
            {
                "started_at": "2024-12-02T10:00:00Z",
                "duration_seconds": 200.0,
                "overall_success_rate": 0.7,
            },
        ]
        for run_data in runs_data:
            run_data["status"] = "success"
            run_data["questions_requested"] = 50
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Sort by started_at descending (default)
        response = client.get(
            "/v1/admin/generation-runs",
            headers=service_key_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["runs"][0]["started_at"] > data["runs"][1]["started_at"]
        assert data["runs"][1]["started_at"] > data["runs"][2]["started_at"]

        # Sort by started_at ascending
        response = client.get(
            "/v1/admin/generation-runs?sort_by=started_at&sort_order=asc",
            headers=service_key_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["runs"][0]["started_at"] < data["runs"][1]["started_at"]
        assert data["runs"][1]["started_at"] < data["runs"][2]["started_at"]

        # Sort by duration_seconds descending
        response = client.get(
            "/v1/admin/generation-runs?sort_by=duration_seconds&sort_order=desc",
            headers=service_key_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["runs"][0]["duration_seconds"] == 300.0
        assert data["runs"][1]["duration_seconds"] == 200.0
        assert data["runs"][2]["duration_seconds"] == 100.0

        # Sort by overall_success_rate ascending
        response = client.get(
            "/v1/admin/generation-runs?sort_by=overall_success_rate&sort_order=asc",
            headers=service_key_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["runs"][0]["overall_success_rate"] == 0.5
        assert data["runs"][1]["overall_success_rate"] == 0.7
        assert data["runs"][2]["overall_success_rate"] == 0.9

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_combined_filters(
        self, client, db_session, service_key_headers
    ):
        """Test combining multiple filters."""
        # Create runs with various attributes
        runs_data = [
            {
                "status": "success",
                "environment": "production",
                "overall_success_rate": 0.9,
            },
            {
                "status": "success",
                "environment": "staging",
                "overall_success_rate": 0.8,
            },
            {
                "status": "failed",
                "environment": "production",
                "overall_success_rate": 0.3,
            },
            {
                "status": "success",
                "environment": "production",
                "overall_success_rate": 0.6,
            },
        ]
        for i, run_data in enumerate(runs_data):
            run_data["started_at"] = f"2024-12-0{i+1}T10:00:00Z"
            run_data["questions_requested"] = 50
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Filter: status=success, environment=production, min_success_rate=0.7
        response = client.get(
            "/v1/admin/generation-runs?status=success&environment=production&min_success_rate=0.7",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        run = data["runs"][0]
        assert run["status"] == "success"
        assert run["environment"] == "production"
        assert run["overall_success_rate"] >= 0.7

    def test_list_generation_runs_no_auth(self, client):
        """Test that request without service key is rejected."""
        response = client.get("/v1/admin/generation-runs")
        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_invalid_auth(self, client):
        """Test that request with invalid service key is rejected."""
        response = client.get(
            "/v1/admin/generation-runs",
            headers={"X-Service-Key": "wrong-key"},
        )
        assert response.status_code == 401
        assert "Invalid service API key" in response.json()["detail"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_invalid_page(self, client, service_key_headers):
        """Test validation of page parameter."""
        response = client.get(
            "/v1/admin/generation-runs?page=0",
            headers=service_key_headers,
        )
        assert response.status_code == 422  # Validation error

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_invalid_page_size(self, client, service_key_headers):
        """Test validation of page_size parameter."""
        response = client.get(
            "/v1/admin/generation-runs?page_size=101",
            headers=service_key_headers,
        )
        assert response.status_code == 422  # Validation error

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_invalid_sort_by(self, client, service_key_headers):
        """Test validation of sort_by parameter."""
        response = client.get(
            "/v1/admin/generation-runs?sort_by=invalid_field",
            headers=service_key_headers,
        )
        assert response.status_code == 422  # Validation error

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_invalid_success_rate(
        self, client, service_key_headers
    ):
        """Test validation of success rate range parameters."""
        # Invalid min_success_rate (> 1.0)
        response = client.get(
            "/v1/admin/generation-runs?min_success_rate=1.5",
            headers=service_key_headers,
        )
        assert response.status_code == 422

        # Invalid min_success_rate (< 0.0)
        response = client.get(
            "/v1/admin/generation-runs?min_success_rate=-0.1",
            headers=service_key_headers,
        )
        assert response.status_code == 422

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_list_generation_runs_page_beyond_data(
        self, client, db_session, service_key_headers
    ):
        """Test requesting a page beyond available data."""
        # Create only 2 runs
        for i in range(2):
            run_data = {
                "started_at": f"2024-12-05T10:0{i}:00Z",
                "status": "success",
                "questions_requested": 50,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        # Request page 10
        response = client.get(
            "/v1/admin/generation-runs?page=10",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["total"] == 2
        assert data["page"] == 10
        assert data["total_pages"] == 1


class TestGetGenerationRun:
    """Tests for GET /v1/admin/generation-runs/{id} endpoint."""

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_success(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test successfully retrieving a single generation run."""
        # Create a run first
        create_response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )
        assert create_response.status_code == 201
        run_id = create_response.json()["id"]

        # Retrieve the run
        response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify basic fields
        assert data["id"] == run_id
        assert data["status"] == "success"
        assert data["questions_requested"] == 50
        assert data["questions_generated"] == 48
        assert data["questions_inserted"] == 43
        assert data["overall_success_rate"] == 0.86
        assert data["environment"] == "production"
        assert data["triggered_by"] == "scheduler"

        # Verify JSONB fields are present (unlike the list endpoint)
        assert data["provider_metrics"] is not None
        assert "openai" in data["provider_metrics"]
        assert data["provider_metrics"]["openai"]["generated"] == 25
        assert data["type_metrics"] is not None
        assert "pattern_recognition" in data["type_metrics"]
        assert data["difficulty_metrics"] is not None
        assert data["error_summary"] is not None

        # Verify configuration fields
        assert data["prompt_version"] == "v2.1"
        assert data["arbiter_config_version"] == "v1.0"
        assert data["min_arbiter_score_threshold"] == 0.7

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_pipeline_losses(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test that pipeline loss metrics are computed correctly."""
        # Create a run first
        create_response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )
        run_id = create_response.json()["id"]

        # Retrieve the run
        response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify pipeline_losses field exists
        assert "pipeline_losses" in data
        losses = data["pipeline_losses"]

        # Based on valid_generation_run_data:
        # requested=50, generated=48, evaluated=48, approved=45, rejected=3
        # duplicates_found=2, inserted=43

        # generation_loss = requested - generated = 50 - 48 = 2
        assert losses["generation_loss"] == 2

        # evaluation_loss = generated - evaluated = 48 - 48 = 0
        assert losses["evaluation_loss"] == 0

        # rejection_loss = questions_rejected = 3
        assert losses["rejection_loss"] == 3

        # deduplication_loss = duplicates_found = 2
        assert losses["deduplication_loss"] == 2

        # insertion_loss = (approved - duplicates) - inserted = (45 - 2) - 43 = 0
        assert losses["insertion_loss"] == 0

        # total_loss = requested - inserted = 50 - 43 = 7
        assert losses["total_loss"] == 7

        # Check percentage values
        assert losses["generation_loss_pct"] == 4.0  # 2/50 * 100
        assert losses["evaluation_loss_pct"] == 0.0  # 0/48 * 100
        assert losses["rejection_loss_pct"] == 6.25  # 3/48 * 100
        assert losses["deduplication_loss_pct"] == 4.44  # 2/45 * 100 (rounded)
        assert losses["insertion_loss_pct"] == 0.0  # 0/43 * 100

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_pipeline_losses_with_zeros(
        self, client, db_session, service_key_headers
    ):
        """Test pipeline loss computation handles zero values correctly."""
        # Create a run with minimal data (all zeros except required fields)
        minimal_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "status": "running",
            "questions_requested": 50,
        }

        create_response = client.post(
            "/v1/admin/generation-runs",
            json=minimal_data,
            headers=service_key_headers,
        )
        run_id = create_response.json()["id"]

        # Retrieve the run
        response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        losses = data["pipeline_losses"]

        # With all zeros: generation_loss = 50 - 0 = 50
        assert losses["generation_loss"] == 50
        assert losses["total_loss"] == 50

        # Percentages should handle division by zero gracefully
        assert losses["generation_loss_pct"] == 100.0  # 50/50 * 100
        # evaluation_loss_pct should be None (generated is 0)
        assert losses["evaluation_loss_pct"] is None
        assert losses["rejection_loss_pct"] is None
        assert losses["deduplication_loss_pct"] is None
        assert losses["insertion_loss_pct"] is None

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_not_found(self, client, service_key_headers):
        """Test that 404 is returned for non-existent run."""
        response = client.get(
            "/v1/admin/generation-runs/99999",
            headers=service_key_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_get_generation_run_no_auth(self, client):
        """Test that request without service key is rejected."""
        response = client.get("/v1/admin/generation-runs/1")
        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_invalid_auth(self, client):
        """Test that request with invalid service key is rejected."""
        response = client.get(
            "/v1/admin/generation-runs/1",
            headers={"X-Service-Key": "wrong-key"},
        )
        assert response.status_code == 401
        assert "Invalid service API key" in response.json()["detail"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_all_fields_present(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test that all expected fields are present in the response."""
        # Create a run
        create_response = client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )
        run_id = create_response.json()["id"]

        # Retrieve the run
        response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check all expected fields are present
        expected_fields = [
            "id",
            "started_at",
            "completed_at",
            "duration_seconds",
            "status",
            "exit_code",
            "questions_requested",
            "questions_generated",
            "generation_failures",
            "generation_success_rate",
            "questions_evaluated",
            "questions_approved",
            "questions_rejected",
            "approval_rate",
            "avg_arbiter_score",
            "min_arbiter_score",
            "max_arbiter_score",
            "duplicates_found",
            "exact_duplicates",
            "semantic_duplicates",
            "duplicate_rate",
            "questions_inserted",
            "insertion_failures",
            "overall_success_rate",
            "total_errors",
            "total_api_calls",
            "provider_metrics",
            "type_metrics",
            "difficulty_metrics",
            "error_summary",
            "prompt_version",
            "arbiter_config_version",
            "min_arbiter_score_threshold",
            "environment",
            "triggered_by",
            "created_at",
            "pipeline_losses",
        ]

        for field in expected_fields:
            assert field in data, f"Expected field '{field}' not in response"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_failed_status(
        self, client, db_session, service_key_headers
    ):
        """Test retrieving a run with failed status."""
        failed_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "completed_at": "2024-12-05T10:01:00Z",
            "duration_seconds": 60.0,
            "status": "failed",
            "exit_code": 1,
            "questions_requested": 50,
            "questions_generated": 0,
            "total_errors": 5,
        }

        create_response = client.post(
            "/v1/admin/generation-runs",
            json=failed_data,
            headers=service_key_headers,
        )
        run_id = create_response.json()["id"]

        response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["exit_code"] == 1
        assert data["total_errors"] == 5

        # Pipeline losses should reflect complete failure
        losses = data["pipeline_losses"]
        assert losses["generation_loss"] == 50  # All requested, none generated
        assert losses["total_loss"] == 50

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_generation_run_partial_failure_status(
        self, client, db_session, service_key_headers
    ):
        """Test retrieving a run with partial_failure status."""
        partial_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "completed_at": "2024-12-05T10:05:00Z",
            "duration_seconds": 300.0,
            "status": "partial_failure",
            "exit_code": 3,
            "questions_requested": 50,
            "questions_generated": 30,
            "questions_evaluated": 30,
            "questions_approved": 25,
            "questions_rejected": 5,
            "questions_inserted": 20,
            "duplicates_found": 3,
            "total_errors": 10,
        }

        create_response = client.post(
            "/v1/admin/generation-runs",
            json=partial_data,
            headers=service_key_headers,
        )
        run_id = create_response.json()["id"]

        response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "partial_failure"

        # Verify pipeline losses for partial failure
        losses = data["pipeline_losses"]
        assert losses["generation_loss"] == 20  # 50 - 30
        assert losses["evaluation_loss"] == 0  # 30 - 30
        assert losses["rejection_loss"] == 5
        assert losses["deduplication_loss"] == 3
        # insertion_loss = (25 - 3) - 20 = 2
        assert losses["insertion_loss"] == 2
        assert losses["total_loss"] == 30  # 50 - 20
