"""
Tests for question serving endpoints.
"""


class TestGetUnseenQuestions:
    """Tests for the GET /v1/questions/unseen endpoint."""

    def test_get_unseen_questions_success(self, client, auth_headers, test_questions):
        """Test successfully fetching unseen questions."""
        response = client.get("/v1/questions/unseen?count=3", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        assert "questions" in data
        assert "total_count" in data
        assert "requested_count" in data

        # Should return 3 questions (we have 4 active questions available)
        assert data["total_count"] == 3
        assert data["requested_count"] == 3
        assert len(data["questions"]) == 3

        # Verify question structure
        question = data["questions"][0]
        assert "id" in question
        assert "question_text" in question
        assert "question_type" in question
        assert "difficulty_level" in question
        assert "answer_options" in question

        # CRITICAL: Verify correct_answer is NOT returned
        assert "correct_answer" not in question

        # Verify explanation is not returned before submission
        assert question["explanation"] is None

    def test_get_unseen_questions_default_count(
        self, client, auth_headers, test_questions
    ):
        """Test fetching unseen questions with default count."""
        response = client.get("/v1/questions/unseen", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Default should be 20, but we only have 4 active questions
        assert data["requested_count"] == 20
        assert data["total_count"] == 4  # Only 4 active questions available
        assert len(data["questions"]) == 4

    def test_get_unseen_questions_filters_inactive(
        self, client, auth_headers, test_questions
    ):
        """Test that inactive questions are not returned."""
        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should only return 4 active questions, not 5
        assert data["total_count"] == 4

        # Verify no inactive questions are in the results
        question_texts = [q["question_text"] for q in data["questions"]]
        assert "Inactive question - should not appear" not in question_texts

    def test_get_unseen_questions_excludes_seen(
        self, client, auth_headers, test_questions, mark_questions_seen
    ):
        """Test that questions already seen by user are excluded."""
        # Mark first two questions as seen (indices 0 and 1)
        mark_questions_seen([0, 1])

        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Should return only 2 unseen questions (4 active - 2 seen = 2)
        assert data["total_count"] == 2
        assert len(data["questions"]) == 2

        # Verify the seen questions are not in the results
        returned_ids = [q["id"] for q in data["questions"]]
        assert test_questions[0].id not in returned_ids
        assert test_questions[1].id not in returned_ids

        # Verify unseen questions are present
        assert test_questions[2].id in returned_ids
        assert test_questions[3].id in returned_ids

    def test_get_unseen_questions_all_seen(
        self, client, auth_headers, test_questions, mark_questions_seen
    ):
        """Test response when all active questions have been seen."""
        # Mark all active questions as seen (indices 0, 1, 2, 3)
        mark_questions_seen([0, 1, 2, 3])

        response = client.get("/v1/questions/unseen", headers=auth_headers)

        # Should return 404 when no unseen questions are available
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "No unseen questions available" in data["detail"]

    def test_get_unseen_questions_count_validation(
        self, client, auth_headers, test_questions
    ):
        """Test count parameter validation."""
        # Test count = 0 (below minimum)
        response = client.get("/v1/questions/unseen?count=0", headers=auth_headers)
        assert response.status_code == 422  # Validation error

        # Test count = 101 (above maximum)
        response = client.get("/v1/questions/unseen?count=101", headers=auth_headers)
        assert response.status_code == 422  # Validation error

        # Test count = 1 (valid minimum)
        response = client.get("/v1/questions/unseen?count=1", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["total_count"] == 1

        # Test count = 100 (valid maximum)
        response = client.get("/v1/questions/unseen?count=100", headers=auth_headers)
        assert response.status_code == 200
        # Should return 4 (all available active questions)
        assert response.json()["total_count"] == 4

    def test_get_unseen_questions_requires_auth(self, client, test_questions):
        """Test that endpoint requires authentication."""
        response = client.get("/v1/questions/unseen")

        # Should return 401 or 403 for missing authentication
        assert response.status_code in [401, 403]

    def test_get_unseen_questions_invalid_token(self, client, test_questions):
        """Test that endpoint rejects invalid token."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/v1/questions/unseen", headers=headers)

        assert response.status_code == 401  # Unauthorized

    def test_get_unseen_questions_multiple_users(
        self, client, db_session, test_questions, mark_questions_seen
    ):
        """Test that seen questions are tracked per-user."""
        from app.models import User
        from app.core.security import hash_password, create_access_token

        # Create second user
        user2 = User(
            email="user2@example.com",
            password_hash=hash_password("password123"),
            first_name="User",
            last_name="Two",
        )
        db_session.add(user2)
        db_session.commit()
        db_session.refresh(user2)

        # Mark questions as seen for first user
        mark_questions_seen([0, 1])

        # Mark questions as seen for first user (need to get test_user from fixture)
        # Get test user ID from the database
        from app.models import User as UserModel

        test_user = (
            db_session.query(UserModel)
            .filter(UserModel.email == "test@example.com")
            .first()
        )

        # First user should see only 2 unseen questions
        user1_token = create_access_token({"user_id": test_user.id})
        response1 = client.get(
            "/v1/questions/unseen?count=10",
            headers={"Authorization": f"Bearer {user1_token}"},
        )
        assert response1.status_code == 200
        assert response1.json()["total_count"] == 2

        # Second user should see all 4 active questions
        user2_token = create_access_token({"user_id": user2.id})
        response2 = client.get(
            "/v1/questions/unseen?count=10",
            headers={"Authorization": f"Bearer {user2_token}"},
        )
        assert response2.status_code == 200
        assert response2.json()["total_count"] == 4

    def test_get_unseen_questions_response_format(
        self, client, auth_headers, test_questions
    ):
        """Test that response format matches schema."""
        response = client.get("/v1/questions/unseen?count=1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify top-level structure
        assert isinstance(data["questions"], list)
        assert isinstance(data["total_count"], int)
        assert isinstance(data["requested_count"], int)

        # Verify question structure
        question = data["questions"][0]
        assert isinstance(question["id"], int)
        assert isinstance(question["question_text"], str)
        assert isinstance(question["question_type"], str)
        assert isinstance(question["difficulty_level"], str)
        assert question["explanation"] is None

        # answer_options can be null or list
        assert question["answer_options"] is None or isinstance(
            question["answer_options"], list
        )

    def test_get_unseen_questions_question_types(
        self, client, auth_headers, test_questions
    ):
        """Test that various question types are returned correctly."""
        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # We have different question types in our test data
        question_types = [q["question_type"] for q in data["questions"]]

        # Verify we have different types
        assert "pattern" in question_types
        assert "logic" in question_types
        assert "math" in question_types
        assert "verbal" in question_types

    def test_get_unseen_questions_difficulty_levels(
        self, client, auth_headers, test_questions
    ):
        """Test that various difficulty levels are returned correctly."""
        response = client.get("/v1/questions/unseen?count=10", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # We have different difficulty levels in our test data
        difficulty_levels = [q["difficulty_level"] for q in data["questions"]]

        # Verify we have different difficulty levels
        assert "easy" in difficulty_levels
        assert "medium" in difficulty_levels
