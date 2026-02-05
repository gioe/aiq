"""
Performance monitoring middleware for tracking API response times.
"""
import time
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable
from app.core.analytics import AnalyticsTracker
from app.observability import metrics

logger = logging.getLogger(__name__)


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor and log API endpoint performance.

    Tracks:
    - Request processing time
    - Slow queries (> threshold)
    - Response status codes
    """

    def __init__(self, app, slow_request_threshold: float = 1.0):
        """
        Initialize performance monitoring middleware.

        Args:
            app: FastAPI application
            slow_request_threshold: Time in seconds to consider a request slow (default: 1.0s)
        """
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and track performance metrics.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint in chain

        Returns:
            Response from the endpoint
        """
        start_time = time.time()

        # Process request
        response = await call_next(request)

        # Calculate processing time
        process_time = time.time() - start_time

        # Add custom header with processing time
        response.headers["X-Process-Time"] = str(round(process_time, 4))

        # Record OpenTelemetry metrics
        metrics.record_http_request(
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
            duration=process_time,
        )

        # Log slow requests and track analytics
        if process_time > self.slow_request_threshold:
            logger.warning(
                f"Slow request: {request.method} {request.url.path} "
                f"took {process_time:.4f}s (threshold: {self.slow_request_threshold}s)"
            )
            # Track slow request analytics
            AnalyticsTracker.track_slow_request(
                method=request.method,
                path=str(request.url.path),
                duration_seconds=process_time,
                status_code=response.status_code,
            )

        # Log all requests in debug mode
        logger.debug(
            f"{request.method} {request.url.path} "
            f"- Status: {response.status_code} "
            f"- Time: {process_time:.4f}s"
        )

        return response
