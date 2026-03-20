"""Shared embedding generation utilities.

Provides a single entry point for generating text embeddings via the
OpenAI API, with automatic fallback to Google text-embedding-004 when
OpenAI quota is exhausted (HTTP 429 / insufficient_quota errors).
"""

import logging
import os
from typing import List, Optional

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

# Default embedding configuration
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSION = 1536

# Fallback provider (Google) configuration
FALLBACK_EMBEDDING_MODEL = "text-embedding-004"
FALLBACK_EMBEDDING_DIMENSION = 768


def _is_quota_error(e: Exception) -> bool:
    """Return True if the exception indicates an OpenAI quota/rate-limit failure."""
    error_str = str(e)
    return "429" in error_str or "insufficient_quota" in error_str.lower()


def _generate_embedding_google(
    text: str, google_api_key: Optional[str] = None
) -> np.ndarray:
    """Generate an embedding using Google's text-embedding-004 model.

    Args:
        text: Text to embed.
        google_api_key: Google API key. Falls back to the GOOGLE_API_KEY env var.

    Returns:
        Numpy array with 768 float values.

    Raises:
        RuntimeError: If no Google API key is available.
        Exception: If the Google API call fails.
    """
    api_key = google_api_key or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError(
            "No GOOGLE_API_KEY available for fallback embedding generation"
        )

    from google import genai  # local import to avoid hard dependency at module load

    client = genai.Client(api_key=api_key)
    result = client.models.embed_content(
        model=FALLBACK_EMBEDDING_MODEL,
        contents=text,
    )
    if not result.embeddings:
        raise RuntimeError("Google embed_content returned no embeddings")
    return np.array(result.embeddings[0].values)


def generate_embedding_with_fallback(
    openai_client: OpenAI,
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    google_api_key: Optional[str] = None,
    timeout: float = 30.0,
) -> np.ndarray:
    """Generate an embedding, falling back to Google on OpenAI quota errors.

    Tries OpenAI first. If a 429 / quota error is returned, logs a warning and
    attempts Google text-embedding-004 instead.  The returned vector may have a
    different dimensionality (768 vs 1536) when the fallback is used — callers
    that compare embeddings across providers must handle this.

    Args:
        openai_client: Configured OpenAI client.
        text: Text to embed.
        model: OpenAI embedding model name.
        google_api_key: Google API key for the fallback provider.
        timeout: Request timeout in seconds.

    Returns:
        Numpy array containing the embedding vector.

    Raises:
        Exception: If both providers fail.
    """
    try:
        return generate_embedding(openai_client, text, model, timeout)
    except Exception as e:
        if not _is_quota_error(e):
            raise
        logger.warning(
            f"OpenAI embedding failed with quota error ({e}); "
            "falling back to Google text-embedding-004"
        )

    return _generate_embedding_google(text, google_api_key)


def generate_embedding(
    client: OpenAI,
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    timeout: float = 30.0,
) -> np.ndarray:
    """Generate an embedding vector for a single text.

    Args:
        client: Configured OpenAI client
        text: Text to generate embedding for
        model: Embedding model name
        timeout: Request timeout in seconds

    Returns:
        Numpy array containing the embedding vector

    Raises:
        Exception: If the API call fails
    """
    response = client.embeddings.create(
        input=text,
        model=model,
        timeout=timeout,
    )
    return np.array(response.data[0].embedding)


def generate_embeddings_batch(
    client: OpenAI,
    texts: List[str],
    model: str = DEFAULT_EMBEDDING_MODEL,
    timeout: float = 60.0,
) -> List[np.ndarray]:
    """Generate embedding vectors for multiple texts in a single API call.

    The OpenAI embeddings API accepts a list of inputs, which is more efficient
    than making separate calls for each text.

    Args:
        client: Configured OpenAI client
        texts: List of texts to generate embeddings for
        model: Embedding model name
        timeout: Request timeout in seconds

    Returns:
        List of numpy arrays, one per input text, in the same order

    Raises:
        ValueError: If texts list is empty
        Exception: If the API call fails
    """
    if not texts:
        raise ValueError("texts list cannot be empty")

    response = client.embeddings.create(
        input=texts,
        model=model,
        timeout=timeout,
    )
    # Response data is sorted by index, but sort explicitly to be safe
    sorted_data = sorted(response.data, key=lambda d: d.index)
    return [np.array(d.embedding) for d in sorted_data]


def generate_embedding_safe(
    client: Optional[OpenAI],
    text: str,
    model: str = DEFAULT_EMBEDDING_MODEL,
    google_api_key: Optional[str] = None,
) -> Optional[List[float]]:
    """Generate embedding with graceful failure for database insertion.

    Returns None instead of raising on failure, allowing the caller to
    proceed without an embedding (e.g., for database insertion where
    the embedding can be backfilled later).

    When OpenAI returns a quota/rate-limit error (429 / insufficient_quota),
    automatically retries with Google text-embedding-004 so questions are
    not inserted without embeddings due to transient quota exhaustion.

    Args:
        client: OpenAI client, or None if not configured.
        text: Text to generate embedding for.
        model: OpenAI embedding model name.
        google_api_key: Google API key used for the fallback provider.

    Returns:
        List of floats representing the embedding, or None on failure.
    """
    if not client:
        logger.debug("Skipping embedding generation - OpenAI client not configured")
        return None

    try:
        response = client.embeddings.create(
            input=text,
            model=model,
        )
        embedding = response.data[0].embedding

        if len(embedding) != DEFAULT_EMBEDDING_DIMENSION:
            logger.warning(
                f"Expected {DEFAULT_EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
            )

        logger.debug(f"Generated embedding for text: {text[:50]}...")
        return embedding

    except Exception as primary_error:
        if _is_quota_error(primary_error):
            logger.warning(
                f"OpenAI embedding quota exhausted ({primary_error}); "
                "attempting fallback to Google text-embedding-004"
            )
            try:
                fallback_embedding = _generate_embedding_google(text, google_api_key)
                logger.info(
                    f"Fallback embedding generated via Google "
                    f"({len(fallback_embedding)}-dim) for text: {text[:50]}..."
                )
                return fallback_embedding.tolist()
            except Exception as fallback_error:
                logger.error(f"Fallback embedding also failed: {fallback_error}")
                return None

        logger.debug(f"Failed to generate embedding: {primary_error}")
        return None
