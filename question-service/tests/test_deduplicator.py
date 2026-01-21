"""Tests for question deduplication functionality."""

import numpy as np
import pytest
from unittest.mock import Mock, patch

from app.deduplicator import DuplicateCheckResult, EmbeddingCache, QuestionDeduplicator
from app.models import DifficultyLevel, GeneratedQuestion, QuestionType


@pytest.fixture
def sample_question():
    """Create a sample generated question for testing."""
    return GeneratedQuestion(
        question_text="What is 2 + 2?",
        question_type=QuestionType.MATH,
        difficulty_level=DifficultyLevel.EASY,
        correct_answer="4",
        answer_options=["2", "3", "4", "5"],
        explanation="2 + 2 equals 4 by basic addition",
        metadata={},
        source_llm="openai",
        source_model="gpt-4",
    )


@pytest.fixture
def sample_existing_questions():
    """Create sample existing questions for testing."""
    return [
        {
            "id": 1,
            "question_text": "What is the capital of France?",
            "question_type": "verbal_reasoning",
        },
        {
            "id": 2,
            "question_text": "If x + 3 = 7, what is x?",
            "question_type": "mathematical",
        },
        {
            "id": 3,
            "question_text": "Complete the pattern: 2, 4, 8, 16, ?",
            "question_type": "pattern_recognition",
        },
    ]


class TestDuplicateCheckResult:
    """Tests for DuplicateCheckResult class."""

    def test_initialization_not_duplicate(self):
        """Test initialization for non-duplicate result."""
        result = DuplicateCheckResult(is_duplicate=False)

        assert result.is_duplicate is False
        assert result.duplicate_type is None
        assert result.similarity_score == pytest.approx(0.0)
        assert result.matched_question is None

    def test_initialization_duplicate(self):
        """Test initialization for duplicate result."""
        matched = {"id": 1, "question_text": "Test question"}
        result = DuplicateCheckResult(
            is_duplicate=True,
            duplicate_type="exact",
            similarity_score=1.0,
            matched_question=matched,
        )

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"
        assert result.similarity_score == pytest.approx(1.0)
        assert result.matched_question == matched

    def test_repr_not_duplicate(self):
        """Test string representation for non-duplicate."""
        result = DuplicateCheckResult(is_duplicate=False)
        assert "is_duplicate=False" in repr(result)

    def test_repr_duplicate(self):
        """Test string representation for duplicate."""
        result = DuplicateCheckResult(
            is_duplicate=True,
            duplicate_type="semantic",
            similarity_score=0.92,
        )
        representation = repr(result)
        assert "is_duplicate=True" in representation
        assert "semantic" in representation
        assert "0.92" in representation


