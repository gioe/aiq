"""Tests for configuration settings."""

import pytest
from unittest.mock import patch

from app.config import Settings


class TestDedupConfig:
    """Tests for deduplication configuration settings."""

    def test_default_dedup_similarity_threshold(self):
        """Test default similarity threshold value."""
        settings = Settings()
        assert settings.dedup_similarity_threshold == pytest.approx(0.85)

    def test_default_dedup_embedding_model(self):
        """Test default embedding model value."""
        settings = Settings()
        assert settings.dedup_embedding_model == "text-embedding-3-small"

    def test_custom_dedup_similarity_threshold_from_env(self):
        """Test loading custom similarity threshold from environment."""
        with patch.dict(
            "os.environ", {"DEDUP_SIMILARITY_THRESHOLD": "0.90"}, clear=False
        ):
            settings = Settings()
            assert settings.dedup_similarity_threshold == pytest.approx(0.90)

    def test_custom_dedup_embedding_model_from_env(self):
        """Test loading custom embedding model from environment."""
        with patch.dict(
            "os.environ",
            {"DEDUP_EMBEDDING_MODEL": "text-embedding-ada-002"},
            clear=False,
        ):
            settings = Settings()
            assert settings.dedup_embedding_model == "text-embedding-ada-002"

    def test_similarity_threshold_boundary_zero(self):
        """Test similarity threshold at boundary value 0.0."""
        with patch.dict(
            "os.environ", {"DEDUP_SIMILARITY_THRESHOLD": "0.0"}, clear=False
        ):
            settings = Settings()
            assert settings.dedup_similarity_threshold == pytest.approx(0.0)

    def test_similarity_threshold_boundary_one(self):
        """Test similarity threshold at boundary value 1.0."""
        with patch.dict(
            "os.environ", {"DEDUP_SIMILARITY_THRESHOLD": "1.0"}, clear=False
        ):
            settings = Settings()
            assert settings.dedup_similarity_threshold == pytest.approx(1.0)


class TestCircuitBreakerConfig:
    """Tests for circuit breaker configuration settings."""

    def test_default_circuit_breaker_enabled(self):
        """Test default circuit breaker enabled value."""
        settings = Settings()
        assert settings.circuit_breaker_enabled is True

    def test_default_circuit_breaker_failure_threshold(self):
        """Test default failure threshold value."""
        settings = Settings()
        assert settings.circuit_breaker_failure_threshold == 5

    def test_default_circuit_breaker_error_rate_threshold(self):
        """Test default error rate threshold value."""
        settings = Settings()
        assert settings.circuit_breaker_error_rate_threshold == pytest.approx(0.5)

    def test_default_circuit_breaker_recovery_timeout(self):
        """Test default recovery timeout value."""
        settings = Settings()
        assert settings.circuit_breaker_recovery_timeout == pytest.approx(60.0)

    def test_default_circuit_breaker_success_threshold(self):
        """Test default success threshold value."""
        settings = Settings()
        assert settings.circuit_breaker_success_threshold == 2

    def test_default_circuit_breaker_window_size(self):
        """Test default window size value."""
        settings = Settings()
        assert settings.circuit_breaker_window_size == 10

    def test_custom_circuit_breaker_failure_threshold_from_env(self):
        """Test loading custom failure threshold from environment."""
        with patch.dict(
            "os.environ", {"CIRCUIT_BREAKER_FAILURE_THRESHOLD": "10"}, clear=False
        ):
            settings = Settings()
            assert settings.circuit_breaker_failure_threshold == 10

    def test_custom_circuit_breaker_recovery_timeout_from_env(self):
        """Test loading custom recovery timeout from environment."""
        with patch.dict(
            "os.environ", {"CIRCUIT_BREAKER_RECOVERY_TIMEOUT": "120.0"}, clear=False
        ):
            settings = Settings()
            assert settings.circuit_breaker_recovery_timeout == pytest.approx(120.0)

    def test_circuit_breaker_disabled_from_env(self):
        """Test disabling circuit breaker from environment."""
        with patch.dict(
            "os.environ", {"CIRCUIT_BREAKER_ENABLED": "false"}, clear=False
        ):
            settings = Settings()
            assert settings.circuit_breaker_enabled is False
