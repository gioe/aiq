"""
Tests for backward compatibility with questions that don't have stimulus field.

This test suite verifies that questions created before the stimulus field was
added (with stimulus=None in the database) continue to work correctly across
all API endpoints and utility functions.

Context:
- The stimulus field was added to support memory-type questions (TASK-737)
- Existing questions in production have stimulus=NULL
- The QuestionResponse schema has stimulus as Optional[str] with default None
- TASK-744 updated question_to_response() to include stimulus in API responses
- Questions without stimulus return stimulus=None, while memory questions return their stimulus content
"""

from app.models import Question, TestSession
from app.models.models import QuestionType, DifficultyLevel, TestStatus
from app.core.question_utils import question_to_response
from app.schemas.questions import QuestionResponse
from sqlalchemy import select


class TestDatabaseLayerBackwardCompatibility:
    """Tests for database-level backward compatibility with NULL stimulus."""

    async def test_create_question_without_stimulus(self, db_session):
        """Test that a Question can be created with stimulus=None."""
        question = Question(
            question_text="What is 2 + 2?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options={"A": "3", "B": "4", "C": "5", "D": "6"},
            explanation="Simple addition",
            source_llm="test-llm",
            judge_score=0.95,
            is_active=True,
            stimulus=None,  # Explicitly set to None
        )

        db_session.add(question)
        await db_session.commit()
        await db_session.refresh(question)

        # Verify question was created successfully
        assert question.id is not None
        assert question.stimulus is None
        assert question.question_text == "What is 2 + 2?"

    async def test_query_question_with_null_stimulus(self, db_session):
        """Test that questions with NULL stimulus can be queried from database."""
        # Create question without stimulus
        question = Question(
            question_text="Pattern: 1, 2, 3, ?",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options={"A": "3", "B": "4", "C": "5", "D": "6"},
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )
        db_session.add(question)
        await db_session.commit()

        # Query the question back
        _qresult = await db_session.execute(
            select(Question).filter(Question.question_text == "Pattern: 1, 2, 3, ?")
        )

        retrieved = _qresult.scalars().first()

        assert retrieved is not None
        assert retrieved.stimulus is None
        assert retrieved.question_text == "Pattern: 1, 2, 3, ?"

    async def test_filter_questions_regardless_of_stimulus_value(self, db_session):
        """Test that querying questions works regardless of stimulus value."""
        # Create one question without stimulus
        q1 = Question(
            question_text="Question without stimulus",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="A",
            answer_options={"A": "Yes", "B": "No"},
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )

        # Create one question with stimulus
        q2 = Question(
            question_text="Question with stimulus",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "Cat", "B": "Dog"},
            source_llm="test-llm",
            is_active=True,
            stimulus="Remember these items: apple, banana, cherry.",
        )

        db_session.add(q1)
        db_session.add(q2)
        await db_session.commit()

        # Query all active questions
        _qresult = await db_session.execute(
            select(Question).filter(Question.is_active.is_(True))
        )
        questions = _qresult.scalars().all()

        # Both questions should be returned
        assert len(questions) >= 2
        question_texts = [q.question_text for q in questions]
        assert "Question without stimulus" in question_texts
        assert "Question with stimulus" in question_texts


class TestQuestionUtilityBackwardCompatibility:
    """Tests for question_to_response() utility handling NULL stimulus."""

    async def test_question_to_response_with_null_stimulus(self, db_session):
        """Test that question_to_response() handles questions with NULL stimulus."""
        question = Question(
            question_text="What is the capital of France?",
            question_type=QuestionType.VERBAL,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="Paris",
            answer_options={"A": "London", "B": "Paris", "C": "Berlin", "D": "Madrid"},
            explanation="Paris is the capital of France",
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )
        db_session.add(question)
        await db_session.commit()
        await db_session.refresh(question)

        # Convert to response
        response = question_to_response(question, include_explanation=False)

        # Verify response structure
        assert isinstance(response, QuestionResponse)
        assert response.id == question.id
        assert response.question_text == question.question_text
        assert response.question_type == question.question_type.value
        assert response.difficulty_level == question.difficulty_level.value
        assert response.answer_options is not None
        assert response.explanation is None  # Not included
        # TASK-744: stimulus field is now included in question_to_response() output
        # Questions without stimulus return stimulus=None
        assert response.stimulus is None

    async def test_question_to_response_preserves_none_stimulus(self, db_session):
        """Test that QuestionResponse schema correctly handles missing stimulus field."""
        question = Question(
            question_text="Which shape comes next?",
            question_type=QuestionType.SPATIAL,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="Triangle",
            answer_options={
                "A": "Circle",
                "B": "Square",
                "C": "Triangle",
                "D": "Pentagon",
            },
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )
        db_session.add(question)
        await db_session.commit()
        await db_session.refresh(question)

        # Convert to response (doesn't include stimulus)
        response = question_to_response(question, include_explanation=False)

        # Verify the response can be serialized to dict
        response_dict = response.model_dump()
        assert "id" in response_dict
        assert "question_text" in response_dict
        # stimulus field should be in the dict with None value due to schema default
        assert "stimulus" in response_dict
        assert response_dict["stimulus"] is None


