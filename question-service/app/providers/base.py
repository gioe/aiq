"""Base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from ..error_classifier import ClassifiedError, ErrorClassifier


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

    @abstractmethod
    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        Generate a completion from the LLM.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
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
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a structured (JSON) completion from the LLM.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum number of tokens to generate
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

    def get_provider_name(self) -> str:
        """
        Get the name of this provider.

        Returns:
            Provider name (e.g., "openai", "anthropic", "google")
        """
        return self.__class__.__name__.replace("Provider", "").lower()

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
