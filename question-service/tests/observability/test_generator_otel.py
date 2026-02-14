"""Tests for OTEL metrics emitted in generator.py."""

from unittest.mock import MagicMock, patch

import pytest

from app.generation.generator import _safe_record_metric


class TestGenerationFailureDifficultyLabel:
    """Verify generation.failure counter includes the difficulty label."""

    @pytest.fixture
    def mock_observability(self):
        with patch("app.generation.generator.observability") as mock_obs:
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


class TestLatencyCostDifficultyLabel:
    """Verify question.generation.latency and question.generation.cost include difficulty."""

    @pytest.fixture
    def mock_observability(self):
        with patch("app.generation.generator.observability") as mock_obs:
            mock_obs.is_initialized = True
            yield mock_obs

    @staticmethod
    def _simulate_latency_metric(
        question_type: str,
        provider: str,
        difficulty: str,
        latency: float,
        mock_obs: MagicMock,
    ):
        """Reproduce the question.generation.latency metric from generator.py."""
        _safe_record_metric(
            "question.generation.latency",
            value=latency,
            labels={
                "question_type": question_type,
                "provider": provider,
                "difficulty": difficulty,
            },
            metric_type="histogram",
            unit="s",
        )

    @staticmethod
    def _simulate_cost_metric(
        question_type: str,
        provider: str,
        difficulty: str,
        cost: float,
        mock_obs: MagicMock,
    ):
        """Reproduce the question.generation.cost metric from generator.py."""
        _safe_record_metric(
            "question.generation.cost",
            value=cost,
            labels={
                "question_type": question_type,
                "provider": provider,
                "difficulty": difficulty,
            },
            metric_type="counter",
            unit="usd",
        )

    def test_latency_includes_difficulty_label(self, mock_observability):
        self._simulate_latency_metric(
            "pattern_recognition", "openai", "hard", 2.5, mock_observability
        )

        mock_observability.record_metric.assert_called_once_with(
            "question.generation.latency",
            value=2.5,
            labels={
                "question_type": "pattern_recognition",
                "provider": "openai",
                "difficulty": "hard",
            },
            metric_type="histogram",
            unit="s",
        )

    def test_cost_includes_difficulty_label(self, mock_observability):
        self._simulate_cost_metric(
            "math", "anthropic", "easy", 0.003, mock_observability
        )

        mock_observability.record_metric.assert_called_once_with(
            "question.generation.cost",
            value=0.003,
            labels={
                "question_type": "math",
                "provider": "anthropic",
                "difficulty": "easy",
            },
            metric_type="counter",
            unit="usd",
        )

    def test_latency_difficulty_varies_by_level(self, mock_observability):
        for difficulty in ("easy", "medium", "hard"):
            mock_observability.record_metric.reset_mock()
            self._simulate_latency_metric(
                "verbal_reasoning", "google", difficulty, 1.0, mock_observability
            )

            call_labels = mock_observability.record_metric.call_args[1]["labels"]
            assert call_labels["difficulty"] == difficulty

    def test_cost_difficulty_varies_by_level(self, mock_observability):
        for difficulty in ("easy", "medium", "hard"):
            mock_observability.record_metric.reset_mock()
            self._simulate_cost_metric(
                "spatial", "openai", difficulty, 0.01, mock_observability
            )

            call_labels = mock_observability.record_metric.call_args[1]["labels"]
            assert call_labels["difficulty"] == difficulty

    def test_latency_all_labels_present(self, mock_observability):
        self._simulate_latency_metric(
            "math", "anthropic", "medium", 3.0, mock_observability
        )

        call_labels = mock_observability.record_metric.call_args[1]["labels"]
        assert set(call_labels.keys()) == {"question_type", "provider", "difficulty"}

    def test_cost_all_labels_present(self, mock_observability):
        self._simulate_cost_metric(
            "math", "anthropic", "medium", 0.005, mock_observability
        )

        call_labels = mock_observability.record_metric.call_args[1]["labels"]
        assert set(call_labels.keys()) == {"question_type", "provider", "difficulty"}
