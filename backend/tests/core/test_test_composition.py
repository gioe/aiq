"""
Tests for test composition and question selection logic.

Tests IDA-005: Flagged questions should be excluded from test composition.
Tests IDA-006: Discrimination preference in test composition.
"""
import pytest
from app.models import Question
from app.models.models import QuestionType, DifficultyLevel
from app.core.scoring.test_composition import select_stratified_questions


class TestDifficultyDistribution:
    """Test that difficulty distribution produces expected question counts."""

    def test_25_question_distribution(self, db_session, test_user):
        """For 25 questions, distribution should be 5 easy, 13 medium, 7 hard with weighted domains."""
        # Create enough questions across all difficulties and types
        question_types = list(QuestionType)
        for difficulty in DifficultyLevel:
            for i, qt in enumerate(question_types):
                for j in range(10):  # 10 per type per difficulty for sufficient pool
                    q = Question(
                        question_text=f"Q-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.95,
                        is_active=True,
                        quality_flag="normal",
                    )
                    db_session.add(q)
        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        assert len(selected) == 25

        # Verify difficulty counts from metadata
        easy_count = metadata["difficulty"].get("easy", 0)
        medium_count = metadata["difficulty"].get("medium", 0)
        hard_count = metadata["difficulty"].get("hard", 0)

        # 25 * 0.20 = 5.0 -> 5 easy
        assert easy_count == 5
        # 25 * 0.30 = 7.5 -> 7 hard
        assert hard_count == 7
        # 25 * 0.50 = 12.5 -> 12, plus 1 rounding adjustment = 13 medium
        assert medium_count == 13
        assert easy_count + medium_count + hard_count == 25

        # Verify domain distribution matches weights within tolerance
        domain_counts = metadata["domain"]

        # Expected counts based on weights (25 questions total):
        # pattern: 25 * 0.22 = 5.5 -> 5 or 6
        # logic: 25 * 0.20 = 5.0 -> 5
        # verbal: 25 * 0.19 = 4.75 -> 4 or 5
        # spatial: 25 * 0.16 = 4.0 -> 4
        # math: 25 * 0.13 = 3.25 -> 3 or 4
        # memory: 25 * 0.10 = 2.5 -> 2 or 3

        pattern_count = domain_counts.get("pattern", 0)
        logic_count = domain_counts.get("logic", 0)
        verbal_count = domain_counts.get("verbal", 0)
        spatial_count = domain_counts.get("spatial", 0)
        math_count = domain_counts.get("math", 0)
        memory_count = domain_counts.get("memory", 0)

        # Allow +/-1 tolerance per domain due to rounding
        assert 5 <= pattern_count <= 6, f"Pattern count {pattern_count} not in [5, 6]"
        assert 4 <= logic_count <= 6, f"Logic count {logic_count} not in [4, 6]"
        assert 4 <= verbal_count <= 5, f"Verbal count {verbal_count} not in [4, 5]"
        assert 3 <= spatial_count <= 5, f"Spatial count {spatial_count} not in [3, 5]"
        assert 2 <= math_count <= 4, f"Math count {math_count} not in [2, 4]"
        assert 2 <= memory_count <= 3, f"Memory count {memory_count} not in [2, 3]"

        # Total must equal 25
        total_domain = sum(domain_counts.values())
        assert total_domain == 25


