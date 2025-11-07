"""
Tests for user profile endpoints.
"""


class TestGetUserProfile:
    """Tests for GET /v1/user/profile endpoint."""

    def test_get_user_profile_success(self, client, auth_headers, test_user):
        """Test successfully retrieving user profile."""
        response = client.get("/v1/user/profile", headers=auth_headers)

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

    def test_get_user_profile_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.get("/v1/user/profile")

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_get_user_profile_invalid_token(self, client):
        """Test that requests with invalid token are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get("/v1/user/profile", headers=headers)

        assert response.status_code == 401

    def test_get_user_profile_returns_latest_data(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that profile returns latest data from database."""
        from app.models import User

        # Update user in database
        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.first_name = "Updated"  # type: ignore
        db_session.commit()

        # Get profile should return updated data
        response = client.get("/v1/user/profile", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["first_name"] == "Updated"


class TestUpdateUserProfile:
    """Tests for PUT /v1/user/profile endpoint."""

    def test_update_user_profile_all_fields(self, client, auth_headers, test_user):
        """Test updating all profile fields."""
        update_data = {
            "first_name": "Updated",
            "last_name": "Name",
            "notification_enabled": False,
        }

        response = client.put(
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

    def test_update_user_profile_first_name_only(self, client, auth_headers, test_user):
        """Test updating only first name."""
        update_data = {
            "first_name": "NewFirstName",
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["first_name"] == "NewFirstName"

        # Verify other fields unchanged
        assert data["last_name"] == "User"  # Original value
        assert data["notification_enabled"] is True  # Original value

    def test_update_user_profile_last_name_only(self, client, auth_headers, test_user):
        """Test updating only last name."""
        update_data = {
            "last_name": "NewLastName",
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["last_name"] == "NewLastName"

        # Verify other fields unchanged
        assert data["first_name"] == "Test"  # Original value
        assert data["notification_enabled"] is True  # Original value

    def test_update_user_profile_notification_only(
        self, client, auth_headers, test_user
    ):
        """Test updating only notification preference."""
        update_data = {
            "notification_enabled": False,
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify updated field
        assert data["notification_enabled"] is False

        # Verify other fields unchanged
        assert data["first_name"] == "Test"  # Original value
        assert data["last_name"] == "User"  # Original value

    def test_update_user_profile_toggle_notifications(
        self, client, auth_headers, test_user
    ):
        """Test toggling notifications on and off."""
        # First, turn off
        response1 = client.put(
            "/v1/user/profile",
            json={"notification_enabled": False},
            headers=auth_headers,
        )
        assert response1.status_code == 200
        assert response1.json()["notification_enabled"] is False

        # Then, turn back on
        response2 = client.put(
            "/v1/user/profile",
            json={"notification_enabled": True},
            headers=auth_headers,
        )
        assert response2.status_code == 200
        assert response2.json()["notification_enabled"] is True

    def test_update_user_profile_empty_first_name_rejected(self, client, auth_headers):
        """Test that empty first name is rejected."""
        update_data = {
            "first_name": "",
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_update_user_profile_empty_last_name_rejected(self, client, auth_headers):
        """Test that empty last name is rejected."""
        update_data = {
            "last_name": "",
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_update_user_profile_name_too_long_rejected(self, client, auth_headers):
        """Test that names longer than 100 characters are rejected."""
        update_data = {
            "first_name": "A" * 101,  # 101 characters
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 422  # Validation error

    def test_update_user_profile_name_max_length_accepted(
        self, client, auth_headers, test_user
    ):
        """Test that names with exactly 100 characters are accepted."""
        long_name = "A" * 100  # Exactly 100 characters
        update_data = {
            "first_name": long_name,
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["first_name"] == long_name

    def test_update_user_profile_persisted_in_database(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that profile updates are persisted to database."""
        from app.models import User

        update_data = {
            "first_name": "Persisted",
            "last_name": "InDatabase",
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )
        assert response.status_code == 200

        # Verify in database
        db_session.expire_all()  # Clear cache
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.first_name == "Persisted"
        assert user.last_name == "InDatabase"

    def test_update_user_profile_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        update_data = {
            "first_name": "NewName",
        }

        response = client.put("/v1/user/profile", json=update_data)

        assert response.status_code == 403  # FastAPI returns 403 for missing auth

    def test_update_user_profile_invalid_token(self, client):
        """Test that requests with invalid token are rejected."""
        update_data = {
            "first_name": "NewName",
        }

        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.put("/v1/user/profile", json=update_data, headers=headers)

        assert response.status_code == 401

    def test_update_user_profile_cannot_change_email(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that email cannot be changed through profile update."""
        from app.models import User

        # Try to include email in update (should be ignored)
        update_data = {
            "email": "newemail@example.com",  # Should be ignored
            "first_name": "Updated",
        }

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        # Should succeed but email unchanged
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"  # Original email
        assert data["first_name"] == "Updated"  # Other field updated

        # Verify in database
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.email == "test@example.com"

    def test_update_user_profile_empty_body_accepted(
        self, client, auth_headers, test_user
    ):
        """Test that empty update (no fields) is accepted."""
        update_data = {}

        response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )

        # Should succeed with no changes
        assert response.status_code == 200
        data = response.json()

        # All fields should be unchanged
        assert data["first_name"] == "Test"
        assert data["last_name"] == "User"
        assert data["notification_enabled"] is True

    def test_update_user_profile_multiple_sequential_updates(
        self, client, auth_headers, test_user
    ):
        """Test multiple sequential profile updates."""
        # First update
        response1 = client.put(
            "/v1/user/profile",
            json={"first_name": "First"},
            headers=auth_headers,
        )
        assert response1.status_code == 200
        assert response1.json()["first_name"] == "First"

        # Second update
        response2 = client.put(
            "/v1/user/profile",
            json={"last_name": "Second"},
            headers=auth_headers,
        )
        assert response2.status_code == 200
        assert response2.json()["first_name"] == "First"  # Preserved from first update
        assert response2.json()["last_name"] == "Second"

        # Third update
        response3 = client.put(
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

    def test_profile_updates_visible_immediately(self, client, auth_headers, test_user):
        """Test that profile updates are visible immediately on GET."""
        # Update profile
        update_data = {
            "first_name": "Immediate",
            "notification_enabled": False,
        }

        update_response = client.put(
            "/v1/user/profile", json=update_data, headers=auth_headers
        )
        assert update_response.status_code == 200

        # Immediately get profile
        get_response = client.get("/v1/user/profile", headers=auth_headers)
        assert get_response.status_code == 200

        # Should see updated values
        data = get_response.json()
        assert data["first_name"] == "Immediate"
        assert data["notification_enabled"] is False

    def test_different_users_profiles_isolated(self, client, test_user, db_session):
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
        db_session.commit()
        db_session.refresh(user2)

        # Get tokens for both users
        token1 = create_access_token({"user_id": test_user.id})
        token2 = create_access_token({"user_id": user2.id})

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Update user1's profile
        client.put(
            "/v1/user/profile",
            json={"first_name": "UpdatedUserOne"},
            headers=headers1,
        )

        # Update user2's profile
        client.put(
            "/v1/user/profile",
            json={"first_name": "UpdatedUserTwo"},
            headers=headers2,
        )

        # Get both profiles
        profile1 = client.get("/v1/user/profile", headers=headers1)
        profile2 = client.get("/v1/user/profile", headers=headers2)

        # Verify isolation
        assert profile1.json()["first_name"] == "UpdatedUserOne"
        assert profile1.json()["email"] == "test@example.com"

        assert profile2.json()["first_name"] == "UpdatedUserTwo"
        assert profile2.json()["email"] == "user2@example.com"
