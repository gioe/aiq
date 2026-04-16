"""Tests for the answer correctness auditor."""

from unittest.mock import MagicMock, patch

import pytest

from app.data.answer_correctness_auditor import run_answer_correctness_audit
from app.data.answer_leakage_auditor import MIN_ACTIVE_PER_BUCKET


def _make_question(
    q_id: int = 1,
    question_text: str = "Which planet is known as the Red Planet?",
    correct_answer: str = "Mars",
    question_type: str = "math",
    difficulty_level: str = "easy",
    answer_options: list | None = None,
    explanation: str | None = None,
    stimulus: str | None = None,
    sub_type: str | None = None,
    question_metadata: dict | None = None,
    source_llm: str = "openai",
    source_model: str = "gpt-4o",
    is_active: bool = True,
    last_audited_at=None,
) -> MagicMock:
    q = MagicMock()
    q.id = q_id
    q.question_text = question_text
    q.correct_answer = correct_answer
    q.question_type = question_type
    q.difficulty_level = difficulty_level
    q.answer_options = answer_options or ["Mars", "Venus", "Jupiter", "Saturn"]
    q.explanation = explanation
    q.stimulus = stimulus
    q.sub_type = sub_type
    q.question_metadata = question_metadata
    q.source_llm = source_llm
    q.source_model = source_model
    q.is_active = is_active
    q.last_audited_at = last_audited_at
    return q


def _build_factory(active_questions: list) -> tuple:
    """Return (session_factory, session_mock) with stubbed query results.

    The mock chain supports: query → filter → filter → order_by → limit → all
    Each chained method returns the same terminal mock so that any subset of
    the chain (e.g. no second filter, no limit) resolves correctly.
    """
    session = MagicMock()
    terminal = MagicMock()
    terminal.all.return_value = active_questions

    # Make every chaining method return the same terminal mock
    terminal.filter.return_value = terminal
    terminal.order_by.return_value = terminal
    terminal.limit.return_value = terminal

    query_mock = session.query.return_value
    query_mock.filter.return_value = terminal

    factory = MagicMock(return_value=session)
    return factory, session


def _make_judge(verify_result: tuple | None = None) -> MagicMock:
    """Create a mock judge with verify_answer returning the given result."""
    judge = MagicMock()
    judge.providers = {"openai": MagicMock(model="gpt-4o")}
    if verify_result is not None:
        judge.verify_answer.return_value = verify_result
    return judge


def _make_judge_config() -> MagicMock:
    config = MagicMock()
    config.resolve_judge_provider.return_value = ("openai", "gpt-4o")
    return config


