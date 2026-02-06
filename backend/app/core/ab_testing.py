"""
A/B testing assignment logic for adaptive rollout (TASK-885).

This module provides consistent user assignment to test variants using
deterministic hashing. Users are assigned to either "fixed" or "adaptive"
test delivery modes based on a configurable percentage.

Key Features:
- Consistent hashing ensures same user always gets same variant
- Configurable rollout percentage (0-100%)
- Admin override capability for forcing specific users to specific variants
- Thread-safe admin override operations
- Logging for variant assignments (analytics)

Thread Safety:
    Admin override operations use a reentrant lock for thread-safe access.
    The assign_test_variant function is inherently thread-safe as it only
    reads from the override dict (protected by lock) and computes a
    deterministic hash.

Persistence:
    Admin overrides are stored in-memory and will be lost on application
    restart. For persistent overrides, consider storing in database.

Usage:
    from app.core.ab_testing import assign_test_variant

    variant = assign_test_variant(user_id=123, adaptive_percentage=10.0)
    # Returns: "fixed" or "adaptive"
"""

import hashlib
import logging
import math
import threading
from typing import Dict, Literal, Optional

logger = logging.getLogger(__name__)

# Type alias for test variants
TestVariant = Literal["fixed", "adaptive"]

# Thread-safe admin override storage
# Lock protects all access to _admin_overrides dictionary
_override_lock = threading.RLock()
_admin_overrides: Dict[int, TestVariant] = {}

# Percentage bounds
MIN_PERCENTAGE = 0.0
MAX_PERCENTAGE = 100.0

# Hash computation constants
MAX_HASH_INT = 2**64 - 1

# Public API
__all__ = [
    "TestVariant",
    "assign_test_variant",
    "set_admin_override",
    "clear_admin_override",
    "clear_all_admin_overrides",
    "get_admin_override",
    "get_all_admin_overrides",
]


def assign_test_variant(user_id: int, adaptive_percentage: float) -> TestVariant:
    """
    Assign a user to a test variant using consistent hashing.

    The assignment is deterministic - the same user_id will always get the
    same variant for a given adaptive_percentage. This ensures users have
    a consistent experience across sessions.

    Args:
        user_id: The user's ID (must be positive integer)
        adaptive_percentage: Percentage of users to assign to adaptive variant (0.0-100.0)

    Returns:
        "adaptive" if user is in adaptive group, "fixed" otherwise

    Raises:
        ValueError: If user_id is not a positive integer
        ValueError: If adaptive_percentage is not in range [0.0, 100.0]

    Examples:
        >>> assign_test_variant(user_id=123, adaptive_percentage=50.0)
        'adaptive'  # or 'fixed', deterministic for this user

        >>> assign_test_variant(user_id=123, adaptive_percentage=0.0)
        'fixed'  # Always fixed when 0%

        >>> assign_test_variant(user_id=123, adaptive_percentage=100.0)
        'adaptive'  # Always adaptive when 100%
    """
    # Validate inputs
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"user_id must be a positive integer, got: {user_id}")

    if not isinstance(adaptive_percentage, (int, float)):
        raise ValueError(
            f"adaptive_percentage must be a number, got: {type(adaptive_percentage)}"
        )

    if not (MIN_PERCENTAGE <= adaptive_percentage <= MAX_PERCENTAGE):
        raise ValueError(
            f"adaptive_percentage must be between {MIN_PERCENTAGE} and {MAX_PERCENTAGE}, "
            f"got: {adaptive_percentage}"
        )

    # Check for admin override first (thread-safe read)
    with _override_lock:
        if user_id in _admin_overrides:
            override_variant = _admin_overrides[user_id]
            logger.info(
                f"A/B test assignment for user {user_id}: {override_variant} (admin override)",
                extra={
                    "user_id": user_id,
                    "variant": override_variant,
                    "assignment_method": "admin_override",
                    "adaptive_percentage": adaptive_percentage,
                },
            )
            return override_variant

    # Edge cases: 0% or 100% (using math.isclose for float precision)
    if math.isclose(adaptive_percentage, MIN_PERCENTAGE, abs_tol=1e-9):
        logger.debug(
            f"A/B test assignment for user {user_id}: fixed (0% rollout)",
            extra={
                "user_id": user_id,
                "variant": "fixed",
                "assignment_method": "zero_percent",
                "adaptive_percentage": adaptive_percentage,
            },
        )
        return "fixed"

    if math.isclose(adaptive_percentage, MAX_PERCENTAGE, abs_tol=1e-9):
        logger.debug(
            f"A/B test assignment for user {user_id}: adaptive (100% rollout)",
            extra={
                "user_id": user_id,
                "variant": "adaptive",
                "assignment_method": "hundred_percent",
                "adaptive_percentage": adaptive_percentage,
            },
        )
        return "adaptive"

    # Use consistent hashing to assign variant
    # Convert user_id to bytes and hash with SHA-256
    user_id_bytes = str(user_id).encode("utf-8")
    hash_digest = hashlib.sha256(user_id_bytes).digest()

    # Convert first 8 bytes to integer (0 to MAX_HASH_INT)
    # Then normalize to range [0.0, 100.0]
    hash_int = int.from_bytes(hash_digest[:8], byteorder="big")
    hash_percentage = (hash_int / MAX_HASH_INT) * 100.0

    # Assign to adaptive if hash_percentage < adaptive_percentage
    variant: TestVariant = (
        "adaptive" if hash_percentage < adaptive_percentage else "fixed"
    )

    logger.debug(
        f"A/B test assignment for user {user_id}: {variant}",
        extra={
            "user_id": user_id,
            "variant": variant,
            "assignment_method": "hash",
            "adaptive_percentage": adaptive_percentage,
            "hash_percentage": hash_percentage,
        },
    )

    return variant


