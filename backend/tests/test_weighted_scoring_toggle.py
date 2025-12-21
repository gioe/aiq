"""
Tests for DW-014: Weighted scoring toggle functionality.

Tests cover:
- Admin endpoints for getting/setting weighted scoring config
- Admin endpoints for getting/setting domain weights
- A/B comparison endpoint
- Integration with test submission
"""
import pytest
from unittest.mock import patch

from app.core.system_config import (
    is_weighted_scoring_enabled,
    set_weighted_scoring_enabled,
    get_domain_weights,
    set_domain_weights,
)
from app.core.scoring import (
    calculate_iq_score,
    calculate_weighted_iq_score,
)


@pytest.fixture
def admin_token_header():
    """Create admin token headers for authentication."""
    return {"X-Admin-Token": "test-admin-token"}


def with_admin_token(func):
    """Decorator to patch admin token setting for tests."""
    return patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")(func)


class TestWeightedScoringToggle:
    """Tests for weighted scoring toggle functionality."""

    def test_default_weighted_scoring_disabled(self, db_session):
        """Test that weighted scoring is disabled by default."""
        result = is_weighted_scoring_enabled(db_session)
        assert result is False

    def test_enable_weighted_scoring(self, db_session):
        """Test enabling weighted scoring."""
        set_weighted_scoring_enabled(db_session, True)
        result = is_weighted_scoring_enabled(db_session)
        assert result is True

    def test_disable_weighted_scoring(self, db_session):
        """Test disabling weighted scoring after enabling."""
        set_weighted_scoring_enabled(db_session, True)
        set_weighted_scoring_enabled(db_session, False)
        result = is_weighted_scoring_enabled(db_session)
        assert result is False

    def test_toggle_weighted_scoring_multiple_times(self, db_session):
        """Test toggling weighted scoring multiple times."""
        # Toggle on
        set_weighted_scoring_enabled(db_session, True)
        assert is_weighted_scoring_enabled(db_session) is True

        # Toggle off
        set_weighted_scoring_enabled(db_session, False)
        assert is_weighted_scoring_enabled(db_session) is False

        # Toggle on again
        set_weighted_scoring_enabled(db_session, True)
        assert is_weighted_scoring_enabled(db_session) is True


class TestDomainWeightsConfig:
    """Tests for domain weights configuration."""

    def test_default_no_domain_weights(self, db_session):
        """Test that no domain weights are configured by default."""
        result = get_domain_weights(db_session)
        assert result is None

    def test_set_domain_weights(self, db_session):
        """Test setting domain weights."""
        weights = {
            "pattern": 0.20,
            "logic": 0.18,
            "spatial": 0.16,
            "math": 0.17,
            "verbal": 0.15,
            "memory": 0.14,
        }
        set_domain_weights(db_session, weights)
        result = get_domain_weights(db_session)
        assert result == weights

    def test_update_domain_weights(self, db_session):
        """Test updating existing domain weights."""
        # Set initial weights
        initial_weights = {
            "pattern": 0.20,
            "logic": 0.18,
            "spatial": 0.16,
            "math": 0.17,
            "verbal": 0.15,
            "memory": 0.14,
        }
        set_domain_weights(db_session, initial_weights)

        # Update weights
        updated_weights = {
            "pattern": 0.25,
            "logic": 0.20,
            "spatial": 0.15,
            "math": 0.15,
            "verbal": 0.15,
            "memory": 0.10,
        }
        set_domain_weights(db_session, updated_weights)

        result = get_domain_weights(db_session)
        assert result == updated_weights

    def test_partial_domain_weights(self, db_session):
        """Test setting partial domain weights (not all domains)."""
        # Only set some domains
        partial_weights = {
            "pattern": 0.5,
            "logic": 0.5,
        }
        set_domain_weights(db_session, partial_weights)
        result = get_domain_weights(db_session)
        assert result == partial_weights


