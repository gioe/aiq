"""
Tests for the ProcessRegistry module (BCQ-036, BCQ-049, BCQ-050).

This module tests the background process tracking functionality including:
- Process registration and deregistration
- Status updates and monitoring
- Cleanup of finished processes
- Graceful shutdown handling
- Opportunistic cleanup of old finished jobs (BCQ-049)
- Shutdown flag to prevent new registrations during shutdown (BCQ-050)
"""
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.core.process_registry import (
    DEFAULT_CLEANUP_MAX_AGE_HOURS,
    JobStatus,
    ProcessRegistry,
)


@pytest.fixture
def fresh_registry():
    """Create a fresh ProcessRegistry instance for testing.

    The registry is a singleton, so we need to reset it for each test.
    """
    # Reset the singleton
    ProcessRegistry._instance = None

    # Create a new instance
    registry = ProcessRegistry()

    yield registry

    # Cleanup: shutdown any remaining processes
    registry.shutdown_all(timeout=2.0)

    # Reset singleton again for next test
    ProcessRegistry._instance = None


class TestProcessRegistry:
    """Tests for ProcessRegistry class."""

    def test_singleton_pattern(self, fresh_registry):
        """Test that ProcessRegistry is a singleton."""
        registry1 = ProcessRegistry()
        registry2 = ProcessRegistry()
        assert registry1 is registry2

    def test_register_process(self, fresh_registry):
        """Test registering a process in the registry."""
        # Create a simple subprocess that sleeps
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            job_info = fresh_registry.register(
                process=process,
                job_type="test_job",
                command=["python", "-c", "import time; time.sleep(10)"],
                metadata={"test": True},
            )

            assert job_info.job_id is not None
            assert job_info.pid == process.pid
            assert job_info.job_type == "test_job"
            assert job_info.status == JobStatus.RUNNING
            assert job_info.metadata == {"test": True}
        finally:
            process.terminate()
            process.wait()

    def test_get_job_status(self, fresh_registry):
        """Test getting job status from registry."""
        # Create a subprocess that exits quickly
        process = subprocess.Popen(
            [sys.executable, "-c", "print('hello')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(
            process=process,
            job_type="test_job",
        )

        # Wait for process to complete
        process.wait()

        # Get updated status
        updated_info = fresh_registry.get_job_status(job_info.job_id)

        assert updated_info is not None
        assert updated_info.status == JobStatus.COMPLETED
        assert updated_info.exit_code == 0
        assert updated_info.finished_at is not None

    def test_get_job_by_pid(self, fresh_registry):
        """Test getting job by PID."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            job_info = fresh_registry.register(
                process=process,
                job_type="test_job",
            )

            # Look up by PID
            found_info = fresh_registry.get_job_by_pid(process.pid)

            assert found_info is not None
            assert found_info.job_id == job_info.job_id
            assert found_info.pid == process.pid
        finally:
            process.terminate()
            process.wait()

    def test_get_job_not_found(self, fresh_registry):
        """Test getting a non-existent job."""
        result = fresh_registry.get_job_status("nonexistent_job_id")
        assert result is None

    def test_list_jobs(self, fresh_registry):
        """Test listing all jobs."""
        # Create two processes
        process1 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process2 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            fresh_registry.register(process=process1, job_type="type_a")
            fresh_registry.register(process=process2, job_type="type_b")

            # List all jobs
            all_jobs = fresh_registry.list_jobs()
            assert len(all_jobs) == 2

            # List by type
            type_a_jobs = fresh_registry.list_jobs(job_type="type_a")
            assert len(type_a_jobs) == 1
            assert type_a_jobs[0].job_type == "type_a"

            # List by status
            running_jobs = fresh_registry.list_jobs(status=JobStatus.RUNNING)
            assert len(running_jobs) == 2
        finally:
            process1.terminate()
            process2.terminate()
            process1.wait()
            process2.wait()

    def test_list_jobs_exclude_finished(self, fresh_registry):
        """Test listing jobs excluding finished ones."""
        # Create one quick process and one long-running
        process1 = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        process2 = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            fresh_registry.register(process=process1, job_type="quick")
            fresh_registry.register(process=process2, job_type="slow")

            # Wait for process1 to complete
            process1.wait()

            # List only running (exclude finished)
            running_jobs = fresh_registry.list_jobs(include_finished=False)
            assert len(running_jobs) == 1
            assert running_jobs[0].job_type == "slow"
        finally:
            process2.terminate()
            process2.wait()

    def test_cleanup_finished(self, fresh_registry):
        """Test cleaning up finished processes."""
        # Create a process that exits quickly
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        fresh_registry.register(process=process, job_type="quick")

        # Wait for process to complete
        process.wait()

        # Verify it's in the registry
        assert len(fresh_registry.list_jobs()) == 1

        # Cleanup finished
        cleaned = fresh_registry.cleanup_finished()
        assert cleaned == 1

        # Verify registry is now empty
        assert len(fresh_registry.list_jobs()) == 0

    def test_terminate_job(self, fresh_registry):
        """Test terminating a running job."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="long_job")

        # Terminate the job
        success = fresh_registry.terminate_job(job_info.job_id)
        assert success is True

        # Wait for process to actually terminate
        process.wait(timeout=5)

        # Verify status is updated
        updated_info = fresh_registry.get_job_status(job_info.job_id)
        assert updated_info.status == JobStatus.TERMINATED
        assert updated_info.exit_code is not None

    def test_terminate_job_force(self, fresh_registry):
        """Test force killing a job."""
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="long_job")

        # Force kill the job
        success = fresh_registry.terminate_job(job_info.job_id, force=True)
        assert success is True

        # Wait for process to actually terminate
        process.wait(timeout=5)

        # Verify process was killed
        updated_info = fresh_registry.get_job_status(job_info.job_id)
        assert updated_info.status in (JobStatus.TERMINATED, JobStatus.FAILED)

    def test_terminate_nonexistent_job(self, fresh_registry):
        """Test terminating a non-existent job returns False."""
        success = fresh_registry.terminate_job("nonexistent_job_id")
        assert success is False

    def test_terminate_already_finished_job(self, fresh_registry):
        """Test terminating an already finished job returns False."""
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="quick")

        # Wait for process to complete
        process.wait()

        # Try to terminate (should fail since already done)
        success = fresh_registry.terminate_job(job_info.job_id)
        assert success is False

    def test_shutdown_all(self, fresh_registry):
        """Test shutting down all processes."""
        # Create multiple long-running processes
        processes = []
        for i in range(3):
            process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(process)
            fresh_registry.register(process=process, job_type=f"job_{i}")

        # Shutdown all
        terminated = fresh_registry.shutdown_all(timeout=5.0)
        assert terminated == 3

        # All processes should be terminated
        for process in processes:
            assert process.poll() is not None

    def test_get_stats(self, fresh_registry):
        """Test getting registry statistics."""
        # Create processes with different outcomes
        quick_process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        failing_process = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(1)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        running_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            fresh_registry.register(process=quick_process, job_type="quick")
            fresh_registry.register(process=failing_process, job_type="failing")
            fresh_registry.register(process=running_process, job_type="running")

            # Wait for quick processes to complete
            quick_process.wait()
            failing_process.wait()

            # Get stats
            stats = fresh_registry.get_stats()

            assert stats["total_registered"] == 3
            assert stats["running"] == 1
            assert stats["completed"] == 1
            assert stats["failed"] == 1
        finally:
            running_process.terminate()
            running_process.wait()

    def test_job_info_to_dict(self, fresh_registry):
        """Test JobInfo.to_dict() method."""
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(
            process=process,
            job_type="test",
            command=["python", "-c", "print('done')"],
            working_directory="/tmp",
            metadata={"key": "value"},
        )

        process.wait()
        job_info = fresh_registry.get_job_status(job_info.job_id)

        result = job_info.to_dict()

        assert "job_id" in result
        assert "pid" in result
        assert "job_type" in result
        assert result["job_type"] == "test"
        assert "started_at" in result
        assert "status" in result
        assert result["command"] == ["python", "-c", "print('done')"]
        assert result["working_directory"] == "/tmp"
        assert result["metadata"] == {"key": "value"}

    def test_unregister_job(self, fresh_registry):
        """Test unregistering a job from the registry."""
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="test")
        process.wait()

        # Unregister
        result = fresh_registry.unregister(job_info.job_id)
        assert result is True

        # Verify it's gone
        assert fresh_registry.get_job_status(job_info.job_id) is None

        # Try to unregister again
        result = fresh_registry.unregister(job_info.job_id)
        assert result is False


