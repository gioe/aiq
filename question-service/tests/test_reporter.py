"""Tests for RunReporter class."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import httpx

from app.reporter import RunReporter
from app.metrics import MetricsTracker


@pytest.fixture
def reporter():
    """Create a RunReporter instance for testing."""
    return RunReporter(
        backend_url="http://localhost:8000",
        service_key="test-service-key",
        timeout=10.0,
    )


@pytest.fixture
def populated_metrics_tracker():
    """Create a MetricsTracker with sample data."""
    tracker = MetricsTracker()
    tracker.start_run()

    # Record generation metrics
    tracker.record_generation_request(50)
    for _ in range(45):
        tracker.record_generation_success(
            provider="openai",
            question_type="pattern_recognition",
            difficulty="medium",
        )
    for _ in range(3):
        tracker.record_generation_failure(
            provider="openai",
            error="Rate limit exceeded",
        )

    # Record evaluation metrics
    for i in range(40):
        score = 0.7 + (i % 10) * 0.03
        approved = score >= 0.75
        tracker.record_evaluation_success(
            score=score,
            approved=approved,
            arbiter_model="openai/gpt-4",
        )

    # Record deduplication metrics
    for _ in range(35):
        tracker.record_duplicate_check(is_duplicate=False)
    for _ in range(3):
        tracker.record_duplicate_check(is_duplicate=True, duplicate_type="exact")
    for _ in range(2):
        tracker.record_duplicate_check(is_duplicate=True, duplicate_type="semantic")

    # Record database metrics
    tracker.record_insertion_success(count=30)
    tracker.record_insertion_failure(error="Duplicate key", count=2)

    tracker.end_run()
    return tracker


@pytest.fixture
def minimal_metrics_tracker():
    """Create a MetricsTracker with minimal data (failed run)."""
    tracker = MetricsTracker()
    tracker.start_run()
    tracker.record_generation_request(50)
    tracker.end_run()
    return tracker


class TestRunReporterInit:
    """Tests for RunReporter initialization."""

    def test_init_basic(self):
        """Test basic initialization."""
        reporter = RunReporter(
            backend_url="http://localhost:8000",
            service_key="test-key",
        )
        assert reporter.backend_url == "http://localhost:8000"
        assert reporter.service_key == "test-key"
        assert reporter.timeout == 30.0

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        reporter = RunReporter(
            backend_url="http://localhost:8000",
            service_key="test-key",
            timeout=60.0,
        )
        assert reporter.timeout == 60.0

    def test_init_strips_trailing_slash(self):
        """Test that trailing slash is stripped from URL."""
        reporter = RunReporter(
            backend_url="http://localhost:8000/",
            service_key="test-key",
        )
        assert reporter.backend_url == "http://localhost:8000"


class TestGetHeaders:
    """Tests for _get_headers method."""

    def test_headers_include_service_key(self, reporter):
        """Test that headers include service key."""
        headers = reporter._get_headers()
        assert headers["X-Service-Key"] == "test-service-key"
        assert headers["Content-Type"] == "application/json"


class TestDetermineStatus:
    """Tests for _determine_status method."""

    def test_status_success(self, reporter):
        """Test status determination for exit code 0."""
        status = reporter._determine_status(0, {})
        assert status == "success"

    def test_status_partial_failure(self, reporter):
        """Test status determination for exit code 3."""
        status = reporter._determine_status(3, {})
        assert status == "partial_failure"

    def test_status_failed_config_error(self, reporter):
        """Test status determination for exit code 1."""
        status = reporter._determine_status(1, {})
        assert status == "failed"

    def test_status_failed_no_questions(self, reporter):
        """Test status determination for exit code 2."""
        status = reporter._determine_status(2, {})
        assert status == "failed"

    def test_status_failed_db_error(self, reporter):
        """Test status determination for exit code 4."""
        status = reporter._determine_status(4, {})
        assert status == "failed"

    def test_status_failed_unknown_error(self, reporter):
        """Test status determination for exit code 5."""
        status = reporter._determine_status(5, {})
        assert status == "failed"

    def test_status_failed_pipeline_error(self, reporter):
        """Test status determination for exit code 6."""
        status = reporter._determine_status(6, {})
        assert status == "failed"

    def test_status_unknown_exit_code_no_questions(self, reporter):
        """Test status for unknown exit code with no questions."""
        overall = {"questions_final_output": 0, "questions_requested": 50}
        status = reporter._determine_status(99, overall)
        assert status == "failed"

    def test_status_unknown_exit_code_partial(self, reporter):
        """Test status for unknown exit code with partial output."""
        overall = {"questions_final_output": 25, "questions_requested": 50}
        status = reporter._determine_status(99, overall)
        assert status == "partial_failure"

    def test_status_unknown_exit_code_success(self, reporter):
        """Test status for unknown exit code with full output."""
        overall = {"questions_final_output": 50, "questions_requested": 50}
        status = reporter._determine_status(99, overall)
        assert status == "success"


class TestBuildProviderMetrics:
    """Tests for _build_provider_metrics method."""

    def test_build_provider_metrics_basic(self, reporter):
        """Test building provider metrics from generation and API data."""
        generation = {"by_provider": {"openai": 30, "anthropic": 20}}
        api = {"by_provider": {"openai": 35, "anthropic": 25, "google": 5}}

        result = reporter._build_provider_metrics(generation, api)

        assert result["openai"]["generated"] == 30
        assert result["openai"]["api_calls"] == 35
        assert result["anthropic"]["generated"] == 20
        assert result["anthropic"]["api_calls"] == 25
        assert result["google"]["generated"] == 0
        assert result["google"]["api_calls"] == 5

    def test_build_provider_metrics_empty(self, reporter):
        """Test building provider metrics with empty data."""
        result = reporter._build_provider_metrics({}, {})
        assert result == {}


class TestTransformMetricsToPayload:
    """Tests for _transform_metrics_to_payload method."""

    def test_transform_basic(self, reporter, populated_metrics_tracker):
        """Test basic transformation of metrics to payload."""
        summary = populated_metrics_tracker.get_summary()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
            environment="production",
            triggered_by="scheduler",
        )

        # Check required fields
        assert payload["status"] == "success"
        assert payload["exit_code"] == 0
        assert payload["questions_requested"] == 50
        assert payload["environment"] == "production"
        assert payload["triggered_by"] == "scheduler"

        # Check optional fields
        assert "started_at" in payload
        assert "completed_at" in payload
        assert "duration_seconds" in payload
        assert "provider_metrics" in payload
        assert "type_metrics" in payload
        assert "difficulty_metrics" in payload

    def test_transform_with_config_versions(self, reporter, populated_metrics_tracker):
        """Test transformation with configuration versions."""
        summary = populated_metrics_tracker.get_summary()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
            prompt_version="v2.1",
            arbiter_config_version="v1.0",
            min_arbiter_score_threshold=0.75,
        )

        assert payload["prompt_version"] == "v2.1"
        assert payload["arbiter_config_version"] == "v1.0"
        assert payload["min_arbiter_score_threshold"] == 0.75

    def test_transform_failed_run(self, reporter, minimal_metrics_tracker):
        """Test transformation of a failed run."""
        summary = minimal_metrics_tracker.get_summary()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=2,
        )

        assert payload["status"] == "failed"
        assert payload["exit_code"] == 2
        assert payload["questions_requested"] == 50
        assert payload["questions_generated"] == 0
        assert payload["questions_inserted"] == 0


class TestReportRun:
    """Tests for report_run method."""

    def test_report_run_success(self, reporter, populated_metrics_tracker):
        """Test successful run reporting."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 123, "status": "success"}

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                metrics_tracker=populated_metrics_tracker,
                exit_code=0,
                environment="production",
                triggered_by="scheduler",
            )

            assert result == 123
            mock_client_instance.post.assert_called_once()

    def test_report_run_http_error(self, reporter, populated_metrics_tracker):
        """Test run reporting with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                metrics_tracker=populated_metrics_tracker,
                exit_code=0,
            )

            assert result is None

    def test_report_run_connection_error(self, reporter, populated_metrics_tracker):
        """Test run reporting with connection error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                metrics_tracker=populated_metrics_tracker,
                exit_code=0,
            )

            assert result is None

    def test_report_run_timeout_error(self, reporter, populated_metrics_tracker):
        """Test run reporting with timeout error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.TimeoutException(
                "Request timed out"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                metrics_tracker=populated_metrics_tracker,
                exit_code=0,
            )

            assert result is None

    def test_report_run_unexpected_error(self, reporter, populated_metrics_tracker):
        """Test run reporting with unexpected error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = Exception("Unexpected error")
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                metrics_tracker=populated_metrics_tracker,
                exit_code=0,
            )

            assert result is None


