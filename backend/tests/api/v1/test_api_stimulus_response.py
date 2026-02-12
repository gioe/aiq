"""
Tests for verifying the stimulus field is returned correctly in API responses.

TASK-744: Verify API returns stimulus in responses.

This test suite verifies that:
1. The stimulus field appears in JSON responses from GET /v1/questions endpoints
2. Memory questions return their stimulus content (non-null)
3. Non-memory questions return stimulus as null
4. Both /v1/questions/unseen and /v1/test/start endpoints handle stimulus correctly
"""

from app.models import Question
from app.models.models import QuestionType, DifficultyLevel


class TestStimulusInUnseenQuestionsEndpoint:
    """Tests for stimulus field in GET /v1/questions/unseen responses."""

    def test_stimulus_field_present_in_response(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that stimulus field is always present in question responses."""
        # Create a non-memory question without stimulus
        question = Question(
            question_text="What is 5 + 5?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="10",
            answer_options={"A": "8", "B": "9", "C": "10", "D": "11"},
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )
        db_session.add(question)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["questions"]) >= 1

        # Verify stimulus field is present in response with correct value
        for q in data["questions"]:
            assert "stimulus" in q, "stimulus field must be present in response"
            # Non-memory questions should have null stimulus
            assert (
                q["stimulus"] is None
            ), "Non-memory question should have null stimulus"

    def test_memory_question_returns_non_null_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that memory questions return their stimulus content (non-null)."""
        stimulus_content = (
            "Remember these items in order: apple, banana, cherry, date, elderberry."
        )

        memory_question = Question(
            question_text="What was the third item in the list?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="cherry",
            answer_options={"A": "apple", "B": "banana", "C": "cherry", "D": "date"},
            source_llm="test-llm",
            is_active=True,
            stimulus=stimulus_content,
        )
        db_session.add(memory_question)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find the memory question in responses
        memory_questions = [
            q for q in data["questions"] if q["question_type"] == "memory"
        ]
        assert len(memory_questions) >= 1, "Memory question should be returned"

        memory_q = memory_questions[0]
        assert (
            memory_q["stimulus"] is not None
        ), "Memory question should have non-null stimulus"
        assert memory_q["stimulus"] == stimulus_content, "Stimulus content should match"

    def test_non_memory_question_returns_null_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that non-memory questions return stimulus as null."""
        # Create questions of each non-memory type
        non_memory_questions = [
            Question(
                question_text="Pattern: 1, 2, 4, 8, ?",
                question_type=QuestionType.PATTERN,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="16",
                answer_options={"A": "10", "B": "12", "C": "16", "D": "32"},
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            ),
            Question(
                question_text="All dogs are mammals. Some mammals are pets. Therefore?",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="Some pets may be dogs",
                answer_options={
                    "A": "All dogs are pets",
                    "B": "Some pets may be dogs",
                    "C": "No pets are dogs",
                    "D": "All mammals are dogs",
                },
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            ),
            Question(
                question_text="What is 12 x 8?",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="96",
                answer_options={"A": "84", "B": "96", "C": "108", "D": "120"},
                source_llm="test-llm",
                is_active=True,
                stimulus=None,
            ),
        ]
        for q in non_memory_questions:
            db_session.add(q)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify all non-memory questions have null stimulus
        for q in data["questions"]:
            if q["question_type"] != "memory":
                assert (
                    q["stimulus"] is None
                ), f"{q['question_type']} question should have null stimulus"

    def test_mixed_memory_and_non_memory_questions(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that a mix of memory and non-memory questions have correct stimulus values."""
        stimulus_content = "Study this sequence: red, blue, green, yellow, purple."

        # Create one memory question with stimulus
        memory_q = Question(
            question_text="What color came after blue?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="green",
            answer_options={"A": "red", "B": "green", "C": "yellow", "D": "purple"},
            source_llm="test-llm",
            is_active=True,
            stimulus=stimulus_content,
        )

        # Create one non-memory question without stimulus
        math_q = Question(
            question_text="What is 7 x 7?",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="49",
            answer_options={"A": "42", "B": "49", "C": "56", "D": "63"},
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )

        db_session.add(memory_q)
        db_session.add(math_q)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find questions by type
        questions_by_type = {}
        for q in data["questions"]:
            if q["question_type"] not in questions_by_type:
                questions_by_type[q["question_type"]] = []
            questions_by_type[q["question_type"]].append(q)

        # Verify memory question has non-null stimulus
        assert "memory" in questions_by_type
        memory_questions = questions_by_type["memory"]
        for mq in memory_questions:
            assert mq["stimulus"] is not None
            assert mq["stimulus"] == stimulus_content

        # Verify math question has null stimulus
        assert "math" in questions_by_type
        for math_question in questions_by_type["math"]:
            if math_question["question_text"] == "What is 7 x 7?":
                assert math_question["stimulus"] is None


class TestStimulusInTestStartEndpoint:
    """Tests for stimulus field in POST /v1/test/start responses."""

    def test_stimulus_field_present_in_test_start_response(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that stimulus field is present in test start response."""
        # Create questions for the test
        questions = [
            Question(
                question_text=f"Test question {i}",
                question_type=QuestionType.PATTERN,
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
        db_session.commit()

        response = client.post("/v1/test/start?question_count=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "questions" in data
        for q in data["questions"]:
            assert (
                "stimulus" in q
            ), "stimulus field must be present in test start response"

    def test_memory_question_stimulus_in_test_start(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that memory questions have non-null stimulus in test start response."""
        stimulus_content = "Memorize: 42, 17, 83, 91, 56"

        memory_question = Question(
            question_text="What was the second number?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="17",
            answer_options={"A": "42", "B": "17", "C": "83", "D": "91"},
            source_llm="test-llm",
            is_active=True,
            stimulus=stimulus_content,
        )
        db_session.add(memory_question)
        db_session.commit()

        response = client.post("/v1/test/start?question_count=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data["questions"]) == 1
        question = data["questions"][0]
        assert question["stimulus"] == stimulus_content

    def test_test_with_mixed_question_types_has_correct_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that a test with mixed question types returns correct stimulus values."""
        # Create a memory question with stimulus
        memory_q = Question(
            question_text="What item was last?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="orange",
            answer_options={"A": "apple", "B": "banana", "C": "grape", "D": "orange"},
            source_llm="test-llm",
            is_active=True,
            stimulus="Remember: apple, banana, grape, orange",
        )

        # Create non-memory questions without stimulus
        logic_q = Question(
            question_text="If A then B. A is true. What can we conclude?",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="B is true",
            answer_options={
                "A": "A is false",
                "B": "B is true",
                "C": "B is false",
                "D": "Nothing",
            },
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )

        db_session.add(memory_q)
        db_session.add(logic_q)
        db_session.commit()

        response = client.post("/v1/test/start?question_count=2", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert len(data["questions"]) == 2

        # Verify each question has appropriate stimulus
        for q in data["questions"]:
            if q["question_type"] == "memory":
                assert q["stimulus"] is not None
                assert q["stimulus"] == "Remember: apple, banana, grape, orange"
            else:
                assert q["stimulus"] is None


class TestStimulusFieldIntegrity:
    """Tests for stimulus field data integrity across API operations."""

    def test_stimulus_content_preserved_exactly(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that stimulus content is preserved exactly as stored."""
        # Use stimulus with special characters and formatting
        stimulus_content = """Study the following carefully:
1. First item: "apple" (red)
2. Second item: 'banana' (yellow)
3. Third item: grape & orange

Note: Pay attention to colors!"""

        question = Question(
            question_text="What color was the apple?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="red",
            answer_options={"A": "red", "B": "yellow", "C": "green", "D": "orange"},
            source_llm="test-llm",
            is_active=True,
            stimulus=stimulus_content,
        )
        db_session.add(question)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find the memory question
        memory_qs = [q for q in data["questions"] if q["question_type"] == "memory"]
        assert len(memory_qs) >= 1

        # Verify stimulus content is exactly preserved
        assert memory_qs[0]["stimulus"] == stimulus_content

    def test_empty_string_stimulus_vs_null_stimulus(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that empty string stimulus is distinguished from null stimulus."""
        # Create question with empty string stimulus (edge case)
        q_empty = Question(
            question_text="Question with empty stimulus",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
            answer_options={"A": "1", "B": "2"},
            source_llm="test-llm",
            is_active=True,
            stimulus="",  # Empty string, not None
        )

        # Create question with null stimulus
        q_null = Question(
            question_text="Question with null stimulus",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="B",
            answer_options={"A": "1", "B": "2"},
            source_llm="test-llm",
            is_active=True,
            stimulus=None,
        )

        db_session.add(q_empty)
        db_session.add(q_null)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Find questions by text
        questions_by_text = {q["question_text"]: q for q in data["questions"]}

        if "Question with empty stimulus" in questions_by_text:
            # Empty string is still a string value
            assert questions_by_text["Question with empty stimulus"]["stimulus"] == ""

        if "Question with null stimulus" in questions_by_text:
            assert questions_by_text["Question with null stimulus"]["stimulus"] is None

    def test_long_stimulus_content_preserved(
        self, client, auth_headers, db_session, test_user
    ):
        """Test that long stimulus content is fully preserved."""
        # Create a very long stimulus (e.g., a passage to memorize)
        long_stimulus = "Lorem ipsum " * 100  # ~1200 characters

        question = Question(
            question_text="What phrase was repeated?",
            question_type=QuestionType.MEMORY,
            difficulty_level=DifficultyLevel.HARD,
            correct_answer="Lorem ipsum",
            answer_options={
                "A": "Lorem ipsum",
                "B": "Dolor sit",
                "C": "Amet consectetur",
                "D": "Adipiscing elit",
            },
            source_llm="test-llm",
            is_active=True,
            stimulus=long_stimulus,
        )
        db_session.add(question)
        db_session.commit()

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        memory_qs = [q for q in data["questions"] if q["question_type"] == "memory"]
        assert len(memory_qs) >= 1
        assert memory_qs[0]["stimulus"] == long_stimulus
        assert len(memory_qs[0]["stimulus"]) == len(long_stimulus)
