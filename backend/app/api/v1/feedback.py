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
    Extract client IP address from request.

    Checks X-Forwarded-For header first (for proxy/load balancer scenarios),
    then falls back to direct client IP.

    Args:
        request: FastAPI request object

    Returns:
        Client IP address as string
    """
    # Check X-Forwarded-For header (used by proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client:
        return request.client.host

    # Default fallback
    return "unknown"


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


def _send_feedback_notification(feedback: FeedbackSubmission) -> None:
    """
    Send notification about new feedback submission.

    Stub implementation that logs the feedback. In production, this would
    send an email to the admin team.

    Args:
        feedback: The feedback submission object
    """
    category_display = feedback.category.value.replace("_", " ").title()
    description_preview = (
        feedback.description[:100] + "..."
        if len(feedback.description) > 100
        else feedback.description
    )

    logger.info(
        f"New feedback received from {feedback.email}: "
        f"{category_display} - {description_preview}"
    )

    # TODO: Implement actual email notification
    # This would use SMTP settings from config to send an email to admins
    # Example:
    # await send_email(
    #     to=settings.ADMIN_EMAIL,
    #     subject=f"New {category_display} from {feedback.name}",
    #     body=f"Email: {feedback.email}\n\n{feedback.description}"
    # )


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
    feedback_submission = FeedbackSubmission(
        user_id=current_user.id if current_user else None,
        name=feedback_data.name,
        email=feedback_data.email,
        category=feedback_data.category,
        description=feedback_data.description,
        app_version=headers["app_version"],
        ios_version=headers["ios_version"],
        device_id=headers["device_id"],
        ip_address=client_ip,
    )

    try:
        db.add(feedback_submission)
        db.commit()
        db.refresh(feedback_submission)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Database error during feedback submission: {e}")
        raise_server_error(ErrorMessages.GENERIC_SERVER_ERROR)

    # Send notification (stub)
    _send_feedback_notification(feedback_submission)

    # Log successful submission (without PII in structured logs)
    logger.info(
        f"Feedback submission successful: "
        f"id={feedback_submission.id}, "
        f"category={feedback_submission.category.value}, "
        f"user_id={current_user.id if current_user else 'anonymous'}"
    )

    return FeedbackSubmitResponse(
        success=True,
        submission_id=feedback_submission.id,
        message="Thank you for your feedback! We'll review it shortly.",
    )
