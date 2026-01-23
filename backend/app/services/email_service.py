"""
Email service for sending password reset emails and other notifications.

This module provides email functionality using SMTP configuration from settings.
In development/testing environments without SMTP configured, it logs tokens
instead of sending actual emails.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional
from urllib.parse import urlencode

from app.core.config import settings

# SMTP connection timeout in seconds
SMTP_TIMEOUT_SECONDS = 10

logger = logging.getLogger(__name__)

# Password reset email template
PASSWORD_RESET_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reset Your Password</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 20px;">
        <h1 style="color: #1a1a1a; margin-top: 0;">Reset Your Password</h1>
        <p style="font-size: 16px; margin-bottom: 20px;">
            We received a request to reset your password for your AIQ account.
        </p>
        <p style="font-size: 16px; margin-bottom: 20px;">
            Click the button below to reset your password. This link will expire in 30 minutes.
        </p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{reset_url}" style="background-color: #007AFF; color: white; padding: 14px 28px; text-decoration: none; border-radius: 8px; display: inline-block; font-weight: 600; font-size: 16px;">
                Reset Password
            </a>
        </div>
        <p style="font-size: 14px; color: #666; margin-top: 30px;">
            If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.
        </p>
        <p style="font-size: 14px; color: #666; margin-top: 10px;">
            If the button above doesn't work, copy and paste this link into your browser:
        </p>
        <p style="font-size: 14px; color: #007AFF; word-break: break-all;">
            {reset_url}
        </p>
    </div>
    <div style="font-size: 12px; color: #999; text-align: center; margin-top: 20px;">
        <p>This is an automated email from AIQ. Please do not reply to this message.</p>
        <p>© {year} AIQ. All rights reserved.</p>
    </div>
</body>
</html>
"""

PASSWORD_RESET_TEXT_TEMPLATE = """
Reset Your Password

We received a request to reset your password for your AIQ account.

Click the link below to reset your password. This link will expire in 30 minutes:

{reset_url}

If you didn't request a password reset, you can safely ignore this email. Your password will not be changed.

---
This is an automated email from AIQ. Please do not reply to this message.
© {year} AIQ. All rights reserved.
"""


def _is_smtp_configured() -> bool:
    """
    Check if SMTP is properly configured.

    Returns:
        True if all required SMTP settings are configured, False otherwise.
    """
    return bool(
        settings.SMTP_HOST
        and settings.SMTP_PORT
        and settings.SMTP_USERNAME
        and settings.SMTP_PASSWORD
        and settings.SMTP_FROM_EMAIL
    )


async def send_password_reset_email(
    email: str,
    reset_token: str,
    reset_url_base: Optional[str] = None,
) -> bool:
    """
    Send password reset email with secure token.

    In production environments with SMTP configured, sends an actual email.
    In development/testing without SMTP, logs the token for manual testing.

    Args:
        email: Recipient email address
        reset_token: Secure random token for password reset
        reset_url_base: Base URL for reset link (defaults to backend production URL)

    Returns:
        True if email was sent successfully or logged, False on error

    Example:
        >>> success = await send_password_reset_email(
        ...     email="user@example.com",
        ...     reset_token="abc123xyz",
        ...     reset_url_base="https://app.aiq.com"
        ... )
    """
    # Default to production backend URL if not specified
    if reset_url_base is None:
        reset_url_base = "https://aiq-backend-production.up.railway.app"

    # Construct the reset URL with proper URL encoding
    # NOTE: For production iOS app, this should be a deep link or universal link
    # that opens the app. For now, using a backend URL endpoint.
    query_params = urlencode({"token": reset_token})
    reset_url = f"{reset_url_base}/reset-password?{query_params}"

    # If SMTP is not configured, log the token for development/testing
    if not _is_smtp_configured():
        logger.info(
            f"SMTP not configured. Password reset requested for {email}. "
            f"Reset token: {reset_token}"
        )
        logger.info(f"Reset URL (for testing): {reset_url}")
        return True

    try:
        # Prepare email content
        from datetime import datetime

        current_year = datetime.now().year

        # Create message with properly encoded headers
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Reset Your AIQ Password"
        msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
        msg["To"] = formataddr(
            ("", email)
        )  # Properly encode email to prevent header injection

        # Create plain text and HTML versions
        text_content = PASSWORD_RESET_TEXT_TEMPLATE.format(
            reset_url=reset_url,
            year=current_year,
        )
        html_content = PASSWORD_RESET_HTML_TEMPLATE.format(
            reset_url=reset_url,
            year=current_year,
        )

        # Attach parts
        part_text = MIMEText(text_content, "plain")
        part_html = MIMEText(html_content, "html")
        msg.attach(part_text)
        msg.attach(part_html)

        # Send email via SMTP with timeout to prevent hanging
        with smtplib.SMTP(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
        ) as server:
            server.starttls()  # Upgrade to secure connection
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Password reset email sent successfully to {email}")
        return True

    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending password reset email to {email}: {e}")
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error sending password reset email to {email}: {e}",
            exc_info=True,
        )
        return False