class TestQuestionResponseSchemaBackwardCompatibility:
    """Tests for QuestionResponse schema handling of stimulus field."""

    def test_schema_validates_with_stimulus_none(self):
        """Test that QuestionResponse validates correctly with stimulus=None."""
        data = {
            "id": 1,
            "question_text": "Test question",
            "question_type": "pattern",
            "difficulty_level": "easy",
            "answer_options": ["A", "B", "C", "D"],
            "explanation": None,
            "stimulus": None,
        }

        response = QuestionResponse.model_validate(data)
        assert response.stimulus is None

    def test_schema_validates_without_stimulus_field(self):
        """Test that QuestionResponse validates when stimulus field is omitted."""
        # This simulates the current behavior where question_to_response()
        # doesn't include the stimulus field in its output dict
        data = {
            "id": 1,
            "question_text": "Test question",
            "question_type": "pattern",
            "difficulty_level": "easy",
            "answer_options": ["A", "B", "C", "D"],
            "explanation": None,
            # Note: stimulus field is NOT included
        }

        response = QuestionResponse.model_validate(data)
        # Schema should default stimulus to None
        assert response.stimulus is None

    def test_schema_serialization_includes_stimulus_as_none(self):
        """Test that serialized QuestionResponse includes stimulus=None."""
        data = {
            "id": 1,
            "question_text": "Test question",
            "question_type": "pattern",
            "difficulty_level": "easy",
            "answer_options": ["A", "B", "C", "D"],
            "explanation": None,
        }

        response = QuestionResponse.model_validate(data)
        serialized = response.model_dump()

        # Verify stimulus is in serialized output with None value
        assert "stimulus" in serialized
        assert serialized["stimulus"] is None


