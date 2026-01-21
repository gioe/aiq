"""xAI (Grok) LLM provider integration.

This provider uses the xAI API which is fully compatible with the OpenAI API,
allowing us to use the OpenAI SDK with a different base URL.
"""

import json
import logging
from typing import Any, Dict, Optional

from openai import OpenAI

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
            model: Model identifier (e.g., "grok-4", "grok-beta")
        """
        self.api_key = api_key
        self.model = model
        self.provider_name = "xai"

        # Initialize OpenAI client with xAI base URL
        self.client = OpenAI(
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
        **kwargs,
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
        **kwargs,
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
