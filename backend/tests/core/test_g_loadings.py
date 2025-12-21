"""
Unit tests for calculate_g_loadings() (DW-010).

Tests the g-loading factor analysis function that calculates empirical
g-loadings per cognitive domain using single-factor extraction.

Test Cases:
- Basic g-loading calculation with valid data
- Returns InsufficientSampleError when sample size is too small
- Returns InsufficientSampleError when too few items have variance
- Filters out items with zero/near-zero variance
- Calculates correct variance explained
- Calculates correct Cronbach's alpha
- Domain loadings are mean of item loadings per domain
- Item loadings are correctly mapped to question IDs
- Analysis warnings are generated appropriately
- Works with simulated data having known factor structure
"""

import pytest
import numpy as np
from typing import List

from app.core.analytics import (
    ResponseMatrixResult,
    GLoadingResult,
    calculate_g_loadings,
    calculate_cronbachs_alpha,
    InsufficientSampleError,
)


# =============================================================================
# FIXTURES AND HELPERS
# =============================================================================


def create_response_matrix(
    n_users: int,
    n_items: int,
    question_ids: List[int] = None,
    question_domains: List[str] = None,
    session_ids: List[int] = None,
    seed: int = 42,
) -> ResponseMatrixResult:
    """Create a ResponseMatrixResult with random binary data for testing."""
    np.random.seed(seed)

    matrix = np.random.randint(0, 2, size=(n_users, n_items), dtype=np.int8)

    if question_ids is None:
        question_ids = list(range(1, n_items + 1))

    if question_domains is None:
        # Distribute domains evenly
        domains = ["pattern", "logic", "spatial", "math", "verbal", "memory"]
        question_domains = [domains[i % len(domains)] for i in range(n_items)]

    if session_ids is None:
        session_ids = list(range(1, n_users + 1))

    return ResponseMatrixResult(
        matrix=matrix,
        question_ids=question_ids,
        question_domains=question_domains,
        session_ids=session_ids,
    )


def create_correlated_matrix(
    n_users: int,
    items_per_domain: int,
    domain_correlations: dict,
    base_difficulty: float = 0.5,
    seed: int = 42,
) -> ResponseMatrixResult:
    """
    Create a response matrix with known factor structure for testing.

    This simulates responses where items within the same domain are correlated
    through a common latent factor (g-factor).

    Args:
        n_users: Number of users/sessions.
        items_per_domain: Number of items per domain.
        domain_correlations: Dict mapping domain to g-loading (0-1).
            Higher values = more correlated with g.
        base_difficulty: Average probability of correct answer.
        seed: Random seed for reproducibility.

    Returns:
        ResponseMatrixResult with simulated correlated responses.
    """
    np.random.seed(seed)

    domains = list(domain_correlations.keys())
    n_items = len(domains) * items_per_domain

    # Generate latent g-factor for each user (ability level)
    g_factor = np.random.normal(0, 1, n_users)

    # Generate responses based on g-factor and domain loadings
    matrix = np.zeros((n_users, n_items), dtype=np.int8)
    question_domains = []
    question_ids = []

    item_idx = 0
    for domain in domains:
        loading = domain_correlations[domain]

        for _ in range(items_per_domain):
            # Item response probability = base + loading * g_factor
            # Add item-specific noise
            item_noise = np.random.normal(0, 0.3, n_users)
            probs = base_difficulty + loading * 0.3 * g_factor + item_noise

            # Clip to valid probability range
            probs = np.clip(probs, 0.1, 0.9)

            # Generate binary responses
            matrix[:, item_idx] = (np.random.random(n_users) < probs).astype(np.int8)

            question_domains.append(domain)
            question_ids.append(item_idx + 1)
            item_idx += 1

    session_ids = list(range(1, n_users + 1))

    return ResponseMatrixResult(
        matrix=matrix,
        question_ids=question_ids,
        question_domains=question_domains,
        session_ids=session_ids,
    )


# =============================================================================
# CRONBACH'S ALPHA TESTS
# =============================================================================


