"""LLM-specific error category constants for AIQ.

These categories are LLM-provider-specific and are defined locally so that
AIQ does not depend on them being present in gioe_libs.alerting.ErrorCategory.
All values are plain strings compatible with AlertableError.category (which
accepts any str value).
"""

from enum import Enum


class LLMErrorCategory(str, Enum):
    """LLM provider error categories specific to AIQ's question-service."""

    BILLING_QUOTA = "billing_quota"  # Insufficient funds, quota exceeded
    RATE_LIMIT = "rate_limit"  # Rate limit / throttling errors
    MODEL_ERROR = "model_error"  # Model not found or unavailable