def set_admin_override(user_id: int, variant: TestVariant) -> None:
    """
    Force a specific user to a specific test variant (admin override).

    This allows administrators to manually assign users to variants,
    overriding the normal hash-based assignment. Useful for:
    - Testing specific scenarios
    - VIP users or beta testers
    - Debugging issues with specific variants

    Args:
        user_id: The user's ID to override
        variant: The variant to assign ("fixed" or "adaptive")

    Raises:
        ValueError: If user_id is not a positive integer
        ValueError: If variant is not "fixed" or "adaptive"

    Examples:
        >>> set_admin_override(user_id=123, variant="adaptive")
        >>> assign_test_variant(user_id=123, adaptive_percentage=0.0)
        'adaptive'  # Override takes precedence
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"user_id must be a positive integer, got: {user_id}")

    if variant not in ("fixed", "adaptive"):
        raise ValueError(f"variant must be 'fixed' or 'adaptive', got: {variant}")

    with _override_lock:
        _admin_overrides[user_id] = variant
    logger.info(
        f"Admin override set for user {user_id}: {variant}",
        extra={"user_id": user_id, "variant": variant, "action": "set_override"},
    )


def clear_admin_override(user_id: int) -> bool:
    """
    Remove admin override for a specific user.

    After calling this, the user will be assigned via normal hash-based logic.

    Args:
        user_id: The user's ID to clear override for

    Returns:
        True if override was removed, False if no override existed

    Raises:
        ValueError: If user_id is not a positive integer

    Examples:
        >>> set_admin_override(user_id=123, variant="adaptive")
        >>> clear_admin_override(user_id=123)
        True
        >>> clear_admin_override(user_id=123)
        False  # Already cleared
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"user_id must be a positive integer, got: {user_id}")

    with _override_lock:
        if user_id in _admin_overrides:
            prev_variant = _admin_overrides.pop(user_id)
            logger.info(
                f"Admin override cleared for user {user_id} (was: {prev_variant})",
                extra={
                    "user_id": user_id,
                    "previous_variant": prev_variant,
                    "action": "clear_override",
                },
            )
            return True
        return False


def clear_all_admin_overrides() -> int:
    """
    Clear all admin overrides.

    Useful for resetting test state or cleaning up after experiments.

    Returns:
        Number of overrides that were cleared

    Examples:
        >>> set_admin_override(user_id=123, variant="adaptive")
        >>> set_admin_override(user_id=456, variant="fixed")
        >>> clear_all_admin_overrides()
        2
    """
    with _override_lock:
        count = len(_admin_overrides)
        _admin_overrides.clear()

    if count > 0:
        logger.info(
            f"Cleared all admin overrides ({count} total)",
            extra={"count": count, "action": "clear_all_overrides"},
        )

    return count


def get_admin_override(user_id: int) -> Optional[TestVariant]:
    """
    Get the admin override for a specific user, if any.

    Args:
        user_id: The user's ID to check

    Returns:
        The overridden variant ("fixed" or "adaptive"), or None if no override exists

    Raises:
        ValueError: If user_id is not a positive integer

    Examples:
        >>> set_admin_override(user_id=123, variant="adaptive")
        >>> get_admin_override(user_id=123)
        'adaptive'
        >>> get_admin_override(user_id=999)
        None
    """
    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError(f"user_id must be a positive integer, got: {user_id}")

    with _override_lock:
        return _admin_overrides.get(user_id)


def get_all_admin_overrides() -> Dict[int, TestVariant]:
    """
    Get all admin overrides.

    Returns:
        Dictionary mapping user_id to variant for all overrides

    Examples:
        >>> set_admin_override(user_id=123, variant="adaptive")
        >>> set_admin_override(user_id=456, variant="fixed")
        >>> get_all_admin_overrides()
        {123: 'adaptive', 456: 'fixed'}
    """
    with _override_lock:
        return _admin_overrides.copy()
