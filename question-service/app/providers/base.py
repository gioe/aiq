"""Base class for LLM providers."""

import asyncio
import logging
import random
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar

from ..config import settings
from ..cost_tracking import CompletionResult, TokenUsage, get_cost_tracker
from ..error_classifier import ClassifiedError, ErrorClassifier

logger = logging.getLogger(__name__)


@dataclass
class ModelCache:
    """Thread-safe cache for provider models with TTL.

    This cache stores the list of models fetched from the provider's API,
    allowing us to avoid repeated API calls while still ensuring model
    lists stay reasonably up-to-date.
    """

    models: List[str] = field(default_factory=list)
    last_fetched: float = 0.0
    ttl: int = field(default_factory=lambda: settings.provider_model_cache_ttl)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def is_valid(self) -> bool:
        """Check if the cache is still valid based on TTL.

        Returns:
            True if cache is valid, False if expired or empty
        """
        if not self.models:
            return False
        return (time.time() - self.last_fetched) < self.ttl

    def update(self, models: List[str]) -> None:
        """Update the cache with new model data.

        Args:
            models: List of model identifiers from the API
        """
        with self._lock:
            self.models = models
            self.last_fetched = time.time()

    def get_models(self) -> List[str]:
        """Get cached models.

        Returns:
            List of cached model identifiers
        """
        with self._lock:
            return list(self.models)

    def clear(self) -> None:
        """Clear the cache."""
        with self._lock:
            self.models = []
            self.last_fetched = 0.0


T = TypeVar("T")

# Minimum delay between retries to prevent tight loops
MIN_RETRY_DELAY = 0.1


