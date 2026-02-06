"""Unified observability abstraction for AIQ services.

This package provides a single API for application-level instrumentation
that routes to the appropriate backend systems:
- Errors → Sentry (superior alerting, grouping, and debugging UX)
- Metrics → OpenTelemetry/Prometheus (for Grafana dashboards)
- Traces → Configurable (OTEL, Sentry Performance, or both)

Usage:
    from libs.observability import observability

    # Initialize at application startup
    observability.init(
        config_path="config/observability.yaml",
        service_name="my-service",
    )

    # Capture errors (routed to Sentry)
    try:
        risky_operation()
    except Exception as e:
        observability.capture_error(e, context={"operation": "risky"})
        raise

    # Record metrics (routed to OTEL/Prometheus)
    observability.record_metric(
        name="requests.processed",
        value=1,
        labels={"endpoint": "/api/test"},
        metric_type="counter",
    )

    # Distributed tracing
    with observability.start_span("process_request") as span:
        span.set_attribute("user_id", user.id)
        # ... do work

    # Record structured events
    observability.record_event(
        "user.signup",
        data={"user_id": "123", "method": "oauth"},
        tags={"source": "web"},
    )

    # Set user context for error tracking
    observability.set_user("user-123", username="alice", email="alice@example.com")

    # Set additional context
    observability.set_context("request", {"url": "/api/test", "method": "POST"})
"""

from libs.observability.facade import ObservabilityFacade

# Singleton instance for application use
observability = ObservabilityFacade()

__all__ = ["observability", "ObservabilityFacade"]
