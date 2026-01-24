"""Tests for metrics tracking module."""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.metrics import MetricsTracker, get_metrics_tracker, reset_metrics


class TestMetricsTracker:
    """Tests for MetricsTracker class."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh metrics tracker for each test."""
        tracker = MetricsTracker()
        tracker.reset()
        return tracker

    def test_initialization(self, tracker):
        """Test that tracker initializes with zero metrics."""
        assert tracker.questions_requested == 0
        assert tracker.questions_generated == 0
        assert tracker.generation_failures == 0
        assert tracker.questions_evaluated == 0
        assert tracker.questions_approved == 0
        assert tracker.questions_rejected == 0
        assert tracker.duplicates_found == 0
        assert tracker.questions_inserted == 0
        assert tracker.start_time is None
        assert tracker.end_time is None

    def test_reset(self, tracker):
        """Test that reset clears all metrics."""
        # Set some metrics
        tracker.questions_requested = 10
        tracker.questions_generated = 5
        tracker.generation_failures = 2

        # Reset
        tracker.reset()

        # Verify all metrics are cleared
        assert tracker.questions_requested == 0
        assert tracker.questions_generated == 0
        assert tracker.generation_failures == 0

    def test_start_and_end_run(self, tracker):
        """Test marking start and end of pipeline run."""
        tracker.start_run()
        assert tracker.start_time is not None
        assert isinstance(tracker.start_time, datetime)

        tracker.end_run()
        assert tracker.end_time is not None
        assert isinstance(tracker.end_time, datetime)
        assert tracker.end_time >= tracker.start_time

    def test_get_duration_seconds(self, tracker):
        """Test duration calculation."""
        # Before start/end
        assert tracker.get_duration_seconds() == pytest.approx(0.0)

        # After start/end
        tracker.start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        tracker.end_time = datetime(2024, 1, 1, 12, 5, 30, tzinfo=timezone.utc)

        duration = tracker.get_duration_seconds()
        assert duration == pytest.approx(330.0)  # 5 minutes 30 seconds

    def test_record_generation_request(self, tracker):
        """Test recording generation requests."""
        tracker.record_generation_request(10)
        assert tracker.questions_requested == 10

        tracker.record_generation_request(5)
        assert tracker.questions_requested == 15

    def test_record_generation_success(self, tracker):
        """Test recording successful question generation."""
        tracker.record_generation_success(
            provider="openai",
            question_type="pattern_recognition",
            difficulty="easy",
        )

        assert tracker.questions_generated == 1
        assert tracker.questions_by_provider["openai"] == 1
        assert tracker.questions_by_type["pattern_recognition"] == 1
        assert tracker.questions_by_difficulty["easy"] == 1
        assert tracker.api_calls_by_provider["openai"] == 1
        assert tracker.total_api_calls == 1

    def test_record_generation_failure(self, tracker):
        """Test recording failed question generation."""
        tracker.record_generation_failure(
            provider="anthropic",
            error="API timeout",
            question_type="logical_reasoning",
            difficulty="hard",
        )

        assert tracker.generation_failures == 1
        assert len(tracker.generation_errors) == 1

        error = tracker.generation_errors[0]
        assert error["provider"] == "anthropic"
        assert error["error"] == "API timeout"
        assert error["question_type"] == "logical_reasoning"
        assert "timestamp" in error

    def test_record_evaluation_success_approved(self, tracker):
        """Test recording successful evaluation with approval."""
        tracker.record_evaluation_success(
            score=0.85,
            approved=True,
            judge_model="openai/gpt-4",
        )

        assert tracker.questions_evaluated == 1
        assert tracker.questions_approved == 1
        assert tracker.questions_rejected == 0
        assert 0.85 in tracker.evaluation_scores
        assert tracker.api_calls_by_provider["openai"] == 1

    def test_record_evaluation_success_rejected(self, tracker):
        """Test recording successful evaluation with rejection."""
        tracker.record_evaluation_success(
            score=0.65,
            approved=False,
            judge_model="anthropic/claude",
        )

        assert tracker.questions_evaluated == 1
        assert tracker.questions_approved == 0
        assert tracker.questions_rejected == 1
        assert 0.65 in tracker.evaluation_scores

    def test_record_evaluation_failure(self, tracker):
        """Test recording failed evaluation."""
        tracker.record_evaluation_failure(
            error="Invalid response format",
            judge_model="google/gemini",
        )

        assert tracker.evaluation_failures == 1
        assert len(tracker.evaluation_errors) == 1

        error = tracker.evaluation_errors[0]
        assert error["error"] == "Invalid response format"
        assert error["judge_model"] == "google/gemini"

    def test_record_duplicate_check_not_duplicate(self, tracker):
        """Test recording duplicate check for non-duplicate."""
        tracker.record_duplicate_check(
            is_duplicate=False,
            duplicate_type=None,
        )

        assert tracker.questions_checked_for_duplicates == 1
        assert tracker.duplicates_found == 0
        assert tracker.exact_duplicates == 0
        assert tracker.semantic_duplicates == 0

    def test_record_duplicate_check_exact(self, tracker):
        """Test recording exact duplicate detection."""
        tracker.record_duplicate_check(
            is_duplicate=True,
            duplicate_type="exact",
        )

        assert tracker.questions_checked_for_duplicates == 1
        assert tracker.duplicates_found == 1
        assert tracker.exact_duplicates == 1
        assert tracker.semantic_duplicates == 0

    def test_record_duplicate_check_semantic(self, tracker):
        """Test recording semantic duplicate detection."""
        tracker.record_duplicate_check(
            is_duplicate=True,
            duplicate_type="semantic",
        )

        assert tracker.questions_checked_for_duplicates == 1
        assert tracker.duplicates_found == 1
        assert tracker.exact_duplicates == 0
        assert tracker.semantic_duplicates == 1

    def test_record_deduplication_failure(self, tracker):
        """Test recording deduplication failure."""
        tracker.record_deduplication_failure(error="Embedding API failed")

        assert len(tracker.deduplication_errors) == 1
        error = tracker.deduplication_errors[0]
        assert error["error"] == "Embedding API failed"
        assert "timestamp" in error

    def test_record_insertion_success(self, tracker):
        """Test recording successful database insertion."""
        tracker.record_insertion_success(count=5)

        assert tracker.questions_inserted == 5

    def test_record_insertion_failure(self, tracker):
        """Test recording failed database insertion."""
        tracker.record_insertion_failure(
            error="Database connection lost",
            count=3,
        )

        assert tracker.insertion_failures == 3
        assert len(tracker.insertion_errors) == 1

        error = tracker.insertion_errors[0]
        assert error["error"] == "Database connection lost"
        assert error["count"] == 3

    def test_get_summary_basic(self, tracker):
        """Test getting summary with basic metrics."""
        tracker.start_run()
        tracker.record_generation_request(10)
        tracker.record_generation_success("openai", "pattern", "easy")
        tracker.end_run()

        summary = tracker.get_summary()

        # Check structure
        assert "execution" in summary
        assert "generation" in summary
        assert "evaluation" in summary
        assert "deduplication" in summary
        assert "database" in summary
        assert "api" in summary
        assert "overall" in summary

        # Check generation metrics
        gen = summary["generation"]
        assert gen["requested"] == 10
        assert gen["generated"] == 1
        assert gen["by_provider"]["openai"] == 1

    def test_get_summary_success_rates(self, tracker):
        """Test success rate calculations in summary."""
        tracker.start_run()

        # Generation: 8/10 success
        tracker.record_generation_request(10)
        for _ in range(8):
            tracker.record_generation_success("openai", "pattern", "easy")
        for _ in range(2):
            tracker.record_generation_failure("openai", "error")

        # Evaluation: 6/8 approved
        for _ in range(6):
            tracker.record_evaluation_success(0.8, True, "openai/gpt-4")
        for _ in range(2):
            tracker.record_evaluation_success(0.6, False, "openai/gpt-4")

        # Database: 6/6 inserted
        tracker.record_insertion_success(6)

        tracker.end_run()

        summary = tracker.get_summary()

        # Check success rates
        assert summary["generation"]["success_rate"] == pytest.approx(0.8)
        assert summary["evaluation"]["approval_rate"] == pytest.approx(0.75)
        assert summary["database"]["success_rate"] == pytest.approx(1.0)
        assert summary["overall"]["overall_success_rate"] == pytest.approx(0.6)

    def test_get_summary_with_evaluation_scores(self, tracker):
        """Test summary with evaluation score statistics."""
        tracker.record_evaluation_success(0.7, True, "openai/gpt-4")
        tracker.record_evaluation_success(0.8, True, "openai/gpt-4")
        tracker.record_evaluation_success(0.9, True, "openai/gpt-4")

        summary = tracker.get_summary()

        eval_stats = summary["evaluation"]
        assert eval_stats["average_score"] == pytest.approx(0.8, rel=0.01)
        assert eval_stats["min_score"] == pytest.approx(0.7)
        assert eval_stats["max_score"] == pytest.approx(0.9)

    def test_get_summary_api_usage(self, tracker):
        """Test API usage tracking in summary."""
        tracker.record_generation_success("openai", "pattern", "easy")
        tracker.record_generation_success("anthropic", "logic", "medium")
        tracker.record_evaluation_success(0.8, True, "google/gemini")

        summary = tracker.get_summary()

        api = summary["api"]
        assert api["total_calls"] == 3
        assert api["by_provider"]["openai"] == 1
        assert api["by_provider"]["anthropic"] == 1
        assert api["by_provider"]["google"] == 1

    def test_save_summary(self, tracker):
        """Test saving summary to JSON file."""
        tracker.start_run()
        tracker.record_generation_request(5)
        tracker.record_generation_success("openai", "pattern", "easy")
        tracker.end_run()

        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = Path(tmpdir) / "metrics" / "summary.json"

            tracker.save_summary(str(output_file))

            # Check file was created
            assert output_file.exists()

            # Check content is valid JSON
            with open(output_file) as f:
                summary = json.load(f)

            assert "generation" in summary
            assert summary["generation"]["requested"] == 5
            assert summary["generation"]["generated"] == 1

    def test_print_summary(self, tracker, capsys):
        """Test printing summary to console."""
        tracker.start_run()
        tracker.record_generation_request(10)
        tracker.record_generation_success("openai", "pattern", "easy")
        tracker.end_run()

        tracker.print_summary()

        captured = capsys.readouterr()
        output = captured.out

        # Check that output contains key information
        assert "QUESTION GENERATION PIPELINE" in output
        assert "Generation:" in output
        assert "Evaluation:" in output
        assert "Requested: 10" in output
        assert "Generated: 1" in output


