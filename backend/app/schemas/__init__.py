"""
Pydantic schemas for request/response validation.
"""
from .auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenRefresh,
    UserResponse,
    UserProfileUpdate,
)
from .questions import (
    QuestionResponse,
    UnseenQuestionsResponse,
)
from .test_sessions import (
    TestSessionResponse,
    StartTestResponse,
    TestSessionStatusResponse,
)
from .responses import (
    ResponseItem,
    ResponseSubmission,
    TestResultResponse,
    SubmitTestResponse,
)
from .generation_runs import (
    GenerationRunStatusSchema,
    QuestionGenerationRunCreate,
    QuestionGenerationRunRead,
    QuestionGenerationRunSummary,
    QuestionGenerationRunListResponse,
    QuestionGenerationRunStats,
)

__all__ = [
    "UserRegister",
    "UserLogin",
    "Token",
    "TokenRefresh",
    "UserResponse",
    "UserProfileUpdate",
    "QuestionResponse",
    "UnseenQuestionsResponse",
    "TestSessionResponse",
    "StartTestResponse",
    "TestSessionStatusResponse",
    "ResponseItem",
    "ResponseSubmission",
    "TestResultResponse",
    "SubmitTestResponse",
    # Generation run tracking schemas
    "GenerationRunStatusSchema",
    "QuestionGenerationRunCreate",
    "QuestionGenerationRunRead",
    "QuestionGenerationRunSummary",
    "QuestionGenerationRunListResponse",
    "QuestionGenerationRunStats",
]
