"""
Security middleware for adding security headers and enforcing security policies.
"""
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses.

    Implements security best practices including:
    - Content Security Policy (CSP)
    - X-Frame-Options (Clickjacking protection)
    - X-Content-Type-Options (MIME sniffing protection)
    - Strict-Transport-Security (HTTPS enforcement)
    - X-XSS-Protection (XSS protection for older browsers)
    - Referrer-Policy (Control referrer information)
    - Permissions-Policy (Feature policy)
    """

    def __init__(
        self,
        app: ASGIApp,
        hsts_enabled: bool = True,
        hsts_max_age: int = 31536000,  # 1 year
        csp_enabled: bool = True,
    ):
        """
        Initialize security headers middleware.

        Args:
            app: ASGI application
            hsts_enabled: Enable HTTP Strict Transport Security
            hsts_max_age: HSTS max age in seconds
            csp_enabled: Enable Content Security Policy
        """
        super().__init__(app)
        self.hsts_enabled = hsts_enabled
        self.hsts_max_age = hsts_max_age
        self.csp_enabled = csp_enabled

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and add security headers to response.

        Args:
            request: HTTP request
            call_next: Next middleware in chain

        Returns:
            HTTP response with security headers
        """
        response = await call_next(request)

        # X-Frame-Options: Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options: Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection: Enable XSS filter (for older browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Referrer-Policy: Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: Control browser features
        response.headers[
            "Permissions-Policy"
        ] = "geolocation=(), microphone=(), camera=(), payment=(), usb=()"

        # Content-Security-Policy: Control resource loading
        if self.csp_enabled:
            # Restrictive CSP for API (no script execution needed)
            csp_directives = [
                "default-src 'self'",
                "script-src 'none'",
                "object-src 'none'",
                "base-uri 'self'",
                "form-action 'self'",
                "frame-ancestors 'none'",
                "upgrade-insecure-requests",
            ]
            response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Strict-Transport-Security: Enforce HTTPS (only in production)
        if self.hsts_enabled:
            response.headers[
                "Strict-Transport-Security"
            ] = f"max-age={self.hsts_max_age}; includeSubDomains; preload"

        # X-Permitted-Cross-Domain-Policies: Restrict cross-domain access
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce maximum request body size limits.

    Protects against DoS attacks via large request bodies.
    """

    def __init__(self, app: ASGIApp, max_body_size: int = 1024 * 1024):
        """
        Initialize request size limit middleware.

        Args:
            app: ASGI application
            max_body_size: Maximum request body size in bytes (default: 1MB)
        """
        super().__init__(app)
        self.max_body_size = max_body_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Check request body size before processing.

        Args:
            request: HTTP request
            call_next: Next middleware in chain

        Returns:
            HTTP response or error if body too large
        """
        # Check Content-Length header if present
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self.max_body_size:
            return Response(
                content='{"detail": "Request body too large"}',
                status_code=413,
                media_type="application/json",
            )

        response = await call_next(request)
        return response
