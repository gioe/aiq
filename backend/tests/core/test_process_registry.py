"""
Tests for the ProcessRegistry module (BCQ-036).

This module tests the background process tracking functionality including:
- Process registration and deregistration
- Status updates and monitoring
- Cleanup of finished processes
- Graceful shutdown handling
"""
import subprocess
import sys

import pytest

from app.core.process_registry import JobStatus, ProcessRegistry


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