class TestWeightedDomainDistribution:
    """Test that domain distribution follows configured weights."""

    def test_weighted_allocation_25_questions(self, db_session, test_user):
        """
        Verify weighted domain allocation for 25 questions.

        Expected distribution based on TEST_DOMAIN_WEIGHTS:
        - Easy (5): pattern=1, logic=1, verbal=1, spatial=1, math=1, memory=0
        - Medium (13): pattern=3, logic=3, verbal=2, spatial=2, math=2, memory=1
        - Hard (7): pattern=2, logic=1, verbal=1, spatial=1, math=1, memory=1
        Total: pattern=6, logic=5, verbal=4, spatial=4, math=4, memory=2

        Note: Exact distribution may vary due to largest-remainder rounding,
        but should be within +/-1 per domain.
        """
        # Create sufficient questions across all difficulties and types
        question_types = list(QuestionType)
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(15):  # Ample pool
                    q = Question(
                        question_text=f"Q-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.95,
                        is_active=True,
                        quality_flag="normal",
                    )
                    db_session.add(q)
        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        assert len(selected) == 25

        # Verify total equals target
        domain_counts = metadata["domain"]
        total_domain = sum(domain_counts.values())
        assert total_domain == 25, f"Total domain count {total_domain} != 25"

        # Verify distribution matches weights within tolerance
        # Using largest-remainder method, expected approximate counts:
        # pattern: 25 * 0.22 = 5.5 -> likely 5 or 6
        # logic: 25 * 0.20 = 5.0 -> 5
        # verbal: 25 * 0.19 = 4.75 -> likely 4 or 5
        # spatial: 25 * 0.16 = 4.0 -> 4
        # math: 25 * 0.13 = 3.25 -> likely 3
        # memory: 25 * 0.10 = 2.5 -> likely 2 or 3

        pattern_count = domain_counts.get("pattern", 0)
        logic_count = domain_counts.get("logic", 0)
        verbal_count = domain_counts.get("verbal", 0)
        spatial_count = domain_counts.get("spatial", 0)
        math_count = domain_counts.get("math", 0)
        memory_count = domain_counts.get("memory", 0)

        # Pattern has highest weight (0.22) - should get 5-6 questions
        assert 5 <= pattern_count <= 6, f"Pattern: expected [5,6], got {pattern_count}"

        # Logic (0.20) - should get 4-5 questions
        assert 4 <= logic_count <= 6, f"Logic: expected [4,6], got {logic_count}"

        # Verbal (0.19) - should get 4-5 questions
        assert 4 <= verbal_count <= 5, f"Verbal: expected [4,5], got {verbal_count}"

        # Spatial (0.16) - should get 3-4 questions
        assert 3 <= spatial_count <= 5, f"Spatial: expected [3,5], got {spatial_count}"

        # Math (0.13) - should get 3-4 questions
        assert 2 <= math_count <= 4, f"Math: expected [2,4], got {math_count}"

        # Memory has lowest weight (0.10) - should get 2-3 questions
        assert 2 <= memory_count <= 3, f"Memory: expected [2,3], got {memory_count}"

    def test_weighted_allocation_preserves_total(self, db_session, test_user):
        """Verify weighted allocation always produces exactly the requested total."""
        # Create sufficient questions
        question_types = list(QuestionType)
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(20):
                    q = Question(
                        question_text=f"Q-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.95,
                        is_active=True,
                        quality_flag="normal",
                    )
                    db_session.add(q)
        db_session.commit()

        # Test various totals
        for total in [10, 15, 20, 25, 30]:
            selected, metadata = select_stratified_questions(
                db_session, test_user.id, total
            )
            assert len(selected) == total
            assert metadata["total"] == total
            # Domain counts must sum to total
            domain_total = sum(metadata["domain"].values())
            assert (
                domain_total == total
            ), f"For total={total}, domain counts sum to {domain_total}"

    def test_weighted_allocation_respects_difficulty_splits(
        self, db_session, test_user
    ):
        """
        Verify that weighted allocation is applied within each difficulty level,
        not globally, so difficulty distribution is preserved.
        """
        # Create sufficient questions
        question_types = list(QuestionType)
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(15):
                    q = Question(
                        question_text=f"Q-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.95,
                        is_active=True,
                        quality_flag="normal",
                    )
                    db_session.add(q)
        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Verify difficulty distribution (20/50/30)
        assert metadata["difficulty"]["easy"] == 5
        assert metadata["difficulty"]["medium"] == 13
        assert metadata["difficulty"]["hard"] == 7

        # Now manually verify that questions are distributed across domains
        # within each difficulty level
        from collections import Counter

        easy_questions = [q for q in selected if q.difficulty_level.value == "easy"]
        medium_questions = [q for q in selected if q.difficulty_level.value == "medium"]
        hard_questions = [q for q in selected if q.difficulty_level.value == "hard"]

        easy_domains = Counter(q.question_type.value for q in easy_questions)
        medium_domains = Counter(q.question_type.value for q in medium_questions)
        hard_domains = Counter(q.question_type.value for q in hard_questions)

        # Each difficulty level should have diversity across domains
        # (at least 3 different domains represented in each difficulty)
        assert len(easy_domains) >= 3, f"Easy: {easy_domains}"
        assert len(medium_domains) >= 5, f"Medium: {medium_domains}"
        assert len(hard_domains) >= 4, f"Hard: {hard_domains}"


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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.90,
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
            judge_score=0.90,
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
                judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
                judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.90,
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
                judge_score=0.95,
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
            judge_score=0.90,
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
            judge_score=0.95,
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
                judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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
            judge_score=0.95,
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


