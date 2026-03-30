"""Unit tests for AnalyticsTracker.track_event observability integration."""

from unittest.mock import patch

from app.core.analytics import AnalyticsTracker, EventType


@patch("app.core.analytics.observability")
def test_record_event_called_with_correct_args(mock_obs):
    """record_event is called with event_type.value, event_data dict, and tags."""
    AnalyticsTracker.track_event(
        EventType.USER_LOGIN,
        user_id=42,
        properties={"ip": "127.0.0.1"},
    )

    mock_obs.record_event.assert_called_once()
    call_kwargs = mock_obs.record_event.call_args

    # First positional arg is event_type.value
    assert call_kwargs.args[0] == EventType.USER_LOGIN.value

    # data kwarg is the full event_data dict
    data = call_kwargs.kwargs["data"]
    assert data["event"] == EventType.USER_LOGIN.value
    assert data["user_id"] == 42
    assert data["properties"] == {"ip": "127.0.0.1"}

    # tags kwarg contains environment key
    tags = call_kwargs.kwargs["tags"]
    assert "environment" in tags


@patch("app.core.analytics.observability")
def test_set_user_called_when_user_id_provided(mock_obs):
    """set_user is called with str(user_id) when user_id is not None."""
    AnalyticsTracker.track_event(EventType.USER_LOGIN, user_id=99)

    mock_obs.set_user.assert_called_once_with("99")


@patch("app.core.analytics.observability")
def test_set_user_not_called_when_user_id_is_none(mock_obs):
    """set_user is NOT called when user_id is None."""
    AnalyticsTracker.track_event(EventType.USER_LOGIN, user_id=None)

    mock_obs.set_user.assert_not_called()
    # record_event should still be called
    mock_obs.record_event.assert_called_once()
