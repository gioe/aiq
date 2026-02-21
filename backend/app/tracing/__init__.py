"""
OpenTelemetry distributed tracing integration.
"""

from app.tracing.setup import setup_tracing, shutdown_tracing

__all__ = ["setup_tracing", "shutdown_tracing"]
