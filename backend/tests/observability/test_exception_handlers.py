"""
Tests for exception handlers in main.py.

This module tests that exception handlers properly record metrics
for observability while maintaining existing analytics tracking.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from gioe_libs.alerting.alerting import ErrorCategory, ErrorSeverity
from tests.conftest import create_full_test_app


class TestAlertManagerSendAlert:
    """Tests for AlertManager.send_alert integration in generic_exception_handler."""

    @pytest.fixture
    def test_app(self):
        return create_full_test_app()

    @pytest.fixture
    def mock_alert_manager(self):
        mgr = MagicMock()
        mgr.send_alert = MagicMock()
        return mgr

    def test_send_alert_called_with_critical_severity_and_server_error_category(
        self, test_app, mock_alert_manager
    ):
        """Trigger a 500, assert send_alert is called with CRITICAL/SERVER_ERROR."""

        @test_app.get("/test-alert-send")
        async def raise_500():
            raise RuntimeError("boom")

        with patch("app.main._alert_manager", mock_alert_manager):
            with TestClient(test_app, raise_server_exceptions=False) as client:
                response = client.get("/test-alert-send")

        assert response.status_code == 500
        mock_alert_manager.send_alert.assert_called_once()
        error_arg = mock_alert_manager.send_alert.call_args[0][0]
        assert error_arg.severity == ErrorSeverity.CRITICAL
        assert error_arg.category == ErrorCategory.SERVER_ERROR

    def test_send_alert_not_called_when_alert_manager_is_none(self, test_app):
        """When _alert_manager is None, no send_alert call occurs (no AttributeError)."""

        @test_app.get("/test-no-alert-manager")
        async def raise_500():
            raise RuntimeError("boom without manager")

        with patch("app.main._alert_manager", None):
            with TestClient(test_app, raise_server_exceptions=False) as client:
                response = client.get("/test-no-alert-manager")

        assert response.status_code == 500


class TestExceptionHandlerMetrics:
    """Tests for metrics integration in exception handlers."""

    def test_http_exception_handler_exists(self):
        """Test that HTTP exception handler is registered."""
        from app.main import create_application
        from starlette.exceptions import HTTPException as StarletteHTTPException

        app = create_application()
        assert StarletteHTTPException in app.exception_handlers
        # The handler should be registered
        handler = app.exception_handlers[StarletteHTTPException]
        assert handler is not None

    def test_validation_exception_handler_exists(self):
        """Test that validation exception handler is registered."""
        from app.main import create_application
        from fastapi.exceptions import RequestValidationError

        app = create_application()
        assert RequestValidationError in app.exception_handlers
        handler = app.exception_handlers[RequestValidationError]
        assert handler is not None

    def test_generic_exception_handler_exists(self):
        """Test that generic exception handler is registered."""
        from app.main import create_application

        app = create_application()
        assert Exception in app.exception_handlers
        handler = app.exception_handlers[Exception]
        assert handler is not None

    def test_observability_import_is_present(self):
        """Test that observability is imported in main.py."""
        # This test verifies the unified observability integration is set up
        import app.main

        assert hasattr(app.main, "observability")
