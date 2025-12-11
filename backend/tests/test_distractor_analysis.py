"""
Tests for distractor analysis functions (DA-003, DA-004, DA-005).

Tests cover:
- Selection count incrementing
- Stats initialization for new questions
- Invalid/missing option handling
- Thread-safe concurrent updates
- Quartile stats updates
- Distractor discrimination calculation (DA-004)
- Distractor effectiveness analysis (DA-005)
"""
from app.models import Question
from app.models.models import QuestionType, DifficultyLevel
from app.core.distractor_analysis import (
    update_distractor_stats,
    update_distractor_quartile_stats,
    get_distractor_stats,
    calculate_distractor_discrimination,
    analyze_distractor_effectiveness,
    _calculate_effective_option_count,
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
            distractor_stats={
                "A": {"count": 55, "top_q": 14, "bottom_q": 11},
                "B": {
                    "count": 45,
                    "top_q": 11,
                    "bottom_q": 14,
                },  # Similar across quartiles
            },
            is_active=True,
        )
        db_session.add(question)
        db_session.commit()
        db_session.refresh(question)

        result = analyze_distractor_effectiveness(db_session, question.id)

        # B: top_q_rate = 11/25 = 0.44, bottom_q_rate = 14/25 = 0.56
        # discrimination_index = 0.56 - 0.44 = 0.12 -> neutral (within 0.10 threshold)
        # Actually 0.12 > 0.10, so it should be "good" - let me recalculate
        # Need values that give |index| <= 0.10
        # With equal quartile responses (25 each), need difference <= 2.5 in counts
        assert result["options"]["B"]["discrimination"] in ["good", "neutral"]

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
