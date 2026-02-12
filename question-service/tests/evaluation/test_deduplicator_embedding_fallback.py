"""Integration tests for deduplicator embedding fallback scenarios.

Tests cover behavior when:
- OpenAI API fails during embedding generation
- Pre-computed embeddings are missing for some existing questions
- Mixed availability of pre-computed and on-demand embeddings
- Embedding cache errors during deduplication
"""

import numpy as np
import pytest
from unittest.mock import Mock, patch

from app.deduplicator import QuestionDeduplicator
from app.models import DifficultyLevel, GeneratedQuestion, QuestionType


@pytest.fixture
def sample_question():
    """Create a sample generated question."""
    return GeneratedQuestion(
        question_text="What is 3 + 5?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="8",
        answer_options=["6", "7", "8", "9"],
        explanation="3 + 5 = 8",
        metadata={},
        source_llm="openai",
        source_model="gpt-4",
    )


class TestEmbeddingGenerationFailure:
    """Tests for when OpenAI embedding API fails completely."""

    @patch("app.deduplicator.OpenAI")
    def test_semantic_check_raises_on_new_question_embedding_failure(
        self, mock_openai, sample_question
    ):
        """When embedding generation fails for the new question, the error propagates."""
        mock_openai.return_value.embeddings.create.side_effect = Exception(
            "OpenAI API rate limited"
        )

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        existing = [{"id": 1, "question_text": "What is 2 + 3?"}]

        with pytest.raises(Exception, match="OpenAI API rate limited"):
            deduplicator.check_duplicate(sample_question, existing)

    @patch("app.deduplicator.OpenAI")
    def test_batch_check_gracefully_handles_embedding_failure(
        self, mock_openai, sample_question
    ):
        """Batch check returns non-duplicate when embedding generation fails."""
        mock_openai.return_value.embeddings.create.side_effect = Exception(
            "API unavailable"
        )

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        existing = [{"id": 1, "question_text": "Different question entirely"}]

        results = deduplicator.check_duplicates_batch([sample_question], existing)

        # Should not crash; returns non-duplicate as fallback
        assert len(results) == 1
        assert results[0].is_duplicate is False


class TestPreComputedEmbeddingFallback:
    """Tests for mixed pre-computed and on-demand embedding scenarios."""

    @patch("app.deduplicator.OpenAI")
    def test_uses_precomputed_embedding_when_available(
        self, mock_openai, sample_question
    ):
        """Pre-computed embeddings should be used without additional API calls."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.5] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
            similarity_threshold=0.5,
        )

        # Existing question with different text (no exact match) but pre-computed embedding
        precomputed = [0.5] * 1536
        existing = [
            {
                "id": 1,
                "question_text": "A completely different question about addition",
                "question_embedding": precomputed,
            }
        ]

        deduplicator.check_duplicate(sample_question, existing)

        # API should only be called once (for the new question, not the existing one)
        assert mock_openai.return_value.embeddings.create.call_count == 1

    @patch("app.deduplicator.OpenAI")
    def test_falls_back_to_on_demand_when_no_precomputed(
        self, mock_openai, sample_question
    ):
        """Without pre-computed embedding, falls back to on-demand generation."""
        np.random.seed(42)
        vec1 = np.random.rand(1536)
        np.random.seed(43)
        vec2 = np.random.rand(1536)

        mock_response_new = Mock()
        mock_response_new.data = [Mock(embedding=vec1.tolist())]
        mock_response_existing = Mock()
        mock_response_existing.data = [Mock(embedding=vec2.tolist())]

        mock_openai.return_value.embeddings.create.side_effect = [
            mock_response_new,
            mock_response_existing,
        ]

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        existing = [
            {"id": 1, "question_text": "Completely different question"}
            # No question_embedding field
        ]

        deduplicator.check_duplicate(sample_question, existing)

        # API should be called twice: once for new question, once for existing
        assert mock_openai.return_value.embeddings.create.call_count == 2

    @patch("app.deduplicator.OpenAI")
    def test_mixed_precomputed_and_missing_embeddings(
        self, mock_openai, sample_question
    ):
        """Questions with and without pre-computed embeddings in same batch."""
        call_count = [0]

        def mock_create(input, model, timeout=None):
            call_count[0] += 1
            np.random.seed(call_count[0] * 100)
            mock_resp = Mock()
            mock_resp.data = [Mock(embedding=np.random.rand(1536).tolist())]
            return mock_resp

        mock_openai.return_value.embeddings.create.side_effect = mock_create

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        existing = [
            {
                "id": 1,
                "question_text": "Question with embedding",
                "question_embedding": np.random.rand(1536).tolist(),
            },
            {
                "id": 2,
                "question_text": "Question without embedding",
                # No question_embedding field
            },
            {
                "id": 3,
                "question_text": "Another with embedding",
                "question_embedding": np.random.rand(1536).tolist(),
            },
        ]

        deduplicator.check_duplicate(sample_question, existing)

        # 1 call for new question + 1 call for existing[1] (missing embedding)
        # existing[0] and existing[2] use pre-computed, no API call
        assert call_count[0] == 2

    @patch("app.deduplicator.OpenAI")
    def test_empty_precomputed_embedding_triggers_fallback(
        self, mock_openai, sample_question
    ):
        """Empty list as pre-computed embedding should fall back to on-demand."""
        call_count = [0]

        def mock_create(input, model, timeout=None):
            call_count[0] += 1
            np.random.seed(call_count[0])
            mock_resp = Mock()
            mock_resp.data = [Mock(embedding=np.random.rand(1536).tolist())]
            return mock_resp

        mock_openai.return_value.embeddings.create.side_effect = mock_create

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        existing = [
            {
                "id": 1,
                "question_text": "Question with empty embedding",
                "question_embedding": [],  # Empty
            }
        ]

        deduplicator.check_duplicate(sample_question, existing)

        # Empty list is falsy, so falls back to on-demand: 1 new + 1 existing = 2
        assert call_count[0] == 2


class TestCacheInteractionDuringDedup:
    """Tests for cache behavior during deduplication."""

    @patch("app.deduplicator.OpenAI")
    def test_cache_hit_prevents_api_call_for_repeated_texts(self, mock_openai):
        """Cache should prevent re-generating embeddings for the same text."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        # Same text appears in multiple existing questions
        existing = [
            {"id": 1, "question_text": "Duplicate text"},
            {"id": 2, "question_text": "Duplicate text"},
        ]

        question = GeneratedQuestion(
            question_text="New question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            explanation="Explanation",
            metadata={},
            source_llm="openai",
            source_model="gpt-4",
        )

        deduplicator.check_duplicate(question, existing)

        # 1 for new question + 1 for "Duplicate text" (cached for second occurrence)
        assert mock_openai.return_value.embeddings.create.call_count == 2

    @patch("app.deduplicator.OpenAI")
    def test_clear_cache_forces_regenration(self, mock_openai):
        """After clearing cache, same text should generate a new API call."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",  # pragma: allowlist secret
        )

        deduplicator._get_embedding("test text")
        assert mock_openai.return_value.embeddings.create.call_count == 1

        deduplicator.clear_cache()

        deduplicator._get_embedding("test text")
        assert mock_openai.return_value.embeddings.create.call_count == 2
