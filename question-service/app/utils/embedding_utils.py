"""Shared embedding generation utilities.

Provides a single entry point for generating text embeddings via the
OpenAI API, with support for both single and batch generation.
"""

import logging
from typing import List, Optional

import numpy as np
from openai import OpenAI

logger = logging.getLogger(__name__)

# Default embedding configuration
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
DEFAULT_EMBEDDING_DIMENSION = 1536


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
) -> Optional[List[float]]:
    """Generate embedding with graceful failure for database insertion.

    Returns None instead of raising on failure, allowing the caller to
    proceed without an embedding (e.g., for database insertion where
    the embedding can be backfilled later).

    Args:
        client: OpenAI client, or None if not configured
        text: Text to generate embedding for
        model: Embedding model name

    Returns:
        List of floats representing the embedding, or None on failure
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

    except Exception as e:
        logger.debug(f"Failed to generate embedding: {str(e)}")
        return None
