"""Tests for question generation models."""

import pytest
from pydantic import ValidationError

from app.models import (
    DifficultyLevel,
    GeneratedQuestion,
    GenerationBatch,
    QuestionType,
    EvaluationScore,
    EvaluatedQuestion,
)


class TestGeneratedQuestion:
    """Tests for GeneratedQuestion model."""

    def test_create_valid_question(self):
        """Test creating a valid question."""
        question = GeneratedQuestion(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            explanation="2 + 2 equals 4 by basic addition.",
            metadata={"tag": "arithmetic"},
            source_llm="openai",
            source_model="gpt-4",
        )

        assert question.question_text == "What is 2 + 2?"
        assert question.question_type == QuestionType.MATH
        assert question.difficulty_level == DifficultyLevel.EASY
        assert question.correct_answer == "4"
        assert len(question.answer_options) == 4
        assert "4" in question.answer_options

    def test_question_text_too_short(self):
        """Test that question text must be at least 10 characters."""
        with pytest.raises(ValidationError):
            GeneratedQuestion(
                question_text="Short",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="4",
                answer_options=["2", "3", "4", "5"],
                source_llm="openai",
                source_model="gpt-4",
            )

    def test_correct_answer_not_in_options(self):
        """Test that correct answer must be in answer_options."""
        with pytest.raises(ValidationError) as exc_info:
            GeneratedQuestion(
                question_text="What is 2 + 2?",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="4",
                answer_options=["2", "3", "5", "6"],  # Missing "4"
                source_llm="openai",
                source_model="gpt-4",
            )
        assert "correct_answer" in str(exc_info.value)

    def test_too_few_answer_options(self):
        """Test that at least 2 answer options are required."""
        with pytest.raises(ValidationError):
            GeneratedQuestion(
                question_text="What is 2 + 2?",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="4",
                answer_options=["4"],  # Only 1 option
                source_llm="openai",
                source_model="gpt-4",
            )

    def test_question_without_options(self):
        """Test creating a question without answer options (open-ended)."""
        question = GeneratedQuestion(
            question_text="What is the capital of France?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="Paris",
            answer_options=None,
            source_llm="anthropic",
            source_model="claude-3-5-sonnet",
        )

        assert question.answer_options is None
        assert question.correct_answer == "Paris"

    def test_to_dict(self):
        """Test converting question to dictionary."""
        question = GeneratedQuestion(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            explanation="Basic addition",
            metadata={"tag": "test"},
            source_llm="openai",
            source_model="gpt-4",
        )

        result = question.to_dict()

        assert result["question_text"] == "What is 2 + 2?"
        assert result["question_type"] == "math"
        assert result["difficulty_level"] == "easy"
        assert result["correct_answer"] == "4"
        assert len(result["answer_options"]) == 4


class TestEvaluationScore:
    """Tests for EvaluationScore model."""

    def test_create_valid_score(self):
        """Test creating a valid evaluation score."""
        score = EvaluationScore(
            clarity_score=0.9,
            difficulty_score=0.8,
            validity_score=0.85,
            formatting_score=0.95,
            creativity_score=0.7,
            overall_score=0.84,
            feedback="Good question overall",
        )

        assert score.clarity_score == 0.9
        assert score.overall_score == 0.84
        assert score.feedback == "Good question overall"

    def test_score_bounds(self):
        """Test that scores must be between 0.0 and 1.0."""
        # Test upper bound
        with pytest.raises(ValidationError):
            EvaluationScore(
                clarity_score=1.5,  # Too high
                difficulty_score=0.8,
                validity_score=0.85,
                formatting_score=0.95,
                creativity_score=0.7,
                overall_score=0.84,
            )

        # Test lower bound
        with pytest.raises(ValidationError):
            EvaluationScore(
                clarity_score=-0.1,  # Too low
                difficulty_score=0.8,
                validity_score=0.85,
                formatting_score=0.95,
                creativity_score=0.7,
                overall_score=0.84,
            )


class TestEvaluatedQuestion:
    """Tests for EvaluatedQuestion model."""

    def test_create_evaluated_question(self):
        """Test creating an evaluated question."""
        question = GeneratedQuestion(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            source_llm="openai",
            source_model="gpt-4",
        )

        score = EvaluationScore(
            clarity_score=0.9,
            difficulty_score=0.8,
            validity_score=0.85,
            formatting_score=0.95,
            creativity_score=0.7,
            overall_score=0.84,
        )

        evaluated = EvaluatedQuestion(
            question=question,
            evaluation=score,
            judge_model="gpt-4-turbo",
            approved=True,
        )

        assert evaluated.is_approved is True
        assert evaluated.judge_model == "gpt-4-turbo"
        assert evaluated.question.question_text == "What is 2 + 2?"


class TestGenerationBatch:
    """Tests for GenerationBatch model."""

    def test_create_batch(self):
        """Test creating a generation batch."""
        questions = [
            GeneratedQuestion(
                question_text=f"Question {i}?",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer=str(i),
                answer_options=[str(i), str(i + 1), str(i + 2)],
                source_llm="openai",
                source_model="gpt-4",
            )
            for i in range(5)
        ]

        batch = GenerationBatch(
            questions=questions,
            question_type=QuestionType.MATH,
            batch_size=5,
            generation_timestamp="2024-01-01T00:00:00",
            metadata={"test": True},
        )

        assert len(batch) == 5
        assert batch.batch_size == 5
        assert batch.question_type == QuestionType.MATH
        assert len(batch.questions) == 5

    def test_empty_batch(self):
        """Test creating an empty batch."""
        batch = GenerationBatch(
            questions=[],
            question_type=QuestionType.LOGIC,
            batch_size=0,
            generation_timestamp="2024-01-01T00:00:00",
        )

        assert len(batch) == 0
        assert batch.batch_size == 0


class TestQuestionTypeEnumConsistency:
    """Tests to ensure QuestionType enum values match backend exactly.

    These values must stay synchronized with backend/app/models/models.py
    to eliminate mapping code and ensure data consistency.
    """

    def test_question_type_values_match_backend(self):
        """Verify QuestionType enum values exactly match backend enum values.

        Backend enum (backend/app/models/models.py) defines:
            PATTERN = "pattern"
            LOGIC = "logic"
            SPATIAL = "spatial"
            MATH = "math"
            VERBAL = "verbal"
            MEMORY = "memory"
        """
        expected_values = {
            "PATTERN": "pattern",
            "LOGIC": "logic",
            "SPATIAL": "spatial",
            "MATH": "math",
            "VERBAL": "verbal",
            "MEMORY": "memory",
        }

        # Verify all expected values exist
        for name, value in expected_values.items():
            assert hasattr(QuestionType, name), f"Missing enum: {name}"
            assert getattr(QuestionType, name).value == value, (
                f"Value mismatch for {name}: expected '{value}', "
                f"got '{getattr(QuestionType, name).value}'"
            )

        # Verify no extra enum values exist
        actual_names = {e.name for e in QuestionType}
        expected_names = set(expected_values.keys())
        assert actual_names == expected_names, (
            f"Enum members mismatch. Extra: {actual_names - expected_names}, "
            f"Missing: {expected_names - actual_names}"
        )

    def test_question_type_count(self):
        """Verify the exact number of question types."""
        assert len(QuestionType) == 6, (
            f"Expected 6 question types, got {len(QuestionType)}. "
            "If adding/removing types, update both question-service and backend."
        )
