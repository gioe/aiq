"""Tests for the trigger server API."""

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestTriggerServer:
    """Tests for the trigger server endpoints."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset module state before each test."""
        # Clear environment and reimport module with fresh state
        with patch.dict(os.environ, {"ADMIN_TOKEN": "test-secret-token"}, clear=False):
            # Import fresh module for each test
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            self.app = trigger_server.app
            self.client = TestClient(self.app)
            self.module = trigger_server

            # Reset job state
            with trigger_server._job_lock:
                trigger_server._running_job = None

            yield

    def test_health_check_returns_200(self):
        """Test that health check returns healthy status."""
        response = self.client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "question-generation-trigger"

    def test_trigger_with_valid_token_returns_200(self):
        """Test that trigger endpoint accepts valid admin token."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            response = self.client.post(
                "/trigger",
                json={"count": 10, "dry_run": True},
                headers={"X-Admin-Token": "test-secret-token"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "started"
            assert "count=10" in data["message"]
            assert "dry_run=True" in data["message"]

    def test_trigger_with_invalid_token_returns_401(self):
        """Test that trigger endpoint rejects invalid admin token."""
        response = self.client.post(
            "/trigger",
            json={"count": 10},
            headers={"X-Admin-Token": "wrong-token"},
        )
        assert response.status_code == 401
        assert "Invalid admin token" in response.json()["detail"]

    def test_trigger_with_missing_token_returns_422(self):
        """Test that trigger endpoint returns 422 when token header is missing."""
        response = self.client.post(
            "/trigger",
            json={"count": 10},
        )
        assert response.status_code == 422

    def test_trigger_with_empty_admin_token_env_returns_500(self):
        """Test that trigger returns 500 when ADMIN_TOKEN is not configured."""
        with patch.dict(os.environ, {"ADMIN_TOKEN": ""}, clear=False):
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            client = TestClient(trigger_server.app)

            response = client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "any-token"},
            )
            assert response.status_code == 500
            assert "not configured" in response.json()["detail"]

    def test_trigger_concurrent_request_returns_409(self):
        """Test that concurrent trigger requests return 409."""
        # Create a mock that simulates a long-running job
        job_started = threading.Event()
        job_can_finish = threading.Event()

        def slow_job(*args, **kwargs):
            job_started.set()
            job_can_finish.wait(timeout=5)

        with patch.object(self.module, "run_generation_job", side_effect=slow_job):
            # First request starts the job
            response1 = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-secret-token"},
            )
            assert response1.status_code == 200

            # Wait for job to start
            job_started.wait(timeout=2)

            # Second request should get 409
            response2 = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-secret-token"},
            )
            assert response2.status_code == 409
            assert "already running" in response2.json()["detail"]

            # Clean up
            job_can_finish.set()

    def test_trigger_after_job_completes_returns_200(self):
        """Test that new job can start after previous job completes."""
        job_finished = threading.Event()

        def quick_job(*args, **kwargs):
            job_finished.set()

        with patch.object(self.module, "run_generation_job", side_effect=quick_job):
            # First request
            response1 = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-secret-token"},
            )
            assert response1.status_code == 200

            # Wait for job to complete
            job_finished.wait(timeout=2)
            time.sleep(0.1)  # Allow thread to finish

            # Reset event for second job
            job_finished.clear()

            # Second request should succeed after first completes
            response2 = self.client.post(
                "/trigger",
                json={"count": 20},
                headers={"X-Admin-Token": "test-secret-token"},
            )
            assert response2.status_code == 200
            assert "count=20" in response2.json()["message"]

    def test_trigger_default_parameters(self):
        """Test that trigger uses default parameters when not specified."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            response = self.client.post(
                "/trigger",
                json={},
                headers={"X-Admin-Token": "test-secret-token"},
            )
            assert response.status_code == 200
            # Default is count=50, dry_run=False
            assert "count=50" in response.json()["message"]
            assert "dry_run=False" in response.json()["message"]

    def test_trigger_count_validation(self):
        """Test that count parameter is validated."""
        # Count too low
        response = self.client.post(
            "/trigger",
            json={"count": 0},
            headers={"X-Admin-Token": "test-secret-token"},
        )
        assert response.status_code == 422

        # Count too high
        response = self.client.post(
            "/trigger",
            json={"count": 501},
            headers={"X-Admin-Token": "test-secret-token"},
        )
        assert response.status_code == 422


