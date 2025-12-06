"""
End-to-end tests for question generation tracking.

These tests verify the complete integration between the question-service
RunReporter and the backend admin API, ensuring that:
1. The question-service can report metrics to the real backend
2. Metrics are persisted correctly to the database
3. API endpoints return correct data after persistence

Task: QGT-014
"""
import pytest
from unittest.mock import patch

from app.models import QuestionGenerationRun, GenerationRunStatus


# Import from question-service - these are added to path in conftest
# We'll simulate the question-service behavior directly in tests


@pytest.fixture
def service_key_headers():
    """Create service key headers for authentication."""
    return {"X-Service-Key": "test-service-key"}


@pytest.fixture
def complete_metrics_summary():
    """
    Create a complete metrics summary simulating MetricsTracker.get_summary().

    This represents what the question-service MetricsTracker would produce
    after a successful generation run.
    """
    return {
        "execution": {
            "start_time": "2024-12-05T10:00:00+00:00",
            "end_time": "2024-12-05T10:05:30+00:00",
            "duration_seconds": 330.5,
        },
        "generation": {
            "requested": 50,
            "generated": 48,
            "failed": 2,
            "success_rate": 0.96,
            "by_provider": {"openai": 30, "anthropic": 18},
            "by_type": {
                "pattern_recognition": 10,
                "logical_reasoning": 12,
                "spatial_reasoning": 8,
                "mathematical": 10,
                "verbal_reasoning": 5,
                "memory": 3,
            },
            "by_difficulty": {"easy": 16, "medium": 20, "hard": 12},
            "errors": [],
        },
        "evaluation": {
            "evaluated": 48,
            "approved": 45,
            "rejected": 3,
            "failed": 0,
            "approval_rate": 0.9375,
            "average_score": 0.842,
            "min_score": 0.68,
            "max_score": 0.96,
            "errors": [],
        },
        "deduplication": {
            "checked": 45,
            "duplicates_found": 3,
            "exact_duplicates": 2,
            "semantic_duplicates": 1,
            "duplicate_rate": 0.0667,
            "errors": [],
        },
        "database": {
            "inserted": 42,
            "failed": 0,
            "success_rate": 1.0,
            "errors": [],
        },
        "api": {
            "total_calls": 120,
            "by_provider": {"openai": 75, "anthropic": 45},
        },
        "error_classification": {
            "by_category": {"rate_limit": 1, "timeout": 1},
            "by_severity": {"medium": 2},
            "critical_errors": 0,
            "critical_error_details": [],
            "total_classified_errors": 2,
        },
        "overall": {
            "questions_requested": 50,
            "questions_final_output": 42,
            "overall_success_rate": 0.84,
            "total_errors": 2,
        },
    }


