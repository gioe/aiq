"""Anthropic LLM provider integration."""

import json
import logging
from typing import Any, Dict, Optional

import anthropic
from anthropic import Anthropic, AsyncAnthropic

from ..cost_tracking import CompletionResult, TokenUsage
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)

# Known Anthropic models ordered from newest to oldest.
# This constant is the single source of truth for model availability.
# Update this list when new Claude models are released.
# See: https://docs.anthropic.com/en/docs/about-claude/models
ANTHROPIC_MODELS: list[str] = [
    # Claude 4.5 models (latest)
    "claude-opus-4-5-20251101",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    # Claude 4.x models
    "claude-opus-4-1-20250805",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    # Claude 3.x models (legacy)
    "claude-3-7-sonnet-20250219",
    # claude-3-5-sonnet-20241022 removed: deprecated by Anthropic
    "claude-3-haiku-20240307",
]


class AnthropicProvider(BaseLLMProvider):
    """Anthropic API integration for question generation and evaluation."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20250929"):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-sonnet-4-5-20250929)
        """
        super().__init__(api_key, model)
        self.client = Anthropic(api_key=api_key)
        self.async_client = AsyncAnthropic(api_key=api_key)

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using Anthropic API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            The generated text completion

        Raises:
            anthropic.AnthropicError: If the API call fails
        """
        model_to_use = model_override or self.model

        def _make_request() -> str:
            try:
                response = self.client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                if response.content and len(response.content) > 0:
                    return response.content[0].text
                return ""

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)

        return self._execute_with_retry(_make_request)

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
        Generate a structured JSON completion using Anthropic API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            anthropic.AnthropicError: If the API call fails
            json.JSONDecodeError: If response cannot be parsed as JSON

        Note:
            Anthropic doesn't have native JSON mode like OpenAI, so we
            instruct the model via the prompt and parse the response.
        """
        model_to_use = model_override or self.model

        def _make_request() -> Dict[str, Any]:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                response = self.client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                if response.content and len(response.content) > 0:
                    content = response.content[0].text
                    logger.debug(f"Anthropic API response content: {content[:500]}")

                    # Strip markdown code fences if present
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]  # Remove ```json
                    elif content.startswith("```"):
                        content = content[3:]  # Remove ```
                    if content.endswith("```"):
                        content = content[:-3]  # Remove trailing ```
                    content = content.strip()

                    return json.loads(content)

                logger.warning("Anthropic API returned empty response")
                return {}

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e

        return self._execute_with_retry(_make_request)

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Args:
            text: The text to count tokens for

        Returns:
            Estimated number of tokens

        Note:
            This is a rough approximation (1 token ≈ 4 characters).
            Anthropic's actual tokenization may differ.
        """
        # Rough approximation: 1 token ≈ 4 characters
        # For Claude models, this is a reasonable estimate
        return len(text) // 4

    async def generate_completion_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using Anthropic API asynchronously.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            The generated text completion

        Raises:
            anthropic.AnthropicError: If the API call fails
        """
        model_to_use = model_override or self.model

        async def _make_request() -> str:
            try:
                response = await self.async_client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                if response.content and len(response.content) > 0:
                    return response.content[0].text
                return ""

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)

        return await self._execute_with_retry_async(_make_request)

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
        Generate a structured JSON completion using Anthropic API asynchronously.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            anthropic.AnthropicError: If the API call fails
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        model_to_use = model_override or self.model

        async def _make_request() -> Dict[str, Any]:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                response = await self.async_client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                if response.content and len(response.content) > 0:
                    content = response.content[0].text
                    logger.debug(
                        f"Anthropic API async response content: {content[:500]}"
                    )

                    # Strip markdown code fences if present
                    content = content.strip()
                    if content.startswith("```json"):
                        content = content[7:]  # Remove ```json
                    elif content.startswith("```"):
                        content = content[3:]  # Remove ```
                    if content.endswith("```"):
                        content = content[:-3]  # Remove trailing ```
                    content = content.strip()

                    return json.loads(content)

                logger.warning("Anthropic API returned empty response")
                return {}

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e

        return await self._execute_with_retry_async(_make_request)

    def _generate_completion_internal(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate completion with actual token usage from Anthropic API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            CompletionResult with content and actual token usage
        """
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                response = self.client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                content = ""
                if response.content and len(response.content) > 0:
                    content = response.content[0].text

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)

        return self._execute_with_retry(_make_request)

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
        Generate structured completion with actual token usage from Anthropic API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            CompletionResult with parsed JSON content and actual token usage
        """
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                response = self.client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                content: Dict[str, Any] = {}
                if response.content and len(response.content) > 0:
                    raw_content = response.content[0].text
                    logger.debug(f"Anthropic API response content: {raw_content[:500]}")

                    # Strip markdown code fences if present
                    raw_content = raw_content.strip()
                    if raw_content.startswith("```json"):
                        raw_content = raw_content[7:]  # Remove ```json
                    elif raw_content.startswith("```"):
                        raw_content = raw_content[3:]  # Remove ```
                    if raw_content.endswith("```"):
                        raw_content = raw_content[:-3]  # Remove trailing ```
                    raw_content = raw_content.strip()

                    content = json.loads(raw_content)
                else:
                    logger.warning("Anthropic API returned empty response")

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e

        return self._execute_with_retry(_make_request)

    async def _generate_completion_internal_async(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> CompletionResult:
        """
        Generate completion asynchronously with actual token usage from Anthropic API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            CompletionResult with content and actual token usage
        """
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                response = await self.async_client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                content = ""
                if response.content and len(response.content) > 0:
                    content = response.content[0].text

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)

        return await self._execute_with_retry_async(_make_request)

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
        Generate structured completion asynchronously with actual token usage from Anthropic API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            CompletionResult with parsed JSON content and actual token usage
        """
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                response = await self.async_client.messages.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                # Extract text from response
                content: Dict[str, Any] = {}
                if response.content and len(response.content) > 0:
                    raw_content = response.content[0].text
                    logger.debug(
                        f"Anthropic API async response content: {raw_content[:500]}"
                    )

                    # Strip markdown code fences if present
                    raw_content = raw_content.strip()
                    if raw_content.startswith("```json"):
                        raw_content = raw_content[7:]  # Remove ```json
                    elif raw_content.startswith("```"):
                        raw_content = raw_content[3:]  # Remove ```
                    if raw_content.endswith("```"):
                        raw_content = raw_content[:-3]  # Remove trailing ```
                    raw_content = raw_content.strip()

                    content = json.loads(raw_content)
                else:
                    logger.warning("Anthropic API returned empty response")

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.input_tokens,
                        output_tokens=response.usage.output_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except anthropic.AnthropicError as e:
                raise self._handle_api_error(e)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e

        return await self._execute_with_retry_async(_make_request)

    def get_available_models(self) -> list[str]:
        """
        Get list of known Anthropic models (static list).

        For runtime validation against the API, use get_validated_models().
        Note that Anthropic does not provide a public models list endpoint,
        so fetch_available_models() returns an empty list and validation
        falls back to this static list.

        Returns:
            List of model identifiers ordered from newest to oldest.
            See ANTHROPIC_MODELS constant for the current list and maintenance notes.
        """
        return list(ANTHROPIC_MODELS)

    def fetch_available_models(self) -> list[str]:
        """
        Fetch available models from the Anthropic API.

        Note:
            Anthropic does not provide a public models list endpoint.
            This method returns an empty list, which causes get_validated_models()
            to fall back to the static list from get_available_models().

            To validate individual models, run the integration tests which make
            minimal API calls to check each model's availability.

        Returns:
            Empty list (Anthropic does not support model listing)
        """
        # Anthropic does not provide a models list endpoint
        # Return empty list to signal that runtime validation is not available
        logger.debug(
            "Anthropic does not provide a models list API. "
            "Using static model list for validation."
        )
        return []

    async def fetch_available_models_async(self) -> list[str]:
        """
        Fetch available models from the Anthropic API asynchronously.

        Note:
            Anthropic does not provide a public models list endpoint.
            This method returns an empty list, which causes get_validated_models_async()
            to fall back to the static list from get_available_models().

        Returns:
            Empty list (Anthropic does not support model listing)
        """
        # Anthropic does not provide a models list endpoint
        logger.debug(
            "Anthropic does not provide a models list API. "
            "Using static model list for validation."
        )
        return []

    async def cleanup(self) -> None:
        """Clean up async resources.

        Closes the async client to release connection pools and file handles.
        """
        if hasattr(self, "async_client") and self.async_client is not None:
            await self.async_client.close()
