"""
Unit tests for ApplicationMetrics methods in app.observability.

Tests verify the correct metric types and labels are emitted
by each business metric method.
"""

from unittest.mock import patch

import pytest

from app.observability import ApplicationMetrics


@pytest.fixture
def initialized_metrics():
    """Return an ApplicationMetrics instance that believes it's initialized."""
    m = ApplicationMetrics()
    m._initialized = True
    return m


class TestRecordTestCompleted:
    """Unit tests for record_test_completed()."""

    def test_emits_counter_and_histogram(self, initialized_metrics):
        """record_test_completed emits both a counter and a duration histogram."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_test_completed(
                adaptive=False, question_count=10, duration_seconds=120.5
            )

            assert mock_obs.record_metric.call_count == 2

            counter_call, histogram_call = mock_obs.record_metric.call_args_list

            # Counter call
            assert counter_call.kwargs["name"] == "test.sessions.completed"
            assert counter_call.kwargs["value"] == 1
            assert counter_call.kwargs["metric_type"] == "counter"

            # Histogram call
            assert histogram_call.kwargs["name"] == "test.sessions.duration"
            assert histogram_call.kwargs["value"] == pytest.approx(120.5)
            assert histogram_call.kwargs["metric_type"] == "histogram"
            assert histogram_call.kwargs["unit"] == "s"

    def test_histogram_uses_same_labels_as_counter(self, initialized_metrics):
        """Both the counter and histogram share the same label set."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_test_completed(
                adaptive=True, question_count=5, duration_seconds=60.0
            )

            counter_call, histogram_call = mock_obs.record_metric.call_args_list

            expected_labels = {
                "test.adaptive": "true",
                "test.question_count": "5",
            }
            assert counter_call.kwargs["labels"] == expected_labels
            assert histogram_call.kwargs["labels"] == expected_labels

    def test_histogram_records_zero_duration(self, initialized_metrics):
        """A zero-second test duration is recorded as 0.0."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_test_completed(
                adaptive=False, question_count=1, duration_seconds=0.0
            )

            histogram_call = mock_obs.record_metric.call_args_list[1]
            assert histogram_call.kwargs["value"] == pytest.approx(0.0)

    def test_negative_duration_clamped_to_zero(self, initialized_metrics):
        """Negative duration is clamped to 0.0 before recording."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_test_completed(
                adaptive=False, question_count=1, duration_seconds=-5.0
            )

            histogram_call = mock_obs.record_metric.call_args_list[1]
            assert histogram_call.kwargs["value"] == pytest.approx(0.0)

    def test_noop_when_not_initialized(self):
        """No metrics emitted when ApplicationMetrics is not initialized."""
        m = ApplicationMetrics()  # _initialized defaults to False
        with patch("app.observability.observability") as mock_obs:
            m.record_test_completed(
                adaptive=False, question_count=5, duration_seconds=30.0
            )

            mock_obs.record_metric.assert_not_called()

    def test_existing_counter_preserved(self, initialized_metrics):
        """The pre-existing counter emission is not removed or altered."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_test_completed(
                adaptive=False, question_count=3, duration_seconds=45.0
            )

            counter_call = mock_obs.record_metric.call_args_list[0]
            assert counter_call.kwargs["name"] == "test.sessions.completed"
            assert counter_call.kwargs["value"] == 1
            assert counter_call.kwargs["metric_type"] == "counter"
            assert counter_call.kwargs["unit"] == "1"
