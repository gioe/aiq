"""Circuit breaker pattern for LLM provider resilience.

This module implements the circuit breaker pattern to prevent cascading failures
when LLM providers are experiencing issues. When a provider fails repeatedly,
the circuit breaker "opens" to fail-fast and prevent wasting resources.

States:
    CLOSED: Normal operation, requests pass through
    OPEN: Provider is failing, requests are rejected immediately
    HALF_OPEN: Testing if provider has recovered

Transitions:
    CLOSED -> OPEN: When failure count exceeds threshold
    OPEN -> HALF_OPEN: After recovery timeout expires
    HALF_OPEN -> CLOSED: When success count threshold is met
    HALF_OPEN -> OPEN: On any failure during testing
"""

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Deque, Dict, List, Optional, TypeVar

from app.config.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    failure_threshold: int = 5
    """Number of consecutive failures before opening the circuit."""

    error_rate_threshold: float = 0.5
    """Error rate threshold (0.0-1.0) for opening circuit based on error rate."""

    recovery_timeout: float = 60.0
    """Seconds to wait before transitioning from OPEN to HALF_OPEN."""

    success_threshold: int = 2
    """Number of successful calls in HALF_OPEN state before closing circuit."""

    window_size: int = 10
    """Number of recent calls to consider for error rate calculation."""

    enabled: bool = True
    """Whether circuit breaker is enabled."""

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if self.failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if not 0.0 <= self.error_rate_threshold <= 1.0:
            raise ValueError("error_rate_threshold must be between 0.0 and 1.0")
        if self.recovery_timeout < 0:
            raise ValueError("recovery_timeout must be non-negative")
        if self.success_threshold < 1:
            raise ValueError("success_threshold must be at least 1")
        if self.window_size < 1:
            raise ValueError("window_size must be at least 1")

    @classmethod
    def from_settings(cls) -> "CircuitBreakerConfig":
        """Create config from application settings.

        Returns:
            CircuitBreakerConfig populated from settings
        """
        return cls(
            failure_threshold=getattr(settings, "circuit_breaker_failure_threshold", 5),
            error_rate_threshold=getattr(
                settings, "circuit_breaker_error_rate_threshold", 0.5
            ),
            recovery_timeout=getattr(
                settings, "circuit_breaker_recovery_timeout", 60.0
            ),
            success_threshold=getattr(settings, "circuit_breaker_success_threshold", 2),
            window_size=getattr(settings, "circuit_breaker_window_size", 10),
            enabled=getattr(settings, "circuit_breaker_enabled", True),
        )


MAX_STATE_CHANGES_HISTORY = 50


