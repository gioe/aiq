"""Question deduplication checking.

This module provides functionality to detect duplicate questions using both
exact match checking and semantic similarity analysis via embeddings.

TASK-629: Added Redis caching support via HybridEmbeddingCache for distributed
embedding caching across workers, with automatic fallback to in-memory caching.
"""

import hashlib
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
from openai import OpenAI

from app.infrastructure.embedding_cache import HybridEmbeddingCache
from app.utils.embedding_utils import generate_embedding
from app.data.models import GeneratedQuestion

# Import observability facade for distributed tracing
try:
    from libs.observability import observability
except ImportError:
    # Fallback for environments where libs.observability isn't installed as a package
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))
    from libs.observability import observability  # noqa: E402

logger = logging.getLogger(__name__)


class EmbeddingCache:
    """In-memory cache for text embeddings with hash-based keys.

    Uses SHA-256 hash of normalized text as cache key to efficiently store
    and retrieve embeddings. This reduces API calls from O(n*m) to O(n+m)
    when checking n new questions against m existing questions.

    Cache Invalidation Strategy:
    - The cache is instance-scoped, so it is automatically cleared when
      the QuestionDeduplicator instance is garbage collected
    - For long-running processes, call clear() periodically or create
      a new QuestionDeduplicator instance
    - The cache has no TTL as embeddings are deterministic for a given
      model - the same text always produces the same embedding
    """

    def __init__(self) -> None:
        """Initialize empty embedding cache."""
        self._cache: Dict[str, np.ndarray] = {}
        self._hits = 0
        self._misses = 0

    def _normalize_text(self, text: str) -> str:
        """Normalize text for consistent cache keys.

        Args:
            text: Raw text to normalize

        Returns:
            Normalized text (stripped and lowercased)
        """
        return text.strip().lower()

    def _compute_key(self, text: str, model: str) -> str:
        """Compute SHA-256 hash key for text and model combination.

        Args:
            text: Text to hash (will be normalized first)
            model: Embedding model name to include in key

        Returns:
            Hex digest of SHA-256 hash
        """
        normalized = self._normalize_text(text)
        key_input = f"{model}:{normalized}"
        return hashlib.sha256(key_input.encode("utf-8")).hexdigest()

    def get(self, text: str, model: str) -> Optional[np.ndarray]:
        """Get cached embedding for text if available.

        Args:
            text: Text to look up
            model: Embedding model name used for generation

        Returns:
            Cached embedding array or None if not found
        """
        key = self._compute_key(text, model)
        embedding = self._cache.get(key)
        if embedding is not None:
            self._hits += 1
            logger.debug(f"Cache hit for text hash {key[:8]}...")
        else:
            self._misses += 1
            logger.debug(f"Cache miss for text hash {key[:8]}...")
        return embedding

    def set(self, text: str, model: str, embedding: np.ndarray) -> None:
        """Store embedding in cache.

        Args:
            text: Text that was embedded
            model: Embedding model name used for generation
            embedding: Embedding vector to cache
        """
        key = self._compute_key(text, model)
        self._cache[key] = embedding
        logger.debug(f"Cached embedding for text hash {key[:8]}...")

    def clear(self) -> None:
        """Clear all cached embeddings."""
        count = len(self._cache)
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        logger.info(f"Cleared {count} cached embeddings")

    @property
    def size(self) -> int:
        """Return number of cached embeddings."""
        return len(self._cache)

    @property
    def stats(self) -> Dict[str, int]:
        """Return cache statistics.

        Returns:
            Dictionary with size, hits, and misses counts
        """
        return {
            "size": self.size,
            "hits": self._hits,
            "misses": self._misses,
        }


