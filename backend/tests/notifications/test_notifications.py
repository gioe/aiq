"""
Tests for notification endpoints.
"""


class TestRegisterDeviceToken:
    """Tests for POST /v1/notifications/register-device endpoint."""

    def test_register_device_token_success(self, client, auth_headers, test_user):
        """Test successfully registering a device token."""
        device_token = "a" * 64  # Valid 64-character hex string

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "registered successfully" in data["message"].lower()

    def test_register_device_token_updates_existing(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that registering a token updates an existing token."""
        from app.models import User

        # Register first token
        token1 = "a" * 64
        response1 = client.post(
            "/v1/notifications/register-device",
            json={"device_token": token1},
            headers=auth_headers,
        )
        assert response1.status_code == 200

        # Register second token (should replace first)
        token2 = "b" * 64
        response2 = client.post(
            "/v1/notifications/register-device",
            json={"device_token": token2},
            headers=auth_headers,
        )
        assert response2.status_code == 200

        # Verify in database that only second token is stored
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token == token2

    def test_register_device_token_persisted_in_database(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that device token is persisted to database."""
        from app.models import User

        device_token = "c" * 64
        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify in database
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token == device_token

    def test_register_device_token_normalized_to_lowercase(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that device token is normalized to lowercase."""
        from app.models import User

        device_token_upper = "ABCDEF" * 10 + "ABCD"  # 64 chars uppercase
        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token_upper},
            headers=auth_headers,
        )
        assert response.status_code == 200

        # Verify stored as lowercase
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token == device_token_upper.lower()

    def test_register_device_token_too_short(self, client, auth_headers):
        """Test that tokens shorter than 64 characters are rejected."""
        device_token = "a" * 63  # 63 characters (too short)

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_register_device_token_too_long(self, client, auth_headers):
        """Test that tokens longer than 200 characters are rejected."""
        device_token = "a" * 201  # 201 characters (too long)

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_register_device_token_invalid_characters(self, client, auth_headers):
        """Test that tokens with non-hex characters are rejected."""
        device_token = "xyz" + "a" * 61  # Contains non-hex characters

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_register_device_token_with_spaces(self, client, auth_headers):
        """Test that tokens with spaces are rejected."""
        device_token = "a" * 32 + " " + "b" * 31  # 64 chars with space

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_register_device_token_empty_string(self, client, auth_headers):
        """Test that empty device token is rejected."""
        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": ""},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_register_device_token_missing_field(self, client, auth_headers):
        """Test that missing device_token field is rejected."""
        response = client.post(
            "/v1/notifications/register-device",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_register_device_token_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        device_token = "a" * 64

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
        )

        assert response.status_code == 403  # Missing auth

    def test_register_device_token_invalid_token(self, client):
        """Test that requests with invalid auth token are rejected."""
        device_token = "a" * 64
        headers = {"Authorization": "Bearer invalid_token_here"}

        response = client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=headers,
        )

        assert response.status_code == 401


class TestUnregisterDeviceToken:
    """Tests for DELETE /v1/notifications/register-device endpoint."""

    def test_unregister_device_token_success(
        self, client, auth_headers, test_user, db_session
    ):
        """Test successfully unregistering a device token."""
        from app.models import User

        # First, register a token
        device_token = "a" * 64
        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        # Verify token is registered
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token == device_token

        # Now unregister
        response = client.delete(
            "/v1/notifications/register-device",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "unregistered successfully" in data["message"].lower()

        # Verify token is removed
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token is None

    def test_unregister_device_token_when_none_registered(
        self, client, auth_headers, test_user, db_session
    ):
        """Test unregistering when no token is registered."""
        from app.models import User

        # Verify no token is registered
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token is None

        # Try to unregister anyway (should succeed)
        response = client.delete(
            "/v1/notifications/register-device",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_unregister_device_token_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.delete("/v1/notifications/register-device")

        assert response.status_code == 403  # Missing auth

    def test_unregister_device_token_invalid_token(self, client):
        """Test that requests with invalid auth token are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.delete(
            "/v1/notifications/register-device",
            headers=headers,
        )

        assert response.status_code == 401


class TestUpdateNotificationPreferences:
    """Tests for PUT /v1/notifications/preferences endpoint."""

    def test_update_notification_preferences_enable(
        self, client, auth_headers, test_user, db_session
    ):
        """Test enabling notification preferences."""
        from app.models import User

        # Disable first
        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.notification_enabled = False
        db_session.commit()

        # Enable via API
        response = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notification_enabled"] is True
        assert "updated successfully" in data["message"].lower()

        # Verify in database
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.notification_enabled is True

    def test_update_notification_preferences_disable(
        self, client, auth_headers, test_user, db_session
    ):
        """Test disabling notification preferences."""
        from app.models import User

        # Disable via API
        response = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notification_enabled"] is False

        # Verify in database
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.notification_enabled is False

    def test_update_notification_preferences_toggle(
        self, client, auth_headers, test_user
    ):
        """Test toggling notification preferences multiple times."""
        # Disable
        response1 = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=auth_headers,
        )
        assert response1.status_code == 200
        assert response1.json()["notification_enabled"] is False

        # Enable
        response2 = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": True},
            headers=auth_headers,
        )
        assert response2.status_code == 200
        assert response2.json()["notification_enabled"] is True

        # Disable again
        response3 = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=auth_headers,
        )
        assert response3.status_code == 200
        assert response3.json()["notification_enabled"] is False

    def test_update_notification_preferences_missing_field(self, client, auth_headers):
        """Test that missing notification_enabled field is rejected."""
        response = client.put(
            "/v1/notifications/preferences",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 422  # Validation error

    def test_update_notification_preferences_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
        )

        assert response.status_code == 403  # Missing auth

    def test_update_notification_preferences_invalid_token(self, client):
        """Test that requests with invalid auth token are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=headers,
        )

        assert response.status_code == 401


class TestGetNotificationPreferences:
    """Tests for GET /v1/notifications/preferences endpoint."""

    def test_get_notification_preferences_enabled(
        self, client, auth_headers, test_user
    ):
        """Test getting notification preferences when enabled."""
        response = client.get(
            "/v1/notifications/preferences",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notification_enabled"] is True
        assert "retrieved successfully" in data["message"].lower()

    def test_get_notification_preferences_disabled(
        self, client, auth_headers, test_user, db_session
    ):
        """Test getting notification preferences when disabled."""
        from app.models import User

        # Disable notifications
        user = db_session.query(User).filter(User.id == test_user.id).first()
        user.notification_enabled = False
        db_session.commit()

        response = client.get(
            "/v1/notifications/preferences",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["notification_enabled"] is False

    def test_get_notification_preferences_unauthenticated(self, client):
        """Test that unauthenticated requests are rejected."""
        response = client.get("/v1/notifications/preferences")

        assert response.status_code == 403  # Missing auth

    def test_get_notification_preferences_invalid_token(self, client):
        """Test that requests with invalid auth token are rejected."""
        headers = {"Authorization": "Bearer invalid_token_here"}
        response = client.get(
            "/v1/notifications/preferences",
            headers=headers,
        )

        assert response.status_code == 401


class TestNotificationIntegration:
    """Integration tests for notification functionality."""

    def test_register_token_and_disable_notifications_independently(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that device token and notification preference are independent."""
        from app.models import User

        # Register device token
        device_token = "a" * 64
        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )

        # Disable notifications
        client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=auth_headers,
        )

        # Verify both settings in database
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token == device_token
        assert user.notification_enabled is False

    def test_unregister_token_keeps_notification_preference(
        self, client, auth_headers, test_user, db_session
    ):
        """Test that unregistering token doesn't change notification preference."""
        from app.models import User

        # Register token and disable notifications
        device_token = "a" * 64
        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token},
            headers=auth_headers,
        )
        client.put(
            "/v1/notifications/preferences",
            json={"notification_enabled": False},
            headers=auth_headers,
        )

        # Unregister token
        client.delete(
            "/v1/notifications/register-device",
            headers=auth_headers,
        )

        # Verify token removed but preference unchanged
        db_session.expire_all()
        user = db_session.query(User).filter(User.id == test_user.id).first()
        assert user.apns_device_token is None
        assert user.notification_enabled is False

    def test_different_users_tokens_isolated(self, client, test_user, db_session):
        """Test that different users' device tokens are properly isolated."""
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

        # Register different device tokens
        device_token1 = "a" * 64
        device_token2 = "b" * 64

        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token1},
            headers=headers1,
        )
        client.post(
            "/v1/notifications/register-device",
            json={"device_token": device_token2},
            headers=headers2,
        )

        # Verify isolation
        db_session.expire_all()
        user1_db = db_session.query(User).filter(User.id == test_user.id).first()
        user2_db = db_session.query(User).filter(User.id == user2.id).first()

        assert user1_db.apns_device_token == device_token1
        assert user2_db.apns_device_token == device_token2
