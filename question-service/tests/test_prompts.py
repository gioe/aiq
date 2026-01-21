"""Tests for prompt generation."""

from app.models import DifficultyLevel, QuestionType
from app.prompts import (
    build_generation_prompt,
    build_arbiter_prompt,
    QUESTION_TYPE_PROMPTS,
    DIFFICULTY_INSTRUCTIONS,
)


class TestBuildGenerationPrompt:
    """Tests for build_generation_prompt function."""

    def test_build_single_question_prompt(self):
        """Test building a prompt for a single question."""
        prompt = build_generation_prompt(
            question_type=QuestionType.MATH,
            difficulty=DifficultyLevel.EASY,
            count=1,
        )

        assert "mathematical" in prompt.lower()
        assert "easy" in prompt.lower()
        assert "Generate 1 unique" in prompt
        assert "psychometrician" in prompt.lower()
        assert "JSON" in prompt

    def test_build_multiple_questions_prompt(self):
        """Test building a prompt for multiple questions."""
        prompt = build_generation_prompt(
            question_type=QuestionType.LOGIC,
            difficulty=DifficultyLevel.HARD,
            count=5,
        )

        assert "logic" in prompt.lower()
        assert "hard" in prompt.lower()
        assert "Generate 5 unique" in prompt
        assert "array of question objects" in prompt.lower()

    def test_prompt_contains_type_specific_instructions(self):
        """Test that prompt contains type-specific instructions."""
        for question_type in QuestionType:
            prompt = build_generation_prompt(
                question_type=question_type,
                difficulty=DifficultyLevel.MEDIUM,
                count=1,
            )

            # Should contain the type-specific prompt
            assert question_type.value in prompt.lower()

    def test_prompt_contains_difficulty_instructions(self):
        """Test that prompt contains difficulty-specific instructions."""
        for difficulty in DifficultyLevel:
            prompt = build_generation_prompt(
                question_type=QuestionType.MATH,
                difficulty=difficulty,
                count=1,
            )

            # Should contain the difficulty level
            assert difficulty.value in prompt.lower()

    def test_all_question_types_have_prompts(self):
        """Test that all question types have prompt templates."""
        for question_type in QuestionType:
            assert question_type in QUESTION_TYPE_PROMPTS
            assert len(QUESTION_TYPE_PROMPTS[question_type]) > 0

    def test_all_difficulties_have_instructions(self):
        """Test that all difficulty levels have instructions."""
        for difficulty in DifficultyLevel:
            assert difficulty in DIFFICULTY_INSTRUCTIONS
            assert len(DIFFICULTY_INSTRUCTIONS[difficulty]) > 0


class TestBuildArbiterPrompt:
    """Tests for build_arbiter_prompt function."""

    def test_build_arbiter_prompt(self):
        """Test building an arbiter evaluation prompt."""
        prompt = build_arbiter_prompt(
            question="What is 2 + 2?",
            answer_options=["2", "3", "4", "5"],
            correct_answer="4",
            question_type="mathematical",
            difficulty="easy",
        )

        assert "What is 2 + 2?" in prompt
        assert "4" in prompt
        assert "mathematical" in prompt
        assert "easy" in prompt
        assert "clarity" in prompt.lower()
        assert "validity" in prompt.lower()
        assert "JSON" in prompt

    def test_arbiter_prompt_includes_all_options(self):
        """Test that arbiter prompt includes all answer options."""
        options = ["Option A", "Option B", "Option C", "Option D"]
        prompt = build_arbiter_prompt(
            question="Test question?",
            answer_options=options,
            correct_answer="Option C",
            question_type="logical_reasoning",
            difficulty="medium",
        )

        for option in options:
            assert option in prompt

    def test_arbiter_prompt_includes_evaluation_criteria(self):
        """Test that arbiter prompt includes all evaluation criteria."""
        prompt = build_arbiter_prompt(
            question="Test question?",
            answer_options=["A", "B", "C", "D"],
            correct_answer="A",
            question_type="verbal_reasoning",
            difficulty="hard",
        )

        criteria = ["clarity", "difficulty", "validity", "formatting", "creativity"]
        for criterion in criteria:
            assert criterion.lower() in prompt.lower()

    def test_arbiter_prompt_specifies_score_range(self):
        """Test that arbiter prompt specifies valid score range."""
        prompt = build_arbiter_prompt(
            question="Test question?",
            answer_options=["A", "B"],
            correct_answer="A",
            question_type="pattern_recognition",
            difficulty="easy",
        )

        assert "0.0-1.0" in prompt or "0.0 to 1.0" in prompt