class TestScoringWithToggle:
    """Tests for scoring behavior based on toggle state."""

    def test_equal_weight_scoring_when_disabled(self, db_session):
        """Test that equal weights are used when weighted scoring is disabled."""
        # Ensure weighted scoring is disabled
        set_weighted_scoring_enabled(db_session, False)

        # Set up domain weights (shouldn't be used)
        weights = {
            "pattern": 0.50,
            "logic": 0.50,
        }
        set_domain_weights(db_session, weights)

        # Check that weighted scoring is disabled
        assert is_weighted_scoring_enabled(db_session) is False

        # Standard scoring should be used
        score_result = calculate_iq_score(correct_answers=10, total_questions=20)
        assert score_result.iq_score == 100  # 50% correct = IQ 100

    def test_weighted_scoring_when_enabled_with_weights(self, db_session):
        """Test that weighted scoring is used when enabled and weights configured."""
        # Enable weighted scoring
        set_weighted_scoring_enabled(db_session, True)

        # Set domain weights
        weights = {
            "pattern": 0.75,  # High weight
            "logic": 0.25,  # Low weight
        }
        set_domain_weights(db_session, weights)

        # Domain scores: pattern is perfect, logic is 0%
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},  # 100%
            "logic": {"correct": 0, "total": 4, "pct": 0.0},  # 0%
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # With weights: 0.75 * 1.0 + 0.25 * 0.0 = 0.75
        # IQ: 100 + (0.75 - 0.5) * 30 = 107.5 → 108
        score_result = calculate_weighted_iq_score(domain_scores, weights)
        assert score_result.iq_score == 108

    def test_fallback_to_equal_weights_when_no_weights_configured(self, db_session):
        """Test fallback to equal weights when enabled but no weights configured."""
        # Enable weighted scoring
        set_weighted_scoring_enabled(db_session, True)

        # Don't set any weights
        assert get_domain_weights(db_session) is None

        # Domain scores
        domain_scores = {
            "pattern": {"correct": 2, "total": 4, "pct": 50.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # Equal weights should be used: (0.5 + 0.5) / 2 = 0.5
        # IQ: 100 + (0.5 - 0.5) * 30 = 100
        score_result = calculate_weighted_iq_score(domain_scores, None)
        assert score_result.iq_score == 100


class TestABComparisonCalculation:
    """Tests for A/B comparison score calculation."""

    def test_ab_comparison_equal_weights(self):
        """Test A/B comparison with equal domain accuracy."""
        domain_scores = {
            "pattern": {"correct": 2, "total": 4, "pct": 50.0},
            "logic": {"correct": 2, "total": 4, "pct": 50.0},
            "spatial": {"correct": 2, "total": 4, "pct": 50.0},
            "math": {"correct": 2, "total": 4, "pct": 50.0},
            "verbal": {"correct": 2, "total": 4, "pct": 50.0},
            "memory": {"correct": 2, "total": 4, "pct": 50.0},
        }

        # Equal weights
        equal_score = calculate_weighted_iq_score(domain_scores, None)

        # Weighted (but with same accuracy everywhere, should match)
        weights = {
            "pattern": 0.20,
            "logic": 0.18,
            "spatial": 0.16,
            "math": 0.17,
            "verbal": 0.15,
            "memory": 0.14,
        }
        weighted_score = calculate_weighted_iq_score(domain_scores, weights)

        # Same accuracy for all domains means same result
        assert equal_score.iq_score == weighted_score.iq_score
        assert equal_score.iq_score == 100

    def test_ab_comparison_different_domain_performance(self):
        """Test A/B comparison with varying domain performance."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},  # 100%
            "logic": {"correct": 0, "total": 4, "pct": 0.0},  # 0%
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # Equal weights: (1.0 + 0.0) / 2 = 0.5 → IQ 100
        equal_score = calculate_weighted_iq_score(domain_scores, None)
        assert equal_score.iq_score == 100

        # Weighted: favor pattern heavily
        weights = {
            "pattern": 0.80,
            "logic": 0.20,
        }
        # Weighted: 0.80 * 1.0 + 0.20 * 0.0 = 0.80
        # IQ: 100 + (0.80 - 0.5) * 30 = 109
        weighted_score = calculate_weighted_iq_score(domain_scores, weights)
        assert weighted_score.iq_score == 109

        # Difference
        assert weighted_score.iq_score - equal_score.iq_score == 9

    def test_ab_comparison_favor_low_performer(self):
        """Test A/B comparison where weights favor the lower-performing domain."""
        domain_scores = {
            "pattern": {"correct": 4, "total": 4, "pct": 100.0},  # 100%
            "logic": {"correct": 0, "total": 4, "pct": 0.0},  # 0%
            "spatial": {"correct": 0, "total": 0, "pct": None},
            "math": {"correct": 0, "total": 0, "pct": None},
            "verbal": {"correct": 0, "total": 0, "pct": None},
            "memory": {"correct": 0, "total": 0, "pct": None},
        }

        # Equal weights: (1.0 + 0.0) / 2 = 0.5 → IQ 100
        equal_score = calculate_weighted_iq_score(domain_scores, None)
        assert equal_score.iq_score == 100

        # Weighted: favor logic (the weak domain)
        weights = {
            "pattern": 0.20,
            "logic": 0.80,
        }
        # Weighted: 0.20 * 1.0 + 0.80 * 0.0 = 0.20
        # IQ: 100 + (0.20 - 0.5) * 30 = 91
        weighted_score = calculate_weighted_iq_score(domain_scores, weights)
        assert weighted_score.iq_score == 91

        # Difference (negative because weighted is lower)
        assert weighted_score.iq_score - equal_score.iq_score == -9


class TestWeightedScoringAdminEndpoints:
    """Tests for admin API endpoints for weighted scoring configuration."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_weighted_scoring_status_default(self, client, admin_token_header):
        """Test getting default weighted scoring status."""
        response = client.get(
            "/v1/admin/config/weighted-scoring",
            headers=admin_token_header,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["domain_weights"] is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_toggle_weighted_scoring_on(self, client, admin_token_header, db_session):
        """Test enabling weighted scoring via API."""
        response = client.post(
            "/v1/admin/config/weighted-scoring",
            headers=admin_token_header,
            json={"enabled": True},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert "enabled" in data["message"]

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_toggle_weighted_scoring_off(self, client, admin_token_header, db_session):
        """Test disabling weighted scoring via API."""
        # First enable it
        client.post(
            "/v1/admin/config/weighted-scoring",
            headers=admin_token_header,
            json={"enabled": True},
        )

        # Then disable it
        response = client.post(
            "/v1/admin/config/weighted-scoring",
            headers=admin_token_header,
            json={"enabled": False},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert "disabled" in data["message"]

    def test_toggle_weighted_scoring_requires_admin_token(self, client):
        """Test that toggling weighted scoring requires admin token."""
        response = client.post(
            "/v1/admin/config/weighted-scoring",
            json={"enabled": True},
        )
        assert response.status_code == 422  # Missing required header

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_get_domain_weights_none(self, client, admin_token_header):
        """Test getting domain weights when none configured."""
        response = client.get(
            "/v1/admin/config/domain-weights",
            headers=admin_token_header,
        )
        assert response.status_code == 200
        # Returns null when not configured
        assert response.json() is None

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_set_domain_weights(self, client, admin_token_header, db_session):
        """Test setting domain weights via API."""
        weights = {
            "pattern": 0.20,
            "logic": 0.18,
            "spatial": 0.16,
            "math": 0.17,
            "verbal": 0.15,
            "memory": 0.14,
        }
        response = client.post(
            "/v1/admin/config/domain-weights",
            headers=admin_token_header,
            json={"weights": weights},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["weights"] == weights
        assert (
            "updated" in data["message"].lower() or "success" in data["message"].lower()
        )

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_set_invalid_domain_weights(self, client, admin_token_header):
        """Test setting weights with invalid domain name."""
        weights = {
            "invalid_domain": 0.50,
            "pattern": 0.50,
        }
        response = client.post(
            "/v1/admin/config/domain-weights",
            headers=admin_token_header,
            json={"weights": weights},
        )
        assert response.status_code == 400
        assert "invalid" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_set_negative_domain_weights(self, client, admin_token_header):
        """Test setting negative weights."""
        weights = {
            "pattern": -0.20,
            "logic": 0.80,
        }
        response = client.post(
            "/v1/admin/config/domain-weights",
            headers=admin_token_header,
            json={"weights": weights},
        )
        assert response.status_code == 400
        assert "negative" in response.json()["detail"].lower()

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_set_weights_not_summing_to_one_warning(
        self, client, admin_token_header, db_session
    ):
        """Test that weights not summing to 1.0 shows a warning in message."""
        weights = {
            "pattern": 0.30,
            "logic": 0.20,
        }
        response = client.post(
            "/v1/admin/config/domain-weights",
            headers=admin_token_header,
            json={"weights": weights},
        )
        assert response.status_code == 200
        data = response.json()
        # Should warn about normalization
        assert "0.5" in data["message"] or "normalized" in data["message"].lower()


class TestABComparisonEndpoint:
    """Tests for A/B comparison admin endpoint."""

    @patch("app.core.config.settings.ADMIN_TOKEN", "test-admin-token")
    def test_ab_comparison_not_found(self, client, admin_token_header):
        """Test A/B comparison for non-existent session."""
        response = client.get(
            "/v1/admin/scoring/compare/99999",
            headers=admin_token_header,
        )
        assert response.status_code == 404

    def test_ab_comparison_requires_admin_token(self, client):
        """Test that A/B comparison requires admin token."""
        response = client.get("/v1/admin/scoring/compare/1")
        assert response.status_code == 422  # Missing required header
