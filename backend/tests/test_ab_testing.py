"""
Unit tests for A/B testing assignment logic (TASK-885).

Tests verify:
- Distribution matches target percentage (within 5% tolerance)
- Same user always gets same variant (deterministic)
- Admin overrides work correctly
- Edge cases (0%, 100%, invalid inputs)
"""

import pytest
from collections import Counter

from app.core.ab_testing import (
    assign_test_variant,
    set_admin_override,
    clear_admin_override,
    clear_all_admin_overrides,
    get_admin_override,
    get_all_admin_overrides,
)


class TestAssignTestVariant:
    """Tests for the assign_test_variant function."""

    def setup_method(self):
        """Clear admin overrides before each test."""
        clear_all_admin_overrides()

    def teardown_method(self):
        """Clear admin overrides after each test."""
        clear_all_admin_overrides()

    # =========================================================================
    # Distribution Tests - Verify percentage accuracy
    # =========================================================================

    def test_distribution_10_percent(self):
        """Test that 10% rollout assigns ~10% to adaptive (within 5% tolerance)."""
        adaptive_percentage = 10.0
        sample_size = 1000
        tolerance = 5.0  # Allow ±5% deviation

        # Assign variants to 1000 users
        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        # Count assignments
        counts = Counter(assignments)
        adaptive_count = counts["adaptive"]
        adaptive_actual = (adaptive_count / sample_size) * 100.0

        # Verify within tolerance (5% to 15% for 10% target)
        assert (
            adaptive_percentage - tolerance
            <= adaptive_actual
            <= adaptive_percentage + tolerance
        ), f"Expected ~{adaptive_percentage}% adaptive, got {adaptive_actual:.2f}%"

    def test_distribution_50_percent(self):
        """Test that 50% rollout assigns ~50% to adaptive (within 5% tolerance)."""
        adaptive_percentage = 50.0
        sample_size = 1000
        tolerance = 5.0

        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        counts = Counter(assignments)
        adaptive_count = counts["adaptive"]
        adaptive_actual = (adaptive_count / sample_size) * 100.0

        assert (
            adaptive_percentage - tolerance
            <= adaptive_actual
            <= adaptive_percentage + tolerance
        ), f"Expected ~{adaptive_percentage}% adaptive, got {adaptive_actual:.2f}%"

    def test_distribution_90_percent(self):
        """Test that 90% rollout assigns ~90% to adaptive (within 5% tolerance)."""
        adaptive_percentage = 90.0
        sample_size = 1000
        tolerance = 5.0

        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        counts = Counter(assignments)
        adaptive_count = counts["adaptive"]
        adaptive_actual = (adaptive_count / sample_size) * 100.0

        assert (
            adaptive_percentage - tolerance
            <= adaptive_actual
            <= adaptive_percentage + tolerance
        ), f"Expected ~{adaptive_percentage}% adaptive, got {adaptive_actual:.2f}%"

    def test_distribution_25_percent(self):
        """Test that 25% rollout assigns ~25% to adaptive (within 5% tolerance)."""
        adaptive_percentage = 25.0
        sample_size = 1000
        tolerance = 5.0

        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        counts = Counter(assignments)
        adaptive_count = counts["adaptive"]
        adaptive_actual = (adaptive_count / sample_size) * 100.0

        assert (
            adaptive_percentage - tolerance
            <= adaptive_actual
            <= adaptive_percentage + tolerance
        ), f"Expected ~{adaptive_percentage}% adaptive, got {adaptive_actual:.2f}%"

    # =========================================================================
    # Determinism Tests - Verify same user gets same variant
    # =========================================================================

    def test_deterministic_assignment(self):
        """Test that same user_id always gets same variant."""
        user_id = 12345
        adaptive_percentage = 50.0

        # Call multiple times
        variant1 = assign_test_variant(
            user_id=user_id, adaptive_percentage=adaptive_percentage
        )
        variant2 = assign_test_variant(
            user_id=user_id, adaptive_percentage=adaptive_percentage
        )
        variant3 = assign_test_variant(
            user_id=user_id, adaptive_percentage=adaptive_percentage
        )

        # All should be the same
        assert variant1 == variant2 == variant3

    def test_deterministic_across_percentages(self):
        """Test that increasing percentage doesn't change existing assignments inconsistently."""
        user_id = 42

        # Get assignment at 10%
        variant_10 = assign_test_variant(user_id=user_id, adaptive_percentage=10.0)

        # Get assignment at 50%
        variant_50 = assign_test_variant(user_id=user_id, adaptive_percentage=50.0)

        # If user was in adaptive at 10%, they must be in adaptive at 50%
        # (increasing percentage only adds more users to adaptive, doesn't remove)
        if variant_10 == "adaptive":
            assert (
                variant_50 == "adaptive"
            ), "User in adaptive at 10% must stay in adaptive at 50%"

    def test_multiple_users_deterministic(self):
        """Test determinism for multiple users."""
        user_ids = [1, 10, 100, 1000, 9999]
        adaptive_percentage = 30.0

        for user_id in user_ids:
            variant1 = assign_test_variant(
                user_id=user_id, adaptive_percentage=adaptive_percentage
            )
            variant2 = assign_test_variant(
                user_id=user_id, adaptive_percentage=adaptive_percentage
            )
            assert variant1 == variant2, f"User {user_id} got different variants"

    # =========================================================================
    # Edge Cases - 0%, 100%
    # =========================================================================

    def test_zero_percent_all_fixed(self):
        """Test that 0% rollout assigns everyone to fixed."""
        adaptive_percentage = 0.0
        sample_size = 100

        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        # All should be fixed
        assert all(variant == "fixed" for variant in assignments)

    def test_hundred_percent_all_adaptive(self):
        """Test that 100% rollout assigns everyone to adaptive."""
        adaptive_percentage = 100.0
        sample_size = 100

        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        # All should be adaptive
        assert all(variant == "adaptive" for variant in assignments)

    # =========================================================================
    # Input Validation Tests
    # =========================================================================

    def test_invalid_user_id_negative(self):
        """Test that negative user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            assign_test_variant(user_id=-1, adaptive_percentage=50.0)

    def test_invalid_user_id_zero(self):
        """Test that zero user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            assign_test_variant(user_id=0, adaptive_percentage=50.0)

    def test_invalid_user_id_string(self):
        """Test that string user_id raises ValueError."""
        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            assign_test_variant(user_id="123", adaptive_percentage=50.0)  # type: ignore

    def test_invalid_percentage_negative(self):
        """Test that negative percentage raises ValueError."""
        with pytest.raises(ValueError, match="adaptive_percentage must be between"):
            assign_test_variant(user_id=1, adaptive_percentage=-10.0)

    def test_invalid_percentage_over_100(self):
        """Test that percentage > 100 raises ValueError."""
        with pytest.raises(ValueError, match="adaptive_percentage must be between"):
            assign_test_variant(user_id=1, adaptive_percentage=150.0)

    def test_invalid_percentage_string(self):
        """Test that string percentage raises ValueError."""
        with pytest.raises(ValueError, match="adaptive_percentage must be a number"):
            assign_test_variant(user_id=1, adaptive_percentage="50")  # type: ignore

    # =========================================================================
    # Valid Edge Values
    # =========================================================================

    def test_valid_percentage_decimal(self):
        """Test that decimal percentages work (e.g., 12.5%)."""
        variant = assign_test_variant(user_id=1, adaptive_percentage=12.5)
        assert variant in ("fixed", "adaptive")

    def test_valid_percentage_integer(self):
        """Test that integer percentages work."""
        variant = assign_test_variant(user_id=1, adaptive_percentage=50)
        assert variant in ("fixed", "adaptive")

    def test_valid_small_user_id(self):
        """Test that small user_id (1) works."""
        variant = assign_test_variant(user_id=1, adaptive_percentage=50.0)
        assert variant in ("fixed", "adaptive")

    def test_valid_large_user_id(self):
        """Test that large user_id works."""
        variant = assign_test_variant(user_id=999999999, adaptive_percentage=50.0)
        assert variant in ("fixed", "adaptive")