class TestCronbachsAlpha:
    """Tests for calculate_cronbachs_alpha helper function."""

    def test_perfect_reliability_identical_items(self):
        """Identical items should have high alpha (perfect internal consistency)."""
        # All items are the same (perfect correlation)
        matrix = np.array(
            [[1, 1, 1, 1], [0, 0, 0, 0], [1, 1, 1, 1], [0, 0, 0, 0]], dtype=np.int8
        )

        alpha = calculate_cronbachs_alpha(matrix)

        # Should be 1.0 for perfectly correlated items
        assert alpha == pytest.approx(1.0, abs=0.01)

    def test_zero_alpha_uncorrelated_items(self):
        """Uncorrelated items should have low alpha."""
        # Design items to be uncorrelated
        matrix = np.array(
            [
                [1, 0, 1, 0],
                [0, 1, 0, 1],
                [1, 0, 1, 0],
                [0, 1, 0, 1],
            ],
            dtype=np.int8,
        )

        alpha = calculate_cronbachs_alpha(matrix)

        # Should be low or negative for negatively correlated items
        assert alpha < 0.5

    def test_alpha_with_variance(self):
        """Alpha calculation with typical variance pattern."""
        # Create data with some correlation
        np.random.seed(42)
        n_users, n_items = 100, 10
        # Generate correlated responses
        ability = np.random.normal(0, 1, n_users)
        matrix = np.zeros((n_users, n_items), dtype=np.int8)
        for i in range(n_items):
            probs = 0.5 + 0.3 * ability + np.random.normal(0, 0.2, n_users)
            probs = np.clip(probs, 0.1, 0.9)
            matrix[:, i] = (np.random.random(n_users) < probs).astype(np.int8)

        alpha = calculate_cronbachs_alpha(matrix)

        # Should be positive and reasonable for correlated items
        assert 0.3 < alpha < 1.0

    def test_alpha_single_item_returns_zero(self):
        """Single item should return 0 (can't measure internal consistency)."""
        matrix = np.array([[1], [0], [1]], dtype=np.int8)

        alpha = calculate_cronbachs_alpha(matrix)

        assert alpha == pytest.approx(0.0)

    def test_alpha_zero_total_variance_returns_zero(self):
        """Zero total variance should return 0."""
        # All rows have same total score
        matrix = np.array([[1, 0], [0, 1], [1, 0], [0, 1]], dtype=np.int8)

        alpha = calculate_cronbachs_alpha(matrix)

        # Total score is always 1, so variance is 0
        assert alpha == pytest.approx(0.0)


# =============================================================================
# INSUFFICIENT SAMPLE SIZE TESTS
# =============================================================================


class TestInsufficientSampleSize:
    """Tests for sample size validation."""

    def test_raises_error_when_sample_too_small(self):
        """Raises InsufficientSampleError when below min_sample_size."""
        matrix_result = create_response_matrix(n_users=50, n_items=10)

        with pytest.raises(InsufficientSampleError) as exc_info:
            calculate_g_loadings(matrix_result, min_sample_size=100)

        assert exc_info.value.sample_size == 50
        assert exc_info.value.minimum_required == 100
        assert "50" in str(exc_info.value)
        assert "100" in str(exc_info.value)

    def test_accepts_exact_min_sample_size(self):
        """Accepts sample size exactly at minimum."""
        matrix_result = create_response_matrix(n_users=100, n_items=10)

        # Should not raise
        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert result.sample_size == 100

    def test_raises_error_when_too_few_items_have_variance(self):
        """Raises error when fewer than 3 items have sufficient variance."""
        # Create matrix where most items have zero variance
        matrix = np.zeros((100, 10), dtype=np.int8)
        # Only 2 items have variance
        matrix[:50, 0] = 1
        matrix[:30, 1] = 1

        matrix_result = ResponseMatrixResult(
            matrix=matrix,
            question_ids=list(range(1, 11)),
            question_domains=["pattern"] * 10,
            session_ids=list(range(1, 101)),
        )

        with pytest.raises(InsufficientSampleError) as exc_info:
            calculate_g_loadings(matrix_result, min_sample_size=50)

        assert "items have sufficient variance" in str(exc_info.value)


# =============================================================================
# BASIC FUNCTIONALITY TESTS
# =============================================================================


