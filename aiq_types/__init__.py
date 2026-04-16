"""
AIQ-internal shared enums used across aiq services.

These enums are aiq-specific (not generic infrastructure) and therefore live
here rather than in gioe_libs. Both the backend and question-service import
from this module, ensuring a single definition.
"""

import enum


class QuestionType(str, enum.Enum):
    """Types of IQ test questions."""

    PATTERN = "pattern"
    LOGIC = "logic"
    SPATIAL = "spatial"
    MATH = "math"
    VERBAL = "verbal"
    MEMORY = "memory"


class TestStatus(str, enum.Enum):
    """Test session status."""

    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class NotificationType(str, enum.Enum):
    """Notification type for APNs push notifications."""

    TEST_REMINDER = "test_reminder"
    DAY_30_REMINDER = "day_30_reminder"
    LOGOUT_ALL = "logout_all"
    ADMIN_TEST = "admin_test"
