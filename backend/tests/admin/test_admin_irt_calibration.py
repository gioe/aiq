"""
Tests for IRT calibration admin endpoints (TASK-862).

These tests verify the API endpoints for triggering and monitoring IRT calibration jobs:
- POST /v1/admin/calibration/run - Trigger calibration
- GET /v1/admin/calibration/status/{job_id} - Check job status
"""
import threading
import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.cat.calibration_runner import calibration_runner
from app.core.config import settings
from tests.conftest import create_test_app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(create_test_app())


@pytest.fixture
def admin_headers():
    """Return headers with valid admin token."""
    return {"X-Admin-Token": settings.ADMIN_TOKEN}


@pytest.fixture
def clean_calibration_runner():
    """Clean the global calibration runner before and after each test.

    Instead of creating a new runner, we clean the global one
    since the endpoints use the global calibration_runner singleton.
    """
    # Clean up any existing state
    with calibration_runner._lock:
        calibration_runner._jobs.clear()
        calibration_runner._current_running_job_id = None

    yield calibration_runner

    # Cleanup after test
    with calibration_runner._lock:
        calibration_runner._jobs.clear()
        calibration_runner._current_running_job_id = None


class TestTriggerCalibrationEndpoint:
    """Tests for POST /v1/admin/calibration/run endpoint."""

    def test_trigger_calibration_requires_auth(self, client, clean_calibration_runner):
        """Test that triggering calibration without auth token fails."""
        response = client.post("/v1/admin/calibration/run")
        # 422 is returned when the required X-Admin-Token header is missing
        assert response.status_code in (401, 403, 422)

    @patch("app.core.cat.calibration_runner.SessionLocal")
    @patch("app.core.cat.calibration_runner.run_calibration_job")
    def test_trigger_calibration_returns_job_id(
        self,
        mock_run_calibration,
        mock_session_local,
        client,
        admin_headers,
        clean_calibration_runner,
    ):
        """Test that triggering calibration returns job ID and status."""
        # Mock the calibration job to return immediately
        mock_run_calibration.return_value = {
            "calibrated": 5,
            "skipped": 2,
            "mean_difficulty": 0.3,
            "mean_discrimination": 1.2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_session_local.return_value = MagicMock()

        response = client.post("/v1/admin/calibration/run", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert data["status"] == "running"
        assert data["message"] == "IRT calibration job started."
        assert "irt_calibration_" in data["job_id"]

    @patch("app.core.cat.calibration_runner.SessionLocal")
    @patch("app.core.cat.calibration_runner.run_calibration_job")
    def test_concurrent_calibration_returns_429(
        self,
        mock_run_calibration,
        mock_session_local,
        client,
        admin_headers,
        clean_calibration_runner,
    ):
        """Test that concurrent calibration requests return 429."""
        # Use an event to keep the first job "running"
        job_started = threading.Event()
        job_should_finish = threading.Event()

        def long_running_calibration(*args, **kwargs):
            job_started.set()
            job_should_finish.wait(timeout=5)
            return {
                "calibrated": 5,
                "skipped": 2,
                "mean_difficulty": 0.3,
                "mean_discrimination": 1.2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        mock_run_calibration.side_effect = long_running_calibration
        mock_session_local.return_value = MagicMock()

        # Start first job
        response1 = client.post("/v1/admin/calibration/run", headers=admin_headers)
        assert response1.status_code == 200

        # Wait for the job to actually start
        job_started.wait(timeout=2)
        time.sleep(0.1)  # Brief pause to ensure thread is running

        try:
            # Try to start second job - should fail with 429
            response2 = client.post("/v1/admin/calibration/run", headers=admin_headers)
            assert response2.status_code == 429
            assert "already running" in response2.json()["detail"]
        finally:
            # Let the first job finish
            job_should_finish.set()
            time.sleep(0.5)  # Wait for cleanup

    @patch("app.core.cat.calibration_runner.SessionLocal")
    @patch("app.core.cat.calibration_runner.run_calibration_job")
    def test_trigger_with_custom_params(
        self,
        mock_run_calibration,
        mock_session_local,
        client,
        admin_headers,
        clean_calibration_runner,
    ):
        """Test triggering calibration with custom parameters."""
        mock_run_calibration.return_value = {
            "calibrated": 3,
            "skipped": 0,
            "mean_difficulty": 0.5,
            "mean_discrimination": 1.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_session_local.return_value = MagicMock()

        # Custom request parameters
        request_data = {
            "question_ids": [1, 2, 3],
            "min_responses": 100,
            "bootstrap_se": False,
        }

        response = client.post(
            "/v1/admin/calibration/run",
            headers=admin_headers,
            json=request_data,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"

        # Verify the mock was called with correct params (once thread runs)
        time.sleep(0.5)
        assert mock_run_calibration.called


class TestCalibrationStatusEndpoint:
    """Tests for GET /v1/admin/calibration/status/{job_id} endpoint."""

    def test_status_unknown_job_returns_404(
        self, client, admin_headers, clean_calibration_runner
    ):
        """Test getting status of unknown job returns 404."""
        response = client.get(
            "/v1/admin/calibration/status/nonexistent_job_id",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_status_requires_auth(self, client, clean_calibration_runner):
        """Test that getting status without auth token fails."""
        response = client.get("/v1/admin/calibration/status/some_job_id")
        # 422 is returned when the required X-Admin-Token header is missing
        assert response.status_code in (401, 403, 422)

    @patch("app.core.cat.calibration_runner.SessionLocal")
    @patch("app.core.cat.calibration_runner.run_calibration_job")
    def test_completed_job_shows_results(
        self,
        mock_run_calibration,
        mock_session_local,
        client,
        admin_headers,
        clean_calibration_runner,
    ):
        """Test that completed job shows full results."""
        # Mock calibration to return immediately
        mock_run_calibration.return_value = {
            "calibrated": 10,
            "skipped": 3,
            "mean_difficulty": 0.4,
            "mean_discrimination": 1.5,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        mock_session_local.return_value = MagicMock()

        # Start job
        response = client.post("/v1/admin/calibration/run", headers=admin_headers)
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        # Wait for job to complete
        time.sleep(0.5)

        # Check status
        response = client.get(
            f"/v1/admin/calibration/status/{job_id}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "completed"
        assert data["calibrated"] == 10
        assert data["skipped"] == 3
        assert data["mean_difficulty"] == pytest.approx(0.4)
        assert data["mean_discrimination"] == pytest.approx(1.5)
        assert data["duration_seconds"] is not None
        assert data["duration_seconds"] > 0
        assert data["error_message"] is None

    @patch("app.core.cat.calibration_runner.SessionLocal")
    @patch("app.core.cat.calibration_runner.run_calibration_job")
    def test_running_job_shows_status(
        self,
        mock_run_calibration,
        mock_session_local,
        client,
        admin_headers,
        clean_calibration_runner,
    ):
        """Test that running job shows running status."""
        # Use an event to keep the job running
        job_should_finish = threading.Event()

        def long_running_calibration(*args, **kwargs):
            job_should_finish.wait(timeout=5)
            return {
                "calibrated": 5,
                "skipped": 2,
                "mean_difficulty": 0.3,
                "mean_discrimination": 1.2,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        mock_run_calibration.side_effect = long_running_calibration
        mock_session_local.return_value = MagicMock()

        # Start job
        response = client.post("/v1/admin/calibration/run", headers=admin_headers)
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        # Brief pause to ensure thread is running
        time.sleep(0.1)

        try:
            # Check status while running
            response = client.get(
                f"/v1/admin/calibration/status/{job_id}",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_id
            assert data["status"] == "running"
            assert data["completed_at"] is None
            assert data["duration_seconds"] is None
            assert data["calibrated"] is None
        finally:
            # Let the job finish
            job_should_finish.set()
            time.sleep(0.5)

    @patch("app.core.cat.calibration_runner.SessionLocal")
    @patch("app.core.cat.calibration_runner.run_calibration_job")
    def test_failed_job_shows_error(
        self,
        mock_run_calibration,
        mock_session_local,
        client,
        admin_headers,
        clean_calibration_runner,
    ):
        """Test that failed job shows error message."""
        from app.core.cat.calibration import CalibrationError

        # Mock calibration to raise an error
        mock_run_calibration.side_effect = CalibrationError(
            "Insufficient data for calibration",
            context={"n_items": 1},
        )
        mock_session_local.return_value = MagicMock()

        # Start job
        response = client.post("/v1/admin/calibration/run", headers=admin_headers)
        assert response.status_code == 200
        job_id = response.json()["job_id"]

        # Wait for job to fail
        time.sleep(0.5)

        # Check status
        response = client.get(
            f"/v1/admin/calibration/status/{job_id}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"] == job_id
        assert data["status"] == "failed"
        assert data["error_message"] is not None
        assert "Insufficient data" in data["error_message"]
        assert data["calibrated"] is None
