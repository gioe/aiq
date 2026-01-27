"""Tests for database operations."""

import pytest
from unittest.mock import Mock, patch, ANY
from sqlalchemy.orm import Session

from app.database import DatabaseService
from app.models import (
    DifficultyLevel,
    EvaluatedQuestion,
    EvaluationScore,
    GeneratedQuestion,
    QuestionType,
)


@pytest.fixture
def sample_question():
    """Create a sample generated question for testing."""
    return GeneratedQuestion(
        question_text="What is 2 + 2?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="4",
        answer_options=["2", "3", "4", "5"],
        explanation="2 + 2 equals 4 by basic addition",
        metadata={"category": "arithmetic"},
        source_llm="openai",
        source_model="gpt-4",
    )


@pytest.fixture
def sample_evaluated_question(sample_question):
    """Create a sample evaluated question for testing."""
    evaluation = EvaluationScore(
        clarity_score=0.9,
        difficulty_score=0.8,
        validity_score=0.85,
        formatting_score=0.95,
        creativity_score=0.7,
        overall_score=0.84,
        feedback="Good question",
    )

    return EvaluatedQuestion(
        question=sample_question,
        evaluation=evaluation,
        judge_model="openai/gpt-4",
        approved=True,
    )


@pytest.fixture
def mock_database_service():
    """Create a mock database service."""
    with patch("app.database.create_engine"):
        with patch("app.database.sessionmaker"):
            service = DatabaseService(
                database_url="postgresql://test:test@localhost/test"
            )
            return service


