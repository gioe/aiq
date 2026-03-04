"""Tests for the answer leakage auditor."""

from unittest.mock import MagicMock

import pytest

from app.data.answer_leakage_auditor import (
    MIN_ACTIVE_PER_BUCKET,
    MIN_ANSWER_LENGTH_FOR_LEAKAGE_CHECK,
    run_answer_leakage_audit,
)


def _make_question(
    question_text: str,
    correct_answer: str,
    question_type: str = "logic",
    difficulty_level: str = "easy",
    is_active: bool = True,
    q_id: int = 1,
) -> MagicMock:
    q = MagicMock()
    q.id = q_id
    q.question_text = question_text
    q.correct_answer = correct_answer
    q.question_type = question_type
    q.difficulty_level = difficulty_level
    q.is_active = is_active
    return q


def _build_factory(active_questions: list) -> tuple:
    """Return (session_factory, session_mock) with stubbed query results."""
    session = MagicMock()
    query_mock = session.query.return_value
    filter_mock = query_mock.filter.return_value
    filter_mock.all.return_value = active_questions
    factory = MagicMock(return_value=session)
    return factory, session


class TestRunAnswerLeakageAudit:
    def test_clean_pool_returns_zero_leaking(self):
        q = _make_question(
            question_text="Which shape has three sides?",
            correct_answer="triangle",
        )
        factory, session = _build_factory([q])
        result = run_answer_leakage_audit(factory)
        assert result["leaking_count"] == 0
        assert result["deactivated_count"] == 0
        session.commit.assert_not_called()

    def test_leaking_question_is_deactivated(self):
        q = _make_question(
            question_text="The answer is Berlin. What is the capital of Germany?",
            correct_answer="Berlin",
        )
        factory, session = _build_factory([q])
        result = run_answer_leakage_audit(factory)
        assert result["leaking_count"] == 1
        assert result["deactivated_count"] == 1
        session.commit.assert_called_once()

    def test_dry_run_does_not_commit(self):
        q = _make_question(
            question_text="The answer is Paris. What is the capital of France?",
            correct_answer="Paris",
        )
        factory, session = _build_factory([q])
        result = run_answer_leakage_audit(factory, dry_run=True)
        assert result["leaking_count"] == 1
        assert result["deactivated_count"] == 0
        session.commit.assert_not_called()

    def test_short_answer_not_flagged(self):
        """Answers shorter than MIN_ANSWER_LENGTH_FOR_LEAKAGE_CHECK must not trigger."""
        short = "A" * (MIN_ANSWER_LENGTH_FOR_LEAKAGE_CHECK - 1)
        q = _make_question(
            question_text=f"Which option is correct? Option {short} is often chosen.",
            correct_answer=short,
        )
        factory, _ = _build_factory([q])
        result = run_answer_leakage_audit(factory)
        assert result["leaking_count"] == 0

    def test_answer_at_min_length_is_checked(self):
        """Answers exactly at the threshold should be subject to the check."""
        answer = "B" * MIN_ANSWER_LENGTH_FOR_LEAKAGE_CHECK
        q = _make_question(
            question_text=f"The correct answer is {answer}. Pick it.",
            correct_answer=answer,
        )
        factory, _ = _build_factory([q])
        result = run_answer_leakage_audit(factory)
        assert result["leaking_count"] == 1

    def test_case_insensitive_match(self):
        q = _make_question(
            question_text="The answer is LONDON. What is the capital of England?",
            correct_answer="london",
        )
        factory, _ = _build_factory([q])
        result = run_answer_leakage_audit(factory)
        assert result["leaking_count"] == 1

    def test_low_bucket_reported(self):
        """A bucket with fewer than MIN_ACTIVE_PER_BUCKET questions appears in low_buckets."""
        questions = [
            _make_question(
                question_text=f"Question {i} about geometry",
                correct_answer=f"answer{i}",
                question_type="logic",
                difficulty_level="easy",
                q_id=i,
            )
            for i in range(MIN_ACTIVE_PER_BUCKET - 1)
        ]
        factory, _ = _build_factory(questions)
        result = run_answer_leakage_audit(factory)
        assert any("logic" in b and "easy" in b for b in result["low_buckets"])

    def test_full_bucket_not_reported(self):
        """A bucket at or above the threshold should NOT appear in low_buckets."""
        questions = [
            _make_question(
                question_text=f"Question {i} about math",
                correct_answer=f"answer{i}",
                question_type="math",
                difficulty_level="hard",
                q_id=i,
            )
            for i in range(MIN_ACTIVE_PER_BUCKET)
        ]
        factory, _ = _build_factory(questions)
        result = run_answer_leakage_audit(factory)
        assert not any("math" in b and "hard" in b for b in result["low_buckets"])

    def test_session_closed_on_success(self):
        factory, session = _build_factory([])
        run_answer_leakage_audit(factory)
        session.close.assert_called_once()

    def test_session_rolled_back_on_error(self):
        session = MagicMock()
        session.query.side_effect = RuntimeError("db error")
        factory = MagicMock(return_value=session)
        with pytest.raises(RuntimeError):
            run_answer_leakage_audit(factory)
        session.rollback.assert_called_once()
        session.close.assert_called_once()
