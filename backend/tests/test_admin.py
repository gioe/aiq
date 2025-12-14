"""
Tests for admin API endpoints.
"""
import pytest
from unittest.mock import patch

from app.models import QuestionGenerationRun, GenerationRunStatus, Question
from app.models.models import QuestionType, DifficultyLevel


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


class TestGetGenerationRunStats:
    """Tests for GET /v1/admin/generation-runs/stats endpoint."""

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_empty_period(self, client, db_session, service_key_headers):
        """Test getting stats when no runs exist in the period."""
        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 0
        assert data["successful_runs"] == 0
        assert data["failed_runs"] == 0
        assert data["partial_failure_runs"] == 0
        assert data["total_questions_requested"] == 0
        assert data["total_questions_generated"] == 0
        assert data["total_questions_inserted"] == 0
        assert data["avg_overall_success_rate"] is None
        assert data["avg_approval_rate"] is None
        assert data["avg_arbiter_score"] is None
        assert data["total_api_calls"] == 0
        assert data["total_errors"] == 0
        assert data["provider_summary"] is None
        assert data["success_rate_trend"] is None
        assert data["approval_rate_trend"] is None

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_with_data(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test getting stats with run data."""
        # Create a run within the period
        client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 1
        assert data["successful_runs"] == 1
        assert data["failed_runs"] == 0
        assert data["partial_failure_runs"] == 0
        assert data["total_questions_requested"] == 50
        assert data["total_questions_generated"] == 48
        assert data["total_questions_inserted"] == 43
        assert data["avg_overall_success_rate"] == 0.86
        assert data["avg_approval_rate"] == 0.9375
        assert data["avg_arbiter_score"] == 0.85
        assert data["min_arbiter_score"] == 0.65
        assert data["max_arbiter_score"] == 0.98
        assert data["total_duplicates_found"] == 2
        assert data["avg_duplicate_rate"] == 0.04
        assert data["avg_duration_seconds"] == 300.5
        assert data["total_api_calls"] == 120
        assert data["total_errors"] == 4

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_multiple_runs(self, client, db_session, service_key_headers):
        """Test stats aggregation with multiple runs."""
        # Create runs with different statuses and values
        runs_data = [
            {
                "started_at": "2024-12-01T10:00:00Z",
                "completed_at": "2024-12-01T10:05:00Z",
                "duration_seconds": 300.0,
                "status": "success",
                "questions_requested": 50,
                "questions_generated": 48,
                "questions_inserted": 45,
                "overall_success_rate": 0.9,
                "approval_rate": 0.92,
                "avg_arbiter_score": 0.88,
                "min_arbiter_score": 0.75,
                "max_arbiter_score": 0.95,
                "duplicates_found": 3,
                "duplicate_rate": 0.06,
                "total_api_calls": 100,
                "total_errors": 2,
            },
            {
                "started_at": "2024-12-02T10:00:00Z",
                "completed_at": "2024-12-02T10:05:00Z",
                "duration_seconds": 350.0,
                "status": "success",
                "questions_requested": 50,
                "questions_generated": 45,
                "questions_inserted": 40,
                "overall_success_rate": 0.8,
                "approval_rate": 0.88,
                "avg_arbiter_score": 0.82,
                "min_arbiter_score": 0.70,
                "max_arbiter_score": 0.92,
                "duplicates_found": 2,
                "duplicate_rate": 0.04,
                "total_api_calls": 110,
                "total_errors": 3,
            },
            {
                "started_at": "2024-12-03T10:00:00Z",
                "completed_at": "2024-12-03T10:01:00Z",
                "duration_seconds": 60.0,
                "status": "failed",
                "questions_requested": 50,
                "questions_generated": 0,
                "questions_inserted": 0,
                "overall_success_rate": 0.0,
                "total_api_calls": 20,
                "total_errors": 10,
            },
            {
                "started_at": "2024-12-04T10:00:00Z",
                "completed_at": "2024-12-04T10:03:00Z",
                "duration_seconds": 180.0,
                "status": "partial_failure",
                "questions_requested": 50,
                "questions_generated": 25,
                "questions_inserted": 20,
                "overall_success_rate": 0.4,
                "approval_rate": 0.80,
                "avg_arbiter_score": 0.78,
                "min_arbiter_score": 0.65,
                "max_arbiter_score": 0.88,
                "duplicates_found": 1,
                "duplicate_rate": 0.04,
                "total_api_calls": 80,
                "total_errors": 5,
            },
        ]

        for run_data in runs_data:
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify counts
        assert data["total_runs"] == 4
        assert data["successful_runs"] == 2
        assert data["failed_runs"] == 1
        assert data["partial_failure_runs"] == 1

        # Verify totals
        assert data["total_questions_requested"] == 200  # 50 * 4
        assert data["total_questions_generated"] == 118  # 48 + 45 + 0 + 25
        assert data["total_questions_inserted"] == 105  # 45 + 40 + 0 + 20

        # Verify averages
        # avg_overall_success_rate = (0.9 + 0.8 + 0.0 + 0.4) / 4 = 0.525
        assert data["avg_overall_success_rate"] == 0.525

        # avg_approval_rate = (0.92 + 0.88 + 0.80) / 3 (only runs with approval_rate)
        expected_avg_approval = round((0.92 + 0.88 + 0.80) / 3, 4)
        assert data["avg_approval_rate"] == expected_avg_approval

        # avg_arbiter_score = (0.88 + 0.82 + 0.78) / 3
        expected_avg_arbiter = round((0.88 + 0.82 + 0.78) / 3, 4)
        assert data["avg_arbiter_score"] == expected_avg_arbiter

        # min/max arbiter scores across all runs
        assert data["min_arbiter_score"] == 0.65
        assert data["max_arbiter_score"] == 0.95

        # Verify totals
        assert data["total_duplicates_found"] == 6  # 3 + 2 + 0 + 1
        assert data["total_api_calls"] == 310  # 100 + 110 + 20 + 80
        assert data["total_errors"] == 20  # 2 + 3 + 10 + 5

        # Verify average duration
        expected_avg_duration = round((300.0 + 350.0 + 60.0 + 180.0) / 4, 2)
        assert data["avg_duration_seconds"] == expected_avg_duration

        # Verify avg_api_calls_per_question = total_api_calls / total_questions_inserted
        expected_avg_api_per_q = round(310 / 105, 2)
        assert data["avg_api_calls_per_question"] == expected_avg_api_per_q

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_provider_summary(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test that provider summary is correctly aggregated."""
        # Create two runs with provider metrics
        run1 = valid_generation_run_data.copy()
        run1["started_at"] = "2024-12-01T10:00:00Z"
        run1["provider_metrics"] = {
            "openai": {"generated": 25, "api_calls": 60, "failures": 1},
            "anthropic": {"generated": 20, "api_calls": 50, "failures": 2},
        }

        run2 = valid_generation_run_data.copy()
        run2["started_at"] = "2024-12-02T10:00:00Z"
        run2["provider_metrics"] = {
            "openai": {"generated": 30, "api_calls": 70, "failures": 0},
            "anthropic": {"generated": 15, "api_calls": 40, "failures": 3},
            "google": {"generated": 10, "api_calls": 25, "failures": 1},
        }

        client.post(
            "/v1/admin/generation-runs",
            json=run1,
            headers=service_key_headers,
        )
        client.post(
            "/v1/admin/generation-runs",
            json=run2,
            headers=service_key_headers,
        )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["provider_summary"] is not None

        # Verify OpenAI aggregation
        assert data["provider_summary"]["openai"]["total_generated"] == 55  # 25 + 30
        assert data["provider_summary"]["openai"]["total_api_calls"] == 130  # 60 + 70
        assert data["provider_summary"]["openai"]["total_failures"] == 1  # 1 + 0
        # success_rate = 55 / (55 + 1) = 0.9821
        assert data["provider_summary"]["openai"]["success_rate"] == 0.9821

        # Verify Anthropic aggregation
        assert data["provider_summary"]["anthropic"]["total_generated"] == 35  # 20 + 15
        assert data["provider_summary"]["anthropic"]["total_api_calls"] == 90  # 50 + 40
        assert data["provider_summary"]["anthropic"]["total_failures"] == 5  # 2 + 3
        # success_rate = 35 / (35 + 5) = 0.875
        assert data["provider_summary"]["anthropic"]["success_rate"] == 0.875

        # Verify Google (only in run2)
        assert data["provider_summary"]["google"]["total_generated"] == 10
        assert data["provider_summary"]["google"]["total_api_calls"] == 25
        assert data["provider_summary"]["google"]["total_failures"] == 1
        # success_rate = 10 / (10 + 1) = 0.9091
        assert data["provider_summary"]["google"]["success_rate"] == 0.9091

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_trend_improving(self, client, db_session, service_key_headers):
        """Test trend detection when metrics are improving."""
        # Create runs with improving success rates
        runs_data = [
            {
                "started_at": "2024-12-01T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.5,
                "approval_rate": 0.6,
            },
            {
                "started_at": "2024-12-02T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.55,
                "approval_rate": 0.65,
            },
            {
                "started_at": "2024-12-03T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.8,
                "approval_rate": 0.85,
            },
            {
                "started_at": "2024-12-04T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.85,
                "approval_rate": 0.9,
            },
        ]

        for run_data in runs_data:
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Older half: 0.5, 0.55 avg = 0.525
        # Recent half: 0.8, 0.85 avg = 0.825
        # Diff = 0.825 - 0.525 = 0.3 > 0.05 -> improving
        assert data["success_rate_trend"] == "improving"
        assert data["approval_rate_trend"] == "improving"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_trend_declining(self, client, db_session, service_key_headers):
        """Test trend detection when metrics are declining."""
        # Create runs with declining success rates
        runs_data = [
            {
                "started_at": "2024-12-01T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.9,
                "approval_rate": 0.92,
            },
            {
                "started_at": "2024-12-02T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.85,
                "approval_rate": 0.88,
            },
            {
                "started_at": "2024-12-03T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.6,
                "approval_rate": 0.65,
            },
            {
                "started_at": "2024-12-04T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.55,
                "approval_rate": 0.6,
            },
        ]

        for run_data in runs_data:
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Older half: 0.9, 0.85 avg = 0.875
        # Recent half: 0.6, 0.55 avg = 0.575
        # Diff = 0.575 - 0.875 = -0.3 < -0.05 -> declining
        assert data["success_rate_trend"] == "declining"
        assert data["approval_rate_trend"] == "declining"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_trend_stable(self, client, db_session, service_key_headers):
        """Test trend detection when metrics are stable."""
        # Create runs with stable success rates
        runs_data = [
            {
                "started_at": "2024-12-01T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.85,
                "approval_rate": 0.88,
            },
            {
                "started_at": "2024-12-02T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.83,
                "approval_rate": 0.86,
            },
            {
                "started_at": "2024-12-03T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.86,
                "approval_rate": 0.89,
            },
            {
                "started_at": "2024-12-04T10:00:00Z",
                "status": "success",
                "questions_requested": 50,
                "overall_success_rate": 0.84,
                "approval_rate": 0.87,
            },
        ]

        for run_data in runs_data:
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Older half: 0.85, 0.83 avg = 0.84
        # Recent half: 0.86, 0.84 avg = 0.85
        # Diff = 0.85 - 0.84 = 0.01 < 0.05 -> stable
        assert data["success_rate_trend"] == "stable"
        assert data["approval_rate_trend"] == "stable"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_environment_filter(
        self, client, db_session, service_key_headers
    ):
        """Test filtering stats by environment."""
        # Create runs in different environments
        for env, count in [("production", 3), ("staging", 2), ("development", 1)]:
            for i in range(count):
                run_data = {
                    "started_at": f"2024-12-0{i+1}T10:00:00Z",
                    "status": "success",
                    "questions_requested": 50,
                    "questions_inserted": 45 if env == "production" else 40,
                    "overall_success_rate": 0.9 if env == "production" else 0.8,
                    "environment": env,
                }
                client.post(
                    "/v1/admin/generation-runs",
                    json=run_data,
                    headers=service_key_headers,
                )

        # Get stats for production only
        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&environment=production",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 3
        assert data["total_questions_inserted"] == 135  # 45 * 3
        assert data["avg_overall_success_rate"] == 0.9

        # Get stats for staging only
        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z&environment=staging",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 2
        assert data["total_questions_inserted"] == 80  # 40 * 2
        assert data["avg_overall_success_rate"] == 0.8

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_date_range_filter(self, client, db_session, service_key_headers):
        """Test that date range correctly filters runs."""
        # Create runs on different dates
        dates = [
            "2024-11-15T10:00:00Z",  # Before range
            "2024-12-01T10:00:00Z",  # In range
            "2024-12-15T10:00:00Z",  # In range
            "2025-01-15T10:00:00Z",  # After range
        ]

        for date in dates:
            run_data = {
                "started_at": date,
                "status": "success",
                "questions_requested": 50,
                "questions_inserted": 45,
            }
            client.post(
                "/v1/admin/generation-runs",
                json=run_data,
                headers=service_key_headers,
            )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Only 2 runs should be in the range
        assert data["total_runs"] == 2
        assert data["total_questions_inserted"] == 90  # 45 * 2

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_single_run_no_trends(
        self, client, db_session, service_key_headers
    ):
        """Test that trends are None with a single run (can't compute trend)."""
        run_data = {
            "started_at": "2024-12-05T10:00:00Z",
            "status": "success",
            "questions_requested": 50,
            "overall_success_rate": 0.9,
            "approval_rate": 0.85,
        }

        client.post(
            "/v1/admin/generation-runs",
            json=run_data,
            headers=service_key_headers,
        )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_runs"] == 1
        # With only 1 run, midpoint = 0, so trends should be None
        assert data["success_rate_trend"] is None
        assert data["approval_rate_trend"] is None

    def test_get_stats_no_auth(self, client):
        """Test that request without service key is rejected."""
        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z"
        )
        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_invalid_auth(self, client):
        """Test that request with invalid service key is rejected."""
        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers={"X-Service-Key": "wrong-key"},
        )
        assert response.status_code == 401
        assert "Invalid service API key" in response.json()["detail"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_missing_required_params(self, client, service_key_headers):
        """Test that missing required parameters returns 422."""
        # Missing both dates
        response = client.get(
            "/v1/admin/generation-runs/stats",
            headers=service_key_headers,
        )
        assert response.status_code == 422

        # Missing end_date
        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z",
            headers=service_key_headers,
        )
        assert response.status_code == 422

        # Missing start_date
        response = client.get(
            "/v1/admin/generation-runs/stats?end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )
        assert response.status_code == 422

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_get_stats_all_fields_present(
        self, client, db_session, service_key_headers, valid_generation_run_data
    ):
        """Test that all expected fields are present in the response."""
        client.post(
            "/v1/admin/generation-runs",
            json=valid_generation_run_data,
            headers=service_key_headers,
        )

        response = client.get(
            "/v1/admin/generation-runs/stats?start_date=2024-12-01T00:00:00Z&end_date=2024-12-31T23:59:59Z",
            headers=service_key_headers,
        )

        assert response.status_code == 200
        data = response.json()

        expected_fields = [
            "period_start",
            "period_end",
            "total_runs",
            "successful_runs",
            "failed_runs",
            "partial_failure_runs",
            "total_questions_requested",
            "total_questions_generated",
            "total_questions_inserted",
            "avg_overall_success_rate",
            "avg_approval_rate",
            "avg_arbiter_score",
            "min_arbiter_score",
            "max_arbiter_score",
            "total_duplicates_found",
            "avg_duplicate_rate",
            "avg_duration_seconds",
            "total_api_calls",
            "avg_api_calls_per_question",
            "total_errors",
            "provider_summary",
            "success_rate_trend",
            "approval_rate_trend",
        ]

        for field in expected_fields:
            assert field in data, f"Expected field '{field}' not in response"


# =============================================================================
# CALIBRATION HEALTH ENDPOINT TESTS (EIC-005)
# =============================================================================


@pytest.fixture
def admin_token_headers():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


@pytest.fixture
def calibration_test_questions(db_session):
    """
    Create questions with various empirical difficulty levels for testing
    calibration health endpoint.
    """
    questions = [
        # Correctly calibrated easy question (p-value in 0.70-0.90 range)
        Question(
            question_text="Easy question 1",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
            response_count=150,
            empirical_difficulty=0.80,  # Within easy range (0.70-0.90)
        ),
        # Correctly calibrated medium question (p-value in 0.40-0.70 range)
        Question(
            question_text="Medium question 1",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.85,
            is_active=True,
            response_count=120,
            empirical_difficulty=0.55,  # Within medium range (0.40-0.70)
        ),
        # Correctly calibrated hard question (p-value in 0.15-0.40 range)
        Question(
            question_text="Hard question 1",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="C",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.88,
            is_active=True,
            response_count=100,
            empirical_difficulty=0.25,  # Within hard range (0.15-0.40)
        ),
        # Miscalibrated: labeled HARD but actually easy (severe miscalibration)
        Question(
            question_text="Miscalibrated severe",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="D",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.92,
            is_active=True,
            response_count=200,
            empirical_difficulty=0.85,  # Should be "easy" - severe deviation
        ),
        # Miscalibrated: labeled EASY but actually hard (major miscalibration)
        Question(
            question_text="Miscalibrated major",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.85,
            is_active=True,
            response_count=150,
            empirical_difficulty=0.45,  # Should be "medium" - major deviation
        ),
        # Miscalibrated: labeled MEDIUM but slightly outside range (minor)
        Question(
            question_text="Miscalibrated minor",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.80,
            is_active=True,
            response_count=110,
            empirical_difficulty=0.75,  # Just outside medium upper bound (0.70)
        ),
        # Insufficient data - below min_responses threshold
        Question(
            question_text="Insufficient data",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="C",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.75,
            is_active=True,
            response_count=50,  # Below default 100 threshold
            empirical_difficulty=0.30,
        ),
        # Inactive question - should not be counted
        Question(
            question_text="Inactive question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="D",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.70,
            is_active=False,
            response_count=200,
            empirical_difficulty=0.10,
        ),
    ]

    for q in questions:
        db_session.add(q)
    db_session.commit()

    for q in questions:
        db_session.refresh(q)

    return questions


class TestCalibrationHealth:
    """Tests for GET /v1/admin/questions/calibration-health endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_success(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test successful retrieval of calibration health."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "summary" in data
        assert "by_severity" in data
        assert "by_difficulty" in data
        assert "worst_offenders" in data

        # Verify summary (3 calibrated, 3 miscalibrated based on fixtures)
        assert data["summary"]["correctly_calibrated"] == 3
        assert data["summary"]["miscalibrated"] == 3
        assert data["summary"]["total_questions_with_data"] == 6

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_severity_breakdown(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test severity breakdown is correctly calculated."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Based on fixtures:
        # - severe: 1 (hard labeled but 0.85 p-value)
        # - major: 1 (easy labeled but 0.45 p-value)
        # - minor: 1 (medium labeled but 0.75 p-value)
        assert data["by_severity"]["severe"] == 1
        assert data["by_severity"]["major"] == 1
        assert data["by_severity"]["minor"] == 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_difficulty_breakdown(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test difficulty breakdown is correctly calculated."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Based on fixtures:
        # Easy: 1 calibrated (0.80), 1 miscalibrated (0.45)
        # Medium: 1 calibrated (0.55), 1 miscalibrated (0.75)
        # Hard: 1 calibrated (0.25), 1 miscalibrated (0.85)
        assert data["by_difficulty"]["easy"]["calibrated"] == 1
        assert data["by_difficulty"]["easy"]["miscalibrated"] == 1
        assert data["by_difficulty"]["medium"]["calibrated"] == 1
        assert data["by_difficulty"]["medium"]["miscalibrated"] == 1
        assert data["by_difficulty"]["hard"]["calibrated"] == 1
        assert data["by_difficulty"]["hard"]["miscalibrated"] == 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_worst_offenders(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test worst offenders are correctly identified and sorted."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have 3 worst offenders (all miscalibrated)
        assert len(data["worst_offenders"]) == 3

        # First should be most severe (hard labeled, 0.85 p-value)
        first = data["worst_offenders"][0]
        assert first["severity"] == "severe"
        assert first["assigned_difficulty"] == "hard"
        assert first["suggested_label"] == "easy"
        assert first["empirical_difficulty"] == 0.85

        # Verify structure of worst offenders
        for offender in data["worst_offenders"]:
            assert "question_id" in offender
            assert "assigned_difficulty" in offender
            assert "empirical_difficulty" in offender
            assert "expected_range" in offender
            assert "suggested_label" in offender
            assert "response_count" in offender
            assert "severity" in offender

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_custom_min_responses(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test that min_responses parameter works correctly."""
        # With min_responses=50, should include the "insufficient data" question
        response = client.get(
            "/v1/admin/questions/calibration-health?min_responses=50",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Now should have 7 questions with data (including the 50-response one)
        assert data["summary"]["total_questions_with_data"] == 7

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_empty_database(
        self, client, db_session, admin_token_headers
    ):
        """Test calibration health with no questions."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return zeros/empty
        assert data["summary"]["total_questions_with_data"] == 0
        assert data["summary"]["correctly_calibrated"] == 0
        assert data["summary"]["miscalibrated"] == 0
        assert data["summary"]["miscalibration_rate"] == 0.0
        assert data["worst_offenders"] == []

    def test_calibration_health_no_auth(self, client):
        """Test that request without admin token is rejected."""
        response = client.get("/v1/admin/questions/calibration-health")
        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_invalid_auth(self, client):
        """Test that request with invalid admin token is rejected."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "")
    def test_calibration_health_token_not_configured(self, client, admin_token_headers):
        """Test error when admin token is not configured on server."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )
        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_invalid_min_responses(
        self, client, admin_token_headers
    ):
        """Test validation of min_responses parameter."""
        # Below minimum (1)
        response = client.get(
            "/v1/admin/questions/calibration-health?min_responses=0",
            headers=admin_token_headers,
        )
        assert response.status_code == 422

        # Above maximum (1000)
        response = client.get(
            "/v1/admin/questions/calibration-health?min_responses=1001",
            headers=admin_token_headers,
        )
        assert response.status_code == 422

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_miscalibration_rate(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test that miscalibration rate is correctly calculated."""
        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # 3 miscalibrated / 6 total = 0.5
        assert data["summary"]["miscalibration_rate"] == 0.5

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_calibration_health_all_calibrated(
        self, client, db_session, admin_token_headers
    ):
        """Test when all questions are correctly calibrated."""
        # Create only correctly calibrated questions
        for i, (difficulty, p_value) in enumerate(
            [
                (DifficultyLevel.EASY, 0.80),
                (DifficultyLevel.MEDIUM, 0.55),
                (DifficultyLevel.HARD, 0.25),
            ]
        ):
            q = Question(
                question_text=f"Calibrated question {i}",
                question_type=QuestionType.MATH,
                difficulty_level=difficulty,
                correct_answer="A",
                answer_options={"A": "1", "B": "2"},
                source_llm="test-llm",
                arbiter_score=0.90,
                is_active=True,
                response_count=150,
                empirical_difficulty=p_value,
            )
            db_session.add(q)
        db_session.commit()

        response = client.get(
            "/v1/admin/questions/calibration-health",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["summary"]["correctly_calibrated"] == 3
        assert data["summary"]["miscalibrated"] == 0
        assert data["summary"]["miscalibration_rate"] == 0.0
        assert data["worst_offenders"] == []


class TestRecalibrateQuestions:
    """Tests for POST /v1/admin/questions/recalibrate endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_dry_run_success(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test dry run recalibration returns preview without changes."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "major",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "recalibrated" in data
        assert "skipped" in data
        assert "total_recalibrated" in data
        assert "dry_run" in data

        # Dry run should be True
        assert data["dry_run"] is True

        # Should find miscalibrated questions at major+ severity
        # From fixture: severe (0.85 labeled hard) and major (0.45 labeled easy)
        assert data["total_recalibrated"] == 2

        # Verify the recalibrated questions
        recalibrated_ids = [q["question_id"] for q in data["recalibrated"]]
        assert len(recalibrated_ids) == 2

        # Check a specific recalibration (severe case: hard -> easy)
        severe_q = next(
            (q for q in data["recalibrated"] if q["severity"] == "severe"),
            None,
        )
        assert severe_q is not None
        assert severe_q["old_label"] == "hard"
        assert severe_q["new_label"] == "easy"
        assert severe_q["empirical_difficulty"] == 0.85

        # Verify database NOT changed (dry run)
        for q in calibration_test_questions:
            db_session.refresh(q)
        # Find the severe miscalibrated question
        severe_question = next(
            (
                q
                for q in calibration_test_questions
                if q.question_text == "Miscalibrated severe"
            ),
            None,
        )
        assert severe_question is not None
        assert severe_question.difficulty_level == DifficultyLevel.HARD  # Unchanged

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_commit_success(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test actual recalibration with dry_run=false commits changes."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": False,
                "min_responses": 100,
                "severity_threshold": "major",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Dry run should be False
        assert data["dry_run"] is False

        # Should recalibrate major+ severity questions
        assert data["total_recalibrated"] == 2

        # Verify database WAS changed
        for q in calibration_test_questions:
            db_session.refresh(q)

        # Find the severe miscalibrated question
        severe_question = next(
            (
                q
                for q in calibration_test_questions
                if q.question_text == "Miscalibrated severe"
            ),
            None,
        )
        assert severe_question is not None
        assert severe_question.difficulty_level == DifficultyLevel.EASY  # Changed!
        assert (
            severe_question.original_difficulty_level == DifficultyLevel.HARD
        )  # Preserved
        assert severe_question.difficulty_recalibrated_at is not None

        # Find the major miscalibrated question
        major_question = next(
            (
                q
                for q in calibration_test_questions
                if q.question_text == "Miscalibrated major"
            ),
            None,
        )
        assert major_question is not None
        assert major_question.difficulty_level == DifficultyLevel.MEDIUM  # Changed!
        assert (
            major_question.original_difficulty_level == DifficultyLevel.EASY
        )  # Preserved

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_severity_threshold_minor(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test recalibration with minor threshold includes more questions."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "minor",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should include all miscalibrated: severe, major, minor
        assert data["total_recalibrated"] == 3

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_severity_threshold_severe(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test recalibration with severe threshold only includes severe."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "severe",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include severe miscalibration
        assert data["total_recalibrated"] == 1
        assert data["recalibrated"][0]["severity"] == "severe"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_specific_question_ids(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test recalibration limited to specific question IDs."""
        # Get the ID of the severe miscalibrated question
        severe_question = next(
            (
                q
                for q in calibration_test_questions
                if q.question_text == "Miscalibrated severe"
            ),
            None,
        )

        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "major",
                "question_ids": [severe_question.id],
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only recalibrate the specified question
        assert data["total_recalibrated"] == 1
        assert data["recalibrated"][0]["question_id"] == severe_question.id

        # The other major question should be skipped
        skipped_not_in_ids = [
            q for q in data["skipped"] if q["reason"] == "not_in_question_ids"
        ]
        assert len(skipped_not_in_ids) >= 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_min_responses_filter(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test recalibration respects min_responses threshold."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 150,  # Higher threshold
                "severity_threshold": "major",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # The minor miscalibrated (110 responses) should be insufficient data
        # Only severe (200) and major (150) should qualify
        # Major is exactly at threshold, should be included
        assert data["total_recalibrated"] == 2

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_skipped_reasons(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test that skipped questions have correct reasons."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "major",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check various skip reasons
        skip_reasons = {q["reason"] for q in data["skipped"]}

        # Minor miscalibrated should be skipped due to below_threshold
        assert "below_threshold" in skip_reasons

        # Correctly calibrated should be skipped
        assert "correctly_calibrated" in skip_reasons

        # Insufficient data should be skipped
        assert "insufficient_data" in skip_reasons

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_empty_database(self, client, db_session, admin_token_headers):
        """Test recalibration with no questions."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "major",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_recalibrated"] == 0
        assert data["recalibrated"] == []
        assert data["skipped"] == []

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_all_calibrated(self, client, db_session, admin_token_headers):
        """Test recalibration when all questions are correctly calibrated."""
        # Create only correctly calibrated questions
        for i, (difficulty, p_value) in enumerate(
            [
                (DifficultyLevel.EASY, 0.80),
                (DifficultyLevel.MEDIUM, 0.55),
                (DifficultyLevel.HARD, 0.25),
            ]
        ):
            q = Question(
                question_text=f"Calibrated question {i}",
                question_type=QuestionType.MATH,
                difficulty_level=difficulty,
                correct_answer="A",
                answer_options={"A": "1", "B": "2"},
                source_llm="test-llm",
                arbiter_score=0.90,
                is_active=True,
                response_count=150,
                empirical_difficulty=p_value,
            )
            db_session.add(q)
        db_session.commit()

        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "minor",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["total_recalibrated"] == 0
        assert data["recalibrated"] == []
        # All questions should be skipped as correctly_calibrated
        assert len(data["skipped"]) == 3
        assert all(q["reason"] == "correctly_calibrated" for q in data["skipped"])

    def test_recalibrate_no_auth(self, client):
        """Test that request without admin token is rejected."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={"dry_run": True},
        )
        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_invalid_auth(self, client):
        """Test that request with invalid admin token is rejected."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={"dry_run": True},
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "")
    def test_recalibrate_token_not_configured(self, client, admin_token_headers):
        """Test error when admin token is not configured on server."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={"dry_run": True},
            headers=admin_token_headers,
        )
        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_invalid_min_responses(self, client, admin_token_headers):
        """Test validation of min_responses parameter."""
        # Below minimum (1)
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={"dry_run": True, "min_responses": 0},
            headers=admin_token_headers,
        )
        assert response.status_code == 422

        # Above maximum (1000)
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={"dry_run": True, "min_responses": 1001},
            headers=admin_token_headers,
        )
        assert response.status_code == 422

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_invalid_severity_threshold(self, client, admin_token_headers):
        """Test validation of severity_threshold parameter."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={"dry_run": True, "severity_threshold": "invalid"},
            headers=admin_token_headers,
        )
        assert response.status_code == 422

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_default_values(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test that default values work correctly."""
        # Send minimal request (defaults should apply)
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={},  # Use all defaults
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Defaults: dry_run=True, min_responses=100, severity_threshold=major
        assert data["dry_run"] is True
        # Should include major+ (not minor)
        assert data["total_recalibrated"] == 2

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_preserves_original_difficulty(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test that original difficulty is preserved on first recalibration."""
        # Get the severe miscalibrated question
        severe_question = next(
            (
                q
                for q in calibration_test_questions
                if q.question_text == "Miscalibrated severe"
            ),
            None,
        )
        assert severe_question.original_difficulty_level is None  # Not set yet

        # Perform actual recalibration
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": False,
                "min_responses": 100,
                "severity_threshold": "severe",
                "question_ids": [severe_question.id],
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200

        # Refresh and verify
        db_session.refresh(severe_question)
        assert severe_question.original_difficulty_level == DifficultyLevel.HARD
        assert severe_question.difficulty_level == DifficultyLevel.EASY
        assert severe_question.difficulty_recalibrated_at is not None

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_recalibrate_response_format(
        self, client, db_session, admin_token_headers, calibration_test_questions
    ):
        """Test that response format matches schema exactly."""
        response = client.post(
            "/v1/admin/questions/recalibrate",
            json={
                "dry_run": True,
                "min_responses": 100,
                "severity_threshold": "severe",
            },
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify recalibrated question structure
        assert len(data["recalibrated"]) == 1
        recal_q = data["recalibrated"][0]
        assert "question_id" in recal_q
        assert "old_label" in recal_q
        assert "new_label" in recal_q
        assert "empirical_difficulty" in recal_q
        assert "response_count" in recal_q
        assert "severity" in recal_q
        assert recal_q["severity"] == "severe"

        # Verify skipped question structure
        assert len(data["skipped"]) > 0
        skip_q = data["skipped"][0]
        assert "question_id" in skip_q
        assert "reason" in skip_q
        assert "assigned_difficulty" in skip_q
        assert "severity" in skip_q or skip_q.get("severity") is None


# =============================================================================
# DISTRACTOR ANALYSIS ENDPOINT TESTS (DA-008)
# =============================================================================


@pytest.fixture
def distractor_analysis_question(db_session):
    """Create a question with distractor stats for testing."""
    from app.models.models import Question, QuestionType, DifficultyLevel

    question = Question(
        question_text="What is the next number in the sequence: 2, 4, 8, 16, ?",
        question_type=QuestionType.PATTERN,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="B",
        answer_options={
            "A": "24",
            "B": "32",
            "C": "20",
            "D": "64",
        },
        distractor_stats={
            "A": {"count": 25, "top_q": 5, "bottom_q": 15},  # functioning, good disc.
            "B": {"count": 150, "top_q": 50, "bottom_q": 20},  # correct answer
            "C": {"count": 3, "top_q": 1, "bottom_q": 1},  # non-functioning
            "D": {"count": 22, "top_q": 14, "bottom_q": 4},  # inverted discrimination
        },
        is_active=True,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


@pytest.fixture
def distractor_insufficient_data_question(db_session):
    """Create a question with insufficient distractor stats for testing."""
    from app.models.models import Question, QuestionType, DifficultyLevel

    question = Question(
        question_text="Which pattern comes next?",
        question_type=QuestionType.PATTERN,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="A",
        answer_options={
            "A": "Square",
            "B": "Circle",
            "C": "Triangle",
            "D": "Hexagon",
        },
        distractor_stats={
            "A": {"count": 10, "top_q": 2, "bottom_q": 3},
            "B": {"count": 5, "top_q": 1, "bottom_q": 2},
        },
        is_active=True,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


@pytest.fixture
def free_response_question(db_session):
    """Create a free-response question (no answer_options) for testing."""
    from app.models.models import Question, QuestionType, DifficultyLevel

    question = Question(
        question_text="Describe the pattern you see.",
        question_type=QuestionType.VERBAL,
        difficulty_level=DifficultyLevel.HARD,
        correct_answer="The pattern shows increasing complexity",
        answer_options=None,  # Free-response question
        is_active=True,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    return question


class TestDistractorAnalysisEndpoint:
    """Tests for GET /v1/admin/questions/{id}/distractor-analysis endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_success(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test successful distractor analysis with full data."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify basic structure
        assert data["question_id"] == distractor_analysis_question.id
        assert "What is the next number" in data["question_text"]
        assert data["total_responses"] == 200  # 25 + 150 + 3 + 22
        assert data["correct_answer"] == "B"

        # Verify options are present
        assert len(data["options"]) == 4

        # Verify summary structure
        assert "summary" in data
        summary = data["summary"]
        assert "functioning_distractors" in summary
        assert "weak_distractors" in summary
        assert "non_functioning_distractors" in summary
        assert "inverted_distractors" in summary
        assert "effective_option_count" in summary
        assert "guessing_probability" in summary

        # Verify recommendations are present (should have some for non-functioning distractor)
        assert "recommendations" in data
        assert isinstance(data["recommendations"], list)

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_options_detail(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that option analysis contains correct details."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Find option B (correct answer)
        option_b = next((o for o in data["options"] if o["option_key"] == "B"), None)
        assert option_b is not None
        assert option_b["is_correct"] is True
        assert option_b["selection_rate"] > 0.5  # Majority selected correct answer
        assert "status" in option_b
        assert "discrimination" in option_b
        assert "discrimination_index" in option_b
        assert "top_quartile_rate" in option_b
        assert "bottom_quartile_rate" in option_b

        # Find option C (non-functioning - only 3 selections)
        option_c = next((o for o in data["options"] if o["option_key"] == "C"), None)
        assert option_c is not None
        assert option_c["is_correct"] is False
        assert option_c["selection_rate"] < 0.02  # Less than 2% threshold

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_insufficient_data(
        self,
        client,
        db_session,
        admin_token_headers,
        distractor_insufficient_data_question,
    ):
        """Test distractor analysis with insufficient data returns proper response."""
        response = client.get(
            f"/v1/admin/questions/{distractor_insufficient_data_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return empty options due to insufficient data
        assert data["question_id"] == distractor_insufficient_data_question.id
        assert len(data["options"]) == 0
        assert data["total_responses"] == 15  # 10 + 5

        # Recommendations should indicate insufficient data
        assert len(data["recommendations"]) > 0
        assert "Insufficient data" in data["recommendations"][0]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_question_not_found(self, client, admin_token_headers):
        """Test 404 response when question doesn't exist."""
        response = client.get(
            "/v1/admin/questions/99999/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_free_response_question(
        self, client, db_session, admin_token_headers, free_response_question
    ):
        """Test 400 response for free-response questions."""
        response = client.get(
            f"/v1/admin/questions/{free_response_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 400
        assert "not a multiple-choice" in response.json()["detail"].lower()

    def test_distractor_analysis_no_auth(self, client, distractor_analysis_question):
        """Test that request without admin token is rejected."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis"
        )

        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_invalid_token(
        self, client, distractor_analysis_question
    ):
        """Test that request with invalid admin token is rejected."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis",
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "")
    def test_distractor_analysis_token_not_configured(
        self, client, admin_token_headers, distractor_analysis_question
    ):
        """Test error when admin token is not configured on server."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 500

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_custom_min_responses(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that min_responses parameter is respected."""
        # Request with high threshold that the question won't meet
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis"
            "?min_responses=500",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return insufficient data response
        assert len(data["options"]) == 0
        assert "Insufficient data" in data["recommendations"][0]
        assert "500" in data["recommendations"][0]  # The threshold is mentioned

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_response_schema(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that response matches the expected schema exactly."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Top-level required fields
        required_fields = [
            "question_id",
            "question_text",
            "total_responses",
            "correct_answer",
            "options",
            "summary",
            "recommendations",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Option required fields
        if len(data["options"]) > 0:
            option = data["options"][0]
            option_fields = [
                "option_key",
                "is_correct",
                "selection_rate",
                "status",
                "discrimination",
                "discrimination_index",
                "top_quartile_rate",
                "bottom_quartile_rate",
            ]
            for field in option_fields:
                assert field in option, f"Missing option field: {field}"

        # Summary required fields
        summary_fields = [
            "functioning_distractors",
            "weak_distractors",
            "non_functioning_distractors",
            "inverted_distractors",
            "effective_option_count",
            "guessing_probability",
        ]
        for field in summary_fields:
            assert field in data["summary"], f"Missing summary field: {field}"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_analysis_status_values(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that status values are valid enum values."""
        response = client.get(
            f"/v1/admin/questions/{distractor_analysis_question.id}/distractor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        valid_statuses = {"functioning", "weak", "non-functioning"}
        valid_discriminations = {"good", "neutral", "inverted"}

        for option in data["options"]:
            assert (
                option["status"] in valid_statuses
            ), f"Invalid status: {option['status']}"
            assert (
                option["discrimination"] in valid_discriminations
            ), f"Invalid discrimination: {option['discrimination']}"


# =============================================================================
# DISTRACTOR SUMMARY ENDPOINT TESTS (DA-009)
# =============================================================================


class TestDistractorSummaryEndpoint:
    """Tests for GET /v1/admin/questions/distractor-summary endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_success(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test successful bulk distractor summary retrieval."""
        response = client.get(
            "/v1/admin/questions/distractor-summary",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify required fields present
        required_fields = [
            "total_questions_analyzed",
            "questions_with_non_functioning_distractors",
            "questions_with_inverted_distractors",
            "non_functioning_rate",
            "inverted_rate",
            "by_non_functioning_count",
            "worst_offenders",
            "by_question_type",
            "avg_effective_option_count",
            "questions_below_threshold",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_response_schema(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that response matches expected schema structure."""
        response = client.get(
            "/v1/admin/questions/distractor-summary",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify by_non_functioning_count structure
        nf_count = data["by_non_functioning_count"]
        assert "zero" in nf_count
        assert "one" in nf_count
        assert "two" in nf_count
        assert "three_or_more" in nf_count

        # All values should be non-negative integers
        for key, value in nf_count.items():
            assert isinstance(value, int)
            assert value >= 0

        # Verify by_question_type structure
        by_type = data["by_question_type"]
        assert isinstance(by_type, dict)
        # Should contain all question types
        valid_types = {"pattern", "logic", "spatial", "math", "verbal", "memory"}
        for qt in valid_types:
            assert qt in by_type, f"Missing question type: {qt}"
            assert "total_questions" in by_type[qt]
            assert "questions_with_issues" in by_type[qt]
            assert "avg_effective_options" in by_type[qt]

        # Verify rates are valid
        assert 0.0 <= data["non_functioning_rate"] <= 1.0
        assert 0.0 <= data["inverted_rate"] <= 1.0

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_includes_analyzed_question(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that the fixture question appears in the summary."""
        response = client.get(
            "/v1/admin/questions/distractor-summary?min_responses=50",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # The fixture has 200 responses which exceeds threshold of 50
        # It should be included in the analysis
        assert data["total_questions_analyzed"] >= 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_worst_offenders_structure(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test worst offenders list structure."""
        response = client.get(
            "/v1/admin/questions/distractor-summary",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        worst_offenders = data["worst_offenders"]
        assert isinstance(worst_offenders, list)
        assert len(worst_offenders) <= 10  # Max 10 offenders

        # Verify structure of each offender
        for offender in worst_offenders:
            required_fields = [
                "question_id",
                "question_type",
                "difficulty_level",
                "non_functioning_count",
                "inverted_count",
                "total_responses",
                "effective_option_count",
            ]
            for field in required_fields:
                assert field in offender, f"Missing offender field: {field}"

            # Verify types
            assert isinstance(offender["question_id"], int)
            assert isinstance(offender["non_functioning_count"], int)
            assert isinstance(offender["inverted_count"], int)
            assert isinstance(offender["total_responses"], int)
            assert isinstance(offender["effective_option_count"], (int, float))

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_with_question_type_filter(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test filtering by question type."""
        # Filter by the type of the fixture question
        response = client.get(
            "/v1/admin/questions/distractor-summary?question_type=pattern",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Response should still have all the required fields
        assert "total_questions_analyzed" in data
        assert "by_question_type" in data

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_with_min_responses_filter(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test filtering by minimum response count."""
        # High threshold - fixture has 200 responses
        response = client.get(
            "/v1/admin/questions/distractor-summary?min_responses=500",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # With threshold of 500, the fixture with 200 responses should be below threshold
        # and total_questions_analyzed should be 0 (or less than with lower threshold)
        assert data["questions_below_threshold"] >= 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_without_auth(self, client, db_session):
        """Test that endpoint requires admin authentication."""
        response = client.get("/v1/admin/questions/distractor-summary")

        assert response.status_code == 422  # Missing header

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_invalid_auth(self, client, db_session):
        """Test that endpoint rejects invalid admin token."""
        response = client.get(
            "/v1/admin/questions/distractor-summary",
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert response.status_code == 401

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_empty_dataset(
        self, client, db_session, admin_token_headers
    ):
        """Test behavior with no questions meeting threshold."""
        # Use high threshold (max allowed is 1000) to ensure no questions qualify
        # The fixture has 200 responses so 1000 will exclude it
        response = client.get(
            "/v1/admin/questions/distractor-summary?min_responses=1000",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should return valid response with zeros (or low counts since fixture has 200)
        # When threshold is 1000 and fixture has 200, it won't be analyzed
        assert data["total_questions_analyzed"] == 0
        assert data["questions_with_non_functioning_distractors"] == 0
        assert data["questions_with_inverted_distractors"] == 0
        assert data["non_functioning_rate"] == 0.0
        assert data["inverted_rate"] == 0.0
        assert data["worst_offenders"] == []
        assert data["avg_effective_option_count"] is None

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_invalid_question_type(
        self, client, db_session, admin_token_headers
    ):
        """Test behavior with invalid question type filter."""
        # Invalid question type should be handled gracefully
        response = client.get(
            "/v1/admin/questions/distractor-summary?question_type=invalid_type",
            headers=admin_token_headers,
        )

        # Should still succeed - just returns results without filtering
        assert response.status_code == 200
        data = response.json()
        assert "total_questions_analyzed" in data

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_distractor_summary_totals_consistent(
        self, client, db_session, admin_token_headers, distractor_analysis_question
    ):
        """Test that breakdown totals are consistent with overall totals."""
        response = client.get(
            "/v1/admin/questions/distractor-summary",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Sum of by_non_functioning_count should equal total_questions_analyzed
        nf_count = data["by_non_functioning_count"]
        nf_sum = (
            nf_count["zero"]
            + nf_count["one"]
            + nf_count["two"]
            + nf_count["three_or_more"]
        )
        assert nf_sum == data["total_questions_analyzed"]

        # Sum of by_question_type total_questions should equal total_questions_analyzed
        by_type_sum = sum(
            stats["total_questions"] for stats in data["by_question_type"].values()
        )
        assert by_type_sum == data["total_questions_analyzed"]


# =============================================================================
# SESSION VALIDITY ENDPOINT TESTS (CD-009)
# =============================================================================


@pytest.fixture
def validity_test_session(db_session, test_user, test_questions):
    """
    Create a test session with stored validity data for testing the
    session validity endpoint.
    """
    from app.models.models import TestSession, TestResult, Response, TestStatus
    from datetime import datetime, timezone

    # Create a test session
    test_session = TestSession(
        user_id=test_user.id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    db_session.flush()  # Get the session ID

    # Create some responses
    for i, question in enumerate(test_questions[:5]):
        response = Response(
            test_session_id=test_session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A" if i < 3 else "B",
            is_correct=(i < 3),  # First 3 correct, last 2 incorrect
            time_spent_seconds=30 + (i * 10),  # 30, 40, 50, 60, 70 seconds
        )
        db_session.add(response)

    # Create test result with stored validity data
    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=test_user.id,
        iq_score=110,
        total_questions=5,
        correct_answers=3,
        completion_time_seconds=280,
        validity_status="valid",
        validity_flags=None,
        validity_checked_at=datetime.now(timezone.utc),
    )
    db_session.add(test_result)
    db_session.commit()
    db_session.refresh(test_session)

    return test_session


@pytest.fixture
def suspect_validity_test_session(db_session, test_user, test_questions):
    """
    Create a test session with suspect validity status and flags.
    """
    from app.models.models import TestSession, TestResult, Response, TestStatus
    from datetime import datetime, timezone

    # Create a test session
    test_session = TestSession(
        user_id=test_user.id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    db_session.flush()

    # Create responses with suspicious timing (rapid responses)
    for i, question in enumerate(test_questions[:5]):
        response = Response(
            test_session_id=test_session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A",
            is_correct=True,
            time_spent_seconds=2 if i < 3 else 30,  # 3 rapid responses
        )
        db_session.add(response)

    # Create test result with suspect validity
    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=test_user.id,
        iq_score=120,
        total_questions=5,
        correct_answers=5,
        completion_time_seconds=100,
        validity_status="suspect",
        validity_flags=[
            {
                "type": "multiple_rapid_responses",
                "severity": "high",
                "source": "time_check",
                "details": "3 responses completed in under 3 seconds each.",
                "count": 3,
            }
        ],
        validity_checked_at=datetime.now(timezone.utc),
    )
    db_session.add(test_result)
    db_session.commit()
    db_session.refresh(test_session)

    return test_session


@pytest.fixture
def unchecked_validity_test_session(db_session, test_user, test_questions):
    """
    Create a test session without validity data (simulates pre-CD-007 sessions).
    """
    from app.models.models import TestSession, TestResult, Response, TestStatus
    from datetime import datetime, timezone

    # Create a test session
    test_session = TestSession(
        user_id=test_user.id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status=TestStatus.COMPLETED,
    )
    db_session.add(test_session)
    db_session.flush()

    # Create responses
    for i, question in enumerate(test_questions[:5]):
        response = Response(
            test_session_id=test_session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="A" if i < 2 else "B",
            is_correct=(i < 2),
            time_spent_seconds=45,
        )
        db_session.add(response)

    # Create test result WITHOUT validity data (pre-CD-007 simulation)
    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=test_user.id,
        iq_score=95,
        total_questions=5,
        correct_answers=2,
        completion_time_seconds=225,
        validity_status="valid",  # Default
        validity_flags=None,
        validity_checked_at=None,  # Key: not checked yet
    )
    db_session.add(test_result)
    db_session.commit()
    db_session.refresh(test_session)

    return test_session


class TestSessionValidityEndpoint:
    """Tests for GET /v1/admin/sessions/{session_id}/validity endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_with_stored_data(
        self, client, db_session, admin_token_headers, validity_test_session
    ):
        """Test getting validity for a session with stored validity data."""
        response = client.get(
            f"/v1/admin/sessions/{validity_test_session.id}/validity",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == validity_test_session.id
        assert data["validity_status"] == "valid"
        assert data["severity_score"] == 0
        assert data["confidence"] == 1.0
        assert data["flags"] == []
        assert data["flag_details"] == []
        assert data["completed_at"] is not None
        assert data["validity_checked_at"] is not None

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_with_suspect_status(
        self, client, db_session, admin_token_headers, suspect_validity_test_session
    ):
        """Test getting validity for a session with suspect status and flags."""
        response = client.get(
            f"/v1/admin/sessions/{suspect_validity_test_session.id}/validity",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == suspect_validity_test_session.id
        assert data["validity_status"] == "suspect"
        assert data["severity_score"] == 2  # 1 high-severity flag = 2 points
        assert len(data["flags"]) == 1
        assert "multiple_rapid_responses" in data["flags"]
        assert len(data["flag_details"]) == 1
        assert data["flag_details"][0]["type"] == "multiple_rapid_responses"
        assert data["flag_details"][0]["severity"] == "high"
        assert data["flag_details"][0]["source"] == "time_check"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_on_demand(
        self, client, db_session, admin_token_headers, unchecked_validity_test_session
    ):
        """Test on-demand validity analysis for sessions without stored data."""
        response = client.get(
            f"/v1/admin/sessions/{unchecked_validity_test_session.id}/validity",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == unchecked_validity_test_session.id
        # On-demand analysis should return a status
        assert data["validity_status"] in ["valid", "suspect", "invalid"]
        assert "severity_score" in data
        assert "confidence" in data
        assert "flags" in data
        assert "flag_details" in data
        # On-demand analysis includes full details
        assert data["details"] is not None
        assert "person_fit" in data["details"]
        assert "time_check" in data["details"]
        assert "guttman_check" in data["details"]
        # Not stored
        assert data["validity_checked_at"] is None

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_not_found(
        self, client, db_session, admin_token_headers
    ):
        """Test getting validity for a non-existent session."""
        response = client.get(
            "/v1/admin/sessions/999999/validity",
            headers=admin_token_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_requires_auth(self, client, db_session):
        """Test that the endpoint requires admin authentication."""
        response = client.get("/v1/admin/sessions/1/validity")

        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_invalid_token(
        self, client, db_session, validity_test_session
    ):
        """Test that the endpoint rejects invalid admin tokens."""
        response = client.get(
            f"/v1/admin/sessions/{validity_test_session.id}/validity",
            headers={"X-Admin-Token": "invalid-token"},
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    @patch("app.core.settings.ADMIN_TOKEN", None)
    def test_get_session_validity_token_not_configured(
        self, client, db_session, admin_token_headers
    ):
        """Test behavior when admin token is not configured on server."""
        response = client.get(
            "/v1/admin/sessions/1/validity",
            headers=admin_token_headers,
        )

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"].lower()

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_session_validity_response_schema(
        self, client, db_session, admin_token_headers, validity_test_session
    ):
        """Test that the response matches the expected schema."""
        response = client.get(
            f"/v1/admin/sessions/{validity_test_session.id}/validity",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "session_id" in data
        assert "user_id" in data
        assert "validity_status" in data
        assert "severity_score" in data
        assert "confidence" in data
        assert "flags" in data
        assert "flag_details" in data

        # Check types
        assert isinstance(data["session_id"], int)
        assert isinstance(data["user_id"], int)
        assert isinstance(data["validity_status"], str)
        assert isinstance(data["severity_score"], int)
        assert isinstance(data["confidence"], float)
        assert isinstance(data["flags"], list)
        assert isinstance(data["flag_details"], list)

        # Check validity_status is a valid enum value
        assert data["validity_status"] in ["valid", "suspect", "invalid"]

        # Check confidence is in valid range
        assert 0.0 <= data["confidence"] <= 1.0


# =============================================================================
# VALIDITY SUMMARY REPORT ENDPOINT TESTS (CD-010)
# =============================================================================


class TestValiditySummaryReport:
    """Tests for GET /v1/admin/validity-report endpoint."""

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_empty(self, client, db_session, admin_token_headers):
        """Test validity report with no test sessions."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "summary" in data
        assert "by_flag_type" in data
        assert "trends" in data
        assert "action_needed" in data
        assert "period_days" in data
        assert "generated_at" in data

        # Verify summary with empty data
        assert data["summary"]["total_sessions_analyzed"] == 0
        assert data["summary"]["valid"] == 0
        assert data["summary"]["suspect"] == 0
        assert data["summary"]["invalid"] == 0

        # Verify trends with no data
        assert data["trends"]["invalid_rate_7d"] == 0.0
        assert data["trends"]["invalid_rate_30d"] == 0.0

        # Verify no action needed
        assert data["action_needed"] == []

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_with_data(
        self,
        client,
        db_session,
        admin_token_headers,
        validity_test_session,
        suspect_validity_test_session,
    ):
        """Test validity report with sessions having different validity statuses."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have 2 sessions analyzed (1 valid, 1 suspect)
        assert data["summary"]["total_sessions_analyzed"] == 2
        assert data["summary"]["valid"] == 1
        assert data["summary"]["suspect"] == 1
        assert data["summary"]["invalid"] == 0

        # Action needed should include the suspect session
        assert len(data["action_needed"]) >= 1

        # Find the suspect session in action_needed
        suspect_session = next(
            (s for s in data["action_needed"] if s["validity_status"] == "suspect"),
            None,
        )
        assert suspect_session is not None
        assert "multiple_rapid_responses" in suspect_session["flags"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_custom_days(
        self, client, db_session, admin_token_headers, validity_test_session
    ):
        """Test validity report with custom days parameter."""
        response = client.get(
            "/v1/admin/validity-report?days=7",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify period_days reflects the custom value
        assert data["period_days"] == 7

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_status_filter(
        self,
        client,
        db_session,
        admin_token_headers,
        validity_test_session,
        suspect_validity_test_session,
    ):
        """Test validity report with status filter."""
        # Filter by valid status only
        response = client.get(
            "/v1/admin/validity-report?status=valid",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include valid sessions
        assert data["summary"]["valid"] == 1
        assert data["summary"]["suspect"] == 0
        assert data["summary"]["invalid"] == 0
        assert data["summary"]["total_sessions_analyzed"] == 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_flag_breakdown(
        self, client, db_session, admin_token_headers, suspect_validity_test_session
    ):
        """Test that flag type breakdown is correctly calculated."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify by_flag_type structure
        by_flag_type = data["by_flag_type"]
        assert "aberrant_response_pattern" in by_flag_type
        assert "multiple_rapid_responses" in by_flag_type
        assert "suspiciously_fast_on_hard" in by_flag_type
        assert "extended_pauses" in by_flag_type
        assert "total_time_too_fast" in by_flag_type
        assert "total_time_excessive" in by_flag_type
        assert "high_guttman_errors" in by_flag_type
        assert "elevated_guttman_errors" in by_flag_type

        # The suspect session has multiple_rapid_responses flag
        assert by_flag_type["multiple_rapid_responses"] == 1

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_trend_calculation(
        self,
        client,
        db_session,
        admin_token_headers,
        validity_test_session,
        suspect_validity_test_session,
    ):
        """Test that trend calculation works correctly."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify trends structure
        trends = data["trends"]
        assert "invalid_rate_7d" in trends
        assert "invalid_rate_30d" in trends
        assert "suspect_rate_7d" in trends
        assert "suspect_rate_30d" in trends
        assert "trend" in trends

        # Trend should be one of the valid values
        assert trends["trend"] in ["improving", "stable", "worsening"]

        # Rates should be valid percentages (0.0 to 1.0)
        assert 0.0 <= trends["invalid_rate_7d"] <= 1.0
        assert 0.0 <= trends["invalid_rate_30d"] <= 1.0
        assert 0.0 <= trends["suspect_rate_7d"] <= 1.0
        assert 0.0 <= trends["suspect_rate_30d"] <= 1.0

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_action_needed_sorted(
        self,
        client,
        db_session,
        admin_token_headers,
        suspect_validity_test_session,
    ):
        """Test that action_needed is sorted by severity score."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        action_needed = data["action_needed"]
        if len(action_needed) >= 2:
            # Verify sorted by severity_score descending
            for i in range(len(action_needed) - 1):
                assert (
                    action_needed[i]["severity_score"]
                    >= action_needed[i + 1]["severity_score"]
                )

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_session_needing_review_structure(
        self, client, db_session, admin_token_headers, suspect_validity_test_session
    ):
        """Test structure of sessions needing review."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should have at least one session needing review
        assert len(data["action_needed"]) >= 1

        # Check structure of first session
        session = data["action_needed"][0]
        assert "session_id" in session
        assert "user_id" in session
        assert "validity_status" in session
        assert "severity_score" in session
        assert "flags" in session
        assert "completed_at" in session

        # Verify types
        assert isinstance(session["session_id"], int)
        assert isinstance(session["user_id"], int)
        assert session["validity_status"] in ["invalid", "suspect"]
        assert isinstance(session["severity_score"], int)
        assert isinstance(session["flags"], list)

    def test_validity_report_no_auth(self, client, db_session):
        """Test that endpoint requires admin authentication."""
        response = client.get("/v1/admin/validity-report")

        assert response.status_code == 422  # Missing required header

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_invalid_auth(self, client, db_session):
        """Test that endpoint rejects invalid admin token."""
        response = client.get(
            "/v1/admin/validity-report",
            headers={"X-Admin-Token": "wrong-token"},
        )

        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "")
    def test_validity_report_token_not_configured(
        self, client, db_session, admin_token_headers
    ):
        """Test error when admin token is not configured on server."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 500
        assert "not configured" in response.json()["detail"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_invalid_days_parameter(
        self, client, db_session, admin_token_headers
    ):
        """Test validation of days parameter."""
        # Below minimum (1)
        response = client.get(
            "/v1/admin/validity-report?days=0",
            headers=admin_token_headers,
        )
        assert response.status_code == 422

        # Above maximum (365)
        response = client.get(
            "/v1/admin/validity-report?days=366",
            headers=admin_token_headers,
        )
        assert response.status_code == 422

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_response_schema(
        self, client, db_session, admin_token_headers, validity_test_session
    ):
        """Test that response matches the expected schema."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Top-level required fields
        required_fields = [
            "summary",
            "by_flag_type",
            "trends",
            "action_needed",
            "period_days",
            "generated_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Summary required fields
        summary_fields = [
            "total_sessions_analyzed",
            "valid",
            "suspect",
            "invalid",
        ]
        for field in summary_fields:
            assert field in data["summary"], f"Missing summary field: {field}"

        # Trends required fields
        trends_fields = [
            "invalid_rate_7d",
            "invalid_rate_30d",
            "suspect_rate_7d",
            "suspect_rate_30d",
            "trend",
        ]
        for field in trends_fields:
            assert field in data["trends"], f"Missing trends field: {field}"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_excludes_valid_from_action_needed(
        self, client, db_session, admin_token_headers, validity_test_session
    ):
        """Test that valid sessions are not included in action_needed."""
        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # The validity_test_session has status "valid"
        # It should not appear in action_needed
        for session in data["action_needed"]:
            assert session["validity_status"] != "valid"

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_validity_report_action_needed_limit(
        self, client, db_session, admin_token_headers, test_user, test_questions
    ):
        """Test that action_needed is limited to 50 sessions."""
        from app.models.models import TestSession, TestResult, TestStatus
        from datetime import datetime, timezone

        # Create 55 suspect sessions
        for i in range(55):
            session = TestSession(
                user_id=test_user.id,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()

            result = TestResult(
                test_session_id=session.id,
                user_id=test_user.id,
                iq_score=100,
                total_questions=5,
                correct_answers=3,
                completion_time_seconds=300,
                validity_status="suspect",
                validity_flags=[
                    {"type": "multiple_rapid_responses", "severity": "medium"}
                ],
                validity_checked_at=datetime.now(timezone.utc),
            )
            db_session.add(result)

        db_session.commit()

        response = client.get(
            "/v1/admin/validity-report",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Should be limited to 50 sessions
        assert len(data["action_needed"]) <= 50


# =============================================================================
# Factor Analysis Endpoint Tests (DW-011)
# =============================================================================


class TestFactorAnalysisEndpoint:
    """Tests for GET /v1/admin/analytics/factor-analysis endpoint."""

    @pytest.fixture
    def admin_token_headers(self):
        """Create admin token headers for authentication."""
        return {"X-Admin-Token": "test-admin-token"}

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_factor_analysis_requires_auth(self, client):
        """Test that factor analysis endpoint requires admin token."""
        # No headers
        response = client.get("/v1/admin/analytics/factor-analysis")
        assert response.status_code == 422  # Missing header

        # Wrong header
        response = client.get(
            "/v1/admin/analytics/factor-analysis",
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_factor_analysis_insufficient_data_no_sessions(
        self, client, db_session, admin_token_headers
    ):
        """Test error response when no completed sessions exist."""
        response = client.get(
            "/v1/admin/analytics/factor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["error"] == "insufficient_sample"
        assert detail["sample_size"] == 0
        assert detail["minimum_required"] == 500

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_factor_analysis_insufficient_sample_below_500(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test error response when sample size is below 500."""
        from app.models.models import (
            TestSession,
            Response,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )
        from datetime import datetime, timezone

        # Create our own questions to ensure proper response counts
        questions = []
        for i in range(15):  # 15 questions
            q = Question(
                question_text=f"Test question {i}",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                answer_options={"A": "opt1", "B": "opt2"},
                correct_answer="A",
                is_active=True,
            )
            db_session.add(q)
            questions.append(q)
        db_session.flush()

        # Create 100 completed test sessions (below the 500 minimum)
        for i in range(100):
            session = TestSession(
                user_id=test_user.id,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()

            # Add responses for each question
            for q in questions:
                resp = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=q.id,
                    user_answer="A" if i % 2 == 0 else "B",
                    is_correct=(i % 2 == 0),
                    time_spent_seconds=10,
                )
                db_session.add(resp)

        db_session.commit()

        # Use min_responses_per_question=10 to ensure our questions are included
        response = client.get(
            "/v1/admin/analytics/factor-analysis?min_responses_per_question=10",
            headers=admin_token_headers,
        )

        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        detail = data["detail"]
        assert detail["error"] == "insufficient_sample"
        assert detail["sample_size"] == 100
        assert detail["minimum_required"] == 500
        assert "400" in detail["recommendation"]  # Should mention ~400 more needed

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_factor_analysis_success_with_sufficient_data(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test successful factor analysis with 500+ completed sessions."""
        from app.models.models import (
            TestSession,
            Response,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )
        from datetime import datetime, timezone
        import random

        # Create questions of different types with varying difficulties
        question_type_enums = [
            QuestionType.PATTERN,
            QuestionType.LOGIC,
            QuestionType.SPATIAL,
            QuestionType.MATH,
            QuestionType.VERBAL,
            QuestionType.MEMORY,
        ]
        questions = []
        for i, q_type in enumerate(question_type_enums):
            for j in range(10):  # 10 questions per type = 60 total
                q = Question(
                    question_text=f"Question {q_type.value}_{j}",
                    question_type=q_type,
                    difficulty_level=DifficultyLevel.MEDIUM,
                    answer_options={"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
                    correct_answer="A",
                    is_active=True,
                )
                db_session.add(q)
                questions.append(q)
        db_session.flush()

        # Create 550 completed test sessions
        random.seed(42)  # For reproducibility
        for i in range(550):
            session = TestSession(
                user_id=test_user.id,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()

            # Add responses for each question with some variance
            for q in questions:
                # Simulate varying difficulty: harder questions have lower accuracy
                base_accuracy = 0.6
                is_correct = random.random() < base_accuracy
                resp = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=q.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=10 + random.randint(-5, 15),
                )
                db_session.add(resp)

        db_session.commit()

        response = client.get(
            "/v1/admin/analytics/factor-analysis",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "analysis_date" in data
        assert "sample_size" in data
        assert "n_items" in data
        assert "g_loadings" in data
        assert "variance_explained" in data
        assert "reliability" in data
        assert "recommendations" in data
        assert "warnings" in data

        # Verify sample size is reported correctly
        assert data["sample_size"] >= 500

        # Verify g_loadings contains domain entries
        assert len(data["g_loadings"]) > 0

        # Verify variance explained is between 0 and 1
        assert 0 <= data["variance_explained"] <= 1

        # Verify reliability metrics
        # Note: Cronbach's alpha can be slightly negative with random data
        # In practice, values range from -1 to 1, with negative values indicating
        # items don't correlate well (expected with random test data)
        assert "cronbachs_alpha" in data["reliability"]
        assert -1 <= data["reliability"]["cronbachs_alpha"] <= 1

        # Verify recommendations structure
        if data["recommendations"]:
            rec = data["recommendations"][0]
            assert "category" in rec
            assert "message" in rec
            assert "severity" in rec
            assert rec["severity"] in ["info", "warning", "critical"]

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_factor_analysis_custom_min_responses(
        self, client, db_session, admin_token_headers, test_user
    ):
        """Test factor analysis with custom min_responses_per_question parameter."""
        from app.models.models import (
            TestSession,
            Response,
            TestStatus,
            Question,
            QuestionType,
            DifficultyLevel,
        )
        from datetime import datetime, timezone
        import random

        # Create questions
        questions = []
        for i in range(20):
            q = Question(
                question_text=f"Question_{i}",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                answer_options={"A": "opt1", "B": "opt2", "C": "opt3", "D": "opt4"},
                correct_answer="A",
                is_active=True,
            )
            db_session.add(q)
            questions.append(q)
        db_session.flush()

        # Create 600 sessions
        random.seed(42)
        for i in range(600):
            session = TestSession(
                user_id=test_user.id,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                status=TestStatus.COMPLETED,
            )
            db_session.add(session)
            db_session.flush()

            for q in questions:
                is_correct = random.random() < 0.6
                resp = Response(
                    test_session_id=session.id,
                    user_id=test_user.id,
                    question_id=q.id,
                    user_answer="A" if is_correct else "B",
                    is_correct=is_correct,
                    time_spent_seconds=15,
                )
                db_session.add(resp)

        db_session.commit()

        # Request with custom min_responses_per_question
        response = client.get(
            "/v1/admin/analytics/factor-analysis?min_responses_per_question=50",
            headers=admin_token_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["sample_size"] >= 500

    @patch("app.core.settings.ADMIN_TOKEN", "test-admin-token")
    def test_factor_analysis_min_responses_validation(
        self, client, admin_token_headers
    ):
        """Test that min_responses_per_question has proper validation."""
        # Too low
        response = client.get(
            "/v1/admin/analytics/factor-analysis?min_responses_per_question=5",
            headers=admin_token_headers,
        )
        assert response.status_code == 422

        # Too high
        response = client.get(
            "/v1/admin/analytics/factor-analysis?min_responses_per_question=500",
            headers=admin_token_headers,
        )
        assert response.status_code == 422
