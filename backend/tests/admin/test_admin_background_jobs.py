"""
Tests for admin background-jobs endpoints (BCQ-036).

These tests verify the API endpoints for managing background generation jobs:
- List running jobs
- Get job status
- Get job statistics
- Terminate jobs
- Cleanup finished jobs
"""
import subprocess
import sys

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.process_registry import process_registry
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
def clean_registry():
    """Clean the global process registry before and after each test.

    Instead of creating a new registry, we clean the global one
    since the endpoints use the global process_registry singleton.
    """
    # Clean up any existing processes from previous tests
    process_registry.cleanup_finished()
    process_registry.shutdown_all(timeout=2.0)

    # Reset the internal state
    with process_registry._registry_lock:
        process_registry._processes.clear()

    yield process_registry

    # Cleanup after test
    process_registry.shutdown_all(timeout=2.0)
    with process_registry._registry_lock:
        process_registry._processes.clear()


class TestBackgroundJobsListEndpoint:
    """Tests for GET /v1/admin/background-jobs endpoint."""

    def test_list_jobs_empty(self, client, admin_headers, clean_registry):
        """Test listing jobs when no jobs are registered."""
        response = client.get("/v1/admin/background-jobs", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["jobs"] == []
        assert data["total"] == 0
        assert data["running"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0

    def test_list_jobs_with_running_job(self, client, admin_headers, clean_registry):
        """Test listing jobs with a running job."""
        # Create a subprocess that sleeps
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Register in the registry
            clean_registry.register(
                process=process,
                job_type="test_job",
                command=["python", "-c", "import time; time.sleep(60)"],
                metadata={"test": True},
            )

            response = client.get("/v1/admin/background-jobs", headers=admin_headers)

            assert response.status_code == 200
            data = response.json()
            assert len(data["jobs"]) == 1
            assert data["total"] == 1
            assert data["running"] == 1
            assert data["jobs"][0]["status"] == "running"
            assert data["jobs"][0]["job_type"] == "test_job"
            assert data["jobs"][0]["metadata"] == {"test": True}
        finally:
            process.terminate()
            process.wait()

    def test_list_jobs_filter_by_status(self, client, admin_headers, clean_registry):
        """Test filtering jobs by status."""
        # Create one completed and one running job
        completed_process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        running_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            clean_registry.register(process=completed_process, job_type="quick")
            clean_registry.register(process=running_process, job_type="slow")

            # Wait for completed process
            completed_process.wait()

            # Filter by running status
            response = client.get(
                "/v1/admin/background-jobs?status=running",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["jobs"]) == 1
            assert data["jobs"][0]["job_type"] == "slow"
        finally:
            running_process.terminate()
            running_process.wait()

    def test_list_jobs_filter_by_type(self, client, admin_headers, clean_registry):
        """Test filtering jobs by job type."""
        process1 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process2 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            clean_registry.register(process=process1, job_type="type_a")
            clean_registry.register(process=process2, job_type="type_b")

            # Filter by type_a
            response = client.get(
                "/v1/admin/background-jobs?job_type=type_a",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert len(data["jobs"]) == 1
            assert data["jobs"][0]["job_type"] == "type_a"
        finally:
            process1.terminate()
            process2.terminate()
            process1.wait()
            process2.wait()

    def test_list_jobs_invalid_status(self, client, admin_headers, clean_registry):
        """Test listing jobs with invalid status filter."""
        response = client.get(
            "/v1/admin/background-jobs?status=invalid",
            headers=admin_headers,
        )

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_list_jobs_unauthorized(self, client, clean_registry):
        """Test listing jobs without admin token.

        The endpoint returns 422 (Unprocessable Entity) when the X-Admin-Token
        header is missing, because FastAPI validates required headers before
        the endpoint is called.
        """
        response = client.get("/v1/admin/background-jobs")
        # 422 is returned when the required X-Admin-Token header is missing
        assert response.status_code in (401, 403, 422)


class TestBackgroundJobsStatsEndpoint:
    """Tests for GET /v1/admin/background-jobs/stats endpoint."""

    def test_get_stats_empty(self, client, admin_headers, clean_registry):
        """Test getting stats when no jobs are registered."""
        response = client.get("/v1/admin/background-jobs/stats", headers=admin_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_registered"] == 0
        assert data["running"] == 0
        assert data["completed"] == 0
        assert data["failed"] == 0
        assert data["terminated"] == 0

    def test_get_stats_with_jobs(self, client, admin_headers, clean_registry):
        """Test getting stats with various job statuses."""
        # Create jobs with different outcomes
        completed = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        failed = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(1)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        running = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            clean_registry.register(process=completed, job_type="quick")
            clean_registry.register(process=failed, job_type="failing")
            clean_registry.register(process=running, job_type="slow")

            # Wait for completion
            completed.wait()
            failed.wait()

            response = client.get(
                "/v1/admin/background-jobs/stats",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["total_registered"] == 3
            assert data["running"] == 1
            assert data["completed"] == 1
            assert data["failed"] == 1
        finally:
            running.terminate()
            running.wait()


class TestBackgroundJobDetailEndpoint:
    """Tests for GET /v1/admin/background-jobs/{job_id} endpoint."""

    def test_get_job_detail(self, client, admin_headers, clean_registry):
        """Test getting details of a specific job."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            job_info = clean_registry.register(
                process=process,
                job_type="test_job",
                command=["python", "-c", "import time; time.sleep(60)"],
                working_directory="/tmp",
                metadata={"key": "value"},
            )

            response = client.get(
                f"/v1/admin/background-jobs/{job_info.job_id}",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_info.job_id
            assert data["pid"] == process.pid
            assert data["job_type"] == "test_job"
            assert data["status"] == "running"
            assert data["working_directory"] == "/tmp"
            assert data["metadata"] == {"key": "value"}
        finally:
            process.terminate()
            process.wait()

    def test_get_job_not_found(self, client, admin_headers, clean_registry):
        """Test getting a non-existent job."""
        response = client.get(
            "/v1/admin/background-jobs/nonexistent_job_id",
            headers=admin_headers,
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]


class TestBackgroundJobTerminateEndpoint:
    """Tests for DELETE /v1/admin/background-jobs/{job_id} endpoint."""

    def test_terminate_running_job(self, client, admin_headers, clean_registry):
        """Test terminating a running job."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = clean_registry.register(process=process, job_type="test_job")

        response = client.delete(
            f"/v1/admin/background-jobs/{job_info.job_id}",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "terminated successfully" in data["message"]
        assert data["method"] == "SIGTERM"

        # Wait for process to actually terminate
        process.wait(timeout=5)

    def test_terminate_job_force(self, client, admin_headers, clean_registry):
        """Test force killing a job."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = clean_registry.register(process=process, job_type="test_job")

        response = client.delete(
            f"/v1/admin/background-jobs/{job_info.job_id}?force=true",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["method"] == "SIGKILL"

        # Wait for process to actually terminate
        process.wait(timeout=5)

    def test_terminate_nonexistent_job(self, client, admin_headers, clean_registry):
        """Test terminating a non-existent job."""
        response = client.delete(
            "/v1/admin/background-jobs/nonexistent_job_id",
            headers=admin_headers,
        )

        assert response.status_code == 404

    def test_terminate_finished_job(self, client, admin_headers, clean_registry):
        """Test terminating an already finished job."""
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = clean_registry.register(process=process, job_type="quick")

        # Wait for process to complete
        process.wait()

        response = client.delete(
            f"/v1/admin/background-jobs/{job_info.job_id}",
            headers=admin_headers,
        )

        assert response.status_code == 400
        assert "not running" in response.json()["detail"]


class TestBackgroundJobCleanupEndpoint:
    """Tests for POST /v1/admin/background-jobs/cleanup endpoint."""

    def test_cleanup_finished_jobs(self, client, admin_headers, clean_registry):
        """Test cleaning up finished jobs."""
        # Create a process that finishes quickly
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        clean_registry.register(process=process, job_type="quick")

        # Wait for process to complete
        process.wait()

        # Verify job is in registry
        response = client.get("/v1/admin/background-jobs", headers=admin_headers)
        assert len(response.json()["jobs"]) == 1

        # Cleanup
        response = client.post(
            "/v1/admin/background-jobs/cleanup",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cleaned_count"] == 1

        # Verify registry is empty
        response = client.get("/v1/admin/background-jobs", headers=admin_headers)
        assert len(response.json()["jobs"]) == 0

    def test_cleanup_no_finished_jobs(self, client, admin_headers, clean_registry):
        """Test cleanup when there are no finished jobs."""
        response = client.post(
            "/v1/admin/background-jobs/cleanup",
            headers=admin_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["cleaned_count"] == 0


class TestLegacyQuestionGenerationStatusEndpoint:
    """Tests for the legacy GET /v1/admin/question-generation-status/{job_id} endpoint."""

    def test_status_by_registry_job_id(self, client, admin_headers, clean_registry):
        """Test getting status by registry job ID."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            job_info = clean_registry.register(process=process, job_type="test_job")

            response = client.get(
                f"/v1/admin/question-generation-status/{job_info.job_id}",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["job_id"] == job_info.job_id
            assert data["pid"] == process.pid
            assert data["status"] == "running"
        finally:
            process.terminate()
            process.wait()

    def test_status_by_pid(self, client, admin_headers, clean_registry):
        """Test getting status by PID (legacy behavior)."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Register the process in the registry
            clean_registry.register(process=process, job_type="test_job")

            # Query by PID instead of job_id
            response = client.get(
                f"/v1/admin/question-generation-status/{process.pid}",
                headers=admin_headers,
            )

            assert response.status_code == 200
            data = response.json()
            assert data["pid"] == process.pid
            assert data["status"] == "running"
        finally:
            process.terminate()
            process.wait()

    def test_status_invalid_job_id(self, client, admin_headers, clean_registry):
        """Test getting status with invalid job ID."""
        response = client.get(
            "/v1/admin/question-generation-status/not_a_number_or_valid_id",
            headers=admin_headers,
        )

        # The endpoint should return 400 for invalid job IDs that aren't in registry
        # and can't be parsed as PIDs
        assert response.status_code == 400