class RunReporterSimulator:
    """
    Simulates the question-service RunReporter behavior for E2E testing.

    This class mirrors the RunReporter from question-service but uses
    the test client directly instead of making HTTP requests.
    """

    def __init__(self, test_client, service_key: str):
        """Initialize the simulator with test client and service key."""
        self.test_client = test_client
        self.service_key = service_key

    def _transform_summary_to_payload(
        self,
        summary: dict,
        exit_code: int,
        environment: str = None,
        triggered_by: str = None,
        prompt_version: str = None,
        arbiter_config_version: str = None,
        min_arbiter_score_threshold: float = None,
    ) -> dict:
        """Transform MetricsTracker summary to API payload format."""
        execution = summary.get("execution", {})
        generation = summary.get("generation", {})
        evaluation = summary.get("evaluation", {})
        deduplication = summary.get("deduplication", {})
        database = summary.get("database", {})
        api = summary.get("api", {})
        error_classification = summary.get("error_classification", {})
        overall = summary.get("overall", {})

        # Determine status based on exit code
        if exit_code == 0:
            status = "success"
        elif exit_code == 3:
            status = "partial_failure"
        else:
            status = "failed"

        # Build provider metrics
        providers_generated = generation.get("by_provider", {})
        providers_api_calls = api.get("by_provider", {})
        all_providers = set(providers_generated.keys()) | set(
            providers_api_calls.keys()
        )

        provider_metrics = {}
        for provider in all_providers:
            provider_metrics[provider] = {
                "generated": providers_generated.get(provider, 0),
                "api_calls": providers_api_calls.get(provider, 0),
                "failures": 0,
            }

        # Build error summary
        error_summary = {
            "by_category": error_classification.get("by_category", {}),
            "by_severity": error_classification.get("by_severity", {}),
            "critical_count": error_classification.get("critical_errors", 0),
        }

        return {
            "started_at": execution.get("start_time"),
            "completed_at": execution.get("end_time"),
            "duration_seconds": execution.get("duration_seconds"),
            "status": status,
            "exit_code": exit_code,
            "questions_requested": generation.get("requested", 0),
            "questions_generated": generation.get("generated", 0),
            "generation_failures": generation.get("failed", 0),
            "generation_success_rate": generation.get("success_rate"),
            "questions_evaluated": evaluation.get("evaluated", 0),
            "questions_approved": evaluation.get("approved", 0),
            "questions_rejected": evaluation.get("rejected", 0),
            "approval_rate": evaluation.get("approval_rate"),
            "avg_arbiter_score": evaluation.get("average_score"),
            "min_arbiter_score": evaluation.get("min_score"),
            "max_arbiter_score": evaluation.get("max_score"),
            "duplicates_found": deduplication.get("duplicates_found", 0),
            "exact_duplicates": deduplication.get("exact_duplicates", 0),
            "semantic_duplicates": deduplication.get("semantic_duplicates", 0),
            "duplicate_rate": deduplication.get("duplicate_rate"),
            "questions_inserted": database.get("inserted", 0),
            "insertion_failures": database.get("failed", 0),
            "overall_success_rate": overall.get("overall_success_rate"),
            "total_errors": overall.get("total_errors", 0),
            "total_api_calls": api.get("total_calls", 0),
            "provider_metrics": provider_metrics if provider_metrics else None,
            "type_metrics": generation.get("by_type") or None,
            "difficulty_metrics": generation.get("by_difficulty") or None,
            "error_summary": error_summary if any(error_summary.values()) else None,
            "prompt_version": prompt_version,
            "arbiter_config_version": arbiter_config_version,
            "min_arbiter_score_threshold": min_arbiter_score_threshold,
            "environment": environment,
            "triggered_by": triggered_by,
        }

    def report_run(
        self,
        summary: dict,
        exit_code: int,
        environment: str = None,
        triggered_by: str = None,
        prompt_version: str = None,
        arbiter_config_version: str = None,
        min_arbiter_score_threshold: float = None,
    ) -> dict:
        """Report a completed run to the backend API."""
        payload = self._transform_summary_to_payload(
            summary=summary,
            exit_code=exit_code,
            environment=environment,
            triggered_by=triggered_by,
            prompt_version=prompt_version,
            arbiter_config_version=arbiter_config_version,
            min_arbiter_score_threshold=min_arbiter_score_threshold,
        )

        response = self.test_client.post(
            "/v1/admin/generation-runs",
            json=payload,
            headers={"X-Service-Key": self.service_key},
        )

        return response