class TestAdminOverrides:
    """Tests for admin override functionality."""

    def setup_method(self):
        """Clear admin overrides before each test."""
        clear_all_admin_overrides()

    def teardown_method(self):
        """Clear admin overrides after each test."""
        clear_all_admin_overrides()

    # =========================================================================
    # Basic Override Tests
    # =========================================================================

    def test_set_admin_override_adaptive(self):
        """Test setting admin override to adaptive."""
        user_id = 123
        set_admin_override(user_id=user_id, variant="adaptive")

        # User should get adaptive even at 0% rollout
        variant = assign_test_variant(user_id=user_id, adaptive_percentage=0.0)
        assert variant == "adaptive"

    def test_set_admin_override_fixed(self):
        """Test setting admin override to fixed."""
        user_id = 456
        set_admin_override(user_id=user_id, variant="fixed")

        # User should get fixed even at 100% rollout
        variant = assign_test_variant(user_id=user_id, adaptive_percentage=100.0)
        assert variant == "fixed"

    def test_override_takes_precedence(self):
        """Test that admin override takes precedence over hash assignment."""
        user_id = 789

        # Set override to adaptive
        set_admin_override(user_id=user_id, variant="adaptive")

        # Should get adaptive at any percentage
        assert (
            assign_test_variant(user_id=user_id, adaptive_percentage=0.0) == "adaptive"
        )
        assert (
            assign_test_variant(user_id=user_id, adaptive_percentage=50.0) == "adaptive"
        )
        assert (
            assign_test_variant(user_id=user_id, adaptive_percentage=100.0)
            == "adaptive"
        )

    def test_multiple_overrides(self):
        """Test setting overrides for multiple users."""
        set_admin_override(user_id=1, variant="adaptive")
        set_admin_override(user_id=2, variant="fixed")
        set_admin_override(user_id=3, variant="adaptive")

        assert assign_test_variant(user_id=1, adaptive_percentage=0.0) == "adaptive"
        assert assign_test_variant(user_id=2, adaptive_percentage=100.0) == "fixed"
        assert assign_test_variant(user_id=3, adaptive_percentage=0.0) == "adaptive"

    # =========================================================================
    # Clear Override Tests
    # =========================================================================

    def test_clear_admin_override(self):
        """Test clearing a single admin override."""
        user_id = 123
        set_admin_override(user_id=user_id, variant="adaptive")

        # Clear the override
        result = clear_admin_override(user_id=user_id)
        assert result is True

        # User should now follow normal hash assignment
        # At 0%, should get fixed (not adaptive)
        variant = assign_test_variant(user_id=user_id, adaptive_percentage=0.0)
        assert variant == "fixed"

    def test_clear_nonexistent_override(self):
        """Test clearing an override that doesn't exist."""
        result = clear_admin_override(user_id=999)
        assert result is False

    def test_clear_all_admin_overrides(self):
        """Test clearing all admin overrides."""
        set_admin_override(user_id=1, variant="adaptive")
        set_admin_override(user_id=2, variant="fixed")
        set_admin_override(user_id=3, variant="adaptive")

        count = clear_all_admin_overrides()
        assert count == 3

        # All users should now follow normal hash assignment
        variant1 = assign_test_variant(user_id=1, adaptive_percentage=0.0)
        variant2 = assign_test_variant(user_id=2, adaptive_percentage=100.0)
        variant3 = assign_test_variant(user_id=3, adaptive_percentage=0.0)

        assert variant1 == "fixed"  # 0% rollout
        assert variant2 == "adaptive"  # 100% rollout
        assert variant3 == "fixed"  # 0% rollout

    def test_clear_all_when_empty(self):
        """Test clearing all overrides when none exist."""
        count = clear_all_admin_overrides()
        assert count == 0

    # =========================================================================
    # Get Override Tests
    # =========================================================================

    def test_get_admin_override_exists(self):
        """Test getting an existing admin override."""
        user_id = 123
        set_admin_override(user_id=user_id, variant="adaptive")

        override = get_admin_override(user_id=user_id)
        assert override == "adaptive"

    def test_get_admin_override_not_exists(self):
        """Test getting a non-existent admin override."""
        override = get_admin_override(user_id=999)
        assert override is None

    def test_get_all_admin_overrides(self):
        """Test getting all admin overrides."""
        set_admin_override(user_id=1, variant="adaptive")
        set_admin_override(user_id=2, variant="fixed")
        set_admin_override(user_id=3, variant="adaptive")

        overrides = get_all_admin_overrides()
        assert overrides == {1: "adaptive", 2: "fixed", 3: "adaptive"}

    def test_get_all_admin_overrides_empty(self):
        """Test getting all overrides when none exist."""
        overrides = get_all_admin_overrides()
        assert overrides == {}

    def test_get_all_returns_copy(self):
        """Test that get_all_admin_overrides returns a copy (not reference)."""
        set_admin_override(user_id=1, variant="adaptive")

        overrides = get_all_admin_overrides()
        overrides[2] = "fixed"  # Modify the returned dict

        # Original should be unchanged
        assert get_admin_override(user_id=2) is None

    # =========================================================================
    # Override Input Validation
    # =========================================================================

    def test_set_override_invalid_user_id(self):
        """Test that set_admin_override validates user_id."""
        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            set_admin_override(user_id=-1, variant="adaptive")

        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            set_admin_override(user_id=0, variant="adaptive")

    def test_set_override_invalid_variant(self):
        """Test that set_admin_override validates variant."""
        with pytest.raises(ValueError, match="variant must be 'fixed' or 'adaptive'"):
            set_admin_override(user_id=1, variant="invalid")  # type: ignore

        with pytest.raises(ValueError, match="variant must be 'fixed' or 'adaptive'"):
            set_admin_override(user_id=1, variant="")  # type: ignore

    def test_clear_override_invalid_user_id(self):
        """Test that clear_admin_override validates user_id."""
        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            clear_admin_override(user_id=-1)

        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            clear_admin_override(user_id=0)

    def test_get_override_invalid_user_id(self):
        """Test that get_admin_override validates user_id."""
        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            get_admin_override(user_id=-1)

        with pytest.raises(ValueError, match="user_id must be a positive integer"):
            get_admin_override(user_id=0)

    # =========================================================================
    # Override Update Tests
    # =========================================================================

    def test_override_can_be_updated(self):
        """Test that an override can be changed."""
        user_id = 123

        # Set to adaptive
        set_admin_override(user_id=user_id, variant="adaptive")
        assert (
            assign_test_variant(user_id=user_id, adaptive_percentage=0.0) == "adaptive"
        )

        # Change to fixed
        set_admin_override(user_id=user_id, variant="fixed")
        assert (
            assign_test_variant(user_id=user_id, adaptive_percentage=100.0) == "fixed"
        )


