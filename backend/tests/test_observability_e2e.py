"""
End-to-end tests for observability with real Sentry and OTEL backends.

These tests verify that the observability facade correctly sends data
to real backend services. They require test credentials to be configured
via environment variables.

Environment Variables:
    SENTRY_TEST_DSN: Sentry DSN for a test project (required)
    OTEL_TEST_ENDPOINT: OTLP endpoint for a test collector (optional)
    OTEL_TEST_HEADERS: Headers for OTEL authentication, comma-separated key=value (optional)
    RUN_E2E_OBSERVABILITY_TESTS: Set to "true" to enable these tests

Local Usage:
    # Run with test credentials (Sentry + Grafana Cloud OTEL)
    export SENTRY_TEST_DSN="https://...@sentry.io/..."
    export OTEL_TEST_ENDPOINT="https://otlp-gateway-prod-us-central-0.grafana.net/otlp"
    export OTEL_TEST_HEADERS="Authorization=Basic ..."
    export RUN_E2E_OBSERVABILITY_TESTS=true
    pytest tests/test_observability_e2e.py -v -s

    # Run with just Sentry (OTEL-specific assertions will adapt)
    export SENTRY_TEST_DSN="https://...@sentry.io/..."
    export RUN_E2E_OBSERVABILITY_TESTS=true
    pytest tests/test_observability_e2e.py -v -s

    # Skip e2e tests (default behavior)
    pytest tests/test_observability_e2e.py -v

CI Setup (GitHub Actions):
    Add these secrets to your repository:
    - SENTRY_TEST_DSN: Your Sentry test project DSN
    - OTEL_TEST_ENDPOINT: Your OTLP collector endpoint (e.g., Grafana Cloud)
    - OTEL_TEST_HEADERS: Authentication headers for OTLP

    Example workflow step:
        - name: Run E2E Observability Tests
          env:
            RUN_E2E_OBSERVABILITY_TESTS: "true"
            SENTRY_TEST_DSN: ${{ secrets.SENTRY_TEST_DSN }}
            OTEL_TEST_ENDPOINT: ${{ secrets.OTEL_TEST_ENDPOINT }}
            OTEL_TEST_HEADERS: ${{ secrets.OTEL_TEST_HEADERS }}
          run: pytest tests/test_observability_e2e.py -v -s

Verification:
    After tests run, verify data appears in your backends:
    1. Sentry: Search for environment:"e2e-test" or the test_run_id in tags
    2. Grafana/OTEL: Query for service_name starting with "aiq-e2e-test"

Note:
    These tests are OPTIONAL and marked as skipped by default. They validate
    real integration with external services, which is useful for:
    - Verifying deployment configurations work
    - Testing after infrastructure changes
    - Validating credentials and connectivity
"""

from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from libs.observability.facade import ObservabilityFacade

# Test configuration constants
FIXTURE_FLUSH_TIMEOUT_SECONDS = 5.0  # Timeout for fixture teardown flush
FINAL_FLUSH_TIMEOUT_SECONDS = 10.0  # Extended timeout for final verification test
COUNTER_TEST_ITERATIONS = 5  # Number of counter increments to test batching
HISTOGRAM_TEST_VALUES_MS = [
    10,
    25,
    50,
    75,
    100,
    150,
    200,
    500,
]  # Realistic latency distribution

# Skip all tests in this module unless explicitly enabled
pytestmark = [
    pytest.mark.skipif(
        os.environ.get("RUN_E2E_OBSERVABILITY_TESTS", "").lower() != "true",
        reason="E2E observability tests disabled. Set RUN_E2E_OBSERVABILITY_TESTS=true to enable.",
    ),
    pytest.mark.e2e,  # Mark as e2e tests for selective running
]


@pytest.fixture(scope="module")
def test_run_id() -> str:
    """Generate a unique ID for this test run to help identify data in backends."""
    return f"e2e-test-{uuid.uuid4().hex[:8]}"


@pytest.fixture(scope="module")
def sentry_dsn() -> str | None:
    """Get Sentry test DSN from environment."""
    dsn = os.environ.get("SENTRY_TEST_DSN")
    if not dsn:
        pytest.skip("SENTRY_TEST_DSN not configured")
    return dsn


