"""
Feedback submission endpoints for user feedback, bug reports, and feature requests.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import get_db, User, FeedbackSubmission
from app.schemas.feedback import (
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
)
from app.core.auth import get_current_user_optional
from app.core.error_responses import raise_server_error, ErrorMessages
from app.core.ip_extraction import get_secure_client_ip
from app.ratelimit.limiter import RateLimiter
from app.ratelimit.storage import InMemoryStorage
from app.ratelimit.strategies import TokenBucketStrategy

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiter for feedback submissions
# 5 submissions per hour (3600 seconds) per IP address
feedback_storage = InMemoryStorage()
feedback_strategy = TokenBucketStrategy(feedback_storage)
feedback_limiter = RateLimiter(
    strategy=feedback_strategy,
    storage=feedback_storage,
    default_limit=5,
    default_window=3600,  # 1 hour in seconds
)


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP for rate limiting and logging.

    Delegates to the shared secure IP extraction utility.
    See app.core.ip_extraction for security documentation.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    return get_secure_client_ip(request)


def _extract_headers(request: Request) -> dict:
    """
    Extract relevant headers from request for logging.

    Args:
        request: FastAPI request object

    Returns:
        Dictionary with app_version, ios_version, device_id
    """
    return {
        "app_version": request.headers.get("X-App-Version"),
        "ios_version": request.headers.get("X-Platform"),
        "device_id": request.headers.get("X-Device-ID"),
    }


def _send_feedback_notification(feedback: FeedbackSubmission) -> bool:
    """
    Send notification about new feedback submission.

    This function handles email notification failures gracefully to ensure
    the user's feedback submission succeeds even if notifications fail.
    Failures are logged for monitoring but do not bubble up to the user.

    Args:
        feedback: The feedback submission object

    Returns:
        True if notification was sent successfully, False otherwise
    """
    try:
        category_display = feedback.category.value.replace("_", " ").title()
        description_preview = (
            feedback.description[:100] + "..."
            if len(feedback.description) > 100
            else feedback.description
        )

        # Log without PII - redact email to protect user privacy
        email_domain = (
            feedback.email.split("@")[-1] if "@" in feedback.email else "unknown"
        )
        logger.info(
            f"New feedback received (domain: {email_domain}): "
            f"{category_display} - {description_preview}"
        )

        # TODO: Implement actual email notification
        # When implementing, add email sending here. The try-except will
        # catch any SMTP errors, connection timeouts, etc.
        # Example:
        # await send_email(
        #     to=settings.ADMIN_EMAIL,
        #     subject=f"New {category_display} from {feedback.name}",
        #     body=f"Email: {feedback.email}\n\n{feedback.description}"
        # )

        return True

    except Exception as e:
        # Log the error with context for debugging and monitoring
        # Include feedback ID but no PII
        logger.error(
            f"Failed to send feedback notification: "
            f"feedback_id={feedback.id}, "
            f"category={feedback.category.value}, "
            f"error={type(e).__name__}: {e}"
        )
        return False


@router.post(
    "/submit",
    response_model=FeedbackSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def submit_feedback(
    feedback_data: FeedbackSubmitRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Submit user feedback, bug report, or feature request.

    This endpoint allows users to submit feedback even before authentication,
    making it useful for reporting onboarding issues or bugs encountered
    during the registration process.

    Rate limit: 5 submissions per hour per IP address.

    Args:
        feedback_data: Feedback submission data
        request: FastAPI request object (for IP extraction)
        db: Database session
        current_user: Optional authenticated user (injected by dependency)

    Returns:
        Feedback submission confirmation with submission ID

    Raises:
        HTTPException: 429 if rate limit exceeded, 500 on server error
    """
    # Get client IP for rate limiting
    client_ip = _get_client_ip(request)

    # Check rate limit
    allowed, metadata = feedback_limiter.check(client_ip)
    if not allowed:
        retry_after = metadata.get("retry_after", 3600)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "message": "Too many feedback submissions. Please try again later.",
                "retry_after": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )

    # Extract request headers
    headers = _extract_headers(request)

    # Create feedback submission
    # Note: IP address extraction still used for rate limiting but NOT persisted
    # to comply with privacy policy (no IP-based location data collection)
    feedback_submission = FeedbackSubmission(
        user_id=current_user.id if current_user else None,
        name=feedback_data.name,
        email=feedback_data.email,
        category=feedback_data.category,
        description=feedback_data.description,
        app_version=headers["app_version"],
        ios_version=headers["ios_version"],
        device_id=headers["device_id"],
    )

    try:
        db.add(feedback_submission)
        db.commit()
        db.refresh(feedback_submission)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during feedback submission: {e}")
        raise_server_error(ErrorMessages.GENERIC_SERVER_ERROR)

    # Send notification - failures are handled gracefully and don't affect user response
    notification_sent = _send_feedback_notification(feedback_submission)

    # Log successful submission (without PII in structured logs)
    logger.info(
        f"Feedback submission successful: "
        f"id={feedback_submission.id}, "
        f"category={feedback_submission.category.value}, "
        f"user_id={current_user.id if current_user else 'anonymous'}, "
        f"notification_sent={notification_sent}"
    )

    return FeedbackSubmitResponse(
        success=True,
        submission_id=feedback_submission.id,
        message="Thank you for your feedback! We'll review it shortly.",
    )
