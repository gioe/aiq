"""OpenAI LLM provider integration."""

import json
import logging
from typing import Any, Dict, Optional

import openai
from openai import AsyncOpenAI, OpenAI

from ..cost_tracking import CompletionResult, TokenUsage
from .base import BaseLLMProvider


logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API integration for question generation and evaluation."""

    # Models that require max_completion_tokens instead of max_tokens.
    # These reasoning models use internal chain-of-thought that consumes
    # the completion token budget, so they need a higher limit.
    _MAX_COMPLETION_TOKENS_MODELS = ("gpt-5", "o1", "o3", "o4")
    _REASONING_TOKEN_MULTIPLIER = 4

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4-turbo-preview",
        organization: Optional[str] = None,
    ):
        """
        Initialize OpenAI provider.

        Args:
            api_key: OpenAI API key
            model: Model to use (default: gpt-4-turbo-preview)
            organization: Optional organization ID
        """
        super().__init__(api_key, model)
        self.client = OpenAI(api_key=api_key, organization=organization)
        self.async_client = AsyncOpenAI(api_key=api_key, organization=organization)

    def _uses_max_completion_tokens(self, model: str) -> bool:
        """Check if a model requires max_completion_tokens instead of max_tokens."""
        return model.startswith(self._MAX_COMPLETION_TOKENS_MODELS)

    def _get_message_content(self, response: Any) -> Optional[str]:
        """Extract message content from a chat completion response.

        Raises LLMProviderError if the response has no choices.
        """
        if not response.choices:
            raise self._handle_api_error(ValueError("API returned empty choices list"))
        return response.choices[0].message.content

    def _token_limit_kwargs(self, model: str, max_tokens: int) -> Dict[str, int]:
        """Return the correct token limit parameter for the given model.

        Reasoning models (GPT-5.x, o1, o3, o4) use internal chain-of-thought
        that consumes the completion token budget. The requested max_tokens
        is multiplied to leave room for both reasoning and output.
        """
        if self._uses_max_completion_tokens(model):
            return {
                "max_completion_tokens": max_tokens * self._REASONING_TOKEN_MULTIPLIER,
            }
        return {"max_tokens": max_tokens}

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using OpenAI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            The generated text completion

        Raises:
            openai.OpenAIError: If the API call fails
        """
        model_to_use = model_override or self.model

        def _make_request() -> str:
            try:
                response = self.client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    **kwargs,
                )
                return self._get_message_content(response) or ""
            except openai.OpenAIError as e:
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
        Generate a structured JSON completion using OpenAI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            openai.OpenAIError: If the API call fails
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        model_to_use = model_override or self.model

        def _make_request() -> Dict[str, Any]:
            try:
                # Add JSON mode instruction to the prompt
                json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"

                response = self.client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                content = self._get_message_content(response) or "{}"
                return json.loads(content)
            except openai.OpenAIError as e:
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
            For accurate counting, use tiktoken library.
        """
        # Rough approximation: 1 token ≈ 4 characters
        # For more accuracy, we could integrate tiktoken library
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
        Generate a text completion using OpenAI API asynchronously.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            The generated text completion

        Raises:
            openai.OpenAIError: If the API call fails
        """
        model_to_use = model_override or self.model

        async def _make_request() -> str:
            try:
                response = await self.async_client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    **kwargs,
                )
                return self._get_message_content(response) or ""
            except openai.OpenAIError as e:
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
        Generate a structured JSON completion using OpenAI API asynchronously.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            openai.OpenAIError: If the API call fails
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        model_to_use = model_override or self.model

        async def _make_request() -> Dict[str, Any]:
            try:
                # Add JSON mode instruction to the prompt
                json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"

                response = await self.async_client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                content = self._get_message_content(response) or "{}"
                return json.loads(content)
            except openai.OpenAIError as e:
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
        Generate completion with actual token usage from OpenAI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            CompletionResult with content and actual token usage
        """
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                response = self.client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    **kwargs,
                )

                content = self._get_message_content(response) or ""

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)
            except openai.OpenAIError as e:
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
        Generate structured completion with actual token usage from OpenAI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            CompletionResult with parsed JSON content and actual token usage
        """
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                # Add JSON mode instruction to the prompt
                json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"

                response = self.client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                raw_content = self._get_message_content(response) or "{}"
                content = json.loads(raw_content)

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)
            except openai.OpenAIError as e:
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
        Generate completion asynchronously with actual token usage from OpenAI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            CompletionResult with content and actual token usage
        """
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                response = await self.async_client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    **kwargs,
                )

                content = self._get_message_content(response) or ""

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)
            except openai.OpenAIError as e:
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
        Generate structured completion asynchronously with actual token usage from OpenAI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            CompletionResult with parsed JSON content and actual token usage
        """
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                # Add JSON mode instruction to the prompt
                json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"

                response = await self.async_client.chat.completions.create(  # type: ignore[call-overload]
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    **self._token_limit_kwargs(model_to_use, max_tokens),
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                raw_content = self._get_message_content(response)
                if not raw_content:
                    logger.warning(
                        "OpenAI async structured response had empty content. "
                        "finish_reason=%s, usage=%s, model=%s",
                        response.choices[0].finish_reason,
                        response.usage,
                        model_to_use,
                    )
                    raw_content = "{}"
                content = json.loads(raw_content)

                # Extract actual token usage from response
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)
            except openai.OpenAIError as e:
                raise self._handle_api_error(e)
            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e

        return await self._execute_with_retry_async(_make_request)

    def get_available_models(self) -> list[str]:
        """
        Get list of known OpenAI models (static list).

        For runtime validation against the API, use get_validated_models().

        Returns:
            List of model identifiers (ordered newest to oldest)

        Note:
            Current models (as of January 2026):
            - gpt-5.2 (latest GPT-5 series)
            - gpt-5.1, gpt-5 (GPT-5 series)
            - o4-mini (latest reasoning model, efficient)
            - o3, o3-mini (reasoning models)
            - o1 (original reasoning model)
            - gpt-4o, gpt-4o-mini (GPT-4o series)
            - gpt-4-turbo-preview, gpt-4 (GPT-4 series)
            - gpt-3.5-turbo (faster, cheaper, legacy)
        """
        # Last reviewed: 2026-02-10
        # Docs: https://platform.openai.com/docs/models
        return [
            # GPT-5 series (newest)
            "gpt-5.2",
            "gpt-5.1",
            "gpt-5",
            # Reasoning models (o-series) — use max_completion_tokens, not max_tokens
            "o4-mini",
            "o3",
            "o3-mini",
            "o1",
            # GPT-4 series
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4-turbo-preview",
            "gpt-4",
            "gpt-4-0125-preview",
            # GPT-3.5 series (legacy)
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
        ]

    def fetch_available_models(self) -> list[str]:
        """
        Fetch available models from the OpenAI API.

        Queries the OpenAI models.list() endpoint to get the current list
        of available models. Filters to only include chat-compatible models.

        Returns:
            List of model identifiers from the API

        Raises:
            openai.OpenAIError: If the API call fails
        """
        try:
            models = self.client.models.list()
            # Filter to models that support chat completions
            # Chat models typically include gpt-*, o1*, o3*, o4*, etc.
            chat_model_prefixes = ("gpt-", "o1", "o3", "o4")
            result = []
            for model in models.data:
                if any(model.id.startswith(prefix) for prefix in chat_model_prefixes):
                    result.append(model.id)
                else:
                    logger.debug(f"Filtered out non-chat model: {model.id}")
            return sorted(result)
        except openai.OpenAIError:
            raise

    async def fetch_available_models_async(self) -> list[str]:
        """
        Fetch available models from the OpenAI API asynchronously.

        Queries the OpenAI models.list() endpoint to get the current list
        of available models. Filters to only include chat-compatible models.

        Returns:
            List of model identifiers from the API

        Raises:
            openai.OpenAIError: If the API call fails
        """
        try:
            models = await self.async_client.models.list()
            # Filter to models that support chat completions
            chat_model_prefixes = ("gpt-", "o1", "o3", "o4")
            return sorted(
                [
                    model.id
                    for model in models.data
                    if any(
                        model.id.startswith(prefix) for prefix in chat_model_prefixes
                    )
                ]
            )
        except openai.OpenAIError:
            raise

    async def cleanup(self) -> None:
        """Clean up async resources.

        Closes the async client to release connection pools and file handles.
        """
        if hasattr(self, "async_client") and self.async_client is not None:
            await self.async_client.close()