@pytest.fixture(scope="module")
def otel_endpoint() -> str | None:
    """Get OTEL test endpoint from environment."""
    return os.environ.get("OTEL_TEST_ENDPOINT")


@pytest.fixture(scope="module")
def otel_headers() -> str:
    """Get OTEL headers string from environment (comma-separated key=value)."""
    return os.environ.get("OTEL_TEST_HEADERS", "")


@pytest.fixture(scope="module")
def e2e_config_file(
    tmp_path_factory: pytest.TempPathFactory,
    test_run_id: str,
    sentry_dsn: str,
    otel_endpoint: str | None,
    otel_headers: str,
) -> Path:
    """Create a temporary YAML config file for e2e tests."""
    config_dir = tmp_path_factory.mktemp("config")
    config_file = config_dir / "e2e_observability.yaml"

    # Determine if OTEL should be enabled based on endpoint availability
    otel_enabled = otel_endpoint is not None

    config_content = f"""
# E2E Test Configuration - Generated for test run {test_run_id}
sentry:
  enabled: true
  dsn: "{sentry_dsn}"
  environment: "e2e-test"
  release: "test-{test_run_id}"
  traces_sample_rate: 1.0
  profiles_sample_rate: 0.0
  send_default_pii: false

otel:
  enabled: {str(otel_enabled).lower()}
  service_name: "aiq-e2e-test"
  service_version: "{test_run_id}"
  endpoint: "{otel_endpoint or ''}"
  otlp_headers: "{otel_headers}"
  exporter: "{'otlp' if otel_enabled else 'none'}"
  metrics_enabled: true
  traces_enabled: true
  traces_sample_rate: 1.0
  logs_enabled: false
  prometheus_enabled: false
  insecure: false

routing:
  errors: sentry
  metrics: otel
  traces: {'both' if otel_enabled else 'sentry'}
"""
    config_file.write_text(config_content)
    return config_file


@pytest.fixture(scope="module")
def observability_facade(e2e_config_file: Path, test_run_id: str):
    """Initialize the observability facade with real backends using config file."""
    from libs.observability import observability

    # Reset facade state if previously initialized (use public property)
    if observability.is_initialized:
        observability.shutdown()

    # Initialize with our e2e test config file
    result = observability.init(
        config_path=str(e2e_config_file),
        service_name=f"aiq-e2e-test-{test_run_id}",
        environment="e2e-test",
    )

    if not result:
        pytest.skip("Failed to initialize observability with real backends")

    yield observability

    # Flush and shutdown after tests
    observability.flush(timeout=FIXTURE_FLUSH_TIMEOUT_SECONDS)
    observability.shutdown()


