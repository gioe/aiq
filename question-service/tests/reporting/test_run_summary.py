"""Tests for RunSummary dataclass."""

import pytest
from datetime import datetime, timezone

from app.reporting.run_summary import RunSummary


class TestRunSummaryInit:
    """Tests for RunSummary initialization."""

    def test_default_values(self):
        summary = RunSummary()
        assert summary.questions_requested == 0
        assert summary.questions_generated == 0
        assert summary.generation_failures == 0
        assert summary.questions_by_provider == {}
        assert summary.questions_by_type == {}
        assert summary.questions_by_difficulty == {}
        assert summary.questions_evaluated == 0
        assert summary.questions_approved == 0
        assert summary.questions_rejected == 0
        assert summary.evaluation_scores == []
        assert summary.duplicates_found == 0
        assert summary.questions_inserted == 0
        assert summary.insertion_failures == 0
        assert summary.start_time is None
        assert summary.end_time is None


class TestRunSummaryTiming:
    """Tests for start/end run timing."""

    def test_start_run_sets_time(self):
        summary = RunSummary()
        summary.start_run()
        assert summary.start_time is not None
        assert summary.start_time.tzinfo == timezone.utc

    def test_end_run_sets_time(self):
        summary = RunSummary()
        summary.end_run()
        assert summary.end_time is not None
        assert summary.end_time.tzinfo == timezone.utc

    def test_duration_seconds(self):
        summary = RunSummary()
        summary.start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        summary.end_time = datetime(2024, 1, 1, 0, 1, 30, tzinfo=timezone.utc)
        assert summary._duration_seconds() == pytest.approx(90.0)

    def test_duration_seconds_no_times(self):
        summary = RunSummary()
        assert summary._duration_seconds() == pytest.approx(0.0)


class TestRecordGeneration:
    """Tests for generation recording."""

    def test_record_generation_success(self):
        summary = RunSummary()
        summary.record_generation_success("openai", "pattern_recognition", "medium")
        assert summary.questions_generated == 1
        assert summary.questions_by_provider == {"openai": 1}
        assert summary.questions_by_type == {"pattern_recognition": 1}
        assert summary.questions_by_difficulty == {"medium": 1}
        assert summary.total_api_calls == 1
        assert summary.api_calls_by_provider == {"openai": 1}

    def test_record_multiple_generations(self):
        summary = RunSummary()
        summary.record_generation_success("openai", "math", "easy")
        summary.record_generation_success("openai", "math", "hard")
        summary.record_generation_success("anthropic", "verbal", "easy")
        assert summary.questions_generated == 3
        assert summary.questions_by_provider == {"openai": 2, "anthropic": 1}
        assert summary.questions_by_type == {"math": 2, "verbal": 1}
        assert summary.questions_by_difficulty == {"easy": 2, "hard": 1}


class TestRecordEvaluation:
    """Tests for evaluation recording."""

    def test_record_evaluation_approved(self):
        summary = RunSummary()
        summary.record_evaluation_success(0.85, True, "openai/gpt-4")
        assert summary.questions_evaluated == 1
        assert summary.questions_approved == 1
        assert summary.questions_rejected == 0
        assert summary.evaluation_scores == [0.85]
        assert summary.api_calls_by_provider == {"openai": 1}

    def test_record_evaluation_rejected(self):
        summary = RunSummary()
        summary.record_evaluation_success(0.4, False, "anthropic/claude")
        assert summary.questions_evaluated == 1
        assert summary.questions_approved == 0
        assert summary.questions_rejected == 1


class TestRecordDeduplication:
    """Tests for deduplication recording."""

    def test_record_not_duplicate(self):
        summary = RunSummary()
        summary.record_duplicate_check(is_duplicate=False)
        assert summary.questions_checked_for_duplicates == 1
        assert summary.duplicates_found == 0

    def test_record_exact_duplicate(self):
        summary = RunSummary()
        summary.record_duplicate_check(is_duplicate=True, duplicate_type="exact")
        assert summary.duplicates_found == 1
        assert summary.exact_duplicates == 1
        assert summary.semantic_duplicates == 0

    def test_record_semantic_duplicate(self):
        summary = RunSummary()
        summary.record_duplicate_check(is_duplicate=True, duplicate_type="semantic")
        assert summary.duplicates_found == 1
        assert summary.semantic_duplicates == 1
        assert summary.exact_duplicates == 0


