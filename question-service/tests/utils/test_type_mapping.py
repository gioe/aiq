"""Tests for type_mapping module."""

import pytest

from app.utils.type_mapping import (
    DIFFICULTY_LEVELS,
    LEGACY_DIFFICULTY_MAPPING,
    LEGACY_QUESTION_TYPE_MAPPING,
    QUESTION_TYPES,
    normalize_difficulty,
    normalize_difficulty_metrics,
    normalize_question_type,
    normalize_type_metrics,
)


class TestCanonicalValues:
    """Tests for canonical enum value lists."""

    def test_question_types_contains_expected_values(self):
        """Test QUESTION_TYPES contains all canonical values."""
        expected = ["pattern", "logic", "spatial", "math", "verbal", "memory"]
        assert sorted(QUESTION_TYPES) == sorted(expected)

    def test_difficulty_levels_contains_expected_values(self):
        """Test DIFFICULTY_LEVELS contains all canonical values."""
        expected = ["easy", "medium", "hard"]
        assert sorted(DIFFICULTY_LEVELS) == sorted(expected)


class TestLegacyMappings:
    """Tests for legacy to canonical mapping dictionaries."""

    def test_legacy_question_type_mapping_includes_legacy_values(self):
        """Test legacy question type values are mapped correctly."""
        # Legacy values from old codebase
        assert LEGACY_QUESTION_TYPE_MAPPING["pattern_recognition"] == "pattern"
        assert LEGACY_QUESTION_TYPE_MAPPING["logical_reasoning"] == "logic"
        assert LEGACY_QUESTION_TYPE_MAPPING["spatial_reasoning"] == "spatial"
        assert LEGACY_QUESTION_TYPE_MAPPING["mathematical"] == "math"
        assert LEGACY_QUESTION_TYPE_MAPPING["verbal_reasoning"] == "verbal"
        assert LEGACY_QUESTION_TYPE_MAPPING["memory"] == "memory"

    def test_legacy_question_type_mapping_includes_canonical_values(self):
        """Test canonical values map to themselves."""
        assert LEGACY_QUESTION_TYPE_MAPPING["pattern"] == "pattern"
        assert LEGACY_QUESTION_TYPE_MAPPING["logic"] == "logic"
        assert LEGACY_QUESTION_TYPE_MAPPING["spatial"] == "spatial"
        assert LEGACY_QUESTION_TYPE_MAPPING["math"] == "math"
        assert LEGACY_QUESTION_TYPE_MAPPING["verbal"] == "verbal"
        assert LEGACY_QUESTION_TYPE_MAPPING["memory"] == "memory"

    def test_legacy_difficulty_mapping_includes_canonical_values(self):
        """Test difficulty values map to themselves."""
        assert LEGACY_DIFFICULTY_MAPPING["easy"] == "easy"
        assert LEGACY_DIFFICULTY_MAPPING["medium"] == "medium"
        assert LEGACY_DIFFICULTY_MAPPING["hard"] == "hard"


class TestNormalizeQuestionType:
    """Tests for normalize_question_type function."""

    def test_normalizes_legacy_pattern_recognition(self):
        """Test pattern_recognition is normalized to pattern."""
        assert normalize_question_type("pattern_recognition") == "pattern"

    def test_normalizes_legacy_logical_reasoning(self):
        """Test logical_reasoning is normalized to logic."""
        assert normalize_question_type("logical_reasoning") == "logic"

    def test_normalizes_legacy_spatial_reasoning(self):
        """Test spatial_reasoning is normalized to spatial."""
        assert normalize_question_type("spatial_reasoning") == "spatial"

    def test_normalizes_legacy_mathematical(self):
        """Test mathematical is normalized to math."""
        assert normalize_question_type("mathematical") == "math"

    def test_normalizes_legacy_verbal_reasoning(self):
        """Test verbal_reasoning is normalized to verbal."""
        assert normalize_question_type("verbal_reasoning") == "verbal"

    def test_preserves_canonical_values(self):
        """Test canonical values are preserved."""
        for canonical in ["pattern", "logic", "spatial", "math", "verbal", "memory"]:
            assert normalize_question_type(canonical) == canonical

    def test_raises_for_unknown_type(self):
        """Test ValueError is raised for unknown question types."""
        with pytest.raises(ValueError) as exc_info:
            normalize_question_type("unknown_type")
        assert "Unknown question type" in str(exc_info.value)
        assert "unknown_type" in str(exc_info.value)


class TestNormalizeDifficulty:
    """Tests for normalize_difficulty function."""

    def test_preserves_canonical_values(self):
        """Test canonical difficulty values are preserved."""
        assert normalize_difficulty("easy") == "easy"
        assert normalize_difficulty("medium") == "medium"
        assert normalize_difficulty("hard") == "hard"

    def test_raises_for_unknown_difficulty(self):
        """Test ValueError is raised for unknown difficulty levels."""
        with pytest.raises(ValueError) as exc_info:
            normalize_difficulty("impossible")
        assert "Unknown difficulty level" in str(exc_info.value)
        assert "impossible" in str(exc_info.value)


