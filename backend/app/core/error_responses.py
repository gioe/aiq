"""
Standardized error response messages and builders (BCQ-027).

This module provides consistent error messages and HTTPException builders
for the entire API. Using these utilities ensures:

1. Consistent message format across all endpoints
2. User-friendly error messages without leaking implementation details
3. Easy maintenance and localization of error messages
4. Clear separation of user-facing messages from log messages

Error Message Format Guidelines:
- Use sentence case (capitalize first letter only)
- End with a period for complete sentences
- Include relevant IDs in parentheses when helpful for debugging: "(ID: 123)"
- Use "Please try again later." for transient server errors
- Use action-oriented language ("Please complete..." not "You must complete...")

Usage:
    from app.core.error_responses import ErrorMessages, raise_not_found, raise_forbidden

    # Using predefined messages:
    if not user:
        raise_not_found(ErrorMessages.USER_NOT_FOUND)

    # Using message templates:
    raise_conflict(ErrorMessages.active_session_exists(session_id=123))

    # Using the builder directly:
    raise_bad_request("Custom message for specific case.")
"""

from typing import NoReturn, Optional

from fastapi import HTTPException, status


class ErrorMessages:
    """Centralized error message constants and templates.

    All user-facing error messages should be defined here to ensure
    consistency and make future localization easier.

    Naming Convention:
    - Constants: SCREAMING_SNAKE_CASE for static messages
    - Methods: snake_case for templates that accept parameters
    """

    # ==========================================================================
    # Authentication Errors (401)
    # ==========================================================================
    INVALID_CREDENTIALS = "Invalid email or password."
    INVALID_TOKEN = "Invalid authentication token."
    INVALID_REFRESH_TOKEN = "Invalid refresh token."
    INVALID_TOKEN_TYPE = "Invalid token type."
    INVALID_TOKEN_PAYLOAD = "Invalid token payload."
    USER_NOT_FOUND_AUTH = "User not found."
    TOKEN_EXPIRED = "Token has expired."

    # ==========================================================================
    # Authorization Errors (403)
    # ==========================================================================
    SESSION_ACCESS_DENIED = "Not authorized to access this test session."
    RESULT_ACCESS_DENIED = "Not authorized to access this test result."
    ADMIN_TOKEN_INVALID = "Invalid admin token."
    SERVICE_KEY_INVALID = "Invalid service API key."

    # ==========================================================================
    # Not Found Errors (404)
    # ==========================================================================
    TEST_SESSION_NOT_FOUND = "Test session not found."
    TEST_RESULT_NOT_FOUND = "Test result not found."
    USER_NOT_FOUND = "User not found."
    QUESTION_NOT_FOUND = "Question not found."
    GENERATION_RUN_NOT_FOUND = "Generation run not found."

    # ==========================================================================
    # Conflict Errors (409)
    # ==========================================================================
    EMAIL_ALREADY_REGISTERED = "Email already registered."
    # BCQ-045: Used for database-level race condition detection (IntegrityError).
    # Cannot include session_id because the transaction was rolled back.
    # For app-level detection with session_id, use active_session_exists() below.
    SESSION_ALREADY_IN_PROGRESS = (
        "A test session is already in progress. "
        "Please complete or abandon the existing session before starting a new one."
    )

    # ==========================================================================
    # Bad Request Errors (400)
    # ==========================================================================
    EMPTY_RESPONSE_LIST = "Response list cannot be empty."
    SESSION_NOT_IN_PROGRESS = "Only in-progress sessions can be modified."
    NO_QUESTIONS_AVAILABLE = (
        "No unseen questions available. Question pool may be exhausted."
    )
    QUALITY_FLAG_REASON_REQUIRED = (
        "Reason is required when setting quality_flag to 'deactivated'."
    )

    # ==========================================================================
    # Server Errors (500)
    # ==========================================================================
    ACCOUNT_CREATION_FAILED = "Failed to create user account. Please try again later."
    LOGIN_FAILED = "Login failed due to a server error. Please try again later."
    RELIABILITY_REPORT_FAILED = (
        "Failed to generate reliability report. Please try again later."
    )
    RELIABILITY_HISTORY_FAILED = (
        "Failed to retrieve reliability history. Please try again later."
    )

    # ==========================================================================
    # Configuration Errors (500)
    # ==========================================================================
    ADMIN_TOKEN_NOT_CONFIGURED = "Admin token not configured on server."
    SERVICE_KEY_NOT_CONFIGURED = "Service API key not configured on server."
    SCRIPT_NOT_FOUND = "Question generation script not found."
    INVALID_JOB_ID = "Invalid job ID."

    # ==========================================================================
    # Template Methods for Dynamic Messages
    # ==========================================================================
    @staticmethod
    def active_session_exists(session_id: int) -> str:
        """Message for when user has an active session blocking a new one.

        BCQ-045: Used for app-level active session detection (returns 400).
        Includes session_id so clients can offer "Resume session" functionality.
        For database-level race condition detection, use SESSION_ALREADY_IN_PROGRESS.
        """
        return (
            f"User already has an active test session (ID: {session_id}). "
            "Please complete or abandon the existing session before starting a new one."
        )

    @staticmethod
    def session_already_completed(status: str) -> str:
        """Message for when trying to modify a non-in-progress session."""
        return (
            f"Test session is already {status}. "
            "Only in-progress sessions can be modified."
        )

    @staticmethod
    def test_cadence_not_met(
        cadence_days: int,
        last_completed: str,
        next_eligible: str,
        days_remaining: int,
    ) -> str:
        """Message for when user tries to start a test too soon."""
        # Approximate months for display purposes only (30 days per month)
        months = cadence_days // 30
        return (
            f"You must wait {cadence_days} days ({months} months) between tests. "
            f"Your last test was completed on {last_completed}. "
            f"You can take your next test on {next_eligible} "
            f"({days_remaining} days remaining)."
        )

    @staticmethod
    def insufficient_questions(requested: int, available: int) -> str:
        """Message when fewer questions are available than requested."""
        return (
            f"Only {available} questions available, but {requested} were requested. "
            "Proceeding with available questions."
        )

    @staticmethod
    def database_operation_failed(operation: str) -> str:
        """Generic message for database operation failures."""
        return f"Failed to {operation}. Please try again later."

    @staticmethod
    def invalid_question_ids(question_ids: set) -> str:
        """Message when submitted question IDs don't belong to the test session."""
        # Sort for consistent, readable output (avoids curly brace set notation)
        ids_str = ", ".join(str(qid) for qid in sorted(question_ids))
        return (
            f"Invalid question IDs: {ids_str}. "
            "These questions do not belong to this test session."
        )

    @staticmethod
    def empty_answer(question_id: int) -> str:
        """Message when a user answer is empty."""
        return f"User answer for question {question_id} cannot be empty."

    @staticmethod
    def question_not_found(question_id: int) -> str:
        """Message when a specific question is not found."""
        return f"Question {question_id} not found."

    @staticmethod
    def result_not_found(result_id: int) -> str:
        """Message when a specific test result is not found."""
        return f"Test result {result_id} not found."


