"""Tests for embedding_utils fallback behaviour."""

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.utils.embedding_utils import (
    FALLBACK_EMBEDDING_DIMENSION,
    _generate_embedding_google,
    _is_quota_error,
    generate_embedding_safe,
    generate_embedding_with_fallback,
)


# ---------------------------------------------------------------------------
# _is_quota_error
# ---------------------------------------------------------------------------


class TestIsQuotaError:
    def test_detects_429_in_message(self):
        assert _is_quota_error(Exception("HTTP 429 Too Many Requests"))

    def test_detects_insufficient_quota(self):
        assert _is_quota_error(Exception("Error: insufficient_quota exceeded"))

    def test_ignores_other_errors(self):
        assert not _is_quota_error(Exception("connection timeout"))

    def test_ignores_500_errors(self):
        assert not _is_quota_error(Exception("HTTP 500 Internal Server Error"))


# ---------------------------------------------------------------------------
# _generate_embedding_google
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingGoogle:
    def test_returns_numpy_array(self):
        vector = [0.1] * FALLBACK_EMBEDDING_DIMENSION

        embedding = MagicMock()
        embedding.values = vector
        embed_result = MagicMock()
        embed_result.embeddings = [embedding]

        mock_client = MagicMock()
        mock_client.models.embed_content.return_value = embed_result

        # Patch genai.Client at the google.genai module level (it is installed in venv)
        with patch("google.genai.Client", return_value=mock_client):
            result = _generate_embedding_google("test text", "fake-key")

        assert isinstance(result, np.ndarray)
        assert len(result) == FALLBACK_EMBEDDING_DIMENSION

    def test_raises_when_no_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            # Remove GOOGLE_API_KEY from env if present
            import os

            env_backup = os.environ.pop("GOOGLE_API_KEY", None)
            try:
                with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
                    _generate_embedding_google("text", google_api_key=None)
            finally:
                if env_backup is not None:
                    os.environ["GOOGLE_API_KEY"] = env_backup


# ---------------------------------------------------------------------------
# generate_embedding_with_fallback
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingWithFallback:
    def _openai_client(self) -> MagicMock:
        client = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.5] * 1536
        client.embeddings.create.return_value.data = [embedding_data]
        return client

    def test_uses_openai_on_success(self):
        client = self._openai_client()
        result = generate_embedding_with_fallback(client, "hello", google_api_key=None)
        assert len(result) == 1536
        client.embeddings.create.assert_called_once()

    def test_falls_back_to_google_on_429(self):
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("HTTP 429 insufficient_quota")

        fallback_vec = np.array([0.1] * FALLBACK_EMBEDDING_DIMENSION)

        with patch(
            "app.utils.embedding_utils._generate_embedding_google",
            return_value=fallback_vec,
        ) as mock_google:
            result = generate_embedding_with_fallback(
                client, "hello", google_api_key="fake-key"  # pragma: allowlist secret
            )

        mock_google.assert_called_once_with(
            "hello", "fake-key"
        )  # pragma: allowlist secret
        np.testing.assert_array_equal(result, fallback_vec)

    def test_propagates_non_quota_errors(self):
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("connection refused")

        with pytest.raises(Exception, match="connection refused"):
            generate_embedding_with_fallback(
                client, "hello", google_api_key="key"  # pragma: allowlist secret
            )


# ---------------------------------------------------------------------------
# generate_embedding_safe (fallback integration)
# ---------------------------------------------------------------------------


class TestGenerateEmbeddingSafeFallback:
    def test_returns_none_when_no_client(self):
        assert generate_embedding_safe(None, "text") is None

    def test_returns_embedding_on_success(self):
        client = MagicMock()
        embedding_data = MagicMock()
        embedding_data.embedding = [0.1] * 1536
        client.embeddings.create.return_value.data = [embedding_data]

        result = generate_embedding_safe(client, "text")
        assert result is not None
        assert len(result) == 1536

    def test_falls_back_to_google_on_quota_error(self):
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("429 insufficient_quota")

        fallback_vec = [0.2] * FALLBACK_EMBEDDING_DIMENSION

        with patch(
            "app.utils.embedding_utils._generate_embedding_google",
            return_value=np.array(fallback_vec),
        ) as mock_google:
            result = generate_embedding_safe(client, "text", google_api_key="gkey")

        mock_google.assert_called_once_with("text", "gkey")
        assert result == fallback_vec

    def test_returns_none_when_both_providers_fail(self):
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("429 insufficient_quota")

        with patch(
            "app.utils.embedding_utils._generate_embedding_google",
            side_effect=Exception("google also failed"),
        ):
            result = generate_embedding_safe(client, "text", google_api_key="gkey")

        assert result is None

    def test_returns_none_on_non_quota_error(self):
        client = MagicMock()
        client.embeddings.create.side_effect = Exception("network error")

        result = generate_embedding_safe(client, "text")
        assert result is None
