"""xAI (Grok) LLM provider integration.

This provider uses the xAI API which is fully compatible with the OpenAI API,
allowing us to use the OpenAI SDK with a different base URL.
"""

import json
import logging
from typing import Any, Dict, Optional

from openai import AsyncOpenAI, OpenAI

from ..cost_tracking import CompletionResult, TokenUsage
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class XAIProvider(BaseLLMProvider):
    """xAI (Grok) API integration for question generation and evaluation.

    Uses OpenAI SDK with xAI base URL for compatibility.
    """

    def __init__(self, api_key: str, model: str = "grok-4"):
        """
        Initialize xAI provider.

        Args:
            api_key: xAI API key (starts with "xai-")
            model: Model identifier (e.g., "grok-4", "grok-3")
        """
        self.api_key = api_key
        self.model = model
        self.provider_name = "xai"

        # Initialize OpenAI client with xAI base URL
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )
        self.async_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.x.ai/v1",
        )

        logger.info(f"Initialized xAI provider with model {model}")

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using xAI's Grok model.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            Generated text response

        Raises:
            Exception: If API call fails
        """
        model_to_use = model_override or self.model

        def _make_request() -> str:
            try:
                response = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                return response.choices[0].message.content

            except Exception as e:
                logger.debug(f"xAI API call failed: {str(e)}")
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
        Generate a structured response using xAI's Grok model.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            response_format: Expected response schema (for validation)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            Parsed JSON response as dictionary

        Raises:
            Exception: If API call or JSON parsing fails
        """
        model_to_use = model_override or self.model

        def _make_request() -> Dict[str, Any]:
            content = ""
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"IMPORTANT: Return ONLY valid JSON with no markdown formatting or additional text."
                )

                # Make API call using OpenAI SDK
                response = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                # Extract and parse JSON response
                content = response.choices[0].message.content
                logger.debug(f"xAI API response content: {content[:500]}")

                # Strip markdown code fences if present (defensive)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                return json.loads(content)

            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON response: {str(e)}")
                logger.debug(f"Raw response: {content}")
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                logger.debug(f"xAI API call failed: {str(e)}")
                raise self._handle_api_error(e)

        return self._execute_with_retry(_make_request)

    def count_tokens(self, text: str) -> int:
        """
        Estimate token count for text.

        Uses a simple heuristic (1 token ≈ 4 characters) as xAI doesn't
        provide a public tokenizer. This is approximate.

        Args:
            text: Text to count tokens for

        Returns:
            Estimated token count
        """
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
        Generate a text completion using xAI's Grok model asynchronously.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            Generated text response

        Raises:
            Exception: If API call fails
        """
        model_to_use = model_override or self.model

        async def _make_request() -> str:
            try:
                response = await self.async_client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                return response.choices[0].message.content

            except Exception as e:
                logger.error(f"xAI API async error: {str(e)}")
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
        Generate a structured response using xAI's Grok model asynchronously.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            response_format: Expected response schema (for validation)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            Parsed JSON response as dictionary

        Raises:
            Exception: If API call or JSON parsing fails
        """
        model_to_use = model_override or self.model

        async def _make_request() -> Dict[str, Any]:
            content = ""
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"IMPORTANT: Return ONLY valid JSON with no markdown formatting or additional text."
                )

                # Make API call using OpenAI SDK
                response = await self.async_client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                # Extract and parse JSON response
                content = response.choices[0].message.content
                logger.debug(f"xAI API async response content: {content[:500]}")

                # Strip markdown code fences if present (defensive)
                content = content.strip()
                if content.startswith("```json"):
                    content = content[7:]
                elif content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                content = content.strip()

                return json.loads(content)

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response: {content}")
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                logger.error(f"xAI API async error: {str(e)}")
                raise self._handle_api_error(e)

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
        Generate completion with actual token usage from xAI API.

        Since xAI uses OpenAI-compatible API, we get usage data the same way.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            CompletionResult with content and actual token usage
        """
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                response = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                content = response.choices[0].message.content or ""

                # Extract actual token usage from response (OpenAI-compatible)
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except Exception as e:
                logger.debug(f"xAI API call failed: {str(e)}")
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
        Generate structured completion with actual token usage from xAI API.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            response_format: Expected response schema (for validation)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            CompletionResult with parsed JSON content and actual token usage
        """
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            content_str = ""
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"IMPORTANT: Return ONLY valid JSON with no markdown formatting or additional text."
                )

                # Make API call using OpenAI SDK
                response = self.client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                # Extract and parse JSON response
                content_str = response.choices[0].message.content or "{}"
                logger.debug(f"xAI API response content: {content_str[:500]}")

                # Strip markdown code fences if present (defensive)
                content_str = content_str.strip()
                if content_str.startswith("```json"):
                    content_str = content_str[7:]
                elif content_str.startswith("```"):
                    content_str = content_str[3:]
                if content_str.endswith("```"):
                    content_str = content_str[:-3]
                content_str = content_str.strip()

                content = json.loads(content_str)

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

            except json.JSONDecodeError as e:
                logger.debug(f"Failed to parse JSON response: {str(e)}")
                logger.debug(f"Raw response: {content_str}")
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                logger.debug(f"xAI API call failed: {str(e)}")
                raise self._handle_api_error(e)

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
        Generate completion asynchronously with actual token usage from xAI API.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            CompletionResult with content and actual token usage
        """
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                response = await self.async_client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )

                content = response.choices[0].message.content or ""

                # Extract actual token usage from response (OpenAI-compatible)
                token_usage = None
                if response.usage:
                    token_usage = TokenUsage(
                        input_tokens=response.usage.prompt_tokens,
                        output_tokens=response.usage.completion_tokens,
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except Exception as e:
                logger.error(f"xAI API async error: {str(e)}")
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
        Generate structured completion asynchronously with actual token usage from xAI API.

        Args:
            prompt: The prompt to generate from
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            response_format: Expected response schema (for validation)
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional arguments passed to the API

        Returns:
            CompletionResult with parsed JSON content and actual token usage
        """
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            content_str = ""
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"IMPORTANT: Return ONLY valid JSON with no markdown formatting or additional text."
                )

                # Make API call using OpenAI SDK
                response = await self.async_client.chat.completions.create(
                    model=model_to_use,
                    messages=[{"role": "user", "content": json_prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                    **kwargs,
                )

                # Extract and parse JSON response
                content_str = response.choices[0].message.content or "{}"
                logger.debug(f"xAI API async response content: {content_str[:500]}")

                # Strip markdown code fences if present (defensive)
                content_str = content_str.strip()
                if content_str.startswith("```json"):
                    content_str = content_str[7:]
                elif content_str.startswith("```"):
                    content_str = content_str[3:]
                if content_str.endswith("```"):
                    content_str = content_str[:-3]
                content_str = content_str.strip()

                content = json.loads(content_str)

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

            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {str(e)}")
                logger.error(f"Raw response: {content_str}")
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                logger.error(f"xAI API async error: {str(e)}")
                raise self._handle_api_error(e)

        return await self._execute_with_retry_async(_make_request)

    def get_available_models(self) -> list[str]:
        """
        Get list of known xAI models (static list).

        For runtime validation against the API, use get_validated_models().

        Returns:
            List of model identifiers

        Note:
            Current xAI models (as of February 2026):
            - grok-4: Latest flagship model with exceptional math performance (alias for latest stable version)
            - grok-3: Previous generation flagship
        """
        # Last reviewed: 2026-02-10
        # Docs: https://docs.x.ai/docs/models
        return [
            "grok-4",
            "grok-3",
        ]

    def fetch_available_models(self) -> list[str]:
        """
        Fetch available models from the xAI API.

        Queries the xAI models.list() endpoint (OpenAI-compatible) to get
        the current list of available Grok models.

        Returns:
            List of model identifiers from the API

        Raises:
            Exception: If the API call fails
        """
        try:
            models = self.client.models.list()
            # Filter to grok models
            result = []
            for model in models.data:
                if model.id.startswith("grok"):
                    result.append(model.id)
                else:
                    logger.debug(f"Filtered out non-Grok model: {model.id}")
            return sorted(result)
        except Exception:
            raise

    async def fetch_available_models_async(self) -> list[str]:
        """
        Fetch available models from the xAI API asynchronously.

        Queries the xAI models.list() endpoint (OpenAI-compatible) to get
        the current list of available Grok models.

        Returns:
            List of model identifiers from the API

        Raises:
            Exception: If the API call fails
        """
        try:
            models = await self.async_client.models.list()
            # Filter to grok models
            return sorted(
                [model.id for model in models.data if model.id.startswith("grok")]
            )
        except Exception:
            raise

    async def cleanup(self) -> None:
        """Clean up async resources.

        Closes the async client to release connection pools and file handles.
        """
        if hasattr(self, "async_client") and self.async_client is not None:
            await self.async_client.close()
