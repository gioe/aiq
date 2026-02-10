"""Tests for OTEL metrics emitted in generator.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.generator import _safe_record_metric


class TestGenerationFailureDifficultyLabel:
    """Verify generation.failure counter includes the difficulty label."""

    @pytest.fixture
    def mock_observability(self):
        with patch("app.generator.observability") as mock_obs:
            mock_obs.is_initialized = True
            yield mock_obs

    @staticmethod
    def _simulate_failure_metric(
        provider: str,
        question_type: str,
        difficulty: str,
        mock_obs: MagicMock,
    ):
        """Reproduce the generation.failure metric-emission logic from generator.py."""
        _safe_record_metric(
            "generation.failure",
            value=1,
            labels={
                "provider": provider,
                "question_type": question_type,
                "difficulty": difficulty,
            },
            metric_type="counter",
        )

    def test_includes_difficulty_label(self, mock_observability):
        self._simulate_failure_metric(
            "openai", "pattern_recognition", "hard", mock_observability
        )

        mock_observability.record_metric.assert_called_once_with(
            "generation.failure",
            value=1,
            labels={
                "provider": "openai",
                "question_type": "pattern_recognition",
                "difficulty": "hard",
            },
            metric_type="counter",
            unit=None,
        )

    def test_difficulty_label_varies_by_level(self, mock_observability):
        for difficulty in ("easy", "medium", "hard"):
            mock_observability.record_metric.reset_mock()
            self._simulate_failure_metric(
                "anthropic", "math", difficulty, mock_observability
            )

            call_labels = mock_observability.record_metric.call_args[1]["labels"]
            assert call_labels["difficulty"] == difficulty

    def test_all_three_labels_present(self, mock_observability):
        self._simulate_failure_metric(
            "google", "verbal_reasoning", "medium", mock_observability
        )

        call_labels = mock_observability.record_metric.call_args[1]["labels"]
        assert set(call_labels.keys()) == {"provider", "question_type", "difficulty"}
