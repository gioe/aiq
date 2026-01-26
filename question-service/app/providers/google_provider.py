"""Google Gen AI provider integration using the new google-genai SDK."""

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from google import genai
from google.genai import types

from ..cost_tracking import CompletionResult, TokenUsage
from .base import BaseLLMProvider

logger = logging.getLogger(__name__)


@dataclass
class BatchJobResult:
    """Result from a batch job execution."""

    job_name: str
    state: str
    responses: List[Dict[str, Any]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0


class GoogleProvider(BaseLLMProvider):
    """Google Gen AI integration for question generation and evaluation.

    This provider uses the new google-genai SDK which supports both the
    Gemini Developer API and Vertex AI APIs. It includes support for
    batch processing to handle bulk question generation efficiently.
    """

    def __init__(self, api_key: str, model: str = "gemini-2.5-pro"):
        """
        Initialize Google provider.

        Args:
            api_key: Google API key
            model: Model to use (default: gemini-2.5-pro)
        """
        super().__init__(api_key, model)
        self._client = genai.Client(api_key=api_key)

    @property
    def client(self) -> genai.Client:
        """Get the GenAI client."""
        return self._client

    def generate_completion(
        self,
        prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1000,
        model_override: Optional[str] = None,
        **kwargs: Any,
    ) -> str:
        """
        Generate a text completion using Google Gen AI API.

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
        model = model_override or self.model

        def _make_request() -> str:
            try:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

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
        Generate a structured JSON completion using Google Gen AI API.

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
        model = model_override or self.model

        def _make_request() -> Dict[str, Any]:
            try:
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = self._client.models.generate_content(
                    model=model,
                    contents=json_prompt,
                    config=config,
                )

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
        Generate a text completion using Google Gen AI API asynchronously.

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
        model = model_override or self.model

        async def _make_request() -> str:
            try:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

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
        Generate a structured JSON completion using Google Gen AI API asynchronously.

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
        model = model_override or self.model

        async def _make_request() -> Dict[str, Any]:
            try:
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=json_prompt,
                    config=config,
                )

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
        Generate completion with token usage from Google Gen AI API.

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
        model = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = self._client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

                content = response.text if response.text else ""

                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model,
                        provider=self.get_provider_name(),
                    )
                else:
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(prompt),
                        output_tokens=self.count_tokens(content),
                        model=model,
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
        Generate structured completion with token usage from Google Gen AI API.

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
        model = model_override or self.model

        def _make_request() -> CompletionResult:
            try:
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = self._client.models.generate_content(
                    model=model,
                    contents=json_prompt,
                    config=config,
                )

                content: Dict[str, Any] = {}
                raw_content = response.text if response.text else ""
                if raw_content:
                    content = json.loads(raw_content)

                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model,
                        provider=self.get_provider_name(),
                    )
                else:
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(json_prompt),
                        output_tokens=self.count_tokens(raw_content),
                        model=model,
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
        Generate completion asynchronously with token usage from Google Gen AI API.

        Args:
            prompt: The prompt to send to the model
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            model_override: Optional model to use instead of the provider's default
            **kwargs: Additional Google-specific parameters

        Returns:
            CompletionResult with content and token usage
        """
        model = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=config,
                )

                content = response.text if response.text else ""

                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model,
                        provider=self.get_provider_name(),
                    )
                else:
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(prompt),
                        output_tokens=self.count_tokens(content),
                        model=model,
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
        Generate structured completion asynchronously with token usage from Google Gen AI API.

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
        model = model_override or self.model

        async def _make_request() -> CompletionResult:
            try:
                json_prompt = (
                    f"{prompt}\n\n"
                    f"Respond with valid JSON matching this schema: {json.dumps(response_format)}\n"
                    f"Your response must be only valid JSON with no additional text."
                )

                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                    **kwargs,
                )

                response = await self._client.aio.models.generate_content(
                    model=model,
                    contents=json_prompt,
                    config=config,
                )

                content: Dict[str, Any] = {}
                raw_content = response.text if response.text else ""
                if raw_content:
                    content = json.loads(raw_content)

                token_usage = None
                if hasattr(response, "usage_metadata") and response.usage_metadata:
                    metadata = response.usage_metadata
                    token_usage = TokenUsage(
                        input_tokens=getattr(metadata, "prompt_token_count", 0),
                        output_tokens=getattr(metadata, "candidates_token_count", 0),
                        model=model,
                        provider=self.get_provider_name(),
                    )
                else:
                    token_usage = TokenUsage(
                        input_tokens=self.count_tokens(json_prompt),
                        output_tokens=self.count_tokens(raw_content),
                        model=model,
                        provider=self.get_provider_name(),
                    )

                return CompletionResult(content=content, token_usage=token_usage)

            except json.JSONDecodeError as e:
                raise Exception(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                raise self._handle_api_error(e)

        return await self._execute_with_retry_async(_make_request)

    # -------------------------------------------------------------------------
    # Batch API Methods
    # -------------------------------------------------------------------------

    def create_batch_job(
        self,
        prompts: List[str],
        model_override: Optional[str] = None,
        display_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """
        Create a batch job for processing multiple prompts.

        This is useful for bulk question generation where individual API calls
        might timeout on complex prompts. Batch jobs are processed asynchronously
        and can handle longer processing times.

        Args:
            prompts: List of prompts to process
            model_override: Optional model to use instead of the provider's default
            display_name: Optional display name for the batch job
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens per response

        Returns:
            The batch job name/ID for tracking

        Raises:
            Exception: If batch job creation fails
        """
        model = model_override or self.model

        inline_requests: List[Dict[str, Any]] = []
        for i, prompt in enumerate(prompts):
            request: Dict[str, Any] = {
                "contents": prompt,
                "config": {
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
                "metadata": {"key": f"request-{i}"},
            }
            inline_requests.append(request)

        job_display_name = (
            display_name or f"question-generation-batch-{int(time.time())}"
        )

        batch_job = self._client.batches.create(
            model=f"models/{model}",
            src=inline_requests,  # type: ignore[arg-type]
            config={"display_name": job_display_name},
        )

        job_name = batch_job.name or ""
        logger.info(f"Created batch job: {job_name} with {len(prompts)} requests")
        return job_name

    def get_batch_job_status(self, job_name: str) -> str:
        """
        Get the status of a batch job.

        Args:
            job_name: The batch job name/ID

        Returns:
            Job state string (e.g., 'JOB_STATE_SUCCEEDED', 'JOB_STATE_FAILED')
        """
        batch_job = self._client.batches.get(name=job_name)
        if batch_job.state is None:
            return "UNKNOWN"
        return batch_job.state.name

    def wait_for_batch_job(
        self,
        job_name: str,
        poll_interval: float = 30.0,
        timeout: float = 3600.0,
    ) -> BatchJobResult:
        """
        Wait for a batch job to complete and return results.

        Args:
            job_name: The batch job name/ID
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait before timing out

        Returns:
            BatchJobResult with responses and any errors

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        completed_states = {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

        start_time = time.time()
        batch_job = self._client.batches.get(name=job_name)
        current_state = batch_job.state.name if batch_job.state else "UNKNOWN"

        while current_state not in completed_states:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    f"Batch job {job_name} did not complete within {timeout}s"
                )

            logger.info(
                f"Batch job {job_name} state: {current_state}, "
                f"elapsed: {elapsed:.1f}s"
            )
            time.sleep(poll_interval)
            batch_job = self._client.batches.get(name=job_name)
            current_state = batch_job.state.name if batch_job.state else "UNKNOWN"

        return self._extract_batch_results(batch_job)

    def _extract_batch_results(self, batch_job: Any) -> BatchJobResult:
        """
        Extract results from a completed batch job.

        Args:
            batch_job: The completed batch job object

        Returns:
            BatchJobResult with all responses and errors
        """
        job_name = batch_job.name or ""
        state_name = batch_job.state.name if batch_job.state else "UNKNOWN"
        result = BatchJobResult(
            job_name=job_name,
            state=state_name,
        )

        if state_name != "JOB_STATE_SUCCEEDED":
            result.errors.append(f"Job ended with state: {state_name}")
            return result

        if batch_job.dest and batch_job.dest.inlined_responses:
            for inline_response in batch_job.dest.inlined_responses:
                result.total_requests += 1
                if inline_response.response:
                    try:
                        text = inline_response.response.text
                        result.responses.append(
                            {"text": text, "key": inline_response.key}
                        )
                        result.successful_requests += 1
                    except Exception as e:
                        result.errors.append(f"Error extracting response: {str(e)}")
                        result.failed_requests += 1
                elif inline_response.error:
                    result.errors.append(str(inline_response.error))
                    result.failed_requests += 1

        return result

    def generate_batch_completions(
        self,
        prompts: List[str],
        model_override: Optional[str] = None,
        display_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        poll_interval: float = 30.0,
        timeout: float = 3600.0,
    ) -> BatchJobResult:
        """
        Generate completions for multiple prompts using batch API.

        This is a convenience method that creates a batch job, waits for it
        to complete, and returns the results. Use this for bulk question
        generation where individual API calls might timeout.

        Args:
            prompts: List of prompts to process
            model_override: Optional model to use instead of the provider's default
            display_name: Optional display name for the batch job
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens per response
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait for completion

        Returns:
            BatchJobResult with all responses and any errors

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        job_name = self.create_batch_job(
            prompts=prompts,
            model_override=model_override,
            display_name=display_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return self.wait_for_batch_job(
            job_name=job_name,
            poll_interval=poll_interval,
            timeout=timeout,
        )

    async def generate_batch_completions_async(
        self,
        prompts: List[str],
        model_override: Optional[str] = None,
        display_name: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
        poll_interval: float = 30.0,
        timeout: float = 3600.0,
    ) -> BatchJobResult:
        """
        Generate completions for multiple prompts using batch API asynchronously.

        Args:
            prompts: List of prompts to process
            model_override: Optional model to use instead of the provider's default
            display_name: Optional display name for the batch job
            temperature: Sampling temperature for generation
            max_tokens: Maximum tokens per response
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait for completion

        Returns:
            BatchJobResult with all responses and any errors

        Raises:
            TimeoutError: If job doesn't complete within timeout
        """
        import asyncio

        job_name = self.create_batch_job(
            prompts=prompts,
            model_override=model_override,
            display_name=display_name,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        completed_states = {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

        start_time = time.time()
        batch_job = self._client.batches.get(name=job_name)
        current_state = batch_job.state.name if batch_job.state else "UNKNOWN"

        while current_state not in completed_states:
            elapsed = time.time() - start_time
            if elapsed > timeout:
                raise TimeoutError(
                    f"Batch job {job_name} did not complete within {timeout}s"
                )

            logger.info(
                f"Batch job {job_name} state: {current_state}, "
                f"elapsed: {elapsed:.1f}s"
            )
            await asyncio.sleep(poll_interval)
            batch_job = self._client.batches.get(name=job_name)
            current_state = batch_job.state.name if batch_job.state else "UNKNOWN"

        return self._extract_batch_results(batch_job)

    def list_batch_jobs(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        List recent batch jobs.

        Args:
            limit: Maximum number of jobs to return

        Returns:
            List of batch job summaries
        """
        jobs = []
        for job in self._client.batches.list():
            state_name = job.state.name if job.state else "UNKNOWN"
            jobs.append(
                {
                    "name": job.name,
                    "state": state_name,
                    "display_name": getattr(job, "display_name", None),
                }
            )
            if len(jobs) >= limit:
                break
        return jobs

    def cancel_batch_job(self, job_name: str) -> None:
        """
        Cancel a running batch job.

        Args:
            job_name: The batch job name/ID to cancel
        """
        self._client.batches.cancel(name=job_name)
        logger.info(f"Cancelled batch job: {job_name}")

    def delete_batch_job(self, job_name: str) -> None:
        """
        Delete a batch job and its resources.

        Args:
            job_name: The batch job name/ID to delete
        """
        self._client.batches.delete(name=job_name)
        logger.info(f"Deleted batch job: {job_name}")

    # -------------------------------------------------------------------------
    # Model Management
    # -------------------------------------------------------------------------

    def get_available_models(self) -> list[str]:
        """
        Get list of known Google Gen AI models (static list).

        For runtime validation against the API, use get_validated_models().

        Returns:
            List of model identifiers

        Warning:
            This list is hardcoded and may not reflect current API availability.
            Using an incorrect or deprecated model identifier will fail at runtime
            when making API calls. Use fetch_available_models() to query the API
            for currently available models, or get_validated_models() for a
            validated intersection of known and available models.

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

    def fetch_available_models(self) -> list[str]:
        """
        Fetch available models from the Google Gen AI API.

        Queries the models endpoint to get the current list of available
        Gemini models. Filters to only include generative models.

        Returns:
            List of model identifiers from the API

        Raises:
            Exception: If the API call fails
        """
        try:
            model_names: list[str] = []
            for model in self._client.models.list():
                name = model.name
                if name is None:
                    continue
                if name.startswith("models/"):
                    name = name[7:]
                if name.startswith("gemini-"):
                    model_names.append(name)
            return sorted(model_names)
        except Exception:
            raise

    async def fetch_available_models_async(self) -> list[str]:
        """
        Fetch available models from the Google Gen AI API asynchronously.

        Returns:
            List of model identifiers from the API

        Raises:
            Exception: If the API call fails
        """
        import asyncio

        return await asyncio.get_event_loop().run_in_executor(
            None, self.fetch_available_models
        )

    async def cleanup(self) -> None:
        """Clean up async resources.

        The google-genai SDK manages connections internally.
        Call client.close() to clean up resources.
        """
        self._client.close()