class DuplicateCheckResult:
    """Result of a duplicate check operation.

    Attributes:
        is_duplicate: Whether the question is a duplicate
        duplicate_type: Type of duplicate ("exact" or "semantic")
        similarity_score: Similarity score (1.0 for exact, 0.0-1.0 for semantic)
        matched_question: The matched question data if duplicate found
    """

    def __init__(
        self,
        is_duplicate: bool,
        duplicate_type: Optional[str] = None,
        similarity_score: float = 0.0,
        matched_question: Optional[Dict[str, Any]] = None,
    ):
        """Initialize duplicate check result.

        Args:
            is_duplicate: Whether question is a duplicate
            duplicate_type: Type of duplicate detection
            similarity_score: Similarity score
            matched_question: Matched question data
        """
        self.is_duplicate = is_duplicate
        self.duplicate_type = duplicate_type
        self.similarity_score = similarity_score
        self.matched_question = matched_question

    def __repr__(self) -> str:
        """String representation of result."""
        if not self.is_duplicate:
            return "DuplicateCheckResult(is_duplicate=False)"
        return (
            f"DuplicateCheckResult(is_duplicate=True, type={self.duplicate_type}, "
            f"score={self.similarity_score:.3f})"
        )


class QuestionDeduplicator:
    """Checks for duplicate questions using exact and semantic matching.

    This class provides methods to detect duplicate questions by comparing
    question text using both exact string matching and semantic similarity
    via embeddings.

    TASK-629: Updated to support Redis-backed embedding cache via HybridEmbeddingCache.
    When redis_url is provided, embeddings are cached in Redis for distributed access
    across workers. Falls back to in-memory caching when Redis is unavailable.
    """

    def __init__(
        self,
        openai_api_key: str,
        similarity_threshold: float = 0.98,
        embedding_model: str = "text-embedding-3-small",
        embedding_cache: Optional[Union[EmbeddingCache, HybridEmbeddingCache]] = None,
        redis_url: Optional[str] = None,
        embedding_cache_ttl: Optional[int] = None,
    ):
        """Initialize the question deduplicator.

        Args:
            openai_api_key: OpenAI API key for embeddings
            similarity_threshold: Threshold for semantic similarity (0.0-1.0)
            embedding_model: OpenAI embedding model to use
            embedding_cache: Optional pre-configured embedding cache. If provided,
                            redis_url and embedding_cache_ttl are ignored.
            redis_url: Redis connection URL for distributed caching. If None and
                      embedding_cache is None, uses in-memory cache.
            embedding_cache_ttl: TTL for cached embeddings in seconds (None = no expiration)

        Raises:
            ValueError: If similarity_threshold is not between 0 and 1
        """
        if not 0.0 <= similarity_threshold <= 1.0:
            raise ValueError(
                f"similarity_threshold must be between 0.0 and 1.0, got {similarity_threshold}"
            )

        self.openai_client = OpenAI(api_key=openai_api_key)
        self.similarity_threshold = similarity_threshold
        self.embedding_model = embedding_model

        # TASK-629: Support external cache injection or create HybridEmbeddingCache
        if embedding_cache is not None:
            self._embedding_cache: Union[EmbeddingCache, HybridEmbeddingCache] = (
                embedding_cache
            )
            cache_type = (
                "hybrid (Redis)"
                if isinstance(embedding_cache, HybridEmbeddingCache)
                and embedding_cache.using_redis
                else "in-memory"
            )
        else:
            # Create HybridEmbeddingCache which handles Redis/in-memory fallback
            self._embedding_cache = HybridEmbeddingCache(
                redis_url=redis_url,
                default_ttl=embedding_cache_ttl,
            )
            cache_type = "Redis" if self._embedding_cache.using_redis else "in-memory"

        logger.info(
            f"QuestionDeduplicator initialized with threshold={similarity_threshold}, "
            f"model={embedding_model}, cache={cache_type}"
        )

    def check_duplicate(
        self,
        question: GeneratedQuestion,
        existing_questions: List[Dict[str, Any]],
    ) -> DuplicateCheckResult:
        """Check if a question is a duplicate of any existing questions.

        Args:
            question: Generated question to check
            existing_questions: List of existing question data dictionaries
                               Each should have 'question_text' key

        Returns:
            DuplicateCheckResult with duplicate status and details

        Raises:
            Exception: If embedding generation fails
        """
        with observability.start_span(
            "deduplicator.check_duplicate",
            attributes={
                "question_type": question.question_type.value,
                "existing_count": len(existing_questions),
            },
        ) as span:
            question_text = question.question_text.strip().lower()

            # Step 1: Check for exact match (case-insensitive)
            for existing in existing_questions:
                existing_text = existing.get("question_text", "").strip().lower()
                if question_text == existing_text:
                    span.set_attribute("is_duplicate", True)
                    span.set_attribute("duplicate_type", "exact")
                    logger.info(f"Exact duplicate found for: {question_text[:50]}...")
                    return DuplicateCheckResult(
                        is_duplicate=True,
                        duplicate_type="exact",
                        similarity_score=1.0,
                        matched_question=existing,
                    )

            # Step 2: Check for semantic similarity using embeddings
            if len(existing_questions) > 0:
                result = self._check_semantic_similarity(
                    question_text, existing_questions
                )
                if result.is_duplicate:
                    span.set_attribute("is_duplicate", True)
                    span.set_attribute("duplicate_type", "semantic")
                    span.set_attribute("similarity_score", result.similarity_score)
                    logger.info(
                        f"Semantic duplicate found with score {result.similarity_score:.3f}"
                    )
                    return result

            # No duplicate found
            span.set_attribute("is_duplicate", False)
            logger.debug(f"No duplicate found for: {question_text[:50]}...")
            return DuplicateCheckResult(is_duplicate=False)

    def check_duplicates_batch(
        self,
        questions: List[GeneratedQuestion],
        existing_questions: List[Dict[str, Any]],
    ) -> List[DuplicateCheckResult]:
        """Check multiple questions for duplicates.

        Args:
            questions: List of generated questions to check
            existing_questions: List of existing question data

        Returns:
            List of DuplicateCheckResult, one per input question

        Raises:
            Exception: If any check fails
        """
        logger.info(f"Checking {len(questions)} questions for duplicates")

        results = []
        for question in questions:
            try:
                result = self.check_duplicate(question, existing_questions)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to check duplicate for question: {str(e)}")
                # Return non-duplicate result to be safe (don't block question)
                results.append(DuplicateCheckResult(is_duplicate=False))

        duplicates_found = sum(1 for r in results if r.is_duplicate)
        logger.info(
            f"Duplicate check complete: {duplicates_found}/{len(questions)} duplicates found"
        )

        return results

    def _check_semantic_similarity(
        self,
        question_text: str,
        existing_questions: List[Dict[str, Any]],
    ) -> DuplicateCheckResult:
        """Check semantic similarity using embeddings.

        TASK-433: Updated to use pre-computed embeddings when available.
        Falls back to on-demand computation for questions without embeddings.

        Args:
            question_text: Question text to check
            existing_questions: List of existing question data (may include
                              'question_embedding' field with pre-computed vectors)

        Returns:
            DuplicateCheckResult with semantic similarity details

        Raises:
            Exception: If embedding generation fails
        """
        try:
            # Generate embedding for new question
            new_embedding = self._get_embedding(question_text)

            # Compare with existing questions
            max_similarity = 0.0
            most_similar_question = None

            for existing in existing_questions:
                existing_text = existing.get("question_text", "")
                if not existing_text:
                    continue

                # TASK-433: Use pre-computed embedding if available
                # This eliminates API calls for existing questions, dramatically
                # improving performance as the question pool grows.
                existing_embedding_data = existing.get("question_embedding")

                if existing_embedding_data:
                    # Use pre-computed embedding from database
                    existing_embedding = np.array(existing_embedding_data)
                    logger.debug(
                        f"Using pre-computed embedding for question {existing.get('id', 'unknown')}"
                    )
                else:
                    # Fall back to on-demand generation for questions without embeddings
                    # (e.g., questions created before TASK-433 was implemented)
                    existing_embedding = self._get_embedding(existing_text)
                    logger.debug(
                        f"Computing embedding on-demand for question {existing.get('id', 'unknown')} "
                        "(missing pre-computed embedding)"
                    )

                # Calculate cosine similarity
                similarity = self._cosine_similarity(new_embedding, existing_embedding)

                if similarity > max_similarity:
                    max_similarity = similarity
                    most_similar_question = existing

            # Check if similarity exceeds threshold
            if max_similarity >= self.similarity_threshold:
                return DuplicateCheckResult(
                    is_duplicate=True,
                    duplicate_type="semantic",
                    similarity_score=max_similarity,
                    matched_question=most_similar_question,
                )

            return DuplicateCheckResult(is_duplicate=False)

        except Exception as e:
            logger.error(f"Semantic similarity check failed: {str(e)}")
            raise

    def _get_embedding(self, text: str) -> np.ndarray:
        """Generate embedding vector for text using OpenAI API with caching.

        Uses the embedding cache to avoid redundant API calls for the same text.
        Cache keys are SHA-256 hashes of normalized (stripped, lowercased) text
        scoped by model name.

        Args:
            text: Text to generate embedding for

        Returns:
            Numpy array containing embedding vector

        Raises:
            Exception: If API call fails
        """
        cached = self._embedding_cache.get(text, self.embedding_model)
        if cached is not None:
            return cached

        try:
            embedding_array = generate_embedding(
                self.openai_client, text, self.embedding_model
            )
            self._embedding_cache.set(text, self.embedding_model, embedding_array)
            return embedding_array

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise

    def _cosine_similarity(self, vector1: np.ndarray, vector2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors.

        Args:
            vector1: First embedding vector
            vector2: Second embedding vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        # Normalize vectors
        norm1 = np.linalg.norm(vector1)
        norm2 = np.linalg.norm(vector2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Calculate cosine similarity
        similarity = np.dot(vector1, vector2) / (norm1 * norm2)

        # Clamp to [0, 1] range (cosine similarity is [-1, 1], but we expect [0, 1])
        return float(max(0.0, min(1.0, similarity)))

    def filter_duplicates(
        self,
        questions: List[GeneratedQuestion],
        existing_questions: List[Dict[str, Any]],
    ) -> Tuple[
        List[GeneratedQuestion], List[Tuple[GeneratedQuestion, DuplicateCheckResult]]
    ]:
        """Filter out duplicate questions from a list.

        Args:
            questions: List of generated questions to filter
            existing_questions: List of existing question data

        Returns:
            Tuple of (unique_questions, duplicate_questions_with_results)

        Raises:
            Exception: If duplicate checking fails
        """
        with observability.start_span(
            "deduplicator.filter_duplicates",
            attributes={
                "questions_count": len(questions),
                "existing_count": len(existing_questions),
            },
        ) as span:
            logger.info(f"Filtering duplicates from {len(questions)} questions")

            unique_questions = []
            duplicates = []

            for question in questions:
                result = self.check_duplicate(question, existing_questions)

                if result.is_duplicate:
                    duplicates.append((question, result))
                else:
                    unique_questions.append(question)

            span.set_attribute("unique_count", len(unique_questions))
            span.set_attribute("duplicate_count", len(duplicates))
            logger.info(
                f"Filtering complete: {len(unique_questions)} unique, "
                f"{len(duplicates)} duplicates"
            )

            return unique_questions, duplicates

    def get_stats(self) -> Dict[str, Any]:
        """Get deduplicator configuration and cache statistics.

        Returns:
            Dictionary with configuration and cache information
        """
        # Handle both EmbeddingCache (stats property) and HybridEmbeddingCache (get_stats method)
        if hasattr(self._embedding_cache, "get_stats"):
            cache_stats = self._embedding_cache.get_stats()
        else:
            cache_stats = self._embedding_cache.stats

        return {
            "similarity_threshold": self.similarity_threshold,
            "embedding_model": self.embedding_model,
            "cache": cache_stats,
        }

    def clear_cache(self) -> None:
        """Clear the embedding cache.

        Useful for long-running processes or when memory needs to be freed.
        """
        self._embedding_cache.clear()

    @property
    def using_redis_cache(self) -> bool:
        """Return whether Redis is being used for embedding cache.

        Returns:
            True if Redis cache is active, False if using in-memory cache
        """
        if hasattr(self._embedding_cache, "using_redis"):
            return self._embedding_cache.using_redis
        return False

    def close(self) -> None:
        """Close cache connections and release resources."""
        if hasattr(self._embedding_cache, "close"):
            self._embedding_cache.close()