class TestGlobalMetricsTracker:
    """Tests for global metrics tracker functions."""

    def test_get_metrics_tracker_creates_instance(self):
        """Test that get_metrics_tracker creates and returns instance."""
        tracker = get_metrics_tracker()

        assert isinstance(tracker, MetricsTracker)

    def test_get_metrics_tracker_returns_same_instance(self):
        """Test that get_metrics_tracker returns same instance."""
        tracker1 = get_metrics_tracker()
        tracker2 = get_metrics_tracker()

        assert tracker1 is tracker2

    def test_reset_metrics(self):
        """Test that reset_metrics resets the global tracker."""
        tracker = get_metrics_tracker()
        tracker.questions_requested = 100

        reset_metrics()

        # Tracker should be reset
        assert tracker.questions_requested == 0


class TestMetricsIntegration:
    """Integration tests for metrics tracking."""

    def test_full_pipeline_metrics(self):
        """Test metrics tracking through a full pipeline simulation."""
        tracker = MetricsTracker()
        tracker.start_run()

        # Simulate generation phase
        tracker.record_generation_request(20)
        for i in range(18):
            tracker.record_generation_success(
                provider="openai" if i % 2 == 0 else "anthropic",
                question_type="pattern_recognition",
                difficulty="easy" if i < 6 else "medium" if i < 12 else "hard",
            )
        for _ in range(2):
            tracker.record_generation_failure("google", "timeout")

        # Simulate evaluation phase
        for i in range(18):
            score = 0.75 + (i % 3) * 0.1  # Scores: 0.75, 0.85, 0.95
            approved = score >= 0.7
            tracker.record_evaluation_success(
                score=score,
                approved=approved,
                judge_model="openai/gpt-4",
            )

        # Simulate deduplication phase
        for i in range(18):
            is_dup = i < 3  # First 3 are duplicates
            dup_type = "exact" if i < 2 else "semantic" if i < 3 else None
            tracker.record_duplicate_check(
                is_duplicate=is_dup,
                duplicate_type=dup_type,
            )

        # Simulate database insertion
        tracker.record_insertion_success(15)  # 18 - 3 duplicates = 15

        tracker.end_run()

        # Get summary
        summary = tracker.get_summary()

        # Verify metrics
        assert summary["generation"]["requested"] == 20
        assert summary["generation"]["generated"] == 18
        assert summary["generation"]["failed"] == 2
        assert summary["generation"]["success_rate"] == pytest.approx(0.9)

        assert summary["evaluation"]["evaluated"] == 18
        assert summary["evaluation"]["approved"] == 18
        assert summary["evaluation"]["approval_rate"] == pytest.approx(1.0)

        assert summary["deduplication"]["checked"] == 18
        assert summary["deduplication"]["duplicates_found"] == 3
        assert summary["deduplication"]["exact_duplicates"] == 2
        assert summary["deduplication"]["semantic_duplicates"] == 1

        assert summary["database"]["inserted"] == 15
        assert summary["database"]["success_rate"] == pytest.approx(1.0)

        assert summary["overall"]["questions_requested"] == 20
        assert summary["overall"]["questions_final_output"] == 15
        assert summary["overall"]["overall_success_rate"] == pytest.approx(0.75)


