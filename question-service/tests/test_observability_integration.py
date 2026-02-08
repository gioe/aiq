"""Tests for observability integration in the question-service.

Verifies that:
- trigger_server.py initializes and shuts down observability via lifespan
- trigger_server.py instruments the generation job with spans and metrics
- trigger_server.py records metrics on trigger requests
- run_generation.py captures errors in exception handlers
"""

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestTriggerServerObservabilityLifespan:
    """Tests that trigger_server initializes and shuts down observability."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset module state before each test."""
        with patch.dict(os.environ, {"ADMIN_TOKEN": "test-token"}, clear=False):
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            self.module = trigger_server
            self.app = trigger_server.app
            yield

    def test_lifespan_initializes_observability(self):
        """Test that the FastAPI lifespan calls observability.init on startup."""
        with patch.object(self.module, "observability") as mock_obs:
            with TestClient(self.app):
                mock_obs.init.assert_called_once_with(
                    config_path="config/observability.yaml",
                    service_name="aiq-question-service-trigger",
                    environment=self.module.settings.env,
                )

    def test_lifespan_shuts_down_observability(self):
        """Test that the FastAPI lifespan calls flush and shutdown on exit."""
        with patch.object(self.module, "observability") as mock_obs:
            with TestClient(self.app):
                pass
            mock_obs.flush.assert_called_once_with(timeout=5.0)
            mock_obs.shutdown.assert_called_once()


class TestTriggerServerObservabilityInstrumentation:
    """Tests that trigger_server instruments key operations."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Reset module state before each test."""
        with patch.dict(os.environ, {"ADMIN_TOKEN": "test-token"}, clear=False):
            import importlib

            import trigger_server

            importlib.reload(trigger_server)
            self.module = trigger_server
            self.app = trigger_server.app
            self.client = TestClient(self.app)

            with trigger_server._job_lock:
                trigger_server._running_job = None
            yield

    def test_trigger_endpoint_records_request_metric(self):
        """Test that trigger endpoint records a metric on each request."""
        with (
            patch.object(self.module, "run_generation_job", return_value=None),
            patch.object(self.module, "observability") as mock_obs,
        ):
            mock_obs.start_span.return_value.__enter__ = MagicMock()
            mock_obs.start_span.return_value.__exit__ = MagicMock(return_value=False)

            self.client.post(
                "/trigger",
                json={"count": 10, "dry_run": True},
                headers={"X-Admin-Token": "test-token"},
            )

            mock_obs.record_metric.assert_any_call(
                "trigger.requests",
                value=1,
                labels={"dry_run": "True"},
                metric_type="counter",
            )

    def test_trigger_endpoint_records_rejection_metric_on_409(self):
        """Test that a rejection metric is recorded when job is already running."""
        import threading

        job_started = threading.Event()
        job_can_finish = threading.Event()

        def slow_job(*args, **kwargs):
            job_started.set()
            job_can_finish.wait(timeout=5)

        with (
            patch.object(self.module, "run_generation_job", side_effect=slow_job),
            patch.object(self.module, "observability") as mock_obs,
        ):
            mock_obs.start_span.return_value.__enter__ = MagicMock()
            mock_obs.start_span.return_value.__exit__ = MagicMock(return_value=False)

            # First request starts job
            self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-token"},
            )
            job_started.wait(timeout=2)

            # Second request should get rejected
            self.client.post(
                "/trigger",
                json={"count": 10},
                headers={"X-Admin-Token": "test-token"},
            )

            mock_obs.record_metric.assert_any_call(
                "trigger.rejected",
                value=1,
                labels={"reason": "already_running"},
                metric_type="counter",
            )

            job_can_finish.set()

    def test_generation_job_creates_span(self):
        """Test that run_generation_job creates an observability span."""
        mock_span = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_span)
        mock_context.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(self.module, "observability") as mock_obs,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_obs.start_span.return_value = mock_context

            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            mock_obs.start_span.assert_called_once_with(
                "generation_job",
                kind="internal",
                attributes={"count": 10, "dry_run": False, "verbose": True},
            )
            mock_span.set_attribute.assert_any_call("exit_code", 0)
            mock_span.set_status.assert_called_once_with("ok")

    def test_generation_job_captures_error_on_timeout(self):
        """Test that a timeout during generation captures an error."""
        mock_span = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_span)
        mock_context.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(self.module, "observability") as mock_obs,
        ):
            timeout_error = subprocess.TimeoutExpired(cmd="test", timeout=3600)
            mock_run.side_effect = timeout_error
            mock_obs.start_span.return_value = mock_context

            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            mock_obs.capture_error.assert_called_once()
            args, kwargs = mock_obs.capture_error.call_args
            assert args[0] is timeout_error
            mock_span.set_status.assert_called_once_with("error", "Timeout after 3600s")

    def test_generation_job_captures_error_on_exception(self):
        """Test that an exception during generation captures an error."""
        mock_span = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_span)
        mock_context.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(self.module, "observability") as mock_obs,
        ):
            error = OSError("disk full")
            mock_run.side_effect = error
            mock_obs.start_span.return_value = mock_context

            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            mock_obs.capture_error.assert_called_once()
            args, kwargs = mock_obs.capture_error.call_args
            assert args[0] is error

    def test_generation_job_records_success_metric(self):
        """Test that a successful generation job records completion metric."""
        mock_span = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_span)
        mock_context.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(self.module, "observability") as mock_obs,
        ):
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            mock_obs.start_span.return_value = mock_context

            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            # Check that completion counter was recorded with success status
            metric_calls = [
                c
                for c in mock_obs.record_metric.call_args_list
                if c[0][0] == "trigger.job.completed"
            ]
            assert len(metric_calls) == 1
            assert metric_calls[0][1]["labels"]["status"] == "success"

    def test_generation_job_records_failure_metric(self):
        """Test that a failed generation job records failure metric."""
        mock_span = MagicMock()
        mock_context = MagicMock()
        mock_context.__enter__ = MagicMock(return_value=mock_span)
        mock_context.__exit__ = MagicMock(return_value=False)

        with (
            patch("subprocess.run") as mock_run,
            patch.object(self.module, "observability") as mock_obs,
        ):
            mock_run.return_value = MagicMock(returncode=1, stdout="out", stderr="err")
            mock_obs.start_span.return_value = mock_context

            self.module.run_generation_job(count=10, dry_run=False, verbose=True)

            metric_calls = [
                c
                for c in mock_obs.record_metric.call_args_list
                if c[0][0] == "trigger.job.completed"
            ]
            assert len(metric_calls) == 1
            assert metric_calls[0][1]["labels"]["status"] == "failure"
