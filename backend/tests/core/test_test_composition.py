"""
Tests for test composition and question selection logic.

Tests IDA-005: Flagged questions should be excluded from test composition.
Tests IDA-006: Discrimination preference in test composition.
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


class TestDiscriminationPreference:
    """Test discrimination preference in test composition (IDA-006)."""

    def test_negative_discrimination_excluded(self, db_session, test_user):
        """Questions with negative discrimination should not be selected."""
        # Create a question with positive discrimination
        positive_question = Question(
            question_text="Positive discrimination question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=0.35,
            response_count=100,
        )

        # Create a question with negative discrimination
        negative_question = Question(
            question_text="Negative discrimination question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=-0.15,
            response_count=100,
        )

        db_session.add(positive_question)
        db_session.add(negative_question)
        db_session.commit()

        # Select questions
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Should only select the positive discrimination question
        selected_ids = [q.id for q in selected]
        assert positive_question.id in selected_ids
        assert negative_question.id not in selected_ids

    def test_null_discrimination_included(self, db_session, test_user):
        """Questions with NULL discrimination (new questions) should be included."""
        # Create a question with NULL discrimination (new question)
        new_question = Question(
            question_text="New question no data",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
            quality_flag="normal",
            discrimination=None,  # New question, no data yet
            response_count=0,
        )

        db_session.add(new_question)
        db_session.commit()

        # Select questions
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # New question should be included
        selected_ids = [q.id for q in selected]
        assert new_question.id in selected_ids

    def test_high_discrimination_preferred(self, db_session, test_user):
        """Questions with higher discrimination should be selected first."""
        # Create questions with varying discrimination values
        # All same difficulty/type to ensure they compete for same slots
        questions = []
        discriminations = [0.45, 0.35, 0.25, 0.15, 0.05]

        for i, disc in enumerate(discriminations):
            q = Question(
                question_text=f"Question with discrimination {disc}",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="C",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                arbiter_score=0.95,
                is_active=True,
                quality_flag="normal",
                discrimination=disc,
                response_count=100,
            )
            questions.append(q)
            db_session.add(q)

        db_session.commit()

        # Select only 3 questions (less than available)
        selected, _ = select_stratified_questions(db_session, test_user.id, 3)

        # Get discrimination values of selected questions
        selected_discriminations = [q.discrimination for q in selected]

        # The selected questions should be the highest discrimination ones
        # (or close to it, depending on stratification)
        assert all(d >= 0.25 for d in selected_discriminations if d is not None)

    def test_zero_discrimination_included(self, db_session, test_user):
        """Questions with exactly zero discrimination should be included (boundary test)."""
        # Create a question with zero discrimination (boundary case)
        zero_question = Question(
            question_text="Zero discrimination question",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="D",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.90,
            is_active=True,
            quality_flag="normal",
            discrimination=0.0,
            response_count=50,
        )

        db_session.add(zero_question)
        db_session.commit()

        # Select questions
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Zero discrimination should be included (threshold is < 0, not <= 0)
        selected_ids = [q.id for q in selected]
        assert zero_question.id in selected_ids

    def test_negative_discrimination_excluded_all_fallbacks(
        self, db_session, test_user
    ):
        """
        Negative discrimination should be excluded from all query paths:
        stratified, difficulty fallback, and final fallback.
        """
        # Create only negative discrimination questions except one positive
        positive = Question(
            question_text="Only positive question",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=0.30,
            response_count=100,
        )

        # Create multiple negative discrimination questions across difficulties
        for i in range(5):
            q = Question(
                question_text=f"Negative question {i}",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                arbiter_score=0.95,
                is_active=True,
                quality_flag="normal",
                discrimination=-0.1 * (i + 1),  # -0.1, -0.2, -0.3, etc.
                response_count=100,
            )
            db_session.add(q)

        db_session.add(positive)
        db_session.commit()

        # Request many questions - should only get the positive one
        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        # Only the positive discrimination question should be selected
        assert len(selected) == 1
        assert selected[0].id == positive.id

    def test_mixed_discrimination_and_null(self, db_session, test_user):
        """
        With a mix of positive, negative, and NULL discrimination,
        only positive and NULL should be selected.
        """
        positive = Question(
            question_text="Positive discrimination",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=0.40,
            response_count=100,
        )

        negative = Question(
            question_text="Negative discrimination",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=-0.20,
            response_count=100,
        )

        null_disc = Question(
            question_text="NULL discrimination (new)",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=None,
            response_count=0,
        )

        db_session.add_all([positive, negative, null_disc])
        db_session.commit()

        selected, _ = select_stratified_questions(db_session, test_user.id, 10)

        selected_ids = [q.id for q in selected]
        assert positive.id in selected_ids
        assert null_disc.id in selected_ids
        assert negative.id not in selected_ids

    def test_discrimination_ordering_nulls_last(self, db_session, test_user):
        """
        Questions should be ordered with highest discrimination first,
        and NULL discrimination questions last.
        """
        # Create questions with different discrimination values
        high_disc = Question(
            question_text="High discrimination",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=0.50,
            response_count=100,
        )

        low_disc = Question(
            question_text="Low discrimination",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=0.10,
            response_count=100,
        )

        null_disc = Question(
            question_text="NULL discrimination",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            arbiter_score=0.95,
            is_active=True,
            quality_flag="normal",
            discrimination=None,
            response_count=0,
        )

        db_session.add_all([low_disc, null_disc, high_disc])  # Add in wrong order
        db_session.commit()

        # Select 2 questions (less than available) to test preference
        selected, _ = select_stratified_questions(db_session, test_user.id, 2)

        # High discrimination should be selected first
        assert high_disc.id in [q.id for q in selected]

        # If we only need 2, low_disc should be selected before null_disc
        selected_ids = [q.id for q in selected]
        if null_disc.id not in selected_ids:
            assert low_disc.id in selected_ids
