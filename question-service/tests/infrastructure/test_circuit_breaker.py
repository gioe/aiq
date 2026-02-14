"""Tests for circuit breaker pattern implementation."""

import threading
import time
from unittest.mock import MagicMock

import pytest

from app.infrastructure.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpen,
    CircuitBreakerRegistry,
    CircuitBreakerStats,
    CircuitState,
    get_circuit_breaker_registry,
    reset_circuit_breaker_registry,
)


class TestCircuitBreakerConfig:
    """Tests for CircuitBreakerConfig class."""

    def test_default_values(self):
        """Test that config uses reasonable defaults."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.error_rate_threshold == pytest.approx(0.5)
        assert config.recovery_timeout == pytest.approx(60.0)
        assert config.success_threshold == 2
        assert config.window_size == 10
        assert config.enabled is True

    def test_custom_values(self):
        """Test that config accepts custom values."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            error_rate_threshold=0.3,
            recovery_timeout=30.0,
            success_threshold=1,
            window_size=5,
            enabled=False,
        )
        assert config.failure_threshold == 3
        assert config.error_rate_threshold == pytest.approx(0.3)
        assert config.recovery_timeout == pytest.approx(30.0)
        assert config.success_threshold == 1
        assert config.window_size == 5
        assert config.enabled is False

    def test_invalid_failure_threshold(self):
        """Test that failure_threshold must be at least 1."""
        with pytest.raises(ValueError, match="failure_threshold must be at least 1"):
            CircuitBreakerConfig(failure_threshold=0)

    def test_invalid_error_rate_threshold_low(self):
        """Test that error_rate_threshold must be >= 0."""
        with pytest.raises(ValueError, match="error_rate_threshold must be between"):
            CircuitBreakerConfig(error_rate_threshold=-0.1)

    def test_invalid_error_rate_threshold_high(self):
        """Test that error_rate_threshold must be <= 1.0."""
        with pytest.raises(ValueError, match="error_rate_threshold must be between"):
            CircuitBreakerConfig(error_rate_threshold=1.1)

    def test_invalid_recovery_timeout(self):
        """Test that recovery_timeout must be non-negative."""
        with pytest.raises(ValueError, match="recovery_timeout must be non-negative"):
            CircuitBreakerConfig(recovery_timeout=-1.0)

    def test_invalid_success_threshold(self):
        """Test that success_threshold must be at least 1."""
        with pytest.raises(ValueError, match="success_threshold must be at least 1"):
            CircuitBreakerConfig(success_threshold=0)

    def test_invalid_window_size(self):
        """Test that window_size must be at least 1."""
        with pytest.raises(ValueError, match="window_size must be at least 1"):
            CircuitBreakerConfig(window_size=0)

    def test_boundary_error_rate_threshold_zero(self):
        """Test that error_rate_threshold can be 0.0."""
        config = CircuitBreakerConfig(error_rate_threshold=0.0)
        assert config.error_rate_threshold == pytest.approx(0.0)

    def test_boundary_error_rate_threshold_one(self):
        """Test that error_rate_threshold can be 1.0."""
        config = CircuitBreakerConfig(error_rate_threshold=1.0)
        assert config.error_rate_threshold == pytest.approx(1.0)

    def test_from_settings(self):
        """Test that config can be created from settings."""
        config = CircuitBreakerConfig.from_settings()
        # Should use settings values (defaults if not configured)
        assert isinstance(config.failure_threshold, int)
        assert isinstance(config.recovery_timeout, float)
        assert isinstance(config.enabled, bool)