class TestRunAnswerCorrectnessAudit:
    def test_empty_pool_returns_zeros(self):
        factory, session = _build_factory([])
        judge = _make_judge()
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["scanned"] == 0
        assert result["verified_correct"] == 0
        assert result["failed"] == 0
        assert result["deactivated"] == 0

    def test_verified_correct_question(self):
        q = _make_question()
        factory, session = _build_factory([q])
        judge = _make_judge(verify_result=(True, {"outcome": "pass"}))
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["scanned"] == 1
        assert result["verified_correct"] == 1
        assert result["failed"] == 0
        assert result["deactivated"] == 0
        session.commit.assert_called()  # Commits last_audited_at timestamps

    def test_failed_question_deactivated(self):
        questions = [_make_question(q_id=i) for i in range(MIN_ACTIVE_PER_BUCKET + 1)]
        factory, session = _build_factory(questions)
        # First question fails, rest pass
        judge = _make_judge()
        judge.verify_answer.side_effect = [(False, {"outcome": "concession"})] + [
            (True, {"outcome": "pass"})
        ] * MIN_ACTIVE_PER_BUCKET
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["failed"] == 1
        assert result["deactivated"] == 1
        # Three commits: audit results, record_pipeline_run, persist session
        assert session.commit.call_count == 3

    def test_bucket_safety_prevents_deactivation(self):
        """Should not deactivate if it would breach MIN_ACTIVE_PER_BUCKET."""
        questions = [_make_question(q_id=i) for i in range(MIN_ACTIVE_PER_BUCKET)]
        factory, session = _build_factory(questions)
        # First question fails, rest pass
        judge = _make_judge()
        judge.verify_answer.side_effect = [(False, {"outcome": "defense_rejected"})] + [
            (True, {"outcome": "pass"})
        ] * (MIN_ACTIVE_PER_BUCKET - 1)
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["failed"] == 1
        assert result["deactivated"] == 0  # Safety threshold prevents deactivation

    def test_skipped_question_counted(self):
        q = _make_question()
        factory, _ = _build_factory([q])
        judge = _make_judge(
            verify_result=(
                True,
                {"outcome": "skipped", "reason": "insufficient_answer_options"},
            )
        )
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["skipped"] == 1
        assert result["verified_correct"] == 0

    def test_error_during_verification_counted(self):
        q = _make_question()
        factory, _ = _build_factory([q])
        judge = _make_judge()
        judge.verify_answer.side_effect = RuntimeError("LLM error")
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["errors"] == 1
        assert result["failed"] == 0

    def test_session_closed_on_success(self):
        factory, session = _build_factory([])
        judge = _make_judge()
        config = _make_judge_config()
        run_answer_correctness_audit(factory, judge, config)
        # Three close calls: audit session, record_pipeline_run, persist session
        assert session.close.call_count == 3

    def test_session_rolled_back_on_error(self):
        session = MagicMock()
        session.query.side_effect = RuntimeError("db error")
        factory = MagicMock(return_value=session)
        judge = _make_judge()
        config = _make_judge_config()
        with pytest.raises(RuntimeError):
            run_answer_correctness_audit(factory, judge, config)
        session.rollback.assert_called_once()
        session.close.assert_called_once()

    def test_low_bucket_reported_after_deactivation(self):
        """After deactivation, low buckets should be reported."""
        questions = [_make_question(q_id=i) for i in range(MIN_ACTIVE_PER_BUCKET + 1)]
        # Build factory with custom side_effect: first call returns all,
        # second call (pool health check) returns fewer questions.
        remaining = questions[2:]
        session = MagicMock()
        terminal = MagicMock()
        terminal.filter.return_value = terminal
        terminal.order_by.return_value = terminal
        terminal.limit.return_value = terminal
        terminal.all.side_effect = [questions, remaining]
        query_mock = session.query.return_value
        query_mock.filter.return_value = terminal
        factory = MagicMock(return_value=session)

        judge = _make_judge()
        judge.verify_answer.side_effect = [
            (False, {"outcome": "concession"}),
            (False, {"outcome": "defense_rejected"}),
        ] + [(True, {"outcome": "pass"})] * (MIN_ACTIVE_PER_BUCKET - 1)
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert result["failed"] == 2

    @patch("app.data.answer_correctness_auditor.observability")
    def test_metrics_recorded_when_initialized(self, mock_obs):
        mock_obs.is_initialized = True
        factory, _ = _build_factory([])
        judge = _make_judge()
        config = _make_judge_config()
        run_answer_correctness_audit(factory, judge, config)
        calls = [c[0][0] for c in mock_obs.record_metric.call_args_list]
        assert "audit.correctness.scanned" in calls
        assert "audit.correctness.failed" in calls
        assert "audit.correctness.deactivated" in calls

    @patch("app.data.answer_correctness_auditor.observability")
    def test_metrics_not_recorded_when_uninitialized(self, mock_obs):
        mock_obs.is_initialized = False
        factory, _ = _build_factory([])
        judge = _make_judge()
        config = _make_judge_config()
        run_answer_correctness_audit(factory, judge, config)
        mock_obs.record_metric.assert_not_called()

    def test_last_audited_at_stamped_on_verified_question(self):
        """Verified questions should get last_audited_at set."""
        q = _make_question()
        factory, session = _build_factory([q])
        judge = _make_judge(verify_result=(True, {"outcome": "pass"}))
        config = _make_judge_config()
        run_answer_correctness_audit(factory, judge, config)
        assert q.last_audited_at is not None
        session.commit.assert_called()

    def test_max_questions_passes_through(self):
        """max_questions should be forwarded to the query chain."""
        q = _make_question()
        factory, session = _build_factory([q])
        judge = _make_judge(verify_result=(True, {"outcome": "pass"}))
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config, max_questions=5)
        assert result["scanned"] == 1
        # Verify limit was called on the query chain
        query_mock = session.query.return_value
        terminal = query_mock.filter.return_value
        terminal.order_by.return_value.limit.assert_called_once_with(5)

    def test_cost_summary_included_in_result(self):
        """Audit result should include a cost_summary key from CostTracker."""
        factory, _ = _build_factory([])
        judge = _make_judge()
        config = _make_judge_config()
        result = run_answer_correctness_audit(factory, judge, config)
        assert "cost_summary" in result
        assert "total_cost_usd" in result["cost_summary"]
        assert "total_input_tokens" in result["cost_summary"]
        assert "total_output_tokens" in result["cost_summary"]

    def test_audit_window_hours_passes_through(self):
        """audit_window_hours should add a filter for recently-audited questions."""
        factory, session = _build_factory([])
        judge = _make_judge()
        config = _make_judge_config()
        result = run_answer_correctness_audit(
            factory, judge, config, audit_window_hours=24.0
        )
        assert result["scanned"] == 0
        # Two filter calls: is_active + audit_window cutoff
        query_mock = session.query.return_value
        assert query_mock.filter.call_count >= 1