class TestQuestionDeduplicator:
    """Tests for QuestionDeduplicator class."""

    @patch("app.deduplicator.OpenAI")
    def test_initialization_valid_threshold(self, mock_openai):
        """Test initialization with valid threshold."""
        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",
            similarity_threshold=0.85,
        )

        assert deduplicator.similarity_threshold == pytest.approx(0.85)
        assert deduplicator.embedding_model == "text-embedding-3-small"

    @patch("app.deduplicator.OpenAI")
    def test_initialization_invalid_threshold_too_high(self, mock_openai):
        """Test initialization with threshold > 1.0."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            QuestionDeduplicator(
                openai_api_key="test-key",
                similarity_threshold=1.5,
            )

    @patch("app.deduplicator.OpenAI")
    def test_initialization_invalid_threshold_negative(self, mock_openai):
        """Test initialization with negative threshold."""
        with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
            QuestionDeduplicator(
                openai_api_key="test-key",
                similarity_threshold=-0.1,
            )

    @patch("app.deduplicator.OpenAI")
    def test_initialization_custom_model(self, mock_openai):
        """Test initialization with custom embedding model."""
        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",
            embedding_model="text-embedding-ada-002",
        )

        assert deduplicator.embedding_model == "text-embedding-ada-002"

    @patch("app.deduplicator.OpenAI")
    def test_check_duplicate_exact_match(
        self, mock_openai, sample_question, sample_existing_questions
    ):
        """Test exact duplicate detection."""
        # Add exact match to existing questions
        existing_with_duplicate = sample_existing_questions + [
            {"id": 4, "question_text": "What is 2 + 2?"}
        ]

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")
        result = deduplicator.check_duplicate(sample_question, existing_with_duplicate)

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"
        assert result.similarity_score == pytest.approx(1.0)
        assert result.matched_question["id"] == 4

    @patch("app.deduplicator.OpenAI")
    def test_check_duplicate_exact_match_case_insensitive(
        self, mock_openai, sample_question, sample_existing_questions
    ):
        """Test exact match is case-insensitive."""
        # Add case-variant to existing questions
        existing_with_duplicate = sample_existing_questions + [
            {"id": 4, "question_text": "WHAT IS 2 + 2?"}
        ]

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")
        result = deduplicator.check_duplicate(sample_question, existing_with_duplicate)

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"

    @patch("app.deduplicator.OpenAI")
    def test_check_duplicate_no_match(
        self, mock_openai, sample_question, sample_existing_questions
    ):
        """Test when no duplicate found."""
        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Mock embedding generation to return orthogonal vectors (low similarity)
        # Use different random vectors with specific seeds for reproducibility
        np.random.seed(42)
        vec_new = np.random.rand(1536)
        np.random.seed(123)
        vec1 = np.random.rand(1536)
        np.random.seed(456)
        vec2 = np.random.rand(1536)
        np.random.seed(789)
        vec3 = np.random.rand(1536)

        deduplicator._get_embedding = Mock(side_effect=[vec_new, vec1, vec2, vec3])

        result = deduplicator.check_duplicate(
            sample_question, sample_existing_questions
        )

        assert result.is_duplicate is False

    @patch("app.deduplicator.OpenAI")
    def test_check_duplicate_semantic_match(
        self, mock_openai, sample_question, sample_existing_questions
    ):
        """Test semantic duplicate detection."""
        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",
            similarity_threshold=0.85,
        )

        # Mock embedding generation to return similar vectors
        base_vector = np.random.rand(1536)
        similar_vector = base_vector + np.random.rand(1536) * 0.1  # Very similar

        deduplicator._get_embedding = Mock(
            side_effect=[
                base_vector,  # New question
                np.random.rand(1536),  # Existing 1 (different)
                np.random.rand(1536),  # Existing 2 (different)
                similar_vector,  # Existing 3 (similar)
            ]
        )

        result = deduplicator.check_duplicate(
            sample_question, sample_existing_questions
        )

        assert result.is_duplicate is True
        assert result.duplicate_type == "semantic"
        assert result.similarity_score >= 0.85

    @patch("app.deduplicator.OpenAI")
    def test_check_duplicate_empty_existing_list(self, mock_openai, sample_question):
        """Test check with empty existing questions list."""
        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        result = deduplicator.check_duplicate(sample_question, [])

        assert result.is_duplicate is False

    @patch("app.deduplicator.OpenAI")
    def test_check_duplicates_batch(self, mock_openai, sample_existing_questions):
        """Test batch duplicate checking."""
        questions = [
            GeneratedQuestion(
                question_text="New question 1",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="4",
                answer_options=["2", "3", "4", "5"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
            GeneratedQuestion(
                question_text="What is the capital of France?",  # Exact duplicate
                question_type=QuestionType.VERBAL,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="Paris",
                answer_options=["London", "Paris", "Berlin", "Rome"],
                explanation="Paris is the capital of France",
                source_llm="openai",
                source_model="gpt-4",
            ),
            GeneratedQuestion(
                question_text="New question 3",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="true",
                answer_options=["true", "false"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
        ]

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Mock embeddings to ensure no semantic matches for non-exact duplicates
        # Generate different random vectors for each question
        def get_mock_embedding(seed):
            np.random.seed(seed)
            return np.random.rand(1536)

        deduplicator._get_embedding = Mock(
            side_effect=[get_mock_embedding(i) for i in range(100, 120)]
        )

        results = deduplicator.check_duplicates_batch(
            questions, sample_existing_questions
        )

        assert len(results) == 3
        assert results[0].is_duplicate is False  # New question
        assert results[1].is_duplicate is True  # Exact duplicate
        assert results[1].duplicate_type == "exact"
        assert results[2].is_duplicate is False  # New question

    @patch("app.deduplicator.OpenAI")
    def test_cosine_similarity(self, mock_openai):
        """Test cosine similarity calculation."""
        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Test identical vectors
        vec1 = np.array([1.0, 2.0, 3.0])
        similarity = deduplicator._cosine_similarity(vec1, vec1)
        assert pytest.approx(similarity, abs=0.01) == 1.0

        # Test orthogonal vectors
        vec2 = np.array([1.0, 0.0, 0.0])
        vec3 = np.array([0.0, 1.0, 0.0])
        similarity = deduplicator._cosine_similarity(vec2, vec3)
        assert pytest.approx(similarity, abs=0.01) == 0.0

        # Test similar vectors
        vec4 = np.array([1.0, 1.0, 1.0])
        vec5 = np.array([1.1, 0.9, 1.0])
        similarity = deduplicator._cosine_similarity(vec4, vec5)
        assert 0.9 < similarity < 1.0

    @patch("app.deduplicator.OpenAI")
    def test_cosine_similarity_zero_vectors(self, mock_openai):
        """Test cosine similarity with zero vectors."""
        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        vec1 = np.array([0.0, 0.0, 0.0])
        vec2 = np.array([1.0, 2.0, 3.0])

        similarity = deduplicator._cosine_similarity(vec1, vec2)
        assert similarity == pytest.approx(0.0)

    @patch("app.deduplicator.OpenAI")
    def test_get_embedding_success(self, mock_openai):
        """Test successful embedding generation."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")
        embedding = deduplicator._get_embedding("Test question")

        assert isinstance(embedding, np.ndarray)
        assert len(embedding) == 1536
        assert all(v == pytest.approx(0.1) for v in embedding)

    @patch("app.deduplicator.OpenAI")
    def test_get_embedding_failure(self, mock_openai):
        """Test embedding generation failure."""
        mock_openai.return_value.embeddings.create.side_effect = Exception("API error")

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        with pytest.raises(Exception, match="API error"):
            deduplicator._get_embedding("Test question")

    @patch("app.deduplicator.OpenAI")
    def test_filter_duplicates(self, mock_openai, sample_existing_questions):
        """Test filtering duplicates from question list."""
        questions = [
            GeneratedQuestion(
                question_text="Unique question 1",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="4",
                answer_options=["2", "3", "4", "5"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
            GeneratedQuestion(
                question_text="What is the capital of France?",  # Duplicate
                question_type=QuestionType.VERBAL,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="Paris",
                answer_options=["London", "Paris", "Berlin", "Rome"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
            GeneratedQuestion(
                question_text="Unique question 2",
                question_type=QuestionType.LOGIC,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="true",
                answer_options=["true", "false"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
        ]

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Mock embeddings to ensure no semantic matches
        def get_mock_embedding(seed):
            np.random.seed(seed)
            return np.random.rand(1536)

        deduplicator._get_embedding = Mock(
            side_effect=[get_mock_embedding(i) for i in range(200, 220)]
        )

        unique, duplicates = deduplicator.filter_duplicates(
            questions, sample_existing_questions
        )

        assert len(unique) == 2
        assert len(duplicates) == 1
        assert duplicates[0][0].question_text == "What is the capital of France?"
        assert duplicates[0][1].is_duplicate is True

    @patch("app.deduplicator.OpenAI")
    def test_get_stats(self, mock_openai):
        """Test getting deduplicator statistics."""
        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",
            similarity_threshold=0.90,
            embedding_model="text-embedding-ada-002",
        )

        stats = deduplicator.get_stats()

        assert stats["similarity_threshold"] == pytest.approx(0.90)
        assert stats["embedding_model"] == "text-embedding-ada-002"


class TestDeduplicatorIntegration:
    """Integration tests for deduplicator with different scenarios."""

    @patch("app.deduplicator.OpenAI")
    def test_whitespace_normalization(self, mock_openai):
        """Test that whitespace differences don't affect exact matching."""
        question = GeneratedQuestion(
            question_text="  What is 2 + 2?  ",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            explanation="Explanation",
            source_llm="openai",
            source_model="gpt-4",
        )

        existing = [
            {"id": 1, "question_text": "What is 2 + 2?"},  # No extra whitespace
        ]

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")
        result = deduplicator.check_duplicate(question, existing)

        assert result.is_duplicate is True
        assert result.duplicate_type == "exact"

    @patch("app.deduplicator.OpenAI")
    def test_similarity_threshold_boundary(self, mock_openai):
        """Test behavior at similarity threshold boundary."""
        question = GeneratedQuestion(
            question_text="Test question",
            question_type=QuestionType.MATH,
            difficulty_level=DifficultyLevel.EASY,
            correct_answer="4",
            answer_options=["2", "3", "4", "5"],
            explanation="Explanation",
            source_llm="openai",
            source_model="gpt-4",
        )

        existing = [{"id": 1, "question_text": "Similar test question"}]

        deduplicator = QuestionDeduplicator(
            openai_api_key="test-key",
            similarity_threshold=0.85,
        )

        # Mock embeddings to return vectors with similarity at or above threshold
        # For cosine similarity = 0.85, if vec1 = [1, 0], then vec2 = [0.85, sqrt(1-0.85^2)]
        vec1 = np.array([1.0, 0.0])
        vec2 = np.array([0.85, np.sqrt(1 - 0.85**2)])  # Cosine similarity = 0.85

        deduplicator._get_embedding = Mock(side_effect=[vec1, vec2])

        result = deduplicator.check_duplicate(question, existing)

        # Should be marked as duplicate if at or above threshold
        assert result.is_duplicate is True
        assert result.similarity_score >= 0.85


class TestEmbeddingCache:
    """Tests for EmbeddingCache class."""

    def test_cache_initialization(self):
        """Test cache initializes empty."""
        cache = EmbeddingCache()

        assert cache.size == 0
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0

    def test_cache_miss_returns_none(self):
        """Test cache miss returns None."""
        cache = EmbeddingCache()

        result = cache.get("uncached text")

        assert result is None
        assert cache.stats["misses"] == 1
        assert cache.stats["hits"] == 0

    def test_cache_set_and_get(self):
        """Test setting and getting cached embedding."""
        cache = EmbeddingCache()
        embedding = np.array([0.1, 0.2, 0.3])

        cache.set("test text", embedding)
        result = cache.get("test text")

        assert result is not None
        np.testing.assert_array_equal(result, embedding)
        assert cache.size == 1
        assert cache.stats["hits"] == 1

    def test_cache_normalization(self):
        """Test that cache normalizes text (case-insensitive, stripped)."""
        cache = EmbeddingCache()
        embedding = np.array([0.1, 0.2, 0.3])

        cache.set("Test Text", embedding)

        # All variations should hit the same cache entry
        assert cache.get("test text") is not None
        assert cache.get("TEST TEXT") is not None
        assert cache.get("  Test Text  ") is not None
        assert cache.get("  test text  ") is not None

        # All 4 lookups should be hits
        assert cache.stats["hits"] == 4
        # Only one entry in cache
        assert cache.size == 1

    def test_cache_clear(self):
        """Test clearing the cache."""
        cache = EmbeddingCache()
        cache.set("text1", np.array([0.1, 0.2]))
        cache.set("text2", np.array([0.3, 0.4]))
        cache.get("text1")  # hit

        assert cache.size == 2
        assert cache.stats["hits"] == 1

        cache.clear()

        assert cache.size == 0
        assert cache.stats["hits"] == 0
        assert cache.stats["misses"] == 0

    def test_cache_stats(self):
        """Test cache statistics tracking."""
        cache = EmbeddingCache()

        # Miss
        cache.get("text1")
        # Set
        cache.set("text1", np.array([0.1]))
        # Hit
        cache.get("text1")
        # Miss
        cache.get("text2")

        stats = cache.stats
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 2


class TestDeduplicatorCacheIntegration:
    """Tests for QuestionDeduplicator embedding cache integration."""

    @patch("app.deduplicator.OpenAI")
    def test_cache_reduces_api_calls(self, mock_openai):
        """Test that caching reduces duplicate API calls."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Get embedding for same text twice
        embedding1 = deduplicator._get_embedding("test question")
        embedding2 = deduplicator._get_embedding("test question")

        # API should only be called once
        assert mock_openai.return_value.embeddings.create.call_count == 1
        # Both embeddings should be identical
        np.testing.assert_array_equal(embedding1, embedding2)

    @patch("app.deduplicator.OpenAI")
    def test_cache_case_insensitive(self, mock_openai):
        """Test that cache is case-insensitive for same text."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Get embedding with different case variations
        deduplicator._get_embedding("Test Question")
        deduplicator._get_embedding("test question")
        deduplicator._get_embedding("TEST QUESTION")

        # API should only be called once
        assert mock_openai.return_value.embeddings.create.call_count == 1

    @patch("app.deduplicator.OpenAI")
    def test_get_stats_includes_cache(self, mock_openai):
        """Test that get_stats includes cache statistics."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Generate some cache activity
        deduplicator._get_embedding("question 1")  # miss
        deduplicator._get_embedding("question 1")  # hit
        deduplicator._get_embedding("question 2")  # miss

        stats = deduplicator.get_stats()

        assert "cache" in stats
        assert stats["cache"]["size"] == 2
        assert stats["cache"]["hits"] == 1
        assert stats["cache"]["misses"] == 2

    @patch("app.deduplicator.OpenAI")
    def test_clear_cache(self, mock_openai):
        """Test that clear_cache removes all cached embeddings."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Cache some embeddings
        deduplicator._get_embedding("question 1")
        deduplicator._get_embedding("question 2")

        assert deduplicator.get_stats()["cache"]["size"] == 2

        deduplicator.clear_cache()

        assert deduplicator.get_stats()["cache"]["size"] == 0
        assert deduplicator.get_stats()["cache"]["hits"] == 0
        assert deduplicator.get_stats()["cache"]["misses"] == 0

    @patch("app.deduplicator.OpenAI")
    def test_batch_check_uses_cache_efficiently(
        self, mock_openai, sample_existing_questions
    ):
        """Test that batch checking reuses embeddings for existing questions."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=[0.1] * 1536)]
        mock_openai.return_value.embeddings.create.return_value = mock_response

        deduplicator = QuestionDeduplicator(openai_api_key="test-key")

        # Create two questions to check
        questions = [
            GeneratedQuestion(
                question_text="New question 1",
                question_type=QuestionType.MATH,
                difficulty_level=DifficultyLevel.EASY,
                correct_answer="4",
                answer_options=["2", "3", "4", "5"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
            GeneratedQuestion(
                question_text="New question 2",
                question_type=QuestionType.VERBAL,
                difficulty_level=DifficultyLevel.MEDIUM,
                correct_answer="answer",
                answer_options=["a", "b", "answer", "d"],
                explanation="Explanation",
                source_llm="openai",
                source_model="gpt-4",
            ),
        ]

        # Check both questions against existing ones
        deduplicator.check_duplicates_batch(questions, sample_existing_questions)

        # Without cache: 2 new + 2*3 existing = 8 API calls
        # With cache: 2 new + 3 existing = 5 API calls
        # (each existing question only embedded once, regardless of how many new questions)
        assert mock_openai.return_value.embeddings.create.call_count == 5

        # Check cache stats
        stats = deduplicator.get_stats()["cache"]
        # 5 unique texts cached
        assert stats["size"] == 5
        # 3 hits (existing questions checked second time)
        assert stats["hits"] == 3
        # 5 misses (first time for each text)
        assert stats["misses"] == 5