@dataclass
class CircuitBreakerStats:
    """Statistics for a circuit breaker instance."""

    provider_name: str
    state: CircuitState = CircuitState.CLOSED
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    state_changes: Deque[Dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=MAX_STATE_CHANGES_HISTORY)
    )
    last_failure_time: Optional[float] = None
    last_state_change_time: Optional[float] = None
    recent_calls: List[bool] = field(default_factory=list)

    def record_call(self, success: bool, window_size: int) -> None:
        """Record a call result.

        Args:
            success: Whether the call succeeded
            window_size: Maximum size of sliding window
        """
        self.total_calls += 1
        self.recent_calls.append(success)

        if len(self.recent_calls) > window_size:
            self.recent_calls.pop(0)

        if success:
            self.total_successes += 1
            self.consecutive_successes += 1
            self.consecutive_failures = 0
        else:
            self.total_failures += 1
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            self.last_failure_time = time.time()

    def get_error_rate(self) -> float:
        """Calculate error rate from recent calls.

        Returns:
            Error rate between 0.0 and 1.0
        """
        if not self.recent_calls:
            return 0.0
        failures = sum(1 for call in self.recent_calls if not call)
        return failures / len(self.recent_calls)

    def record_state_change(
        self, from_state: CircuitState, to_state: CircuitState, reason: str
    ) -> None:
        """Record a state transition.

        Args:
            from_state: Previous state
            to_state: New state
            reason: Reason for the transition
        """
        self.state = to_state
        self.last_state_change_time = time.time()
        self.state_changes.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_state": from_state.value,
                "to_state": to_state.value,
                "reason": reason,
                "consecutive_failures": self.consecutive_failures,
                "error_rate": self.get_error_rate(),
            }
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary.

        Returns:
            Dictionary representation of stats
        """
        return {
            "provider_name": self.provider_name,
            "state": self.state.value,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "error_rate": self.get_error_rate(),
            "state_changes_count": len(self.state_changes),
            "recent_state_changes": list(self.state_changes)[-5:],
        }


class CircuitBreakerOpen(Exception):
    """Exception raised when circuit breaker is open."""

    def __init__(self, provider_name: str, time_until_retry: float):
        """Initialize circuit breaker open exception.

        Args:
            provider_name: Name of the provider
            time_until_retry: Seconds until retry is allowed
        """
        self.provider_name = provider_name
        self.time_until_retry = time_until_retry
        super().__init__(
            f"Circuit breaker is OPEN for provider '{provider_name}'. "
            f"Retry in {time_until_retry:.1f}s"
        )


class CircuitBreaker:
    """Circuit breaker for a single provider.

    Monitors call failures and opens the circuit when failures exceed
    thresholds, preventing further calls until recovery.

    Thread-safe implementation using locks.
    """

    def __init__(
        self, provider_name: str, config: Optional[CircuitBreakerConfig] = None
    ):
        """Initialize circuit breaker.

        Args:
            provider_name: Name of the provider this circuit breaker protects
            config: Circuit breaker configuration (uses defaults if not provided)
        """
        self.provider_name = provider_name
        self.config = config or CircuitBreakerConfig.from_settings()
        self._lock = threading.RLock()
        self._stats = CircuitBreakerStats(provider_name=provider_name)

        logger.debug(
            f"CircuitBreaker initialized for {provider_name} "
            f"(threshold={self.config.failure_threshold}, "
            f"recovery={self.config.recovery_timeout}s)"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit state.

        Returns:
            Current circuit state
        """
        with self._lock:
            return self._stats.state

    @property
    def is_available(self) -> bool:
        """Check if the circuit allows calls.

        Returns:
            True if calls are allowed
        """
        if not self.config.enabled:
            return True

        with self._lock:
            self._check_state_transition()
            return self._stats.state != CircuitState.OPEN

    def _check_state_transition(self) -> None:
        """Check and perform state transitions based on current conditions.

        Must be called while holding the lock.

        Only OPEN state requires a timed transition check. CLOSED and HALF_OPEN
        states transition based on call outcomes recorded in record_success/record_failure.
        """
        if self._stats.state != CircuitState.OPEN:
            return

        if self._stats.last_failure_time is not None:
            elapsed = time.time() - self._stats.last_failure_time
            if elapsed >= self.config.recovery_timeout:
                self._transition_to(
                    CircuitState.HALF_OPEN,
                    f"Recovery timeout ({self.config.recovery_timeout}s) elapsed",
                )

    def _transition_to(self, new_state: CircuitState, reason: str) -> None:
        """Transition to a new state.

        Must be called while holding the lock.

        Args:
            new_state: Target state
            reason: Reason for transition
        """
        old_state = self._stats.state
        if old_state != new_state:
            logger.info(
                f"Circuit breaker [{self.provider_name}]: "
                f"{old_state.value} -> {new_state.value} ({reason})"
            )
            self._stats.record_state_change(old_state, new_state, reason)

            if new_state == CircuitState.HALF_OPEN:
                self._stats.consecutive_successes = 0
            elif new_state == CircuitState.CLOSED:
                self._stats.consecutive_failures = 0
                self._stats.recent_calls.clear()

    def _should_open_circuit(self) -> bool:
        """Check if circuit should open based on failure metrics.

        Must be called while holding the lock.

        Returns:
            True if circuit should open
        """
        if self._stats.consecutive_failures >= self.config.failure_threshold:
            return True

        if len(self._stats.recent_calls) >= self.config.window_size:
            error_rate = self._stats.get_error_rate()
            if error_rate >= self.config.error_rate_threshold:
                return True

        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if not self.config.enabled:
            return

        with self._lock:
            self._stats.record_call(success=True, window_size=self.config.window_size)

            if self._stats.state == CircuitState.HALF_OPEN:
                if self._stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(
                        CircuitState.CLOSED,
                        f"Success threshold ({self.config.success_threshold}) met in HALF_OPEN",
                    )

    def record_failure(self) -> None:
        """Record a failed call."""
        if not self.config.enabled:
            return

        with self._lock:
            self._stats.record_call(success=False, window_size=self.config.window_size)

            if self._stats.state == CircuitState.CLOSED:
                if self._should_open_circuit():
                    self._transition_to(
                        CircuitState.OPEN,
                        f"Failure threshold exceeded "
                        f"(consecutive={self._stats.consecutive_failures}, "
                        f"error_rate={self._stats.get_error_rate():.2%})",
                    )
            elif self._stats.state == CircuitState.HALF_OPEN:
                self._transition_to(
                    CircuitState.OPEN, "Failure during HALF_OPEN testing"
                )

    def execute(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute a function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the function

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: If the function raises an exception
        """
        if not self.config.enabled:
            return func(*args, **kwargs)

        with self._lock:
            self._check_state_transition()

            if self._stats.state == CircuitState.OPEN:
                time_until_retry = 0.0
                if self._stats.last_failure_time is not None:
                    elapsed = time.time() - self._stats.last_failure_time
                    time_until_retry = max(0, self.config.recovery_timeout - elapsed)
                raise CircuitBreakerOpen(self.provider_name, time_until_retry)

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    async def execute_async(
        self, func: Callable[..., Any], *args: Any, **kwargs: Any
    ) -> Any:
        """Execute an async function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            Result of the async function

        Raises:
            CircuitBreakerOpen: If circuit is open
            Exception: If the function raises an exception
        """
        if not self.config.enabled:
            return await func(*args, **kwargs)

        with self._lock:
            self._check_state_transition()

            if self._stats.state == CircuitState.OPEN:
                time_until_retry = 0.0
                if self._stats.last_failure_time is not None:
                    elapsed = time.time() - self._stats.last_failure_time
                    time_until_retry = max(0, self.config.recovery_timeout - elapsed)
                raise CircuitBreakerOpen(self.provider_name, time_until_retry)

        try:
            result = await func(*args, **kwargs)
            self.record_success()
            return result
        except Exception:
            self.record_failure()
            raise

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics.

        Returns:
            Dictionary with circuit breaker stats
        """
        with self._lock:
            return self._stats.to_dict()

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        with self._lock:
            old_state = self._stats.state
            self._stats = CircuitBreakerStats(provider_name=self.provider_name)
            logger.info(
                f"Circuit breaker [{self.provider_name}] reset from {old_state.value}"
            )


class CircuitBreakerRegistry:
    """Registry for managing circuit breakers across providers.

    Thread-safe singleton that provides centralized access to circuit breakers.
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """Initialize the registry.

        Args:
            config: Default configuration for new circuit breakers
        """
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self._config = config or CircuitBreakerConfig.from_settings()

    def get_or_create(self, provider_name: str) -> CircuitBreaker:
        """Get or create a circuit breaker for a provider.

        Args:
            provider_name: Name of the provider

        Returns:
            CircuitBreaker for the provider
        """
        with self._lock:
            if provider_name not in self._breakers:
                self._breakers[provider_name] = CircuitBreaker(
                    provider_name=provider_name,
                    config=self._config,
                )
            return self._breakers[provider_name]

    def get(self, provider_name: str) -> Optional[CircuitBreaker]:
        """Get a circuit breaker if it exists.

        Args:
            provider_name: Name of the provider

        Returns:
            CircuitBreaker if exists, None otherwise
        """
        with self._lock:
            return self._breakers.get(provider_name)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all circuit breakers.

        Returns:
            Dictionary mapping provider names to their stats
        """
        with self._lock:
            return {name: cb.get_stats() for name, cb in self._breakers.items()}

    def get_available_providers(self) -> List[str]:
        """Get list of providers with available (non-open) circuits.

        Returns:
            List of provider names that are available
        """
        with self._lock:
            return [name for name, cb in self._breakers.items() if cb.is_available]

    def get_unavailable_providers(self) -> List[str]:
        """Get list of providers with open circuits.

        Returns:
            List of provider names that are unavailable
        """
        with self._lock:
            return [name for name, cb in self._breakers.items() if not cb.is_available]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()
            logger.info("All circuit breakers reset")

    def reset(self, provider_name: str) -> bool:
        """Reset a specific circuit breaker.

        Args:
            provider_name: Name of the provider

        Returns:
            True if reset was performed, False if provider not found
        """
        with self._lock:
            if provider_name in self._breakers:
                self._breakers[provider_name].reset()
                return True
            return False


_registry: Optional[CircuitBreakerRegistry] = None
_registry_lock = threading.Lock()


def get_circuit_breaker_registry() -> CircuitBreakerRegistry:
    """Get the global circuit breaker registry.

    Returns:
        Global CircuitBreakerRegistry instance
    """
    global _registry
    with _registry_lock:
        if _registry is None:
            _registry = CircuitBreakerRegistry()
        return _registry


def reset_circuit_breaker_registry() -> None:
    """Reset the global circuit breaker registry."""
    global _registry
    with _registry_lock:
        if _registry is not None:
            _registry.reset_all()
        _registry = None