class TestRunGenerationJob:
    """Tests for the run_generation_job function."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up for run_generation_job tests."""
        with patch.dict(os.environ, {"ADMIN_TOKEN": "test-token"}, clear=False):
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            self.module = trigger_server
            yield

    def test_run_generation_job_builds_correct_command(self):
        """Test that run_generation_job builds the correct command."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            self.module.run_generation_job(count=25, dry_run=False, verbose=True)

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert cmd[0] == "python"
            assert cmd[1] == "run_generation.py"
            assert "--count" in cmd
            assert "25" in cmd
            assert "--verbose" in cmd
            assert "--dry-run" not in cmd

    def test_run_generation_job_includes_dry_run_flag(self):
        """Test that dry_run flag is included when set."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            self.module.run_generation_job(count=10, dry_run=True, verbose=False)

            cmd = mock_run.call_args[0][0]
            assert "--dry-run" in cmd
            assert "--verbose" not in cmd

    def test_run_generation_job_handles_subprocess_failure(self):
        """Test that subprocess failures are logged."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="output", stderr="error"
            )

            # Should not raise - just logs the error
            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            mock_run.assert_called_once()

    def test_run_generation_job_handles_timeout(self):
        """Test that subprocess timeout is handled."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=3600)

            # Should not raise - just logs the error
            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            mock_run.assert_called_once()

    def test_run_generation_job_handles_exception(self):
        """Test that exceptions are logged."""
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("Unexpected error")

            # Should not raise - just logs the error
            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            mock_run.assert_called_once()


