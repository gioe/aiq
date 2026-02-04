"""
Tests for notification delivery tracking metrics.

Verifies that analytics events (NOTIFICATION_SENT, NOTIFICATION_FAILED)
are emitted when notifications are sent or fail.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.core.analytics import AnalyticsTracker, EventType
from app.services.apns_service import (
    APNsService,
    send_test_reminder_notification,
    send_logout_all_notification,
)


class TestAnalyticsTrackerNotificationMethods:
    """Tests for the AnalyticsTracker notification tracking methods."""

    def test_track_notification_sent(self):
        """Test track_notification_sent emits correct event."""
        with patch.object(AnalyticsTracker, "track_event") as mock_track:
            AnalyticsTracker.track_notification_sent(
                notification_type="logout_all",
                user_id=42,
                device_token_prefix="abc12345",
            )

            mock_track.assert_called_once_with(
                EventType.NOTIFICATION_SENT,
                user_id=42,
                properties={
                    "notification_type": "logout_all",
                    "device_token_prefix": "abc12345",
                },
            )

    def test_track_notification_failed(self):
        """Test track_notification_failed emits correct event."""
        with patch.object(AnalyticsTracker, "track_event") as mock_track:
            AnalyticsTracker.track_notification_failed(
                notification_type="test_reminder",
                error="Connection refused",
                user_id=7,
                device_token_prefix="def67890",
            )

            mock_track.assert_called_once_with(
                EventType.NOTIFICATION_FAILED,
                user_id=7,
                properties={
                    "notification_type": "test_reminder",
                    "error": "Connection refused",
                    "device_token_prefix": "def67890",
                },
            )

    def test_track_notification_sent_without_optional_fields(self):
        """Test track_notification_sent works with only required fields."""
        with patch.object(AnalyticsTracker, "track_event") as mock_track:
            AnalyticsTracker.track_notification_sent(
                notification_type="day_30_reminder",
            )

            mock_track.assert_called_once_with(
                EventType.NOTIFICATION_SENT,
                user_id=None,
                properties={
                    "notification_type": "day_30_reminder",
                    "device_token_prefix": None,
                },
            )


class TestAPNsServiceDeliveryTracking:
    """Tests for analytics tracking in APNsService.send_notification."""

    @pytest.mark.asyncio
    async def test_send_notification_tracks_success_with_user_id(self):
        """Test that successful send emits NOTIFICATION_SENT with user_id."""
        service = APNsService()
        mock_client = AsyncMock()
        service._client = mock_client

        with patch.object(AnalyticsTracker, "track_notification_sent") as mock_sent:
            result = await service.send_notification(
                device_token="abc123def456gh",
                title="Test",
                body="Test body",
                notification_type="logout_all",
                user_id=42,
            )

            assert result is True
            mock_sent.assert_called_once_with(
                notification_type="logout_all",
                user_id=42,
                device_token_prefix="abc123def456",  # pragma: allowlist secret
            )

    @pytest.mark.asyncio
    async def test_send_notification_tracks_success_without_user_id(self):
        """Test that successful send emits NOTIFICATION_SENT with user_id=None."""
        service = APNsService()
        mock_client = AsyncMock()
        service._client = mock_client

        with patch.object(AnalyticsTracker, "track_notification_sent") as mock_sent:
            result = await service.send_notification(
                device_token="abc123def456gh",
                title="Test",
                body="Test body",
                notification_type="logout_all",
            )

            assert result is True
            mock_sent.assert_called_once_with(
                notification_type="logout_all",
                user_id=None,
                device_token_prefix="abc123def456",  # pragma: allowlist secret
            )

    @pytest.mark.asyncio
    async def test_send_notification_tracks_failure_with_user_id(self):
        """Test that failed send emits NOTIFICATION_FAILED with user_id."""
        service = APNsService()
        mock_client = AsyncMock()
        mock_client.send_notification.side_effect = Exception("APNs error")
        service._client = mock_client

        with patch.object(AnalyticsTracker, "track_notification_failed") as mock_failed:
            result = await service.send_notification(
                device_token="abc123def456gh",
                title="Test",
                body="Test body",
                notification_type="test_reminder",
                user_id=7,
            )

            assert result is False
            mock_failed.assert_called_once_with(
                notification_type="test_reminder",
                error="APNs error",
                user_id=7,
                device_token_prefix="abc123def456",  # pragma: allowlist secret
            )

    @pytest.mark.asyncio
    async def test_send_notification_no_tracking_without_type(self):
        """Test that no analytics events are emitted when notification_type is None."""
        service = APNsService()
        mock_client = AsyncMock()
        service._client = mock_client

        with patch.object(AnalyticsTracker, "track_notification_sent") as mock_sent:
            with patch.object(
                AnalyticsTracker, "track_notification_failed"
            ) as mock_failed:
                result = await service.send_notification(
                    device_token="abc123def456gh",
                    title="Test",
                    body="Test body",
                )

                assert result is True
                mock_sent.assert_not_called()
                mock_failed.assert_not_called()

    @pytest.mark.asyncio
    async def test_send_notification_no_tracking_on_failure_without_type(self):
        """Test no analytics on failure when notification_type is None."""
        service = APNsService()
        mock_client = AsyncMock()
        mock_client.send_notification.side_effect = Exception("error")
        service._client = mock_client

        with patch.object(AnalyticsTracker, "track_notification_failed") as mock_failed:
            result = await service.send_notification(
                device_token="abc123def456gh",
                title="Test",
                body="Test body",
            )

            assert result is False
            mock_failed.assert_not_called()


class TestBatchNotificationDeliveryTracking:
    """Tests for analytics tracking in batch notification sending."""

    @pytest.mark.asyncio
    async def test_batch_notifications_track_per_notification(self):
        """Test that batch send tracks each notification individually."""
        service = APNsService()
        mock_client = AsyncMock()
        service._client = mock_client

        notifications = [
            {"device_token": "token1aaa", "title": "T1", "body": "B1", "user_id": 1},
            {"device_token": "token2bbb", "title": "T2", "body": "B2", "user_id": 2},
        ]

        with patch.object(AnalyticsTracker, "track_notification_sent") as mock_sent:
            result = await service.send_batch_notifications(
                notifications, notification_type="test_reminder"
            )

            assert result["success"] == 2
            assert result["failed"] == 0
            assert mock_sent.call_count == 2

    @pytest.mark.asyncio
    async def test_batch_notifications_pass_user_id(self):
        """Test that batch send passes user_id from notification dict to analytics."""
        service = APNsService()
        mock_client = AsyncMock()
        service._client = mock_client

        notifications = [
            {"device_token": "token1aaa", "title": "T1", "body": "B1", "user_id": 99},
        ]

        with patch.object(AnalyticsTracker, "track_notification_sent") as mock_sent:
            await service.send_batch_notifications(
                notifications, notification_type="test_reminder"
            )

            mock_sent.assert_called_once_with(
                notification_type="test_reminder",
                user_id=99,
                device_token_prefix="token1aaa",
            )

    @pytest.mark.asyncio
    async def test_batch_notifications_track_mixed_outcomes(self):
        """Test batch send tracks both successes and failures."""
        service = APNsService()
        mock_client = AsyncMock()
        mock_client.send_notification.side_effect = [
            None,  # success
            Exception("APNs error"),  # failure
        ]
        service._client = mock_client

        notifications = [
            {"device_token": "token1aaa", "title": "T1", "body": "B1"},
            {"device_token": "token2bbb", "title": "T2", "body": "B2"},
        ]

        with patch.object(AnalyticsTracker, "track_notification_sent") as mock_sent:
            with patch.object(
                AnalyticsTracker, "track_notification_failed"
            ) as mock_failed:
                result = await service.send_batch_notifications(
                    notifications, notification_type="test_reminder"
                )

                assert result["success"] == 1
                assert result["failed"] == 1
                mock_sent.assert_called_once()
                mock_failed.assert_called_once()


class TestConvenienceFunctionTracking:
    """Tests for analytics tracking in convenience functions."""

    @pytest.mark.asyncio
    async def test_send_logout_all_notification_tracks_with_user_id(self, tmp_path):
        """Test that send_logout_all_notification passes user_id to analytics."""
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

                with patch.object(
                    AnalyticsTracker, "track_notification_sent"
                ) as mock_sent:
                    result = await send_logout_all_notification(
                        device_token="test_token_abc123",
                        user_id=42,
                    )

                    assert result is True
                    mock_sent.assert_called_once_with(
                        notification_type="logout_all",
                        user_id=42,
                        device_token_prefix="test_token_a",
                    )

    @pytest.mark.asyncio
    async def test_send_logout_all_notification_tracks_failure_with_user_id(
        self, tmp_path
    ):
        """Test that send_logout_all_notification tracks failure with user_id."""
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
                    "Connection refused"
                )
                mock_apns.return_value = mock_apns_instance

                with patch.object(
                    AnalyticsTracker, "track_notification_failed"
                ) as mock_failed:
                    result = await send_logout_all_notification(
                        device_token="test_token_abc123",
                        user_id=42,
                    )

                    assert result is False
                    mock_failed.assert_called_once_with(
                        notification_type="logout_all",
                        error="Connection refused",
                        user_id=42,
                        device_token_prefix="test_token_a",
                    )

    @pytest.mark.asyncio
    async def test_send_logout_all_without_user_id(self, tmp_path):
        """Test that send_logout_all_notification works without user_id (backward compat)."""
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

                with patch.object(
                    AnalyticsTracker, "track_notification_sent"
                ) as mock_sent:
                    result = await send_logout_all_notification(
                        device_token="test_token_abc123"
                    )

                    assert result is True
                    mock_sent.assert_called_once_with(
                        notification_type="logout_all",
                        user_id=None,
                        device_token_prefix="test_token_a",
                    )

    @pytest.mark.asyncio
    async def test_send_test_reminder_tracks_delivery(self, tmp_path):
        """Test that send_test_reminder_notification tracks delivery."""
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

                with patch.object(
                    AnalyticsTracker, "track_notification_sent"
                ) as mock_sent:
                    result = await send_test_reminder_notification(
                        device_token="test_token_abc123"
                    )

                    assert result is True
                    mock_sent.assert_called_once_with(
                        notification_type="test_reminder",
                        user_id=None,
                        device_token_prefix="test_token_a",
                    )
