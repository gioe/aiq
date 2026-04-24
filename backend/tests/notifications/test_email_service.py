"""
Tests for the email service — send_feedback_notification_email.
"""

import smtplib
from unittest.mock import MagicMock, patch

from app.services.email_service import (
    send_feedback_notification_email,
    send_oauth_link_notification_email,
    send_password_reset_email,
)


SMTP_SETTINGS = {
    "SMTP_HOST": "smtp.example.com",
    "SMTP_PORT": 587,
    "SMTP_USERNAME": "user@example.com",
    "SMTP_PASSWORD": "test-smtp-password",  # pragma: allowlist secret
    "SMTP_FROM_EMAIL": "noreply@a-iq-test.com",
    "SMTP_FROM_NAME": "AIQ Support",
    "ADMIN_EMAIL": "admin@a-iq-test.com",
}


def _make_mock_settings(**overrides):
    mock = MagicMock()
    for key, value in {**SMTP_SETTINGS, **overrides}.items():
        setattr(mock, key, value)
    return mock


class TestSendFeedbackNotificationEmail:
    """Unit tests for send_feedback_notification_email."""

    # ------------------------------------------------------------------
    # SMTP-not-configured path
    # ------------------------------------------------------------------

    def test_returns_true_when_smtp_not_configured(self):
        """When SMTP is not configured, the function logs and returns True."""
        mock_settings = _make_mock_settings(SMTP_PASSWORD="")
        with patch("app.services.email_service.settings", mock_settings):
            result = send_feedback_notification_email(
                name="Alice",
                email="alice@example.com",
                category="Bug Report",
                description="Something broke",
                submission_id=42,
            )
        assert result is True

    def test_returns_true_when_admin_email_not_configured(self):
        """When ADMIN_EMAIL is empty, _is_smtp_configured() returns False → logs and returns True."""
        mock_settings = _make_mock_settings(ADMIN_EMAIL="")
        with patch("app.services.email_service.settings", mock_settings):
            result = send_feedback_notification_email(
                name="Alice",
                email="alice@example.com",
                category="Bug Report",
                description="Something broke",
                submission_id=42,
            )
        assert result is True

    # ------------------------------------------------------------------
    # SMTP success path
    # ------------------------------------------------------------------

    def test_returns_true_on_successful_send(self):
        """Returns True when SMTP send succeeds."""
        mock_settings = _make_mock_settings()
        mock_smtp_instance = MagicMock()

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = send_feedback_notification_email(
                name="Alice",
                email="alice@example.com",
                category="Bug Report",
                description="Something broke",
                submission_id=42,
            )

        assert result is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with(
            mock_settings.SMTP_USERNAME, mock_settings.SMTP_PASSWORD
        )
        mock_smtp_instance.send_message.assert_called_once()

    def test_message_addressed_to_admin_email(self):
        """The To header is set to ADMIN_EMAIL."""
        mock_settings = _make_mock_settings()
        captured = {}

        def capture_send(msg):
            captured["msg"] = msg

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.send_message.side_effect = capture_send

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            send_feedback_notification_email(
                name="Alice",
                email="alice@example.com",
                category="Bug Report",
                description="Something broke",
                submission_id=42,
            )

        assert "admin@a-iq-test.com" in captured["msg"]["To"]

    def test_html_body_escapes_user_input(self):
        """HTML-escapes user-supplied values to prevent injection."""
        mock_settings = _make_mock_settings()
        captured = {}

        def capture_send(msg):
            captured["msg"] = msg

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.send_message.side_effect = capture_send

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            send_feedback_notification_email(
                name='<script>alert("xss")</script>',
                email="bad@example.com",
                category="Bug Report",
                description="<b>bold</b>",
                submission_id=1,
            )

        # Extract the HTML payload
        msg = captured["msg"]
        html_part = None
        for part in msg.walk():
            if part.get_content_type() == "text/html":
                html_part = part.get_payload(decode=True).decode()
                break

        assert html_part is not None
        assert "<script>" not in html_part
        assert "&lt;script&gt;" in html_part
        assert "<b>" not in html_part
        assert "&lt;b&gt;" in html_part

    # ------------------------------------------------------------------
    # SMTP error paths
    # ------------------------------------------------------------------

    def test_returns_false_on_smtp_exception(self):
        """Returns False when an SMTPException is raised."""
        mock_settings = _make_mock_settings()

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch(
                "app.services.email_service.smtplib.SMTP",
                side_effect=smtplib.SMTPException("connection refused"),
            ),
        ):
            result = send_feedback_notification_email(
                name="Alice",
                email="alice@example.com",
                category="Bug Report",
                description="Something broke",
                submission_id=42,
            )

        assert result is False

    def test_returns_false_on_unexpected_exception(self):
        """Returns False when an unexpected exception is raised."""
        mock_settings = _make_mock_settings()

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch(
                "app.services.email_service.smtplib.SMTP",
                side_effect=RuntimeError("unexpected"),
            ),
        ):
            result = send_feedback_notification_email(
                name="Alice",
                email="alice@example.com",
                category="Bug Report",
                description="Something broke",
                submission_id=42,
            )

        assert result is False


class TestSendPasswordResetEmail:
    """Unit tests for send_password_reset_email."""

    def test_returns_true_on_successful_send(self):
        """Returns True when SMTP send succeeds."""
        mock_settings = _make_mock_settings()
        mock_smtp_instance = MagicMock()

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = send_password_reset_email(
                email="alice@example.com",
                reset_token="reset-token",
                reset_url_base="https://app.example.com",
            )

        assert result is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with(
            mock_settings.SMTP_USERNAME, mock_settings.SMTP_PASSWORD
        )
        mock_smtp_instance.send_message.assert_called_once()

    def test_message_addressed_to_user_email(self):
        """The To header is set to the reset requester."""
        mock_settings = _make_mock_settings()
        captured = {}

        def capture_send(msg):
            captured["msg"] = msg

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.send_message.side_effect = capture_send

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            send_password_reset_email(
                email="alice@example.com",
                reset_token="reset-token",
                reset_url_base="https://app.example.com",
            )

        assert "alice@example.com" in captured["msg"]["To"]
        assert captured["msg"]["Subject"] == "Reset Your AIQ Password"


class TestSendOAuthLinkNotificationEmail:
    """Unit tests for send_oauth_link_notification_email."""

    def test_returns_true_on_successful_send(self):
        """Returns True when SMTP send succeeds."""
        mock_settings = _make_mock_settings()
        mock_smtp_instance = MagicMock()

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            result = send_oauth_link_notification_email(
                email="alice@example.com",
                provider="google",
            )

        assert result is True
        mock_smtp_instance.starttls.assert_called_once()
        mock_smtp_instance.login.assert_called_once_with(
            mock_settings.SMTP_USERNAME, mock_settings.SMTP_PASSWORD
        )
        mock_smtp_instance.send_message.assert_called_once()

    def test_message_addressed_to_user_email(self):
        """The To header is set to the account owner."""
        mock_settings = _make_mock_settings()
        captured = {}

        def capture_send(msg):
            captured["msg"] = msg

        mock_smtp_instance = MagicMock()
        mock_smtp_instance.send_message.side_effect = capture_send

        with (
            patch("app.services.email_service.settings", mock_settings),
            patch("app.services.email_service.smtplib.SMTP") as mock_smtp_cls,
        ):
            mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp_instance
            mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

            send_oauth_link_notification_email(
                email="alice@example.com",
                provider="google",
            )

        assert "alice@example.com" in captured["msg"]["To"]
        assert (
            captured["msg"]["Subject"]
            == "A new sign-in method was added to your AIQ account (Google)"
        )
