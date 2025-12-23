"""
Process registry for tracking background generation jobs (BCQ-036).

This module provides a singleton registry for tracking subprocess instances
spawned by the application, specifically for question generation jobs.

Key Features:
- Thread-safe process registration and deregistration
- Automatic cleanup of finished processes
- Graceful shutdown of all running processes
- Status reporting for individual and all processes
- Opportunistic cleanup of old finished jobs to prevent memory leaks
- Shutdown flag to prevent new registrations during shutdown (BCQ-050)

Automatic Cleanup Behavior (BCQ-049):
    The registry performs opportunistic cleanup of finished jobs older than
    1 hour (configurable) when list_jobs() or get_stats() is called. This
    prevents memory leaks in long-running applications without requiring
    manual cleanup calls. The cleanup is performed automatically and silently
    to avoid impacting the primary operation's performance.

    To disable opportunistic cleanup, pass `opportunistic_cleanup=False` to
    list_jobs() or get_stats(). Manual cleanup is available via cleanup_finished().

Shutdown Flag Behavior (BCQ-050):
    When shutdown_all() is called, a `_shutting_down` flag is set to True
    at the very start of the method, before any processes are terminated.
    This prevents new process registrations during the shutdown sequence,
    which could otherwise lead to orphaned processes or race conditions.

    If register() is called while _shutting_down is True, it raises a
    RuntimeError with the message: "Cannot register new processes:
    ProcessRegistry is shutting down"

    After shutdown_all() completes (all processes terminated and registry
    cleared), the flag is reset to False so the registry can be reused.
    This is particularly useful in testing scenarios where the same
    singleton instance may need to be used across multiple tests.

Usage:
    from app.core.process_registry import process_registry

    # Register a new process
    job_info = process_registry.register(process, job_type="question_generation")

    # Get status of a specific job
    status = process_registry.get_job_status(job_id)

    # List all running jobs (automatically cleans up old finished jobs)
    jobs = process_registry.list_jobs()

    # List jobs without opportunistic cleanup
    jobs = process_registry.list_jobs(opportunistic_cleanup=False)

    # Cleanup finished processes manually
    process_registry.cleanup_finished()

    # Shutdown all processes (call on application shutdown)
    # NOTE: After shutdown_all(), register() will raise RuntimeError
    process_registry.shutdown_all()
"""
import atexit
import logging
import signal
import subprocess
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Default maximum age for finished jobs before opportunistic cleanup removes them
# 1 hour is sufficient to allow for manual inspection while preventing memory leaks
DEFAULT_CLEANUP_MAX_AGE_HOURS = 1


class JobStatus(str, Enum):
    """Status of a background job."""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TERMINATED = "terminated"
    UNKNOWN = "unknown"


