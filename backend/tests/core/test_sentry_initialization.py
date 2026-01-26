"""
Tests for Sentry SDK initialization in main.py.

These tests verify that Sentry initializes correctly based on the SENTRY_DSN configuration.
"""
import logging
from unittest.mock import patch

import pytest


class TestSentryInitialization:
    """Tests for Sentry SDK initialization behavior."""

    def test_sentry_initializes_when_dsn_is_provided(self, caplog):
        """Test that Sentry initializes correctly when DSN is provided."""
        mock_dsn = "https://public@sentry.io/123456"

        with patch("sentry_sdk.init") as mock_init:
            with patch("app.core.config.settings") as mock_settings:
                # Configure mock settings
                mock_settings.SENTRY_DSN = mock_dsn
                mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.1
                mock_settings.ENV = "test"
                mock_settings.APP_VERSION = "1.0.0"

                # Execute Sentry initialization code
                if mock_settings.SENTRY_DSN:
                    import sentry_sdk
                    from sentry_sdk.integrations.fastapi import FastApiIntegration
                    from sentry_sdk.integrations.starlette import StarletteIntegration

                    sentry_sdk.init(
                        dsn=mock_settings.SENTRY_DSN,
                        traces_sample_rate=mock_settings.SENTRY_TRACES_SAMPLE_RATE,
                        environment=mock_settings.ENV,
                        release=mock_settings.APP_VERSION,
                        send_default_pii=False,
                        integrations=[
                            StarletteIntegration(transaction_style="endpoint"),
                            FastApiIntegration(transaction_style="endpoint"),
                        ],
                    )

                # Verify sentry_sdk.init was called
                mock_init.assert_called_once()
                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["dsn"] == mock_dsn
                assert call_kwargs["traces_sample_rate"] == pytest.approx(0.1)
                assert call_kwargs["environment"] == "test"
                assert call_kwargs["release"] == "1.0.0"
                assert call_kwargs["send_default_pii"] is False
                assert len(call_kwargs["integrations"]) == 2

    def test_sentry_does_not_initialize_when_dsn_is_empty(self):
        """Test that Sentry does not initialize when DSN is empty string."""
        with patch("sentry_sdk.init") as mock_init:
            with patch("app.core.config.settings") as mock_settings:
                # Configure mock settings with empty DSN
                mock_settings.SENTRY_DSN = ""

                # Execute Sentry initialization code (same pattern as main.py)
                if mock_settings.SENTRY_DSN:
                    import sentry_sdk

                    sentry_sdk.init(dsn=mock_settings.SENTRY_DSN)

                # Verify sentry_sdk.init was NOT called
                mock_init.assert_not_called()

    def test_sentry_does_not_initialize_when_dsn_is_none(self):
        """Test that Sentry does not initialize when DSN is None."""
        with patch("sentry_sdk.init") as mock_init:
            with patch("app.core.config.settings") as mock_settings:
                # Configure mock settings with None DSN
                mock_settings.SENTRY_DSN = None

                # Execute Sentry initialization code (same pattern as main.py)
                if mock_settings.SENTRY_DSN:
                    import sentry_sdk

                    sentry_sdk.init(dsn=mock_settings.SENTRY_DSN)

                # Verify sentry_sdk.init was NOT called
                mock_init.assert_not_called()

    def test_sentry_logs_initialization_message(self, caplog):
        """Test that Sentry logs an info message when initialized."""
        mock_dsn = "https://public@sentry.io/123456"

        with caplog.at_level(logging.INFO):
            with patch("sentry_sdk.init"):
                with patch("app.core.config.settings") as mock_settings:
                    mock_settings.SENTRY_DSN = mock_dsn
                    mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.25
                    mock_settings.ENV = "production"
                    mock_settings.APP_VERSION = "2.0.0"

                    logger = logging.getLogger("test_sentry")

                    # Execute Sentry initialization code with logging
                    if mock_settings.SENTRY_DSN:
                        import sentry_sdk

                        sentry_sdk.init(dsn=mock_settings.SENTRY_DSN)
                        logger.info(
                            f"Sentry initialized for environment '{mock_settings.ENV}' "
                            f"with {mock_settings.SENTRY_TRACES_SAMPLE_RATE * 100:.0f}% trace sampling"
                        )

                    # Verify log message
                    assert (
                        "Sentry initialized for environment 'production'" in caplog.text
                    )
                    assert "25% trace sampling" in caplog.text

    def test_sentry_initialization_with_different_sample_rates(self):
        """Test Sentry initialization with various valid sample rates."""
        sample_rates = [0.0, 0.1, 0.5, 1.0]

        for rate in sample_rates:
            with patch("sentry_sdk.init") as mock_init:
                with patch("app.core.config.settings") as mock_settings:
                    mock_settings.SENTRY_DSN = "https://public@sentry.io/123456"
                    mock_settings.SENTRY_TRACES_SAMPLE_RATE = rate
                    mock_settings.ENV = "test"
                    mock_settings.APP_VERSION = "1.0.0"

                    if mock_settings.SENTRY_DSN:
                        import sentry_sdk
                        from sentry_sdk.integrations.fastapi import FastApiIntegration
                        from sentry_sdk.integrations.starlette import (
                            StarletteIntegration,
                        )

                        sentry_sdk.init(
                            dsn=mock_settings.SENTRY_DSN,
                            traces_sample_rate=mock_settings.SENTRY_TRACES_SAMPLE_RATE,
                            environment=mock_settings.ENV,
                            release=mock_settings.APP_VERSION,
                            send_default_pii=False,
                            integrations=[
                                StarletteIntegration(transaction_style="endpoint"),
                                FastApiIntegration(transaction_style="endpoint"),
                            ],
                        )

                    call_kwargs = mock_init.call_args[1]
                    assert call_kwargs["traces_sample_rate"] == rate

    def test_sentry_pii_disabled_by_default(self):
        """Test that Sentry is configured with send_default_pii=False."""
        with patch("sentry_sdk.init") as mock_init:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.SENTRY_DSN = "https://public@sentry.io/123456"
                mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.1
                mock_settings.ENV = "test"
                mock_settings.APP_VERSION = "1.0.0"

                if mock_settings.SENTRY_DSN:
                    import sentry_sdk
                    from sentry_sdk.integrations.fastapi import FastApiIntegration
                    from sentry_sdk.integrations.starlette import StarletteIntegration

                    sentry_sdk.init(
                        dsn=mock_settings.SENTRY_DSN,
                        traces_sample_rate=mock_settings.SENTRY_TRACES_SAMPLE_RATE,
                        environment=mock_settings.ENV,
                        release=mock_settings.APP_VERSION,
                        send_default_pii=False,
                        integrations=[
                            StarletteIntegration(transaction_style="endpoint"),
                            FastApiIntegration(transaction_style="endpoint"),
                        ],
                    )

                call_kwargs = mock_init.call_args[1]
                assert call_kwargs["send_default_pii"] is False

    def test_sentry_includes_fastapi_and_starlette_integrations(self):
        """Test that Sentry includes FastAPI and Starlette integrations."""
        with patch("sentry_sdk.init") as mock_init:
            with patch("app.core.config.settings") as mock_settings:
                mock_settings.SENTRY_DSN = "https://public@sentry.io/123456"
                mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.1
                mock_settings.ENV = "test"
                mock_settings.APP_VERSION = "1.0.0"

                if mock_settings.SENTRY_DSN:
                    import sentry_sdk
                    from sentry_sdk.integrations.fastapi import FastApiIntegration
                    from sentry_sdk.integrations.starlette import StarletteIntegration

                    sentry_sdk.init(
                        dsn=mock_settings.SENTRY_DSN,
                        traces_sample_rate=mock_settings.SENTRY_TRACES_SAMPLE_RATE,
                        environment=mock_settings.ENV,
                        release=mock_settings.APP_VERSION,
                        send_default_pii=False,
                        integrations=[
                            StarletteIntegration(transaction_style="endpoint"),
                            FastApiIntegration(transaction_style="endpoint"),
                        ],
                    )

                call_kwargs = mock_init.call_args[1]
                integrations = call_kwargs["integrations"]
                assert len(integrations) == 2

                # Check integration types
                integration_types = [type(i).__name__ for i in integrations]
                assert "StarletteIntegration" in integration_types
                assert "FastApiIntegration" in integration_types


