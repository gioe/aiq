"""
Safe background task wrapper for consistent exception handling.

Starlette BackgroundTask exceptions propagate differently depending on the
middleware stack: with middleware present they are silently caught, but without
middleware (e.g., in TestClient) they crash the ASGI lifecycle. This module
provides a thin wrapper that catches and logs all background task exceptions
so behavior is identical in both environments.

Usage with FastAPI BackgroundTasks::

    from app.core.background_tasks import safe_background_task

    background_tasks.add_task(
        safe_background_task,
        send_logout_all_notification,
        device_token,
        user_id=user_id,
    )
"""

import logging
from typing import Any, Awaitable, Callable

from app.observability import metrics

logger = logging.getLogger(__name__)


async def safe_background_task(
    func: Callable[..., Awaitable[Any]],
    *args: Any,
    **kwargs: Any,
) -> None:
    """Execute an async function, catching and logging any exception.

    This wrapper is designed to be passed directly to
    ``BackgroundTasks.add_task`` with the target coroutine as the first
    positional argument.  All remaining positional and keyword arguments
    are forwarded to *func*.

    No retries are attempted — background tasks are fire-and-forget.
    """
    name = getattr(func, "__name__", repr(func))
    try:
        await func(*args, **kwargs)
    except Exception:
        logger.exception("Background task '%s' failed", name)
        try:
            metrics.record_error(error_type="BackgroundTaskFailure")
        except Exception:
            pass  # Metrics must never break the wrapper