# ==============================================================================
# HTTPException Builder Functions
# ==============================================================================


def raise_bad_request(detail: str) -> NoReturn:
    """Raise a 400 Bad Request exception.

    Use for client errors where the request is malformed or invalid.

    Args:
        detail: User-facing error message

    Raises:
        HTTPException: 400 Bad Request
    """
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def raise_unauthorized(
    detail: str,
    include_www_authenticate: bool = True,
) -> NoReturn:
    """Raise a 401 Unauthorized exception.

    Use for authentication failures (invalid/missing credentials).

    Args:
        detail: User-facing error message
        include_www_authenticate: Whether to include WWW-Authenticate header

    Raises:
        HTTPException: 401 Unauthorized
    """
    headers = {"WWW-Authenticate": "Bearer"} if include_www_authenticate else None
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=headers,
    )


def raise_forbidden(detail: str) -> NoReturn:
    """Raise a 403 Forbidden exception.

    Use for authorization failures (valid credentials but insufficient permissions).

    Args:
        detail: User-facing error message

    Raises:
        HTTPException: 403 Forbidden
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=detail,
    )


def raise_not_found(detail: str) -> NoReturn:
    """Raise a 404 Not Found exception.

    Use when a requested resource doesn't exist.

    Args:
        detail: User-facing error message

    Raises:
        HTTPException: 404 Not Found
    """
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def raise_conflict(detail: str) -> NoReturn:
    """Raise a 409 Conflict exception.

    Use when the request conflicts with current state (e.g., duplicate creation).

    Args:
        detail: User-facing error message

    Raises:
        HTTPException: 409 Conflict
    """
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )


def raise_server_error(
    detail: str,
    error_id: Optional[str] = None,
) -> NoReturn:
    """Raise a 500 Internal Server Error exception.

    Use for unexpected server errors. Always use user-friendly messages;
    log technical details separately.

    Args:
        detail: User-facing error message (should be generic and friendly)
        error_id: Optional error tracking ID to include in response

    Raises:
        HTTPException: 500 Internal Server Error
    """
    # If error_id provided, append it to help with support requests
    if error_id:
        detail = f"{detail} (Error ID: {error_id})"

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )


def raise_not_configured(detail: str) -> NoReturn:
    """Raise a 500 error for missing server configuration.

    Use when required server configuration (e.g., API keys) is missing.

    Args:
        detail: Error message describing what's not configured

    Raises:
        HTTPException: 500 Internal Server Error
    """
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=detail,
    )