@dataclass
class JobInfo:
    """Information about a registered background job."""

    job_id: str
    pid: int
    job_type: str
    started_at: datetime
    command: List[str]
    working_directory: Optional[str] = None
    status: JobStatus = JobStatus.RUNNING
    exit_code: Optional[int] = None
    finished_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert job info to dictionary for API responses."""
        return {
            "job_id": self.job_id,
            "pid": self.pid,
            "job_type": self.job_type,
            "started_at": self.started_at.isoformat(),
            "status": self.status.value,
            "exit_code": self.exit_code,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "command": self.command,
            "working_directory": self.working_directory,
            "metadata": self.metadata,
        }


class ProcessRegistry:
    """
    Thread-safe registry for managing background subprocess instances.

    This singleton class tracks all spawned subprocesses, allowing for:
    - Status monitoring of individual processes
    - Listing all running processes
    - Cleanup of finished processes
    - Graceful shutdown of all processes on application exit

    Thread Safety:
        All operations on the internal process dictionary are protected
        by a reentrant lock to ensure thread safety.
    """

    _instance: Optional["ProcessRegistry"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "ProcessRegistry":
        """Ensure only one instance of ProcessRegistry exists (singleton)."""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        """Initialize the registry (only runs once due to singleton pattern)."""
        if self._initialized:
            return

        self._processes: Dict[str, tuple[subprocess.Popen, JobInfo]] = {}
        self._registry_lock = threading.RLock()
        self._job_counter = 0
        self._initialized = True
        self._shutdown_registered = False
        self._shutting_down = False

        logger.info("ProcessRegistry initialized")

    def _generate_job_id(self, job_type: str, pid: int) -> str:
        """Generate a unique job ID."""
        with self._registry_lock:
            self._job_counter += 1
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            return f"{job_type}_{timestamp}_{self._job_counter}_{pid}"

    def register(
        self,
        process: subprocess.Popen,
        job_type: str = "question_generation",
        command: Optional[List[str]] = None,
        working_directory: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ) -> JobInfo:
        """
        Register a new subprocess in the registry.

        Args:
            process: The subprocess.Popen instance to track
            job_type: Type of job (e.g., "question_generation")
            command: The command that was executed (for display)
            working_directory: The working directory where the command runs
            metadata: Additional metadata about the job (e.g., count, dry_run)

        Returns:
            JobInfo with the registered job details

        Raises:
            RuntimeError: If called during shutdown sequence
        """
        # Prevent new registrations during shutdown (BCQ-050)
        if self._shutting_down:
            raise RuntimeError(
                "Cannot register new processes: ProcessRegistry is shutting down"
            )

        job_id = self._generate_job_id(job_type, process.pid)

        job_info = JobInfo(
            job_id=job_id,
            pid=process.pid,
            job_type=job_type,
            started_at=datetime.now(timezone.utc),
            command=command or [],
            working_directory=working_directory,
            status=JobStatus.RUNNING,
            metadata=metadata or {},
        )

        with self._registry_lock:
            self._processes[job_id] = (process, job_info)

        logger.info(
            f"Registered background job: job_id={job_id}, "
            f"pid={process.pid}, type={job_type}"
        )

        return job_info

    def unregister(self, job_id: str) -> bool:
        """
        Remove a job from the registry.

        Args:
            job_id: The unique job ID

        Returns:
            True if the job was found and removed, False otherwise
        """
        with self._registry_lock:
            if job_id in self._processes:
                del self._processes[job_id]
                logger.info(f"Unregistered job: job_id={job_id}")
                return True
            return False

    def get_job_status(self, job_id: str) -> Optional[JobInfo]:
        """
        Get the current status of a job.

        Args:
            job_id: The unique job ID

        Returns:
            JobInfo with updated status, or None if not found
        """
        with self._registry_lock:
            if job_id not in self._processes:
                return None

            process, job_info = self._processes[job_id]
            self._update_job_status(process, job_info)
            return job_info

    def get_job_by_pid(self, pid: int) -> Optional[JobInfo]:
        """
        Get job information by process ID.

        Args:
            pid: The process ID

        Returns:
            JobInfo if found, None otherwise
        """
        with self._registry_lock:
            for process, job_info in self._processes.values():
                if job_info.pid == pid:
                    self._update_job_status(process, job_info)
                    return job_info
            return None

    def _update_job_status(
        self, process: subprocess.Popen, job_info: JobInfo
    ) -> JobInfo:
        """
        Update job status based on the current process state.

        Args:
            process: The subprocess.Popen instance
            job_info: The JobInfo to update

        Returns:
            Updated JobInfo
        """
        poll_result = process.poll()

        if poll_result is None:
            # Process is still running
            job_info.status = JobStatus.RUNNING
        else:
            # Process has finished
            job_info.exit_code = poll_result
            if job_info.finished_at is None:
                job_info.finished_at = datetime.now(timezone.utc)

            if poll_result == 0:
                job_info.status = JobStatus.COMPLETED
            elif poll_result < 0:
                # Negative exit code means killed by signal
                job_info.status = JobStatus.TERMINATED
            else:
                job_info.status = JobStatus.FAILED

        return job_info

    def list_jobs(
        self,
        job_type: Optional[str] = None,
        status: Optional[JobStatus] = None,
        include_finished: bool = True,
        opportunistic_cleanup: bool = True,
    ) -> List[JobInfo]:
        """
        List all registered jobs, optionally filtered.

        Args:
            job_type: Filter by job type (e.g., "question_generation")
            status: Filter by status
            include_finished: Whether to include finished jobs
            opportunistic_cleanup: If True (default), automatically remove
                finished jobs older than DEFAULT_CLEANUP_MAX_AGE_HOURS to
                prevent memory leaks in long-running applications.

        Returns:
            List of JobInfo for matching jobs
        """
        # Perform opportunistic cleanup of old finished jobs (BCQ-049)
        if opportunistic_cleanup:
            self._cleanup_old_finished_jobs()

        results = []

        with self._registry_lock:
            for process, job_info in self._processes.values():
                # Update status before filtering
                self._update_job_status(process, job_info)

                # Apply filters
                if job_type and job_info.job_type != job_type:
                    continue
                if status and job_info.status != status:
                    continue
                if not include_finished and job_info.status != JobStatus.RUNNING:
                    continue

                results.append(job_info)

        # Sort by started_at descending (most recent first)
        results.sort(key=lambda j: j.started_at, reverse=True)
        return results

    def cleanup_finished(self) -> int:
        """
        Remove finished processes from the registry.

        This should be called periodically to prevent memory leaks
        from accumulating finished process references.

        Returns:
            Number of processes cleaned up
        """
        to_remove = []

        with self._registry_lock:
            for job_id, (process, job_info) in self._processes.items():
                self._update_job_status(process, job_info)
                if job_info.status != JobStatus.RUNNING:
                    to_remove.append(job_id)

            for job_id in to_remove:
                del self._processes[job_id]

        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} finished processes")

        return len(to_remove)

    def _cleanup_old_finished_jobs(
        self, max_age_hours: float = DEFAULT_CLEANUP_MAX_AGE_HOURS
    ) -> int:
        """
        Remove finished jobs older than the specified age (BCQ-049).

        This is an internal method called opportunistically by list_jobs()
        and get_stats() to prevent memory leaks in long-running applications.
        Unlike cleanup_finished(), this only removes jobs that have been
        finished for longer than max_age_hours, preserving recent finished
        jobs for inspection.

        Args:
            max_age_hours: Maximum age in hours for finished jobs.
                Jobs finished more than this long ago will be removed.

        Returns:
            Number of old finished jobs cleaned up
        """
        to_remove = []
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        with self._registry_lock:
            for job_id, (process, job_info) in self._processes.items():
                self._update_job_status(process, job_info)

                # Only consider finished jobs (not running)
                if job_info.status == JobStatus.RUNNING:
                    continue

                # Remove if finished_at is older than cutoff
                if job_info.finished_at and job_info.finished_at < cutoff_time:
                    to_remove.append(job_id)

            for job_id in to_remove:
                del self._processes[job_id]

        if to_remove:
            logger.debug(
                f"Opportunistic cleanup: removed {len(to_remove)} finished jobs "
                f"older than {max_age_hours} hour(s)"
            )

        return len(to_remove)

    def terminate_job(self, job_id: str, force: bool = False) -> bool:
        """
        Terminate a running job.

        Args:
            job_id: The unique job ID
            force: If True, use SIGKILL instead of SIGTERM

        Returns:
            True if the job was found and terminated, False otherwise
        """
        with self._registry_lock:
            if job_id not in self._processes:
                return False

            process, job_info = self._processes[job_id]

            if process.poll() is not None:
                # Process already finished
                return False

            try:
                if force:
                    process.kill()
                    logger.info(f"Killed job: job_id={job_id}, pid={job_info.pid}")
                else:
                    process.terminate()
                    logger.info(f"Terminated job: job_id={job_id}, pid={job_info.pid}")
                return True
            except OSError as e:
                logger.error(f"Failed to terminate job {job_id}: {e}")
                return False

    def shutdown_all(self, timeout: float = 10.0) -> int:
        """
        Gracefully shutdown all running processes.

        This method:
        1. Sets shutdown flag to prevent new registrations (BCQ-050)
        2. Sends SIGTERM to all running processes
        3. Waits up to `timeout` seconds for graceful shutdown
        4. Sends SIGKILL to any processes still running
        5. Clears the registry and resets the shutdown flag

        After this method completes, the registry can be reused (e.g., in tests).

        Args:
            timeout: Seconds to wait for graceful shutdown before force kill

        Returns:
            Number of processes that were terminated
        """
        # Prevent new registrations during shutdown (BCQ-050)
        self._shutting_down = True

        terminated = 0
        running_processes = []

        with self._registry_lock:
            # First pass: send SIGTERM to all running processes
            for job_id, (process, job_info) in self._processes.items():
                if process.poll() is None:
                    try:
                        process.terminate()
                        running_processes.append((job_id, process, job_info))
                        terminated += 1
                        logger.info(
                            f"Sent SIGTERM to job: job_id={job_id}, pid={job_info.pid}"
                        )
                    except OSError as e:
                        logger.error(f"Failed to terminate job {job_id}: {e}")

        if not running_processes:
            logger.info("No running processes to shutdown")
            # Reset shutdown flag so registry can be reused (e.g., in tests)
            self._shutting_down = False
            return 0

        # Wait for graceful shutdown
        logger.info(
            f"Waiting up to {timeout}s for {len(running_processes)} "
            "processes to shutdown..."
        )

        import time

        start_time = time.time()
        while time.time() - start_time < timeout:
            still_running = []
            for job_id, process, job_info in running_processes:
                if process.poll() is None:
                    still_running.append((job_id, process, job_info))
            running_processes = still_running
            if not running_processes:
                break
            time.sleep(0.1)

        # Force kill any remaining processes
        for job_id, process, job_info in running_processes:
            if process.poll() is None:
                try:
                    process.kill()
                    logger.warning(
                        f"Force killed job: job_id={job_id}, pid={job_info.pid}"
                    )
                except OSError as e:
                    logger.error(f"Failed to kill job {job_id}: {e}")

        # Clear the registry
        with self._registry_lock:
            self._processes.clear()

        # Reset shutdown flag so registry can be reused (e.g., in tests)
        self._shutting_down = False

        logger.info(f"Shutdown complete. Terminated {terminated} processes")
        return terminated

    def get_stats(self, opportunistic_cleanup: bool = True) -> Dict[str, Any]:
        """
        Get statistics about registered processes.

        Args:
            opportunistic_cleanup: If True (default), automatically remove
                finished jobs older than DEFAULT_CLEANUP_MAX_AGE_HOURS to
                prevent memory leaks in long-running applications.

        Returns:
            Dictionary with process statistics
        """
        # Perform opportunistic cleanup of old finished jobs (BCQ-049)
        if opportunistic_cleanup:
            self._cleanup_old_finished_jobs()

        with self._registry_lock:
            running = 0
            completed = 0
            failed = 0
            terminated = 0

            for process, job_info in self._processes.values():
                self._update_job_status(process, job_info)
                if job_info.status == JobStatus.RUNNING:
                    running += 1
                elif job_info.status == JobStatus.COMPLETED:
                    completed += 1
                elif job_info.status == JobStatus.FAILED:
                    failed += 1
                elif job_info.status == JobStatus.TERMINATED:
                    terminated += 1

            return {
                "total_registered": len(self._processes),
                "running": running,
                "completed": completed,
                "failed": failed,
                "terminated": terminated,
            }

    def register_shutdown_handler(self):
        """
        Register signal handlers for graceful shutdown.

        This should be called once during application startup.
        Note: Signal handlers can only be registered from the main thread.
        In non-main threads (e.g., during testing), only the atexit handler
        will be registered as a fallback.
        """
        if self._shutdown_registered:
            return

        def signal_handler(signum, frame):
            """Handle shutdown signals."""
            signal_name = signal.Signals(signum).name
            logger.info(
                f"Received {signal_name}, shutting down background processes..."
            )
            self.shutdown_all(timeout=5.0)

        # Register for common shutdown signals
        # Note: signal handlers can only be registered in the main thread
        try:
            signal.signal(signal.SIGTERM, signal_handler)
            signal.signal(signal.SIGINT, signal_handler)
            logger.info("Signal handlers registered for background processes")
        except ValueError:
            # Signal handlers can only be registered from the main thread
            # This is expected during testing with TestClient
            logger.debug(
                "Could not register signal handlers (not in main thread). "
                "Using atexit handler only."
            )

        # Also register atexit handler as a fallback
        atexit.register(self._atexit_cleanup)

        self._shutdown_registered = True
        logger.info("Shutdown handlers registered for background processes")

    def _atexit_cleanup(self):
        """Atexit handler for cleanup."""
        if self._processes:
            logger.info("Atexit cleanup: shutting down background processes...")
            self.shutdown_all(timeout=5.0)


# Global singleton instance
process_registry = ProcessRegistry()
