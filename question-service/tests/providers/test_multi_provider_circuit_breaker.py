"""Integration tests for multi-provider circuit breaker scenarios.

Tests circuit breaker behavior when multiple providers are registered,
including failover tracking and provider availability queries.
"""

import pytest

from app.infrastructure.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitState,
)


@pytest.fixture
def config():
    """Circuit breaker config with low thresholds for fast testing."""
    return CircuitBreakerConfig(
        failure_threshold=2,
        error_rate_threshold=0.5,
        recovery_timeout=0.1,
        success_threshold=1,
        window_size=5,
        enabled=True,
    )


@pytest.fixture
def registry(config):
    """Fresh registry with test config."""
    return CircuitBreakerRegistry(config=config)


class TestMultiProviderCircuitBreaker:
    """Tests for circuit breaker behavior across multiple providers."""

    def test_independent_provider_states(self, registry):
        """Each provider's circuit breaker operates independently."""
        cb_openai = registry.get_or_create("openai")
        cb_google = registry.get_or_create("google")

        # Fail openai past threshold
        cb_openai.record_failure()
        cb_openai.record_failure()

        assert cb_openai.state == CircuitState.OPEN
        assert cb_google.state == CircuitState.CLOSED

    def test_available_providers_filters_open_circuits(self, registry):
        """get_available_providers excludes providers with open circuits."""
        registry.get_or_create("openai")
        registry.get_or_create("google")
        registry.get_or_create("anthropic")

        # Open the openai circuit
        cb_openai = registry.get_or_create("openai")
        cb_openai.record_failure()
        cb_openai.record_failure()

        available = registry.get_available_providers()
        assert "openai" not in available
        assert "google" in available
        assert "anthropic" in available

    def test_unavailable_providers_lists_open_circuits(self, registry):
        """get_unavailable_providers returns only providers with open circuits."""
        registry.get_or_create("openai")
        registry.get_or_create("google")

        cb_openai = registry.get_or_create("openai")
        cb_openai.record_failure()
        cb_openai.record_failure()

        unavailable = registry.get_unavailable_providers()
        assert "openai" in unavailable
        assert "google" not in unavailable

    def test_all_providers_fail_then_recover(self, registry, config):
        """All providers can fail and recover independently."""
        providers = ["openai", "google", "anthropic", "xai"]
        for name in providers:
            cb = registry.get_or_create(name)
            cb.record_failure()
            cb.record_failure()

        # All should be open
        assert registry.get_available_providers() == []
        assert set(registry.get_unavailable_providers()) == set(providers)

        # Wait for recovery timeout
        import time

        time.sleep(0.15)

        # All should be half-open (available for testing)
        available = registry.get_available_providers()
        assert set(available) == set(providers)

    def test_execute_through_circuit_breaker(self, registry):
        """Functions execute normally when circuit is closed."""
        cb = registry.get_or_create("openai")

        result = cb.execute(lambda: "success")
        assert result == "success"
        assert cb.state == CircuitState.CLOSED

    def test_execute_raises_when_open(self, registry):
        """Raise CircuitBreakerOpen when circuit is open."""
        cb = registry.get_or_create("openai")
        cb.record_failure()
        cb.record_failure()

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            cb.execute(lambda: "should not run")

        assert exc_info.value.provider_name == "openai"

    def test_half_open_recovery_to_closed(self, registry, config):
        """Circuit transitions HALF_OPEN -> CLOSED after success threshold."""
        cb = registry.get_or_create("openai")

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        import time

        time.sleep(0.15)

        # First success in half-open (success_threshold=1)
        cb.execute(lambda: "ok")
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self, registry, config):
        """Circuit transitions HALF_OPEN -> OPEN on failure."""
        cb = registry.get_or_create("openai")

        # Open the circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery
        import time

        time.sleep(0.15)

        # Fail during half-open
        with pytest.raises(RuntimeError):
            cb.execute(lambda: (_ for _ in ()).throw(RuntimeError("still broken")))

        assert cb.state == CircuitState.OPEN

    def test_reset_specific_provider(self, registry):
        """Resetting one provider doesn't affect others."""
        cb_openai = registry.get_or_create("openai")
        cb_google = registry.get_or_create("google")

        cb_openai.record_failure()
        cb_openai.record_failure()
        cb_google.record_failure()
        cb_google.record_failure()

        registry.reset("openai")

        assert cb_openai.state == CircuitState.CLOSED
        assert cb_google.state == CircuitState.OPEN

    def test_reset_all_providers(self, registry):
        """reset_all resets all provider circuit breakers."""
        for name in ["openai", "google", "anthropic"]:
            cb = registry.get_or_create(name)
            cb.record_failure()
            cb.record_failure()

        registry.reset_all()

        for name in ["openai", "google", "anthropic"]:
            cb = registry.get(name)
            assert cb.state == CircuitState.CLOSED

    def test_get_all_stats(self, registry):
        """get_all_stats returns stats for all registered providers."""
        registry.get_or_create("openai")
        registry.get_or_create("google")

        stats = registry.get_all_stats()
        assert "openai" in stats
        assert "google" in stats
        assert stats["openai"]["state"] == "closed"
