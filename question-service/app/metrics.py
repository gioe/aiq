"""Metrics tracking for question generation pipeline.

This module provides functionality to track and report metrics about
question generation, evaluation, deduplication, and database operations.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .error_classifier import ClassifiedError

logger = logging.getLogger(__name__)


class MetricsTracker:
    """Tracks metrics for question generation pipeline operations.

    This class provides methods to record various metrics and generate
    comprehensive reports about pipeline execution.
    """

    def __init__(self):
        """Initialize metrics tracker."""
        self.reset()
        logger.debug("MetricsTracker initialized")

    def reset(self) -> None:
        """Reset all metrics to initial state."""
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None

        # Generation metrics
        self.questions_requested = 0
        self.questions_generated = 0
        self.generation_failures = 0
        self.questions_by_provider: Dict[str, int] = defaultdict(int)
        self.questions_by_type: Dict[str, int] = defaultdict(int)
        self.questions_by_difficulty: Dict[str, int] = defaultdict(int)
        self.generation_errors: List[Dict[str, Any]] = []

        # Evaluation metrics
        self.questions_evaluated = 0
        self.questions_approved = 0
        self.questions_rejected = 0
        self.evaluation_failures = 0
        self.evaluation_scores: List[float] = []
        self.evaluation_errors: List[Dict[str, Any]] = []

        # Deduplication metrics
        self.questions_checked_for_duplicates = 0
        self.duplicates_found = 0
        self.exact_duplicates = 0
        self.semantic_duplicates = 0
        self.deduplication_errors: List[Dict[str, Any]] = []

        # Database metrics
        self.questions_inserted = 0
        self.insertion_failures = 0
        self.insertion_errors: List[Dict[str, Any]] = []

        # API metrics (costs)
        self.api_calls_by_provider: Dict[str, int] = defaultdict(int)
        self.total_api_calls = 0

        # Error categorization metrics
        self.errors_by_category: Dict[str, int] = defaultdict(int)
        self.errors_by_severity: Dict[str, int] = defaultdict(int)
        self.critical_errors: List[Dict[str, Any]] = []
        self.classified_errors: List[Dict[str, Any]] = []

        logger.debug("Metrics reset")

    def start_run(self) -> None:
        """Mark the start of a pipeline run."""
        self.start_time = datetime.now(timezone.utc)
        logger.info("Pipeline run started")

    def end_run(self) -> None:
        """Mark the end of a pipeline run."""
        self.end_time = datetime.now(timezone.utc)
        logger.info("Pipeline run completed")

    def record_generation_request(self, count: int) -> None:
        """Record a request to generate questions.

        Args:
            count: Number of questions requested
        """
        self.questions_requested += count
        logger.debug(f"Recorded generation request: {count} questions")

    def record_generation_success(
        self,
        provider: str,
        question_type: str,
        difficulty: str,
    ) -> None:
        """Record successful question generation.

        Args:
            provider: LLM provider name
            question_type: Type of question
            difficulty: Difficulty level
        """
        self.questions_generated += 1
        self.questions_by_provider[provider] += 1
        self.questions_by_type[question_type] += 1
        self.questions_by_difficulty[difficulty] += 1
        self.api_calls_by_provider[provider] += 1
        self.total_api_calls += 1

        logger.debug(f"Generation success: {provider}/{question_type}/{difficulty}")

    def record_generation_failure(
        self,
        provider: str,
        error: str,
        question_type: Optional[str] = None,
        difficulty: Optional[str] = None,
        classified_error: Optional[ClassifiedError] = None,
    ) -> None:
        """Record failed question generation.

        Args:
            provider: LLM provider name
            error: Error message
            question_type: Type of question (optional)
            difficulty: Difficulty level (optional)
            classified_error: Classified error with category and severity (optional)
        """
        self.generation_failures += 1
        error_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "provider": provider,
            "question_type": question_type,
            "difficulty": difficulty,
            "error": error,
        }

        # Add classification info if available
        if classified_error:
            error_record["category"] = classified_error.category.value
            error_record["severity"] = classified_error.severity.value
            error_record["is_retryable"] = str(classified_error.is_retryable)

            # Track by category and severity
            self.errors_by_category[classified_error.category.value] += 1
            self.errors_by_severity[classified_error.severity.value] += 1

            # Track critical errors separately
            if classified_error.severity.value == "critical":
                self.critical_errors.append(classified_error.to_dict())

            # Store classified error
            self.classified_errors.append(classified_error.to_dict())

        self.generation_errors.append(error_record)
        logger.debug(f"Generation failure: {provider} - {error}")

    def record_evaluation_success(
        self,
        score: float,
        approved: bool,
        arbiter_model: str,
    ) -> None:
        """Record successful question evaluation.

        Args:
            score: Evaluation score
            approved: Whether question was approved
            arbiter_model: Arbiter model used
        """
        self.questions_evaluated += 1
        self.evaluation_scores.append(score)

        if approved:
            self.questions_approved += 1
        else:
            self.questions_rejected += 1

        # Track API call for arbiter
        provider = arbiter_model.split("/")[0]
        self.api_calls_by_provider[provider] += 1
        self.total_api_calls += 1

        logger.debug(f"Evaluation success: score={score:.3f}, approved={approved}")

    def record_evaluation_failure(
        self,
        error: str,
        arbiter_model: Optional[str] = None,
    ) -> None:
        """Record failed question evaluation.

        Args:
            error: Error message
            arbiter_model: Arbiter model used (optional)
        """
        self.evaluation_failures += 1
        self.evaluation_errors.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "arbiter_model": arbiter_model,
                "error": error,
            }
        )
        logger.debug(f"Evaluation failure: {error}")

    def record_duplicate_check(
        self,
        is_duplicate: bool,
        duplicate_type: Optional[str] = None,
    ) -> None:
        """Record duplicate check result.

        Args:
            is_duplicate: Whether question is a duplicate
            duplicate_type: Type of duplicate ("exact" or "semantic")
        """
        self.questions_checked_for_duplicates += 1

        if is_duplicate:
            self.duplicates_found += 1

            if duplicate_type == "exact":
                self.exact_duplicates += 1
            elif duplicate_type == "semantic":
                self.semantic_duplicates += 1

        logger.debug(
            f"Duplicate check: is_duplicate={is_duplicate}, type={duplicate_type}"
        )

    def record_deduplication_failure(self, error: str) -> None:
        """Record failed duplicate check.

        Args:
            error: Error message
        """
        self.deduplication_errors.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": error,
            }
        )
        logger.debug(f"Deduplication failure: {error}")

    def record_insertion_success(self, count: int = 1) -> None:
        """Record successful database insertion.

        Args:
            count: Number of questions inserted
        """
        self.questions_inserted += count
        logger.debug(f"Insertion success: {count} questions")

    def record_insertion_failure(self, error: str, count: int = 1) -> None:
        """Record failed database insertion.

        Args:
            error: Error message
            count: Number of questions that failed to insert
        """
        self.insertion_failures += count
        self.insertion_errors.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": count,
                "error": error,
            }
        )
        logger.debug(f"Insertion failure: {error}")

    def get_duration_seconds(self) -> float:
        """Get duration of pipeline run in seconds.

        Returns:
            Duration in seconds, or 0 if run not completed
        """
        if not self.start_time or not self.end_time:
            return 0.0

        return (self.end_time - self.start_time).total_seconds()

    def get_summary(self) -> Dict[str, Any]:
        """Generate comprehensive metrics summary.

        Returns:
            Dictionary with all metrics and statistics
        """
        duration = self.get_duration_seconds()

        summary = {
            "execution": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "duration_seconds": round(duration, 2),
            },
            "generation": {
                "requested": self.questions_requested,
                "generated": self.questions_generated,
                "failed": self.generation_failures,
                "success_rate": (
                    self.questions_generated / self.questions_requested
                    if self.questions_requested > 0
                    else 0.0
                ),
                "by_provider": dict(self.questions_by_provider),
                "by_type": dict(self.questions_by_type),
                "by_difficulty": dict(self.questions_by_difficulty),
                "errors": self.generation_errors[-10:],  # Last 10 errors
            },
            "evaluation": {
                "evaluated": self.questions_evaluated,
                "approved": self.questions_approved,
                "rejected": self.questions_rejected,
                "failed": self.evaluation_failures,
                "approval_rate": (
                    self.questions_approved / self.questions_evaluated
                    if self.questions_evaluated > 0
                    else 0.0
                ),
                "average_score": (
                    sum(self.evaluation_scores) / len(self.evaluation_scores)
                    if self.evaluation_scores
                    else 0.0
                ),
                "min_score": min(self.evaluation_scores)
                if self.evaluation_scores
                else 0.0,
                "max_score": max(self.evaluation_scores)
                if self.evaluation_scores
                else 0.0,
                "errors": self.evaluation_errors[-10:],  # Last 10 errors
            },
            "deduplication": {
                "checked": self.questions_checked_for_duplicates,
                "duplicates_found": self.duplicates_found,
                "exact_duplicates": self.exact_duplicates,
                "semantic_duplicates": self.semantic_duplicates,
                "duplicate_rate": (
                    self.duplicates_found / self.questions_checked_for_duplicates
                    if self.questions_checked_for_duplicates > 0
                    else 0.0
                ),
                "errors": self.deduplication_errors[-10:],  # Last 10 errors
            },
            "database": {
                "inserted": self.questions_inserted,
                "failed": self.insertion_failures,
                "success_rate": (
                    self.questions_inserted
                    / (self.questions_inserted + self.insertion_failures)
                    if (self.questions_inserted + self.insertion_failures) > 0
                    else 0.0
                ),
                "errors": self.insertion_errors[-10:],  # Last 10 errors
            },
            "api": {
                "total_calls": self.total_api_calls,
                "by_provider": dict(self.api_calls_by_provider),
            },
            "error_classification": {
                "by_category": dict(self.errors_by_category),
                "by_severity": dict(self.errors_by_severity),
                "critical_errors": len(self.critical_errors),
                "critical_error_details": self.critical_errors,
                "total_classified_errors": len(self.classified_errors),
            },
            "overall": {
                "questions_requested": self.questions_requested,
                "questions_final_output": self.questions_inserted,
                "overall_success_rate": (
                    self.questions_inserted / self.questions_requested
                    if self.questions_requested > 0
                    else 0.0
                ),
                "total_errors": (
                    self.generation_failures
                    + self.evaluation_failures
                    + self.insertion_failures
                ),
            },
        }

        return summary

    def print_summary(self) -> None:
        """Print formatted metrics summary to console."""
        summary = self.get_summary()

        print("\n" + "=" * 80)
        print("QUESTION GENERATION PIPELINE - EXECUTION SUMMARY")
        print("=" * 80)

        # Execution info
        exec_info = summary["execution"]
        print("\nExecution Time:")
        print(f"  Started:  {exec_info['start_time']}")
        print(f"  Ended:    {exec_info['end_time']}")
        print(f"  Duration: {exec_info['duration_seconds']}s")

        # Generation stats
        gen = summary["generation"]
        print("\nGeneration:")
        print(f"  Requested: {gen['requested']}")
        print(f"  Generated: {gen['generated']}")
        print(f"  Failed:    {gen['failed']}")
        print(f"  Success Rate: {gen['success_rate']:.1%}")
        print(f"  By Provider: {gen['by_provider']}")

        # Evaluation stats
        eval_stats = summary["evaluation"]
        print("\nEvaluation:")
        print(f"  Evaluated: {eval_stats['evaluated']}")
        print(f"  Approved:  {eval_stats['approved']}")
        print(f"  Rejected:  {eval_stats['rejected']}")
        print(f"  Approval Rate: {eval_stats['approval_rate']:.1%}")
        print(f"  Avg Score: {eval_stats['average_score']:.3f}")

        # Deduplication stats
        dedup = summary["deduplication"]
        print("\nDeduplication:")
        print(f"  Checked:    {dedup['checked']}")
        print(
            f"  Duplicates: {dedup['duplicates_found']} "
            f"(Exact: {dedup['exact_duplicates']}, "
            f"Semantic: {dedup['semantic_duplicates']})"
        )
        print(f"  Duplicate Rate: {dedup['duplicate_rate']:.1%}")

        # Database stats
        db = summary["database"]
        print("\nDatabase:")
        print(f"  Inserted: {db['inserted']}")
        print(f"  Failed:   {db['failed']}")
        print(f"  Success Rate: {db['success_rate']:.1%}")

        # API usage
        api = summary["api"]
        print("\nAPI Usage:")
        print(f"  Total Calls: {api['total_calls']}")
        print(f"  By Provider: {api['by_provider']}")

        # Error classification
        error_class = summary["error_classification"]
        if error_class["total_classified_errors"] > 0:
            print("\nError Classification:")
            print(f"  Total Classified: {error_class['total_classified_errors']}")
            print(f"  Critical Errors:  {error_class['critical_errors']}")
            print(f"  By Category: {error_class['by_category']}")
            print(f"  By Severity: {error_class['by_severity']}")

        # Overall
        overall = summary["overall"]
        print("\nOverall:")
        print(f"  Questions Requested: {overall['questions_requested']}")
        print(f"  Questions Inserted:  {overall['questions_final_output']}")
        print(f"  Overall Success:     {overall['overall_success_rate']:.1%}")
        print(f"  Total Errors:        {overall['total_errors']}")

        print("=" * 80 + "\n")

    def save_summary(self, output_path: str) -> None:
        """Save metrics summary to JSON file.

        Args:
            output_path: Path to output file

        Raises:
            Exception: If file write fails
        """
        try:
            summary = self.get_summary()

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, "w") as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Metrics summary saved to: {output_path}")

        except Exception as e:
            logger.error(f"Failed to save metrics summary: {str(e)}")
            raise


# Global metrics tracker instance
_metrics_tracker: Optional[MetricsTracker] = None


def get_metrics_tracker() -> MetricsTracker:
    """Get the global metrics tracker instance.

    Returns:
        Global MetricsTracker instance
    """
    global _metrics_tracker

    if _metrics_tracker is None:
        _metrics_tracker = MetricsTracker()

    return _metrics_tracker


def reset_metrics() -> None:
    """Reset the global metrics tracker."""
    global _metrics_tracker

    if _metrics_tracker is not None:
        _metrics_tracker.reset()
