"""
Unit tests for build_response_matrix() (DW-009).

Tests the response matrix builder that creates a users × items matrix
for factor analysis, where:
- Rows represent completed test sessions
- Columns represent questions
- Values are 0 (incorrect) or 1 (correct)

Test Cases:
- Basic matrix building with completed sessions and responses
- Returns None when no completed sessions exist
- Returns None when no responses exist
- Returns None when no questions meet the minimum response threshold
- Filters out incomplete/abandoned sessions (only COMPLETED status)
- Filters out inactive questions
- min_responses_per_question threshold filters questions correctly
- min_questions_per_session threshold filters sessions correctly
- question_domains list contains correct domain values
- session_ids list contains correct session IDs in order
- question_ids list contains correct question IDs in order
- Matrix values are 0 or 1 (binary)
- Matrix dtype is int8 for memory efficiency
- Helper function get_domain_column_indices works correctly
- get_response_matrix_stats computes accurate statistics
"""

import pytest
import numpy as np
from app.models.models import (
    User,
    Question,
    TestSession,
    Response,
    QuestionType,
    DifficultyLevel,
    TestStatus,
)
from app.core.analytics import (
    build_response_matrix,
    ResponseMatrixResult,
    get_domain_column_indices,
    get_response_matrix_stats,
)
from app.core.security import hash_password

# db_session fixture is provided by conftest.py (async)


async def create_user(db_session, email: str = "test@example.com") -> User:
    """Create a test user."""
    user = User(
        email=email,
        password_hash=hash_password("testpassword123"),
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def create_question(
    db_session,
    question_type: QuestionType,
    is_active: bool = True,
) -> Question:
    """Create a test question."""
    question = Question(
        question_text=f"Test {question_type.value} question",
        question_type=question_type,
        difficulty_level=DifficultyLevel.MEDIUM,
        correct_answer="A",
        answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
        source_llm="test-llm",
        judge_score=0.90,
        is_active=is_active,
    )
    db_session.add(question)
    await db_session.commit()
    await db_session.refresh(question)
    return question


async def create_test_session(
    db_session,
    user: User,
    status: TestStatus = TestStatus.COMPLETED,
) -> TestSession:
    """Create a test session."""
    session = TestSession(
        user_id=user.id,
        status=status,
    )
    db_session.add(session)
    await db_session.commit()
    await db_session.refresh(session)
    return session


async def create_response(
    db_session,
    session: TestSession,
    user: User,
    question: Question,
    is_correct: bool,
) -> Response:
    """Create a response."""
    response = Response(
        test_session_id=session.id,
        user_id=user.id,
        question_id=question.id,
        user_answer="A" if is_correct else "B",
        is_correct=is_correct,
    )
    db_session.add(response)
    await db_session.commit()
    await db_session.refresh(response)
    return response


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestBuildResponseMatrixBasic:
    """Basic tests for build_response_matrix function."""

    async def test_builds_matrix_with_valid_data(self, db_session):
        """Successfully builds a response matrix with valid data."""
        # Create 3 users with completed sessions
        users = [create_user(db_session, f"user{i}@test.com") for i in range(3)]
        sessions = [create_test_session(db_session, user) for user in users]

        # Create 2 questions
        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.LOGIC)

        # Each user answers both questions (total 6 responses per question)
        # We need min_responses_per_question=1 for this small dataset
        for i, (user, session) in enumerate(zip(users, sessions)):
            await create_response(
                db_session, session, user, q1, is_correct=(i % 2 == 0)
            )
            await create_response(
                db_session, session, user, q2, is_correct=(i % 2 == 1)
            )

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert isinstance(result, ResponseMatrixResult)
        assert result.n_users == 3
        assert result.n_items == 2

    async def test_matrix_values_are_binary(self, db_session):
        """Matrix contains only 0 and 1 values."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.LOGIC)

        await create_response(db_session, session, user, q1, is_correct=True)
        await create_response(db_session, session, user, q2, is_correct=False)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        # Check all values are 0 or 1
        unique_values = np.unique(result.matrix)
        assert all(v in [0, 1] for v in unique_values)

    async def test_matrix_dtype_is_int8(self, db_session):
        """Matrix uses int8 dtype for memory efficiency."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q = await create_question(db_session, QuestionType.PATTERN)
        await create_response(db_session, session, user, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert result.matrix.dtype == np.int8

    async def test_correct_response_is_1_incorrect_is_0(self, db_session):
        """Correct responses are 1, incorrect are 0."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.LOGIC)

        await create_response(db_session, session, user, q1, is_correct=True)
        await create_response(db_session, session, user, q2, is_correct=False)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        # Find column indices for each question
        q1_idx = result.question_ids.index(q1.id)
        q2_idx = result.question_ids.index(q2.id)

        assert result.matrix[0, q1_idx] == 1  # Correct
        assert result.matrix[0, q2_idx] == 0  # Incorrect


# =============================================================================
# NONE RETURN TESTS
# =============================================================================


class TestBuildResponseMatrixReturnsNone:
    """Tests for when build_response_matrix returns None."""

    async def test_returns_none_when_no_completed_sessions(self, db_session):
        """Returns None when no completed sessions exist."""
        user = await create_user(db_session)
        # Create in_progress session instead of completed
        await create_test_session(db_session, user, status=TestStatus.IN_PROGRESS)

        result = await build_response_matrix(db_session)

        assert result is None

    async def test_returns_none_when_no_responses(self, db_session):
        """Returns None when no responses exist."""
        user = await create_user(db_session)
        await create_test_session(db_session, user, status=TestStatus.COMPLETED)
        # No responses created

        result = await build_response_matrix(db_session)

        assert result is None

    async def test_returns_none_when_questions_below_threshold(self, db_session):
        """Returns None when no questions meet min_responses_per_question."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q = await create_question(db_session, QuestionType.PATTERN)
        await create_response(db_session, session, user, q, is_correct=True)

        # Only 1 response, but requiring 100
        result = await build_response_matrix(db_session, min_responses_per_question=100)

        assert result is None

    async def test_returns_none_when_all_questions_inactive(self, db_session):
        """Returns None when all questions with responses are inactive."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q = await create_question(db_session, QuestionType.PATTERN, is_active=False)
        await create_response(db_session, session, user, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
        )

        assert result is None

    async def test_returns_none_when_sessions_below_question_threshold(
        self, db_session
    ):
        """Returns None when no sessions meet min_questions_per_session."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q = await create_question(db_session, QuestionType.PATTERN)
        await create_response(db_session, session, user, q, is_correct=True)

        # Only 1 question answered, but requiring 10
        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=10,
        )

        assert result is None


