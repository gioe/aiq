"""
Background thread calibration job runner (TASK-862).

This module provides a singleton CalibrationRunner that manages IRT calibration
jobs in background threads with concurrency control.

Key design:
- Uses threading.Thread (daemon=True) to run calibration in background
- Creates its own SessionLocal() DB session for the thread (NOT request session)
- Module-level lock prevents concurrent calibration runs
- In-memory dict tracks job state
- _current_running_job_id tracks if a job is active (cleared in finally block)
"""
import logging
import secrets
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.core.cat.calibration import CalibrationError, run_calibration_job
from app.models.base import SessionLocal

logger = logging.getLogger(__name__)


@dataclass
class CalibrationJobState:
    """State for a single calibration job."""

    job_id: str
    status: str  # "pending" | "running" | "completed" | "failed"
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Dict] = None
    error_message: Optional[str] = None


class CalibrationRunner:
    """
    Singleton runner for IRT calibration jobs.

    Only one calibration can run at a time to prevent database contention
    and resource exhaustion.
    """

    def __init__(self):
        """Initialize the calibration runner."""
        self._lock = threading.Lock()
        self._jobs: Dict[str, CalibrationJobState] = {}
        self._current_running_job_id: Optional[str] = None

    def start_job(
        self,
        question_ids: Optional[list] = None,
        min_responses: int = 50,
        bootstrap_se: bool = True,
    ) -> CalibrationJobState:
        """
        Start a new calibration job in a background thread.

        Args:
            question_ids: Specific question IDs to calibrate (None = all eligible)
            min_responses: Minimum responses per item
            bootstrap_se: Whether to compute bootstrap standard errors

        Returns:
            CalibrationJobState with job_id and initial status

        Raises:
            RuntimeError: If a job is already running
        """
        with self._lock:
            if self._current_running_job_id is not None:
                current_job = self._jobs.get(self._current_running_job_id)
                if current_job and current_job.status == "running":
                    raise RuntimeError(
                        f"Calibration job already running: {self._current_running_job_id}"
                    )

            # Generate unique job ID
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
            random_hex = secrets.token_hex(4)
            job_id = f"irt_calibration_{timestamp}_{random_hex}"

            # Create job state
            job = CalibrationJobState(
                job_id=job_id,
                status="running",
                started_at=datetime.now(timezone.utc),
            )
            self._jobs[job_id] = job
            self._current_running_job_id = job_id

        # Start background thread
        thread = threading.Thread(
            target=self._run_calibration_thread,
            args=(job_id, question_ids, min_responses, bootstrap_se),
            daemon=True,
        )
        thread.start()

        logger.info(f"Started calibration job: {job_id}")
        return job

    def _run_calibration_thread(
        self,
        job_id: str,
        question_ids: Optional[list],
        min_responses: int,
        bootstrap_se: bool,
    ):
        """
        Run calibration in a background thread.

        Creates its own database session for thread-safe operation.
        """
        db = None
        try:
            # Create a new database session for this thread
            db = SessionLocal()

            logger.info(
                f"Calibration job {job_id} started in thread: "
                f"question_ids={'all' if question_ids is None else len(question_ids)}, "
                f"min_responses={min_responses}, bootstrap_se={bootstrap_se}"
            )

            # Run the calibration job
            summary = run_calibration_job(
                db=db,
                question_ids=question_ids,
                min_responses=min_responses,
                bootstrap_se=bootstrap_se,
            )

            # Update job state with results
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.result = {
                        "calibrated": summary["calibrated"],
                        "skipped": summary["skipped"],
                        "mean_difficulty": summary["mean_difficulty"],
                        "mean_discrimination": summary["mean_discrimination"],
                    }

            logger.info(
                f"Calibration job {job_id} completed: "
                f"{summary['calibrated']} calibrated, {summary['skipped']} skipped"
            )

        except CalibrationError as e:
            # CalibrationError is expected - handle gracefully
            logger.warning(f"Calibration job {job_id} failed: {e.message}")
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "failed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = e.message

        except Exception as e:
            # Unexpected error - log full traceback
            logger.exception(f"Calibration job {job_id} failed with unexpected error")
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    job.status = "failed"
                    job.completed_at = datetime.now(timezone.utc)
                    job.error_message = f"Unexpected error: {str(e)}"

        finally:
            # Clean up
            if db:
                db.close()

            # Clear current running job
            with self._lock:
                if self._current_running_job_id == job_id:
                    self._current_running_job_id = None

    def get_job(self, job_id: str) -> Optional[CalibrationJobState]:
        """
        Get the state of a calibration job.

        Args:
            job_id: Job identifier

        Returns:
            CalibrationJobState if found, None otherwise
        """
        with self._lock:
            return self._jobs.get(job_id)


# Singleton instance
calibration_runner = CalibrationRunner()