class TestProcessRegistryThreadSafety:
    """Tests for thread safety of ProcessRegistry."""

    def test_concurrent_registration(self, fresh_registry):
        """Test that concurrent registrations are handled correctly."""
        import threading

        processes = []
        job_ids = []
        lock = threading.Lock()

        def register_process():
            process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            with lock:
                processes.append(process)

            job_info = fresh_registry.register(process=process, job_type="concurrent")
            with lock:
                job_ids.append(job_info.job_id)

        # Create threads
        threads = [threading.Thread(target=register_process) for _ in range(10)]

        # Start all threads
        for t in threads:
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Cleanup
        for process in processes:
            process.terminate()
            process.wait()

        # Verify all were registered
        assert len(job_ids) == 10
        assert len(set(job_ids)) == 10  # All unique IDs


class TestJobStatus:
    """Tests for JobStatus enum."""

    def test_job_status_values(self):
        """Test JobStatus enum values."""
        assert JobStatus.RUNNING.value == "running"
        assert JobStatus.COMPLETED.value == "completed"
        assert JobStatus.FAILED.value == "failed"
        assert JobStatus.TERMINATED.value == "terminated"
        assert JobStatus.UNKNOWN.value == "unknown"

    def test_job_status_is_string_enum(self):
        """Test that JobStatus is a str enum."""
        assert isinstance(JobStatus.RUNNING, str)
        assert JobStatus.RUNNING == "running"