class TestStageTimingMetrics:
    """Tests for per-stage timing metrics (TASK-472)."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh metrics tracker for each test."""
        tracker = MetricsTracker()
        tracker.reset()
        return tracker

    def test_start_and_end_stage(self, tracker):
        """Test basic stage timing start/end."""
        tracker.start_stage("generation")
        import time

        time.sleep(0.05)  # Sleep for 50ms
        duration = tracker.end_stage()

        assert duration >= 0.05
        assert tracker._stage_durations["generation"] >= 0.05

    def test_end_stage_with_explicit_name(self, tracker):
        """Test ending a stage with explicit name."""
        tracker.start_stage("evaluation")
        import time

        time.sleep(0.02)
        duration = tracker.end_stage("evaluation")

        assert duration >= 0.02

    def test_end_stage_without_start(self, tracker):
        """Test ending a stage that wasn't started."""
        duration = tracker.end_stage("generation")
        assert duration == pytest.approx(0.0)

    def test_time_stage_context_manager(self, tracker):
        """Test the time_stage context manager."""
        import time

        with tracker.time_stage("deduplication"):
            time.sleep(0.03)

        durations = tracker.get_stage_durations()
        assert durations["deduplication"] >= 0.03

    def test_time_stage_context_manager_with_exception(self, tracker):
        """Test that time_stage records duration even if exception occurs."""
        import time

        try:
            with tracker.time_stage("storage"):
                time.sleep(0.02)
                raise ValueError("Test error")
        except ValueError:
            pass

        durations = tracker.get_stage_durations()
        assert durations["storage"] >= 0.02

    def test_get_stage_durations(self, tracker):
        """Test getting all stage durations."""
        tracker._stage_durations = {
            "generation": 5.123,
            "evaluation": 3.456,
            "deduplication": 1.234,
            "storage": 0.567,
        }

        durations = tracker.get_stage_durations()

        assert durations["generation"] == pytest.approx(5.123)
        assert durations["evaluation"] == pytest.approx(3.456)
        assert durations["deduplication"] == pytest.approx(1.234)
        assert durations["storage"] == pytest.approx(0.567)

    def test_stage_durations_accumulate(self, tracker):
        """Test that multiple starts/ends accumulate duration."""
        import time

        # First generation stage
        with tracker.time_stage("generation"):
            time.sleep(0.02)

        # Second generation stage
        with tracker.time_stage("generation"):
            time.sleep(0.02)

        durations = tracker.get_stage_durations()
        assert durations["generation"] >= 0.04

    def test_unknown_stage_warning(self, tracker, caplog):
        """Test that unknown stage logs warning."""
        import logging

        with caplog.at_level(logging.WARNING):
            tracker.start_stage("unknown_stage")

        assert "Unknown stage: unknown_stage" in caplog.text

    def test_stage_durations_in_summary(self, tracker):
        """Test that stage durations appear in summary."""
        tracker._stage_durations["generation"] = 5.0
        tracker._stage_durations["evaluation"] = 3.0

        summary = tracker.get_summary()

        assert "stage_durations" in summary
        assert summary["stage_durations"]["generation"] == pytest.approx(5.0)
        assert summary["stage_durations"]["evaluation"] == pytest.approx(3.0)

    def test_reset_clears_stage_durations(self, tracker):
        """Test that reset clears stage durations."""
        tracker._stage_durations["generation"] = 5.0

        tracker.reset()

        assert tracker._stage_durations["generation"] == pytest.approx(0.0)
        assert tracker._stage_durations["evaluation"] == pytest.approx(0.0)


