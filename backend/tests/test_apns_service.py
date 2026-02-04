"""
Tests for the Apple Push Notification service (APNs) integration.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.apns_service import (
    APNsService,
    send_logout_all_notification,
    send_test_reminder_notification,
)


class TestAPNsService:
    """Tests for the APNsService class."""

    def test_init_with_defaults(self):
        """Test APNsService initialization with default settings."""
        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "TESTKEY123"
            mock_settings.APNS_TEAM_ID = "TEAM123456"
            mock_settings.APNS_BUNDLE_ID = "com.example.app"
            mock_settings.APNS_KEY_PATH = "/path/to/key.p8"
            mock_settings.APNS_USE_SANDBOX = True

            service = APNsService()

            assert service.key_id == "TESTKEY123"
            assert service.team_id == "TEAM123456"
            assert service.bundle_id == "com.example.app"
            assert service.key_path == "/path/to/key.p8"
            assert service.use_sandbox is True

    def test_init_with_custom_values(self):
        """Test APNsService initialization with custom values."""
        service = APNsService(
            key_id="CUSTOM_KEY",
            team_id="CUSTOM_TEAM",
            bundle_id="com.custom.app",
            key_path="/custom/key.p8",
            use_sandbox=False,
        )

        assert service.key_id == "CUSTOM_KEY"
        assert service.team_id == "CUSTOM_TEAM"
        assert service.bundle_id == "com.custom.app"
        assert service.key_path == "/custom/key.p8"
        assert service.use_sandbox is False

    def test_validate_config_missing_key_id(self):
        """Test config validation fails when key_id is missing."""
        service = APNsService(
            key_id="", team_id="TEAM", bundle_id="com.app", key_path="/path"
        )

        with pytest.raises(ValueError, match="APNS_KEY_ID is required"):
            service._validate_config()

    def test_validate_config_missing_team_id(self):
        """Test config validation fails when team_id is missing."""
        service = APNsService(
            key_id="KEY", team_id="", bundle_id="com.app", key_path="/path"
        )

        with pytest.raises(ValueError, match="APNS_TEAM_ID is required"):
            service._validate_config()

    def test_validate_config_missing_bundle_id(self):
        """Test config validation fails when bundle_id is missing."""
        service = APNsService(
            key_id="KEY", team_id="TEAM", bundle_id="", key_path="/path"
        )

        with pytest.raises(ValueError, match="APNS_BUNDLE_ID is required"):
            service._validate_config()

    def test_validate_config_missing_key_path(self):
        """Test config validation fails when key_path is missing."""
        service = APNsService(
            key_id="KEY", team_id="TEAM", bundle_id="com.app", key_path=""
        )

        with pytest.raises(ValueError, match="APNS_KEY_PATH is required"):
            service._validate_config()

    def test_validate_config_key_file_not_exists(self, tmp_path):
        """Test config validation fails when key file doesn't exist."""
        non_existent_path = str(tmp_path / "nonexistent.p8")
        service = APNsService(
            key_id="KEY",
            team_id="TEAM",
            bundle_id="com.app",
            key_path=non_existent_path,
        )

        with pytest.raises(ValueError, match="APNs key file not found"):
            service._validate_config()

    def test_validate_config_key_path_not_file(self, tmp_path):
        """Test config validation fails when key path is a directory."""
        directory_path = tmp_path / "directory"
        directory_path.mkdir()

        service = APNsService(
            key_id="KEY",
            team_id="TEAM",
            bundle_id="com.app",
            key_path=str(directory_path),
        )

        with pytest.raises(ValueError, match="APNs key path is not a file"):
            service._validate_config()

    def test_validate_config_success(self, tmp_path):
        """Test config validation succeeds with valid configuration."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        service = APNsService(
            key_id="KEY",
            team_id="TEAM",
            bundle_id="com.app",
            key_path=str(key_file),
        )

        # Should not raise any exception
        service._validate_config()

    @pytest.mark.asyncio
    async def test_connect_success(self, tmp_path):
        """Test successful connection to APNs."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        service = APNsService(
            key_id="KEY123456",
            team_id="TEAM123456",
            bundle_id="com.test.app",
            key_path=str(key_file),
            use_sandbox=True,
        )

        with patch("app.services.apns_service.APNs") as mock_apns:
            await service.connect()

            # Verify APNs was instantiated with correct parameters
            mock_apns.assert_called_once_with(
                key=str(key_file),
                key_id="KEY123456",
                team_id="TEAM123456",
                topic="com.test.app",
                use_sandbox=True,
            )

            # Verify client was set
            assert service._client is not None

    @pytest.mark.asyncio
    async def test_connect_validation_error(self):
        """Test connection fails when configuration is invalid."""
        service = APNsService(key_id="", team_id="", bundle_id="", key_path="")

        with pytest.raises(ValueError):
            await service.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, tmp_path):
        """Test disconnecting from APNs."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        service = APNsService(
            key_id="KEY",
            team_id="TEAM",
            bundle_id="com.app",
            key_path=str(key_file),
        )

        # Mock the client
        mock_client = AsyncMock()
        service._client = mock_client

        await service.disconnect()

        # Verify close was called
        mock_client.close.assert_called_once()

        # Verify client was cleared
        assert service._client is None

    @pytest.mark.asyncio
    async def test_send_notification_not_connected(self):
        """Test sending notification fails when not connected."""
        service = APNsService()

        result = await service.send_notification(
            device_token="test_token", title="Test", body="Test message"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_notification_success(self):
        """Test successful notification sending."""
        service = APNsService()

        # Mock the client
        mock_client = AsyncMock()
        service._client = mock_client

        result = await service.send_notification(
            device_token="abc123def456",
            title="Test Title",
            body="Test Body",
            badge=5,
            sound="custom_sound.aiff",
            data={"custom_key": "custom_value"},
        )

        assert result is True

        # Verify send_notification was called
        mock_client.send_notification.assert_called_once()

        # Get the notification request that was passed
        call_args = mock_client.send_notification.call_args
        request = call_args[0][0]

        # Verify the request properties
        assert request.device_token == "abc123def456"
        assert request.message["aps"]["alert"]["title"] == "Test Title"
        assert request.message["aps"]["alert"]["body"] == "Test Body"
        assert request.message["aps"]["badge"] == 5
        assert request.message["aps"]["sound"] == "custom_sound.aiff"
        assert request.message["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_send_notification_without_optional_fields(self):
        """Test notification sending with only required fields."""
        service = APNsService()

        # Mock the client
        mock_client = AsyncMock()
        service._client = mock_client

        result = await service.send_notification(
            device_token="abc123def456",
            title="Test Title",
            body="Test Body",
        )

        assert result is True

        # Get the notification request
        call_args = mock_client.send_notification.call_args
        request = call_args[0][0]

        # Verify no badge was set
        assert "badge" not in request.message["aps"]

        # Verify default sound was used
        assert request.message["aps"]["sound"] == "default"

    @pytest.mark.asyncio
    async def test_send_notification_exception(self):
        """Test notification sending handles exceptions gracefully."""
        service = APNsService()

        # Mock the client to raise an exception
        mock_client = AsyncMock()
        mock_client.send_notification.side_effect = Exception("APNs error")
        service._client = mock_client

        result = await service.send_notification(
            device_token="abc123def456", title="Test", body="Test"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_send_batch_notifications_not_connected(self):
        """Test batch sending fails when not connected."""
        service = APNsService()

        notifications = [
            {"device_token": "token1", "title": "Test", "body": "Test"},
            {"device_token": "token2", "title": "Test", "body": "Test"},
        ]

        result = await service.send_batch_notifications(notifications)

        assert result["success"] == 0
        assert result["failed"] == 2

    @pytest.mark.asyncio
    async def test_send_batch_notifications_success(self):
        """Test successful batch notification sending."""
        service = APNsService()

        # Mock the client
        mock_client = AsyncMock()
        service._client = mock_client

        notifications = [
            {"device_token": "token1", "title": "Test 1", "body": "Body 1"},
            {"device_token": "token2", "title": "Test 2", "body": "Body 2"},
            {"device_token": "token3", "title": "Test 3", "body": "Body 3"},
        ]

        result = await service.send_batch_notifications(notifications)

        assert result["success"] == 3
        assert result["failed"] == 0

        # Verify send_notification was called 3 times
        assert mock_client.send_notification.call_count == 3

    @pytest.mark.asyncio
    async def test_send_batch_notifications_partial_failure(self):
        """Test batch sending with some failures."""
        service = APNsService()

        # Mock the client to fail on second call
        mock_client = AsyncMock()
        mock_client.send_notification.side_effect = [
            None,  # First call succeeds
            Exception("APNs error"),  # Second call fails
            None,  # Third call succeeds
        ]
        service._client = mock_client

        notifications = [
            {"device_token": "token1", "title": "Test 1", "body": "Body 1"},
            {"device_token": "token2", "title": "Test 2", "body": "Body 2"},
            {"device_token": "token3", "title": "Test 3", "body": "Body 3"},
        ]

        result = await service.send_batch_notifications(notifications)

        assert result["success"] == 2
        assert result["failed"] == 1

    @pytest.mark.asyncio
    async def test_send_batch_notifications_with_custom_fields(self):
        """Test batch sending with custom fields."""
        service = APNsService()

        # Mock the client
        mock_client = AsyncMock()
        service._client = mock_client

        notifications = [
            {
                "device_token": "token1",
                "title": "Test",
                "body": "Body",
                "badge": 3,
                "sound": "custom.aiff",
                "data": {"key": "value"},
            }
        ]

        result = await service.send_batch_notifications(notifications)

        assert result["success"] == 1
        assert result["failed"] == 0


class TestSendTestReminderNotification:
    """Tests for the send_test_reminder_notification convenience function."""

    @pytest.mark.asyncio
    async def test_send_test_reminder_without_name(self, tmp_path):
        """Test sending test reminder without user name."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns_instance = AsyncMock()
                mock_apns.return_value = mock_apns_instance

                result = await send_test_reminder_notification(
                    device_token="test_token"
                )

                assert result is True

                # Verify notification was sent
                mock_apns_instance.send_notification.assert_called_once()

                # Verify close was called
                mock_apns_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_test_reminder_with_name(self, tmp_path):
        """Test sending test reminder with user name."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns_instance = AsyncMock()
                mock_apns.return_value = mock_apns_instance

                result = await send_test_reminder_notification(
                    device_token="test_token", user_name="John"
                )

                assert result is True

                # Get the notification request
                call_args = mock_apns_instance.send_notification.call_args
                request = call_args[0][0]

                # Verify user name is in the body
                body = request.message["aps"]["alert"]["body"]
                assert "John" in body

    @pytest.mark.asyncio
    async def test_send_test_reminder_disconnect_on_error(self, tmp_path):
        """Test that disconnect is called even when sending fails."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns_instance = AsyncMock()
                mock_apns_instance.send_notification.side_effect = Exception(
                    "APNs error"
                )
                mock_apns.return_value = mock_apns_instance

                result = await send_test_reminder_notification(
                    device_token="test_token"
                )

                assert result is False

                # Verify close was still called
                mock_apns_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_test_reminder_logs_exception_on_connect_error(self, tmp_path):
        """Test that send_test_reminder_notification logs exceptions with logger.exception when connect fails."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns.side_effect = Exception("Connection failed")

                with patch("app.services.apns_service.logger") as mock_logger:
                    result = await send_test_reminder_notification(
                        device_token="test_token_123"
                    )

                    assert result is False
                    mock_logger.exception.assert_called_once_with(
                        "Failed to send test reminder notification (device_token_prefix=test_token_1)"
                    )


class TestSendLogoutAllNotification:
    """Tests for the send_logout_all_notification convenience function."""

    @pytest.mark.asyncio
    async def test_send_logout_all_success(self, tmp_path):
        """Test successful send_logout_all_notification sends correct payload and disconnects."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns_instance = AsyncMock()
                mock_apns.return_value = mock_apns_instance

                result = await send_logout_all_notification(
                    device_token="test_token_123", user_id=42
                )

                assert result is True

                # Verify notification was sent with correct payload
                mock_apns_instance.send_notification.assert_called_once()
                call_args = mock_apns_instance.send_notification.call_args
                request = call_args[0][0]
                assert request.device_token == "test_token_123"
                assert request.message["aps"]["alert"]["title"] == "Security Alert"
                assert "logged out" in request.message["aps"]["alert"]["body"]
                assert request.message["aps"]["sound"] == "default"
                assert request.message["type"] == "logout_all"
                assert request.message["deep_link"] == "aiq://login"

                # Verify disconnect was called
                mock_apns_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_logout_all_disconnect_on_error(self, tmp_path):
        """Test that disconnect is called even when sending fails."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns_instance = AsyncMock()
                mock_apns_instance.send_notification.side_effect = Exception(
                    "APNs error"
                )
                mock_apns.return_value = mock_apns_instance

                result = await send_logout_all_notification(
                    device_token="test_token_123", user_id=42
                )

                assert result is False

                # Verify close was still called despite the error
                mock_apns_instance.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_logout_all_logs_exception_on_connect_error(self, tmp_path):
        """Test that send_logout_all_notification logs exceptions with logger.exception when connect fails."""
        key_file = tmp_path / "test_key.p8"
        key_file.write_text("fake key content")

        with patch("app.services.apns_service.settings") as mock_settings:
            mock_settings.APNS_KEY_ID = "KEY"
            mock_settings.APNS_TEAM_ID = "TEAM"
            mock_settings.APNS_BUNDLE_ID = "com.app"
            mock_settings.APNS_KEY_PATH = str(key_file)
            mock_settings.APNS_USE_SANDBOX = True

            with patch("app.services.apns_service.APNs") as mock_apns:
                mock_apns.side_effect = Exception("Connection failed")

                with patch("app.services.apns_service.logger") as mock_logger:
                    result = await send_logout_all_notification(
                        device_token="test_token_123", user_id=42
                    )

                    assert result is False
                    mock_logger.exception.assert_called_once_with(
                        "Failed to send logout-all notification (user_id=42, device_token_prefix=test_token_1)"
                    )