class TestEndToEndRunReporting:
    """
    End-to-end tests for the complete run reporting flow.

    These tests verify the integration between question-service and backend.
    """

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_successful_run_reporting(
        self, client, db_session, complete_metrics_summary
    ):
        """
        Test complete E2E flow: report successful run, verify persistence,
        verify API returns correct data.
        """
        # Simulate question-service reporting a run
        reporter = RunReporterSimulator(client, "test-service-key")

        response = reporter.report_run(
            summary=complete_metrics_summary,
            exit_code=0,
            environment="production",
            triggered_by="scheduler",
            prompt_version="v2.1",
            arbiter_config_version="v1.0",
            min_arbiter_score_threshold=0.7,
        )

        # Step 1: Verify the API accepted the run
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        run_id = data["id"]
        assert data["status"] == "success"

        # Step 2: Verify the run was persisted correctly to database
        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == run_id)
            .first()
        )
        assert db_run is not None
        assert db_run.status == GenerationRunStatus.SUCCESS
        assert db_run.exit_code == 0
        assert db_run.questions_requested == 50
        assert db_run.questions_generated == 48
        assert db_run.questions_inserted == 42
        assert db_run.overall_success_rate == 0.84
        assert db_run.environment == "production"
        assert db_run.triggered_by == "scheduler"
        assert db_run.prompt_version == "v2.1"
        assert db_run.arbiter_config_version == "v1.0"
        assert db_run.min_arbiter_score_threshold == 0.7

        # Verify JSONB fields
        assert db_run.provider_metrics["openai"]["generated"] == 30
        assert db_run.provider_metrics["anthropic"]["generated"] == 18
        assert db_run.type_metrics["pattern_recognition"] == 10
        assert db_run.difficulty_metrics["easy"] == 16
        assert db_run.error_summary["by_category"]["rate_limit"] == 1

        # Step 3: Verify API retrieval returns correct data
        get_response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers={"X-Service-Key": "test-service-key"},
        )
        assert get_response.status_code == 200
        get_data = get_response.json()

        assert get_data["id"] == run_id
        assert get_data["status"] == "success"
        assert get_data["questions_requested"] == 50
        assert get_data["questions_generated"] == 48
        assert get_data["questions_inserted"] == 42
        assert get_data["overall_success_rate"] == 0.84
        assert get_data["provider_metrics"]["openai"]["generated"] == 30
        assert get_data["pipeline_losses"]["total_loss"] == 8  # 50 - 42

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_failed_run_reporting(self, client, db_session):
        """
        Test E2E flow for a failed run: verify all failure metrics are captured.
        """
        failed_summary = {
            "execution": {
                "start_time": "2024-12-05T10:00:00+00:00",
                "end_time": "2024-12-05T10:01:00+00:00",
                "duration_seconds": 60.0,
            },
            "generation": {
                "requested": 50,
                "generated": 0,
                "failed": 50,
                "success_rate": 0.0,
                "by_provider": {},
                "by_type": {},
                "by_difficulty": {},
                "errors": [],
            },
            "evaluation": {
                "evaluated": 0,
                "approved": 0,
                "rejected": 0,
                "approval_rate": 0.0,
            },
            "deduplication": {
                "duplicates_found": 0,
                "exact_duplicates": 0,
                "semantic_duplicates": 0,
                "duplicate_rate": 0.0,
            },
            "database": {
                "inserted": 0,
                "failed": 0,
            },
            "api": {
                "total_calls": 50,
                "by_provider": {"openai": 50},
            },
            "error_classification": {
                "by_category": {"api_error": 50},
                "by_severity": {"critical": 50},
                "critical_errors": 50,
            },
            "overall": {
                "questions_requested": 50,
                "questions_final_output": 0,
                "overall_success_rate": 0.0,
                "total_errors": 50,
            },
        }

        reporter = RunReporterSimulator(client, "test-service-key")
        response = reporter.report_run(
            summary=failed_summary,
            exit_code=2,  # No questions generated
            environment="production",
            triggered_by="scheduler",
        )

        assert response.status_code == 201
        run_id = response.json()["id"]

        # Verify database state
        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == run_id)
            .first()
        )
        assert db_run.status == GenerationRunStatus.FAILED
        assert db_run.exit_code == 2
        assert db_run.questions_generated == 0
        assert db_run.questions_inserted == 0
        assert db_run.total_errors == 50

        # Verify API returns failed run correctly
        get_response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers={"X-Service-Key": "test-service-key"},
        )
        assert get_response.status_code == 200
        get_data = get_response.json()
        assert get_data["status"] == "failed"
        assert get_data["pipeline_losses"]["total_loss"] == 50

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_partial_failure_run_reporting(self, client, db_session):
        """
        Test E2E flow for partial failure: some questions succeeded.
        """
        partial_summary = {
            "execution": {
                "start_time": "2024-12-05T10:00:00+00:00",
                "end_time": "2024-12-05T10:03:00+00:00",
                "duration_seconds": 180.0,
            },
            "generation": {
                "requested": 50,
                "generated": 30,
                "failed": 20,
                "success_rate": 0.6,
                "by_provider": {"openai": 20, "anthropic": 10},
                "by_type": {"pattern_recognition": 15, "logical_reasoning": 15},
                "by_difficulty": {"easy": 10, "medium": 15, "hard": 5},
            },
            "evaluation": {
                "evaluated": 30,
                "approved": 25,
                "rejected": 5,
                "approval_rate": 0.833,
                "average_score": 0.78,
                "min_score": 0.55,
                "max_score": 0.92,
            },
            "deduplication": {
                "duplicates_found": 3,
                "exact_duplicates": 2,
                "semantic_duplicates": 1,
                "duplicate_rate": 0.12,
            },
            "database": {
                "inserted": 22,
                "failed": 0,
            },
            "api": {
                "total_calls": 80,
                "by_provider": {"openai": 50, "anthropic": 30},
            },
            "error_classification": {
                "by_category": {"rate_limit": 15, "timeout": 5},
                "by_severity": {"high": 10, "medium": 10},
                "critical_errors": 0,
            },
            "overall": {
                "questions_requested": 50,
                "questions_final_output": 22,
                "overall_success_rate": 0.44,
                "total_errors": 20,
            },
        }

        reporter = RunReporterSimulator(client, "test-service-key")
        response = reporter.report_run(
            summary=partial_summary,
            exit_code=3,  # Partial failure
            environment="staging",
            triggered_by="manual",
        )

        assert response.status_code == 201
        run_id = response.json()["id"]

        # Verify database
        db_run = (
            db_session.query(QuestionGenerationRun)
            .filter(QuestionGenerationRun.id == run_id)
            .first()
        )
        assert db_run.status == GenerationRunStatus.PARTIAL_FAILURE
        assert db_run.questions_inserted == 22
        assert db_run.total_errors == 20

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_multiple_runs_and_stats(
        self, client, db_session, complete_metrics_summary
    ):
        """
        Test E2E flow: report multiple runs and verify stats aggregation.
        """
        reporter = RunReporterSimulator(client, "test-service-key")

        # Report multiple runs with varying success rates
        runs_to_report = [
            {
                "summary": complete_metrics_summary,
                "exit_code": 0,
                "environment": "production",
                "triggered_by": "scheduler",
            },
            {
                "summary": {
                    **complete_metrics_summary,
                    "execution": {
                        "start_time": "2024-12-06T10:00:00+00:00",
                        "end_time": "2024-12-06T10:05:00+00:00",
                        "duration_seconds": 300.0,
                    },
                    "overall": {
                        "questions_requested": 50,
                        "questions_final_output": 40,
                        "overall_success_rate": 0.80,
                        "total_errors": 4,
                    },
                },
                "exit_code": 0,
                "environment": "production",
                "triggered_by": "scheduler",
            },
        ]

        run_ids = []
        for run_data in runs_to_report:
            response = reporter.report_run(
                summary=run_data["summary"],
                exit_code=run_data["exit_code"],
                environment=run_data["environment"],
                triggered_by=run_data["triggered_by"],
            )
            assert response.status_code == 201
            run_ids.append(response.json()["id"])

        # Verify stats endpoint aggregates correctly
        stats_response = client.get(
            "/v1/admin/generation-runs/stats"
            "?start_date=2024-12-01T00:00:00Z"
            "&end_date=2024-12-31T23:59:59Z",
            headers={"X-Service-Key": "test-service-key"},
        )

        assert stats_response.status_code == 200
        stats = stats_response.json()

        assert stats["total_runs"] == 2
        assert stats["successful_runs"] == 2
        # Both runs requested 50 questions
        assert stats["total_questions_requested"] == 100
        # Provider summary should aggregate
        assert stats["provider_summary"] is not None
        assert "openai" in stats["provider_summary"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_list_endpoint_returns_reported_runs(
        self, client, db_session, complete_metrics_summary
    ):
        """
        Test E2E flow: report runs and verify list endpoint returns them.
        """
        reporter = RunReporterSimulator(client, "test-service-key")

        # Report 3 runs
        for i in range(3):
            modified_summary = {
                **complete_metrics_summary,
                "execution": {
                    "start_time": f"2024-12-0{i+1}T10:00:00+00:00",
                    "end_time": f"2024-12-0{i+1}T10:05:00+00:00",
                    "duration_seconds": 300.0 + i * 10,
                },
            }
            response = reporter.report_run(
                summary=modified_summary,
                exit_code=0,
                environment="production",
            )
            assert response.status_code == 201

        # List all runs
        list_response = client.get(
            "/v1/admin/generation-runs",
            headers={"X-Service-Key": "test-service-key"},
        )

        assert list_response.status_code == 200
        list_data = list_response.json()

        assert list_data["total"] == 3
        assert len(list_data["runs"]) == 3
        # Verify runs are sorted by started_at desc (most recent first)
        assert list_data["runs"][0]["started_at"] > list_data["runs"][1]["started_at"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_provider_metrics_correctly_aggregated(
        self, client, db_session, complete_metrics_summary
    ):
        """
        Test E2E flow: verify provider metrics are correctly stored and retrieved.
        """
        reporter = RunReporterSimulator(client, "test-service-key")

        response = reporter.report_run(
            summary=complete_metrics_summary,
            exit_code=0,
            environment="production",
            triggered_by="scheduler",
        )

        run_id = response.json()["id"]

        # Verify via API
        get_response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers={"X-Service-Key": "test-service-key"},
        )

        get_data = get_response.json()
        provider_metrics = get_data["provider_metrics"]

        # Verify OpenAI metrics
        assert provider_metrics["openai"]["generated"] == 30
        assert provider_metrics["openai"]["api_calls"] == 75

        # Verify Anthropic metrics
        assert provider_metrics["anthropic"]["generated"] == 18
        assert provider_metrics["anthropic"]["api_calls"] == 45

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_pipeline_losses_calculated_correctly(
        self, client, db_session, complete_metrics_summary
    ):
        """
        Test E2E flow: verify pipeline loss calculations are correct.
        """
        reporter = RunReporterSimulator(client, "test-service-key")

        response = reporter.report_run(
            summary=complete_metrics_summary,
            exit_code=0,
            environment="production",
        )

        run_id = response.json()["id"]

        # Get detailed run with pipeline losses
        get_response = client.get(
            f"/v1/admin/generation-runs/{run_id}",
            headers={"X-Service-Key": "test-service-key"},
        )

        get_data = get_response.json()
        losses = get_data["pipeline_losses"]

        # Based on complete_metrics_summary:
        # requested=50, generated=48, evaluated=48, approved=45, rejected=3
        # duplicates=3, inserted=42

        assert losses["generation_loss"] == 2  # 50 - 48
        assert losses["evaluation_loss"] == 0  # 48 - 48
        assert losses["rejection_loss"] == 3  # rejected count
        assert losses["deduplication_loss"] == 3  # duplicates found
        # insertion_loss = (approved - duplicates) - inserted = (45 - 3) - 42 = 0
        assert losses["insertion_loss"] == 0
        assert losses["total_loss"] == 8  # 50 - 42


class TestEndToEndFilteringAndSorting:
    """E2E tests for filtering and sorting functionality."""

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_filter_by_status(self, client, db_session, complete_metrics_summary):
        """Test filtering runs by status after reporting."""
        reporter = RunReporterSimulator(client, "test-service-key")

        # Report success run
        reporter.report_run(
            summary=complete_metrics_summary,
            exit_code=0,
            environment="production",
        )

        # Report failed run
        failed_summary = {
            **complete_metrics_summary,
            "execution": {
                "start_time": "2024-12-06T10:00:00+00:00",
                "end_time": "2024-12-06T10:01:00+00:00",
                "duration_seconds": 60.0,
            },
            "generation": {"requested": 50, "generated": 0, "failed": 50},
            "database": {"inserted": 0, "failed": 0},
            "overall": {
                "questions_requested": 50,
                "questions_final_output": 0,
                "overall_success_rate": 0.0,
                "total_errors": 50,
            },
        }
        reporter.report_run(
            summary=failed_summary,
            exit_code=2,
            environment="production",
        )

        # Filter by success
        success_response = client.get(
            "/v1/admin/generation-runs?status=success",
            headers={"X-Service-Key": "test-service-key"},
        )
        assert success_response.status_code == 200
        assert success_response.json()["total"] == 1
        assert success_response.json()["runs"][0]["status"] == "success"

        # Filter by failed
        failed_response = client.get(
            "/v1/admin/generation-runs?status=failed",
            headers={"X-Service-Key": "test-service-key"},
        )
        assert failed_response.status_code == 200
        assert failed_response.json()["total"] == 1
        assert failed_response.json()["runs"][0]["status"] == "failed"

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_filter_by_environment(
        self, client, db_session, complete_metrics_summary
    ):
        """Test filtering runs by environment after reporting."""
        reporter = RunReporterSimulator(client, "test-service-key")

        # Report to production
        reporter.report_run(
            summary=complete_metrics_summary,
            exit_code=0,
            environment="production",
        )

        # Report to staging
        staging_summary = {
            **complete_metrics_summary,
            "execution": {
                "start_time": "2024-12-06T10:00:00+00:00",
                "end_time": "2024-12-06T10:05:00+00:00",
                "duration_seconds": 300.0,
            },
        }
        reporter.report_run(
            summary=staging_summary,
            exit_code=0,
            environment="staging",
        )

        # Filter by production
        prod_response = client.get(
            "/v1/admin/generation-runs?environment=production",
            headers={"X-Service-Key": "test-service-key"},
        )
        assert prod_response.status_code == 200
        assert prod_response.json()["total"] == 1
        assert prod_response.json()["runs"][0]["environment"] == "production"


class TestEndToEndErrorHandling:
    """E2E tests for error handling in the complete flow."""

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_invalid_service_key(self, client, complete_metrics_summary):
        """Test that invalid service key is rejected."""
        reporter = RunReporterSimulator(client, "wrong-key")

        response = reporter.report_run(
            summary=complete_metrics_summary,
            exit_code=0,
            environment="production",
        )

        assert response.status_code == 401
        assert "Invalid service API key" in response.json()["detail"]

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_missing_required_fields(self, client):
        """Test that missing required fields are rejected."""
        # Send incomplete payload directly
        incomplete_payload = {
            "started_at": "2024-12-05T10:00:00+00:00",
            "status": "success",
            # Missing questions_requested
        }

        response = client.post(
            "/v1/admin/generation-runs",
            json=incomplete_payload,
            headers={"X-Service-Key": "test-service-key"},
        )

        assert response.status_code == 422  # Validation error

    @patch("app.core.settings.SERVICE_API_KEY", "test-service-key")
    def test_e2e_get_nonexistent_run(self, client):
        """Test retrieving a non-existent run returns 404."""
        response = client.get(
            "/v1/admin/generation-runs/99999",
            headers={"X-Service-Key": "test-service-key"},
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]