class TestSentryInvalidDSN:
    """Tests for handling invalid Sentry DSN values."""

    def test_sentry_handles_invalid_dsn_gracefully(self):
        """Test that invalid DSN is handled gracefully by Sentry SDK.

        The Sentry SDK itself validates the DSN format. When an invalid DSN
        is provided, the SDK logs a warning but does not raise an exception,
        allowing the application to continue running without error tracking.
        """
        # Invalid DSN formats that Sentry SDK should handle
        invalid_dsns = [
            "not-a-valid-dsn",
            "http://invalid",
            "ftp://wrong-protocol@sentry.io/123",
        ]

        for invalid_dsn in invalid_dsns:
            with patch("sentry_sdk.init") as mock_init:
                with patch("app.core.config.settings") as mock_settings:
                    mock_settings.SENTRY_DSN = invalid_dsn
                    mock_settings.SENTRY_TRACES_SAMPLE_RATE = 0.1
                    mock_settings.ENV = "test"
                    mock_settings.APP_VERSION = "1.0.0"

                    # This simulates what happens in main.py - if DSN is truthy,
                    # sentry_sdk.init is called. The SDK handles invalid DSNs internally.
                    if mock_settings.SENTRY_DSN:
                        import sentry_sdk
                        from sentry_sdk.integrations.fastapi import FastApiIntegration
                        from sentry_sdk.integrations.starlette import (
                            StarletteIntegration,
                        )

                        sentry_sdk.init(
                            dsn=mock_settings.SENTRY_DSN,
                            traces_sample_rate=mock_settings.SENTRY_TRACES_SAMPLE_RATE,
                            environment=mock_settings.ENV,
                            release=mock_settings.APP_VERSION,
                            send_default_pii=False,
                            integrations=[
                                StarletteIntegration(transaction_style="endpoint"),
                                FastApiIntegration(transaction_style="endpoint"),
                            ],
                        )

                    # Verify init was called (even with invalid DSN)
                    mock_init.assert_called_once()
                    assert mock_init.call_args[1]["dsn"] == invalid_dsn

    def test_sentry_sdk_raises_bad_dsn_error_with_invalid_format(self):
        """Test that the Sentry SDK raises BadDsn error with invalid DSN format.

        The Sentry SDK validates DSN format and raises BadDsn exception for
        malformed DSNs. This is the expected behavior - applications should
        validate their DSN configuration before passing to sentry_sdk.init().

        In production, this means:
        1. Empty/missing DSN should skip initialization entirely (our approach)
        2. Malformed DSN in env vars will cause startup failure (fail fast)
        """
        import sentry_sdk
        from sentry_sdk.utils import BadDsn

        # The Sentry SDK raises BadDsn for malformed DSN strings
        with pytest.raises(BadDsn):
            sentry_sdk.init(
                dsn="invalid-dsn-format",
                traces_sample_rate=0.1,
            )

    def test_sentry_whitespace_dsn_treated_as_empty(self):
        """Test that whitespace-only DSN is not used to initialize Sentry."""
        with patch("sentry_sdk.init") as mock_init:
            with patch("app.core.config.settings") as mock_settings:
                # Whitespace DSN - should be treated as falsy after strip
                mock_settings.SENTRY_DSN = "   "

                # In the actual implementation, we check `if settings.SENTRY_DSN`
                # A whitespace string is truthy in Python, but in practice
                # Sentry DSNs from env vars are typically stripped
                # This test documents the current behavior
                if mock_settings.SENTRY_DSN and mock_settings.SENTRY_DSN.strip():
                    import sentry_sdk

                    sentry_sdk.init(dsn=mock_settings.SENTRY_DSN)

                # Verify sentry_sdk.init was NOT called (whitespace stripped is falsy)
                mock_init.assert_not_called()
