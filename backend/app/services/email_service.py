"""
Email service for sending password reset emails and other notifications.

This module provides email functionality using SMTP configuration from settings.
In development/testing environments without SMTP configured, it logs tokens
instead of sending actual emails.
"""

import html
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from typing import Optional
from urllib.parse import urlencode

from app.core.config import settings
from app.core.datetime_utils import utc_now

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

FEEDBACK_NOTIFICATION_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>New Feedback Submission</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
    <div style="background-color: #f8f9fa; border-radius: 8px; padding: 30px; margin-bottom: 20px;">
        <h1 style="color: #1a1a1a; margin-top: 0;">New Feedback: {category}</h1>
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <tr>
                <td style="padding: 8px 0; font-weight: 600; width: 120px; vertical-align: top;">From:</td>
                <td style="padding: 8px 0;">{name} &lt;{email}&gt;</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: 600; vertical-align: top;">Category:</td>
                <td style="padding: 8px 0;">{category}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0; font-weight: 600; vertical-align: top;">Submission ID:</td>
                <td style="padding: 8px 0;">{submission_id}</td>
            </tr>
        </table>
        <div style="background-color: #fff; border-radius: 6px; padding: 20px; border: 1px solid #e0e0e0;">
            <h3 style="margin-top: 0; color: #555;">Message</h3>
            <p style="white-space: pre-wrap; margin: 0;">{description}</p>
        </div>
    </div>
    <div style="font-size: 12px; color: #999; text-align: center; margin-top: 20px;">
        <p>This is an automated notification from AIQ.</p>
        <p>© {year} AIQ. All rights reserved.</p>
    </div>
</body>
</html>
"""

FEEDBACK_NOTIFICATION_TEXT_TEMPLATE = """
New Feedback: {category}

From: {name} <{email}>
Category: {category}
Submission ID: {submission_id}

Message:
{description}

---
This is an automated notification from AIQ.
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
        and settings.SMTP_FROM_NAME
        and settings.ADMIN_EMAIL
    )


def send_password_reset_email(
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
    # Default to iOS Universal Link URL for production
    # Universal links allow the iOS app to handle the URL natively
    # Requires Associated Domains entitlement configured in Xcode
    if reset_url_base is None:
        reset_url_base = "https://aiq.app"

    # Construct the reset URL with proper URL encoding
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
        # Prepare email content - use UTC for consistency
        current_year = utc_now().year

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


def send_feedback_notification_email(
    name: str,
    email: str,
    category: str,
    description: str,
    submission_id: int,
) -> bool:
    """
    Send admin notification email for a new feedback submission.

    In production environments with SMTP configured, sends an actual email to
    settings.ADMIN_EMAIL. In development/testing without SMTP, logs the feedback
    details instead.

    Args:
        name: Submitter's name
        email: Submitter's email address
        category: Feedback category (human-readable, e.g. "Bug Report")
        description: Full feedback message
        submission_id: Database ID of the feedback submission

    Returns:
        True if email was sent successfully or logged, False on error
    """
    if not _is_smtp_configured():
        logger.info(
            f"SMTP not configured. New feedback submission: "
            f"id={submission_id}, category={category}"
        )
        return True

    try:
        current_year = utc_now().year

        # Strip newline/CR from header values to prevent header injection
        safe_category = category.replace("\r", "").replace("\n", "")
        safe_name = name.replace("\r", "").replace("\n", "")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"[AIQ Feedback] New {safe_category} from {safe_name}"
        msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
        msg["To"] = formataddr(("", settings.ADMIN_EMAIL))

        text_content = FEEDBACK_NOTIFICATION_TEXT_TEMPLATE.format(
            name=name,
            email=email,
            category=category,
            description=description,
            submission_id=submission_id,
            year=current_year,
        )
        # HTML-escape all user-supplied values to prevent HTML injection in admin email
        html_content = FEEDBACK_NOTIFICATION_HTML_TEMPLATE.format(
            name=html.escape(name),
            email=html.escape(email),
            category=html.escape(category),
            description=html.escape(description),
            submission_id=submission_id,
            year=current_year,
        )

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        with smtplib.SMTP(
            settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS
        ) as server:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(msg)

        logger.info(f"Feedback notification email sent: submission_id={submission_id}")
        return True

    except smtplib.SMTPException as e:
        logger.error(
            f"SMTP error sending feedback notification: submission_id={submission_id}, error={e}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error sending feedback notification: submission_id={submission_id}, error={e}",
            exc_info=True,
        )
        return False