class TestAnchorItemInclusion:
    """Test anchor item inclusion in test composition (TASK-850)."""

    def test_anchor_items_included_in_every_domain(self, db_session, test_user):
        """When anchors exist for all domains, each domain gets at least 1."""
        question_types = list(QuestionType)

        # Create 1 anchor item per domain (6 total)
        for qt in question_types:
            anchor = Question(
                question_text=f"Anchor-{qt.value}",
                question_type=qt,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                judge_score=0.95,
                is_active=True,
                quality_flag="normal",
                is_anchor=True,
                discrimination=0.35,
            )
            db_session.add(anchor)

        # Create regular questions to fill the rest
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(10):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Verify total count
        assert len(selected) == 25

        # Verify anchor metadata
        assert "anchor_count" in metadata
        assert "anchors_per_domain" in metadata
        assert metadata["anchor_count"] == 6

        # Verify each domain has at least 1 anchor
        for qt in question_types:
            assert metadata["anchors_per_domain"][qt.value] == 1

        # Verify anchor questions are in the selected list
        anchor_questions = [q for q in selected if q.is_anchor]
        assert len(anchor_questions) == 6

        # Verify each domain is represented in anchors
        anchor_types = {q.question_type for q in anchor_questions}
        assert len(anchor_types) == 6

    def test_anchor_items_count_toward_domain_quota(self, db_session, test_user):
        """Anchor items count toward domain quota - total stays at total_count."""
        question_types = list(QuestionType)

        # Create 1 anchor item per domain
        for qt in question_types:
            anchor = Question(
                question_text=f"Anchor-{qt.value}",
                question_type=qt,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                judge_score=0.95,
                is_active=True,
                quality_flag="normal",
                is_anchor=True,
                discrimination=0.40,
            )
            db_session.add(anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(15):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Total should be exactly 25 (not 25 + 6 anchors)
        assert len(selected) == 25
        assert metadata["total"] == 25

        # Anchors are included in the total
        assert metadata["anchor_count"] == 6

    def test_fallback_when_all_anchors_seen(self, db_session, test_user):
        """When user has seen all anchors for a domain, test still works."""
        from app.models import UserQuestion

        question_types = list(QuestionType)

        # Create 1 anchor per domain
        anchors = []
        for qt in question_types:
            anchor = Question(
                question_text=f"Anchor-{qt.value}",
                question_type=qt,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                judge_score=0.95,
                is_active=True,
                quality_flag="normal",
                is_anchor=True,
                discrimination=0.35,
            )
            db_session.add(anchor)
            anchors.append(anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(10):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        # Mark all anchors as seen by the user
        for anchor in anchors:
            uq = UserQuestion(
                user_id=test_user.id,
                question_id=anchor.id,
            )
            db_session.add(uq)
        db_session.commit()

        # Should still work - no anchors but test proceeds
        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        assert len(selected) == 25
        assert metadata["anchor_count"] == 0

        # No anchors should be selected (all were seen)
        anchor_questions = [q for q in selected if q.is_anchor]
        assert len(anchor_questions) == 0

    def test_fallback_when_no_anchors_exist(self, db_session, test_user):
        """When no anchors exist at all, test still works normally."""
        question_types = list(QuestionType)

        # Create only regular questions (no anchors)
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(10):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        assert len(selected) == 25
        assert metadata["anchor_count"] == 0

        # Verify all domains have 0 anchors
        for qt in question_types:
            assert metadata["anchors_per_domain"][qt.value] == 0

    def test_anchor_metadata_in_composition(self, db_session, test_user):
        """Metadata includes anchor_count and anchors_per_domain info."""
        question_types = list(QuestionType)

        # Create varying numbers of anchors per domain
        # pattern: 1, logic: 1, verbal: 1, spatial: 0, math: 0, memory: 0
        for qt in [QuestionType.PATTERN, QuestionType.LOGIC, QuestionType.VERBAL]:
            anchor = Question(
                question_text=f"Anchor-{qt.value}",
                question_type=qt,
                difficulty_level=DifficultyLevel.HARD,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                judge_score=0.95,
                is_active=True,
                quality_flag="normal",
                is_anchor=True,
                discrimination=0.38,
            )
            db_session.add(anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(10):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Verify metadata structure
        assert "anchor_count" in metadata
        assert "anchors_per_domain" in metadata

        # Verify anchor count
        assert metadata["anchor_count"] == 3

        # Verify per-domain breakdown
        assert metadata["anchors_per_domain"]["pattern"] == 1
        assert metadata["anchors_per_domain"]["logic"] == 1
        assert metadata["anchors_per_domain"]["verbal"] == 1
        assert metadata["anchors_per_domain"]["spatial"] == 0
        assert metadata["anchors_per_domain"]["math"] == 0
        assert metadata["anchors_per_domain"]["memory"] == 0

    def test_anchor_items_respect_quality_filters(self, db_session, test_user):
        """Inactive/flagged anchors are excluded from selection."""
        question_types = list(QuestionType)

        # Create inactive anchor
        inactive_anchor = Question(
            question_text="Inactive anchor",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=False,  # Inactive
            quality_flag="normal",
            is_anchor=True,
            discrimination=0.40,
        )
        db_session.add(inactive_anchor)

        # Create flagged anchor
        flagged_anchor = Question(
            question_text="Flagged anchor",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            quality_flag="under_review",  # Flagged
            is_anchor=True,
            discrimination=0.35,
        )
        db_session.add(flagged_anchor)

        # Create valid anchor
        valid_anchor = Question(
            question_text="Valid anchor",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            quality_flag="normal",
            is_anchor=True,
            discrimination=0.42,
        )
        db_session.add(valid_anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(10):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Only 1 anchor should be selected (the valid one)
        assert metadata["anchor_count"] == 1

        # Verify the valid anchor is in selection
        selected_ids = [q.id for q in selected]
        assert valid_anchor.id in selected_ids
        assert inactive_anchor.id not in selected_ids
        assert flagged_anchor.id not in selected_ids

    def test_anchor_items_respect_discrimination_filter(self, db_session, test_user):
        """Negative discrimination anchors are excluded from selection."""
        question_types = list(QuestionType)

        # Create anchor with negative discrimination
        negative_anchor = Question(
            question_text="Negative discrimination anchor",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            quality_flag="normal",
            is_anchor=True,
            discrimination=-0.15,  # Negative
            response_count=100,
        )
        db_session.add(negative_anchor)

        # Create anchor with positive discrimination
        positive_anchor = Question(
            question_text="Positive discrimination anchor",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            quality_flag="normal",
            is_anchor=True,
            discrimination=0.38,
            response_count=100,
        )
        db_session.add(positive_anchor)

        # Create anchor with NULL discrimination (new)
        null_anchor = Question(
            question_text="NULL discrimination anchor",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            quality_flag="normal",
            is_anchor=True,
            discrimination=None,  # NULL (new anchor)
            response_count=0,
        )
        db_session.add(null_anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(10):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Should have 2 anchors (positive and null, but not negative)
        assert metadata["anchor_count"] == 2

        # Verify correct anchors are selected
        selected_ids = [q.id for q in selected]
        assert positive_anchor.id in selected_ids
        assert null_anchor.id in selected_ids
        assert negative_anchor.id not in selected_ids

    @pytest.mark.parametrize("total_count", [10, 15, 20, 25, 30])
    def test_total_count_invariant_with_anchors(
        self, db_session, test_user, total_count
    ):
        """Total count must equal requested count regardless of anchor inclusion."""
        question_types = list(QuestionType)

        # Create 1 anchor per domain at varying difficulties
        difficulties = list(DifficultyLevel)
        for i, qt in enumerate(question_types):
            anchor = Question(
                question_text=f"Anchor-{qt.value}",
                question_type=qt,
                difficulty_level=difficulties[i % len(difficulties)],
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                judge_score=0.95,
                is_active=True,
                quality_flag="normal",
                is_anchor=True,
                discrimination=0.35,
            )
            db_session.add(anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(20):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(
            db_session, test_user.id, total_count
        )

        assert len(selected) == total_count
        assert metadata["total"] == total_count

    def test_total_count_when_anchor_in_zero_allocation_stratum(
        self, db_session, test_user
    ):
        """Total stays correct even when an anchor lands in a stratum with zero allocation.

        Example: MEMORY gets 0 slots in EASY (5 * 0.10 = 0.5, floored to 0).
        An EASY MEMORY anchor must not cause the total to exceed total_count.
        """
        question_types = list(QuestionType)

        # Create an anchor in a stratum that gets 0 allocation (EASY MEMORY)
        anchor = Question(
            question_text="Anchor-memory-easy",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            quality_flag="normal",
            is_anchor=True,
            discrimination=0.40,
        )
        db_session.add(anchor)

        # Create regular questions
        for difficulty in DifficultyLevel:
            for qt in question_types:
                for j in range(15):
                    q = Question(
                        question_text=f"Regular-{difficulty.value}-{qt.value}-{j}",
                        question_type=qt,
                        difficulty_level=difficulty,
                        correct_answer="A",
                        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                        source_llm="test-llm",
                        judge_score=0.90,
                        is_active=True,
                        quality_flag="normal",
                        is_anchor=False,
                    )
                    db_session.add(q)

        db_session.commit()

        selected, metadata = select_stratified_questions(db_session, test_user.id, 25)

        # Total must be exactly 25 — anchor occupies one slot
        assert len(selected) == 25
        assert metadata["total"] == 25

        # Anchor should be in the selection
        assert anchor.id in [q.id for q in selected]
