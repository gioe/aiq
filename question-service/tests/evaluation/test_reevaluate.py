"""Tests for reevaluate_questions.py - db_question_to_generated conversion."""

import sys
from pathlib import Path


# Add parent directory to path for imports (same as reevaluate_questions.py)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.models import DifficultyLevel, GeneratedQuestion, QuestionType  # noqa: E402
from reevaluate_questions import db_question_to_generated  # noqa: E402


def _make_db_question(**overrides) -> dict:
    """Create a minimal database question dict with optional overrides."""
    base = {
        "id": 1,
        "question_text": "What comes next in the sequence: 2, 4, 8, 16, ?",
        "question_type": "pattern",
        "difficulty_level": "medium",
        "correct_answer": "32",
        "answer_options": ["24", "30", "32", "64"],
        "explanation": "Each number doubles.",
        "stimulus": None,
        "sub_type": None,
        "metadata": {},
        "source_llm": "openai",
        "source_model": "gpt-4o",
        "is_active": True,
    }
    base.update(overrides)
    return base


class TestDbQuestionToGenerated:
    """Tests for db_question_to_generated() conversion function."""

    def test_basic_conversion(self):
        """Standard question converts correctly."""
        db_q = _make_db_question()
        result = db_question_to_generated(db_q)

        assert isinstance(result, GeneratedQuestion)
        assert result.question_type == QuestionType.PATTERN
        assert result.difficulty_level == DifficultyLevel.MEDIUM
        assert result.correct_answer == "32"
        assert result.answer_options == ["24", "30", "32", "64"]
        assert result.explanation == "Each number doubles."
        assert result.source_llm == "openai"
        assert result.source_model == "gpt-4o"

    def test_memory_question_with_stimulus(self):
        """Memory question with stimulus converts without error."""
        db_q = _make_db_question(
            question_type="memory",
            question_text="What was the third item in the list you memorized?",
            correct_answer="Elephant",
            answer_options=["Dog", "Cat", "Elephant", "Tiger"],
            stimulus="Memorize this list: Apple, Banana, Elephant, Car, House",
        )
        result = db_question_to_generated(db_q)

        assert result.question_type == QuestionType.MEMORY
        assert (
            result.stimulus == "Memorize this list: Apple, Banana, Elephant, Car, House"
        )

    def test_non_memory_question_without_stimulus(self):
        """Non-memory question without stimulus converts fine (stimulus is None)."""
        db_q = _make_db_question(stimulus=None)
        result = db_question_to_generated(db_q)

        assert result.stimulus is None

    def test_sub_type_preserved(self):
        """Question with sub_type passes it through to GeneratedQuestion."""
        db_q = _make_db_question(sub_type="number_sequence")
        result = db_question_to_generated(db_q)

        assert result.sub_type == "number_sequence"

    def test_sub_type_none_when_absent(self):
        """Question without sub_type defaults to None."""
        db_q = _make_db_question(sub_type=None)
        result = db_question_to_generated(db_q)

        assert result.sub_type is None

    def test_enum_string_values(self):
        """String enum values are converted correctly."""
        db_q = _make_db_question(question_type="logic", difficulty_level="hard")
        result = db_question_to_generated(db_q)

        assert result.question_type == QuestionType.LOGIC
        assert result.difficulty_level == DifficultyLevel.HARD

    def test_enum_object_values(self):
        """Enum object values are handled correctly."""
        db_q = _make_db_question(
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
        )
        result = db_question_to_generated(db_q)

        assert result.question_type == QuestionType.MATH
        assert result.difficulty_level == DifficultyLevel.EASY

    def test_missing_optional_fields_use_defaults(self):
        """Missing optional fields fall back to defaults."""
        db_q = _make_db_question()
        del db_q["explanation"]
        del db_q["stimulus"]
        del db_q["sub_type"]
        del db_q["metadata"]
        del db_q["source_llm"]
        del db_q["source_model"]

        result = db_question_to_generated(db_q)

        assert result.explanation is None
        assert result.stimulus is None
        assert result.sub_type is None
        assert result.metadata == {}
        assert result.source_llm == "unknown"
        assert result.source_model == "unknown"
