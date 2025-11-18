"""Anthropic LLM provider integration."""

import json
import logging
from typing import Any, Dict

import anthropic
from anthropic import Anthropic

from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Anthropic API integration for question generation and evaluation."""

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        """
        Initialize Anthropic provider.

        Args:
            api_key: Anthropic API key
            model: Model to use (default: claude-3-5-sonnet-20241022)
        """
        super().__init__(api_key, model)
        self.client = Anthropic(api_key=api_key)

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using Anthropic API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate (required by Anthropic)
            **kwargs: Additional Anthropic-specific parameters

        Returns:
            The generated text completion

        Raises:
            anthropic.AnthropicError: If the API call fails
        """
        try:
            response = self.client.messages.create(
                model=self.model,
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

    def generate_structured_completion(
        self,
        prompt: str,
        response_format: Dict[str, Any],
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Generate a structured JSON completion using Anthropic API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens to generate
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
        try:
            # Add JSON formatting instruction to the prompt
            json_prompt = (
                f"{prompt}\n\n"
                f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                f"Your response must be only valid JSON with no additional text."
            )

            response = self.client.messages.create(
                model=self.model,
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

    def get_available_models(self) -> list[str]:
        """
        Get list of available Anthropic models.

        Returns:
            List of model identifiers

        Note:
            Common Claude models:
            - claude-3-5-sonnet-20241022 (latest Claude 3.5 Sonnet)
            - claude-3-opus-20240229 (Claude 3 Opus - most capable)
            - claude-3-sonnet-20240229 (Claude 3 Sonnet - balanced)
            - claude-3-haiku-20240307 (Claude 3 Haiku - fast and affordable)
        """
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-sonnet-20240620",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
        ]