# =============================================================================
# FILTERING TESTS
# =============================================================================


class TestBuildResponseMatrixFiltering:
    """Tests for filtering behavior."""

    async def test_filters_incomplete_sessions(self, db_session):
        """Only includes COMPLETED sessions, not IN_PROGRESS or ABANDONED."""
        user1 = await create_user(db_session, "user1@test.com")
        user2 = await create_user(db_session, "user2@test.com")
        user3 = await create_user(db_session, "user3@test.com")

        s_completed = await create_test_session(db_session, user1, TestStatus.COMPLETED)
        s_in_progress = await create_test_session(
            db_session, user2, TestStatus.IN_PROGRESS
        )
        s_abandoned = await create_test_session(db_session, user3, TestStatus.ABANDONED)

        q = await create_question(db_session, QuestionType.PATTERN)

        await create_response(db_session, s_completed, user1, q, is_correct=True)
        await create_response(db_session, s_in_progress, user2, q, is_correct=True)
        await create_response(db_session, s_abandoned, user3, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert result.n_users == 1
        assert s_completed.id in result.session_ids
        assert s_in_progress.id not in result.session_ids
        assert s_abandoned.id not in result.session_ids

    async def test_filters_inactive_questions(self, db_session):
        """Only includes active questions."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        q_active = await create_question(
            db_session, QuestionType.PATTERN, is_active=True
        )
        q_inactive = await create_question(
            db_session, QuestionType.LOGIC, is_active=False
        )

        await create_response(db_session, session, user, q_active, is_correct=True)
        await create_response(db_session, session, user, q_inactive, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert q_active.id in result.question_ids
        assert q_inactive.id not in result.question_ids

    async def test_min_responses_per_question_threshold(self, db_session):
        """Questions below min_responses_per_question are excluded."""
        users = [create_user(db_session, f"user{i}@test.com") for i in range(5)]
        sessions = [create_test_session(db_session, user) for user in users]

        q_many = await create_question(db_session, QuestionType.PATTERN)
        q_few = await create_question(db_session, QuestionType.LOGIC)

        # q_many gets 5 responses, q_few gets only 2
        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q_many, is_correct=True)

        for user, session in zip(users[:2], sessions[:2]):
            await create_response(db_session, session, user, q_few, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=3,  # q_few has only 2
            min_questions_per_session=1,
        )

        assert result is not None
        assert q_many.id in result.question_ids
        assert q_few.id not in result.question_ids

    async def test_min_questions_per_session_threshold(self, db_session):
        """Sessions below min_questions_per_session are excluded."""
        user1 = await create_user(db_session, "user1@test.com")
        user2 = await create_user(db_session, "user2@test.com")

        s1 = await create_test_session(db_session, user1)
        s2 = await create_test_session(db_session, user2)

        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.LOGIC)

        # s1 answers 2 questions
        await create_response(db_session, s1, user1, q1, is_correct=True)
        await create_response(db_session, s1, user1, q2, is_correct=True)

        # s2 answers only 1 question
        await create_response(db_session, s2, user2, q1, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=2,  # s2 has only 1
        )

        assert result is not None
        assert s1.id in result.session_ids
        assert s2.id not in result.session_ids


# =============================================================================
# METADATA TESTS
# =============================================================================


class TestBuildResponseMatrixMetadata:
    """Tests for metadata correctness."""

    async def test_question_ids_in_correct_order(self, db_session):
        """question_ids list is in the same order as matrix columns."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        # Create questions in random order (by ID)
        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.LOGIC)
        q3 = await create_question(db_session, QuestionType.MATH)

        # Respond in different order
        await create_response(db_session, session, user, q3, is_correct=True)
        await create_response(db_session, session, user, q1, is_correct=False)
        await create_response(db_session, session, user, q2, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        # Questions should be ordered by ID
        assert result.question_ids == sorted(result.question_ids)

    async def test_session_ids_in_correct_order(self, db_session):
        """session_ids list is in the same order as matrix rows."""
        users = [create_user(db_session, f"user{i}@test.com") for i in range(3)]
        sessions = [create_test_session(db_session, user) for user in users]

        q = await create_question(db_session, QuestionType.PATTERN)

        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        # Sessions should be ordered by ID
        assert result.session_ids == sorted(result.session_ids)

    async def test_question_domains_match_columns(self, db_session):
        """question_domains list corresponds to matrix columns."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        q_pattern = await create_question(db_session, QuestionType.PATTERN)
        q_logic = await create_question(db_session, QuestionType.LOGIC)
        q_math = await create_question(db_session, QuestionType.MATH)

        await create_response(db_session, session, user, q_pattern, is_correct=True)
        await create_response(db_session, session, user, q_logic, is_correct=True)
        await create_response(db_session, session, user, q_math, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert len(result.question_domains) == result.n_items

        # Verify each domain matches the corresponding question
        for i, q_id in enumerate(result.question_ids):
            expected_domain = None
            if q_id == q_pattern.id:
                expected_domain = "pattern"
            elif q_id == q_logic.id:
                expected_domain = "logic"
            elif q_id == q_math.id:
                expected_domain = "math"
            assert result.question_domains[i] == expected_domain

    async def test_n_users_and_n_items_properties(self, db_session):
        """n_users and n_items properties return correct values."""
        users = [create_user(db_session, f"user{i}@test.com") for i in range(4)]
        sessions = [create_test_session(db_session, user) for user in users]

        questions = [
            await create_question(db_session, qt)
            for qt in [QuestionType.PATTERN, QuestionType.LOGIC, QuestionType.MATH]
        ]

        for user, session in zip(users, sessions):
            for q in questions:
                await create_response(db_session, session, user, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert result.n_users == 4
        assert result.n_items == 3
        assert result.matrix.shape == (4, 3)


# =============================================================================
# HELPER FUNCTION TESTS
# =============================================================================


class TestGetDomainColumnIndices:
    """Tests for get_domain_column_indices helper function."""

    def test_basic_domain_grouping(self):
        """Groups domain indices correctly."""
        domains = ["pattern", "logic", "pattern", "math", "logic"]

        result = get_domain_column_indices(domains)

        assert result["pattern"] == [0, 2]
        assert result["logic"] == [1, 4]
        assert result["math"] == [3]

    def test_single_domain(self):
        """Handles single domain."""
        domains = ["pattern", "pattern", "pattern"]

        result = get_domain_column_indices(domains)

        assert result["pattern"] == [0, 1, 2]
        assert len(result) == 1

    def test_empty_list(self):
        """Handles empty domain list."""
        domains = []

        result = get_domain_column_indices(domains)

        assert result == {}

    def test_all_unique_domains(self):
        """Handles all unique domains."""
        domains = ["pattern", "logic", "math", "verbal", "spatial", "memory"]

        result = get_domain_column_indices(domains)

        for i, domain in enumerate(domains):
            assert result[domain] == [i]


class TestGetResponseMatrixStats:
    """Tests for get_response_matrix_stats helper function."""

    async def test_calculates_overall_accuracy(self, db_session):
        """Calculates correct overall accuracy."""
        users = [create_user(db_session, f"user{i}@test.com") for i in range(2)]
        sessions = [create_test_session(db_session, user) for user in users]

        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.LOGIC)

        # User 1: both correct
        await create_response(db_session, sessions[0], users[0], q1, is_correct=True)
        await create_response(db_session, sessions[0], users[0], q2, is_correct=True)

        # User 2: both incorrect
        await create_response(db_session, sessions[1], users[1], q1, is_correct=False)
        await create_response(db_session, sessions[1], users[1], q2, is_correct=False)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        stats = get_response_matrix_stats(result)

        # 2/4 = 0.5 accuracy
        assert stats["overall_accuracy"] == pytest.approx(0.5)
        assert stats["n_users"] == 2
        assert stats["n_items"] == 2

    async def test_calculates_domain_counts(self, db_session):
        """Calculates correct domain question counts."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        # 2 pattern, 1 logic
        q1 = await create_question(db_session, QuestionType.PATTERN)
        q2 = await create_question(db_session, QuestionType.PATTERN)
        q3 = await create_question(db_session, QuestionType.LOGIC)

        await create_response(db_session, session, user, q1, is_correct=True)
        await create_response(db_session, session, user, q2, is_correct=True)
        await create_response(db_session, session, user, q3, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        stats = get_response_matrix_stats(result)

        assert stats["domain_counts"]["pattern"] == 2
        assert stats["domain_counts"]["logic"] == 1

    async def test_calculates_domain_accuracies(self, db_session):
        """Calculates correct domain-specific accuracies."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        q_pattern1 = await create_question(db_session, QuestionType.PATTERN)
        q_pattern2 = await create_question(db_session, QuestionType.PATTERN)
        q_logic = await create_question(db_session, QuestionType.LOGIC)

        # Pattern: 1/2 correct = 0.5
        await create_response(db_session, session, user, q_pattern1, is_correct=True)
        await create_response(db_session, session, user, q_pattern2, is_correct=False)

        # Logic: 1/1 correct = 1.0
        await create_response(db_session, session, user, q_logic, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        stats = get_response_matrix_stats(result)

        assert stats["domain_accuracies"]["pattern"] == pytest.approx(0.5)
        assert stats["domain_accuracies"]["logic"] == pytest.approx(1.0)

    async def test_calculates_sparsity(self, db_session):
        """Calculates sparsity (proportion of zeros)."""
        users = [create_user(db_session, f"user{i}@test.com") for i in range(2)]
        sessions = [create_test_session(db_session, user) for user in users]

        q = await create_question(db_session, QuestionType.PATTERN)

        # All incorrect = all zeros = sparsity 1.0
        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q, is_correct=False)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        stats = get_response_matrix_stats(result)

        assert stats["sparsity"] == pytest.approx(1.0)


# =============================================================================
# COMPLEX SCENARIO TESTS
# =============================================================================


class TestBuildResponseMatrixComplexScenarios:
    """Tests for complex real-world scenarios."""

    async def test_multiple_sessions_same_user(self, db_session):
        """User with multiple completed sessions appears multiple times."""
        user = await create_user(db_session)

        s1 = await create_test_session(db_session, user)
        s2 = await create_test_session(db_session, user)

        q = await create_question(db_session, QuestionType.PATTERN)

        await create_response(db_session, s1, user, q, is_correct=True)
        await create_response(db_session, s2, user, q, is_correct=False)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        # Both sessions should be included
        assert result.n_users == 2
        assert s1.id in result.session_ids
        assert s2.id in result.session_ids

    async def test_large_dataset(self, db_session):
        """Handles larger datasets correctly."""
        # Create 50 users, 20 questions, all with responses
        users = [create_user(db_session, f"user{i}@test.com") for i in range(50)]
        sessions = [create_test_session(db_session, user) for user in users]

        questions = []
        for i in range(20):
            qt = list(QuestionType)[i % 6]  # Cycle through question types
            questions.append(create_question(db_session, qt))

        for user, session in zip(users, sessions):
            for i, q in enumerate(questions):
                # Alternate correct/incorrect
                await create_response(
                    db_session, session, user, q, is_correct=((i + user.id) % 2 == 0)
                )

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert result.n_users == 50
        assert result.n_items == 20
        assert result.matrix.shape == (50, 20)

    async def test_mixed_active_inactive_questions(self, db_session):
        """Correctly handles mix of active and inactive questions."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        q_active1 = await create_question(
            db_session, QuestionType.PATTERN, is_active=True
        )
        q_active2 = await create_question(
            db_session, QuestionType.LOGIC, is_active=True
        )
        q_inactive = await create_question(
            db_session, QuestionType.MATH, is_active=False
        )

        await create_response(db_session, session, user, q_active1, is_correct=True)
        await create_response(db_session, session, user, q_active2, is_correct=True)
        await create_response(db_session, session, user, q_inactive, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        # Only 2 active questions should be in matrix
        assert result.n_items == 2
        assert q_active1.id in result.question_ids
        assert q_active2.id in result.question_ids
        assert q_inactive.id not in result.question_ids

    async def test_all_domains_represented(self, db_session):
        """All 6 question domains can be represented in matrix."""
        user = await create_user(db_session)
        session = await create_test_session(db_session, user)

        questions = []
        for qt in QuestionType:
            q = await create_question(db_session, qt)
            questions.append(q)
            await create_response(db_session, session, user, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
        )

        assert result is not None
        assert result.n_items == 6

        # All domains should be represented
        domains_in_result = set(result.question_domains)
        expected_domains = {qt.value for qt in QuestionType}
        assert domains_in_result == expected_domains


# =============================================================================
# MAX_RESPONSES LIMIT TESTS (BCQ-002)
# =============================================================================


class TestBuildResponseMatrixMaxResponses:
    """Tests for max_responses limit behavior."""

    async def test_respects_max_responses_limit(self, db_session):
        """Limits the number of responses fetched from database.

        Test scenario: 5 users, each answering 1 question = 5 total responses.
        With max_responses=3, exactly 3 responses should be fetched, which
        means exactly 3 users should appear in the matrix (since each user
        contributes exactly 1 response).
        """
        # Create 5 users with 1 question each = 5 responses
        users = [create_user(db_session, f"user{i}@test.com") for i in range(5)]
        sessions = [create_test_session(db_session, user) for user in users]

        q = await create_question(db_session, QuestionType.PATTERN)

        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q, is_correct=True)

        # Limit to 3 responses
        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
            max_responses=3,
        )

        assert result is not None
        # With 5 users and 1 question each, limit of 3 responses means exactly
        # 3 users should be included (each user = 1 response, so 3 responses = 3 users)
        assert (
            result.n_users == 3
        ), f"Expected exactly 3 users with max_responses=3, got {result.n_users}"
        # Verify there's at least 1 question in the matrix
        assert result.n_items >= 1, "Expected at least 1 question in the matrix"
        # Verify all included session IDs exist in the original set
        original_session_ids = {s.id for s in sessions}
        assert all(sid in original_session_ids for sid in result.session_ids)

    async def test_logs_warning_when_limit_reached(self, db_session):
        """Logs a warning when max_responses limit is reached.

        The warning message should include both the fetched count and the
        total available count for actionable information to administrators.
        (BCQ-038: Improved message format)
        """
        from unittest.mock import patch

        # Create enough data to hit the limit
        users = [create_user(db_session, f"user{i}@test.com") for i in range(10)]
        sessions = [create_test_session(db_session, user) for user in users]

        q = await create_question(db_session, QuestionType.PATTERN)

        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q, is_correct=True)

        # Patch the logger to capture the warning call
        with patch("app.core.analytics.logger") as mock_logger:
            # Set limit lower than total responses (10 total, limit 5)
            build_response_matrix(
                db_session,
                min_responses_per_question=1,
                min_questions_per_session=1,
                max_responses=5,
            )

            # Check that warning was logged
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]

            # BCQ-038: Verify improved message format includes both counts
            # Format: "Fetched X of Y total responses (limit: Z)"
            assert "Fetched 5 of 10 total responses" in warning_msg
            assert "limit: 5" in warning_msg
            assert "Matrix may be incomplete" in warning_msg

    async def test_no_warning_when_limit_not_reached(self, db_session):
        """No warning logged when responses are below the limit."""
        from unittest.mock import patch

        user = await create_user(db_session)
        session = await create_test_session(db_session, user)
        q = await create_question(db_session, QuestionType.PATTERN)
        await create_response(db_session, session, user, q, is_correct=True)

        # Patch the logger to verify no warning is logged
        with patch("app.core.analytics.logger") as mock_logger:
            # Set limit much higher than total responses
            build_response_matrix(
                db_session,
                min_responses_per_question=1,
                min_questions_per_session=1,
                max_responses=1000,
            )

            # Check that no warning about limit was logged
            mock_logger.warning.assert_not_called()

    async def test_zero_max_responses_disables_limit(self, db_session):
        """Setting max_responses=0 disables the limit."""
        # Create 5 users
        users = [create_user(db_session, f"user{i}@test.com") for i in range(5)]
        sessions = [create_test_session(db_session, user) for user in users]

        q = await create_question(db_session, QuestionType.PATTERN)

        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q, is_correct=True)

        # Disable limit with 0
        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
            max_responses=0,
        )

        assert result is not None
        # All 5 users should be included
        assert result.n_users == 5

    async def test_default_max_responses_is_10000(self, db_session):
        """Default max_responses is 10000 (from constant)."""
        from app.core.analytics import DEFAULT_RESPONSE_LIMIT

        assert DEFAULT_RESPONSE_LIMIT == 10000

    async def test_works_normally_under_limit(self, db_session):
        """Matrix is built normally when data is under the limit."""
        users = [create_user(db_session, f"user{i}@test.com") for i in range(3)]
        sessions = [create_test_session(db_session, user) for user in users]

        q = await create_question(db_session, QuestionType.PATTERN)

        for user, session in zip(users, sessions):
            await create_response(db_session, session, user, q, is_correct=True)

        result = await build_response_matrix(
            db_session,
            min_responses_per_question=1,
            min_questions_per_session=1,
            max_responses=100,  # Well above the 3 responses
        )

        assert result is not None
        assert result.n_users == 3
        assert result.n_items == 1