class TestCalculateGLoadingsBasic:
    """Basic tests for calculate_g_loadings function."""

    def test_returns_g_loading_result(self):
        """Returns a GLoadingResult dataclass."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert isinstance(result, GLoadingResult)

    def test_result_has_required_fields(self):
        """Result contains all required fields."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert hasattr(result, "domain_loadings")
        assert hasattr(result, "item_loadings")
        assert hasattr(result, "variance_explained")
        assert hasattr(result, "cronbachs_alpha")
        assert hasattr(result, "sample_size")
        assert hasattr(result, "n_items")
        assert hasattr(result, "analysis_warnings")

    def test_domain_loadings_are_dict(self):
        """domain_loadings is a dictionary."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert isinstance(result.domain_loadings, dict)

    def test_item_loadings_are_dict(self):
        """item_loadings is a dictionary."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert isinstance(result.item_loadings, dict)

    def test_loadings_are_float(self):
        """All loadings are float values."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        for loading in result.domain_loadings.values():
            assert isinstance(loading, float)

        for loading in result.item_loadings.values():
            assert isinstance(loading, float)

    def test_loadings_are_non_negative(self):
        """Loadings should be non-negative (absolute values used)."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        for loading in result.domain_loadings.values():
            assert loading >= 0

        for loading in result.item_loadings.values():
            assert loading >= 0

    def test_variance_explained_in_valid_range(self):
        """variance_explained should be between 0 and 1."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert 0 <= result.variance_explained <= 1

    def test_cronbachs_alpha_calculated(self):
        """Cronbach's alpha is calculated and reasonable."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Alpha can be negative but typically between -1 and 1
        assert -1 <= result.cronbachs_alpha <= 1

    def test_sample_size_in_result(self):
        """sample_size in result matches input."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert result.sample_size == 150


# =============================================================================
# DOMAIN LOADING TESTS
# =============================================================================


class TestDomainLoadings:
    """Tests for domain loading calculations."""

    def test_all_domains_have_loadings(self):
        """All domains in input have loadings in output."""
        domains = ["pattern", "logic", "spatial", "math", "verbal", "memory"]
        question_domains = domains * 2  # 2 items per domain

        matrix_result = create_response_matrix(
            n_users=150,
            n_items=12,
            question_domains=question_domains,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        for domain in domains:
            assert domain in result.domain_loadings

    def test_domain_loadings_within_bounds(self):
        """Domain loadings should be between 0 and 1."""
        matrix_result = create_response_matrix(n_users=200, n_items=18)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        for loading in result.domain_loadings.values():
            assert 0 <= loading <= 1


# =============================================================================
# ITEM LOADING TESTS
# =============================================================================


class TestItemLoadings:
    """Tests for item loading calculations."""

    def test_item_ids_match_input(self):
        """Item IDs in output match valid items from input."""
        question_ids = [101, 102, 103, 104, 105, 106]
        matrix_result = create_response_matrix(
            n_users=150,
            n_items=6,
            question_ids=question_ids,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # At least some items should be in the result
        assert len(result.item_loadings) > 0

        # All returned IDs should be from the input
        for item_id in result.item_loadings.keys():
            assert item_id in question_ids

    def test_item_loadings_within_bounds(self):
        """Item loadings should be between 0 and 1."""
        matrix_result = create_response_matrix(n_users=200, n_items=18)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        for loading in result.item_loadings.values():
            assert 0 <= loading <= 1


# =============================================================================
# VARIANCE FILTERING TESTS
# =============================================================================


class TestVarianceFiltering:
    """Tests for item variance filtering."""

    def test_excludes_zero_variance_items(self):
        """Items with zero variance are excluded."""
        # Create matrix with some zero-variance items
        n_users = 150
        matrix = np.random.randint(0, 2, size=(n_users, 10), dtype=np.int8)
        # Make items 3 and 7 have zero variance (all 1s)
        matrix[:, 3] = 1
        matrix[:, 7] = 1

        matrix_result = ResponseMatrixResult(
            matrix=matrix,
            question_ids=[1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            question_domains=["pattern"] * 10,
            session_ids=list(range(1, n_users + 1)),
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Items 4 and 8 (ids for indices 3 and 7) should be excluded
        assert 4 not in result.item_loadings
        assert 8 not in result.item_loadings

    def test_warning_when_items_excluded(self):
        """Warning generated when items are excluded due to low variance."""
        n_users = 150
        matrix = np.random.randint(0, 2, size=(n_users, 10), dtype=np.int8)
        # Make 2 items have zero variance
        matrix[:, 0] = 1
        matrix[:, 1] = 0

        matrix_result = ResponseMatrixResult(
            matrix=matrix,
            question_ids=list(range(1, 11)),
            question_domains=["pattern"] * 10,
            session_ids=list(range(1, n_users + 1)),
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Should have warning about excluded items
        assert any("excluded" in w.lower() for w in result.analysis_warnings)

    def test_n_items_reflects_valid_items_only(self):
        """n_items in result only counts items with valid variance."""
        n_users = 150
        matrix = np.random.randint(0, 2, size=(n_users, 10), dtype=np.int8)
        # Make 3 items have zero variance
        matrix[:, 0] = 1
        matrix[:, 1] = 0
        matrix[:, 2] = 1

        matrix_result = ResponseMatrixResult(
            matrix=matrix,
            question_ids=list(range(1, 11)),
            question_domains=["pattern"] * 10,
            session_ids=list(range(1, n_users + 1)),
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Should only count 7 valid items
        assert result.n_items == 7


# =============================================================================
# SIMULATED DATA TESTS
# =============================================================================


class TestSimulatedFactorStructure:
    """Tests using simulated data with known factor structure."""

    def test_higher_loading_domains_rank_correctly(self):
        """Domains with higher true loadings should have higher estimated loadings."""
        # Create data where domains have different known correlations with g
        domain_correlations = {
            "pattern": 0.8,
            "logic": 0.7,
            "math": 0.6,
            "verbal": 0.5,
            "spatial": 0.4,
            "memory": 0.3,
        }

        matrix_result = create_correlated_matrix(
            n_users=500,  # Need more users for stable estimates
            items_per_domain=5,
            domain_correlations=domain_correlations,
            seed=42,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Get sorted domains by loading
        sorted_domains = sorted(
            result.domain_loadings.keys(),
            key=lambda d: result.domain_loadings[d],
            reverse=True,
        )

        # Top 3 should include the highest true loadings
        top_3 = set(sorted_domains[:3])
        expected_top_3 = {"pattern", "logic", "math"}

        # At least 2 of the top 3 should match
        assert len(top_3.intersection(expected_top_3)) >= 2

    def test_variance_explained_reasonable_for_factor_structure(self):
        """Variance explained should be reasonable for data with factor structure."""
        domain_correlations = {
            "pattern": 0.7,
            "logic": 0.7,
            "math": 0.6,
            "verbal": 0.6,
            "spatial": 0.5,
            "memory": 0.5,
        }

        matrix_result = create_correlated_matrix(
            n_users=300,
            items_per_domain=4,
            domain_correlations=domain_correlations,
            seed=42,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # With correlated data, variance explained should be > 10%
        assert result.variance_explained > 0.1

    def test_cronbachs_alpha_acceptable_for_correlated_data(self):
        """Cronbach's alpha should be acceptable for correlated data."""
        domain_correlations = {
            "pattern": 0.7,
            "logic": 0.7,
            "math": 0.6,
            "verbal": 0.6,
        }

        matrix_result = create_correlated_matrix(
            n_users=300,
            items_per_domain=5,
            domain_correlations=domain_correlations,
            seed=42,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Alpha should be positive for correlated items
        assert result.cronbachs_alpha > 0


# =============================================================================
# WARNING GENERATION TESTS
# =============================================================================


class TestAnalysisWarnings:
    """Tests for analysis warning generation."""

    def test_warnings_is_list(self):
        """analysis_warnings is always a list."""
        matrix_result = create_response_matrix(n_users=150, n_items=12)

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert isinstance(result.analysis_warnings, list)

    def test_no_warnings_for_good_data(self):
        """Well-behaved data should produce few or no warnings."""
        domain_correlations = {
            "pattern": 0.7,
            "logic": 0.6,
            "math": 0.5,
        }

        matrix_result = create_correlated_matrix(
            n_users=500,
            items_per_domain=8,
            domain_correlations=domain_correlations,
            seed=42,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # May have some warnings, but should not have item exclusion warnings
        exclusion_warnings = [
            w for w in result.analysis_warnings if "excluded" in w.lower()
        ]
        # With good simulated data, we shouldn't have many exclusions
        assert len(exclusion_warnings) <= 1


# =============================================================================
# EDGE CASE TESTS
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_minimum_valid_items(self):
        """Works with exactly 3 valid items (minimum required)."""
        n_users = 150
        # Create matrix with only 3 items having variance
        matrix = np.zeros((n_users, 5), dtype=np.int8)
        # Make 3 items have variance
        np.random.seed(42)
        matrix[:, 0] = np.random.randint(0, 2, n_users)
        matrix[:, 1] = np.random.randint(0, 2, n_users)
        matrix[:, 2] = np.random.randint(0, 2, n_users)
        # Items 3 and 4 have no variance
        matrix[:, 3] = 1
        matrix[:, 4] = 0

        matrix_result = ResponseMatrixResult(
            matrix=matrix,
            question_ids=[1, 2, 3, 4, 5],
            question_domains=["pattern", "logic", "math", "verbal", "spatial"],
            session_ids=list(range(1, n_users + 1)),
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert result.n_items == 3
        assert len(result.item_loadings) == 3

    def test_single_domain_works(self):
        """Works when all items are from a single domain."""
        matrix_result = create_response_matrix(
            n_users=150,
            n_items=10,
            question_domains=["pattern"] * 10,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        # Should only have one domain
        assert len(result.domain_loadings) == 1
        assert "pattern" in result.domain_loadings

    def test_large_dataset(self):
        """Handles larger datasets correctly."""
        matrix_result = create_response_matrix(
            n_users=1000,
            n_items=50,
        )

        result = calculate_g_loadings(matrix_result, min_sample_size=100)

        assert result.sample_size == 1000
        assert result.n_items > 0  # Some items should pass variance filter
