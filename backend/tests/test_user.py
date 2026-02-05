from sqlalchemy import select, func

"""
Tests for user profile endpoints.
"""


class TestGetUserProfile:
    """Tests for GET /v1/user/profile endpoint."""

    async def test_get_user_profile_success(self, client, auth_headers, test_user):
        """Test successfully retrieving user profile."""
        response = await client.get("/v1/user/profile", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["id"] == test_user.id
        assert data["email"] == "test@example.com"
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert "created_at" in data
        assert "last_login_at" in data
        assert data["notification_enabled"] is True

        # Verify sensitive data is not exposed
        assert "password" not in data
        assert "password_hash" not in data

    async def test_get_user_profile_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = await client.get("/v1/user/profile")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    async def test_get_user_profile_invalid_token(self, client):
        """Test that requests with invalid token are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await client.get("/v1/user/profile", headers=headers)

        assert response.status_code == 401

    async def test_get_user_profile_returns_latest_data(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that profile returns latest data from database."""
        from app.models import User

        # Update user in database
        _result = await db_session.execute(select(User).filter(User.id == test_user.id))
        user = _result.scalars().first()
        user.first_name = "Updated"
        await db_session.commit()

        # Get profile should return updated data
        response = await client.get("/v1/user/profile", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"


class TestUpdateUserProfile:
    """Tests for PUT /v1/user/profile endpoint."""

    async def test_update_user_profile_all_fields(
        self, client, auth_headers, test_user
    ):
        """Test updating all profile fields."""
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "notification_enabled": False,
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated fields
        assert data["first_name"] == "Updated"
        assert data["last_name"] == "Name"
        assert data["notification_enabled"] is False

        # Verify unchanged fields
        assert data["id"] == test_user.id
        assert data["email"] == "test@example.com"

    async def test_update_user_profile_first_name_only(
        self, client, auth_headers, test_user
    ):
        """Test updating only first name."""
        update_data = {
            "first_name": "NewFirstName",
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["first_name"] == "NewFirstName"

        # Verify other fields unchanged
        assert data["last_name"] == "User"  # Original value
        assert data["notification_enabled"] is True  # Original value

    async def test_update_user_profile_last_name_only(
        self, client, auth_headers, test_user
    ):
        """Test updating only last name."""
        update_data = {
            "last_name": "NewLastName",
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["last_name"] == "NewLastName"

        # Verify other fields unchanged
        assert data["first_name"] == "Test"  # Original value
        assert data["notification_enabled"] is True  # Original value

    async def test_update_user_profile_notification_only(
        self, client, auth_headers, test_user
    ):
        """Test updating only notification preference."""
        update_data = {
            "notification_enabled": False,
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["notification_enabled"] is False

        # Verify other fields unchanged
        assert data["first_name"] == "Test"  # Original value
        assert data["last_name"] == "User"  # Original value

    async def test_update_user_profile_toggle_notifications(
        self, client, auth_headers, test_user
    ):
        """Test toggling notifications on and off."""
        # First, turn off
        response1 = await client.put(
            "/v1/user/profile",
            json={"notification_enabled": False},
            headers=auth_headers,
        )
        assert response1.status_code == 200
        assert response1.json()["notification_enabled"] is False

        # Then, turn back on
        response2 = await client.put(
            "/v1/user/profile",
            json={"notification_enabled": True},
            headers=auth_headers,
        )
        assert response2.status_code == 200
        assert response2.json()["notification_enabled"] is True

    async def test_update_user_profile_empty_first_name_rejected(
        self, client, auth_headers
    ):
        """Test that empty first name is rejected."""
        update_data = {
            "first_name": "",
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    async def test_update_user_profile_empty_last_name_rejected(
        self, client, auth_headers
    ):
        """Test that empty last name is rejected."""
        update_data = {
            "last_name": "",
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    async def test_update_user_profile_name_too_long_rejected(
        self, client, auth_headers
    ):
        """Test that names longer than 100 characters are rejected."""
        update_data = {
            "first_name": "A" * 101,  # 101 characters
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    async def test_update_user_profile_name_max_length_accepted(
        self, client, auth_headers, test_user
    ):
        """Test that names with exactly 100 characters are accepted."""
        long_name = "A" * 100  # Exactly 100 characters
        update_data = {
            "first_name": long_name,
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["first_name"] == long_name

    async def test_update_user_profile_persisted_in_database(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that profile updates are persisted to database."""
        from app.models import User

        update_data = {
            "first_name": "Persisted",
            "last_name": "InDatabase",
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )
        assert response.status_code == 200

        # Verify in database
        db_session.expire_all()  # Clear cache
        _result = await db_session.execute(select(User).filter(User.id == test_user.id))
        user = _result.scalars().first()
        assert user.first_name == "Persisted"
        assert user.last_name == "InDatabase"

    async def test_update_user_profile_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        update_data = {
            "first_name": "NewName",
        }

        response = await client.put("/v1/user/profile", json=update_data)

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    async def test_update_user_profile_invalid_token(self, client):
        """Test that requests with invalid token are rejected."""
        update_data = {
            "first_name": "NewName",
        }

        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await client.put(
            "/v1/user/profile", json=update_data, headers=headers
        )

        assert response.status_code == 401

    async def test_update_user_profile_cannot_change_email(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that email cannot be changed through profile update."""
        from app.models import User

        # Try to include email in update (should be ignored)
        update_data = {
            "email": "newemail@example.com",  # Should be ignored
            "first_name": "Updated",
        }

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        # Should succeed but email unchanged
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"  # Original email
        assert data["first_name"] == "Updated"  # Other field updated

        # Verify in database
        db_session.expire_all()
        _result = await db_session.execute(select(User).filter(User.id == test_user.id))
        user = _result.scalars().first()
        assert user.email == "test@example.com"

    async def test_update_user_profile_empty_body_accepted(
        self, client, auth_headers, test_user
    ):
        """Test that empty update (no fields) is accepted."""
        update_data = {}

        response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        # Should succeed with no changes
        assert response.status_code == 200
        data = response.json()

        # All fields should be unchanged
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert data["notification_enabled"] is True

    async def test_update_user_profile_multiple_sequential_updates(
        self, client, auth_headers, test_user
    ):
        """Test multiple sequential profile updates."""
        # First update
        response1 = await client.put(
            "/v1/user/profile",
            json={"first_name": "First"},
            headers=auth_headers,
        )
        assert response1.status_code == 200
        assert response1.json()["first_name"] == "First"

        # Second update
        response2 = await client.put(
            "/v1/user/profile",
            json={"last_name": "Second"},
            headers=auth_headers,
        )
        assert response2.status_code == 200
        assert response2.json()["first_name"] == "First"  # Preserved from first update
        assert response2.json()["last_name"] == "Second"

        # Third update
        response3 = await client.put(
            "/v1/user/profile",
            json={"notification_enabled": False},
            headers=auth_headers,
        )
        assert response3.status_code == 200
        assert response3.json()["first_name"] == "First"  # Still preserved
        assert response3.json()["last_name"] == "Second"  # Still preserved
        assert response3.json()["notification_enabled"] is False


class TestUserProfileIntegration:
    """Integration tests for user profile functionality."""

    async def test_profile_updates_visible_immediately(
        self, client, auth_headers, test_user
    ):
        """Test that profile updates are visible immediately on GET."""
        # Update profile
        update_data = {
            "first_name": "Immediate",
            "notification_enabled": False,
        }

        update_response = await client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )
        assert update_response.status_code == 200

        # Immediately get profile
        get_response = await client.get("/v1/user/profile", headers=auth_headers)
        assert get_response.status_code == 200

        # Should see updated values
        data = get_response.json()
        assert data["first_name"] == "Immediate"
        assert data["notification_enabled"] is False

    async def test_different_users_profiles_isolated(
        self, client, test_user, db_session
    ):
        """Test that different users' profiles are properly isolated."""
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
        await db_session.commit()
        await db_session.refresh(user2)

        # Get tokens for both users
        token1 = create_access_token({"user_id": test_user.id})
        token2 = create_access_token({"user_id": user2.id})

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Update user1's profile
        await client.put(
            "/v1/user/profile",
            json={"first_name": "UpdatedUserOne"},
            headers=headers1,
        )

        # Update user2's profile
        await client.put(
            "/v1/user/profile",
            json={"first_name": "UpdatedUserTwo"},
            headers=headers2,
        )

        # Get both profiles
        profile1 = await client.get("/v1/user/profile", headers=headers1)
        profile2 = await client.get("/v1/user/profile", headers=headers2)

        # Verify isolation
        assert profile1.json()["first_name"] == "UpdatedUserOne"
        assert profile1.json()["email"] == "test@example.com"

        assert profile2.json()["first_name"] == "UpdatedUserTwo"
        assert profile2.json()["email"] == "user2@example.com"


class TestDeleteUserAccount:
    """Tests for DELETE /v1/user/delete-account endpoint."""

    async def test_delete_account_success(
        self, client, auth_headers, test_user, db_session
    ):
        """Test successful account deletion."""
        from app.models import User

        user_id = test_user.id

        response = await client.delete("/v1/user/delete-account", headers=auth_headers)

        assert response.status_code == 204
        # No content returned for 204
        assert response.text == ""

        # Verify user is deleted from database
        _result = await db_session.execute(select(User).filter(User.id == user_id))
        deleted_user = _result.scalars().first()
        assert deleted_user is None

    async def test_delete_account_deletes_test_sessions(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that account deletion cascades to test sessions."""
        from app.models import TestSession, TestStatus

        # Create test sessions for the user
        session1 = TestSession(
            user_id=test_user.id, status=TestStatus.IN_PROGRESS, composition_metadata={}
        )
        session2 = TestSession(
            user_id=test_user.id, status=TestStatus.COMPLETED, composition_metadata={}
        )
        db_session.add_all([session1, session2])
        await db_session.commit()

        session1_id = session1.id
        session2_id = session2.id

        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Verify test sessions are deleted
        _result = await db_session.execute(
            select(TestSession).filter(TestSession.id.in_([session1_id, session2_id]))
        )
        deleted_sessions = _result.scalars().all()
        assert len(deleted_sessions) == 0

    async def test_delete_account_deletes_responses(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that account deletion cascades to responses."""
        from app.models import (
            TestSession,
            Response,
            Question,
            DifficultyLevel,
            QuestionType,
            TestStatus,
        )

        # Create two questions
        question1 = Question(
            question_text="Test question 1",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        question2 = Question(
            question_text="Test question 2",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="B",
        )
        db_session.add_all([question1, question2])
        await db_session.commit()

        # Create test session and responses
        session = TestSession(
            user_id=test_user.id, status=TestStatus.IN_PROGRESS, composition_metadata={}
        )
        db_session.add(session)
        await db_session.commit()

        response1 = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question1.id,
            user_answer="A",
            is_correct=True,
        )
        response2 = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question2.id,
            user_answer="B",
            is_correct=False,
        )
        db_session.add_all([response1, response2])
        await db_session.commit()

        response1_id = response1.id
        response2_id = response2.id

        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Verify responses are deleted
        _result = await db_session.execute(
            select(Response).filter(Response.id.in_([response1_id, response2_id]))
        )
        deleted_responses = _result.scalars().all()
        assert len(deleted_responses) == 0

    async def test_delete_account_deletes_test_results(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that account deletion cascades to test results."""
        from app.models import TestSession, TestResult, TestStatus

        # Create test session and result
        session = TestSession(
            user_id=test_user.id, status=TestStatus.COMPLETED, composition_metadata={}
        )
        db_session.add(session)
        await db_session.commit()

        result = TestResult(
            test_session_id=session.id,
            user_id=test_user.id,
            iq_score=120,
            total_questions=20,
            correct_answers=15,
        )
        db_session.add(result)
        await db_session.commit()

        result_id = result.id

        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Verify test result is deleted
        _result = await db_session.execute(
            select(TestResult).filter(TestResult.id == result_id)
        )
        deleted_result = _result.scalars().first()
        assert deleted_result is None

    async def test_delete_account_deletes_user_questions(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that account deletion cascades to user_questions junction table."""
        from app.models import (
            Question,
            UserQuestion,
            QuestionType,
            DifficultyLevel,
        )

        # Create questions
        question1 = Question(
            question_text="Question 1",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        question2 = Question(
            question_text="Question 2",
            question_type=QuestionType.LOGIC,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="B",
        )
        db_session.add_all([question1, question2])
        await db_session.commit()

        # Create user-question associations
        uq1 = UserQuestion(user_id=test_user.id, question_id=question1.id)
        uq2 = UserQuestion(user_id=test_user.id, question_id=question2.id)
        db_session.add_all([uq1, uq2])
        await db_session.commit()

        uq1_id = uq1.id
        uq2_id = uq2.id

        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Verify user-question associations are deleted
        _result = await db_session.execute(
            select(UserQuestion).filter(UserQuestion.id.in_([uq1_id, uq2_id]))
        )
        deleted_uqs = _result.scalars().all()
        assert len(deleted_uqs) == 0

    async def test_delete_account_comprehensive_cascade(
        self, client, auth_headers, test_user, db_session
    ):
        """Test comprehensive cascade deletion of all user data."""
        from app.models import (
            User,
            TestSession,
            Response,
            TestResult,
            UserQuestion,
            Question,
            QuestionType,
            DifficultyLevel,
            TestStatus,
        )

        # Create question
        question = Question(
            question_text="Comprehensive test",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.MEDIUM,
            correct_answer="C",
        )
        db_session.add(question)
        await db_session.commit()

        # Create test session
        session = TestSession(
            user_id=test_user.id, status=TestStatus.COMPLETED, composition_metadata={}
        )
        db_session.add(session)
        await db_session.commit()

        # Create response
        response_obj = Response(
            test_session_id=session.id,
            user_id=test_user.id,
            question_id=question.id,
            user_answer="C",
            is_correct=True,
        )
        db_session.add(response_obj)
        await db_session.commit()

        # Create test result
        result = TestResult(
            test_session_id=session.id,
            user_id=test_user.id,
            iq_score=125,
            total_questions=10,
            correct_answers=8,
        )
        db_session.add(result)
        await db_session.commit()

        # Create user-question association
        uq = UserQuestion(user_id=test_user.id, question_id=question.id)
        db_session.add(uq)
        await db_session.commit()

        user_id = test_user.id

        # Count records before deletion
        _result = await db_session.execute(
            select(func.count())
            .select_from(TestSession)
            .filter(TestSession.user_id == user_id)
        )
        sessions_before = _result.scalar()
        _result = await db_session.execute(
            select(func.count())
            .select_from(Response)
            .filter(Response.user_id == user_id)
        )
        responses_before = _result.scalar()
        _result = await db_session.execute(
            select(func.count())
            .select_from(TestResult)
            .filter(TestResult.user_id == user_id)
        )
        results_before = _result.scalar()
        _result = await db_session.execute(
            select(func.count())
            .select_from(UserQuestion)
            .filter(UserQuestion.user_id == user_id)
        )
        uqs_before = _result.scalar()

        assert sessions_before > 0
        assert responses_before > 0
        assert results_before > 0
        assert uqs_before > 0

        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Verify ALL user data is deleted
        _result = await db_session.execute(select(User).filter(User.id == user_id))
        assert _result.scalars().first() is None
        _result = await db_session.execute(
            select(func.count())
            .select_from(TestSession)
            .filter(TestSession.user_id == user_id)
        )
        assert _result.scalar() == 0
        _result = await db_session.execute(
            select(func.count())
            .select_from(Response)
            .filter(Response.user_id == user_id)
        )
        assert _result.scalar() == 0
        _result = await db_session.execute(
            select(func.count())
            .select_from(TestResult)
            .filter(TestResult.user_id == user_id)
        )
        assert _result.scalar() == 0
        _result = await db_session.execute(
            select(func.count())
            .select_from(UserQuestion)
            .filter(UserQuestion.user_id == user_id)
        )
        assert _result.scalar() == 0

    async def test_delete_account_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = await client.delete("/v1/user/delete-account")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    async def test_delete_account_invalid_token(self, client):
        """Test that requests with invalid token are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = await client.delete("/v1/user/delete-account", headers=headers)

        assert response.status_code == 401

    async def test_delete_account_token_unusable_after_deletion(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that token cannot be used after account is deleted."""
        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Try to use the same token to access profile
        profile_response = await client.get("/v1/user/profile", headers=auth_headers)
        assert profile_response.status_code == 401

        # Try to use the same token to delete again
        delete_response = await client.delete(
            "/v1/user/delete-account", headers=auth_headers
        )
        assert delete_response.status_code == 401

    async def test_delete_account_different_users_isolated(
        self, client, test_user, db_session
    ):
        """Test that deleting one account doesn't affect other users."""
        from app.models import User, TestSession, TestStatus
        from app.core.security import hash_password, create_access_token

        # Create second user with test session
        user2 = User(
            email="user2@example.com",
            password_hash=hash_password("password123"),
            first_name="User",
            last_name="Two",
        )
        db_session.add(user2)
        await db_session.commit()
        await db_session.refresh(user2)

        session2 = TestSession(
            user_id=user2.id, status=TestStatus.IN_PROGRESS, composition_metadata={}
        )
        db_session.add(session2)
        await db_session.commit()

        user2_id = user2.id
        session2_id = session2.id

        # Delete first user's account
        token1 = create_access_token({"user_id": test_user.id})
        headers1 = {"Authorization": f"Bearer {token1}"}
        response = await client.delete("/v1/user/delete-account", headers=headers1)
        assert response.status_code == 204

        # Verify second user and their data still exist
        db_session.expire_all()
        _result = await db_session.execute(select(User).filter(User.id == user2_id))
        user2_still_exists = _result.scalars().first()
        assert user2_still_exists is not None

        _result = await db_session.execute(
            select(TestSession).filter(TestSession.id == session2_id)
        )
        session2_still_exists = _result.scalars().first()
        assert session2_still_exists is not None

    async def test_delete_account_does_not_delete_questions(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that deleting account doesn't delete questions (global resource)."""
        from app.models import Question, UserQuestion, QuestionType, DifficultyLevel

        # Create question and user-question association
        question = Question(
            question_text="Global question",
            question_type=QuestionType.PATTERN,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="A",
        )
        db_session.add(question)
        await db_session.commit()

        uq = UserQuestion(user_id=test_user.id, question_id=question.id)
        db_session.add(uq)
        await db_session.commit()

        question_id = question.id

        # Delete account
        response = await client.delete("/v1/user/delete-account", headers=auth_headers)
        assert response.status_code == 204

        # Verify question still exists (global resource, not user-specific)
        _result = await db_session.execute(
            select(Question).filter(Question.id == question_id)
        )
        question_still_exists = _result.scalars().first()
        assert question_still_exists is not None

    async def test_delete_account_database_error_returns_500(
        self, client, auth_headers
    ):
        """Test that database errors during deletion return 500."""
        from unittest.mock import patch
        from sqlalchemy.exc import SQLAlchemyError

        with patch("app.api.v1.user.Session.commit") as mock_commit:
            mock_commit.side_effect = SQLAlchemyError("Database write failed")
            response = await client.delete(
                "/v1/user/delete-account", headers=auth_headers
            )

            assert response.status_code == 500
            data = response.json()
            assert "delete user account" in data["detail"]
            assert "Please try again later" in data["detail"]
            # Verify error message is user-friendly (no raw exception details)
            assert "Database write failed" not in data["detail"]

    async def test_delete_account_database_error_triggers_rollback(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that database errors during deletion trigger rollback."""
        from unittest.mock import patch
        from sqlalchemy.exc import SQLAlchemyError
        from app.models import User

        user_id = test_user.id

        with patch("app.api.v1.user.Session.commit") as mock_commit:
            with patch("app.api.v1.user.Session.rollback") as mock_rollback:
                mock_commit.side_effect = SQLAlchemyError("Commit failed")
                response = await client.delete(
                    "/v1/user/delete-account", headers=auth_headers
                )

                assert response.status_code == 500
                # Verify rollback was called
                mock_rollback.assert_called_once()

        # Verify user still exists (rollback worked)
        db_session.expire_all()
        _result = await db_session.execute(select(User).filter(User.id == user_id))
        user_still_exists = _result.scalars().first()
        assert user_still_exists is not None

    async def test_delete_account_logs_deletion(self, client, auth_headers):
        """Test that account deletion is logged for audit trail."""
        from unittest.mock import patch

        with patch("app.api.v1.user.logger") as mock_logger:
            response = await client.delete(
                "/v1/user/delete-account", headers=auth_headers
            )

            assert response.status_code == 204
            # Verify success was logged
            mock_logger.info.assert_called_once()
            log_call_args = str(mock_logger.info.call_args)
            assert "User account deleted successfully" in log_call_args
            assert "user_id=" in log_call_args
