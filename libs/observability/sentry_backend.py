"""Sentry backend for error tracking.

This module handles all Sentry SDK interactions including initialization,
error capture, and context management.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Iterator

if TYPE_CHECKING:
    from libs.observability.config import SentryConfig

logger = logging.getLogger(__name__)


class SentryBackend:
    """Backend for Sentry error tracking."""

    def __init__(self, config: SentryConfig) -> None:
        self._config = config
        self._initialized = False

    def init(self) -> bool:
        """Initialize the Sentry SDK with FastAPI/Starlette integrations.

        Configures Sentry with the following integrations when available:
        - LoggingIntegration (always included)
        - FastApiIntegration with transaction_style="endpoint"
        - StarletteIntegration with transaction_style="endpoint"
        - OpenTelemetryIntegration (if OTEL SDK is installed)

        Returns:
            True if Sentry was initialized successfully (SDK configured and ready).
            False if initialization was skipped (disabled/no DSN) or failed (exception).

        Note:
            Does not raise exceptions - failures are logged and return False.
        """
        if not self._config.enabled or not self._config.dsn:
            logger.debug("Sentry initialization skipped (disabled or DSN not configured)")
            return False

        try:
            import sentry_sdk
            from sentry_sdk.integrations.logging import LoggingIntegration

            integrations: list[Any] = [
                LoggingIntegration(
                    level=None,  # Don't capture breadcrumbs from logs
                    event_level=None,  # Don't send log events
                ),
            ]

            # Add FastAPI integration if available
            try:
                from sentry_sdk.integrations.fastapi import FastApiIntegration

                integrations.append(FastApiIntegration(transaction_style="endpoint"))
            except ImportError:
                pass

            # Add Starlette integration if available
            try:
                from sentry_sdk.integrations.starlette import StarletteIntegration

                integrations.append(StarletteIntegration(transaction_style="endpoint"))
            except ImportError:
                pass

            # Add OpenTelemetry integration if available
            # Note: Must catch both ImportError and DidNotEnable - the latter is raised
            # when opentelemetry SDK is not installed even if sentry_sdk is
            try:
                from sentry_sdk.integrations.opentelemetry import OpenTelemetryIntegration

                integrations.append(OpenTelemetryIntegration())
            except ImportError:
                pass
            except Exception as e:
                # DidNotEnable is raised when opentelemetry SDK is not installed
                if e.__class__.__name__ == "DidNotEnable":
                    pass
                else:
                    logger.debug(f"OpenTelemetry integration unavailable: {e}")

            sentry_sdk.init(
                dsn=self._config.dsn,
                environment=self._config.environment,
                release=self._config.release,
                traces_sample_rate=self._config.traces_sample_rate,
                profiles_sample_rate=self._config.profiles_sample_rate,
                integrations=integrations,
                send_default_pii=self._config.send_default_pii,
            )

            self._initialized = True

            logger.info(
                f"Sentry initialized for environment '{self._config.environment}' "
                f"with {self._config.traces_sample_rate * 100:.0f}% trace sampling"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize Sentry: {e}", exc_info=True)
            return False

    def capture_error(
        self,
        exception: BaseException,
        *,
        context: dict[str, Any] | None = None,
        level: str = "error",
        user: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
        fingerprint: list[str] | None = None,
    ) -> str | None:
        """Capture an exception and send to Sentry.

        Returns:
            Event ID if captured.
        """
        if not self._initialized:
            return None

        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if context:
                scope.set_context("additional", context)
            if user:
                scope.set_user(user)
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)
            if fingerprint:
                scope.fingerprint = fingerprint
            scope.level = level

            return sentry_sdk.capture_exception(exception)

    def capture_message(
        self,
        message: str,
        *,
        level: str = "info",
        context: dict[str, Any] | None = None,
        tags: dict[str, str] | None = None,
    ) -> str | None:
        """Capture a message and send to Sentry.

        Returns:
            Event ID if captured.
        """
        if not self._initialized:
            return None

        import sentry_sdk

        with sentry_sdk.push_scope() as scope:
            if context:
                scope.set_context("additional", context)
            if tags:
                for key, value in tags.items():
                    scope.set_tag(key, value)
            scope.level = level

            return sentry_sdk.capture_message(message, level=level)

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        attributes: dict[str, Any] | None = None,
    ) -> Iterator[Any]:
        """Start a Sentry span/transaction.

        Yields:
            Sentry span object.
        """
        if not self._initialized:
            yield None
            return

        import sentry_sdk

        with sentry_sdk.start_span(op="function", description=name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_data(key, value)
            yield span

    def set_user(self, user_id: str | None, **extra: Any) -> None:
        """Set the current user context."""
        if not self._initialized:
            return

        import sentry_sdk

        if user_id is None:
            sentry_sdk.set_user(None)
        else:
            sentry_sdk.set_user({"id": user_id, **extra})

    def set_tag(self, key: str, value: str) -> None:
        """Set a tag on the current scope."""
        if not self._initialized:
            return

        import sentry_sdk

        sentry_sdk.set_tag(key, value)

    def set_context(self, name: str, context: dict[str, Any]) -> None:
        """Set a context block on the current scope."""
        if not self._initialized:
            return

        import sentry_sdk

        sentry_sdk.set_context(name, context)

    def flush(self, timeout: float = 2.0) -> None:
        """Flush pending events."""
        if not self._initialized:
            return

        import sentry_sdk

        sentry_sdk.flush(timeout=timeout)

    def shutdown(self) -> None:
        """Shutdown the Sentry SDK."""
        if not self._initialized:
            return

        import sentry_sdk

        client = sentry_sdk.get_client()
        if client is not None:
            client.close(timeout=2.0)

        self._initialized = False
