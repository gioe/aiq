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


class TestRecordLogin:
    """Unit tests for record_login()."""

    def test_emits_counter_with_success_true(self, initialized_metrics):
        """record_login(success=True) emits auth.login counter with auth.success=true."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_login(success=True)

            mock_obs.record_metric.assert_called_once_with(
                name="auth.login",
                value=1,
                labels={"auth.success": "true"},
                metric_type="counter",
                unit="1",
            )

    def test_emits_counter_with_success_false(self, initialized_metrics):
        """record_login(success=False) emits auth.login counter with auth.success=false."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_login(success=False)

            mock_obs.record_metric.assert_called_once_with(
                name="auth.login",
                value=1,
                labels={"auth.success": "false"},
                metric_type="counter",
                unit="1",
            )

    def test_noop_when_not_initialized(self):
        """No metrics emitted when ApplicationMetrics is not initialized."""
        m = ApplicationMetrics()
        with patch("app.observability.observability") as mock_obs:
            m.record_login(success=True)

            mock_obs.record_metric.assert_not_called()


class TestRecordIqScore:
    """Unit tests for record_iq_score()."""

    def test_emits_histogram(self, initialized_metrics):
        """record_iq_score emits a histogram with the score value."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_iq_score(score=115.0, adaptive=False)

            mock_obs.record_metric.assert_called_once_with(
                name="test.iq_score",
                value=115.0,
                labels={"test.adaptive": "false"},
                metric_type="histogram",
                unit="1",
            )

    def test_adaptive_label_true(self, initialized_metrics):
        """Adaptive label is 'true' for CAT tests."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_iq_score(score=100.0, adaptive=True)

            call = mock_obs.record_metric.call_args
            assert call.kwargs["labels"]["test.adaptive"] == "true"

    def test_warns_on_out_of_range_score(self, initialized_metrics):
        """Out-of-range scores log a warning but still record the metric."""
        with (
            patch("app.observability.observability") as mock_obs,
            patch("app.observability.logger") as mock_logger,
        ):
            initialized_metrics.record_iq_score(score=200.0, adaptive=False)

            mock_logger.warning.assert_called_once()
            mock_obs.record_metric.assert_called_once()

    def test_noop_when_not_initialized(self):
        """No metrics emitted when ApplicationMetrics is not initialized."""
        m = ApplicationMetrics()
        with patch("app.observability.observability") as mock_obs:
            m.record_iq_score(score=100.0, adaptive=False)

            mock_obs.record_metric.assert_not_called()


class TestRecordNotification:
    """Unit tests for record_notification()."""

    def test_emits_counter_with_success_true(self, initialized_metrics):
        """record_notification(success=True) emits notifications.apns counter."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_notification(
                success=True, notification_type="test_reminder"
            )

            mock_obs.record_metric.assert_called_once_with(
                name="notifications.apns",
                value=1,
                labels={
                    "notification.success": "true",
                    "notification.type": "test_reminder",
                },
                metric_type="counter",
                unit="1",
            )

    def test_emits_counter_with_success_false(self, initialized_metrics):
        """record_notification(success=False) emits notifications.apns counter."""
        with patch("app.observability.observability") as mock_obs:
            initialized_metrics.record_notification(
                success=False, notification_type="logout_all"
            )

            mock_obs.record_metric.assert_called_once_with(
                name="notifications.apns",
                value=1,
                labels={
                    "notification.success": "false",
                    "notification.type": "logout_all",
                },
                metric_type="counter",
                unit="1",
            )

    def test_noop_when_not_initialized(self):
        """No metrics emitted when ApplicationMetrics is not initialized."""
        m = ApplicationMetrics()
        with patch("app.observability.observability") as mock_obs:
            m.record_notification(success=True, notification_type="test_reminder")

            mock_obs.record_metric.assert_not_called()
