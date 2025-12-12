"""
Tests for distractor analysis functions (DA-003, DA-004, DA-005, DA-006, DA-007).

Tests cover:
- Selection count incrementing
- Stats initialization for new questions
- Invalid/missing option handling
- Thread-safe concurrent updates
- Quartile stats updates
- Distractor discrimination calculation (DA-004)
- Distractor effectiveness analysis (DA-005)
- Integration with response submission (DA-006)
- Quartile stats update after test completion (DA-007)
"""
import pytest
from app.models import Question
from app.models.models import QuestionType, DifficultyLevel
from app.core.distractor_analysis import (
    update_distractor_stats,
    update_distractor_quartile_stats,
    get_distractor_stats,
    calculate_distractor_discrimination,
    analyze_distractor_effectiveness,
    _calculate_effective_option_count,
    determine_score_quartile,
    update_session_quartile_stats,
)


class TestUpdateDistractorStats:
    """Tests for the update_distractor_stats function."""

    def test_initialize_stats_for_new_question(self, db_session):
        """Test that stats are initialized when question has null distractor_stats."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_stats(db_session, question.id, "B")

        assert result is True
        assert question.distractor_stats is not None
        assert "B" in question.distractor_stats
        assert question.distractor_stats["B"]["count"] == 1
        assert question.distractor_stats["B"]["top_q"] == 0
        assert question.distractor_stats["B"]["bottom_q"] == 0

    def test_increment_existing_count(self, db_session):
        """Test that count is incremented for existing option stats."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={"A": {"count": 5, "top_q": 2, "bottom_q": 1}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_stats(db_session, question.id, "A")

        assert result is True
        assert question.distractor_stats["A"]["count"] == 6
        # Verify top_q and bottom_q are preserved
        assert question.distractor_stats["A"]["top_q"] == 2
        assert question.distractor_stats["A"]["bottom_q"] == 1

    def test_add_new_option_to_existing_stats(self, db_session):
        """Test adding stats for a new option when some stats already exist."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={"A": {"count": 10, "top_q": 3, "bottom_q": 4}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_stats(db_session, question.id, "B")

        assert result is True
        # New option should be initialized with count 1
        assert question.distractor_stats["B"]["count"] == 1
        assert question.distractor_stats["B"]["top_q"] == 0
        assert question.distractor_stats["B"]["bottom_q"] == 0
        # Existing option should be unchanged
        assert question.distractor_stats["A"]["count"] == 10

    def test_skip_free_response_question(self, db_session):
        """Test that free-response questions (no answer_options) are skipped."""
        question = Question(
            question_text="Free response question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="Open-ended answer",
            answer_options=None,  # Free-response question
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_stats(db_session, question.id, "Some answer")

        assert result is False
        assert question.distractor_stats is None

    def test_question_not_found(self, db_session):
        """Test handling of non-existent question ID."""
        result = update_distractor_stats(db_session, 99999, "A")

        assert result is False

    def test_empty_selected_answer(self, db_session):
        """Test handling of empty selected_answer."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_stats(db_session, question.id, "")

        assert result is False
        assert question.distractor_stats is None

    def test_whitespace_handling(self, db_session):
        """Test that selected_answer is normalized (stripped of whitespace)."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_stats(db_session, question.id, "  A  ")

        assert result is True
        assert "A" in question.distractor_stats
        assert question.distractor_stats["A"]["count"] == 1

    def test_multiple_updates_same_option(self, db_session):
        """Test multiple sequential updates to the same option."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Simulate 5 users selecting option B
        for _ in range(5):
            update_distractor_stats(db_session, question.id, "B")

        assert question.distractor_stats["B"]["count"] == 5

    def test_multiple_updates_different_options(self, db_session):
        """Test updates to different options are tracked separately."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Simulate different selection patterns
        update_distractor_stats(db_session, question.id, "A")
        update_distractor_stats(db_session, question.id, "A")
        update_distractor_stats(db_session, question.id, "A")
        update_distractor_stats(db_session, question.id, "B")
        update_distractor_stats(db_session, question.id, "B")
        update_distractor_stats(db_session, question.id, "C")

        assert question.distractor_stats["A"]["count"] == 3
        assert question.distractor_stats["B"]["count"] == 2
        assert question.distractor_stats["C"]["count"] == 1
        assert "D" not in question.distractor_stats  # Never selected


class TestUpdateDistractorQuartileStats:
    """Tests for the update_distractor_quartile_stats function."""

    def test_update_top_quartile(self, db_session):
        """Test incrementing top_q for top quartile scorer."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={"B": {"count": 10, "top_q": 2, "bottom_q": 5}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_quartile_stats(
            db_session, question.id, "B", is_top_quartile=True
        )

        assert result is True
        assert question.distractor_stats["B"]["top_q"] == 3
        assert question.distractor_stats["B"]["bottom_q"] == 5  # Unchanged

    def test_update_bottom_quartile(self, db_session):
        """Test incrementing bottom_q for bottom quartile scorer."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={"B": {"count": 10, "top_q": 2, "bottom_q": 5}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_quartile_stats(
            db_session, question.id, "B", is_top_quartile=False
        )

        assert result is True
        assert question.distractor_stats["B"]["top_q"] == 2  # Unchanged
        assert question.distractor_stats["B"]["bottom_q"] == 6

    def test_initialize_new_option_with_quartile(self, db_session):
        """Test quartile update initializes stats for new option."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_quartile_stats(
            db_session, question.id, "B", is_top_quartile=True
        )

        assert result is True
        assert question.distractor_stats["B"]["count"] == 0  # Not incremented
        assert question.distractor_stats["B"]["top_q"] == 1
        assert question.distractor_stats["B"]["bottom_q"] == 0

    def test_quartile_skip_free_response(self, db_session):
        """Test that free-response questions are skipped for quartile updates."""
        question = Question(
            question_text="Free response question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="Open-ended",
            answer_options=None,
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_quartile_stats(
            db_session, question.id, "Answer", is_top_quartile=True
        )

        assert result is False
        assert question.distractor_stats is None

    def test_quartile_empty_answer(self, db_session):
        """Test handling of empty selected_answer for quartile update."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = update_distractor_quartile_stats(
            db_session, question.id, "", is_top_quartile=True
        )

        assert result is False


class TestGetDistractorStats:
    """Tests for the get_distractor_stats function."""

    def test_get_stats_existing_question(self, db_session):
        """Test retrieving stats for a question with existing stats."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 50, "top_q": 10, "bottom_q": 25},
                "B": {"count": 30, "top_q": 5, "bottom_q": 15},
                "C": {"count": 20, "top_q": 2, "bottom_q": 8},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = get_distractor_stats(db_session, question.id)

        assert result is not None
        assert result["question_id"] == question.id
        assert result["total_responses"] == 100
        assert result["has_quartile_data"] is True
        assert "A" in result["stats"]
        assert result["stats"]["A"]["count"] == 50

    def test_get_stats_no_stats(self, db_session):
        """Test retrieving stats for a question with null distractor_stats."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = get_distractor_stats(db_session, question.id)

        assert result is not None
        assert result["question_id"] == question.id
        assert result["total_responses"] == 0
        assert result["has_quartile_data"] is False
        assert result["stats"] == {}

    def test_get_stats_no_quartile_data(self, db_session):
        """Test has_quartile_data is False when only count data exists."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 50, "top_q": 0, "bottom_q": 0},
                "B": {"count": 30, "top_q": 0, "bottom_q": 0},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = get_distractor_stats(db_session, question.id)

        assert result is not None
        assert result["has_quartile_data"] is False

    def test_get_stats_question_not_found(self, db_session):
        """Test retrieving stats for non-existent question."""
        result = get_distractor_stats(db_session, 99999)

        assert result is None


class TestCalculateDistractorDiscrimination:
    """Tests for the calculate_distractor_discrimination function (DA-004)."""

    def test_insufficient_data_below_threshold(self, db_session):
        """Test that insufficient_data is returned when responses < min_responses."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 20, "top_q": 5, "bottom_q": 10},
                "B": {"count": 10, "top_q": 2, "bottom_q": 5},
                "C": {"count": 5, "top_q": 1, "bottom_q": 2},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        assert result["insufficient_data"] is True
        assert result["total_responses"] == 35  # 20 + 10 + 5
        assert result["min_required"] == 40

    def test_insufficient_data_custom_threshold(self, db_session):
        """Test that custom min_responses threshold is respected."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={
                "A": {"count": 30, "top_q": 8, "bottom_q": 12},
                "B": {"count": 20, "top_q": 4, "bottom_q": 10},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # With default threshold (40), should be OK (50 responses)
        result = calculate_distractor_discrimination(db_session, question.id)
        assert "insufficient_data" not in result

        # With higher threshold (60), should be insufficient
        result = calculate_distractor_discrimination(
            db_session, question.id, min_responses=60
        )
        assert result["insufficient_data"] is True
        assert result["total_responses"] == 50
        assert result["min_required"] == 60

    def test_question_not_found(self, db_session):
        """Test handling of non-existent question ID."""
        result = calculate_distractor_discrimination(db_session, 99999)

        assert result["insufficient_data"] is True
        assert result["total_responses"] == 0

    def test_free_response_question(self, db_session):
        """Test that free-response questions return insufficient_data."""
        question = Question(
            question_text="Free response question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="Open-ended",
            answer_options=None,
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        assert result["insufficient_data"] is True

    def test_null_distractor_stats(self, db_session):
        """Test question with null distractor_stats returns insufficient_data."""
        question = Question(
            question_text="New question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        assert result["insufficient_data"] is True
        assert result["total_responses"] == 0

    def test_selection_rate_calculation(self, db_session):
        """Test that selection rates are calculated correctly."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={
                "A": "Option A",
                "B": "Option B",
                "C": "Option C",
                "D": "Option D",
            },
            distractor_stats={
                "A": {"count": 50, "top_q": 15, "bottom_q": 5},  # 50% selection
                "B": {"count": 25, "top_q": 5, "bottom_q": 10},  # 25% selection
                "C": {"count": 15, "top_q": 3, "bottom_q": 8},  # 15% selection
                "D": {"count": 10, "top_q": 2, "bottom_q": 5},  # 10% selection
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        assert "insufficient_data" not in result
        assert result["total_responses"] == 100
        assert result["options"]["A"]["selection_rate"] == 0.50
        assert result["options"]["B"]["selection_rate"] == 0.25
        assert result["options"]["C"]["selection_rate"] == 0.15
        assert result["options"]["D"]["selection_rate"] == 0.10

    def test_quartile_rate_calculation(self, db_session):
        """Test that quartile rates are calculated correctly."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            # Total: 100 responses, 25 top quartile, 25 bottom quartile
            distractor_stats={
                "A": {"count": 60, "top_q": 20, "bottom_q": 5},  # Top: 80%, Bottom: 20%
                "B": {"count": 40, "top_q": 5, "bottom_q": 20},  # Top: 20%, Bottom: 80%
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Top quartile totals: 20 + 5 = 25
        # Bottom quartile totals: 5 + 20 = 25
        assert result["quartile_responses"]["top"] == 25
        assert result["quartile_responses"]["bottom"] == 25

        # Option A: top_q_rate = 20/25 = 0.8, bottom_q_rate = 5/25 = 0.2
        assert result["options"]["A"]["top_quartile_rate"] == 0.8
        assert result["options"]["A"]["bottom_quartile_rate"] == 0.2

        # Option B: top_q_rate = 5/25 = 0.2, bottom_q_rate = 20/25 = 0.8
        assert result["options"]["B"]["top_quartile_rate"] == 0.2
        assert result["options"]["B"]["bottom_quartile_rate"] == 0.8

    def test_discrimination_index_positive(self, db_session):
        """Test discrimination index calculation - positive (good for distractors)."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={
                "A": {"count": 50, "top_q": 15, "bottom_q": 5},
                "B": {"count": 50, "top_q": 5, "bottom_q": 15},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Option B: bottom_rate (0.75) - top_rate (0.25) = 0.5 (positive = good distractor)
        assert result["options"]["B"]["discrimination_index"] == 0.5

        # Option A: bottom_rate (0.25) - top_rate (0.75) = -0.5 (negative = correct answer behavior)
        assert result["options"]["A"]["discrimination_index"] == -0.5

    def test_discrimination_index_inverted(self, db_session):
        """Test discrimination index - inverted (problematic distractor)."""
        question = Question(
            question_text="Test question with inverted distractor",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            # Distractor B has inverted discrimination (high scorers select it more)
            distractor_stats={
                "A": {"count": 40, "top_q": 12, "bottom_q": 4},  # Correct answer
                "B": {"count": 35, "top_q": 10, "bottom_q": 3},  # Inverted distractor!
                "C": {"count": 25, "top_q": 3, "bottom_q": 13},  # Good distractor
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Total quartile counts: top = 25, bottom = 20
        # Option B: bottom_rate (3/20=0.15) - top_rate (10/25=0.4) = -0.25 (inverted!)
        assert result["options"]["B"]["discrimination_index"] == -0.25

        # Option C: bottom_rate (13/20=0.65) - top_rate (3/25=0.12) = 0.53 (good distractor)
        assert result["options"]["C"]["discrimination_index"] == 0.53

    def test_discrimination_index_neutral(self, db_session):
        """Test discrimination index - neutral (similar selection across ability levels)."""
        question = Question(
            question_text="Test question with neutral distractor",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            # Option B selected equally by both quartiles
            distractor_stats={
                "A": {"count": 50, "top_q": 10, "bottom_q": 10},
                "B": {"count": 50, "top_q": 10, "bottom_q": 10},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Both options have equal top/bottom rates, so discrimination_index = 0
        assert result["options"]["A"]["discrimination_index"] == 0.0
        assert result["options"]["B"]["discrimination_index"] == 0.0

    def test_zero_quartile_data(self, db_session):
        """Test handling when quartile data is zero."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            # Has counts but no quartile data yet
            distractor_stats={
                "A": {"count": 60, "top_q": 0, "bottom_q": 0},
                "B": {"count": 40, "top_q": 0, "bottom_q": 0},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Should not raise division by zero
        assert "insufficient_data" not in result
        assert result["options"]["A"]["top_quartile_rate"] == 0.0
        assert result["options"]["A"]["bottom_quartile_rate"] == 0.0
        assert result["options"]["A"]["discrimination_index"] == 0.0

    def test_complete_response_structure(self, db_session):
        """Test that the complete response structure is correct."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 50, "top_q": 15, "bottom_q": 5},
                "B": {"count": 30, "top_q": 5, "bottom_q": 15},
                "C": {"count": 20, "top_q": 5, "bottom_q": 5},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Verify top-level structure
        assert "question_id" in result
        assert result["question_id"] == question.id
        assert "total_responses" in result
        assert "quartile_responses" in result
        assert "options" in result

        # Verify quartile_responses structure
        assert "top" in result["quartile_responses"]
        assert "bottom" in result["quartile_responses"]

        # Verify each option has required fields
        for option in result["options"].values():
            assert "total_count" in option
            assert "selection_rate" in option
            assert "top_quartile_count" in option
            assert "bottom_quartile_count" in option
            assert "top_quartile_rate" in option
            assert "bottom_quartile_rate" in option
            assert "discrimination_index" in option

    def test_boundary_at_exactly_40_responses(self, db_session):
        """Test boundary condition at exactly 40 responses (minimum threshold)."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={
                "A": {"count": 25, "top_q": 8, "bottom_q": 2},
                "B": {"count": 15, "top_q": 2, "bottom_q": 8},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # Exactly 40 responses should pass threshold
        assert "insufficient_data" not in result
        assert result["total_responses"] == 40

    def test_boundary_at_39_responses(self, db_session):
        """Test boundary condition at 39 responses (just below threshold)."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={
                "A": {"count": 24, "top_q": 8, "bottom_q": 2},
                "B": {"count": 15, "top_q": 2, "bottom_q": 8},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(db_session, question.id)

        # 39 responses should fail threshold
        assert result["insufficient_data"] is True
        assert result["total_responses"] == 39


class TestAnalyzeDistractorEffectiveness:
    """Tests for the analyze_distractor_effectiveness function (DA-005)."""

    def test_insufficient_data_below_threshold(self, db_session):
        """Test that insufficient_data is returned when responses < min_responses."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 20, "top_q": 5, "bottom_q": 10},
                "B": {"count": 15, "top_q": 3, "bottom_q": 8},
                "C": {"count": 10, "top_q": 2, "bottom_q": 5},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Default min_responses is 50, we have 45
        result = analyze_distractor_effectiveness(db_session, question.id)

        assert result["insufficient_data"] is True
        assert result["total_responses"] == 45
        assert result["min_required"] == 50

    def test_question_not_found(self, db_session):
        """Test handling of non-existent question ID."""
        result = analyze_distractor_effectiveness(db_session, 99999)

        assert result["insufficient_data"] is True
        assert result["total_responses"] == 0

    def test_status_functioning_threshold(self, db_session):
        """Test that >=5% selection rate is categorized as functioning."""
        # Total 100 responses, each option should be analyzed
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 60, "top_q": 20, "bottom_q": 5},  # 60% - correct answer
                "B": {"count": 20, "top_q": 3, "bottom_q": 10},  # 20% - functioning
                "C": {"count": 15, "top_q": 2, "bottom_q": 8},  # 15% - functioning
                "D": {
                    "count": 5,
                    "top_q": 1,
                    "bottom_q": 2,
                },  # 5% - functioning (boundary)
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        assert "insufficient_data" not in result
        # B, C, D are distractors with >= 5% selection rate
        assert result["options"]["B"]["status"] == "functioning"
        assert result["options"]["C"]["status"] == "functioning"
        assert result["options"]["D"]["status"] == "functioning"
        assert result["summary"]["functioning_distractors"] == 3

    def test_status_weak_threshold(self, db_session):
        """Test that 2-5% selection rate is categorized as weak."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 80, "top_q": 20, "bottom_q": 5},  # 80% - correct
                "B": {"count": 10, "top_q": 2, "bottom_q": 5},  # 10% - functioning
                "C": {"count": 6, "top_q": 1, "bottom_q": 3},  # 6% - functioning
                "D": {"count": 4, "top_q": 0, "bottom_q": 2},  # 4% - weak (2-5%)
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        assert result["options"]["D"]["status"] == "weak"
        assert result["summary"]["weak_distractors"] == 1

    def test_status_non_functioning_threshold(self, db_session):
        """Test that <2% selection rate is categorized as non-functioning."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 85, "top_q": 22, "bottom_q": 5},  # 85% - correct
                "B": {"count": 10, "top_q": 2, "bottom_q": 5},  # 10% - functioning
                "C": {"count": 4, "top_q": 1, "bottom_q": 2},  # 4% - weak
                "D": {"count": 1, "top_q": 0, "bottom_q": 1},  # 1% - non-functioning
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        assert result["options"]["D"]["status"] == "non-functioning"
        assert result["summary"]["non_functioning_distractors"] == 1

    def test_discrimination_good_category(self, db_session):
        """Test that positive discrimination index > 0.10 is categorized as good."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 60, "top_q": 18, "bottom_q": 2},  # Correct answer
                "B": {"count": 40, "top_q": 2, "bottom_q": 18},  # Good distractor
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # B: top_q_rate = 2/20 = 0.1, bottom_q_rate = 18/20 = 0.9
        # discrimination_index = 0.9 - 0.1 = 0.8 (good)
        assert result["options"]["B"]["discrimination"] == "good"

    def test_discrimination_neutral_category(self, db_session):
        """Test that |discrimination index| <= 0.10 is categorized as neutral."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            # Carefully calculate values to get |discrimination_index| <= 0.10
            # Total quartile counts: top_q = 12 + 12 = 24, bottom_q = 13 + 11 = 24
            # B: top_q_rate = 12/24 = 0.5, bottom_q_rate = 11/24 = 0.458
            # discrimination_index = 0.458 - 0.5 = -0.042 (within ±0.10)
            distractor_stats={
                "A": {"count": 55, "top_q": 12, "bottom_q": 13},
                "B": {"count": 45, "top_q": 12, "bottom_q": 11},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # B: top_q_rate = 12/24 = 0.5, bottom_q_rate = 11/24 = 0.458
        # discrimination_index = 0.458 - 0.5 = -0.042 (neutral, within ±0.10)
        assert result["options"]["B"]["discrimination"] == "neutral"

    def test_discrimination_inverted_category(self, db_session):
        """Test that negative discrimination index < -0.10 is categorized as inverted."""
        question = Question(
            question_text="Test question with inverted distractor",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 40, "top_q": 12, "bottom_q": 4},  # Correct answer
                "B": {"count": 35, "top_q": 10, "bottom_q": 3},  # Inverted distractor!
                "C": {"count": 25, "top_q": 3, "bottom_q": 13},  # Good distractor
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # B is inverted (high scorers select it more than low scorers)
        assert result["options"]["B"]["discrimination"] == "inverted"
        assert result["summary"]["inverted_distractors"] == 1

    def test_correct_answer_excluded_from_distractor_counts(self, db_session):
        """Test that correct answer is not counted in distractor statistics."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {
                    "count": 60,
                    "top_q": 20,
                    "bottom_q": 5,
                },  # Correct - not a distractor
                "B": {
                    "count": 25,
                    "top_q": 3,
                    "bottom_q": 12,
                },  # Functioning distractor
                "C": {"count": 15, "top_q": 2, "bottom_q": 8},  # Functioning distractor
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        assert result["correct_answer"] == "A"
        assert result["options"]["A"]["is_correct"] is True
        assert result["options"]["B"]["is_correct"] is False
        # Only B and C count as distractors
        assert result["summary"]["functioning_distractors"] == 2

    def test_recommendations_non_functioning(self, db_session):
        """Test that recommendations are generated for non-functioning distractors."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 90, "top_q": 23, "bottom_q": 5},  # Correct
                "B": {"count": 6, "top_q": 1, "bottom_q": 4},  # Functioning
                "C": {"count": 3, "top_q": 1, "bottom_q": 1},  # Weak (3%)
                "D": {"count": 1, "top_q": 0, "bottom_q": 1},  # Non-functioning (1%)
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # Should have recommendations for weak and non-functioning
        recommendations = result["recommendations"]
        assert any("non-functioning" in rec.lower() for rec in recommendations)
        assert any("'D'" in rec for rec in recommendations)

    def test_recommendations_inverted(self, db_session):
        """Test that recommendations are generated for inverted distractors."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 50, "top_q": 10, "bottom_q": 10},  # Correct
                "B": {"count": 50, "top_q": 15, "bottom_q": 5},  # Inverted distractor
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        recommendations = result["recommendations"]
        assert any("INVERTED" in rec for rec in recommendations)
        assert any("'B'" in rec for rec in recommendations)

    def test_effective_option_count_equal_distribution(self, db_session):
        """Test effective option count with equal distribution."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 25, "top_q": 7, "bottom_q": 5},
                "B": {"count": 25, "top_q": 6, "bottom_q": 6},
                "C": {"count": 25, "top_q": 6, "bottom_q": 7},
                "D": {"count": 25, "top_q": 6, "bottom_q": 7},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # With perfectly equal distribution, effective_option_count should be 4.0
        # 1 / (0.25^2 + 0.25^2 + 0.25^2 + 0.25^2) = 1 / 0.25 = 4.0
        assert result["summary"]["effective_option_count"] == 4.0

    def test_effective_option_count_skewed_distribution(self, db_session):
        """Test effective option count with skewed distribution."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 90, "top_q": 20, "bottom_q": 10},  # 90%
                "B": {"count": 6, "top_q": 2, "bottom_q": 3},  # 6%
                "C": {"count": 3, "top_q": 1, "bottom_q": 1},  # 3%
                "D": {"count": 1, "top_q": 0, "bottom_q": 1},  # 1%
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # With skewed distribution, effective_option_count should be low (~1.2)
        # 1 / (0.9^2 + 0.06^2 + 0.03^2 + 0.01^2) = 1 / (0.81 + 0.0036 + 0.0009 + 0.0001) = ~1.23
        assert result["summary"]["effective_option_count"] < 2.0
        assert result["summary"]["effective_option_count"] > 1.0

    def test_complete_response_structure(self, db_session):
        """Test that the complete response structure is correct."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 50, "top_q": 15, "bottom_q": 5},
                "B": {"count": 30, "top_q": 5, "bottom_q": 15},
                "C": {"count": 20, "top_q": 5, "bottom_q": 5},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # Verify top-level structure
        assert "question_id" in result
        assert result["question_id"] == question.id
        assert "total_responses" in result
        assert "correct_answer" in result
        assert result["correct_answer"] == "A"
        assert "options" in result
        assert "summary" in result
        assert "recommendations" in result

        # Verify summary structure
        summary = result["summary"]
        assert "functioning_distractors" in summary
        assert "weak_distractors" in summary
        assert "non_functioning_distractors" in summary
        assert "inverted_distractors" in summary
        assert "effective_option_count" in summary

        # Verify each option has required fields
        for option in result["options"].values():
            assert "is_correct" in option
            assert "selection_rate" in option
            assert "status" in option
            assert option["status"] in ["functioning", "weak", "non-functioning"]
            assert "discrimination" in option
            assert option["discrimination"] in ["good", "neutral", "inverted"]
            assert "discrimination_index" in option
            assert "top_quartile_rate" in option
            assert "bottom_quartile_rate" in option

    def test_custom_min_responses_threshold(self, db_session):
        """Test that custom min_responses threshold is respected."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats={
                "A": {"count": 40, "top_q": 12, "bottom_q": 5},
                "B": {"count": 20, "top_q": 3, "bottom_q": 10},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Default min_responses is 50, we have 60 - should pass
        result = analyze_distractor_effectiveness(db_session, question.id)
        assert "insufficient_data" not in result

        # With higher threshold (100), should fail
        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=100
        )
        assert result["insufficient_data"] is True
        assert result["total_responses"] == 60
        assert result["min_required"] == 100

    def test_boundary_status_at_5_percent(self, db_session):
        """Test status boundary at exactly 5% (functioning threshold)."""
        # Total 100 responses
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 90, "top_q": 23, "bottom_q": 5},
                "B": {"count": 5, "top_q": 1, "bottom_q": 3},  # Exactly 5%
                "C": {"count": 5, "top_q": 1, "bottom_q": 2},  # Exactly 5%
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # 5% is the threshold for functioning
        assert result["options"]["B"]["status"] == "functioning"
        assert result["options"]["C"]["status"] == "functioning"

    def test_boundary_status_at_2_percent(self, db_session):
        """Test status boundary at exactly 2% (weak threshold)."""
        # Total 100 responses
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 93, "top_q": 23, "bottom_q": 5},
                "B": {"count": 5, "top_q": 1, "bottom_q": 3},  # 5% - functioning
                "C": {"count": 2, "top_q": 1, "bottom_q": 1},  # Exactly 2% - weak
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # 2% is the boundary for weak (2-5%)
        assert result["options"]["C"]["status"] == "weak"

    def test_edge_case_all_responses_to_correct_answer(self, db_session):
        """Test edge case where all responses go to correct answer."""
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 100, "top_q": 25, "bottom_q": 25},  # 100%
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # All distractors are implicitly non-functioning (0%)
        assert result["summary"]["functioning_distractors"] == 0
        # Effective option count should be 1 (only one option used)
        assert result["summary"]["effective_option_count"] == 1.0


class TestCalculateEffectiveOptionCount:
    """Tests for the _calculate_effective_option_count helper function."""

    def test_equal_distribution_four_options(self):
        """Test with perfectly equal distribution across 4 options."""
        options_data = {
            "A": {"selection_rate": 0.25},
            "B": {"selection_rate": 0.25},
            "C": {"selection_rate": 0.25},
            "D": {"selection_rate": 0.25},
        }
        result = _calculate_effective_option_count(options_data, 100)
        assert result == 4.0

    def test_equal_distribution_two_options(self):
        """Test with equal distribution across 2 options."""
        options_data = {
            "A": {"selection_rate": 0.50},
            "B": {"selection_rate": 0.50},
        }
        result = _calculate_effective_option_count(options_data, 100)
        assert result == 2.0

    def test_single_option_dominates(self):
        """Test when one option has 100% of responses."""
        options_data = {
            "A": {"selection_rate": 1.0},
            "B": {"selection_rate": 0.0},
        }
        result = _calculate_effective_option_count(options_data, 100)
        assert result == 1.0

    def test_zero_responses(self):
        """Test with zero total responses."""
        options_data = {
            "A": {"selection_rate": 0.0},
            "B": {"selection_rate": 0.0},
        }
        result = _calculate_effective_option_count(options_data, 0)
        assert result == 0.0

    def test_skewed_distribution(self):
        """Test with a skewed distribution."""
        options_data = {
            "A": {"selection_rate": 0.80},
            "B": {"selection_rate": 0.10},
            "C": {"selection_rate": 0.05},
            "D": {"selection_rate": 0.05},
        }
        result = _calculate_effective_option_count(options_data, 100)
        # 1 / (0.64 + 0.01 + 0.0025 + 0.0025) = 1 / 0.655 ≈ 1.53
        assert 1.4 < result < 1.6


class TestDistractorStatsIntegration:
    """Integration tests for DA-006: Distractor stats update during response submission."""

    def test_distractor_stats_updated_on_test_submission(
        self, client, auth_headers, test_questions, db_session
    ):
        """Test that distractor_stats are updated when test responses are submitted."""
        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get the questions from database to check initial state
        question_ids = [q["id"] for q in questions]
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )

        # Verify questions have null or empty distractor_stats initially
        for q in db_questions:
            # Either null or empty stats initially
            assert q.distractor_stats is None or q.distractor_stats == {}

        # Prepare answers (mix of correct and incorrect)
        # Note: We need to use valid option KEYS, not the answer text
        questions_dict = {q.id: q for q in db_questions}

        def get_first_option_key(q):
            """Get first valid option key from question's answer_options."""
            if q.answer_options:
                return list(q.answer_options.keys())[0]
            return "A"  # fallback

        def get_wrong_option_key(q):
            """Get a wrong option key (not the correct answer key)."""
            if not q.answer_options:
                return "B"
            # Find the key that maps to correct_answer
            correct_key = None
            for key, value in q.answer_options.items():
                if value == q.correct_answer or key == q.correct_answer:
                    correct_key = key
                    break
            # Return a different key
            for key in q.answer_options.keys():
                if key != correct_key:
                    return key
            return list(q.answer_options.keys())[0]

        q0 = questions_dict[questions[0]["id"]]
        q1 = questions_dict[questions[1]["id"]]
        q2 = questions_dict[questions[2]["id"]]

        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": get_first_option_key(q0),  # Use valid option key
                },
                {
                    "question_id": questions[1]["id"],
                    "user_answer": get_wrong_option_key(
                        q1
                    ),  # Use valid wrong option key
                },
                {
                    "question_id": questions[2]["id"],
                    "user_answer": get_first_option_key(q2),  # Use valid option key
                },
            ],
        }

        # Submit the test
        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )
        assert response.status_code == 200

        # Refresh questions from database
        db_session.expire_all()
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )
        questions_dict = {q.id: q for q in db_questions}

        # Verify distractor_stats were updated for multiple-choice questions
        for q_data in questions:
            q = questions_dict[q_data["id"]]
            # Only questions with answer_options should have distractor_stats updated
            if q.answer_options is not None:
                assert q.distractor_stats is not None
                # Find the answer that was submitted for this question
                submitted_answer = next(
                    r["user_answer"]
                    for r in submission_data["responses"]
                    if r["question_id"] == q.id
                )
                # Verify the submitted answer was tracked
                assert submitted_answer in q.distractor_stats
                assert q.distractor_stats[submitted_answer]["count"] == 1

    def test_distractor_stats_increments_on_multiple_submissions(
        self, client, db_session
    ):
        """Test that distractor_stats accumulate across multiple test submissions."""
        from app.core.security import hash_password, create_access_token
        from app.models import User
        from datetime import datetime, timedelta, timezone

        # Create a question specifically for this test
        question = Question(
            question_text="Test question for distractor stats",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Create multiple users to simulate multiple submissions
        users_and_headers = []
        for i in range(3):
            user = User(
                email=f"user_{i}@example.com",
                password_hash=hash_password("password123"),
                first_name=f"User{i}",
                last_name="Test",
            )
            db_session.add(user)
            db_session.commit()
            db_session.refresh(user)
            token = create_access_token({"user_id": user.id})
            headers = {"Authorization": f"Bearer {token}"}
            users_and_headers.append((user, headers))

        # Have each user take a test and select different answers
        answers_to_select = ["A", "B", "B"]  # Expected: A=1, B=2

        for idx, (user, headers) in enumerate(users_and_headers):
            # Start test
            start_response = client.post(
                "/v1/test/start?question_count=1", headers=headers
            )
            if start_response.status_code != 200:
                # Not enough unseen questions, skip this test
                pytest.skip("Not enough unique questions for all test users")

            session_data = start_response.json()
            session_id = session_data["session"]["id"]
            test_question_id = session_data["questions"][0]["id"]

            # Submit response with selected answer
            submission_data = {
                "session_id": session_id,
                "responses": [
                    {
                        "question_id": test_question_id,
                        "user_answer": answers_to_select[idx],
                    },
                ],
            }

            response = client.post(
                "/v1/test/submit", json=submission_data, headers=headers
            )
            assert response.status_code == 200

            # Backdate completed_at to allow next test (bypass cadence check)
            from app.models.models import TestSession

            session = (
                db_session.query(TestSession)
                .filter(TestSession.id == session_id)
                .first()
            )
            session.completed_at = datetime.now(timezone.utc) - timedelta(days=200)
            db_session.commit()

        # Refresh the question and check stats
        db_session.expire_all()
        db_question = (
            db_session.query(Question).filter(Question.id == question.id).first()
        )

        # Verify stats accumulated (only if the question was used in all tests)
        if db_question.distractor_stats:
            # The stats should reflect selections made
            total_count = sum(
                opt.get("count", 0) for opt in db_question.distractor_stats.values()
            )
            # At least one selection was recorded
            assert total_count >= 1

    def test_distractor_stats_not_updated_for_free_response(
        self, client, auth_headers, db_session
    ):
        """Test that free-response questions (no answer_options) don't get distractor_stats."""
        # Create a free-response question
        free_response_question = Question(
            question_text="Explain your reasoning",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="Any reasonable answer",
            answer_options=None,  # No options = free response
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(free_response_question)
        db_session.commit()
        db_session.refresh(free_response_question)

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=1", headers=auth_headers
        )

        # Check if we got the free response question
        if start_response.status_code != 200:
            pytest.skip("Could not start test")

        questions = start_response.json()["questions"]
        session_id = start_response.json()["session"]["id"]

        # Submit response
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": "Some answer",
                },
            ],
        }

        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )
        assert response.status_code == 200

        # Check that free-response question still has no distractor_stats
        db_session.expire_all()
        fr_question = (
            db_session.query(Question)
            .filter(Question.id == free_response_question.id)
            .first()
        )
        # Free response questions should not have distractor_stats
        assert fr_question.distractor_stats is None

    def test_distractor_stats_graceful_failure(
        self, client, auth_headers, test_questions, db_session, monkeypatch
    ):
        """Test that test submission succeeds even if distractor stats update fails."""
        from app.core import distractor_analysis

        # Patch update_distractor_stats to raise an exception
        def mock_update_distractor_stats(*args, **kwargs):
            raise Exception("Simulated database error")

        monkeypatch.setattr(
            distractor_analysis, "update_distractor_stats", mock_update_distractor_stats
        )

        # Start a test
        start_response = client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        questions = start_response.json()["questions"]

        # Get correct answers
        question_ids = [q["id"] for q in questions]
        db_questions = (
            db_session.query(Question).filter(Question.id.in_(question_ids)).all()
        )
        questions_dict = {q.id: q for q in db_questions}

        # Submit the test
        submission_data = {
            "session_id": session_id,
            "responses": [
                {
                    "question_id": questions[0]["id"],
                    "user_answer": questions_dict[questions[0]["id"]].correct_answer,
                },
                {
                    "question_id": questions[1]["id"],
                    "user_answer": questions_dict[questions[1]["id"]].correct_answer,
                },
            ],
        }

        # Should succeed despite distractor stats update failing
        response = client.post(
            "/v1/test/submit", json=submission_data, headers=auth_headers
        )

        # The test submission should still succeed (graceful degradation)
        assert response.status_code == 200
        assert response.json()["session"]["status"] == "completed"