class TestCircuitBreakerStats:
    """Tests for CircuitBreakerStats class."""

    @pytest.fixture
    def stats(self):
        """Create fresh stats for each test."""
        return CircuitBreakerStats(provider_name="test_provider")

    def test_initialization(self, stats):
        """Test that stats initializes correctly."""
        assert stats.provider_name == "test_provider"
        assert stats.state == CircuitState.CLOSED
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 0
        assert stats.total_calls == 0
        assert stats.total_failures == 0
        assert stats.total_successes == 0
        assert stats.recent_calls == []

    def test_record_success(self, stats):
        """Test recording a successful call."""
        stats.record_call(success=True, window_size=10)

        assert stats.total_calls == 1
        assert stats.total_successes == 1
        assert stats.consecutive_successes == 1
        assert stats.consecutive_failures == 0
        assert stats.recent_calls == [True]

    def test_record_failure(self, stats):
        """Test recording a failed call."""
        stats.record_call(success=False, window_size=10)

        assert stats.total_calls == 1
        assert stats.total_failures == 1
        assert stats.consecutive_failures == 1
        assert stats.consecutive_successes == 0
        assert stats.recent_calls == [False]
        assert stats.last_failure_time is not None

    def test_consecutive_failures_reset_on_success(self, stats):
        """Test that consecutive failures reset on success."""
        stats.record_call(success=False, window_size=10)
        stats.record_call(success=False, window_size=10)
        assert stats.consecutive_failures == 2

        stats.record_call(success=True, window_size=10)
        assert stats.consecutive_failures == 0
        assert stats.consecutive_successes == 1

    def test_consecutive_successes_reset_on_failure(self, stats):
        """Test that consecutive successes reset on failure."""
        stats.record_call(success=True, window_size=10)
        stats.record_call(success=True, window_size=10)
        assert stats.consecutive_successes == 2

        stats.record_call(success=False, window_size=10)
        assert stats.consecutive_successes == 0
        assert stats.consecutive_failures == 1

    def test_sliding_window(self, stats):
        """Test that recent calls window is maintained."""
        window_size = 5
        for i in range(10):
            stats.record_call(success=i % 2 == 0, window_size=window_size)

        assert len(stats.recent_calls) == window_size

    def test_error_rate_calculation(self, stats):
        """Test error rate calculation."""
        # 3 failures, 2 successes = 60% error rate
        stats.record_call(success=False, window_size=10)
        stats.record_call(success=True, window_size=10)
        stats.record_call(success=False, window_size=10)
        stats.record_call(success=True, window_size=10)
        stats.record_call(success=False, window_size=10)

        assert stats.get_error_rate() == pytest.approx(0.6)

    def test_error_rate_empty(self, stats):
        """Test error rate with no calls."""
        assert stats.get_error_rate() == pytest.approx(0.0)

    def test_record_state_change(self, stats):
        """Test recording state transitions."""
        stats.record_state_change(CircuitState.CLOSED, CircuitState.OPEN, "Test reason")

        assert stats.state == CircuitState.OPEN
        assert len(stats.state_changes) == 1
        assert stats.state_changes[0]["from_state"] == "closed"
        assert stats.state_changes[0]["to_state"] == "open"
        assert stats.state_changes[0]["reason"] == "Test reason"
        assert stats.last_state_change_time is not None

    def test_to_dict(self, stats):
        """Test converting stats to dictionary."""
        stats.record_call(success=True, window_size=10)
        stats.record_call(success=False, window_size=10)

        result = stats.to_dict()

        assert result["provider_name"] == "test_provider"
        assert result["state"] == "closed"
        assert result["total_calls"] == 2
        assert result["total_failures"] == 1
        assert result["total_successes"] == 1
        assert result["error_rate"] == pytest.approx(0.5)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def config(self):
        """Create test config with fast timeouts."""
        return CircuitBreakerConfig(
            failure_threshold=3,
            error_rate_threshold=0.5,
            recovery_timeout=0.1,  # Fast for testing
            success_threshold=2,
            window_size=5,
            enabled=True,
        )

    @pytest.fixture
    def breaker(self, config):
        """Create circuit breaker for testing."""
        return CircuitBreaker("test_provider", config)

    def test_initial_state_is_closed(self, breaker):
        """Test that breaker starts in CLOSED state."""
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_available is True

    def test_records_success(self, breaker):
        """Test that success is recorded correctly."""
        breaker.record_success()
        stats = breaker.get_stats()

        assert stats["total_calls"] == 1
        assert stats["total_successes"] == 1
        assert stats["consecutive_successes"] == 1

    def test_records_failure(self, breaker):
        """Test that failure is recorded correctly."""
        breaker.record_failure()
        stats = breaker.get_stats()

        assert stats["total_calls"] == 1
        assert stats["total_failures"] == 1
        assert stats["consecutive_failures"] == 1

    def test_opens_on_failure_threshold(self, breaker, config):
        """Test that circuit opens after failure threshold is reached."""
        for _ in range(config.failure_threshold):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN
        assert breaker.is_available is False

    def test_opens_on_error_rate_threshold(self, breaker, config):
        """Test that circuit opens when error rate exceeds threshold."""
        # Fill window with failures to exceed error rate threshold
        for _ in range(config.window_size):
            breaker.record_failure()

        assert breaker.state == CircuitState.OPEN

    def test_transitions_to_half_open_after_timeout(self, breaker, config):
        """Test transition from OPEN to HALF_OPEN after recovery timeout."""
        # Open the circuit
        for _ in range(config.failure_threshold):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(config.recovery_timeout + 0.1)

        # Check availability triggers transition
        assert breaker.is_available is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_closes_after_success_threshold_in_half_open(self, breaker, config):
        """Test transition from HALF_OPEN to CLOSED after success threshold."""
        # Open the circuit
        for _ in range(config.failure_threshold):
            breaker.record_failure()

        # Wait for recovery timeout
        time.sleep(config.recovery_timeout + 0.1)
        _ = breaker.is_available  # Trigger transition to HALF_OPEN

        # Record successes to close circuit
        for _ in range(config.success_threshold):
            breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    def test_reopens_on_failure_in_half_open(self, breaker, config):
        """Test transition from HALF_OPEN to OPEN on failure."""
        # Open the circuit
        for _ in range(config.failure_threshold):
            breaker.record_failure()

        # Wait for recovery timeout
        time.sleep(config.recovery_timeout + 0.1)
        _ = breaker.is_available  # Trigger transition to HALF_OPEN
        assert breaker.state == CircuitState.HALF_OPEN

        # Any failure in HALF_OPEN should reopen
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_execute_success(self, breaker):
        """Test successful execution through circuit breaker."""
        func = MagicMock(return_value="result")

        result = breaker.execute(func)

        assert result == "result"
        func.assert_called_once()
        assert breaker.get_stats()["total_successes"] == 1

    def test_execute_failure(self, breaker):
        """Test failed execution records failure."""
        func = MagicMock(side_effect=Exception("Error"))

        with pytest.raises(Exception, match="Error"):
            breaker.execute(func)

        func.assert_called_once()
        assert breaker.get_stats()["total_failures"] == 1

    def test_execute_raises_when_open(self, breaker, config):
        """Test that execute raises CircuitBreakerOpen when circuit is open."""
        # Open the circuit
        for _ in range(config.failure_threshold):
            breaker.record_failure()

        func = MagicMock()

        with pytest.raises(CircuitBreakerOpen) as exc_info:
            breaker.execute(func)

        func.assert_not_called()
        assert exc_info.value.provider_name == "test_provider"
        assert exc_info.value.time_until_retry >= 0

    def test_disabled_breaker_always_available(self):
        """Test that disabled breaker is always available."""
        config = CircuitBreakerConfig(enabled=False)
        breaker = CircuitBreaker("test", config)

        # Record many failures
        for _ in range(10):
            breaker.record_failure()

        # Should still be available when disabled
        assert breaker.is_available is True

    def test_disabled_breaker_executes_directly(self):
        """Test that disabled breaker executes functions directly."""
        config = CircuitBreakerConfig(enabled=False)
        breaker = CircuitBreaker("test", config)

        func = MagicMock(return_value="result")
        result = breaker.execute(func)

        assert result == "result"

    def test_reset(self, breaker, config):
        """Test that reset returns to initial state."""
        # Open the circuit
        for _ in range(config.failure_threshold):
            breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.get_stats()["total_calls"] == 0

    def test_get_stats(self, breaker):
        """Test that get_stats returns correct information."""
        breaker.record_success()
        breaker.record_failure()

        stats = breaker.get_stats()

        assert stats["provider_name"] == "test_provider"
        assert stats["state"] == "closed"
        assert stats["total_calls"] == 2
        assert stats["total_failures"] == 1
        assert stats["total_successes"] == 1


