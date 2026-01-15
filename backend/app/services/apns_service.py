"""
Apple Push Notification Service (APNs) integration for sending push notifications.
"""
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional

from aioapns import APNs, NotificationRequest, PushType

from app.core.config import settings

logger = logging.getLogger(__name__)


class APNsService:
    """
    Service for sending push notifications via Apple Push Notification service (APNs).

    This service handles the connection to APNs and provides methods for sending
    notifications to iOS devices.
    """

    def __init__(
        self,
        key_id: Optional[str] = None,
        team_id: Optional[str] = None,
        bundle_id: Optional[str] = None,
        key_path: Optional[str] = None,
        use_sandbox: Optional[bool] = None,
    ):
        """
        Initialize the APNs service.

        Args:
            key_id: APNs Auth Key ID (10 characters). Defaults to settings.APNS_KEY_ID
            team_id: Apple Developer Team ID (10 characters). Defaults to settings.APNS_TEAM_ID
            bundle_id: iOS app bundle identifier. Defaults to settings.APNS_BUNDLE_ID
            key_path: Path to .p8 key file. Defaults to settings.APNS_KEY_PATH
            use_sandbox: Whether to use sandbox APNs server. Defaults to settings.APNS_USE_SANDBOX
        """
        self.key_id = key_id or settings.APNS_KEY_ID
        self.team_id = team_id or settings.APNS_TEAM_ID
        self.bundle_id = bundle_id or settings.APNS_BUNDLE_ID
        self.key_path = key_path or settings.APNS_KEY_PATH
        self.use_sandbox = (
            use_sandbox if use_sandbox is not None else settings.APNS_USE_SANDBOX
        )
        self._client: Optional[APNs] = None

    def _validate_config(self) -> None:
        """
        Validate that all required configuration is present.

        Raises:
            ValueError: If any required configuration is missing
        """
        if not self.key_id:
            raise ValueError("APNS_KEY_ID is required")
        if not self.team_id:
            raise ValueError("APNS_TEAM_ID is required")
        if not self.bundle_id:
            raise ValueError("APNS_BUNDLE_ID is required")
        if not self.key_path:
            raise ValueError("APNS_KEY_PATH is required")

        # Validate key file exists
        key_file = Path(self.key_path)
        if not key_file.exists():
            raise ValueError(f"APNs key file not found at: {self.key_path}")
        if not key_file.is_file():
            raise ValueError(f"APNs key path is not a file: {self.key_path}")

    async def connect(self) -> None:
        """
        Establish connection to APNs.

        Raises:
            ValueError: If configuration is invalid
        """
        self._validate_config()

        logger.info(
            f"Connecting to APNs ({'sandbox' if self.use_sandbox else 'production'})"
        )

        self._client = APNs(
            key=self.key_path,
            key_id=self.key_id,
            team_id=self.team_id,
            topic=self.bundle_id,
            use_sandbox=self.use_sandbox,
        )

        logger.info("Successfully connected to APNs")

    async def disconnect(self) -> None:
        """Disconnect from APNs."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from APNs")

    async def send_notification(
        self,
        device_token: str,
        title: str,
        body: str,
        badge: Optional[int] = None,
        sound: Optional[str] = "default",
        data: Optional[Dict] = None,
    ) -> bool:
        """
        Send a push notification to a single device.

        Args:
            device_token: The device's APNs token
            title: Notification title
            body: Notification body text
            badge: Optional badge count to display on app icon
            sound: Notification sound (default: "default", None for silent)
            data: Optional custom data payload

        Returns:
            True if notification was sent successfully, False otherwise
        """
        if not self._client:
            logger.error("APNs client not connected. Call connect() first.")
            return False

        try:
            # Build the notification payload
            alert = {"title": title, "body": body}

            aps: Dict = {
                "alert": alert,
            }

            # Only include sound if explicitly provided (None = silent notification)
            if sound is not None:
                aps["sound"] = sound

            if badge is not None:
                aps["badge"] = badge

            payload = {"aps": aps}

            # Add custom data if provided
            if data:
                payload.update(data)

            # Create notification request
            request = NotificationRequest(
                device_token=device_token,
                message=payload,
                push_type=PushType.ALERT,
            )

            # Send the notification
            await self._client.send_notification(request)

            logger.info(
                f"Successfully sent notification to device: {device_token[:8]}..."
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to send notification to device {device_token[:8]}...: {str(e)}"
            )
            return False

    async def send_batch_notifications(
        self,
        notifications: List[Dict],
    ) -> Dict[str, int]:
        """
        Send notifications to multiple devices.

        Args:
            notifications: List of notification dictionaries, each containing:
                - device_token (str): The device's APNs token
                - title (str): Notification title
                - body (str): Notification body text
                - badge (int, optional): Badge count
                - sound (str, optional): Notification sound
                - data (dict, optional): Custom data payload

        Returns:
            Dictionary with counts: {"success": X, "failed": Y}
        """
        if not self._client:
            logger.error("APNs client not connected. Call connect() first.")
            return {"success": 0, "failed": len(notifications)}

        success_count = 0
        failed_count = 0

        # Send notifications concurrently
        tasks = []
        for notification in notifications:
            task = self.send_notification(
                device_token=notification["device_token"],
                title=notification["title"],
                body=notification["body"],
                badge=notification.get("badge"),
                sound=notification.get("sound", "default"),
                data=notification.get("data"),
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, bool) and result:
                success_count += 1
            else:
                failed_count += 1

        logger.info(
            f"Batch notification results: {success_count} succeeded, {failed_count} failed"
        )

        return {"success": success_count, "failed": failed_count}


async def send_test_reminder_notification(
    device_token: str,
    user_name: Optional[str] = None,
) -> bool:
    """
    Send a test reminder notification to a user.

    This is a convenience function for sending the standard test reminder notification.

    Args:
        device_token: The device's APNs token
        user_name: Optional user name to personalize the notification

    Returns:
        True if notification was sent successfully, False otherwise
    """
    service = APNsService()

    try:
        await service.connect()

        title = "Time for Your IQ Test!"
        if user_name:
            body = f"Hi {user_name}, it's been 3 months! Ready to track your cognitive progress?"
        else:
            body = "It's been 3 months! Ready to track your cognitive progress?"

        result = await service.send_notification(
            device_token=device_token,
            title=title,
            body=body,
            badge=1,
            data={"type": "test_reminder"},
        )

        return result

    finally:
        await service.disconnect()
