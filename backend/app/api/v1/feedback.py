"""
Feedback submission endpoints for user feedback, bug reports, and feature requests.
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request, status, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import get_db, User, FeedbackSubmission
from app.schemas.feedback import (
    FeedbackSubmitRequest,
    FeedbackSubmitResponse,
)
from app.core.auth import get_current_user_optional
from app.core.config import settings
from app.core.error_responses import raise_server_error, ErrorMessages
from app.core.ip_extraction import get_secure_client_ip
from app.ratelimit.limiter import RateLimiter
from app.ratelimit.storage import InMemoryStorage, RateLimiterStorage
from app.ratelimit.strategies import TokenBucketStrategy

logger = logging.getLogger(__name__)

router = APIRouter()

# Rate limiting configuration for feedback submissions
FEEDBACK_RATE_LIMIT_MAX_REQUESTS = 5
FEEDBACK_RATE_LIMIT_WINDOW_SECONDS = 3600  # 1 hour


def _create_rate_limiter_storage() -> RateLimiterStorage:
    """
    Create rate limiter storage with Redis fallback to in-memory.

    Uses the same RATE_LIMIT_STORAGE and RATE_LIMIT_REDIS_URL settings
    as the global rate limiter to maintain consistent configuration.

    This ensures the rate limiter works correctly in both:
    - Multi-worker production deployments (with Redis)
    - Single-worker local development (without Redis)

    Returns:
        RateLimiterStorage: Redis storage if available, otherwise in-memory
    """
    if settings.RATE_LIMIT_STORAGE == "redis":
        try:
            # Import RedisStorage only when needed (redis-py is optional)
            from app.ratelimit.storage import RedisStorage

            logger.info("Attempting to connect to Redis for feedback rate limiting")
            redis_storage = RedisStorage(redis_url=settings.RATE_LIMIT_REDIS_URL)

            # Test connection
            if redis_storage.is_connected():
                logger.info(
                    "Successfully connected to Redis for feedback rate limiting"
                )
                return redis_storage
            else:
                logger.warning(
                    "Redis connection failed for feedback rate limiter. "
                    "Falling back to in-memory storage. "
                    "Rate limiting will not work correctly across multiple workers."
                )
        except ImportError:
            logger.warning(
                "Redis library not installed. Install with: pip install redis. "
                "Falling back to in-memory storage for feedback rate limiting."
            )
        except Exception as e:
            logger.warning(
                f"Failed to initialize Redis storage for feedback rate limiter: {e}. "
                f"Falling back to in-memory storage. "
                f"Rate limiting will not work correctly across multiple workers."
            )

    # Fallback to in-memory storage
    logger.info(
        "Using in-memory storage for feedback rate limiting. "
        "Set RATE_LIMIT_STORAGE=redis for multi-worker deployments."
    )
    return InMemoryStorage(max_keys=settings.RATE_LIMIT_MAX_KEYS)


# Lazy-initialized rate limiter: created on first use to avoid module-import
# side effects (network calls to Redis, log noise during test collection).
_feedback_limiter: Optional[RateLimiter] = None


def _get_feedback_limiter() -> RateLimiter:
    global _feedback_limiter
    if _feedback_limiter is None:
        storage = _create_rate_limiter_storage()
        strategy = TokenBucketStrategy(storage)
        _feedback_limiter = RateLimiter(
            strategy=strategy,
            storage=storage,
            default_limit=FEEDBACK_RATE_LIMIT_MAX_REQUESTS,
            default_window=FEEDBACK_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _feedback_limiter


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
    db: AsyncSession = Depends(get_db),
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

    # Check rate limit with error handling (fail-open for feedback)
    # If the rate limiter fails (e.g., Redis connection issue), allow the request
    # to proceed since feedback collection is more important than strict rate limiting
    try:
        limiter = _get_feedback_limiter()
        allowed, metadata = limiter.check(client_ip)
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
    except HTTPException:
        # Re-raise rate limit exceeded response
        raise
    except Exception as e:
        # Log the error but allow the request to proceed (fail-open)
        # This ensures feedback can still be submitted when rate limiter has issues
        logger.warning(
            f"Rate limiter error during feedback submission: "
            f"client_ip={client_ip}, "
            f"error={type(e).__name__}: {e}. "
            f"Allowing request to proceed (fail-open)."
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
        await db.commit()
        await db.refresh(feedback_submission)
    except SQLAlchemyError as e:
        await db.rollback()
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