class LLMProviderError(Exception):
    """Exception raised by LLM providers with classification.

    Attributes:
        classified_error: The classified error with category and severity
        original_exception: The original exception that was raised
    """

    def __init__(
        self,
        classified_error: ClassifiedError,
        original_exception: Exception,
    ):
        """Initialize LLM provider error.

        Args:
            classified_error: The classified error
            original_exception: The original exception
        """
        self.classified_error = classified_error
        self.original_exception = original_exception
        super().__init__(str(classified_error))


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_retries: int = settings.provider_max_retries,
        base_delay: float = settings.provider_retry_base_delay,
        max_delay: float = settings.provider_retry_max_delay,
        exponential_base: float = settings.provider_retry_exponential_base,
    ):
        """Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Multiplier for exponential backoff
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base


class RetryMetrics:
    """Thread-safe metrics for retry attempts."""

    def __init__(self):
        """Initialize retry metrics."""
        self._lock = threading.Lock()
        self.total_retries = 0
        self.successful_retries = 0
        self.exhausted_retries = 0
        self.retries_by_provider: Dict[str, int] = {}

    def record_retry(self, provider: str, success: bool) -> None:
        """Record a retry attempt.

        Args:
            provider: Provider name
            success: Whether the retry was successful
        """
        with self._lock:
            self.total_retries += 1
            if provider not in self.retries_by_provider:
                self.retries_by_provider[provider] = 0
            self.retries_by_provider[provider] += 1

            if success:
                self.successful_retries += 1

    def record_exhausted(self, provider: str) -> None:
        """Record when all retries were exhausted.

        Args:
            provider: Provider name
        """
        with self._lock:
            self.exhausted_retries += 1
            # Track exhausted retries by provider for consistency
            if provider not in self.retries_by_provider:
                self.retries_by_provider[provider] = 0

    def get_summary(self) -> Dict[str, Any]:
        """Get retry metrics summary.

        Returns:
            Dictionary with retry metrics
        """
        with self._lock:
            return {
                "total_retries": self.total_retries,
                "successful_retries": self.successful_retries,
                "exhausted_retries": self.exhausted_retries,
                "success_rate": (
                    self.successful_retries / self.total_retries
                    if self.total_retries > 0
                    else 0.0
                ),
                "retries_by_provider": dict(self.retries_by_provider),
            }


# Global retry metrics instance with thread-safe access
_retry_metrics: Optional[RetryMetrics] = None
_metrics_lock = threading.Lock()


def get_retry_metrics() -> RetryMetrics:
    """Get the global retry metrics instance (thread-safe).

    Returns:
        Global RetryMetrics instance
    """
    global _retry_metrics
    with _metrics_lock:
        if _retry_metrics is None:
            _retry_metrics = RetryMetrics()
        return _retry_metrics


def reset_retry_metrics() -> None:
    """Reset the global retry metrics (thread-safe)."""
    global _retry_metrics
    with _metrics_lock:
        _retry_metrics = RetryMetrics()


def calculate_backoff_delay(
    attempt: int,
    base_delay: float,
    max_delay: float,
    exponential_base: float,
) -> float:
    """Calculate delay with exponential backoff and jitter.

    Args:
        attempt: Current attempt number (0-indexed)
        base_delay: Base delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Multiplier for exponential backoff

    Returns:
        Delay in seconds with jitter applied
    """
    delay = base_delay * (exponential_base**attempt)
    delay = min(delay, max_delay)
    # Add jitter (±25%) to prevent thundering herd
    jitter = delay * 0.25 * (2 * random.random() - 1)
    # Enforce minimum delay to prevent tight retry loops
    return max(MIN_RETRY_DELAY, delay + jitter)


def with_retry(
    func: Callable[..., T],
    provider_name: str,
    config: Optional[RetryConfig] = None,
) -> T:
    """Execute a function with retry logic for transient failures.

    Args:
        func: Function to execute
        provider_name: Name of the provider for metrics
        config: Retry configuration (uses defaults if not provided)

    Returns:
        Result of the function call

    Raises:
        LLMProviderError: If all retries are exhausted or error is not retryable
    """
    if config is None:
        config = RetryConfig()

    metrics = get_retry_metrics()
    last_error: Optional[LLMProviderError] = None

    for attempt in range(config.max_retries + 1):
        try:
            result = func()
            # If this was a retry (not first attempt), record success
            if attempt > 0:
                metrics.record_retry(provider_name, success=True)
                logger.info(
                    f"Retry succeeded for {provider_name} on attempt {attempt + 1}"
                )
            return result
        except LLMProviderError as e:
            last_error = e
            classified = e.classified_error

            # If error is not retryable, raise immediately
            if not classified.is_retryable:
                logger.warning(
                    f"Non-retryable error from {provider_name}: {classified.message}"
                )
                raise

            # If we have more attempts, wait and retry
            if attempt < config.max_retries:
                delay = calculate_backoff_delay(
                    attempt,
                    config.base_delay,
                    config.max_delay,
                    config.exponential_base,
                )
                logger.warning(
                    f"Retryable error from {provider_name} "
                    f"(attempt {attempt + 1}/{config.max_retries + 1}): "
                    f"{classified.message}. Retrying in {delay:.2f}s..."
                )
                metrics.record_retry(provider_name, success=False)
                time.sleep(delay)
            else:
                # All retries exhausted
                metrics.record_exhausted(provider_name)
                logger.error(
                    f"All {config.max_retries + 1} attempts exhausted for {provider_name}: "
                    f"{classified.message}"
                )
                raise

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in retry logic")


async def with_retry_async(
    func: Callable[[], Awaitable[T]],
    provider_name: str,
    config: Optional[RetryConfig] = None,
) -> T:
    """Execute an async function with retry logic for transient failures.

    Args:
        func: Async function to execute
        provider_name: Name of the provider for metrics
        config: Retry configuration (uses defaults if not provided)

    Returns:
        Result of the function call

    Raises:
        LLMProviderError: If all retries are exhausted or error is not retryable
    """
    if config is None:
        config = RetryConfig()

    metrics = get_retry_metrics()
    last_error: Optional[LLMProviderError] = None

    for attempt in range(config.max_retries + 1):
        try:
            result = await func()
            # If this was a retry (not first attempt), record success
            if attempt > 0:
                metrics.record_retry(provider_name, success=True)
                logger.info(
                    f"Retry succeeded for {provider_name} on attempt {attempt + 1}"
                )
            return result
        except LLMProviderError as e:
            last_error = e
            classified = e.classified_error

            # If error is not retryable, raise immediately
            if not classified.is_retryable:
                logger.warning(
                    f"Non-retryable error from {provider_name}: {classified.message}"
                )
                raise

            # If we have more attempts, wait and retry
            if attempt < config.max_retries:
                delay = calculate_backoff_delay(
                    attempt,
                    config.base_delay,
                    config.max_delay,
                    config.exponential_base,
                )
                logger.warning(
                    f"Retryable error from {provider_name} "
                    f"(attempt {attempt + 1}/{config.max_retries + 1}): "
                    f"{classified.message}. Retrying in {delay:.2f}s..."
                )
                metrics.record_retry(provider_name, success=False)
                await asyncio.sleep(delay)
            else:
                # All retries exhausted
                metrics.record_exhausted(provider_name)
                logger.error(
                    f"All {config.max_retries + 1} attempts exhausted for {provider_name}: "
                    f"{classified.message}"
                )
                raise

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in retry logic")


class BaseLLMProvider(ABC):
    """Abstract base class for LLM provider integrations."""

    def __init__(self, api_key: str, model: str):
        """
        Initialize the LLM provider.

        Args:
            api_key: API key for the provider
            model: Model identifier to use
        """
        self.api_key = api_key
        self.model = model
        self._model_cache = ModelCache()

    @abstractmethod
    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a completion from the LLM.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            The generated text completion

        Raises:
            Exception: If the API call fails
        """
        pass

    @abstractmethod
    def generate_structured_completion(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a structured (JSON) completion from the LLM.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            Exception: If the API call fails or response cannot be parsed
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """
        Estimate the token count for a given text.

        Args:
            text: The text to count tokens for

        Returns:
            Estimated number of tokens

        Note:
            This is often an approximation and may vary by model.
        """
        pass

    @abstractmethod
    async def generate_completion_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a completion from the LLM asynchronously.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            The generated text completion

        Raises:
            Exception: If the API call fails
        """
        pass

    @abstractmethod
    async def generate_structured_completion_async(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a structured (JSON) completion from the LLM asynchronously.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            Exception: If the API call fails or response cannot be parsed
        """
        pass

    def generate_completion_with_usage(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate a completion and track token usage.

        This is the preferred method for generation as it tracks costs.
        Subclasses should override _generate_completion_internal to provide
        actual token usage from the API response.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResult with content and token usage
        """
        result = self._generate_completion_internal(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Record usage in global tracker if available
        if result.token_usage:
            get_cost_tracker().record_usage(result.token_usage)

        return result

    def generate_structured_completion_with_usage(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate a structured completion and track token usage.

        This is the preferred method for structured generation as it tracks costs.
        Subclasses should override _generate_structured_completion_internal to provide
        actual token usage from the API response.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResult with parsed JSON content and token usage
        """
        result = self._generate_structured_completion_internal(
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Record usage in global tracker if available
        if result.token_usage:
            get_cost_tracker().record_usage(result.token_usage)

        return result

    async def generate_completion_with_usage_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate a completion asynchronously and track token usage.

        This is the preferred async method for generation as it tracks costs.
        Subclasses should override _generate_completion_internal_async to provide
        actual token usage from the API response.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResult with content and token usage
        """
        result = await self._generate_completion_internal_async(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Record usage in global tracker if available
        if result.token_usage:
            get_cost_tracker().record_usage(result.token_usage)

        return result

    async def generate_structured_completion_with_usage_async(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate a structured completion asynchronously and track token usage.

        This is the preferred async method for structured generation as it tracks costs.
        Subclasses should override _generate_structured_completion_internal_async to provide
        actual token usage from the API response.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional provider-specific parameters

        Returns:
            CompletionResult with parsed JSON content and token usage
        """
        result = await self._generate_structured_completion_internal_async(
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Record usage in global tracker if available
        if result.token_usage:
            get_cost_tracker().record_usage(result.token_usage)

        return result

    def _generate_completion_internal(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Internal method to generate completion with token usage.

        Subclasses should override this to extract actual token usage from API responses.
        Default implementation falls back to generate_completion with estimated tokens.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model_override: Optional model override
            **kwargs: Additional parameters

        Returns:
            CompletionResult with content and token usage (may be estimated)
        """
        # Validate model on first use to provide early warning for unrecognized models
        model = model_override or self.model
        self._validate_model_once(model)

        content = self.generate_completion(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Estimate token usage if not provided by subclass
        token_usage = TokenUsage(
            input_tokens=self.count_tokens(prompt),
            output_tokens=self.count_tokens(content),
            model=model,
            provider=self.get_provider_name(),
        )

        return CompletionResult(content=content, token_usage=token_usage)

    def _generate_structured_completion_internal(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Internal method to generate structured completion with token usage.

        Subclasses should override this to extract actual token usage from API responses.
        Default implementation falls back to generate_structured_completion with estimated tokens.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model_override: Optional model override
            **kwargs: Additional parameters

        Returns:
            CompletionResult with parsed JSON content and token usage (may be estimated)
        """
        import json

        # Validate model on first use to provide early warning for unrecognized models
        model = model_override or self.model
        self._validate_model_once(model)

        content = self.generate_structured_completion(
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Estimate token usage if not provided by subclass
        # For structured completion, the prompt includes the schema
        full_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"
        token_usage = TokenUsage(
            input_tokens=self.count_tokens(full_prompt),
            output_tokens=self.count_tokens(json.dumps(content)),
            model=model,
            provider=self.get_provider_name(),
        )

        return CompletionResult(content=content, token_usage=token_usage)

    async def _generate_completion_internal_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Internal async method to generate completion with token usage.

        Subclasses should override this to extract actual token usage from API responses.
        Default implementation falls back to generate_completion_async with estimated tokens.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model_override: Optional model override
            **kwargs: Additional parameters

        Returns:
            CompletionResult with content and token usage (may be estimated)
        """
        # Validate model on first use to provide early warning for unrecognized models
        model = model_override or self.model
        self._validate_model_once(model)

        content = await self.generate_completion_async(
            prompt=prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Estimate token usage if not provided by subclass
        token_usage = TokenUsage(
            input_tokens=self.count_tokens(prompt),
            output_tokens=self.count_tokens(content),
            model=model,
            provider=self.get_provider_name(),
        )

        return CompletionResult(content=content, token_usage=token_usage)

    async def _generate_structured_completion_internal_async(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Internal async method to generate structured completion with token usage.

        Subclasses should override this to extract actual token usage from API responses.
        Default implementation falls back to generate_structured_completion_async with estimated tokens.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            model_override: Optional model override
            **kwargs: Additional parameters

        Returns:
            CompletionResult with parsed JSON content and token usage (may be estimated)
        """
        import json

        # Validate model on first use to provide early warning for unrecognized models
        model = model_override or self.model
        self._validate_model_once(model)

        content = await self.generate_structured_completion_async(
            prompt=prompt,
            response_format=response_format,
            temperature=temperature,
            max_tokens=max_tokens,
            model_override=model_override,
            **kwargs,
        )

        # Estimate token usage if not provided by subclass
        # For structured completion, the prompt includes the schema
        full_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"
        token_usage = TokenUsage(
            input_tokens=self.count_tokens(full_prompt),
            output_tokens=self.count_tokens(json.dumps(content)),
            model=model,
            provider=self.get_provider_name(),
        )

        return CompletionResult(content=content, token_usage=token_usage)

    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider name (e.g., "openai", "anthropic", "google")
        """
        return self.__class__.__name__.replace("Provider", "").lower()

    @abstractmethod
    def get_available_models(self) -> list[str]:
        """
        Get list of known models for this provider (static list).

        This returns a hardcoded list of models that are known to be available.
        For runtime validation against the actual API, use get_validated_models().

        Returns:
            List of model identifiers that are expected to be valid for API calls
        """
        pass

    def fetch_available_models(self) -> list[str]:
        """
        Fetch available models from the provider's API.

        This method queries the provider's API to get the actual list of
        currently available models. Subclasses should override this method
        to implement provider-specific API calls.

        Returns:
            List of model identifiers from the API, or empty list if not supported

        Note:
            The default implementation returns an empty list. Providers that
            support model listing should override this method.
        """
        return []

    async def fetch_available_models_async(self) -> list[str]:
        """
        Fetch available models from the provider's API asynchronously.

        This method queries the provider's API to get the actual list of
        currently available models. Subclasses should override this method
        to implement provider-specific async API calls.

        Returns:
            List of model identifiers from the API, or empty list if not supported

        Note:
            The default implementation returns an empty list. Providers that
            support model listing should override this method.
        """
        return []

    def get_validated_models(self, use_cache: bool = True) -> list[str]:
        """
        Get validated models by querying the API with caching.

        This method combines runtime API validation with the static model list:
        1. If caching is enabled and cache is valid, return cached models
        2. Otherwise, fetch models from the API
        3. If API fetch fails, fall back to the static list
        4. Logs warnings for models in static list but not in API response

        Args:
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of validated model identifiers
        """
        # If runtime validation is disabled, return static list
        if not settings.enable_runtime_model_validation:
            return self.get_available_models()

        # Check cache first if enabled
        if use_cache and self._model_cache.is_valid():
            return self._model_cache.get_models()

        try:
            api_models = self.fetch_available_models()
            if api_models:
                self._model_cache.update(api_models)

                # Log any discrepancies between static and API lists
                static_models = set(self.get_available_models())
                api_model_set = set(api_models)
                missing_from_api = static_models - api_model_set
                if missing_from_api:
                    logger.warning(
                        f"The following models from {self.get_provider_name()}'s static list "
                        f"were not found in the API response: {sorted(missing_from_api)}. "
                        f"Consider updating get_available_models()."
                    )

                return api_models
        except Exception as e:
            logger.warning(
                f"Failed to fetch models from {self.get_provider_name()} API: {e}. "
                f"Falling back to static model list."
            )

        # Fall back to static list if API fetch fails
        return self.get_available_models()

    async def get_validated_models_async(self, use_cache: bool = True) -> list[str]:
        """
        Get validated models by querying the API asynchronously with caching.

        This is the async version of get_validated_models(). It combines runtime
        API validation with the static model list:
        1. If caching is enabled and cache is valid, return cached models
        2. Otherwise, fetch models from the API asynchronously
        3. If API fetch fails, fall back to the static list
        4. Logs warnings for models in static list but not in API response

        Args:
            use_cache: Whether to use cached results (default: True)

        Returns:
            List of validated model identifiers
        """
        # If runtime validation is disabled, return static list
        if not settings.enable_runtime_model_validation:
            return self.get_available_models()

        # Check cache first if enabled
        if use_cache and self._model_cache.is_valid():
            return self._model_cache.get_models()

        try:
            api_models = await self.fetch_available_models_async()
            if api_models:
                self._model_cache.update(api_models)

                # Log any discrepancies between static and API lists
                static_models = set(self.get_available_models())
                api_model_set = set(api_models)
                missing_from_api = static_models - api_model_set
                if missing_from_api:
                    logger.warning(
                        f"The following models from {self.get_provider_name()}'s static list "
                        f"were not found in the API response: {sorted(missing_from_api)}. "
                        f"Consider updating get_available_models()."
                    )

                return api_models
        except Exception as e:
            logger.warning(
                f"Failed to fetch models from {self.get_provider_name()} API: {e}. "
                f"Falling back to static model list."
            )

        # Fall back to static list if API fetch fails
        return self.get_available_models()

    def clear_model_cache(self) -> None:
        """Clear the model cache, forcing the next validation to fetch from API."""
        self._model_cache.clear()

    def validate_model(self, model: str) -> bool:
        """
        Validate that a model identifier is recognized.

        Args:
            model: The model identifier to validate

        Returns:
            True if the model is in the available models list, False otherwise

        Note:
            Logs a warning if the model is not recognized but does not raise
            an exception, as new models may be available before the code is updated.
        """
        available = self.get_available_models()
        if model not in available:
            logger.warning(
                f"Model '{model}' is not in the known models list for {self.get_provider_name()}. "
                f"Available models: {available}. "
                f"The API call may fail or use a different model. "
                f"Consider updating the provider's get_available_models() if this is a valid model."
            )
            return False
        return True

    def _validate_model_once(self, model: str) -> None:
        """
        Validate a model on first use (subsequent calls are no-ops).

        This is called by internal methods to provide warnings for unrecognized
        models without spamming logs on every API call.

        Args:
            model: The model identifier to validate
        """
        # Lazy initialization for providers that don't call super().__init__()
        if not hasattr(self, "_validated_models"):
            object.__setattr__(self, "_validated_models", set())

        if model not in self._validated_models:
            self.validate_model(model)
            self._validated_models.add(model)

    async def cleanup(self) -> None:
        """Clean up async resources.

        Override this method in subclasses to properly close async clients
        and release resources. This should be called when the provider is
        no longer needed.
        """
        pass

    async def __aenter__(self) -> "BaseLLMProvider":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit - ensures cleanup is called."""
        await self.cleanup()

    def _handle_api_error(self, error: Exception) -> LLMProviderError:
        """Classify and wrap an API error.

        Args:
            error: The exception that was raised

        Returns:
            LLMProviderError with classified error
        """
        classified = ErrorClassifier.classify_error(
            error=error,
            provider=self.get_provider_name(),
        )
        return LLMProviderError(
            classified_error=classified,
            original_exception=error,
        )

    def _execute_with_retry(
        self,
        api_call: Callable[[], T],
        retry_config: Optional[RetryConfig] = None,
    ) -> T:
        """Execute an API call with automatic retry for transient failures.

        Args:
            api_call: Function that makes the API call
            retry_config: Optional custom retry configuration

        Returns:
            Result of the API call

        Raises:
            LLMProviderError: If all retries exhausted or error is not retryable
        """
        return with_retry(
            func=api_call,
            provider_name=self.get_provider_name(),
            config=retry_config,
        )

    async def _execute_with_retry_async(
        self,
        api_call: Callable[[], Awaitable[T]],
        retry_config: Optional[RetryConfig] = None,
    ) -> T:
        """Execute an async API call with automatic retry for transient failures.

        Args:
            api_call: Async function that makes the API call
            retry_config: Optional custom retry configuration

        Returns:
            Result of the API call

        Raises:
            LLMProviderError: If all retries exhausted or error is not retryable
        """
        return await with_retry_async(
            func=api_call,
            provider_name=self.get_provider_name(),
            config=retry_config,
        )
