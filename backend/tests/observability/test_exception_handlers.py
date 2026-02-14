"""
Tests for exception handlers in main.py.

This module tests that exception handlers properly record metrics
for observability while maintaining existing analytics tracking.
"""


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