class TestEmbeddingCacheMetrics:
    """Tests for embedding cache performance metrics (TASK-472)."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh metrics tracker for each test."""
        tracker = MetricsTracker()
        tracker.reset()
        return tracker

    def test_record_embedding_cache_stats(self, tracker):
        """Test recording embedding cache stats."""
        tracker.record_embedding_cache_stats(hits=100, misses=20, size=50)

        stats = tracker.get_embedding_cache_stats()

        assert stats["hits"] == 100
        assert stats["misses"] == 20
        assert stats["size"] == 50
        assert stats["hit_rate"] == pytest.approx(100 / 120, rel=0.01)

    def test_embedding_cache_hit_rate_calculation(self, tracker):
        """Test hit rate calculation with various values."""
        # 75% hit rate
        tracker.record_embedding_cache_stats(hits=75, misses=25, size=100)
        stats = tracker.get_embedding_cache_stats()
        assert stats["hit_rate"] == pytest.approx(0.75)

    def test_embedding_cache_hit_rate_zero_when_no_requests(self, tracker):
        """Test hit rate is 0 when no requests made."""
        tracker.record_embedding_cache_stats(hits=0, misses=0, size=0)
        stats = tracker.get_embedding_cache_stats()
        assert stats["hit_rate"] == pytest.approx(0.0)

    def test_embedding_cache_stats_in_summary(self, tracker):
        """Test that embedding cache stats appear in summary."""
        tracker.record_embedding_cache_stats(hits=50, misses=10, size=30)

        summary = tracker.get_summary()

        assert "embedding_cache" in summary
        assert summary["embedding_cache"]["hits"] == 50
        assert summary["embedding_cache"]["misses"] == 10
        assert summary["embedding_cache"]["size"] == 30
        assert summary["embedding_cache"]["hit_rate"] == pytest.approx(
            50 / 60, rel=0.01
        )

    def test_reset_clears_embedding_cache_stats(self, tracker):
        """Test that reset clears embedding cache stats."""
        tracker.record_embedding_cache_stats(hits=100, misses=50, size=75)

        tracker.reset()

        stats = tracker.get_embedding_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["size"] == 0

    def test_print_summary_includes_embedding_cache(self, tracker, capsys):
        """Test that print_summary includes embedding cache stats."""
        tracker.record_embedding_cache_stats(hits=80, misses=20, size=50)

        tracker.print_summary()

        captured = capsys.readouterr()
        assert "Embedding Cache:" in captured.out
        assert "Hits:     80" in captured.out
        assert "Misses:   20" in captured.out

    def test_print_summary_includes_stage_durations(self, tracker, capsys):
        """Test that print_summary includes stage durations."""
        tracker._stage_durations["generation"] = 5.123

        tracker.print_summary()

        captured = capsys.readouterr()
        assert "Stage Durations:" in captured.out
        assert "Generation: 5.123s" in captured.out