class TestDatabaseService:
    """Tests for DatabaseService class."""

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_initialization(self, mock_sessionmaker, mock_create_engine):
        """Test database service initialization."""
        database_url = "postgresql://user:pass@localhost/testdb"
        service = DatabaseService(database_url=database_url)

        assert service.database_url == database_url
        mock_create_engine.assert_called_once_with(database_url)
        mock_sessionmaker.assert_called_once()

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_get_session(self, mock_sessionmaker, mock_create_engine):
        """Test getting a database session."""
        mock_session = Mock(spec=Session)
        mock_sessionmaker.return_value = Mock(return_value=mock_session)

        service = DatabaseService(database_url="postgresql://test:test@localhost/test")
        session = service.get_session()

        assert session == mock_session

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_close_session(self, mock_sessionmaker, mock_create_engine):
        """Test closing a database session."""
        mock_session = Mock(spec=Session)
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        service.close_session(mock_session)
        mock_session.close.assert_called_once()

    def test_insert_question_success(self, mock_database_service, sample_question):
        """Test successful question insertion."""
        mock_session = Mock(spec=Session)
        mock_db_question = Mock()
        mock_db_question.id = 123

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        # Mock session operations
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 123))

        with patch("app.database.QuestionModel", return_value=mock_db_question):
            question_id = mock_database_service.insert_question(sample_question)

        assert question_id == 123
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_database_service.close_session.assert_called_once()

    def test_insert_question_with_judge_score(
        self, mock_database_service, sample_question
    ):
        """Test question insertion with judge score."""
        mock_session = Mock(spec=Session)
        mock_db_question = Mock()
        mock_db_question.id = 456

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 456))

        with patch("app.database.QuestionModel", return_value=mock_db_question):
            question_id = mock_database_service.insert_question(
                sample_question, judge_score=0.85
            )

        assert question_id == 456

    def test_insert_question_failure_rollback(
        self, mock_database_service, sample_question
    ):
        """Test question insertion failure triggers rollback."""
        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock(side_effect=Exception("Database error"))
        mock_session.rollback = Mock()

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        with patch("app.database.QuestionModel"):
            with pytest.raises(Exception, match="Database error"):
                mock_database_service.insert_question(sample_question)

        mock_session.rollback.assert_called_once()
        mock_database_service.close_session.assert_called_once()

    def test_insert_evaluated_question(
        self, mock_database_service, sample_evaluated_question
    ):
        """Test inserting an evaluated question."""
        mock_session = Mock(spec=Session)
        mock_db_question = Mock()
        mock_db_question.id = 789

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 789))

        with patch("app.database.QuestionModel", return_value=mock_db_question):
            question_id = mock_database_service.insert_evaluated_question(
                sample_evaluated_question
            )

        assert question_id == 789

    def test_insert_evaluated_question_stores_individual_scores(
        self, mock_database_service, sample_evaluated_question
    ):
        """Test that individual evaluation scores are stored in metadata."""
        mock_session = Mock(spec=Session)
        mock_db_question = Mock()
        mock_db_question.id = 999

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock(side_effect=lambda obj: setattr(obj, "id", 999))

        captured_question = None

        def capture_question(q):
            nonlocal captured_question
            captured_question = q

        mock_session.add.side_effect = capture_question

        with patch("app.database.QuestionModel") as MockQuestionModel:
            mock_instance = Mock()
            mock_instance.id = 999
            MockQuestionModel.return_value = mock_instance

            mock_database_service.insert_evaluated_question(sample_evaluated_question)

            # Verify the metadata contains individual scores
            call_kwargs = MockQuestionModel.call_args[1]
            metadata = call_kwargs["question_metadata"]

            assert "evaluation_scores" in metadata
            scores = metadata["evaluation_scores"]
            assert scores["clarity_score"] == pytest.approx(0.9)
            assert scores["difficulty_score"] == pytest.approx(0.8)
            assert scores["validity_score"] == pytest.approx(0.85)
            assert scores["formatting_score"] == pytest.approx(0.95)
            assert scores["creativity_score"] == pytest.approx(0.7)
            assert scores["feedback"] == "Good question"
            assert metadata["judge_model"] == "openai/gpt-4"

    def test_insert_questions_batch(self, mock_database_service):
        """Test batch question insertion."""
        questions = [
            GeneratedQuestion(
                question_text=f"Question {i}",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer=str(i + 1),
                answer_options=["1", "2", "3", "4"],
                explanation=f"Explanation {i}",
                source_llm="openai",
                source_model="gpt-4",
            )
            for i in range(3)
        ]

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.new = []  # No new objects after commit in mock

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        with patch("app.database.QuestionModel"):
            question_ids = mock_database_service.insert_questions_batch(questions)

        assert isinstance(question_ids, list)
        assert mock_session.commit.called
        mock_database_service.close_session.assert_called_once()

    def test_insert_questions_batch_with_scores(self, mock_database_service):
        """Test batch insertion with judge scores."""
        questions = [
            GeneratedQuestion(
                question_text=f"Question {i}",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer=str(i + 1),
                answer_options=["1", "2", "3", "4"],
                explanation=f"Explanation {i}",
                source_llm="openai",
                source_model="gpt-4",
            )
            for i in range(3)
        ]
        scores = [0.8, 0.85, 0.9]

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.new = []

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        with patch("app.database.QuestionModel"):
            question_ids = mock_database_service.insert_questions_batch(
                questions, judge_scores=scores
            )

        assert isinstance(question_ids, list)
        mock_database_service.close_session.assert_called_once()

    def test_insert_questions_batch_score_length_mismatch(self, mock_database_service):
        """Test batch insertion fails with mismatched score length."""
        questions = [
            GeneratedQuestion(
                question_text="Question 1",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="1",
                answer_options=["1", "2", "3", "4"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            )
        ]
        scores = [0.8, 0.9]  # Length mismatch

        with pytest.raises(ValueError, match="Length of judge_scores"):
            mock_database_service.insert_questions_batch(questions, judge_scores=scores)

    def test_insert_evaluated_questions_batch(self, mock_database_service):
        """Test batch insertion of evaluated questions."""
        evaluated_questions = [
            EvaluatedQuestion(
                question=GeneratedQuestion(
                    question_text=f"Question {i}",
                    question_type=QuestionType.MATH,
                    difficulty_level=DifficultyLevel.EASY,
                    correct_answer=str(i + 1),
                    answer_options=["1", "2", "3", "4"],
                    explanation=f"Explanation {i}",
                    source_llm="openai",
                    source_model="gpt-4",
                ),
                evaluation=EvaluationScore(
                    clarity_score=0.9,
                    difficulty_score=0.8,
                    validity_score=0.85,
                    formatting_score=0.95,
                    creativity_score=0.7,
                    overall_score=0.84,
                ),
                judge_model="openai/gpt-4",
                approved=True,
            )
            for i in range(2)
        ]

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.new = []

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        with patch("app.database.QuestionModel"):
            question_ids = mock_database_service.insert_evaluated_questions_batch(
                evaluated_questions
            )

        assert isinstance(question_ids, list)
        mock_database_service.close_session.assert_called_once()

    def test_get_all_questions(self, mock_database_service):
        """Test retrieving all questions."""
        mock_session = Mock(spec=Session)
        mock_query = Mock()

        # Create mock question objects
        mock_questions = [
            Mock(
                id=1,
                question_text="Question 1",
                question_type="math",
                difficulty_level="easy",
                correct_answer="1",
                answer_options=["1", "2", "3", "4"],
                explanation="Explanation 1",
                question_metadata={},
                source_llm="openai",
                source_model="gpt-4-turbo",
                judge_score=0.8,
                prompt_version="2.0",
                created_at="2024-01-01",
                is_active=True,
            ),
            Mock(
                id=2,
                question_text="Question 2",
                question_type="logic",
                difficulty_level="medium",
                correct_answer="2",
                answer_options=["1", "2", "3", "4"],
                explanation="Explanation 2",
                question_metadata={},
                source_llm="anthropic",
                source_model="claude-3-opus",
                judge_score=0.85,
                prompt_version="2.0",
                created_at="2024-01-02",
                is_active=True,
            ),
        ]

        mock_query.all.return_value = mock_questions
        mock_session.query.return_value = mock_query

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        questions = mock_database_service.get_all_questions()

        assert len(questions) == 2
        assert questions[0]["id"] == 1
        assert questions[1]["id"] == 2
        mock_database_service.close_session.assert_called_once()

    def test_get_question_count(self, mock_database_service):
        """Test getting question count."""
        mock_session = Mock(spec=Session)
        mock_query = Mock()
        mock_query.count.return_value = 42

        mock_session.query.return_value = mock_query

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        count = mock_database_service.get_question_count()

        assert count == 42
        mock_database_service.close_session.assert_called_once()

    def test_test_connection_success(self, mock_database_service):
        """Test successful database connection test."""
        mock_session = Mock(spec=Session)
        mock_session.execute = Mock()

        mock_database_service.get_session = Mock(return_value=mock_session)
        mock_database_service.close_session = Mock()

        result = mock_database_service.test_connection()

        assert result is True
        mock_session.execute.assert_called_once_with(ANY)
        mock_database_service.close_session.assert_called_once()

    def test_test_connection_failure(self, mock_database_service):
        """Test failed database connection test."""
        mock_database_service.get_session = Mock(
            side_effect=Exception("Connection failed")
        )

        result = mock_database_service.test_connection()

        assert result is False


class TestQuestionTypeMapping:
    """Tests for question type enum mapping."""

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_question_type_mapping(self, mock_sessionmaker, mock_create_engine):
        """Test that question types are correctly mapped to database enums."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        question = GeneratedQuestion(
            question_text="Test question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options=["A", "B", "C", "D"],
            explanation="Test explanation",
            source_llm="openai",
            source_model="gpt-4",
        )

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        mock_db_question = None

        def capture_question(q):
            nonlocal mock_db_question
            mock_db_question = q

        mock_session.add.side_effect = capture_question

        with patch("app.database.QuestionModel") as MockQuestionModel:
            mock_instance = Mock()
            mock_instance.id = 1
            MockQuestionModel.return_value = mock_instance

            service.insert_question(question)

        # Verify the question type was mapped correctly
        MockQuestionModel.assert_called_once()
        call_kwargs = MockQuestionModel.call_args[1]
        assert call_kwargs["question_type"] == "pattern"


class TestStimulusFieldHandling:
    """Tests for stimulus field handling in database operations (TASK-728)."""

    @pytest.fixture
    def memory_question_with_stimulus(self):
        """Create a memory question with stimulus content."""
        return GeneratedQuestion(
            question_text="What was the third item in the list?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="apple",
            answer_options=["dog", "cat", "apple", "house"],
            explanation="Apple was the third item in the memorized list.",
            stimulus="Remember this sequence: dog, cat, apple, house, tree",
            metadata={"memory_type": "sequence_recall"},
            source_llm="openai",
            source_model="gpt-4",
        )

    @pytest.fixture
    def question_without_stimulus(self):
        """Create a question without stimulus (non-memory type)."""
        return GeneratedQuestion(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            explanation="Basic addition",
            source_llm="openai",
            source_model="gpt-4",
        )

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_insert_question_with_stimulus(
        self, mock_sessionmaker, mock_create_engine, memory_question_with_stimulus
    ):
        """Test that stimulus field is properly inserted when present."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        with patch("app.database.QuestionModel") as MockQuestionModel:
            mock_instance = Mock()
            mock_instance.id = 100
            MockQuestionModel.return_value = mock_instance

            service.insert_question(memory_question_with_stimulus)

            # Verify stimulus was passed to QuestionModel
            call_kwargs = MockQuestionModel.call_args[1]
            assert (
                call_kwargs["stimulus"]
                == "Remember this sequence: dog, cat, apple, house, tree"
            )

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_insert_question_without_stimulus(
        self, mock_sessionmaker, mock_create_engine, question_without_stimulus
    ):
        """Test that stimulus field is None when not provided."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        with patch("app.database.QuestionModel") as MockQuestionModel:
            mock_instance = Mock()
            mock_instance.id = 101
            MockQuestionModel.return_value = mock_instance

            service.insert_question(question_without_stimulus)

            # Verify stimulus is None
            call_kwargs = MockQuestionModel.call_args[1]
            assert call_kwargs["stimulus"] is None

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_insert_evaluated_question_preserves_stimulus(
        self, mock_sessionmaker, mock_create_engine, memory_question_with_stimulus
    ):
        """Test that stimulus is preserved when inserting evaluated questions."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        evaluation = EvaluationScore(
            clarity_score=0.9,
            difficulty_score=0.8,
            validity_score=0.85,
            formatting_score=0.95,
            creativity_score=0.7,
            overall_score=0.84,
            feedback="Good memory question",
        )

        evaluated_question = EvaluatedQuestion(
            question=memory_question_with_stimulus,
            evaluation=evaluation,
            judge_model="openai/gpt-4",
            approved=True,
        )

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.refresh = Mock()

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        with patch("app.database.QuestionModel") as MockQuestionModel:
            mock_instance = Mock()
            mock_instance.id = 102
            MockQuestionModel.return_value = mock_instance

            service.insert_evaluated_question(evaluated_question)

            # Verify stimulus was preserved through the evaluation pipeline
            call_kwargs = MockQuestionModel.call_args[1]
            assert (
                call_kwargs["stimulus"]
                == "Remember this sequence: dog, cat, apple, house, tree"
            )

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_insert_questions_batch_with_stimulus(
        self, mock_sessionmaker, mock_create_engine
    ):
        """Test batch insertion handles questions with and without stimulus."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        questions = [
            GeneratedQuestion(
                question_text="What was the second word?",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="banana",
                answer_options=["apple", "banana", "cherry", "date"],
                explanation="Banana was second",
                stimulus="Memorize: apple, banana, cherry",
                source_llm="openai",
                source_model="gpt-4",
            ),
            GeneratedQuestion(
                question_text="What is 3 * 3?",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="9",
                answer_options=["6", "9", "12", "15"],
                explanation="3 times 3 equals 9",
                source_llm="openai",
                source_model="gpt-4",
            ),
        ]

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.new = []

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        captured_questions = []

        with patch("app.database.QuestionModel") as MockQuestionModel:

            def capture_model_call(**kwargs):
                captured_questions.append(kwargs)
                mock_instance = Mock()
                mock_instance.id = len(captured_questions)
                return mock_instance

            MockQuestionModel.side_effect = capture_model_call

            service.insert_questions_batch(questions)

            # Verify both questions were created with correct stimulus values
            assert len(captured_questions) == 2
            assert (
                captured_questions[0]["stimulus"] == "Memorize: apple, banana, cherry"
            )
            assert captured_questions[1]["stimulus"] is None

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_insert_evaluated_questions_batch_preserves_stimulus(
        self, mock_sessionmaker, mock_create_engine
    ):
        """Test batch insertion of evaluated questions preserves stimulus."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        evaluated_questions = [
            EvaluatedQuestion(
                question=GeneratedQuestion(
                    question_text="What was the first color?",
                    question_type=QuestionType.MEMORY,
                    difficulty_level=DifficultyLevel.EASY,
                    correct_answer="red",
                    answer_options=["red", "blue", "green", "yellow"],
                    explanation="Red was first",
                    stimulus="Colors: red, blue, green",
                    source_llm="anthropic",
                    source_model="claude-3-sonnet",
                ),
                evaluation=EvaluationScore(
                    clarity_score=0.9,
                    difficulty_score=0.7,
                    validity_score=0.85,
                    formatting_score=0.95,
                    creativity_score=0.8,
                    overall_score=0.85,
                ),
                judge_model="openai/gpt-4",
                approved=True,
            ),
        ]

        mock_session = Mock(spec=Session)
        mock_session.add = Mock()
        mock_session.commit = Mock()
        mock_session.new = []

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        with patch("app.database.QuestionModel") as MockQuestionModel:
            mock_instance = Mock()
            mock_instance.id = 200
            MockQuestionModel.return_value = mock_instance

            service.insert_evaluated_questions_batch(evaluated_questions)

            # Verify stimulus was preserved
            call_kwargs = MockQuestionModel.call_args[1]
            assert call_kwargs["stimulus"] == "Colors: red, blue, green"

    @patch("app.database.create_engine")
    @patch("app.database.sessionmaker")
    def test_get_all_questions_includes_stimulus(
        self, mock_sessionmaker, mock_create_engine
    ):
        """Test that get_all_questions returns stimulus field."""
        service = DatabaseService(database_url="postgresql://test:test@localhost/test")

        mock_session = Mock(spec=Session)
        mock_query = Mock()

        # Create mock question with stimulus
        mock_questions = [
            Mock(
                id=1,
                question_text="What was the third item?",
                question_type="memory",
                difficulty_level="medium",
                correct_answer="apple",
                answer_options=["dog", "cat", "apple", "house"],
                explanation="Apple was third",
                stimulus="Sequence: dog, cat, apple, house",
                question_metadata={"memory_type": "sequence"},
                source_llm="openai",
                source_model="gpt-4",
                judge_score=0.85,
                prompt_version="2.0",
                created_at="2024-01-01",
                is_active=True,
                question_embedding=None,
            ),
        ]

        mock_query.all.return_value = mock_questions
        mock_session.query.return_value = mock_query

        service.get_session = Mock(return_value=mock_session)
        service.close_session = Mock()

        questions = service.get_all_questions()

        assert len(questions) == 1
        assert questions[0]["stimulus"] == "Sequence: dog, cat, apple, house"
