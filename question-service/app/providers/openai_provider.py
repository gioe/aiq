"""OpenAI LLM provider integration."""

import json
from typing import Any, Dict, Optional

import openai
from openai import OpenAI

from .base import BaseLLMProvider


class OpenAIProvider(BaseLLMProvider):
    """OpenAI API integration for question generation and evaluation."""

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

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using OpenAI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            The generated text completion

        Raises:
            openai.OpenAIError: If the API call fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )
            return response.choices[0].message.content or ""
        except openai.OpenAIError as e:
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
        Generate a structured JSON completion using OpenAI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional OpenAI-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            openai.OpenAIError: If the API call fails
            json.JSONDecodeError: If response cannot be parsed as JSON
        """
        try:
            # Add JSON mode instruction to the prompt
            json_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema: {json.dumps(response_format)}"

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": json_prompt}],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                **kwargs,
            )

            content = response.choices[0].message.content or "{}"
            return json.loads(content)
        except openai.OpenAIError as e:
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
            For accurate counting, use tiktoken library.
        """
        # Rough approximation: 1 token ≈ 4 characters
        # For more accuracy, we could integrate tiktoken library
        return len(text) // 4

    def get_available_models(self) -> list[str]:
        """
        Get list of available OpenAI models.

        Returns:
            List of model identifiers

        Note:
            Common models:
            - gpt-4-turbo-preview (latest GPT-4 Turbo)
            - gpt-4 (standard GPT-4)
            - gpt-3.5-turbo (faster, cheaper)
        """
        return [
            "gpt-4-turbo-preview",
            "gpt-4",
            "gpt-4-0125-preview",
            "gpt-3.5-turbo",
            "gpt-3.5-turbo-16k",
        ]