class TestSentryIntegration:
    """Tests for Sentry integration with real backend."""

    def test_capture_error_sends_to_sentry(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Test that errors are captured and sent to Sentry.

        Note: This test verifies the operation completes without error.
        Manual verification in Sentry is needed to confirm receipt.
        """
        # Create a unique error message for this test
        error_message = f"E2E Test Error [{test_run_id}] - {time.time()}"

        try:
            raise ValueError(error_message)
        except ValueError as e:
            event_id = observability_facade.capture_error(
                e,
                context={
                    "test_run_id": test_run_id,
                    "test_name": "test_capture_error_sends_to_sentry",
                    "timestamp": time.time(),
                },
                tags={
                    "test_type": "e2e",
                    "backend": "sentry",
                },
            )

        # Verify we got an event ID back (indicates successful capture)
        assert event_id is not None, "Expected event_id from Sentry capture"
        print(f"\nSentry event captured: {event_id}")
        print(f"Search in Sentry for: {error_message}")

    def test_capture_error_with_trace_context(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Test that errors include trace context when captured within a span."""
        error_message = f"E2E Traced Error [{test_run_id}] - {time.time()}"

        with observability_facade.start_span(
            "e2e_error_test_span",
            attributes={"test_run_id": test_run_id},
        ) as span:
            span.set_attribute("operation", "error_capture_test")

            try:
                raise RuntimeError(error_message)
            except RuntimeError as e:
                event_id = observability_facade.capture_error(
                    e,
                    context={
                        "test_run_id": test_run_id,
                        "within_span": True,
                    },
                    tags={"test_type": "e2e_traced"},
                )

        assert event_id is not None
        print(f"\nSentry traced error captured: {event_id}")
        print("Verify in Sentry that the error includes trace_id and span_id")


class TestOTELIntegration:
    """Tests for OpenTelemetry integration with real backend."""

    def test_record_metric_counter(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Test that counter metrics are recorded and sent to OTEL.

        Note: Metrics are typically batched and sent periodically.
        """
        metric_name = f"e2e.test.counter.{test_run_id.replace('-', '_')}"

        # Record multiple counter increments to test batching behavior
        for i in range(COUNTER_TEST_ITERATIONS):
            observability_facade.record_metric(
                metric_name,
                1,  # Standard counter increment
                labels={
                    "test_run_id": test_run_id,
                    "iteration": str(i),
                },
                metric_type="counter",
            )

        # Verify facade remains in valid state after recording
        assert (
            observability_facade.is_initialized
        ), "Facade should remain initialized after recording metrics"

        print(f"\nRecorded counter metric: {metric_name}")
        print("Verify in your metrics backend (e.g., Grafana) for this metric")

    def test_record_metric_histogram(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Test that histogram metrics are recorded and sent to OTEL."""
        metric_name = f"e2e.test.histogram.{test_run_id.replace('-', '_')}"

        # Record realistic latency values to create a distribution
        for value in HISTOGRAM_TEST_VALUES_MS:
            observability_facade.record_metric(
                metric_name,
                value,
                labels={"test_run_id": test_run_id},
                metric_type="histogram",
                unit="ms",
            )

        # Verify facade remains in valid state after recording
        assert (
            observability_facade.is_initialized
        ), "Facade should remain initialized after recording metrics"

        print(f"\nRecorded histogram metric: {metric_name}")
        print(f"Values: {HISTOGRAM_TEST_VALUES_MS}")

    def test_create_span(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Test that spans are created and sent to OTEL."""
        span_name = f"e2e_test_span_{test_run_id}"

        with observability_facade.start_span(
            span_name,
            kind="internal",
            attributes={
                "test_run_id": test_run_id,
                "test_type": "e2e",
            },
        ) as span:
            span.set_attribute("step", "initial")

            # Simulate some work
            time.sleep(0.1)

            span.add_event("processing_started", {"items": 10})

            # More work
            time.sleep(0.1)

            span.add_event("processing_completed", {"items_processed": 10})
            span.set_attribute("step", "completed")
            span.set_status("ok")

        print(f"\nSpan created: {span_name}")
        print("Verify in your tracing backend (e.g., Grafana Tempo)")


class TestDualTracingMode:
    """Tests for dual tracing mode (both Sentry and OTEL receive traces)."""

    def test_nested_spans_sent_to_both_backends(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Test that nested spans are sent to both Sentry and OTEL."""
        outer_span_name = f"e2e_outer_span_{test_run_id}"
        inner_span_name = f"e2e_inner_span_{test_run_id}"

        with observability_facade.start_span(
            outer_span_name,
            kind="server",
            attributes={"test_run_id": test_run_id},
        ) as outer:
            outer.set_attribute("layer", "outer")
            time.sleep(0.05)

            with observability_facade.start_span(
                inner_span_name,
                kind="internal",
            ) as inner:
                inner.set_attribute("layer", "inner")
                time.sleep(0.05)

                # Record a metric within the span context
                observability_facade.record_metric(
                    "e2e.nested_span.operations",
                    1,
                    labels={"test_run_id": test_run_id},
                    metric_type="counter",
                )

                inner.set_status("ok")

            outer.set_status("ok")

        print(f"\nNested spans created: {outer_span_name} -> {inner_span_name}")
        print("Verify in both Sentry Performance and OTEL tracing backend")


class TestRealisticWorkflow:
    """Tests simulating realistic application workflows."""

    def test_http_request_workflow(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Simulate a complete HTTP request workflow with all telemetry types."""
        endpoint = f"/api/e2e-test/{test_run_id}"

        with observability_facade.start_span(
            "http_request",
            kind="server",
            attributes={"http.method": "POST", "http.url": endpoint},
        ) as request_span:
            request_span.set_http_attributes(
                method="POST",
                url=endpoint,
                route="/api/e2e-test/{test_run_id}",
            )

            # Record request received metric
            observability_facade.record_metric(
                "e2e.http.requests.total",
                1,
                labels={
                    "method": "POST",
                    "endpoint": endpoint,
                    "test_run_id": test_run_id,
                },
                metric_type="counter",
            )

            # Simulate database query
            with observability_facade.start_span(
                "db_query",
                kind="client",
            ) as db_span:
                db_span.set_attribute("db.system", "postgresql")
                db_span.set_attribute("db.operation", "SELECT")
                time.sleep(0.02)  # Simulate query time

                observability_facade.record_metric(
                    "e2e.db.query.duration",
                    20.0,
                    labels={"operation": "SELECT", "test_run_id": test_run_id},
                    metric_type="histogram",
                    unit="ms",
                )
                db_span.set_status("ok")

            # Simulate business logic
            request_span.add_event("business_logic_start")
            time.sleep(0.05)
            request_span.add_event("business_logic_complete")

            # Record response
            request_span.set_http_attributes(
                method="POST",
                url=endpoint,
                status_code=200,
            )
            request_span.set_status("ok")

            # Record request duration
            observability_facade.record_metric(
                "e2e.http.request.duration",
                100.0,
                labels={
                    "method": "POST",
                    "status_code": "200",
                    "test_run_id": test_run_id,
                },
                metric_type="histogram",
                unit="ms",
            )

        print(f"\nHTTP request workflow completed for: {endpoint}")

    def test_error_handling_workflow(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Simulate an error handling workflow with trace correlation."""
        endpoint = f"/api/e2e-error/{test_run_id}"
        error_message = f"Simulated E2E error [{test_run_id}]"

        with observability_facade.start_span(
            "http_request_with_error",
            kind="server",
            attributes={"http.method": "GET", "http.url": endpoint},
        ) as request_span:
            request_span.set_http_attributes(method="GET", url=endpoint)

            try:
                # Simulate work that fails
                time.sleep(0.01)
                raise ValueError(error_message)

            except ValueError as e:
                # Record error metrics
                observability_facade.record_metric(
                    "e2e.http.errors.total",
                    1,
                    labels={
                        "error_type": "ValueError",
                        "test_run_id": test_run_id,
                    },
                    metric_type="counter",
                )

                # Capture error with trace context
                event_id = observability_facade.capture_error(
                    e,
                    context={
                        "endpoint": endpoint,
                        "test_run_id": test_run_id,
                    },
                    tags={
                        "test_type": "e2e_error_workflow",
                    },
                )

                request_span.set_http_attributes(
                    method="GET",
                    url=endpoint,
                    status_code=500,
                )
                request_span.set_status("error", str(e))

        assert event_id is not None
        print(f"\nError workflow completed. Sentry event: {event_id}")
        print("Verify error has trace context in Sentry")


class TestFlushAndVerification:
    """Tests for flushing data and preparing for verification."""

    def test_flush_all_data(
        self, observability_facade: "ObservabilityFacade", test_run_id: str
    ) -> None:
        """Flush all pending data to backends.

        Note: The observability_facade fixture also flushes on teardown.
        This test provides an explicit flush with verification output.
        """
        # Record a final marker metric
        observability_facade.record_metric(
            "e2e.test.completed",
            1,  # Standard counter increment to mark completion
            labels={"test_run_id": test_run_id},
            metric_type="counter",
        )

        # Flush with generous timeout to ensure async telemetry is sent
        observability_facade.flush(timeout=FINAL_FLUSH_TIMEOUT_SECONDS)

        # Verify facade is still healthy after flush
        assert (
            observability_facade.is_initialized
        ), "Facade should remain initialized after flush"

        print(f"\n{'='*60}")
        print("E2E OBSERVABILITY TEST COMPLETED")
        print(f"{'='*60}")
        print(f"Test Run ID: {test_run_id}")
        print("\nTo verify data was received:")
        print(f"  1. Search Sentry for: test_run_id:{test_run_id}")
        print(f"  2. Search metrics for: test_run_id={test_run_id}")
        print(f"  3. Search traces for: test_run_id={test_run_id}")
        print(f"{'='*60}")
