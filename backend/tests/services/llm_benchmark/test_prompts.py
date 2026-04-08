"""
Unit tests for LLM benchmark prompt building.

Covers build_prompt for all 6 question types including memory stimulus handling.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from app.services.llm_benchmark.prompts import build_prompt, _SYSTEM_PREAMBLE


def _make_question(
    question_type_value: str,
    question_text: str = "What is 2+2?",
    answer_options: list[str] | None = None,
    stimulus: str | None = None,
):
    """Create a lightweight mock Question for prompt tests."""
    q = MagicMock()
    q.question_text = question_text
    q.answer_options = answer_options
    q.stimulus = stimulus
    q.question_type = MagicMock()
    q.question_type.value = question_type_value
    return q


class TestBuildPromptStandardTypes:
    """Test prompt building for the 5 non-memory question types."""

    def test_pattern_prompt(self):
        q = _make_question("pattern", "Find the pattern")
        prompt = build_prompt(q)
        assert "Pattern Recognition" in prompt
        assert "Find the pattern" in prompt
        assert _SYSTEM_PREAMBLE in prompt

    def test_logic_prompt(self):
        q = _make_question("logic", "If A then B")
        prompt = build_prompt(q)
        assert "Logical Reasoning" in prompt
        assert "If A then B" in prompt

    def test_spatial_prompt(self):
        q = _make_question("spatial", "Rotate the cube")
        prompt = build_prompt(q)
        assert "Spatial Reasoning" in prompt

    def test_math_prompt(self):
        q = _make_question("math", "Solve for x")
        prompt = build_prompt(q)
        assert "Mathematical Reasoning" in prompt

    def test_verbal_prompt(self):
        q = _make_question("verbal", "Choose the synonym")
        prompt = build_prompt(q)
        assert "Verbal Reasoning" in prompt

    def test_includes_multiple_choice_options(self):
        q = _make_question(
            "logic",
            "Pick one",
            answer_options=["Alpha", "Beta", "Gamma"],
        )
        prompt = build_prompt(q)
        assert "1. Alpha" in prompt
        assert "2. Beta" in prompt
        assert "3. Gamma" in prompt
        assert "Options:" in prompt

    def test_no_options_when_none(self):
        q = _make_question("math", "What is pi?", answer_options=None)
        prompt = build_prompt(q)
        assert "Options:" not in prompt


class TestBuildPromptMemory:
    """Test prompt building for memory questions with stimulus."""

    def test_memory_with_stimulus(self):
        q = _make_question(
            "memory",
            "What was the third item?",
            stimulus="Apple, Banana, Cherry, Date",
        )
        prompt = build_prompt(q)
        assert "Working Memory" in prompt
        assert "Study the following information carefully" in prompt
        assert "Apple, Banana, Cherry, Date" in prompt
        assert "What was the third item?" in prompt

    def test_memory_without_stimulus(self):
        q = _make_question("memory", "Recall the sequence", stimulus=None)
        prompt = build_prompt(q)
        assert "Working Memory" in prompt
        assert "Study the following" not in prompt
        assert "Recall the sequence" in prompt

    def test_memory_with_options(self):
        q = _make_question(
            "memory",
            "Which was shown?",
            answer_options=["Red", "Blue", "Green"],
            stimulus="Red, Yellow",
        )
        prompt = build_prompt(q)
        assert "1. Red" in prompt
        assert "2. Blue" in prompt


class TestBuildPromptFallback:
    """Test fallback for unknown question types."""

    def test_unknown_type_uses_generic_prompt(self):
        q = _make_question("unknown_type", "Something weird")
        prompt = build_prompt(q)
        assert _SYSTEM_PREAMBLE in prompt
        assert "Something weird" in prompt
        # Should NOT contain any type label
        assert "QUESTION TYPE:" not in prompt