class TestNormalizeTypeMetrics:
    """Tests for normalize_type_metrics function."""

    def test_normalizes_legacy_keys(self):
        """Test legacy metric keys are normalized to canonical values."""
        metrics = {
            "pattern_recognition": 10,
            "logical_reasoning": 5,
            "mathematical": 8,
        }
        normalized = normalize_type_metrics(metrics)

        assert normalized["pattern"] == 10
        assert normalized["logic"] == 5
        assert normalized["math"] == 8

    def test_preserves_canonical_keys(self):
        """Test canonical metric keys are preserved."""
        metrics = {
            "pattern": 10,
            "logic": 5,
            "math": 8,
        }
        normalized = normalize_type_metrics(metrics)

        assert normalized["pattern"] == 10
        assert normalized["logic"] == 5
        assert normalized["math"] == 8

    def test_merges_duplicate_keys(self):
        """Test metrics with both legacy and canonical keys are merged."""
        metrics = {
            "pattern_recognition": 10,
            "pattern": 5,
        }
        normalized = normalize_type_metrics(metrics)

        assert normalized["pattern"] == 15  # 10 + 5

    def test_preserves_unknown_keys(self):
        """Test unknown keys are preserved for debugging."""
        metrics = {
            "pattern": 10,
            "unknown_type": 3,
        }
        normalized = normalize_type_metrics(metrics)

        assert normalized["pattern"] == 10
        assert normalized["unknown_type"] == 3

    def test_handles_empty_dict(self):
        """Test empty dict returns empty dict."""
        assert normalize_type_metrics({}) == {}


class TestNormalizeDifficultyMetrics:
    """Tests for normalize_difficulty_metrics function."""

    def test_preserves_canonical_keys(self):
        """Test canonical difficulty keys are preserved."""
        metrics = {
            "easy": 10,
            "medium": 15,
            "hard": 5,
        }
        normalized = normalize_difficulty_metrics(metrics)

        assert normalized["easy"] == 10
        assert normalized["medium"] == 15
        assert normalized["hard"] == 5

    def test_preserves_unknown_keys(self):
        """Test unknown keys are preserved for debugging."""
        metrics = {
            "easy": 10,
            "nightmare": 1,
        }
        normalized = normalize_difficulty_metrics(metrics)

        assert normalized["easy"] == 10
        assert normalized["nightmare"] == 1

    def test_handles_empty_dict(self):
        """Test empty dict returns empty dict."""
        assert normalize_difficulty_metrics({}) == {}


class TestEdgeCases:
    """Edge case tests for type mapping functions."""

    def test_normalize_question_type_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown question type"):
            normalize_question_type("")

    def test_normalize_difficulty_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Unknown difficulty level"):
            normalize_difficulty("")

    def test_normalize_question_type_case_sensitive(self):
        """Test that normalization is case-sensitive (uppercase is rejected)."""
        with pytest.raises(ValueError, match="Unknown question type"):
            normalize_question_type("Pattern")

    def test_normalize_difficulty_case_sensitive(self):
        """Test that normalization is case-sensitive (uppercase is rejected)."""
        with pytest.raises(ValueError, match="Unknown difficulty level"):
            normalize_difficulty("Easy")

    def test_normalize_type_metrics_all_unknown(self):
        """Test metrics with only unknown keys are preserved."""
        metrics = {"foo": 5, "bar": 3}
        normalized = normalize_type_metrics(metrics)
        assert normalized == {"foo": 5, "bar": 3}

    def test_normalize_difficulty_metrics_all_unknown(self):
        """Test difficulty metrics with only unknown keys are preserved."""
        metrics = {"extreme": 2, "nightmare": 1}
        normalized = normalize_difficulty_metrics(metrics)
        assert normalized == {"extreme": 2, "nightmare": 1}

    def test_normalize_type_metrics_mixed_legacy_and_unknown(self):
        """Test metrics with both legacy values and unknown keys."""
        metrics = {"pattern_recognition": 5, "unknown": 3}
        normalized = normalize_type_metrics(metrics)
        assert normalized["pattern"] == 5
        assert normalized["unknown"] == 3

    def test_normalize_type_metrics_zero_counts(self):
        """Test metrics with zero counts are preserved."""
        metrics = {"pattern": 0, "logic": 0}
        normalized = normalize_type_metrics(metrics)
        assert normalized == {"pattern": 0, "logic": 0}


class TestIntegration:
    """Integration tests for type mapping with realistic data."""

    def test_normalizes_full_metrics_snapshot(self):
        """Test normalization of a realistic metrics snapshot."""
        type_metrics = {
            "pattern_recognition": 8,
            "logical_reasoning": 7,
            "spatial_reasoning": 6,
            "mathematical": 9,
            "verbal_reasoning": 5,
            "memory": 4,
        }
        difficulty_metrics = {
            "easy": 12,
            "medium": 18,
            "hard": 9,
        }

        normalized_types = normalize_type_metrics(type_metrics)
        normalized_difficulties = normalize_difficulty_metrics(difficulty_metrics)

        # Verify all types are normalized
        assert set(normalized_types.keys()) == {
            "pattern",
            "logic",
            "spatial",
            "math",
            "verbal",
            "memory",
        }
        assert normalized_types["pattern"] == 8
        assert normalized_types["logic"] == 7

        # Verify difficulties are preserved
        assert normalized_difficulties == difficulty_metrics
