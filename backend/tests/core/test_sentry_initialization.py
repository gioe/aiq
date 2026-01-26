"""
Tests for Sentry SDK initialization in main.py.

These tests verify that the init_sentry() function correctly initializes Sentry
based on the provided configuration.
"""
import logging
from unittest.mock import patch

import pytest
from sentry_sdk.utils import BadDsn


class TestInitSentry:
    """Tests for the init_sentry() function."""

    def test_returns_true_when_dsn_is_provided(self):
        """Test that init_sentry returns True when a valid DSN is provided."""
        with patch("app.main.sentry_sdk.init"):
            from app.main import init_sentry

            result = init_sentry(
                dsn="https://public@sentry.io/123456",
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )
            assert result is True

    def test_returns_false_when_dsn_is_empty(self):
        """Test that init_sentry returns False when DSN is empty string."""
        with patch("app.main.sentry_sdk.init") as mock_init:
            from app.main import init_sentry

            result = init_sentry(
                dsn="",
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )
            assert result is False
            mock_init.assert_not_called()

    def test_returns_false_when_dsn_is_none(self):
        """Test that init_sentry returns False when DSN is None."""
        with patch("app.main.sentry_sdk.init") as mock_init:
            from app.main import init_sentry

            result = init_sentry(
                dsn=None,  # type: ignore[arg-type]
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )
            assert result is False
            mock_init.assert_not_called()

    def test_calls_sentry_sdk_init_with_correct_parameters(self):
        """Test that sentry_sdk.init is called with the correct parameters."""
        with patch("app.main.sentry_sdk.init") as mock_init:
            from app.main import init_sentry

            init_sentry(
                dsn="https://public@sentry.io/123456",
                traces_sample_rate=0.25,
                environment="production",
                release="2.0.0",
            )

            mock_init.assert_called_once()
            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["dsn"] == "https://public@sentry.io/123456"
            assert call_kwargs["traces_sample_rate"] == pytest.approx(0.25)
            assert call_kwargs["environment"] == "production"
            assert call_kwargs["release"] == "2.0.0"
            assert call_kwargs["send_default_pii"] is False

    def test_includes_starlette_and_fastapi_integrations(self):
        """Test that Sentry is initialized with Starlette and FastAPI integrations."""
        with patch("app.main.sentry_sdk.init") as mock_init:
            from app.main import init_sentry

            init_sentry(
                dsn="https://public@sentry.io/123456",
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )

            call_kwargs = mock_init.call_args[1]
            integrations = call_kwargs["integrations"]
            assert len(integrations) == 2

            integration_types = [type(i).__name__ for i in integrations]
            assert "StarletteIntegration" in integration_types
            assert "FastApiIntegration" in integration_types

    def test_pii_disabled_by_default(self):
        """Test that send_default_pii is always False."""
        with patch("app.main.sentry_sdk.init") as mock_init:
            from app.main import init_sentry

            init_sentry(
                dsn="https://public@sentry.io/123456",
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )

            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["send_default_pii"] is False

    def test_logs_initialization_message(self):
        """Test that init_sentry logs an info message when initialized."""
        with patch("app.main.sentry_sdk.init"):
            with patch("app.main.logger") as mock_logger:
                from app.main import init_sentry

                init_sentry(
                    dsn="https://public@sentry.io/123456",
                    traces_sample_rate=0.25,
                    environment="production",
                    release="2.0.0",
                )

                # Verify logger.info was called with expected message
                mock_logger.info.assert_called_once()
                log_message = mock_logger.info.call_args[0][0]
                assert "Sentry initialized for environment 'production'" in log_message
                assert "25% trace sampling" in log_message

    def test_does_not_log_when_dsn_is_empty(self, caplog):
        """Test that no log message is produced when DSN is empty."""
        with patch("app.main.sentry_sdk.init"):
            from app.main import init_sentry

            with caplog.at_level(logging.INFO):
                init_sentry(
                    dsn="",
                    traces_sample_rate=0.1,
                    environment="test",
                    release="1.0.0",
                )

            assert "Sentry initialized" not in caplog.text

    @pytest.mark.parametrize(
        "sample_rate",
        [0.0, 0.1, 0.5, 1.0],
        ids=["0%", "10%", "50%", "100%"],
    )
    def test_various_sample_rates(self, sample_rate):
        """Test init_sentry with various valid sample rates."""
        with patch("app.main.sentry_sdk.init") as mock_init:
            from app.main import init_sentry

            init_sentry(
                dsn="https://public@sentry.io/123456",
                traces_sample_rate=sample_rate,
                environment="test",
                release="1.0.0",
            )

            call_kwargs = mock_init.call_args[1]
            assert call_kwargs["traces_sample_rate"] == pytest.approx(sample_rate)


class TestSentryInvalidDSN:
    """Tests for Sentry SDK behavior with invalid DSN values."""

    def test_invalid_dsn_raises_bad_dsn_error(self):
        """Test that the Sentry SDK raises BadDsn for malformed DSN strings.

        This verifies the actual Sentry SDK behavior - malformed DSNs cause
        initialization to fail fast, which is the expected behavior.
        """
        from app.main import init_sentry

        with pytest.raises(BadDsn):
            init_sentry(
                dsn="invalid-dsn-format",
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )

    def test_whitespace_dsn_is_truthy_but_invalid(self):
        """Test that whitespace-only DSN passes the truthy check but fails initialization.

        Important: The init_sentry function uses `if not dsn:` which means whitespace
        strings are truthy and will attempt initialization. This will fail with BadDsn
        from the Sentry SDK, which is the correct fail-fast behavior.
        """
        from app.main import init_sentry

        # Whitespace is truthy in Python, so init_sentry will try to initialize
        # This will raise BadDsn because whitespace is not a valid DSN
        with pytest.raises(BadDsn):
            init_sentry(
                dsn="   ",
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )

    @pytest.mark.parametrize(
        "invalid_dsn",
        [
            "not-a-valid-dsn",
            "http://invalid",
            "ftp://wrong-protocol@sentry.io/123",
            "https://missing-project-id@sentry.io/",
        ],
        ids=["plain-string", "http-only", "ftp-protocol", "no-project-id"],
    )
    def test_various_invalid_dsn_formats(self, invalid_dsn):
        """Test that various invalid DSN formats raise BadDsn."""
        from app.main import init_sentry

        with pytest.raises(BadDsn):
            init_sentry(
                dsn=invalid_dsn,
                traces_sample_rate=0.1,
                environment="test",
                release="1.0.0",
            )
