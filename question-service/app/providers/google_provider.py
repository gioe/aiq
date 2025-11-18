"""Google Generative AI provider integration."""

import json
from typing import Any, Dict

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from .base import BaseLLMProvider


class GoogleProvider(BaseLLMProvider):
    """Google Generative AI integration for question generation and evaluation."""

    def __init__(self, api_key: str, model: str = "gemini-1.5-pro"):
        """
        Initialize Google provider.

        Args:
            api_key: Google API key
            model: Model to use (default: gemini-1.5-pro)
        """
        super().__init__(api_key, model)
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model)

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Google-specific parameters

        Returns:
            The generated text completion

        Raises:
            Exception: If the API call fails
        """
        try:
            generation_config = GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                **kwargs,
            )

            response = self.client.generate_content(
                prompt,
                generation_config=generation_config,
            )

            # Extract text from response
            if response.text:
                return response.text
            return ""

        except Exception as e:
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
        Generate a structured JSON completion using Google Generative AI API.

        Args:
            prompt: The prompt to send to the model
            response_format: JSON schema for the expected response
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            **kwargs: Additional Google-specific parameters

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            Exception: If the API call fails or response cannot be parsed as JSON

        Note:
            Google Gemini doesn't have native JSON mode like OpenAI, so we
            instruct the model via the prompt and parse the response.
        """
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

            response = self.client.generate_content(
                json_prompt,
                generation_config=generation_config,
            )

            # Extract text from response
            if response.text:
                return json.loads(response.text)

            return {}

        except Exception as e:
            # Check if it's a JSON parsing error
            if isinstance(e, json.JSONDecodeError):
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            raise self._handle_api_error(e)

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

    def get_available_models(self) -> list[str]:
        """
        Get list of available Google Generative AI models.

        Returns:
            List of model identifiers

        Note:
            Common Gemini models:
            - gemini-1.5-pro (most capable, best for complex reasoning)
            - gemini-1.5-flash (faster, optimized for speed)
            - gemini-1.0-pro (earlier version, still capable)
        """
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro",
        ]
