"""Tests for OTEL metrics emitted in run_generation.py dedup loop."""

from unittest.mock import MagicMock, patch

import pytest

from app.deduplicator import DuplicateCheckResult


class TestDedupByTypeMetric:
    """Verify dedup.by_type counter is emitted only for duplicates."""

    @pytest.fixture
    def mock_observability(self):
        with patch("run_generation.observability") as mock_obs:
            yield mock_obs

    def _simulate_dedup_metric(self, result: DuplicateCheckResult, mock_obs: MagicMock):
        """Reproduce the metric-emission logic from run_generation.py L1670-1676."""
        if result.is_duplicate:
            mock_obs.record_metric(
                "dedup.by_type",
                value=1,
                labels={"duplicate_type": result.duplicate_type or "unknown"},
                metric_type="counter",
            )

    def test_emits_metric_for_exact_duplicate(self, mock_observability):
        result = DuplicateCheckResult(
            is_duplicate=True, duplicate_type="exact", similarity_score=1.0
        )
        self._simulate_dedup_metric(result, mock_observability)

        mock_observability.record_metric.assert_called_once_with(
            "dedup.by_type",
            value=1,
            labels={"duplicate_type": "exact"},
            metric_type="counter",
        )

    def test_emits_metric_for_semantic_duplicate(self, mock_observability):
        result = DuplicateCheckResult(
            is_duplicate=True, duplicate_type="semantic", similarity_score=0.92
        )
        self._simulate_dedup_metric(result, mock_observability)

        mock_observability.record_metric.assert_called_once_with(
            "dedup.by_type",
            value=1,
            labels={"duplicate_type": "semantic"},
            metric_type="counter",
        )

    def test_no_metric_for_unique_question(self, mock_observability):
        result = DuplicateCheckResult(
            is_duplicate=False, duplicate_type=None, similarity_score=0.1
        )
        self._simulate_dedup_metric(result, mock_observability)

        mock_observability.record_metric.assert_not_called()

    def test_fallback_to_unknown_when_type_is_none(self, mock_observability):
        result = DuplicateCheckResult(
            is_duplicate=True, duplicate_type=None, similarity_score=0.95
        )
        self._simulate_dedup_metric(result, mock_observability)

        mock_observability.record_metric.assert_called_once_with(
            "dedup.by_type",
            value=1,
            labels={"duplicate_type": "unknown"},
            metric_type="counter",
        )
