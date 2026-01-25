"""Google Generative AI provider integration."""

import json
from typing import Any, Dict, Optional

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from ..cost_tracking import CompletionResult, TokenUsage
from .base import BaseLLMProvider


class GoogleProvider(BaseLLMProvider):
    """Google Generative AI integration for question generation and evaluation."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        """
        Initialize Google provider.

        Args:
            api_key: Google API key
            model: Model to use (default: gemini-2.5-pro)
        """
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    def _get_client(self, model: str) -> genai.GenerativeModel:
        """Get a GenerativeModel client for the specified model.

        Args:
            model: Model identifier

        Returns:
            GenerativeModel instance
        """
        if model == self.model:
            return self.client
        return genai.GenerativeModel(model)

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            The generated text completion

        Raises:
            Exception: If the API call fails
        """
        client = self._get_client(model_override or self.model)

        def _make_request() -> str:
            try:
                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = client.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                # Extract text from response
                if response.text:
                    return response.text
                return ""

            except Exception as e:
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
        Generate a structured JSON completion using Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            Exception: If the API call fails or response cannot be parsed as JSON

        Note:
            Google Gemini doesn't have native JSON mode like OpenAI, so we
            instruct the model via the prompt and parse the response.
        """
        client = self._get_client(model_override or self.model)

        def _make_request() -> Dict[str, Any]:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = client.generate_content(
                    json_prompt,
                    generation_config=generation_config,
                )

                # Extract text from response
                if response.text:
                    return json.loads(response.text)

                return {}

            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                raise self._handle_api_error(e)

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
            Google's actual tokenization may differ.
        """
        # Rough approximation: 1 token ≈ 4 characters
        # For more accuracy, we could use model.count_tokens() method
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
        Generate a text completion using Google Generative AI API asynchronously.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            The generated text completion

        Raises:
            Exception: If the API call fails
        """
        client = self._get_client(model_override or self.model)

        async def _make_request() -> str:
            try:
                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await client.generate_content_async(
                    prompt,
                    generation_config=generation_config,
                )

                # Extract text from response
                if response.text:
                    return response.text
                return ""

            except Exception as e:
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
        Generate a structured JSON completion using Google Generative AI API asynchronously.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            Exception: If the API call fails or response cannot be parsed as JSON
        """
        client = self._get_client(model_override or self.model)

        async def _make_request() -> Dict[str, Any]:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await client.generate_content_async(
                    json_prompt,
                    generation_config=generation_config,
                )

                # Extract text from response
                if response.text:
                    return json.loads(response.text)

                return {}

            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
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
        Generate completion with token usage from Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            CompletionResult with content and token usage

        Note:
            Google API provides usage_metadata with token counts in the response.
        """
        client = self._get_client(model_override or self.model)
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = client.generate_content(
                    prompt,
                    generation_config=generation_config,
                )

                content = response.text if response.text else ""

                # Extract token usage from response metadata if available
                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )
                else:
                    # Fall back to estimation
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(prompt),
                        output_tokens=self.count_tokens(content),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except Exception as e:
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
        Generate structured completion with token usage from Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            CompletionResult with parsed JSON content and token usage
        """
        client = self._get_client(model_override or self.model)
        model_to_use = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = client.generate_content(
                    json_prompt,
                    generation_config=generation_config,
                )

                # Parse JSON response
                content: Dict[str, Any] = {}
                raw_content = response.text if response.text else ""
                if raw_content:
                    content = json.loads(raw_content)

                # Extract token usage from response metadata if available
                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )
                else:
                    # Fall back to estimation
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(json_prompt),
                        output_tokens=self.count_tokens(raw_content),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
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
        Generate completion asynchronously with token usage from Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            CompletionResult with content and token usage
        """
        client = self._get_client(model_override or self.model)
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await client.generate_content_async(
                    prompt,
                    generation_config=generation_config,
                )

                content = response.text if response.text else ""

                # Extract token usage from response metadata if available
                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )
                else:
                    # Fall back to estimation
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(prompt),
                        output_tokens=self.count_tokens(content),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except Exception as e:
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
        Generate structured completion asynchronously with token usage from Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            CompletionResult with parsed JSON content and token usage
        """
        client = self._get_client(model_override or self.model)
        model_to_use = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                # Add JSON formatting instruction to the prompt
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                generation_config = GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await client.generate_content_async(
                    json_prompt,
                    generation_config=generation_config,
                )

                # Parse JSON response
                content: Dict[str, Any] = {}
                raw_content = response.text if response.text else ""
                if raw_content:
                    content = json.loads(raw_content)

                # Extract token usage from response metadata if available
                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )
                else:
                    # Fall back to estimation
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(json_prompt),
                        output_tokens=self.count_tokens(raw_content),
                        model=model_to_use,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                raise self._handle_api_error(e)

        return await self._execute_with_retry_async(_make_request)

    def get_available_models(self) -> list[str]:
        """
        Get list of available Google Generative AI models.

        Returns:
            List of model identifiers

        Note:
            Common Gemini models (as of January 2026):
            - gemini-3-pro-preview (Gemini 3 Pro Preview - advanced reasoning)
            - gemini-3-flash-preview (Gemini 3 Flash Preview - faster variant)
            - gemini-2.5-pro (stable, enhanced reasoning with 1M context)
            - gemini-2.5-flash (fast, cost-effective)
            - gemini-2.0-flash (previous generation flash model)

        Maintenance:
            Update this list when new Gemini models are released. Check the official
            Google AI documentation for current model IDs.
            Run integration tests to verify model availability:
            pytest tests/providers/test_provider_model_availability_integration.py --run-integration
        """
        return [
            "gemini-3-pro-preview",
            "gemini-3-flash-preview",
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.0-flash",
        ]

    async def cleanup(self) -> None:
        """Clean up async resources.

        Google's generativeai SDK manages connections internally,
        so no explicit cleanup is required for the client itself.
        This method is provided for API consistency.
        """
        # Google's SDK uses a module-level configuration pattern
        # and doesn't expose explicit async client cleanup
        pass
