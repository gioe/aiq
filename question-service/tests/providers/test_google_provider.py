"""Tests for Google Gen AI provider integration."""

import json
from unittest.mock import MagicMock, Mock, patch

import pytest

from app.providers.google_provider import BatchJobResult, GoogleProvider


class TestGoogleProvider:
    """Test suite for GoogleProvider."""

    @patch("app.providers.google_provider.genai.Client")
    def test_initialization(self, mock_client_class, mock_openai_api_key):
        """Test that provider initializes correctly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key, model="gemini-2.5-pro")

        assert provider.api_key == mock_openai_api_key
        assert provider.model == "gemini-2.5-pro"
        assert provider.client is not None
        assert provider.get_provider_name() == "google"
        mock_client_class.assert_called_once_with(api_key=mock_openai_api_key)

    @patch("app.providers.google_provider.genai.Client")
    def test_default_model(self, mock_client_class, mock_openai_api_key):
        """Test that default model is set correctly."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)

        assert provider.model == "gemini-2.5-pro"

    @patch("app.providers.google_provider.genai.Client")
    def test_generate_completion_success(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test successful text completion generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = mock_completion_response

        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion(
            sample_prompt, temperature=0.7, max_tokens=1000
        )

        assert result == mock_completion_response
        mock_client.models.generate_content.assert_called_once()

    @patch("app.providers.google_provider.genai.Client")
    def test_generate_completion_with_kwargs(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
    ):
        """Test completion generation with additional kwargs."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = "Response"

        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        provider.generate_completion(
            sample_prompt, temperature=0.5, max_tokens=500, top_p=0.9
        )

        mock_client.models.generate_content.assert_called_once()

    @patch("app.providers.google_provider.genai.Client")
    def test_generate_completion_api_error(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
    ):
        """Test handling of API errors during completion."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="google.*API error"):
            provider.generate_completion(sample_prompt)

    @patch("app.providers.google_provider.genai.Client")
    def test_generate_structured_completion_success(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
        mock_json_response,
    ):
        """Test successful structured JSON completion generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = json.dumps(mock_json_response)

        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_structured_completion(
            sample_prompt, sample_json_schema, temperature=0.7, max_tokens=1000
        )

        assert result == mock_json_response
        assert isinstance(result, dict)

    @patch("app.providers.google_provider.genai.Client")
    def test_generate_structured_completion_json_error(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of JSON parsing errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = "This is not valid JSON"

        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="Failed to parse JSON response"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.google_provider.genai.Client")
    def test_generate_structured_completion_api_error(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
        sample_json_schema,
    ):
        """Test handling of API errors during structured completion."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API error")

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(Exception, match="google.*API error"):
            provider.generate_structured_completion(sample_prompt, sample_json_schema)

    @patch("app.providers.google_provider.genai.Client")
    def test_count_tokens(self, mock_client_class, mock_openai_api_key):
        """Test token counting approximation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)

        text = "This is a test string for token counting."
        token_count = provider.count_tokens(text)

        expected_count = len(text) // 4
        assert token_count == expected_count

    @patch("app.providers.google_provider.genai.Client")
    def test_count_tokens_empty_string(self, mock_client_class, mock_openai_api_key):
        """Test token counting with empty string."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)

        token_count = provider.count_tokens("")
        assert token_count == 0

    @patch("app.providers.google_provider.genai.Client")
    def test_get_available_models(self, mock_client_class, mock_openai_api_key):
        """Test getting list of available models."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)

        models = provider.get_available_models()

        assert isinstance(models, list)
        assert len(models) > 0
        assert "gemini-3-pro-preview" in models
        assert "gemini-3-flash-preview" in models
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models
        assert "gemini-2.0-flash" in models

    @patch("app.providers.google_provider.genai.Client")
    def test_empty_completion_response(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
    ):
        """Test handling of empty completion response."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = None

        mock_client.models.generate_content.return_value = mock_response

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.generate_completion(sample_prompt)

        assert result == ""