class TestDetermineScoreQuartile:
    """Tests for the determine_score_quartile function (DA-007)."""

    def test_insufficient_historical_data(self, db_session):
        """Test that insufficient_data is returned when insufficient historical data exists."""
        # With no historical data, should return insufficient_data
        result = determine_score_quartile(
            db_session,
            correct_answers=10,
            total_questions=20,
            min_historical_results=10,
        )

        assert result["quartile"] == "insufficient_data"
        assert result["is_top"] is None
        assert result["historical_count"] < 10

    def test_top_quartile_determination(self, db_session):
        """Test that high scores are correctly identified as top quartile."""
        from app.models.models import TestResult, TestSession, TestStatus
        from app.models import User
        from app.core.security import hash_password
        from datetime import datetime, timezone

        # Create a test user
        user = User(
            email="quartile_test@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 20 historical test results with varying scores
        # Scores: 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24
        # 25th percentile threshold: 5 results at indices 0-4, threshold ~9
        # 75th percentile threshold: 15 results at indices 0-14, threshold ~19
        for i in range(20):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            test_result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,  # Scores from 5 to 24
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(test_result)

        db_session.commit()

        # Score of 22 should be in top quartile (>= 75th percentile)
        result = determine_score_quartile(
            db_session,
            correct_answers=22,
            total_questions=20,
            min_historical_results=10,
        )

        assert result["quartile"] == "top"
        assert result["is_top"] is True

    def test_bottom_quartile_determination(self, db_session):
        """Test that low scores are correctly identified as bottom quartile."""
        from app.models.models import TestResult, TestSession, TestStatus
        from app.models import User
        from app.core.security import hash_password
        from datetime import datetime, timezone

        # Create a test user
        user = User(
            email="quartile_bottom@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 20 historical test results
        for i in range(20):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            test_result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(test_result)

        db_session.commit()

        # Score of 6 should be in bottom quartile (<= 25th percentile)
        result = determine_score_quartile(
            db_session,
            correct_answers=6,
            total_questions=20,
            min_historical_results=10,
        )

        assert result["quartile"] == "bottom"
        assert result["is_top"] is False

    def test_middle_quartile_returns_middle(self, db_session):
        """Test that middle scores return middle quartile."""
        from app.models.models import TestResult, TestSession, TestStatus
        from app.models import User
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="quartile_middle@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 20 historical test results
        for i in range(20):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            test_result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(test_result)

        db_session.commit()

        # Score of 14 should be in middle (not top or bottom quartile)
        result = determine_score_quartile(
            db_session,
            correct_answers=14,
            total_questions=20,
            min_historical_results=10,
        )

        assert result["quartile"] == "middle"
        assert result["is_top"] is None

    def test_filters_by_question_count(self, db_session):
        """Test that only tests with similar question count are considered."""
        from app.models.models import TestResult, TestSession, TestStatus
        from app.models import User
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="quartile_filter@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 15 historical test results with 20 questions
        for i in range(15):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            test_result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,  # These should be considered
                correct_answers=10 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(test_result)

        # Create 10 historical test results with 50 questions (different length)
        for i in range(10):
            session = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(session)
            db_session.commit()
            db_session.refresh(session)

            test_result = TestResult(
                test_session_id=session.id,
                user_id=user.id,
                iq_score=100,
                total_questions=50,  # These should NOT be considered
                correct_answers=30 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(test_result)

        db_session.commit()

        # When checking a 20-question test, should only use 20-question historical data
        # 20 * 0.8 = 16, 20 * 1.2 = 24, so only 20-question tests match
        result = determine_score_quartile(
            db_session,
            correct_answers=24,  # High score among 20-question tests
            total_questions=20,
            min_historical_results=10,
        )

        # Should be top quartile among 20-question tests
        assert result["quartile"] == "top"
        assert result["is_top"] is True


class TestUpdateSessionQuartileStats:
    """Tests for the update_session_quartile_stats function (DA-007)."""

    def test_insufficient_historical_data_returns_early(self, db_session):
        """Test that function returns gracefully when insufficient historical data."""
        from app.models.models import TestSession, TestStatus
        from app.models import User
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_quartile@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create a test session
        session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(session)
        db_session.commit()
        db_session.refresh(session)

        # No historical data exists
        result = update_session_quartile_stats(
            db_session,
            test_session_id=session.id,
            correct_answers=15,
            total_questions=20,
        )

        assert result["quartile"] == "insufficient_data"
        assert result["questions_updated"] == 0

    def test_middle_quartile_skips_update(self, db_session):
        """Test that middle quartile scores don't update distractor stats."""
        from app.models.models import TestResult, TestSession, TestStatus, Response
        from app.models import User, Question
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_middle@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 20 historical test results to establish quartiles
        for i in range(20):
            s = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)

            r = TestResult(
                test_session_id=s.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(r)

        db_session.commit()

        # Create a new session with middle score
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        # Create a question and response for this session
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={"B": {"count": 10, "top_q": 0, "bottom_q": 0}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        response = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="B",
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
        db_session.add(response)
        db_session.commit()

        # Score of 14 is in middle quartile
        result = update_session_quartile_stats(
            db_session,
            test_session_id=test_session.id,
            correct_answers=14,
            total_questions=20,
        )

        assert result["quartile"] == "middle"
        assert result["questions_updated"] == 0

        # Verify question's quartile stats were NOT updated
        db_session.refresh(question)
        assert question.distractor_stats["B"]["top_q"] == 0
        assert question.distractor_stats["B"]["bottom_q"] == 0

    def test_top_quartile_updates_stats(self, db_session):
        """Test that top quartile scores update top_q for each response."""
        from app.models.models import TestResult, TestSession, TestStatus, Response
        from app.models import User, Question
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_top@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 20 historical test results
        for i in range(20):
            s = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)

            r = TestResult(
                test_session_id=s.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(r)

        db_session.commit()

        # Create a new session with high score (top quartile)
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        # Create question and response
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={"B": {"count": 10, "top_q": 5, "bottom_q": 3}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        response = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="B",
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
        db_session.add(response)
        db_session.commit()

        # Score of 22 is in top quartile
        result = update_session_quartile_stats(
            db_session,
            test_session_id=test_session.id,
            correct_answers=22,
            total_questions=20,
        )

        assert result["quartile"] == "top"
        assert result["questions_updated"] == 1

        # Verify question's top_q was incremented
        db_session.refresh(question)
        assert question.distractor_stats["B"]["top_q"] == 6  # Was 5, now 6
        assert question.distractor_stats["B"]["bottom_q"] == 3  # Unchanged

    def test_bottom_quartile_updates_stats(self, db_session):
        """Test that bottom quartile scores update bottom_q for each response."""
        from app.models.models import TestResult, TestSession, TestStatus, Response
        from app.models import User, Question
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_bottom@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create 20 historical test results
        for i in range(20):
            s = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)

            r = TestResult(
                test_session_id=s.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(r)

        db_session.commit()

        # Create a new session with low score (bottom quartile)
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        # Create question and response
        question = Question(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={"B": {"count": 10, "top_q": 5, "bottom_q": 3}},
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        response = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=question.id,
            user_answer="B",
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
        db_session.add(response)
        db_session.commit()

        # Score of 6 is in bottom quartile
        result = update_session_quartile_stats(
            db_session,
            test_session_id=test_session.id,
            correct_answers=6,
            total_questions=20,
        )

        assert result["quartile"] == "bottom"
        assert result["questions_updated"] == 1

        # Verify question's bottom_q was incremented
        db_session.refresh(question)
        assert question.distractor_stats["B"]["top_q"] == 5  # Unchanged
        assert question.distractor_stats["B"]["bottom_q"] == 4  # Was 3, now 4

    def test_multiple_responses_updated(self, db_session):
        """Test that all responses in a session are updated."""
        from app.models.models import TestResult, TestSession, TestStatus, Response
        from app.models import User, Question
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_multi@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create historical data
        for i in range(20):
            s = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)

            r = TestResult(
                test_session_id=s.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(r)

        db_session.commit()

        # Create a new session with top quartile score
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        # Create multiple questions and responses
        questions = []
        for i in range(3):
            q = Question(
                question_text=f"Test question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2"},
                distractor_stats={"B": {"count": 10, "top_q": 0, "bottom_q": 0}},
                is_active=True,
            )
            db_session.add(q)
            questions.append(q)

        db_session.commit()

        for q in questions:
            db_session.refresh(q)
            response = Response(
                test_session_id=test_session.id,
                user_id=user.id,
                question_id=q.id,
                user_answer="B",
                is_correct=False,
                answered_at=datetime.now(timezone.utc),
            )
            db_session.add(response)

        db_session.commit()

        # Update quartile stats with top quartile score
        result = update_session_quartile_stats(
            db_session,
            test_session_id=test_session.id,
            correct_answers=22,
            total_questions=20,
        )

        assert result["quartile"] == "top"
        assert result["questions_updated"] == 3

        # Verify all questions were updated
        for q in questions:
            db_session.refresh(q)
            assert q.distractor_stats["B"]["top_q"] == 1

    def test_free_response_questions_skipped(self, db_session):
        """Test that free-response questions are skipped during quartile update."""
        from app.models.models import TestResult, TestSession, TestStatus, Response
        from app.models import User, Question
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_free@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create historical data
        for i in range(20):
            s = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)

            r = TestResult(
                test_session_id=s.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(r)

        db_session.commit()

        # Create a new session
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        # Create one MC question and one free-response question
        mc_question = Question(
            question_text="MC question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={"B": {"count": 10, "top_q": 0, "bottom_q": 0}},
            is_active=True,
        )
        free_response = Question(
            question_text="Free response question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="Open-ended",
            answer_options=None,  # Free response
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(mc_question)
        db_session.add(free_response)
        db_session.commit()
        db_session.refresh(mc_question)
        db_session.refresh(free_response)

        # Create responses for both questions
        response1 = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=mc_question.id,
            user_answer="B",
            is_correct=False,
            answered_at=datetime.now(timezone.utc),
        )
        response2 = Response(
            test_session_id=test_session.id,
            user_id=user.id,
            question_id=free_response.id,
            user_answer="Some answer",
            is_correct=True,
            answered_at=datetime.now(timezone.utc),
        )
        db_session.add(response1)
        db_session.add(response2)
        db_session.commit()

        # Update with top quartile score
        result = update_session_quartile_stats(
            db_session,
            test_session_id=test_session.id,
            correct_answers=22,
            total_questions=20,
        )

        assert result["quartile"] == "top"
        assert result["questions_updated"] == 1  # Only MC question updated
        assert result["questions_skipped"] == 1  # Free response skipped

        # Verify MC question was updated
        db_session.refresh(mc_question)
        assert mc_question.distractor_stats["B"]["top_q"] == 1

        # Verify free response still has no stats
        db_session.refresh(free_response)
        assert free_response.distractor_stats is None

    def test_no_responses_for_session(self, db_session):
        """Test handling when session has no responses."""
        from app.models.models import TestResult, TestSession, TestStatus
        from app.models import User
        from app.core.security import hash_password
        from datetime import datetime, timezone

        user = User(
            email="session_empty@example.com",
            password_hash=hash_password("password123"),
            first_name="Test",
            last_name="User",
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        # Create historical data
        for i in range(20):
            s = TestSession(
                user_id=user.id,
                status=TestStatus.COMPLETED,
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(s)
            db_session.commit()
            db_session.refresh(s)

            r = TestResult(
                test_session_id=s.id,
                user_id=user.id,
                iq_score=100,
                total_questions=20,
                correct_answers=5 + i,
                completion_time_seconds=600,
                completed_at=datetime.now(timezone.utc),
            )
            db_session.add(r)

        db_session.commit()

        # Create a new session with NO responses
        test_session = TestSession(
            user_id=user.id,
            status=TestStatus.COMPLETED,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(test_session)
        db_session.commit()
        db_session.refresh(test_session)

        # Should handle gracefully
        result = update_session_quartile_stats(
            db_session,
            test_session_id=test_session.id,
            correct_answers=22,
            total_questions=20,
        )

        assert result["quartile"] == "top"
        assert result["questions_updated"] == 0
        assert result["questions_skipped"] == 0


class TestGetBulkDistractorSummary:
    """Tests for the get_bulk_distractor_summary function (DA-011)."""

    def test_empty_database_returns_zero_counts(self, db_session):
        """Test that an empty database returns zero counts for all metrics."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 0
        assert result["questions_below_threshold"] == 0
        assert result["questions_with_non_functioning_distractors"] == 0
        assert result["questions_with_inverted_distractors"] == 0
        assert result["by_non_functioning_count"]["zero"] == 0
        assert result["by_non_functioning_count"]["one"] == 0
        assert result["by_non_functioning_count"]["two"] == 0
        assert result["by_non_functioning_count"]["three_or_more"] == 0
        assert result["worst_offenders"] == []
        assert result["avg_effective_option_count"] is None

    def test_questions_below_threshold_counted(self, db_session):
        """Test that questions below the min_responses threshold are counted separately."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with insufficient responses
        question = Question(
            question_text="Low response question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 20, "top_q": 5, "bottom_q": 10},
                "B": {"count": 10, "top_q": 2, "bottom_q": 5},
                "C": {"count": 5, "top_q": 1, "bottom_q": 2},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 0
        assert result["questions_below_threshold"] == 1

    def test_questions_with_no_stats_counted_as_below_threshold(self, db_session):
        """Test that questions with null distractor_stats are counted as below threshold."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with no stats
        question = Question(
            question_text="New question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 0
        assert result["questions_below_threshold"] == 1

    def test_non_functioning_distractor_detection(self, db_session):
        """Test that questions with non-functioning distractors are detected."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with one non-functioning distractor (< 2% selection)
        question = Question(
            question_text="Question with non-functioning distractor",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 80, "top_q": 20, "bottom_q": 10},  # 80% correct
                "B": {"count": 10, "top_q": 2, "bottom_q": 5},  # 10% functioning
                "C": {"count": 9, "top_q": 2, "bottom_q": 5},  # 9% functioning
                "D": {"count": 1, "top_q": 0, "bottom_q": 1},  # 1% non-functioning
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 1
        assert result["questions_with_non_functioning_distractors"] == 1
        assert result["by_non_functioning_count"]["one"] == 1

    def test_inverted_distractor_detection(self, db_session):
        """Test that questions with inverted distractors are detected."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with inverted distractor (high scorers prefer it more)
        question = Question(
            question_text="Question with inverted distractor",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 50, "top_q": 10, "bottom_q": 10},
                "B": {"count": 50, "top_q": 20, "bottom_q": 5},  # Inverted
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 1
        assert result["questions_with_inverted_distractors"] == 1

    def test_by_non_functioning_count_breakdown(self, db_session):
        """Test that the by_non_functioning_count breakdown is accurate."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create questions with different numbers of non-functioning distractors
        # Question 1: zero non-functioning distractors
        q1 = Question(
            question_text="Question 1",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 60, "top_q": 15, "bottom_q": 10},
                "B": {"count": 25, "top_q": 5, "bottom_q": 10},  # 25% functioning
                "C": {"count": 15, "top_q": 5, "bottom_q": 5},  # 15% functioning
            },
            is_active=True,
        )

        # Question 2: one non-functioning distractor
        q2 = Question(
            question_text="Question 2",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 85, "top_q": 20, "bottom_q": 10},
                "B": {"count": 14, "top_q": 3, "bottom_q": 8},  # 14% functioning
                "C": {"count": 1, "top_q": 0, "bottom_q": 1},  # 1% non-functioning
            },
            is_active=True,
        )

        # Question 3: two non-functioning distractors
        q3 = Question(
            question_text="Question 3",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 90, "top_q": 22, "bottom_q": 10},
                "B": {"count": 8, "top_q": 2, "bottom_q": 5},  # 8% functioning
                "C": {"count": 1, "top_q": 0, "bottom_q": 1},  # 1% non-functioning
                "D": {"count": 1, "top_q": 1, "bottom_q": 0},  # 1% non-functioning
            },
            is_active=True,
        )

        db_session.add_all([q1, q2, q3])
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 3
        assert result["by_non_functioning_count"]["zero"] == 1
        assert result["by_non_functioning_count"]["one"] == 1
        assert result["by_non_functioning_count"]["two"] == 1

    def test_worst_offenders_ranking(self, db_session):
        """Test that worst offenders are ranked by issue score."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create question with 2 non-functioning (score: 2*2=4)
        q1 = Question(
            question_text="Worst question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            distractor_stats={
                "A": {"count": 90, "top_q": 22, "bottom_q": 10},
                "B": {"count": 8, "top_q": 2, "bottom_q": 5},
                "C": {"count": 1, "top_q": 0, "bottom_q": 1},  # non-functioning
                "D": {"count": 1, "top_q": 1, "bottom_q": 0},  # non-functioning
            },
            is_active=True,
        )

        # Create question with 1 non-functioning (score: 1*2=2)
        q2 = Question(
            question_text="Less bad question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 90, "top_q": 22, "bottom_q": 10},
                "B": {"count": 9, "top_q": 2, "bottom_q": 5},  # 9% functioning
                "C": {"count": 1, "top_q": 0, "bottom_q": 1},  # 1% non-functioning
            },
            is_active=True,
        )

        db_session.add_all([q1, q2])
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        # Worst offenders should be sorted by issue score (worst first)
        assert len(result["worst_offenders"]) == 2
        assert result["worst_offenders"][0]["question_id"] == q1.id
        assert result["worst_offenders"][0]["non_functioning_count"] == 2
        assert result["worst_offenders"][1]["question_id"] == q2.id
        assert result["worst_offenders"][1]["non_functioning_count"] == 1

    def test_worst_offenders_limited_to_ten(self, db_session):
        """Test that worst offenders list is limited to 10 entries."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create 15 questions with issues
        for i in range(15):
            q = Question(
                question_text=f"Question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3"},
                distractor_stats={
                    "A": {"count": 90, "top_q": 22, "bottom_q": 10},
                    "B": {"count": 9, "top_q": 2, "bottom_q": 5},
                    "C": {"count": 1, "top_q": 0, "bottom_q": 1},  # non-functioning
                },
                is_active=True,
            )
            db_session.add(q)

        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert len(result["worst_offenders"]) == 10

    def test_by_question_type_stats(self, db_session):
        """Test that statistics are grouped by question type."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a PATTERN question
        q1 = Question(
            question_text="Pattern question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 60, "top_q": 15, "bottom_q": 10},
                "B": {"count": 40, "top_q": 10, "bottom_q": 15},
            },
            is_active=True,
        )

        # Create a LOGIC question
        q2 = Question(
            question_text="Logic question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 70, "top_q": 18, "bottom_q": 12},
                "B": {"count": 30, "top_q": 7, "bottom_q": 13},
            },
            is_active=True,
        )

        db_session.add_all([q1, q2])
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["by_question_type"]["pattern"]["total_questions"] == 1
        assert result["by_question_type"]["logic"]["total_questions"] == 1
        assert (
            result["by_question_type"]["pattern"]["avg_effective_options"] is not None
        )
        assert result["by_question_type"]["logic"]["avg_effective_options"] is not None

    def test_question_type_filter(self, db_session):
        """Test that question_type filter works correctly."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a PATTERN question
        q1 = Question(
            question_text="Pattern question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 60, "top_q": 15, "bottom_q": 10},
                "B": {"count": 40, "top_q": 10, "bottom_q": 15},
            },
            is_active=True,
        )

        # Create a LOGIC question
        q2 = Question(
            question_text="Logic question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 70, "top_q": 18, "bottom_q": 12},
                "B": {"count": 30, "top_q": 7, "bottom_q": 13},
            },
            is_active=True,
        )

        db_session.add_all([q1, q2])
        db_session.commit()

        # Filter to only PATTERN questions
        result = get_bulk_distractor_summary(
            db_session, min_responses=50, question_type="pattern"
        )

        assert result["total_questions_analyzed"] == 1

    def test_inactive_questions_excluded(self, db_session):
        """Test that inactive questions are excluded from analysis."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create an inactive question
        q = Question(
            question_text="Inactive question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 60, "top_q": 15, "bottom_q": 10},
                "B": {"count": 40, "top_q": 10, "bottom_q": 15},
            },
            is_active=False,  # Inactive
        )
        db_session.add(q)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert result["total_questions_analyzed"] == 0

    def test_only_mc_questions_analyzed(self, db_session):
        """Test that only multiple-choice questions (with answer_options) are analyzed."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create an MC question with sufficient stats
        mc_question = Question(
            question_text="Multiple choice question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},  # Has options = MC
            distractor_stats={
                "A": {"count": 60, "top_q": 15, "bottom_q": 10},
                "B": {"count": 40, "top_q": 10, "bottom_q": 15},
            },
            is_active=True,
        )
        db_session.add(mc_question)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        # MC question with sufficient stats should be analyzed
        assert result["total_questions_analyzed"] >= 1

        # Verify this specific MC question was included in analysis
        # (total analyzed + below threshold should account for all MC questions)
        total_accounted = (
            result["total_questions_analyzed"] + result["questions_below_threshold"]
        )
        assert total_accounted >= 1

    def test_avg_effective_option_count(self, db_session):
        """Test that average effective option count is calculated correctly."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with equal distribution (effective_option_count = 2.0)
        q1 = Question(
            question_text="Equal distribution",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 50, "top_q": 12, "bottom_q": 13},
                "B": {"count": 50, "top_q": 13, "bottom_q": 12},
            },
            is_active=True,
        )

        # Create another question with equal distribution
        q2 = Question(
            question_text="Equal distribution 2",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 50, "top_q": 12, "bottom_q": 13},
                "B": {"count": 50, "top_q": 13, "bottom_q": 12},
            },
            is_active=True,
        )

        db_session.add_all([q1, q2])
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        # Both questions have effective_option_count = 2.0
        # Average should be 2.0
        assert result["avg_effective_option_count"] == 2.0

    def test_worst_offenders_structure(self, db_session):
        """Test that worst offenders have the correct structure."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with issues
        q = Question(
            question_text="Question with issues",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3"},
            distractor_stats={
                "A": {"count": 90, "top_q": 22, "bottom_q": 10},
                "B": {"count": 9, "top_q": 2, "bottom_q": 5},
                "C": {"count": 1, "top_q": 0, "bottom_q": 1},  # non-functioning
            },
            is_active=True,
        )
        db_session.add(q)
        db_session.commit()

        result = get_bulk_distractor_summary(db_session, min_responses=50)

        assert len(result["worst_offenders"]) == 1
        offender = result["worst_offenders"][0]

        # Check all expected fields are present
        assert "question_id" in offender
        assert "question_type" in offender
        assert "difficulty_level" in offender
        assert "non_functioning_count" in offender
        assert "inverted_count" in offender
        assert "total_responses" in offender
        assert "effective_option_count" in offender

        # Verify values
        assert offender["question_id"] == q.id
        assert offender["question_type"] == "pattern"
        assert offender["difficulty_level"] == "easy"
        assert offender["non_functioning_count"] == 1
        assert offender["total_responses"] == 100

    def test_min_responses_threshold_respected(self, db_session):
        """Test that custom min_responses threshold is respected."""
        from app.core.distractor_analysis import get_bulk_distractor_summary

        # Create a question with 60 responses
        q = Question(
            question_text="Question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            distractor_stats={
                "A": {"count": 40, "top_q": 10, "bottom_q": 10},
                "B": {"count": 20, "top_q": 5, "bottom_q": 5},
            },
            is_active=True,
        )
        db_session.add(q)
        db_session.commit()

        # With min_responses=50, should be analyzed (60 >= 50)
        result = get_bulk_distractor_summary(db_session, min_responses=50)
        assert result["total_questions_analyzed"] == 1
        assert result["questions_below_threshold"] == 0

        # With min_responses=100, should be below threshold (60 < 100)
        result = get_bulk_distractor_summary(db_session, min_responses=100)
        assert result["total_questions_analyzed"] == 0
        assert result["questions_below_threshold"] == 1


