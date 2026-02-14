"""
FastAPI middleware for automatic rate limiting.

Provides middleware to automatically apply rate limiting to all requests
with customizable identifier resolution and response headers.
"""
import logging

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from typing import Callable, Optional, Awaitable, TypedDict

from .limiter import RateLimiter
from app.core.auth.ip_extraction import get_secure_client_ip
from app.core.auth.security_audit import SecurityAuditLogger

logger = logging.getLogger(__name__)

_security_logger = SecurityAuditLogger()


class EndpointLimitConfig(TypedDict):
    """Configuration for per-endpoint rate limits."""

    limit: int
    window: int


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for automatic rate limiting.

    Applies rate limiting to all requests passing through it.
    Adds rate limit headers to responses.
    Supports per-endpoint rate limit overrides.

    Example:
        ```python
        from fastapi import FastAPI
        from ratelimit import RateLimiter, RateLimitMiddleware

        app = FastAPI()
        limiter = RateLimiter(default_limit=100, default_window=60)

        app.add_middleware(
            RateLimitMiddleware,
            limiter=limiter,
            identifier_resolver=lambda request: request.client.host,
            endpoint_limits={
                "/v1/admin/reliability": {"limit": 10, "window": 60},
            }
        )
        ```
    """

    def __init__(
        self,
        app,
        limiter: RateLimiter,
        identifier_resolver: Optional[Callable[[Request], str]] = None,
        skip_paths: Optional[list[str]] = None,
        add_headers: bool = True,
        endpoint_limits: Optional[dict[str, EndpointLimitConfig]] = None,
    ):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            limiter: RateLimiter instance
            identifier_resolver: Function to extract identifier from request
                                (default: uses client IP)
            skip_paths: List of paths to skip rate limiting (e.g., /health)
            add_headers: Whether to add rate limit headers to responses
            endpoint_limits: Per-endpoint rate limit overrides.
                           Dict of path -> EndpointLimitConfig.
                           Each endpoint uses a separate rate limit bucket,
                           independent of the default rate limit.
        """
        super().__init__(app)
        self.limiter = limiter
        self.identifier_resolver = identifier_resolver or self._default_identifier
        self.skip_paths = skip_paths or []
        self.add_headers = add_headers
        self.endpoint_limits = endpoint_limits or {}

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """
        Process request with rate limiting.

        Args:
            request: Incoming request
            call_next: Next middleware/handler

        Returns:
            Response with rate limit headers
        """
        # Check if path should skip rate limiting
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # Resolve identifier
        try:
            identifier = self.identifier_resolver(request)
        except Exception as e:
            # If identifier resolution fails, allow request but log
            logger.warning(
                "Rate limit identifier resolution failed: %s",
                e,
                exc_info=True,
            )
            return await call_next(request)

        # Get endpoint-specific limits or use defaults
        path = request.url.path
        limit: Optional[int] = None
        window: Optional[int] = None

        if path in self.endpoint_limits:
            endpoint_config = self.endpoint_limits[path]
            limit = endpoint_config.get("limit")
            window = endpoint_config.get("window")
            # Use path-specific identifier to separate rate limits per endpoint
            # Using "::endpoint::" delimiter to avoid collision with identifiers that contain colons
            identifier = f"{identifier}::endpoint::{path}"

        # Check rate limit with endpoint-specific or default limits
        allowed, metadata = self.limiter.check(identifier, limit=limit, window=window)

        if not allowed:
            # Log rate limit event for security monitoring
            client_ip = get_secure_client_ip(request)
            _security_logger.log_rate_limit_exceeded(
                ip=client_ip,
                path=path,
                limit=metadata.get("limit", 0),
            )
            return self._rate_limit_response(metadata)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        if self.add_headers:
            self._add_rate_limit_headers(response, metadata)

        return response

    def _default_identifier(self, request: Request) -> str:
        """
        Default identifier resolver using client IP.

        Uses secure IP extraction that only trusts infrastructure-set headers
        (X-Envoy-External-Address from Railway's Envoy proxy) to prevent
        IP spoofing attacks that could bypass rate limiting.

        Args:
            request: Incoming request

        Returns:
            Client IP address
        """
        return get_secure_client_ip(request)

    def _rate_limit_response(self, metadata: dict) -> JSONResponse:
        """
        Create rate limit exceeded response.

        Args:
            metadata: Rate limit metadata

        Returns:
            JSONResponse with 429 status
        """
        response = JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "Too many requests. Please try again later.",
                "retry_after": metadata.get("retry_after", 0),
            },
        )

        # Add rate limit headers
        self._add_rate_limit_headers(response, metadata)

        # Add Retry-After header (standard HTTP header)
        retry_after = metadata.get("retry_after", 0)
        if retry_after > 0:
            response.headers["Retry-After"] = str(retry_after)

        return response

    def _add_rate_limit_headers(self, response: Response, metadata: dict) -> None:
        """
        Add rate limit headers to response.

        Uses standard RateLimit headers (draft RFC):
        - X-RateLimit-Limit: Request quota
        - X-RateLimit-Remaining: Remaining requests
        - X-RateLimit-Reset: When quota resets (Unix timestamp)

        Args:
            response: Response to add headers to
            metadata: Rate limit metadata
        """
        response.headers["X-RateLimit-Limit"] = str(metadata.get("limit", 0))
        response.headers["X-RateLimit-Remaining"] = str(metadata.get("remaining", 0))
        response.headers["X-RateLimit-Reset"] = str(metadata.get("reset_at", 0))


def get_user_identifier(request: Request) -> str:
    """
    Extract user ID from authenticated request.

    Falls back to IP address if not authenticated. Uses secure IP extraction
    that only trusts infrastructure-set headers to prevent IP spoofing attacks.

    Args:
        request: Incoming request

    Returns:
        User ID (format: "user:{id}") or IP address (format: "ip:{address}")
    """
    # Try to get user from request state (set by auth middleware)
    if hasattr(request.state, "user") and request.state.user:
        user_id = getattr(request.state.user, "id", None)
        if user_id:
            return f"user:{user_id}"

    # Fall back to secure IP-based identification
    # Uses X-Envoy-External-Address (Railway infrastructure) or request.client.host
    client_ip = get_secure_client_ip(request)
    return f"ip:{client_ip}"