class TestReportRunning:
    """Tests for report_running method."""

    def test_report_running_success(self, reporter):
        """Test successful running status reporting."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 456, "status": "running"}

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_running(
                started_at=datetime.now(timezone.utc),
                questions_requested=50,
                environment="production",
                triggered_by="manual",
            )

            assert result == 456
            mock_client_instance.post.assert_called_once()

            # Verify payload structure
            call_kwargs = mock_client_instance.post.call_args[1]
            payload = call_kwargs["json"]
            assert payload["status"] == "running"
            assert payload["questions_requested"] == 50
            assert payload["environment"] == "production"
            assert payload["triggered_by"] == "manual"

    def test_report_running_http_error(self, reporter):
        """Test running status reporting with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_running(
                started_at=datetime.now(timezone.utc),
                questions_requested=50,
            )

            assert result is None

    def test_report_running_connection_error(self, reporter):
        """Test running status reporting with connection error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_running(
                started_at=datetime.now(timezone.utc),
                questions_requested=50,
            )

            assert result is None


class TestEndToEnd:
    """End-to-end tests for RunReporter."""

    def test_full_workflow(self, reporter):
        """Test full workflow of creating tracker, populating, and reporting."""
        # Create and populate tracker
        tracker = MetricsTracker()
        tracker.start_run()
        tracker.record_generation_request(10)

        for i in range(8):
            tracker.record_generation_success(
                provider="anthropic" if i % 2 == 0 else "openai",
                question_type="logical_reasoning",
                difficulty="hard",
            )

        for i in range(8):
            tracker.record_evaluation_success(
                score=0.8 + i * 0.01,
                approved=True,
                arbiter_model="anthropic/claude-3-haiku",
            )

        for _ in range(8):
            tracker.record_duplicate_check(is_duplicate=False)

        tracker.record_insertion_success(count=8)
        tracker.end_run()

        # Mock successful report
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 789, "status": "success"}

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                metrics_tracker=tracker,
                exit_code=0,
                environment="development",
                triggered_by="manual",
                prompt_version="v1.0",
            )

            assert result == 789

            # Verify the payload was correctly structured
            call_kwargs = mock_client_instance.post.call_args[1]
            payload = call_kwargs["json"]

            assert payload["status"] == "success"
            assert payload["questions_requested"] == 10
            assert payload["questions_generated"] == 8
            assert payload["questions_inserted"] == 8
            assert payload["environment"] == "development"
            assert payload["triggered_by"] == "manual"
            assert payload["prompt_version"] == "v1.0"
            assert "provider_metrics" in payload
            assert "anthropic" in payload["provider_metrics"]
            assert "openai" in payload["provider_metrics"]