class TestOpportunisticCleanup:
    """Tests for opportunistic cleanup of old finished jobs (BCQ-049)."""

    def test_cleanup_old_finished_jobs_removes_old_jobs(self, fresh_registry):
        """Test that _cleanup_old_finished_jobs removes jobs older than max_age_hours."""
        # Create a quick process that finishes immediately
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="old_job")

        # Wait for process to complete
        process.wait()

        # Update job status so finished_at is set
        fresh_registry.get_job_status(job_info.job_id)

        # Manually backdate the finished_at to 2 hours ago
        with fresh_registry._registry_lock:
            _, stored_job_info = fresh_registry._processes[job_info.job_id]
            stored_job_info.finished_at = datetime.now(timezone.utc) - timedelta(
                hours=2
            )

        # Verify job is still in registry before cleanup
        assert len(fresh_registry.list_jobs(opportunistic_cleanup=False)) == 1

        # Run cleanup with max_age of 1 hour - should remove the job
        cleaned = fresh_registry._cleanup_old_finished_jobs(max_age_hours=1)
        assert cleaned == 1

        # Verify job was removed
        assert len(fresh_registry.list_jobs(opportunistic_cleanup=False)) == 0

    def test_cleanup_old_finished_jobs_preserves_recent_jobs(self, fresh_registry):
        """Test that _cleanup_old_finished_jobs preserves recently finished jobs."""
        # Create a quick process that finishes immediately
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="recent_job")

        # Wait for process to complete
        process.wait()

        # Update job status so finished_at is set (to now)
        fresh_registry.get_job_status(job_info.job_id)

        # Run cleanup with max_age of 1 hour - should NOT remove the job
        cleaned = fresh_registry._cleanup_old_finished_jobs(max_age_hours=1)
        assert cleaned == 0

        # Verify job is still in registry
        assert len(fresh_registry.list_jobs(opportunistic_cleanup=False)) == 1

    def test_cleanup_old_finished_jobs_preserves_running_jobs(self, fresh_registry):
        """Test that _cleanup_old_finished_jobs never removes running jobs."""
        # Create a long-running process
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            fresh_registry.register(process=process, job_type="running_job")

            # Run cleanup - should NOT remove running job
            cleaned = fresh_registry._cleanup_old_finished_jobs(max_age_hours=0)
            assert cleaned == 0

            # Verify job is still in registry
            assert len(fresh_registry.list_jobs(opportunistic_cleanup=False)) == 1
        finally:
            process.terminate()
            process.wait()

    def test_list_jobs_triggers_opportunistic_cleanup(self, fresh_registry):
        """Test that list_jobs() triggers opportunistic cleanup by default."""
        # Create a quick process that finishes immediately
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="old_job")

        # Wait for process to complete
        process.wait()

        # Update job status so finished_at is set
        fresh_registry.get_job_status(job_info.job_id)

        # Manually backdate the finished_at to 2 hours ago
        with fresh_registry._registry_lock:
            _, stored_job_info = fresh_registry._processes[job_info.job_id]
            stored_job_info.finished_at = datetime.now(timezone.utc) - timedelta(
                hours=2
            )

        # list_jobs with opportunistic_cleanup=True (default) should remove old job
        with patch.object(
            fresh_registry,
            "_cleanup_old_finished_jobs",
            wraps=fresh_registry._cleanup_old_finished_jobs,
        ) as mock_cleanup:
            jobs = fresh_registry.list_jobs()
            mock_cleanup.assert_called_once()
            # Job should be removed
            assert len(jobs) == 0

    def test_list_jobs_can_skip_opportunistic_cleanup(self, fresh_registry):
        """Test that list_jobs() can skip opportunistic cleanup."""
        # Create a quick process that finishes immediately
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="old_job")

        # Wait for process to complete
        process.wait()

        # Update job status so finished_at is set
        fresh_registry.get_job_status(job_info.job_id)

        # Manually backdate the finished_at to 2 hours ago
        with fresh_registry._registry_lock:
            _, stored_job_info = fresh_registry._processes[job_info.job_id]
            stored_job_info.finished_at = datetime.now(timezone.utc) - timedelta(
                hours=2
            )

        # list_jobs with opportunistic_cleanup=False should NOT remove old job
        with patch.object(fresh_registry, "_cleanup_old_finished_jobs") as mock_cleanup:
            jobs = fresh_registry.list_jobs(opportunistic_cleanup=False)
            mock_cleanup.assert_not_called()
            # Job should still be there
            assert len(jobs) == 1

    def test_get_stats_triggers_opportunistic_cleanup(self, fresh_registry):
        """Test that get_stats() triggers opportunistic cleanup by default."""
        # Create a quick process that finishes immediately
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="old_job")

        # Wait for process to complete
        process.wait()

        # Update job status so finished_at is set
        fresh_registry.get_job_status(job_info.job_id)

        # Manually backdate the finished_at to 2 hours ago
        with fresh_registry._registry_lock:
            _, stored_job_info = fresh_registry._processes[job_info.job_id]
            stored_job_info.finished_at = datetime.now(timezone.utc) - timedelta(
                hours=2
            )

        # get_stats with opportunistic_cleanup=True (default) should trigger cleanup
        with patch.object(
            fresh_registry,
            "_cleanup_old_finished_jobs",
            wraps=fresh_registry._cleanup_old_finished_jobs,
        ) as mock_cleanup:
            stats = fresh_registry.get_stats()
            mock_cleanup.assert_called_once()
            # Job should be removed, so total_registered should be 0
            assert stats["total_registered"] == 0

    def test_get_stats_can_skip_opportunistic_cleanup(self, fresh_registry):
        """Test that get_stats() can skip opportunistic cleanup."""
        # Create a quick process that finishes immediately
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        job_info = fresh_registry.register(process=process, job_type="old_job")

        # Wait for process to complete
        process.wait()

        # Update job status so finished_at is set
        fresh_registry.get_job_status(job_info.job_id)

        # Manually backdate the finished_at to 2 hours ago
        with fresh_registry._registry_lock:
            _, stored_job_info = fresh_registry._processes[job_info.job_id]
            stored_job_info.finished_at = datetime.now(timezone.utc) - timedelta(
                hours=2
            )

        # get_stats with opportunistic_cleanup=False should NOT trigger cleanup
        with patch.object(fresh_registry, "_cleanup_old_finished_jobs") as mock_cleanup:
            stats = fresh_registry.get_stats(opportunistic_cleanup=False)
            mock_cleanup.assert_not_called()
            # Job should still be there
            assert stats["total_registered"] == 1

    def test_default_cleanup_max_age_hours_constant(self):
        """Test that the default cleanup max age constant is exported."""
        assert DEFAULT_CLEANUP_MAX_AGE_HOURS == 1

    def test_cleanup_mixed_jobs_only_removes_old_finished(self, fresh_registry):
        """Test cleanup with a mix of running, recent finished, and old finished jobs."""
        # Create a running process
        running_process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Create a recently finished process
        recent_process = subprocess.Popen(
            [sys.executable, "-c", "print('recent')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Create an old finished process
        old_process = subprocess.Popen(
            [sys.executable, "-c", "print('old')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            fresh_registry.register(process=running_process, job_type="running")
            recent_job = fresh_registry.register(
                process=recent_process, job_type="recent"
            )
            old_job = fresh_registry.register(process=old_process, job_type="old")

            # Wait for finished processes to complete
            recent_process.wait()
            old_process.wait()

            # Update job statuses
            fresh_registry.get_job_status(recent_job.job_id)
            fresh_registry.get_job_status(old_job.job_id)

            # Backdate only the old job
            with fresh_registry._registry_lock:
                _, old_job_info = fresh_registry._processes[old_job.job_id]
                old_job_info.finished_at = datetime.now(timezone.utc) - timedelta(
                    hours=2
                )

            # Verify we have 3 jobs before cleanup
            assert len(fresh_registry.list_jobs(opportunistic_cleanup=False)) == 3

            # Run cleanup - should only remove the old job
            cleaned = fresh_registry._cleanup_old_finished_jobs(max_age_hours=1)
            assert cleaned == 1

            # Verify we now have 2 jobs (running + recent)
            remaining_jobs = fresh_registry.list_jobs(opportunistic_cleanup=False)
            assert len(remaining_jobs) == 2

            job_types = {job.job_type for job in remaining_jobs}
            assert job_types == {"running", "recent"}

        finally:
            running_process.terminate()
            running_process.wait()


class TestShutdownFlag:
    """Tests for shutdown flag behavior (BCQ-050)."""

    def test_register_raises_during_shutdown(self, fresh_registry):
        """Test that register() raises RuntimeError during shutdown."""
        # Manually set shutdown flag
        fresh_registry._shutting_down = True

        # Create a process to try to register
        process = subprocess.Popen(
            [sys.executable, "-c", "print('done')"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            # Attempt to register should raise RuntimeError
            with pytest.raises(RuntimeError) as exc_info:
                fresh_registry.register(process=process, job_type="test")

            assert "shutting down" in str(exc_info.value).lower()
        finally:
            process.terminate()
            process.wait()

    def test_shutdown_all_resets_shutdown_flag_after_completion(self, fresh_registry):
        """Test that shutdown_all() resets the _shutting_down flag after completion.

        The shutdown flag is set to True at the start of shutdown_all() to prevent
        new registrations during the shutdown sequence. After shutdown completes,
        the flag is reset to False so the registry can be reused (e.g., in tests).
        """
        # Verify flag is initially False
        assert fresh_registry._shutting_down is False

        # Call shutdown_all (with no processes)
        fresh_registry.shutdown_all(timeout=1.0)

        # Verify flag is reset to False after shutdown completes
        # This allows the registry to be reused
        assert fresh_registry._shutting_down is False

    def test_register_before_shutdown_succeeds(self, fresh_registry):
        """Test that register() works normally before shutdown."""
        # Verify flag is initially False
        assert fresh_registry._shutting_down is False

        # Create and register a process
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        try:
            job_info = fresh_registry.register(process=process, job_type="test")
            assert job_info is not None
            assert job_info.job_id is not None
        finally:
            process.terminate()
            process.wait()

    def test_shutdown_flag_prevents_race_condition(self, fresh_registry):
        """Test that shutdown flag prevents registration during active shutdown."""
        import threading

        registered_during_shutdown = []
        registration_errors = []
        processes = []
        lock = threading.Lock()

        def try_register():
            """Try to register a new process."""
            process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(5)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            with lock:
                processes.append(process)

            try:
                job_info = fresh_registry.register(process=process, job_type="test")
                with lock:
                    registered_during_shutdown.append(job_info)
            except RuntimeError as e:
                with lock:
                    registration_errors.append(str(e))

        # First, register a few processes
        for _ in range(3):
            process = subprocess.Popen(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            processes.append(process)
            fresh_registry.register(process=process, job_type="initial")

        # Start concurrent registration attempts
        registration_threads = [threading.Thread(target=try_register) for _ in range(5)]
        for t in registration_threads:
            t.start()

        # Immediately start shutdown
        shutdown_thread = threading.Thread(
            target=lambda: fresh_registry.shutdown_all(timeout=2.0)
        )
        shutdown_thread.start()

        # Wait for everything to complete
        for t in registration_threads:
            t.join(timeout=5.0)
        shutdown_thread.join(timeout=10.0)

        # Cleanup any remaining processes
        for process in processes:
            try:
                process.terminate()
                process.wait(timeout=1.0)
            except Exception:
                pass

        # After shutdown completes, the flag is reset to False to allow reuse
        assert fresh_registry._shutting_down is False

        # The shutdown mechanism prevents new registrations during shutdown, so either:
        # 1. Some registrations failed with RuntimeError (if they raced with shutdown), OR
        # 2. All registrations completed before shutdown_all was called
        # The key is that the registry is now empty and ready for reuse
        assert len(fresh_registry._processes) == 0

        # This test verifies the shutdown mechanism exists and the registry
        # can be reused after shutdown completes
