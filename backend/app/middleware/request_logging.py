"""
Request/response logging middleware for tracking API interactions.
"""
import logging
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

from app.core.logging_config import request_id_context

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests and outgoing responses.

    Logs:
    - Request method, path, client host
    - Response status code and duration
    - User identifier (from auth header if present)
    - Request ID for correlation
    """

    def __init__(self, app):
        """
        Initialize request logging middleware.

        Args:
            app: FastAPI application
        """
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint in chain

        Returns:
            Response from the endpoint
        """
        # Generate or extract request ID for correlation
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = request_id_context.set(request_id)

        try:
            start_time = time.time()

            # Extract user identifier from Authorization header if present
            user_identifier = "anonymous"
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                # Extract first few chars of token for logging (not the full token)
                token_preview = auth_header[7:17] + "..."
                user_identifier = f"token:{token_preview}"

            method = request.method
            path = str(request.url.path)
            client_host = request.client.host if request.client else "unknown"

            # Log incoming request with structured fields
            logger.info(
                "Incoming request",
                extra={
                    "method": method,
                    "path": path,
                    "client_host": client_host,
                    "user_identifier": user_identifier,
                },
            )

            # Process request
            response = await call_next(request)

            # Calculate duration in milliseconds
            duration_ms = round((time.time() - start_time) * 1000, 2)
            status_code = response.status_code

            # Add request_id header to response for client-side correlation
            try:
                response.headers["X-Request-ID"] = request_id
            except (AttributeError, TypeError, RuntimeError):
                # Some response types (e.g., StreamingResponse) may not support header modification
                logger.debug(
                    f"Could not add X-Request-ID header to response type: {type(response).__name__}"
                )

            # Log response with structured fields
            extra_fields = {
                "method": method,
                "path": path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client_host": client_host,
                "user_identifier": user_identifier,
            }

            if status_code >= 500:
                logger.error("Server error response", extra=extra_fields)
            elif status_code >= 400:
                logger.warning("Client error response", extra=extra_fields)
            else:
                logger.info("Request completed", extra=extra_fields)

            return response
        finally:
            # Reset context to prevent request ID leaking between requests
            request_id_context.reset(token)
