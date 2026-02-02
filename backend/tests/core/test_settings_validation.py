"""
Tests for Settings configuration validation in config.py.
"""
import pytest
from pydantic import ValidationError

# Test credentials for Settings instantiation
TEST_SECRET_KEY = "test-secret-key-for-unit-tests"  # pragma: allowlist secret
TEST_JWT_SECRET_KEY = "test-jwt-secret-key-for-unit-tests"  # pragma: allowlist secret


class TestSentryTracesSampleRateValidation:
    """Tests for SENTRY_TRACES_SAMPLE_RATE validation."""

    def test_valid_sample_rate_default(self):
        """Test that the default sample rate (0.1) is valid."""
        # Import fresh Settings class (uses default values)
        from app.core.config import Settings

        # Create a settings instance with required fields
        settings = Settings(
            SECRET_KEY=TEST_SECRET_KEY,
            JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
        )
        assert settings.SENTRY_TRACES_SAMPLE_RATE == pytest.approx(0.1)

    def test_valid_sample_rate_zero(self):
        """Test that 0.0 is a valid sample rate (disables tracing)."""
        from app.core.config import Settings

        settings = Settings(
            SECRET_KEY=TEST_SECRET_KEY,
            JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
            SENTRY_TRACES_SAMPLE_RATE=0.0,
        )
        assert settings.SENTRY_TRACES_SAMPLE_RATE == pytest.approx(0.0)

    def test_valid_sample_rate_one(self):
        """Test that 1.0 is a valid sample rate (traces all transactions)."""
        from app.core.config import Settings

        settings = Settings(
            SECRET_KEY=TEST_SECRET_KEY,
            JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
            SENTRY_TRACES_SAMPLE_RATE=1.0,
        )
        assert settings.SENTRY_TRACES_SAMPLE_RATE == pytest.approx(1.0)

    def test_valid_sample_rate_middle(self):
        """Test that a value in the middle of the range is valid."""
        from app.core.config import Settings

        settings = Settings(
            SECRET_KEY=TEST_SECRET_KEY,
            JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
            SENTRY_TRACES_SAMPLE_RATE=0.5,
        )
        assert settings.SENTRY_TRACES_SAMPLE_RATE == pytest.approx(0.5)

    def test_invalid_sample_rate_negative(self):
        """Test that negative values are rejected."""
        from app.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY=TEST_SECRET_KEY,
                JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
                SENTRY_TRACES_SAMPLE_RATE=-0.1,
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("SENTRY_TRACES_SAMPLE_RATE",)
        assert "greater than or equal to 0" in errors[0]["msg"]

    def test_invalid_sample_rate_greater_than_one(self):
        """Test that values greater than 1.0 are rejected."""
        from app.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY=TEST_SECRET_KEY,
                JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
                SENTRY_TRACES_SAMPLE_RATE=1.1,
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("SENTRY_TRACES_SAMPLE_RATE",)
        assert "less than or equal to 1" in errors[0]["msg"]

    def test_invalid_sample_rate_large_negative(self):
        """Test that large negative values are rejected."""
        from app.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY=TEST_SECRET_KEY,
                JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
                SENTRY_TRACES_SAMPLE_RATE=-100.0,
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("SENTRY_TRACES_SAMPLE_RATE",)

    def test_invalid_sample_rate_large_positive(self):
        """Test that large positive values are rejected."""
        from app.core.config import Settings

        with pytest.raises(ValidationError) as exc_info:
            Settings(
                SECRET_KEY=TEST_SECRET_KEY,
                JWT_SECRET_KEY=TEST_JWT_SECRET_KEY,
                SENTRY_TRACES_SAMPLE_RATE=100.0,
            )
        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("SENTRY_TRACES_SAMPLE_RATE",)


class TestDomainWeightsConfiguration:
    """Tests for TEST_DOMAIN_WEIGHTS configuration constant."""

    def test_weights_sum_to_one(self):
        """Domain weights must sum to exactly 1.0."""
        from app.core.config import settings

        total = sum(settings.TEST_DOMAIN_WEIGHTS.values())
        assert total == pytest.approx(1.0)

    def test_contains_all_question_types(self):
        """Weights must include all six cognitive domains from QuestionType."""
        from app.core.config import settings
        from app.models.models import QuestionType

        expected_domains = {qt.value for qt in QuestionType}
        actual_domains = set(settings.TEST_DOMAIN_WEIGHTS.keys())
        assert actual_domains == expected_domains

    def test_all_weights_positive(self):
        """Every domain weight must be positive."""
        from app.core.config import settings

        for domain, weight in settings.TEST_DOMAIN_WEIGHTS.items():
            assert weight > 0, f"Weight for '{domain}' must be positive, got {weight}"

    def test_gf_domains_have_highest_combined_weight(self):
        """Fluid reasoning (pattern + logic) should have the highest combined weight.

        Reflects Gf's empirical g-loading primacy in CHC theory.
        """
        from app.core.config import settings

        gf_weight = (
            settings.TEST_DOMAIN_WEIGHTS["pattern"]
            + settings.TEST_DOMAIN_WEIGHTS["logic"]
        )
        for other_domain in ["spatial", "math", "verbal", "memory"]:
            assert gf_weight > settings.TEST_DOMAIN_WEIGHTS[other_domain], (
                f"Combined Gf weight ({gf_weight}) should exceed any single domain "
                f"({other_domain}: {settings.TEST_DOMAIN_WEIGHTS[other_domain]})"
            )
