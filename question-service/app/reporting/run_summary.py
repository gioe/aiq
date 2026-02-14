"""Lightweight run summary for pipeline reporting.

Captures only the data that reporter.py needs to POST to the backend API.
Replaces the deprecated MetricsTracker for this purpose.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.observability.cost_tracking import get_cost_tracker
from app.providers.base import get_retry_metrics
from app.infrastructure.circuit_breaker import get_circuit_breaker_registry


@dataclass
class RunSummary:
    """Lightweight summary of a pipeline run for API reporting.

    Collects the minimal set of metrics that reporter.py needs to build
    the backend API payload.  Unlike the deprecated MetricsTracker this
    class carries no processing logic — it is a plain data container.
    """

    # Execution timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    # Generation
    questions_requested: int = 0
    questions_generated: int = 0
    generation_failures: int = 0
    questions_by_provider: Dict[str, int] = field(default_factory=dict)
    questions_by_type: Dict[str, int] = field(default_factory=dict)
    questions_by_difficulty: Dict[str, int] = field(default_factory=dict)

    # Evaluation
    questions_evaluated: int = 0
    questions_approved: int = 0
    questions_rejected: int = 0
    evaluation_scores: List[float] = field(default_factory=list)

    # Deduplication
    duplicates_found: int = 0
    exact_duplicates: int = 0
    semantic_duplicates: int = 0
    questions_checked_for_duplicates: int = 0

    # Database
    questions_inserted: int = 0
    insertion_failures: int = 0

    # API usage
    total_api_calls: int = 0
    api_calls_by_provider: Dict[str, int] = field(default_factory=dict)

    # Error classification
    errors_by_category: Dict[str, int] = field(default_factory=dict)
    errors_by_severity: Dict[str, int] = field(default_factory=dict)
    critical_errors: int = 0

    def start_run(self) -> None:
        """Mark the start of a pipeline run."""
        self.start_time = datetime.now(timezone.utc)

    def end_run(self) -> None:
        """Mark the end of a pipeline run."""
        self.end_time = datetime.now(timezone.utc)

    def record_generation_success(
        self, provider: str, question_type: str, difficulty: str
    ) -> None:
        """Record a successful question generation."""
        self.questions_generated += 1
        self.questions_by_provider[provider] = (
            self.questions_by_provider.get(provider, 0) + 1
        )
        self.questions_by_type[question_type] = (
            self.questions_by_type.get(question_type, 0) + 1
        )
        self.questions_by_difficulty[difficulty] = (
            self.questions_by_difficulty.get(difficulty, 0) + 1
        )
        self.api_calls_by_provider[provider] = (
            self.api_calls_by_provider.get(provider, 0) + 1
        )
        self.total_api_calls += 1

    def record_evaluation_success(
        self, score: float, approved: bool, judge_model: str
    ) -> None:
        """Record a successful question evaluation."""
        self.questions_evaluated += 1
        self.evaluation_scores.append(score)
        if approved:
            self.questions_approved += 1
        else:
            self.questions_rejected += 1
        provider = judge_model.split("/")[0]
        self.api_calls_by_provider[provider] = (
            self.api_calls_by_provider.get(provider, 0) + 1
        )
        self.total_api_calls += 1

    def record_duplicate_check(
        self, is_duplicate: bool, duplicate_type: Optional[str] = None
    ) -> None:
        """Record a deduplication check result."""
        self.questions_checked_for_duplicates += 1
        if is_duplicate:
            self.duplicates_found += 1
            if duplicate_type == "exact":
                self.exact_duplicates += 1
            elif duplicate_type == "semantic":
                self.semantic_duplicates += 1

    def record_insertion_success(self, count: int = 1) -> None:
        """Record successful database insertion."""
        self.questions_inserted += count

    def record_insertion_failure(self, count: int = 1) -> None:
        """Record failed database insertion."""
        self.insertion_failures += count

    def _duration_seconds(self) -> float:
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()

    def to_summary_dict(self) -> Dict[str, Any]:
        """Return the dict shape expected by ``reporter._transform_metrics_to_payload``.

        The structure mirrors ``MetricsTracker.get_summary()`` so the
        reporter can consume it without changes.
        """
        duration = self._duration_seconds()
        eval_scores = self.evaluation_scores

        return {
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
            },
            "evaluation": {
                "evaluated": self.questions_evaluated,
                "approved": self.questions_approved,
                "rejected": self.questions_rejected,
                "approval_rate": (
                    self.questions_approved / self.questions_evaluated
                    if self.questions_evaluated > 0
                    else 0.0
                ),
                "average_score": (
                    sum(eval_scores) / len(eval_scores) if eval_scores else 0.0
                ),
                "min_score": min(eval_scores) if eval_scores else 0.0,
                "max_score": max(eval_scores) if eval_scores else 0.0,
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
            },
            "api": {
                "total_calls": self.total_api_calls,
                "by_provider": dict(self.api_calls_by_provider),
            },
            "error_classification": {
                "by_category": dict(self.errors_by_category),
                "by_severity": dict(self.errors_by_severity),
                "critical_errors": self.critical_errors,
            },
            "overall": {
                "questions_requested": self.questions_requested,
                "questions_final_output": self.questions_inserted,
                "overall_success_rate": (
                    self.questions_inserted / self.questions_requested
                    if self.questions_requested > 0
                    else 0.0
                ),
                "total_errors": (self.generation_failures + self.insertion_failures),
            },
            "retry": get_retry_metrics().get_summary(),
            "circuit_breaker": get_circuit_breaker_registry().get_all_stats(),
            "cost": get_cost_tracker().get_summary(),
        }
