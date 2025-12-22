"""
Request/response logging middleware for tracking API interactions.
"""
import json
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from typing import Callable

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests and outgoing responses.

    Logs:
    - Request method, path, headers
    - Response status code
    - Request body (for POST/PUT/PATCH requests, excluding sensitive endpoints)
    - User identifier (from auth header if present)
    """

    # Endpoints to skip logging request body (sensitive data)
    SKIP_BODY_LOGGING_PATHS = [
        "/auth/login",
        "/auth/register",
        "/auth/refresh",
    ]

    def __init__(
        self, app, log_request_body: bool = True, log_response_body: bool = False
    ):
        """
        Initialize request logging middleware.

        Args:
            app: FastAPI application
            log_request_body: Whether to log request bodies (default: True)
            log_response_body: Whether to log response bodies (default: False, can be verbose)
        """
        super().__init__(app)
        self.log_request_body = log_request_body
        self.log_response_body = log_response_body

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log details.

        Args:
            request: Incoming request
            call_next: Next middleware/endpoint in chain

        Returns:
            Response from the endpoint
        """
        # Extract user identifier from Authorization header if present
        user_identifier = "anonymous"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # Extract first few chars of token for logging (not the full token)
            token_preview = auth_header[7:17] + "..."
            user_identifier = f"token:{token_preview}"

        # Log request
        request_log = {
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "user_identifier": user_identifier,
            "client_host": request.client.host if request.client else "unknown",
        }

        # Log request body for non-sensitive endpoints
        if (
            self.log_request_body
            and request.method in ["POST", "PUT", "PATCH"]
            and not any(
                path in str(request.url.path) for path in self.SKIP_BODY_LOGGING_PATHS
            )
        ):
            try:
                body = await request.body()
                if body:
                    # Try to parse as JSON for better logging
                    try:
                        body_json = json.loads(body.decode("utf-8"))
                        request_log["body"] = body_json
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_log["body"] = "<binary or non-JSON data>"

                    # Re-construct request with body since we've consumed it
                    async def receive():
                        return {"type": "http.request", "body": body}

                    request._receive = receive
            except Exception as e:
                logger.debug(f"Could not read request body: {e}")

        logger.info(f"Incoming request: {json.dumps(request_log)}")

        # Process request
        response = await call_next(request)

        # Log response
        response_log = {
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "user_identifier": user_identifier,
        }

        # Log response status
        if response.status_code >= 500:
            logger.error(f"Server error response: {json.dumps(response_log)}")
        elif response.status_code >= 400:
            logger.warning(f"Client error response: {json.dumps(response_log)}")
        else:
            logger.info(f"Successful response: {json.dumps(response_log)}")

        return response
