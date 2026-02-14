"""Tests for RunReporter class."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import httpx

from app.reporting.reporter import RunReporter
from app.reporting.run_summary import RunSummary


@pytest.fixture
def reporter():
    """Create a RunReporter instance for testing."""
    return RunReporter(
        backend_url="http://localhost:8000",
        service_key="test-service-key",
        timeout=10.0,
    )


@pytest.fixture
def populated_summary_dict():
    """Create a RunSummary with sample data, return its summary dict."""
    s = RunSummary()
    s.start_run()

    # Record generation metrics
    s.questions_requested = 50
    for _ in range(45):
        s.record_generation_success(
            provider="openai",
            question_type="pattern_recognition",
            difficulty="medium",
        )
    s.generation_failures = 3

    # Record evaluation metrics
    for i in range(40):
        score = 0.7 + (i % 10) * 0.03
        approved = score >= 0.75
        s.record_evaluation_success(
            score=score,
            approved=approved,
            judge_model="openai/gpt-4",
        )

    # Record deduplication metrics
    for _ in range(35):
        s.record_duplicate_check(is_duplicate=False)
    for _ in range(3):
        s.record_duplicate_check(is_duplicate=True, duplicate_type="exact")
    for _ in range(2):
        s.record_duplicate_check(is_duplicate=True, duplicate_type="semantic")

    # Record database metrics
    s.record_insertion_success(count=30)
    s.record_insertion_failure(count=2)

    s.end_run()
    return s.to_summary_dict()


@pytest.fixture
def minimal_summary_dict():
    """Create a RunSummary with minimal data (failed run), return its summary dict."""
    s = RunSummary()
    s.start_run()
    s.questions_requested = 50
    s.end_run()
    return s.to_summary_dict()


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
        assert reporter.timeout == pytest.approx(30.0)

    def test_init_with_custom_timeout(self):
        """Test initialization with custom timeout."""
        reporter = RunReporter(
            backend_url="http://localhost:8000",
            service_key="test-key",
            timeout=60.0,
        )
        assert reporter.timeout == pytest.approx(60.0)

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

    def test_transform_basic(self, reporter, populated_summary_dict):
        """Test basic transformation of metrics to payload."""
        summary = populated_summary_dict
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

    def test_transform_with_config_versions(self, reporter, populated_summary_dict):
        """Test transformation with configuration versions."""
        summary = populated_summary_dict
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
            prompt_version="v2.1",
            judge_config_version="v1.0",
            min_judge_score_threshold=0.75,
        )

        assert payload["prompt_version"] == "v2.1"
        assert payload["judge_config_version"] == "v1.0"
        assert payload["min_judge_score_threshold"] == pytest.approx(0.75)

    def test_transform_failed_run(self, reporter, minimal_summary_dict):
        """Test transformation of a failed run."""
        summary = minimal_summary_dict
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

    def test_report_run_success(self, reporter, populated_summary_dict):
        """Test successful run reporting."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {"id": 123, "status": "success"}

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
                environment="production",
                triggered_by="scheduler",
            )

            assert result == 123
            mock_client_instance.post.assert_called_once()

    def test_report_run_http_error(self, reporter, populated_summary_dict):
        """Test run reporting with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert result is None

    def test_report_run_connection_error(self, reporter, populated_summary_dict):
        """Test run reporting with connection error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.ConnectError(
                "Connection refused"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert result is None

    def test_report_run_timeout_error(self, reporter, populated_summary_dict):
        """Test run reporting with timeout error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.TimeoutException(
                "Request timed out"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert result is None

    def test_report_run_unexpected_error(self, reporter, populated_summary_dict):
        """Test run reporting with unexpected error."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = Exception("Unexpected error")
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_run(
                summary=populated_summary_dict,
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
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 10

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
                judge_model="anthropic/claude-3-haiku",
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
                summary=tracker.to_summary_dict(),
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


class TestIntegrationScenarios:
    """Integration tests verifying complete request/response scenarios."""

    def test_report_run_complete_scenario(self, populated_summary_dict):
        """Test report_run with complete request verification."""
        captured_data = {}

        def capture_post(url, json=None, headers=None):
            captured_data["url"] = url
            captured_data["json"] = json
            captured_data["headers"] = headers
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 999, "status": "success"}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_post
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://test-backend.local:8000",
                service_key="integration-test-key",
                timeout=5.0,
            )

            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
                environment="staging",
                triggered_by="webhook",
            )

            # Verify the result
            assert result == 999

            # Verify URL construction
            assert (
                captured_data["url"]
                == "http://test-backend.local:8000/v1/admin/generation-runs"
            )

            # Verify headers
            assert captured_data["headers"]["X-Service-Key"] == "integration-test-key"
            assert captured_data["headers"]["Content-Type"] == "application/json"

            # Verify payload structure
            payload = captured_data["json"]
            assert payload["status"] == "success"
            assert payload["environment"] == "staging"
            assert payload["triggered_by"] == "webhook"
            assert payload["exit_code"] == 0
            assert payload["questions_requested"] == 50
            assert "started_at" in payload
            assert "completed_at" in payload

    def test_report_running_complete_scenario(self):
        """Test report_running with complete request verification."""
        captured_data = {}

        def capture_post(url, json=None, headers=None):
            captured_data["url"] = url
            captured_data["json"] = json
            captured_data["headers"] = headers
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1000, "status": "running"}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_post
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://test.local",
                service_key="test-key",
            )

            started_at = datetime(2024, 12, 1, 10, 30, 0, tzinfo=timezone.utc)
            result = reporter.report_running(
                started_at=started_at,
                questions_requested=100,
                environment="production",
                triggered_by="scheduler",
            )

            # Verify the result
            assert result == 1000

            # Verify datetime serialization
            assert "started_at" in captured_data["json"]
            assert "2024-12-01" in captured_data["json"]["started_at"]
            assert captured_data["json"]["status"] == "running"
            assert captured_data["json"]["questions_requested"] == 100
            assert captured_data["json"]["environment"] == "production"
            assert captured_data["json"]["triggered_by"] == "scheduler"

    def test_report_run_with_all_configuration_options(self, populated_summary_dict):
        """Test report_run with all configuration options provided."""
        captured_data = {}

        def capture_post(url, json=None, headers=None):
            captured_data["json"] = json
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 123}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_post
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://api.example.com",
                service_key="full-test-key",
                timeout=60.0,
            )

            reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
                environment="production",
                triggered_by="scheduler",
                prompt_version="v2.1",
                judge_config_version="v1.5",
                min_judge_score_threshold=0.80,
            )

            payload = captured_data["json"]

            # Verify all configuration options are present
            assert payload["environment"] == "production"
            assert payload["triggered_by"] == "scheduler"
            assert payload["prompt_version"] == "v2.1"
            assert payload["judge_config_version"] == "v1.5"
            assert payload["min_judge_score_threshold"] == pytest.approx(0.80)

    def test_report_run_verifies_metrics_content(self):
        """Test that report_run correctly transforms all metric categories."""
        captured_data = {}

        def capture_post(url, json=None, headers=None):
            captured_data["json"] = json
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 456}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_post
            mock_client.return_value.__enter__.return_value = mock_client_instance

            # Create a detailed tracker with all metric types
            tracker = RunSummary()
            tracker.start_run()
            tracker.questions_requested = 20

            # Generation metrics
            for _ in range(15):
                tracker.record_generation_success(
                    provider="openai",
                    question_type="pattern_recognition",
                    difficulty="medium",
                )
            tracker.generation_failures = 5

            # Evaluation metrics
            for i in range(15):
                score = 0.6 + (i * 0.02)
                tracker.record_evaluation_success(
                    score=score,
                    approved=score >= 0.7,
                    judge_model="openai/gpt-4",
                )

            # Deduplication metrics
            for _ in range(10):
                tracker.record_duplicate_check(is_duplicate=False)
            for _ in range(2):
                tracker.record_duplicate_check(
                    is_duplicate=True, duplicate_type="exact"
                )

            # Database metrics
            tracker.record_insertion_success(count=8)
            tracker.record_insertion_failure(count=2)

            tracker.end_run()

            reporter = RunReporter(
                backend_url="http://test.local",
                service_key="key",
            )

            reporter.report_run(
                summary=tracker.to_summary_dict(),
                exit_code=0,
            )

            payload = captured_data["json"]

            # Verify generation metrics
            assert payload["questions_requested"] == 20
            assert payload["questions_generated"] == 15
            assert payload["generation_failures"] == 5

            # Verify evaluation metrics
            assert payload["questions_evaluated"] == 15
            assert payload["questions_approved"] > 0
            assert payload["questions_rejected"] >= 0
            assert payload["avg_judge_score"] is not None

            # Verify deduplication metrics
            assert payload["duplicates_found"] == 2
            assert payload["exact_duplicates"] == 2

            # Verify database metrics
            assert payload["questions_inserted"] == 8
            assert payload["insertion_failures"] == 2

            # Verify provider metrics
            assert payload["provider_metrics"] is not None
            assert "openai" in payload["provider_metrics"]


