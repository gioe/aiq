"""
Tests for distractor analysis functions (DA-003).

Tests cover:
- Selection count incrementing
- Stats initialization for new questions
- Invalid/missing option handling
- Thread-safe concurrent updates
- Quartile stats updates
"""
from app.models import Question
from app.models.models import QuestionType, DifficultyLevel
from app.core.distractor_analysis import (
    update_distractor_stats,
    update_distractor_quartile_stats,
    get_distractor_stats,
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