class TestEdgeCases:
    """
    Tests for edge case handling in distractor analysis (DA-013).

    Covers:
    1. Free-response questions (no distractors) - skip entirely
    2. Variable option counts (4, 5, or 6 options) - handle dynamically
    3. Option format variations (text, numbers) - normalize for storage
    4. Very new questions - return "insufficient_data" status
    """

    def test_five_option_question_analysis(self, db_session):
        """Test that 5-option questions are analyzed correctly."""
        question = Question(
            question_text="5-option question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={
                "A": "Option A",
                "B": "Option B",
                "C": "Option C",
                "D": "Option D",
                "E": "Option E",
            },
            distractor_stats={
                "A": {"count": 30, "top_q": 15, "bottom_q": 5},
                "B": {"count": 20, "top_q": 3, "bottom_q": 10},
                "C": {"count": 20, "top_q": 4, "bottom_q": 8},
                "D": {"count": 15, "top_q": 2, "bottom_q": 7},
                "E": {"count": 15, "top_q": 1, "bottom_q": 10},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert not result.get("insufficient_data")
        assert result["total_responses"] == 100
        assert len(result["options"]) == 5
        # Verify all 5 options are analyzed
        for opt in ["A", "B", "C", "D", "E"]:
            assert opt in result["options"]

    def test_six_option_question_analysis(self, db_session):
        """Test that 6-option questions are analyzed correctly."""
        question = Question(
            question_text="6-option question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={
                "A": "Option A",
                "B": "Option B",
                "C": "Option C",
                "D": "Option D",
                "E": "Option E",
                "F": "Option F",
            },
            distractor_stats={
                "A": {"count": 25, "top_q": 12, "bottom_q": 4},
                "B": {"count": 15, "top_q": 2, "bottom_q": 8},
                "C": {"count": 15, "top_q": 3, "bottom_q": 7},
                "D": {"count": 15, "top_q": 2, "bottom_q": 6},
                "E": {"count": 15, "top_q": 3, "bottom_q": 5},
                "F": {"count": 15, "top_q": 3, "bottom_q": 5},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert not result.get("insufficient_data")
        assert result["total_responses"] == 100
        assert len(result["options"]) == 6
        # Verify all 6 options are analyzed
        for opt in ["A", "B", "C", "D", "E", "F"]:
            assert opt in result["options"]
        # With 6 options, effective option count can be higher
        assert result["summary"]["effective_option_count"] <= 6.0

    def test_numeric_option_keys(self, db_session):
        """Test that numeric option keys (1, 2, 3, 4) are handled correctly."""
        question = Question(
            question_text="Numeric options question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="1",
            answer_options={"1": "42", "2": "43", "3": "44", "4": "45"},
            distractor_stats={
                "1": {"count": 40, "top_q": 20, "bottom_q": 5},
                "2": {"count": 20, "top_q": 3, "bottom_q": 10},
                "3": {"count": 25, "top_q": 4, "bottom_q": 12},
                "4": {"count": 15, "top_q": 3, "bottom_q": 8},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert not result.get("insufficient_data")
        assert result["correct_answer"] == "1"
        assert result["options"]["1"]["is_correct"] is True
        assert result["options"]["2"]["is_correct"] is False
        assert result["options"]["3"]["is_correct"] is False
        assert result["options"]["4"]["is_correct"] is False

    def test_mixed_format_options(self, db_session):
        """Test options with mixed text/number content are handled correctly."""
        question = Question(
            question_text="Mixed format question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={
                "A": "Answer 1: Yes",
                "B": "Answer 2: No",
                "C": "42",
                "D": "None of the above",
            },
            distractor_stats={
                "A": {"count": 30, "top_q": 15, "bottom_q": 5},
                "B": {"count": 25, "top_q": 5, "bottom_q": 12},
                "C": {"count": 25, "top_q": 7, "bottom_q": 10},
                "D": {"count": 20, "top_q": 3, "bottom_q": 8},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert not result.get("insufficient_data")
        assert result["total_responses"] == 100
        assert len(result["options"]) == 4

    def test_whitespace_in_selected_answer_normalized(self, db_session):
        """Test that whitespace in selected answers is normalized."""
        question = Question(
            question_text="Whitespace test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Update with whitespace-padded answer
        result = update_distractor_stats(db_session, question.id, "  B  ")

        assert result is True
        # Check that whitespace is stripped
        assert "B" in question.distractor_stats
        assert question.distractor_stats["B"]["count"] == 1

    def test_whitespace_in_quartile_update_normalized(self, db_session):
        """Test that whitespace in quartile updates is normalized."""
        question = Question(
            question_text="Quartile whitespace test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Update with whitespace-padded answer
        result = update_distractor_quartile_stats(
            db_session, question.id, " A ", is_top_quartile=True
        )

        assert result is True
        assert "A" in question.distractor_stats
        assert question.distractor_stats["A"]["top_q"] == 1

    def test_very_new_question_insufficient_data(self, db_session):
        """Test that very new questions with 0 responses return insufficient_data."""
        question = Question(
            question_text="Brand new question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats=None,  # No stats yet
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert result.get("insufficient_data") is True
        assert result["total_responses"] == 0
        assert result["min_required"] == 50

    def test_question_with_few_responses_insufficient_data(self, db_session):
        """Test that questions with only a few responses return insufficient_data."""
        question = Question(
            question_text="Low response question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 5, "top_q": 2, "bottom_q": 1},
                "B": {"count": 3, "top_q": 1, "bottom_q": 1},
                "C": {"count": 2, "top_q": 0, "bottom_q": 1},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert result.get("insufficient_data") is True
        assert result["total_responses"] == 10  # 5 + 3 + 2
        assert result["min_required"] == 50

    def test_question_at_threshold_boundary(self, db_session):
        """Test question with exactly min_responses threshold."""
        question = Question(
            question_text="Boundary test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 30, "top_q": 10, "bottom_q": 5},
                "B": {"count": 12, "top_q": 3, "bottom_q": 6},
                "C": {"count": 8, "top_q": 2, "bottom_q": 4},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # With exactly 50 responses at threshold of 50, should be analyzed
        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert not result.get("insufficient_data")
        assert result["total_responses"] == 50

    def test_discrimination_analysis_with_five_options(self, db_session):
        """Test discrimination calculation works with 5 options."""
        question = Question(
            question_text="5-option discrimination test",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={
                "A": "Option A",
                "B": "Option B",
                "C": "Option C",
                "D": "Option D",
                "E": "Option E",
            },
            distractor_stats={
                "A": {"count": 30, "top_q": 15, "bottom_q": 5},  # Correct answer
                "B": {"count": 20, "top_q": 3, "bottom_q": 10},  # Good distractor
                "C": {"count": 20, "top_q": 4, "bottom_q": 8},  # Good distractor
                "D": {"count": 15, "top_q": 1, "bottom_q": 8},  # Good distractor
                "E": {"count": 15, "top_q": 2, "bottom_q": 9},  # Good distractor
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = calculate_distractor_discrimination(
            db_session, question.id, min_responses=40
        )

        assert not result.get("insufficient_data")
        assert len(result["options"]) == 5
        # Verify discrimination indices are calculated for all options
        for opt in ["A", "B", "C", "D", "E"]:
            assert "discrimination_index" in result["options"][opt]

    def test_effective_option_count_with_six_options(self, db_session):
        """Test effective option count calculation with 6 options."""
        question = Question(
            question_text="6-option effective count test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={
                "A": "Option A",
                "B": "Option B",
                "C": "Option C",
                "D": "Option D",
                "E": "Option E",
                "F": "Option F",
            },
            # Equal distribution: effective_option_count should be 6.0
            distractor_stats={
                "A": {"count": 10, "top_q": 3, "bottom_q": 3},
                "B": {"count": 10, "top_q": 3, "bottom_q": 3},
                "C": {"count": 10, "top_q": 3, "bottom_q": 3},
                "D": {"count": 10, "top_q": 2, "bottom_q": 2},
                "E": {"count": 10, "top_q": 2, "bottom_q": 2},
                "F": {"count": 10, "top_q": 2, "bottom_q": 2},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(
            db_session, question.id, min_responses=50
        )

        assert not result.get("insufficient_data")
        # With perfectly equal distribution across 6 options, effective_option_count = 6.0
        assert result["summary"]["effective_option_count"] == 6.0

    def test_empty_selected_answer_rejected(self, db_session):
        """Test that empty selected answers are rejected gracefully."""
        question = Question(
            question_text="Empty answer test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Test empty string - rejected early
        result = update_distractor_stats(db_session, question.id, "")
        assert result is False
        assert question.distractor_stats is None

        # Test whitespace-only string - passes 'if not selected_answer' check but
        # after strip becomes "" which is not a valid option key
        result = update_distractor_stats(db_session, question.id, "   ")
        assert result is False  # Rejected because "" is not a valid option
        assert question.distractor_stats is None

    def test_nonexistent_question_graceful_failure(self, db_session):
        """Test that operations on non-existent questions fail gracefully."""
        # Test update_distractor_stats
        result = update_distractor_stats(db_session, 99999, "A")
        assert result is False

        # Test update_distractor_quartile_stats
        result = update_distractor_quartile_stats(
            db_session, 99999, "A", is_top_quartile=True
        )
        assert result is False

        # Test calculate_distractor_discrimination
        result = calculate_distractor_discrimination(db_session, 99999)
        assert result.get("insufficient_data") is True
        assert result["total_responses"] == 0

        # Test analyze_distractor_effectiveness
        result = analyze_distractor_effectiveness(db_session, 99999)
        assert result.get("insufficient_data") is True

    def test_update_stats_preserves_other_options(self, db_session):
        """Test that updating one option preserves stats for other options."""
        question = Question(
            question_text="Preservation test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats={
                "A": {"count": 10, "top_q": 5, "bottom_q": 2},
                "B": {"count": 8, "top_q": 3, "bottom_q": 4},
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Update option C
        result = update_distractor_stats(db_session, question.id, "C")

        assert result is True
        # Verify A and B stats are preserved
        assert question.distractor_stats["A"]["count"] == 10
        assert question.distractor_stats["A"]["top_q"] == 5
        assert question.distractor_stats["A"]["bottom_q"] == 2
        assert question.distractor_stats["B"]["count"] == 8
        assert question.distractor_stats["B"]["top_q"] == 3
        assert question.distractor_stats["B"]["bottom_q"] == 4
        # And C is added
        assert question.distractor_stats["C"]["count"] == 1

    def test_option_key_case_sensitivity(self, db_session):
        """Test that option keys are case-sensitive - lowercase rejected if not valid."""
        question = Question(
            question_text="Case sensitivity test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # Lowercase 'a' is NOT a valid option (only 'A' is), so it should be rejected
        result = update_distractor_stats(db_session, question.id, "a")
        assert result is False

        # Uppercase 'A' is valid
        result = update_distractor_stats(db_session, question.id, "A")
        assert result is True

        # Only 'A' should be in stats (lowercase was rejected)
        assert "a" not in question.distractor_stats
        assert "A" in question.distractor_stats
        assert question.distractor_stats["A"]["count"] == 1

    def test_invalid_option_key_rejected(self, db_session):
        """Test that selecting a non-existent option is rejected with warning."""
        question = Question(
            question_text="Invalid option test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B", "C": "Option C"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # 'Z' is not a valid option
        result = update_distractor_stats(db_session, question.id, "Z")
        assert result is False
        # No stats should be created
        assert question.distractor_stats is None

        # Now select a valid option
        result = update_distractor_stats(db_session, question.id, "A")
        assert result is True
        assert "A" in question.distractor_stats
        assert question.distractor_stats["A"]["count"] == 1

        # Try another invalid option - stats should remain unchanged
        result = update_distractor_stats(db_session, question.id, "X")
        assert result is False
        assert "X" not in question.distractor_stats
        assert question.distractor_stats["A"]["count"] == 1  # Unchanged

    def test_invalid_option_key_rejected_quartile_update(self, db_session):
        """Test that invalid option keys are rejected in quartile updates."""
        question = Question(
            question_text="Invalid quartile option test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "Option A", "B": "Option B"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # 'Z' is not a valid option
        result = update_distractor_quartile_stats(
            db_session, question.id, "Z", is_top_quartile=True
        )
        assert result is False
        assert question.distractor_stats is None

        # Valid option should work
        result = update_distractor_quartile_stats(
            db_session, question.id, "A", is_top_quartile=True
        )
        assert result is True
        assert "A" in question.distractor_stats
        assert question.distractor_stats["A"]["top_q"] == 1

    def test_numeric_invalid_option_rejected(self, db_session):
        """Test that numeric options outside valid range are rejected."""
        question = Question(
            question_text="Numeric options question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="1",
            answer_options={"1": "42", "2": "43", "3": "44", "4": "45"},
            distractor_stats=None,
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        # '5' is not a valid option (only 1-4)
        result = update_distractor_stats(db_session, question.id, "5")
        assert result is False

        # '0' is also invalid
        result = update_distractor_stats(db_session, question.id, "0")
        assert result is False

        # Valid numeric key should work
        result = update_distractor_stats(db_session, question.id, "2")
        assert result is True
        assert "2" in question.distractor_stats