class TestRecordInsertion:
    """Tests for insertion recording."""

    def test_record_insertion_success(self):
        summary = RunSummary()
        summary.record_insertion_success(5)
        assert summary.questions_inserted == 5

    def test_record_insertion_failure(self):
        summary = RunSummary()
        summary.record_insertion_failure(2)
        assert summary.insertion_failures == 2


class TestToSummaryDict:
    """Tests for to_summary_dict output shape."""

    def _populated_summary(self) -> RunSummary:
        s = RunSummary()
        s.start_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        s.end_time = datetime(2024, 1, 1, 0, 1, 30, tzinfo=timezone.utc)
        s.questions_requested = 50
        for _ in range(45):
            s.record_generation_success("openai", "pattern_recognition", "medium")
        s.generation_failures = 5
        for i in range(40):
            score = 0.7 + (i % 10) * 0.03
            s.record_evaluation_success(score, score >= 0.75, "openai/gpt-4")
        for _ in range(35):
            s.record_duplicate_check(is_duplicate=False)
        for _ in range(3):
            s.record_duplicate_check(is_duplicate=True, duplicate_type="exact")
        s.record_insertion_success(30)
        s.record_insertion_failure(2)
        return s

    def test_has_all_required_sections(self):
        d = self._populated_summary().to_summary_dict()
        required = [
            "execution",
            "generation",
            "evaluation",
            "deduplication",
            "database",
            "api",
            "error_classification",
            "overall",
            "retry",
            "circuit_breaker",
            "cost",
        ]
        for key in required:
            assert key in d, f"Missing section: {key}"

    def test_execution_section(self):
        d = self._populated_summary().to_summary_dict()
        assert d["execution"]["duration_seconds"] == pytest.approx(90.0)
        assert "2024-01-01" in d["execution"]["start_time"]

    def test_generation_section(self):
        d = self._populated_summary().to_summary_dict()
        gen = d["generation"]
        assert gen["requested"] == 50
        assert gen["generated"] == 45
        assert gen["failed"] == 5
        assert gen["success_rate"] == pytest.approx(0.9)
        assert gen["by_provider"] == {"openai": 45}

    def test_evaluation_section(self):
        d = self._populated_summary().to_summary_dict()
        ev = d["evaluation"]
        assert ev["evaluated"] == 40
        assert ev["approved"] > 0
        assert ev["rejected"] >= 0
        assert ev["average_score"] > 0
        assert ev["min_score"] <= ev["max_score"]

    def test_deduplication_section(self):
        d = self._populated_summary().to_summary_dict()
        dd = d["deduplication"]
        assert dd["checked"] == 38
        assert dd["duplicates_found"] == 3
        assert dd["exact_duplicates"] == 3

    def test_database_section(self):
        d = self._populated_summary().to_summary_dict()
        db = d["database"]
        assert db["inserted"] == 30
        assert db["failed"] == 2
        assert db["success_rate"] == pytest.approx(30 / 32)

    def test_overall_section(self):
        d = self._populated_summary().to_summary_dict()
        ov = d["overall"]
        assert ov["questions_requested"] == 50
        assert ov["questions_final_output"] == 30
        assert ov["total_errors"] == 7  # 5 gen failures + 2 insertion failures

    def test_empty_summary(self):
        """Verify to_summary_dict doesn't crash on an empty summary."""
        d = RunSummary().to_summary_dict()
        assert d["generation"]["success_rate"] == pytest.approx(0.0)
        assert d["evaluation"]["average_score"] == pytest.approx(0.0)
        assert d["deduplication"]["duplicate_rate"] == pytest.approx(0.0)
        assert d["database"]["success_rate"] == pytest.approx(0.0)
        assert d["overall"]["overall_success_rate"] == pytest.approx(0.0)