class TestVerifyAdminToken:
    """Tests for the verify_admin_token dependency."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up for verify_admin_token tests."""
        with patch.dict(os.environ, {"ADMIN_TOKEN": "test-token"}, clear=False):
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            self.module = trigger_server
            yield

    @pytest.mark.asyncio
    async def test_verify_admin_token_with_valid_token(self):
        """Test that valid token returns True."""
        result = await self.module.verify_admin_token("test-token")
        assert result is True

    @pytest.mark.asyncio
    async def test_verify_admin_token_with_invalid_token(self):
        """Test that invalid token raises 401."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await self.module.verify_admin_token("wrong-token")
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_verify_admin_token_uses_constant_time_comparison(self):
        """Test that token comparison uses secrets.compare_digest."""
        with patch("secrets.compare_digest", return_value=True) as mock_compare:
            result = await self.module.verify_admin_token("test-token")
            assert result is True
            mock_compare.assert_called_once_with("test-token", "test-token")


class TestRateLimiting:
    """Tests for rate limiting functionality."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset module state before each test."""
        with patch.dict(os.environ, {"ADMIN_TOKEN": "test-secret-token"}, clear=False):
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            self.app = trigger_server.app
            self.client = TestClient(self.app)
            self.module = trigger_server

            # Reset rate limit state
            with trigger_server._rate_limit_lock:
                trigger_server._rate_limit_data.clear()
                trigger_server._last_cleanup = time.time()

            # Reset job state
            with trigger_server._job_lock:
                trigger_server._running_job = None

            yield

    def test_health_endpoint_not_rate_limited(self):
        """Test that health endpoint is exempt from rate limiting."""
        # Make many requests to health endpoint
        for _ in range(15):
            response = self.client.get("/health")
            assert response.status_code == 200

        # Health endpoint should not have rate limit headers
        response = self.client.get("/health")
        assert response.status_code == 200
        assert "X-RateLimit-Limit" not in response.headers

    def test_rate_limit_headers_included_on_success(self):
        """Test that rate limit headers are included in successful responses."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-secret-token"},
            )

            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers

            assert response.headers["X-RateLimit-Limit"] == "10"
            # First request, so 9 remaining
            assert response.headers["X-RateLimit-Remaining"] == "9"

    def test_rate_limit_remaining_decrements(self):
        """Test that remaining count decrements with each request."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Make 3 requests
            for i in range(3):
                response = self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={"X-Admin-Token": "test-secret-token"},
                )
                assert response.status_code == 200
                expected_remaining = 10 - (i + 1)
                assert response.headers["X-RateLimit-Remaining"] == str(
                    expected_remaining
                )

    def test_rate_limit_exceeded_returns_429(self):
        """Test that exceeding rate limit returns 429."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Make exactly 10 requests (the limit)
            for i in range(10):
                response = self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={"X-Admin-Token": "test-secret-token"},
                )
                assert response.status_code == 200

            # 11th request should be rate limited
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-secret-token"},
            )

            assert response.status_code == 429
            data = response.json()
            assert "Rate limit exceeded" in data["detail"]
            assert "Try again in" in data["detail"]

    def test_rate_limit_429_includes_retry_headers(self):
        """Test that 429 response includes retry headers."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Exhaust rate limit
            for _ in range(10):
                self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={"X-Admin-Token": "test-secret-token"},
                )

            # Next request should return 429 with headers
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-secret-token"},
            )

            assert response.status_code == 429
            assert "X-RateLimit-Limit" in response.headers
            assert "X-RateLimit-Remaining" in response.headers
            assert "X-RateLimit-Reset" in response.headers
            assert "Retry-After" in response.headers

            assert response.headers["X-RateLimit-Limit"] == "10"
            assert response.headers["X-RateLimit-Remaining"] == "0"
            # Retry-After should be positive
            assert int(response.headers["Retry-After"]) > 0

    def test_rate_limit_resets_after_window(self):
        """Test that rate limit resets after time window expires."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Mock time to control window transitions
            current_time = time.time()
            window_start = current_time

            with patch("time.time", return_value=window_start):
                # Exhaust rate limit in first window
                for _ in range(10):
                    response = self.client.post(
                        "/trigger",
                        json={"count": 10},
                        headers={"X-Admin-Token": "test-secret-token"},
                    )
                    assert response.status_code == 200

                # Next request should be rate limited
                response = self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={"X-Admin-Token": "test-secret-token"},
                )
                assert response.status_code == 429

            # Move to next window (61 seconds later)
            with patch("time.time", return_value=window_start + 61):
                # Should be allowed again
                response = self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={"X-Admin-Token": "test-secret-token"},
                )
                assert response.status_code == 200
                assert response.headers["X-RateLimit-Remaining"] == "9"

    def test_rate_limit_per_client_ip(self):
        """Test that rate limiting is per client IP address."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Client 1 exhausts their limit
            for _ in range(10):
                response = self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={
                        "X-Admin-Token": "test-secret-token",
                        "X-Envoy-External-Address": "1.2.3.4",
                    },
                )
                assert response.status_code == 200

            # Client 1 is rate limited
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={
                    "X-Admin-Token": "test-secret-token",
                    "X-Envoy-External-Address": "1.2.3.4",
                },
            )
            assert response.status_code == 429

            # Client 2 should still have their full quota
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={
                    "X-Admin-Token": "test-secret-token",
                    "X-Envoy-External-Address": "5.6.7.8",
                },
            )
            assert response.status_code == 200
            assert response.headers["X-RateLimit-Remaining"] == "9"

    def test_rate_limit_uses_envoy_external_address_header(self):
        """Test that rate limiter uses X-Envoy-External-Address header for client IP."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Make request with X-Envoy-External-Address header
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={
                    "X-Admin-Token": "test-secret-token",
                    "X-Envoy-External-Address": "10.0.0.1, 10.0.0.2",  # Multiple IPs
                },
            )
            assert response.status_code == 200

            # Should track by first IP in X-Envoy-External-Address
            # Make 9 more requests from same first IP
            for _ in range(9):
                response = self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={
                        "X-Admin-Token": "test-secret-token",
                        "X-Envoy-External-Address": "10.0.0.1, 10.0.0.3",  # Same first IP
                    },
                )
                assert response.status_code == 200

            # 11th request should be rate limited
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={
                    "X-Admin-Token": "test-secret-token",
                    "X-Envoy-External-Address": "10.0.0.1",
                },
            )
            assert response.status_code == 429

    def test_rate_limit_cleanup_removes_expired_entries(self):
        """Test that cleanup removes expired rate limit entries."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            current_time = time.time()

            # Make requests in first window
            with patch("time.time", return_value=current_time):
                for _ in range(5):
                    self.client.post(
                        "/trigger",
                        json={"count": 10},
                        headers={
                            "X-Admin-Token": "test-secret-token",
                            "X-Envoy-External-Address": "192.168.1.1",
                        },
                    )

            # Verify data exists
            with self.module._rate_limit_lock:
                assert "192.168.1.1" in self.module._rate_limit_data

            # Move forward past cleanup interval (121 seconds = 2 full windows)
            with patch("time.time", return_value=current_time + 121):
                # Make a request to trigger cleanup
                self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={
                        "X-Admin-Token": "test-secret-token",
                        "X-Envoy-External-Address": "192.168.1.2",  # Different client
                    },
                )

            # Old entry should be cleaned up
            with self.module._rate_limit_lock:
                assert "192.168.1.1" not in self.module._rate_limit_data

    def test_rate_limit_applies_before_auth(self):
        """Test that rate limiting is checked before authentication."""
        with patch.object(self.module, "run_generation_job", return_value=None):
            # Exhaust rate limit with valid token
            for _ in range(10):
                self.client.post(
                    "/trigger",
                    json={"count": 10},
                    headers={"X-Admin-Token": "test-secret-token"},
                )

            # Try with invalid token - should get 429, not 401
            response = self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "wrong-token"},
            )

            # Should be rate limited before auth check
            assert response.status_code == 429