class TestPayloadTransformationEdgeCases:
    """Tests for edge cases in payload transformation."""

    def test_transform_with_zero_questions(self, reporter):
        """Test transformation when no questions were requested."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 0
        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=2,
        )

        assert payload["questions_requested"] == 0
        assert payload["questions_generated"] == 0
        assert payload["generation_success_rate"] == pytest.approx(0.0)
        assert payload["overall_success_rate"] == pytest.approx(0.0)

    def test_transform_with_all_failures(self, reporter):
        """Test transformation when all generation attempts failed."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 10
        tracker.generation_failures = 10
        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=2,
        )

        assert payload["questions_requested"] == 10
        assert payload["questions_generated"] == 0
        assert payload["generation_failures"] == 10
        assert payload["status"] == "failed"

    def test_transform_with_all_duplicates(self, reporter):
        """Test transformation when all questions are duplicates."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 5
        for _ in range(5):
            tracker.record_generation_success(
                provider="anthropic",
                question_type="pattern_recognition",
                difficulty="easy",
            )
        for _ in range(5):
            tracker.record_evaluation_success(
                score=0.85,
                approved=True,
                judge_model="openai/gpt-4",
            )
        for _ in range(5):
            tracker.record_duplicate_check(is_duplicate=True, duplicate_type="semantic")
        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=3,
        )

        assert payload["duplicates_found"] == 5
        assert payload["semantic_duplicates"] == 5
        assert payload["duplicate_rate"] == pytest.approx(1.0)
        assert payload["questions_inserted"] == 0

    def test_transform_with_extreme_scores(self, reporter):
        """Test transformation with extreme judge scores."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 3
        for _ in range(3):
            tracker.record_generation_success(
                provider="google",
                question_type="mathematical",
                difficulty="hard",
            )
        # Record scores at extremes
        tracker.record_evaluation_success(score=0.0, approved=False, judge_model="a/b")
        tracker.record_evaluation_success(score=0.5, approved=False, judge_model="a/b")
        tracker.record_evaluation_success(score=1.0, approved=True, judge_model="a/b")
        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        assert payload["min_judge_score"] == pytest.approx(0.0)
        assert payload["max_judge_score"] == pytest.approx(1.0)
        assert payload["avg_judge_score"] == pytest.approx(0.5)

    def test_transform_with_missing_optional_sections(self, reporter):
        """Test transformation handles missing optional sections gracefully."""
        # Create a minimal summary with missing sections
        summary = {
            "execution": {
                "start_time": None,
                "end_time": None,
                "duration_seconds": 0,
            },
            "generation": {
                "requested": 0,
                "generated": 0,
                "failed": 0,
            },
            "evaluation": {},
            "deduplication": {},
            "database": {},
            "api": {},
            "error_classification": {},
            "overall": {},
        }

        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        # Should not raise and should have default values
        assert payload["questions_evaluated"] == 0
        assert payload["duplicates_found"] == 0
        assert payload["questions_inserted"] == 0
        assert payload["total_api_calls"] == 0

    def test_transform_with_multiple_providers(self, reporter):
        """Test transformation with questions from multiple providers."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 12

        providers = ["openai", "anthropic", "google", "xai"]
        for i, provider in enumerate(providers):
            for _ in range(3):
                tracker.record_generation_success(
                    provider=provider,
                    question_type="verbal_reasoning",
                    difficulty="medium",
                )

        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        assert payload["provider_metrics"] is not None
        for provider in providers:
            assert provider in payload["provider_metrics"]
            assert payload["provider_metrics"][provider]["generated"] == 3

    def test_transform_with_mixed_difficulties(self, reporter):
        """Test transformation with mixed difficulty levels."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 6

        for diff in ["easy", "easy", "medium", "medium", "hard", "hard"]:
            tracker.record_generation_success(
                provider="openai",
                question_type="pattern",  # Use canonical value
                difficulty=diff,
            )

        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        assert payload["difficulty_metrics"] == {"easy": 2, "medium": 2, "hard": 2}

    def test_transform_with_mixed_question_types(self, reporter):
        """Test transformation with mixed question types normalizes legacy values.

        Legacy question type values (e.g., "pattern_recognition") should be
        normalized to canonical backend values (e.g., "pattern") in the payload.
        """
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 6

        legacy_types = [
            "pattern_recognition",
            "logical_reasoning",
            "spatial_reasoning",
            "mathematical",
            "verbal_reasoning",
            "memory",
        ]
        for qt in legacy_types:
            tracker.record_generation_success(
                provider="anthropic",
                question_type=qt,
                difficulty="medium",
            )

        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        # Legacy values should be normalized to canonical backend values
        assert payload["type_metrics"] is not None
        expected_canonical = {
            "pattern": 1,  # from pattern_recognition
            "logic": 1,  # from logical_reasoning
            "spatial": 1,  # from spatial_reasoning
            "math": 1,  # from mathematical
            "verbal": 1,  # from verbal_reasoning
            "memory": 1,  # unchanged (already canonical)
        }
        assert payload["type_metrics"] == expected_canonical