class TestAPIEndpointBackwardCompatibility:
    """Tests for API endpoints serving questions without stimulus."""

    async def test_unseen_questions_endpoint_with_no_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test /v1/questions/unseen returns questions correctly when they have no stimulus."""
        # Create questions without stimulus
        questions = [
            Question(
                question_text="Question 1 without stimulus",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            ),
            Question(
                question_text="Question 2 without stimulus",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="B",
                answer_options={"A": "Yes", "B": "No", "C": "Maybe"},
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            ),
        ]
        for q in questions:
            db_session.add(q)
        await db_session.commit()

        # Request unseen questions
        response = await client.get(
            "/v1/questions/unseen?count=2", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "questions" in data
        assert len(data["questions"]) >= 1

        # Verify each question has stimulus field set to None
        for question in data["questions"]:
            assert "stimulus" in question
            assert question["stimulus"] is None
            assert "question_text" in question
            assert "correct_answer" not in question  # Should not be exposed

    async def test_start_test_endpoint_with_no_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test /v1/test/start works correctly with questions that have no stimulus."""
        # Create questions without stimulus
        questions = [
            Question(
                question_text=f"Test question {i} without stimulus",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            )
            for i in range(3)
        ]
        for q in questions:
            db_session.add(q)
        await db_session.commit()

        # Start a test
        response = await client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert "questions" in data
        assert "session" in data
        assert len(data["questions"]) == 3

        # Verify each question has stimulus field set to None
        for question in data["questions"]:
            assert "stimulus" in question
            assert question["stimulus"] is None
            assert "question_text" in question

    async def test_mixed_stimulus_questions_in_same_test(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that a test can contain both questions with and without stimulus.

        Note: Currently question_to_response() does not include the stimulus field
        in its output, so all questions will have stimulus=None in API responses.
        This test verifies the current behavior for backward compatibility.
        """
        # Create questions with mixed stimulus values
        questions = [
            Question(
                question_text="Question without stimulus",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "1", "B": "2", "C": "3", "D": "4"},
                source_llm="test-llm",
                is_active=True,
                stimulus=None,  # No stimulus
            ),
            Question(
                question_text="What was the first item?",
                question_type=QuestionType.MEMORY,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="apple",
                answer_options={"A": "apple", "B": "banana", "C": "cherry"},
                source_llm="test-llm",
                is_active=True,
                stimulus="Remember these items: apple, banana, cherry.",  # Has stimulus
            ),
        ]
        for q in questions:
            db_session.add(q)
        await db_session.commit()

        # Start a test
        response = await client.post(
            "/v1/test/start?question_count=2", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["questions"]) == 2

        # Find questions by text
        questions_by_text = {q["question_text"]: q for q in data["questions"]}

        # Verify question without stimulus has stimulus=None
        q_without = questions_by_text["Question without stimulus"]
        assert q_without["stimulus"] is None

        # TASK-744: question_to_response() now includes stimulus in API responses.
        # Memory questions return their stimulus content; non-memory questions return None.
        q_with = questions_by_text["What was the first item?"]
        assert q_with["stimulus"] == "Remember these items: apple, banana, cherry."


class TestEndToEndBackwardCompatibility:
    """End-to-end tests for complete test flow with no-stimulus questions."""

    async def test_complete_test_flow_with_no_stimulus_questions(
        self, client, auth_headers, db_session, test_user
    ):
        """Test complete test flow from start to submit with questions lacking stimulus."""
        # Create questions without stimulus
        questions = [
            Question(
                question_text=f"E2E question {i} without stimulus",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="A",
                answer_options={"A": "Correct", "B": "Wrong"},
                explanation="This is the explanation",
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            )
            for i in range(3)
        ]
        for q in questions:
            db_session.add(q)
        await db_session.commit()
        await db_session.flush()
        # question_ids are assigned by the database, we'll use returned_questions below

        # Step 1: Start test
        start_response = await client.post(
            "/v1/test/start?question_count=3", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        returned_questions = start_response.json()["questions"]

        # Verify all questions have stimulus=None
        for q in returned_questions:
            assert q["stimulus"] is None

        # Step 2: Submit responses
        responses = [
            {
                "question_id": q["id"],
                "user_answer": "A",
            }
            for q in returned_questions
        ]

        submit_response = await client.post(
            "/v1/test/submit",
            json={"session_id": session_id, "responses": responses},
            headers=auth_headers,
        )
        assert submit_response.status_code == 200

        # Verify submission succeeded and returned results
        result_data = submit_response.json()
        assert "result" in result_data
        assert result_data["result"]["correct_answers"] == 3

        # Step 3: Verify test session was marked as completed
        _result_0 = await db_session.execute(
            select(TestSession).filter_by(id=session_id)
        )
        session = _result_0.scalars().first()
        assert session is not None
        assert session.status == TestStatus.COMPLETED

    async def test_submit_response_works_for_questions_without_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that submitting responses works correctly for questions without stimulus.

        This test verifies that:
        1. Questions without stimulus can be retrieved in a test session
        2. The stimulus field is correctly returned as None
        3. Test submission succeeds for questions without stimulus
        4. The response scoring works correctly regardless of stimulus value
        """
        # Create a question without stimulus but with explanation
        question = Question(
            question_text="Logic question without stimulus",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
            answer_options={"A": "Yes", "B": "No"},
            explanation="This is why the answer is correct.",
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )
        db_session.add(question)
        await db_session.commit()
        await db_session.refresh(question)

        # Start test
        start_response = await client.post(
            "/v1/test/start?question_count=1", headers=auth_headers
        )
        assert start_response.status_code == 200
        session_id = start_response.json()["session"]["id"]
        question_id = start_response.json()["questions"][0]["id"]

        # Verify stimulus is None in response (explanation is hidden before submit)
        assert start_response.json()["questions"][0]["explanation"] is None
        assert start_response.json()["questions"][0]["stimulus"] is None

        # Submit response
        submit_response = await client.post(
            "/v1/test/submit",
            json={
                "session_id": session_id,
                "responses": [{"question_id": question_id, "user_answer": "B"}],
            },
            headers=auth_headers,
        )
        assert submit_response.status_code == 200

        # Verify submission succeeded and scored correctly
        result_data = submit_response.json()
        assert "result" in result_data
        assert result_data["result"]["correct_answers"] == 1
        assert result_data["result"]["total_questions"] == 1