class TestHashingConsistency:
    """Tests for hashing consistency and distribution properties."""

    def setup_method(self):
        """Clear admin overrides before each test."""
        clear_all_admin_overrides()

    def teardown_method(self):
        """Clear admin overrides after each test."""
        clear_all_admin_overrides()

    def test_different_users_different_hashes(self):
        """Test that different user IDs can get different assignments."""
        adaptive_percentage = 50.0

        # With 50% split, we should see both variants in a small sample
        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, 21)
        ]

        counts = Counter(assignments)
        # With 20 users at 50%, we should see both variants (very high probability)
        assert "fixed" in counts, "Should have some users assigned to fixed"
        assert "adaptive" in counts, "Should have some users assigned to adaptive"

    def test_consecutive_user_ids_mixed_assignments(self):
        """Test that consecutive user IDs don't all get same variant."""
        adaptive_percentage = 50.0

        # Test 10 consecutive users
        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(100, 110)
        ]

        # Should have both variants (consecutive IDs should not all hash to same bucket)
        counts = Counter(assignments)
        assert (
            len(counts) == 2
        ), "Consecutive user IDs should distribute across both variants"

    def test_large_sample_distribution_accuracy(self):
        """Test distribution accuracy with large sample (10000 users)."""
        adaptive_percentage = 50.0
        sample_size = 10000
        tolerance = 2.0  # Tighter tolerance with larger sample

        assignments = [
            assign_test_variant(user_id=i, adaptive_percentage=adaptive_percentage)
            for i in range(1, sample_size + 1)
        ]

        counts = Counter(assignments)
        adaptive_count = counts["adaptive"]
        adaptive_actual = (adaptive_count / sample_size) * 100.0

        assert (
            adaptive_percentage - tolerance
            <= adaptive_actual
            <= adaptive_percentage + tolerance
        ), f"Expected ~{adaptive_percentage}% adaptive, got {adaptive_actual:.2f}%"
