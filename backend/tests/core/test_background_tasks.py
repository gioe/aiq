"""Tests for the safe_background_task wrapper."""

import logging
from unittest.mock import AsyncMock, patch

import pytest

from app.core.background_tasks import safe_background_task


@pytest.mark.asyncio
async def test_successful_task_runs_normally():
    """Wrapper should call the function and return without error."""
    func = AsyncMock(return_value=True)
    await safe_background_task(func, "arg1", key="val")
    func.assert_awaited_once_with("arg1", key="val")


@pytest.mark.asyncio
async def test_exception_is_caught_and_logged(caplog):
    """Wrapper should catch exceptions and log them, never propagating."""
    func = AsyncMock(side_effect=RuntimeError("boom"))
    func.__name__ = "exploding_task"

    with caplog.at_level(logging.ERROR, logger="app.core.background_tasks"):
        await safe_background_task(func, "arg1")

    func.assert_awaited_once_with("arg1")
    assert "Background task 'exploding_task' failed" in caplog.text
    assert "boom" in caplog.text


@pytest.mark.asyncio
async def test_exception_does_not_propagate():
    """Wrapper must never let exceptions escape."""
    func = AsyncMock(side_effect=Exception("fatal"))
    func.__name__ = "fatal_task"

    # Should NOT raise
    await safe_background_task(func)


@pytest.mark.asyncio
async def test_metrics_recorded_on_failure():
    """Wrapper should record a BackgroundTaskFailure metric on error."""
    func = AsyncMock(side_effect=ValueError("bad"))
    func.__name__ = "bad_task"

    with patch("app.core.background_tasks.metrics") as mock_metrics:
        await safe_background_task(func)

    mock_metrics.record_error.assert_called_once_with(
        error_type="BackgroundTaskFailure:bad_task"
    )


@pytest.mark.asyncio
async def test_metrics_failure_does_not_break_wrapper(caplog):
    """If metrics recording itself fails, the wrapper should still succeed."""
    func = AsyncMock(side_effect=ValueError("bad"))
    func.__name__ = "bad_task"

    with patch("app.core.background_tasks.metrics") as mock_metrics:
        mock_metrics.record_error.side_effect = RuntimeError("metrics down")
        with caplog.at_level(logging.DEBUG, logger="app.core.background_tasks"):
            # Should NOT raise despite metrics failure
            await safe_background_task(func)

    assert "Failed to record BackgroundTaskFailure metric" in caplog.text


@pytest.mark.asyncio
async def test_kwargs_forwarded_correctly():
    """All positional and keyword args should reach the wrapped function."""
    func = AsyncMock()
    await safe_background_task(func, 1, 2, 3, a="x", b="y")
    func.assert_awaited_once_with(1, 2, 3, a="x", b="y")


@pytest.mark.asyncio
async def test_function_name_extracted():
    """Wrapper should extract __name__ for the log message."""
    func = AsyncMock(side_effect=Exception("err"))
    func.__name__ = "my_custom_task"

    with patch("app.core.background_tasks.logger") as mock_logger:
        await safe_background_task(func)

    mock_logger.exception.assert_called_once()
    # Name is passed as a %s argument to the format string
    assert mock_logger.exception.call_args[0][1] == "my_custom_task"


@pytest.mark.asyncio
async def test_repr_fallback_when_no_name(caplog):
    """Wrapper should fall back to repr() when __name__ is missing."""
    func = AsyncMock(side_effect=Exception("err"))
    del func.__name__

    with caplog.at_level(logging.ERROR, logger="app.core.background_tasks"):
        await safe_background_task(func)

    assert "Background task" in caplog.text


@pytest.mark.asyncio
async def test_sync_function_raises_type_error():
    """Wrapper should raise TypeError with a clear message when passed a sync function."""

    def sync_func() -> None:
        pass

    with pytest.raises(
        TypeError, match="safe_background_task requires an async function"
    ):
        await safe_background_task(sync_func)


@pytest.mark.asyncio
async def test_sync_function_error_includes_function_name():
    """Error message should include the sync function's name."""

    def my_sync_task() -> None:
        pass

    with pytest.raises(TypeError, match="my_sync_task"):
        await safe_background_task(my_sync_task)
