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

    def test_memory_question_with_stimulus(self):
        """Test creating a memory question with stimulus content."""
        question = GeneratedQuestion(
            question_text="What was the third word in the sequence?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="apple",
            answer_options=["orange", "banana", "apple", "grape"],
            stimulus="Remember this sequence: dog, cat, apple, house, tree",
            source_llm="openai",
            source_model="gpt-4",
        )

        assert (
            question.stimulus == "Remember this sequence: dog, cat, apple, house, tree"
        )
        assert question.question_type == QuestionType.MEMORY
        assert question.correct_answer == "apple"

    def test_question_without_stimulus(self):
        """Test that stimulus is optional and defaults to None."""
        question = GeneratedQuestion(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            source_llm="openai",
            source_model="gpt-4",
        )

        assert question.stimulus is None

    def test_sub_type_defaults_to_none(self):
        """Test that sub_type defaults to None."""
        question = GeneratedQuestion(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            source_llm="openai",
            source_model="gpt-4",
        )
        assert question.sub_type is None

    def test_sub_type_can_be_set(self):
        """Test that sub_type can be set on a question."""
        question = GeneratedQuestion(
            question_text="Which shape results from rotating the cube 90 degrees?",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options=["A", "B", "C", "D"],
            sub_type="cube rotations and transformations",
            source_llm="openai",
            source_model="gpt-4",
        )
        assert question.sub_type == "cube rotations and transformations"

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
        assert result["stimulus"] is None
        assert result["sub_type"] is None

    def test_to_dict_with_stimulus(self):
        """Test that to_dict includes stimulus field when present."""
        question = GeneratedQuestion(
            question_text="What was the second item in the list?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="banana",
            answer_options=["apple", "banana", "cherry", "date"],
            stimulus="Memorize: apple, banana, cherry",
            source_llm="anthropic",
            source_model="claude-3-5-sonnet",
        )

        result = question.to_dict()

        assert result["stimulus"] == "Memorize: apple, banana, cherry"
        assert result["question_type"] == "memory"

    def test_to_dict_with_sub_type(self):
        """Test that to_dict includes sub_type field when present."""
        question = GeneratedQuestion(
            question_text="Which shape results from rotating the cube 90 degrees?",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options=["A", "B", "C", "D"],
            sub_type="cube rotations and transformations",
            source_llm="openai",
            source_model="gpt-4",
        )

        result = question.to_dict()
        assert result["sub_type"] == "cube rotations and transformations"

    def test_stimulus_with_empty_string(self):
        """Test that stimulus can be an empty string."""
        question = GeneratedQuestion(
            question_text="What comes next in the pattern?",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="D",
            answer_options=["A", "B", "C", "D"],
            stimulus="",
            source_llm="openai",
            source_model="gpt-4",
        )

        assert question.stimulus == ""
        result = question.to_dict()
        assert result["stimulus"] == ""

    def test_stimulus_with_non_memory_question_type(self):
        """Test that stimulus can be used with any question type, not just memory."""
        # Stimulus could be used for visual patterns, reading comprehension, etc.
        question = GeneratedQuestion(
            question_text="Based on the passage, what is the main theme?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="persistence",
            answer_options=["persistence", "love", "fear", "joy"],
            stimulus="The old man climbed the mountain every day for thirty years.",
            source_llm="anthropic",
            source_model="claude-3-5-sonnet",
        )

        assert question.stimulus is not None
        assert question.question_type == QuestionType.VERBAL
        assert "climbed the mountain" in question.stimulus

    def test_stimulus_json_serialization_roundtrip(self):
        """Test that stimulus is preserved through JSON serialization."""
        original = GeneratedQuestion(
            question_text="What was the pattern shown?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="ABBA",
            answer_options=["ABAB", "ABBA", "AABB", "BABA"],
            stimulus="Study this pattern: A B B A",
            metadata={"category": "visual"},
            source_llm="google",
            source_model="gemini-1.5-pro",
        )

        # Serialize to JSON and back
        json_data = original.model_dump_json()
        restored = GeneratedQuestion.model_validate_json(json_data)

        assert restored.stimulus == original.stimulus
        assert restored.question_text == original.question_text
        assert restored.question_type == original.question_type

    def test_stimulus_with_special_characters(self):
        """Test stimulus with special characters and unicode."""
        question = GeneratedQuestion(
            question_text="What symbol appeared third?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="★",
            answer_options=["●", "■", "★", "▲"],
            stimulus="Remember: ● → ■ → ★ → ▲ (symbols with unicode & special chars)",
            source_llm="openai",
            source_model="gpt-4",
        )

        assert "★" in question.stimulus
        assert "→" in question.stimulus
        result = question.to_dict()
        assert result["stimulus"] == question.stimulus

    def test_memory_question_without_stimulus_rejected(self):
        """Test that memory questions without stimulus are rejected at model level."""
        with pytest.raises(ValidationError) as exc_info:
            GeneratedQuestion(
                question_text="What was the third word in the sequence?",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="apple",
                answer_options=["orange", "banana", "apple", "grape"],
                source_llm="openai",
                source_model="gpt-4",
            )
        assert "stimulus" in str(exc_info.value).lower()

    def test_memory_question_with_empty_stimulus_rejected(self):
        """Test that memory questions with empty string stimulus are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GeneratedQuestion(
                question_text="What was the third word in the sequence?",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="apple",
                answer_options=["orange", "banana", "apple", "grape"],
                stimulus="",
                source_llm="openai",
                source_model="gpt-4",
            )
        assert "stimulus" in str(exc_info.value).lower()

    def test_memory_question_with_whitespace_stimulus_rejected(self):
        """Test that memory questions with whitespace-only stimulus are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            GeneratedQuestion(
                question_text="What was the third word in the sequence?",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="apple",
                answer_options=["orange", "banana", "apple", "grape"],
                stimulus="   \n\t  ",
                source_llm="openai",
                source_model="gpt-4",
            )
        assert "stimulus" in str(exc_info.value).lower()

    def test_non_memory_question_without_stimulus_still_allowed(self):
        """Test that non-memory questions are not affected by stimulus validation."""
        for qtype in [
            QuestionType.PATTERN,
            QuestionType.LOGIC,
            QuestionType.SPATIAL,
            QuestionType.MATH,
            QuestionType.VERBAL,
        ]:
            question = GeneratedQuestion(
                question_text="What is the answer to this question?",
                question_type=qtype,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options=["A", "B", "C", "D"],
                source_llm="openai",
                source_model="gpt-4",
            )
            assert question.stimulus is None


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

        assert score.clarity_score == pytest.approx(0.9)
        assert score.overall_score == pytest.approx(0.84)
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
