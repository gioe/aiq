"""
Pydantic schemas for guest test endpoints (TASK-359).

Guest tests are unauthenticated test sessions linked to a device identifier.
They mirror the authenticated test flow but add a one-time-use token for
correlating the start and submit calls, and expose a remaining-test counter
so the client can display appropriate CTAs.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List

from app.schemas.questions import QuestionResponse
from app.schemas.responses import (
    ResponseItem,
    SubmitTestResponse,
)  # noqa: F401 — re-exported
from app.schemas.test_sessions import TestSessionResponse
from app.core.validators import TextValidator


class GuestStartTestResponse(BaseModel):
    """
    Response returned by POST /v1/test/guest/start.

    Extends the standard StartTestResponse with a one-time guest_token
    (must be supplied verbatim in the subsequent submit call) and the number
    of tests the device can still take after this one begins.
    """

    session: TestSessionResponse = Field(..., description="Created guest test session")
    questions: List[QuestionResponse] = Field(
        ..., description="Questions for this test"
    )
    total_questions: int = Field(..., description="Total number of questions in test")
    guest_token: str = Field(
        ...,
        description=(
            "One-time token that must be supplied when submitting this test. "
            "Valid for GUEST_TOKEN_TTL_MINUTES minutes. Consumed on first use."
        ),
    )
    tests_remaining: int = Field(
        ...,
        ge=0,
        description=(
            "Number of additional guest tests this device may take after the current one. "
            "Zero means the client should prompt account creation."
        ),
    )


class GuestSubmitRequest(BaseModel):
    """
    Request body for POST /v1/test/guest/submit.

    Replaces the authenticated ResponseSubmission.session_id field with a
    guest_token, which the server uses to look up the associated session_id
    and device_id from the in-memory TTLCache.
    """

    guest_token: str = Field(
        ...,
        min_length=1,
        description="One-time token returned by POST /v1/test/guest/start.",
    )
    responses: List[ResponseItem] = Field(
        ..., description="List of responses for the test session"
    )
    time_limit_exceeded: bool = Field(
        False,
        description="Flag indicating if the time limit was exceeded (client-reported)",
    )

    @field_validator("guest_token")
    @classmethod
    def validate_guest_token(cls, v: str) -> str:
        """Strip surrounding whitespace; reject empty values after stripping."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("guest_token cannot be blank.")
        return stripped


class GuestSubmitTestResponse(SubmitTestResponse):
    """
    Response returned by POST /v1/test/guest/submit.

    Identical to SubmitTestResponse — re-exposed under a guest-specific name
    so the OpenAPI spec tags it correctly and the iOS client can generate a
    type-safe model for this endpoint independently.
    """

    pass


class GuestStartRequest(BaseModel):
    """
    Optional explicit request body for POST /v1/test/guest/start.

    Currently the only required information is conveyed via the X-Device-Id
    header; this model is defined for forward-compatibility (e.g. locale hints).
    The body is entirely optional — an empty JSON object {} is accepted.
    """

    question_count: int = Field(
        default=0,  # 0 signals "use server default"
        ge=0,
        le=100,
        description=(
            "Number of questions to include. "
            "Pass 0 (or omit) to use the server's configured default."
        ),
    )

    @field_validator("question_count")
    @classmethod
    def validate_question_count(cls, v: int) -> int:
        result = TextValidator.validate_non_negative_int(v, "Question count")
        # validate_non_negative_int returns Optional[int]; our field is always
        # an int with a default, so None is never passed here.
        return result if result is not None else 0