class TestCircuitBreakerThreadSafety:
    """Tests for thread safety of circuit breaker."""

    def test_concurrent_record_success(self):
        """Test concurrent success recording is thread-safe."""
        config = CircuitBreakerConfig(failure_threshold=1000)
        breaker = CircuitBreaker("test", config)
        num_threads = 10
        calls_per_thread = 100

        def record_successes():
            for _ in range(calls_per_thread):
                breaker.record_success()

        threads = [
            threading.Thread(target=record_successes) for _ in range(num_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = breaker.get_stats()
        assert stats["total_successes"] == num_threads * calls_per_thread

    def test_concurrent_record_failure(self):
        """Test concurrent failure recording is thread-safe."""
        config = CircuitBreakerConfig(failure_threshold=1000)
        breaker = CircuitBreaker("test", config)
        num_threads = 10
        calls_per_thread = 100

        def record_failures():
            for _ in range(calls_per_thread):
                breaker.record_failure()

        threads = [threading.Thread(target=record_failures) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        stats = breaker.get_stats()
        assert stats["total_failures"] == num_threads * calls_per_thread


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry class."""

    @pytest.fixture
    def registry(self):
        """Create fresh registry for each test."""
        return CircuitBreakerRegistry()

    def test_get_or_create_new(self, registry):
        """Test creating new circuit breaker."""
        breaker = registry.get_or_create("openai")

        assert breaker is not None
        assert breaker.provider_name == "openai"

    def test_get_or_create_existing(self, registry):
        """Test getting existing circuit breaker."""
        breaker1 = registry.get_or_create("openai")
        breaker2 = registry.get_or_create("openai")

        assert breaker1 is breaker2

    def test_get_nonexistent(self, registry):
        """Test getting non-existent circuit breaker returns None."""
        result = registry.get("nonexistent")
        assert result is None

    def test_get_existing(self, registry):
        """Test getting existing circuit breaker."""
        registry.get_or_create("anthropic")
        result = registry.get("anthropic")

        assert result is not None
        assert result.provider_name == "anthropic"

    def test_get_all_stats(self, registry):
        """Test getting stats for all circuit breakers."""
        registry.get_or_create("openai")
        registry.get_or_create("anthropic")

        stats = registry.get_all_stats()

        assert "openai" in stats
        assert "anthropic" in stats
        assert stats["openai"]["provider_name"] == "openai"

    def test_get_available_providers(self, registry):
        """Test getting available providers."""
        config = CircuitBreakerConfig(failure_threshold=2)
        registry = CircuitBreakerRegistry(config)

        registry.get_or_create("openai")
        registry.get_or_create("anthropic")

        # Open openai circuit
        openai = registry.get("openai")
        openai.record_failure()
        openai.record_failure()

        available = registry.get_available_providers()
        assert "anthropic" in available
        assert "openai" not in available

    def test_get_unavailable_providers(self, registry):
        """Test getting unavailable providers."""
        config = CircuitBreakerConfig(failure_threshold=2)
        registry = CircuitBreakerRegistry(config)

        registry.get_or_create("openai")
        registry.get_or_create("anthropic")

        # Open openai circuit
        openai = registry.get("openai")
        openai.record_failure()
        openai.record_failure()

        unavailable = registry.get_unavailable_providers()
        assert "openai" in unavailable
        assert "anthropic" not in unavailable

    def test_reset_all(self, registry):
        """Test resetting all circuit breakers."""
        config = CircuitBreakerConfig(failure_threshold=2)
        registry = CircuitBreakerRegistry(config)

        openai = registry.get_or_create("openai")
        openai.record_failure()
        openai.record_failure()
        assert openai.state == CircuitState.OPEN

        registry.reset_all()

        assert openai.state == CircuitState.CLOSED

    def test_reset_specific(self, registry):
        """Test resetting specific circuit breaker."""
        config = CircuitBreakerConfig(failure_threshold=2)
        registry = CircuitBreakerRegistry(config)

        openai = registry.get_or_create("openai")
        anthropic = registry.get_or_create("anthropic")
        openai.record_failure()
        openai.record_failure()
        anthropic.record_failure()
        anthropic.record_failure()

        result = registry.reset("openai")

        assert result is True
        assert openai.state == CircuitState.CLOSED
        assert anthropic.state == CircuitState.OPEN

    def test_reset_nonexistent(self, registry):
        """Test resetting non-existent circuit breaker."""
        result = registry.reset("nonexistent")
        assert result is False


class TestGlobalRegistry:
    """Tests for global registry functions."""

    @pytest.fixture(autouse=True)
    def reset_global_registry(self):
        """Reset global registry before and after each test."""
        reset_circuit_breaker_registry()
        yield
        reset_circuit_breaker_registry()

    def test_get_circuit_breaker_registry_creates_instance(self):
        """Test that get_circuit_breaker_registry creates instance."""
        registry = get_circuit_breaker_registry()
        assert isinstance(registry, CircuitBreakerRegistry)

    def test_get_circuit_breaker_registry_returns_same_instance(self):
        """Test that get_circuit_breaker_registry returns same instance."""
        registry1 = get_circuit_breaker_registry()
        registry2 = get_circuit_breaker_registry()
        assert registry1 is registry2

    def test_reset_circuit_breaker_registry(self):
        """Test that reset_circuit_breaker_registry resets all breakers."""
        registry = get_circuit_breaker_registry()
        breaker = registry.get_or_create("openai")
        breaker.record_failure()

        reset_circuit_breaker_registry()

        # New registry should be created
        new_registry = get_circuit_breaker_registry()
        new_breaker = new_registry.get("openai")
        assert new_breaker is None  # Should not exist in new registry


class TestCircuitBreakerOpen:
    """Tests for CircuitBreakerOpen exception."""

    def test_exception_message(self):
        """Test exception message format."""
        exc = CircuitBreakerOpen("openai", 30.5)

        assert "openai" in str(exc)
        assert "30.5" in str(exc)
        assert exc.provider_name == "openai"
        assert exc.time_until_retry == pytest.approx(30.5)

    def test_exception_is_catchable(self):
        """Test that exception can be caught."""
        try:
            raise CircuitBreakerOpen("anthropic", 10.0)
        except CircuitBreakerOpen as e:
            assert e.provider_name == "anthropic"


class TestCircuitBreakerIntegration:
    """Integration tests for circuit breaker with generator."""

    @pytest.fixture(autouse=True)
    def reset_registry(self):
        """Reset registry before each test."""
        reset_circuit_breaker_registry()
        yield
        reset_circuit_breaker_registry()

    def test_circuit_breaker_fail_fast(self):
        """Test that circuit breaker prevents calls when open."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=60.0,  # Long timeout
        )
        registry = CircuitBreakerRegistry(config)
        breaker = registry.get_or_create("test_provider")

        call_count = 0

        def failing_function():
            nonlocal call_count
            call_count += 1
            raise Exception("Always fails")

        # First two calls should go through and fail
        for _ in range(2):
            try:
                breaker.execute(failing_function)
            except Exception:
                pass

        assert call_count == 2
        assert breaker.state == CircuitState.OPEN

        # Third call should be rejected without calling function
        with pytest.raises(CircuitBreakerOpen):
            breaker.execute(failing_function)

        assert call_count == 2  # Function not called

    def test_circuit_breaker_recovery(self):
        """Test that circuit breaker allows recovery."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,  # Fast recovery for testing
            success_threshold=1,
        )
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        breaker.record_failure()
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        # Wait for recovery
        time.sleep(0.15)

        # Circuit should transition to HALF_OPEN on next availability check
        assert breaker.is_available is True
        assert breaker.state == CircuitState.HALF_OPEN

        # One success should close it
        breaker.record_success()
        assert breaker.state == CircuitState.CLOSED