class TestBatchAPI:
    """Test suite for batch API functionality."""

    @patch("app.providers.google_provider.genai.Client")
    def test_create_batch_job(self, mock_client_class, mock_openai_api_key):
        """Test creating a batch job."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_batch_job = Mock()
        mock_batch_job.name = "batches/batch-123"
        mock_client.batches.create.return_value = mock_batch_job

        provider = GoogleProvider(api_key=mock_openai_api_key)
        job_name = provider.create_batch_job(
            prompts=["Prompt 1", "Prompt 2"],
            display_name="test-batch",
        )

        assert job_name == "batches/batch-123"
        mock_client.batches.create.assert_called_once()

    @patch("app.providers.google_provider.genai.Client")
    def test_create_batch_job_empty_prompts(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test creating a batch job with empty prompts raises ValueError."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(ValueError, match="cannot be empty"):
            provider.create_batch_job(prompts=[])

    @patch("app.providers.google_provider.genai.Client")
    def test_create_batch_job_exceeds_max_size(
        self, mock_client_class, mock_openai_api_key
    ):
        """Test creating a batch job exceeding max size raises ValueError."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(ValueError, match="exceeds maximum"):
            provider.create_batch_job(prompts=["prompt"] * 1001)

    @patch("app.providers.google_provider.genai.Client")
    def test_get_batch_job_status(self, mock_client_class, mock_openai_api_key):
        """Test getting batch job status."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_batch_job = Mock()
        mock_batch_job.state.name = "JOB_STATE_RUNNING"
        mock_client.batches.get.return_value = mock_batch_job

        provider = GoogleProvider(api_key=mock_openai_api_key)
        status = provider.get_batch_job_status("batches/batch-123")

        assert status == "JOB_STATE_RUNNING"
        mock_client.batches.get.assert_called_once_with(name="batches/batch-123")

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.google_provider.time.sleep")
    def test_wait_for_batch_job_success(
        self, mock_sleep, mock_client_class, mock_openai_api_key
    ):
        """Test waiting for a batch job to complete successfully."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_running_job = Mock()
        mock_running_job.state.name = "JOB_STATE_RUNNING"

        mock_completed_job = Mock()
        mock_completed_job.name = "batches/batch-123"
        mock_completed_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_completed_job.dest = Mock()
        mock_completed_job.dest.inlined_responses = [
            Mock(response=Mock(text="Response 1"), error=None, key="request-0"),
            Mock(response=Mock(text="Response 2"), error=None, key="request-1"),
        ]

        mock_client.batches.get.side_effect = [mock_running_job, mock_completed_job]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider.wait_for_batch_job(
            "batches/batch-123",
            poll_interval=0.1,
        )

        assert isinstance(result, BatchJobResult)
        assert result.state == "JOB_STATE_SUCCEEDED"
        assert result.successful_requests == 2
        assert len(result.responses) == 2

    @patch("app.providers.google_provider.genai.Client")
    @patch("app.providers.google_provider.time.sleep")
    @patch("app.providers.google_provider.time.time")
    def test_wait_for_batch_job_timeout(
        self, mock_time, mock_sleep, mock_client_class, mock_openai_api_key
    ):
        """Test batch job timeout."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_running_job = Mock()
        mock_running_job.state.name = "JOB_STATE_RUNNING"
        mock_client.batches.get.return_value = mock_running_job

        mock_time.side_effect = [0, 0, 100, 200]

        provider = GoogleProvider(api_key=mock_openai_api_key)

        with pytest.raises(TimeoutError, match="did not complete within"):
            provider.wait_for_batch_job(
                "batches/batch-123",
                poll_interval=0.1,
                timeout=10.0,
            )

    @patch("app.providers.google_provider.genai.Client")
    def test_list_batch_jobs(self, mock_client_class, mock_openai_api_key):
        """Test listing batch jobs."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_job_1 = Mock()
        mock_job_1.name = "batches/batch-1"
        mock_job_1.state.name = "JOB_STATE_SUCCEEDED"

        mock_job_2 = Mock()
        mock_job_2.name = "batches/batch-2"
        mock_job_2.state.name = "JOB_STATE_RUNNING"

        mock_client.batches.list.return_value = iter([mock_job_1, mock_job_2])

        provider = GoogleProvider(api_key=mock_openai_api_key)
        jobs = provider.list_batch_jobs(limit=10)

        assert len(jobs) == 2
        assert jobs[0]["name"] == "batches/batch-1"
        assert jobs[1]["state"] == "JOB_STATE_RUNNING"

    @patch("app.providers.google_provider.genai.Client")
    def test_cancel_batch_job(self, mock_client_class, mock_openai_api_key):
        """Test cancelling a batch job."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)
        provider.cancel_batch_job("batches/batch-123")

        mock_client.batches.cancel.assert_called_once_with(name="batches/batch-123")

    @patch("app.providers.google_provider.genai.Client")
    def test_delete_batch_job(self, mock_client_class, mock_openai_api_key):
        """Test deleting a batch job."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)
        provider.delete_batch_job("batches/batch-123")

        mock_client.batches.delete.assert_called_once_with(name="batches/batch-123")

    @patch("app.providers.google_provider.genai.Client")
    def test_batch_job_with_errors(self, mock_client_class, mock_openai_api_key):
        """Test batch job result extraction with errors."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_completed_job = Mock()
        mock_completed_job.name = "batches/batch-123"
        mock_completed_job.state.name = "JOB_STATE_SUCCEEDED"
        mock_completed_job.dest = Mock()
        mock_completed_job.dest.inlined_responses = [
            Mock(response=Mock(text="Response 1"), error=None, key="request-0"),
            Mock(response=None, error="Rate limit exceeded", key="request-1"),
        ]

        provider = GoogleProvider(api_key=mock_openai_api_key)
        result = provider._extract_batch_results(mock_completed_job)

        assert result.successful_requests == 1
        assert result.failed_requests == 1
        assert len(result.errors) == 1
        assert "Rate limit exceeded" in result.errors[0]


class TestAsyncMethods:
    """Test suite for async methods."""

    @pytest.mark.asyncio
    @patch("app.providers.google_provider.genai.Client")
    async def test_generate_completion_async(
        self,
        mock_client_class,
        mock_openai_api_key,
        sample_prompt,
        mock_completion_response,
    ):
        """Test async text completion generation."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        mock_response = Mock()
        mock_response.text = mock_completion_response

        mock_client.aio.models.generate_content = MagicMock(return_value=mock_response)

        provider = GoogleProvider(api_key=mock_openai_api_key)

        async def mock_generate_content(*args, **kwargs):
            return mock_response

        mock_client.aio.models.generate_content = mock_generate_content

        result = await provider.generate_completion_async(
            sample_prompt, temperature=0.7, max_tokens=1000
        )

        assert result == mock_completion_response

    @pytest.mark.asyncio
    @patch("app.providers.google_provider.genai.Client")
    async def test_cleanup(self, mock_client_class, mock_openai_api_key):
        """Test cleanup method closes client."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        provider = GoogleProvider(api_key=mock_openai_api_key)
        await provider.cleanup()

        mock_client.close.assert_called_once()