class TestGracefulFailureHandling:
    """Tests for graceful failure handling in RunReporter."""

    def test_report_run_logs_connection_error(self, reporter, populated_summary_dict):
        """Test that connection errors are logged, not raised."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.ConnectError(
                "Network unreachable"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            # Should not raise exception
            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert result is None

    def test_report_running_logs_timeout(self, reporter):
        """Test that timeout errors are logged, not raised."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = httpx.TimeoutException(
                "Request timed out after 30s"
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_running(
                started_at=datetime.now(timezone.utc),
                questions_requested=50,
            )

            assert result is None

    def test_report_run_handles_malformed_response(
        self, reporter, populated_summary_dict
    ):
        """Test handling of malformed JSON response."""
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            # Should handle the exception gracefully
            result = reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert result is None

    def test_report_run_handles_4xx_errors(self, reporter, populated_summary_dict):
        """Test handling of 4xx client errors."""
        for status_code in [400, 401, 403, 404, 422]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = f"Error {status_code}"

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = reporter.report_run(
                    summary=populated_summary_dict,
                    exit_code=0,
                )

                assert result is None, f"Expected None for status code {status_code}"

    def test_report_run_handles_5xx_errors(self, reporter, populated_summary_dict):
        """Test handling of 5xx server errors."""
        for status_code in [500, 502, 503, 504]:
            mock_response = MagicMock()
            mock_response.status_code = status_code
            mock_response.text = f"Server Error {status_code}"

            with patch("httpx.Client") as mock_client:
                mock_client_instance = MagicMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__enter__.return_value = mock_client_instance

                result = reporter.report_run(
                    summary=populated_summary_dict,
                    exit_code=0,
                )

                assert result is None, f"Expected None for status code {status_code}"

    def test_report_running_handles_http_status_error(self, reporter):
        """Test handling of HTTPStatusError exception."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            request = httpx.Request(
                "POST", "http://test.local/v1/admin/generation-runs"
            )
            response = httpx.Response(500, request=request)
            mock_client_instance.post.side_effect = httpx.HTTPStatusError(
                "Server Error", request=request, response=response
            )
            mock_client.return_value.__enter__.return_value = mock_client_instance

            result = reporter.report_running(
                started_at=datetime.now(timezone.utc),
                questions_requested=50,
            )

            assert result is None


class TestURLConstruction:
    """Tests for URL construction and endpoint handling."""

    def test_url_construction_basic(self):
        """Test basic URL construction."""
        reporter = RunReporter(
            backend_url="http://api.example.com",
            service_key="key",
        )
        # The URL used in report_run should be correctly constructed
        assert reporter.backend_url == "http://api.example.com"

    def test_url_construction_with_trailing_slash(self):
        """Test URL construction strips trailing slash."""
        reporter = RunReporter(
            backend_url="http://api.example.com/",
            service_key="key",
        )
        assert reporter.backend_url == "http://api.example.com"

    def test_url_construction_with_port(self):
        """Test URL construction with port number."""
        reporter = RunReporter(
            backend_url="http://localhost:8080",
            service_key="key",
        )
        assert reporter.backend_url == "http://localhost:8080"

    def test_url_construction_https(self):
        """Test URL construction with HTTPS."""
        reporter = RunReporter(
            backend_url="https://secure.example.com",
            service_key="key",
        )
        assert reporter.backend_url == "https://secure.example.com"

    def test_full_endpoint_url_used(self, populated_summary_dict):
        """Test that the full endpoint URL is correctly used in requests."""
        captured_url = None

        def capture_url(*args, **kwargs):
            nonlocal captured_url
            captured_url = args[0] if args else kwargs.get("url")
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_url
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://backend.test.local:9000",
                service_key="key",
            )

            reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert (
                captured_url
                == "http://backend.test.local:9000/v1/admin/generation-runs"
            )


class TestHeaderHandling:
    """Tests for HTTP header handling."""

    def test_service_key_header_included(self, populated_summary_dict):
        """Test that X-Service-Key header is included in requests."""
        captured_headers = None

        def capture_headers(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_headers
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://test.local",
                service_key="my-secret-service-key",
            )

            reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert captured_headers["X-Service-Key"] == "my-secret-service-key"

    def test_content_type_header_included(self, populated_summary_dict):
        """Test that Content-Type header is set to application/json."""
        captured_headers = None

        def capture_headers(*args, **kwargs):
            nonlocal captured_headers
            captured_headers = kwargs.get("headers", {})
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_headers
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://test.local",
                service_key="key",
            )

            reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            assert captured_headers["Content-Type"] == "application/json"


class TestErrorSummaryTransformation:
    """Tests for error summary transformation in payloads."""

    def test_error_summary_with_classified_errors(self, reporter):
        """Test error summary includes classified error information."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 5
        tracker.generation_failures = 1
        tracker.errors_by_category["rate_limit"] = 1
        tracker.errors_by_severity["high"] = 1

        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=3,
        )

        assert payload["error_summary"] is not None
        assert "by_category" in payload["error_summary"]
        assert "by_severity" in payload["error_summary"]

    def test_error_summary_empty_when_no_errors(self, reporter):
        """Test error summary is None when no errors occurred."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 1
        tracker.record_generation_success(
            provider="openai",
            question_type="pattern_recognition",
            difficulty="easy",
        )
        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        # Error summary should be None when empty
        assert payload["error_summary"] is None


class TestDatetimeSerialization:
    """Tests for datetime serialization in payloads."""

    def test_datetime_serialized_as_iso_format(self, reporter):
        """Test that datetime fields are serialized as ISO format strings."""
        tracker = RunSummary()
        tracker.start_run()
        tracker.questions_requested = 1
        tracker.end_run()

        summary = tracker.to_summary_dict()
        payload = reporter._transform_metrics_to_payload(
            summary=summary,
            exit_code=0,
        )

        # Check that timestamps are ISO format strings
        assert isinstance(payload["started_at"], str)
        assert isinstance(payload["completed_at"], str)
        # Should be parseable as ISO format
        datetime.fromisoformat(payload["started_at"].replace("Z", "+00:00"))
        datetime.fromisoformat(payload["completed_at"].replace("Z", "+00:00"))

    def test_report_running_datetime_serialization(self, reporter):
        """Test datetime serialization in report_running."""
        captured_payload = None

        def capture_payload(*args, **kwargs):
            nonlocal captured_payload
            captured_payload = kwargs.get("json", {})
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1}
            return mock_response

        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client_instance.post.side_effect = capture_payload
            mock_client.return_value.__enter__.return_value = mock_client_instance

            test_time = datetime(2024, 6, 15, 14, 30, 45, tzinfo=timezone.utc)
            reporter.report_running(
                started_at=test_time,
                questions_requested=50,
            )

            assert "started_at" in captured_payload
            assert "2024-06-15" in captured_payload["started_at"]
            assert "14:30:45" in captured_payload["started_at"]


class TestTimeoutConfiguration:
    """Tests for timeout configuration."""

    def test_default_timeout(self):
        """Test default timeout is 30 seconds."""
        reporter = RunReporter(
            backend_url="http://test.local",
            service_key="key",
        )
        assert reporter.timeout == pytest.approx(30.0)

    def test_custom_timeout(self):
        """Test custom timeout configuration."""
        reporter = RunReporter(
            backend_url="http://test.local",
            service_key="key",
            timeout=120.0,
        )
        assert reporter.timeout == pytest.approx(120.0)

    def test_timeout_passed_to_client(self, populated_summary_dict):
        """Test that timeout is passed to httpx.Client."""
        with patch("httpx.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_response = MagicMock()
            mock_response.status_code = 201
            mock_response.json.return_value = {"id": 1}
            mock_client_instance.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value = mock_client_instance

            reporter = RunReporter(
                backend_url="http://test.local",
                service_key="key",
                timeout=45.0,
            )

            reporter.report_run(
                summary=populated_summary_dict,
                exit_code=0,
            )

            # Verify Client was instantiated with timeout
            mock_client.assert_called_with(timeout=45.0)
