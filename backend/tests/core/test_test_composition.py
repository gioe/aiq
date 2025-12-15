"""
Tests for test composition and question selection logic.

Tests IDA-005: Flagged questions should be excluded from test composition.
"""
from app.models import Question
from app.models.models import QuestionType, DifficultyLevel
from app.core.test_composition import select_stratified_questions


class TestQualityFlagExclusion:
    """Test that questions with quality_flag != 'normal' are excluded (IDA-005)."""

    def test_under_review_questions_excluded(self, db_session, test_user):
        """Questions with quality_flag='under_review' should not be selected."""
        # Create a normal question
        normal_question = Question(
            question_text="Normal question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
        )

        # Create an under_review question
        flagged_question = Question(
            question_text="Flagged question - under review",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="under_review",
            quality_flag_reason="Negative discrimination: -0.150",
        )

        db_session.add(normal_question)
        db_session.add(flagged_question)
        db_session.commit()

        # Select questions
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Should only select the normal question
        selected_ids = [q.id for q in selected]
        assert normal_question.id in selected_ids
        assert flagged_question.id not in selected_ids

    def test_deactivated_questions_excluded(self, db_session, test_user):
        """Questions with quality_flag='deactivated' should not be selected."""
        # Create a normal question
        normal_question = Question(
            question_text="Normal question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
            quality_flag="normal",
        )

        # Create a deactivated question
        deactivated_question = Question(
            question_text="Deactivated question",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
            quality_flag="deactivated",
            quality_flag_reason="Manual deactivation by admin",
        )

        db_session.add(normal_question)
        db_session.add(deactivated_question)
        db_session.commit()

        # Select questions
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Should only select the normal question
        selected_ids = [q.id for q in selected]
        assert normal_question.id in selected_ids
        assert deactivated_question.id not in selected_ids

    def test_normal_flag_questions_included(self, db_session, test_user):
        """Questions with quality_flag='normal' should be selected."""
        # Create multiple normal questions
        questions = []
        for i in range(5):
            q = Question(
                question_text=f"Normal question {i}",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="C",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                arbiter_score=0.95,
                is_active=True,
                quality_flag="normal",
            )
            questions.append(q)
            db_session.add(q)

        db_session.commit()

        # Select questions
        selected, metadata = select_stratified_questions(db_session, test_user.id, 5)

        # All normal questions should be included
        assert len(selected) == 5
        selected_ids = [q.id for q in selected]
        for q in questions:
            assert q.id in selected_ids

    def test_flagged_excluded_from_difficulty_fallback(self, db_session, test_user):
        """
        Flagged questions should be excluded even from the difficulty-level
        fallback query (when stratified selection can't find enough questions).
        """
        # Create normal question in a domain that won't match stratified selection
        normal_question = Question(
            question_text="Normal fallback question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
        )

        # Create flagged question in same difficulty
        flagged_question = Question(
            question_text="Flagged fallback question",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="under_review",
        )

        db_session.add(normal_question)
        db_session.add(flagged_question)
        db_session.commit()

        # Request more questions than available in strata
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Flagged question should not be in results
        selected_ids = [q.id for q in selected]
        assert flagged_question.id not in selected_ids

    def test_flagged_excluded_from_final_fallback(self, db_session, test_user):
        """
        Flagged questions should be excluded from the final fallback query
        (when not enough questions in any difficulty level).
        """
        # Create only flagged questions except one normal
        normal_question = Question(
            question_text="Only normal question",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="D",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
        )

        # Create multiple flagged questions
        for i in range(5):
            q = Question(
                question_text=f"Flagged question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                arbiter_score=0.95,
                is_active=True,
                quality_flag="deactivated",
            )
            db_session.add(q)

        db_session.add(normal_question)
        db_session.commit()

        # Request many questions - should only get the normal one
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Only the normal question should be selected
        assert len(selected) == 1
        assert selected[0].id == normal_question.id

    def test_mixed_flags_only_normal_selected(self, db_session, test_user):
        """
        With a mix of normal, under_review, and deactivated questions,
        only normal questions should be selected.
        """
        # Create one of each type
        normal = Question(
            question_text="Normal",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
        )

        under_review = Question(
            question_text="Under Review",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="under_review",
        )

        deactivated = Question(
            question_text="Deactivated",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="deactivated",
        )

        db_session.add_all([normal, under_review, deactivated])
        db_session.commit()

        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        selected_ids = [q.id for q in selected]
        assert normal.id in selected_ids
        assert under_review.id not in selected_ids
        assert deactivated.id not in selected_ids
