"""
Tests for RateLimitMiddleware with per-endpoint rate limits.
"""
from unittest.mock import MagicMock

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.ratelimit import RateLimiter, RateLimitMiddleware, InMemoryStorage
from app.ratelimit.middleware import get_user_identifier


def create_test_app_with_rate_limiting(
    default_limit: int = 100,
    default_window: int = 60,
    endpoint_limits: dict | None = None,
    skip_paths: list | None = None,
) -> FastAPI:
    """Create a test FastAPI app with rate limiting middleware."""
    app = FastAPI()
    storage = InMemoryStorage()
    limiter = RateLimiter(
        storage=storage,
        default_limit=default_limit,
        default_window=default_window,
    )

    app.add_middleware(
        RateLimitMiddleware,
        limiter=limiter,
        skip_paths=skip_paths or [],
        endpoint_limits=endpoint_limits or {},
    )

    @app.get("/")
    async def root():
        return {"message": "OK"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.get("/v1/admin/reliability")
    async def admin_reliability():
        return {"reliability": "good"}

    @app.get("/v1/admin/expensive")
    async def admin_expensive():
        return {"result": "computed"}

    @app.post("/v1/admin/trigger")
    async def admin_trigger():
        return {"triggered": True}

    return app


class TestRateLimitMiddlewareBasic:
    """Tests for basic middleware functionality."""

    def test_allows_requests_under_default_limit(self):
        """Test that requests under default limit are allowed."""
        app = create_test_app_with_rate_limiting(default_limit=5)
        client = TestClient(app)

        for i in range(5):
            response = client.get("/")
            assert response.status_code == 200

    def test_denies_requests_over_default_limit(self):
        """Test that requests over default limit return 429."""
        app = create_test_app_with_rate_limiting(default_limit=3)
        client = TestClient(app)

        # Make 3 requests to exhaust limit
        for i in range(3):
            response = client.get("/")
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client.get("/")
        assert response.status_code == 429
        assert response.json()["error"] == "rate_limit_exceeded"

    def test_skip_paths_bypass_rate_limiting(self):
        """Test that skip_paths bypass rate limiting."""
        app = create_test_app_with_rate_limiting(
            default_limit=2,
            skip_paths=["/health"],
        )
        client = TestClient(app)

        # Make more requests than limit to health endpoint
        for i in range(10):
            response = client.get("/health")
            assert response.status_code == 200

    def test_rate_limit_headers_added(self):
        """Test that rate limit headers are added to responses."""
        app = create_test_app_with_rate_limiting(default_limit=10)
        client = TestClient(app)

        response = client.get("/")

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers


class TestRateLimitMiddlewareEndpointLimits:
    """Tests for per-endpoint rate limiting."""

    def test_endpoint_specific_limit_enforced(self):
        """Test that endpoint-specific limits are enforced."""
        app = create_test_app_with_rate_limiting(
            default_limit=100,  # High default
            endpoint_limits={
                "/v1/admin/reliability": {"limit": 3, "window": 60},
            },
        )
        client = TestClient(app)

        # Make 3 requests to admin reliability endpoint
        for i in range(3):
            response = client.get("/v1/admin/reliability")
            assert response.status_code == 200

        # 4th request should be rate limited
        response = client.get("/v1/admin/reliability")
        assert response.status_code == 429

    def test_endpoint_limit_independent_of_default(self):
        """Test that endpoint limits don't affect default-limited endpoints."""
        app = create_test_app_with_rate_limiting(
            default_limit=5,
            endpoint_limits={
                "/v1/admin/reliability": {"limit": 2, "window": 60},
            },
        )
        client = TestClient(app)

        # Exhaust admin endpoint limit
        for i in range(2):
            response = client.get("/v1/admin/reliability")
            assert response.status_code == 200

        # Admin endpoint should be rate limited
        response = client.get("/v1/admin/reliability")
        assert response.status_code == 429

        # Root endpoint should still work (separate limit)
        response = client.get("/")
        assert response.status_code == 200

    def test_multiple_endpoint_limits(self):
        """Test that multiple endpoints can have different limits."""
        app = create_test_app_with_rate_limiting(
            default_limit=100,
            endpoint_limits={
                "/v1/admin/reliability": {"limit": 2, "window": 60},
                "/v1/admin/expensive": {"limit": 5, "window": 60},
            },
        )
        client = TestClient(app)

        # Exhaust reliability endpoint limit
        for i in range(2):
            response = client.get("/v1/admin/reliability")
            assert response.status_code == 200

        response = client.get("/v1/admin/reliability")
        assert response.status_code == 429

        # Expensive endpoint should still have capacity
        for i in range(5):
            response = client.get("/v1/admin/expensive")
            assert response.status_code == 200

        response = client.get("/v1/admin/expensive")
        assert response.status_code == 429

    def test_endpoint_limit_with_different_methods(self):
        """Test endpoint limits work with POST methods."""
        app = create_test_app_with_rate_limiting(
            default_limit=100,
            endpoint_limits={
                "/v1/admin/trigger": {"limit": 2, "window": 60},
            },
        )
        client = TestClient(app)

        # Make 2 POST requests
        for i in range(2):
            response = client.post("/v1/admin/trigger")
            assert response.status_code == 200

        # 3rd request should be rate limited
        response = client.post("/v1/admin/trigger")
        assert response.status_code == 429

    def test_endpoint_without_specific_limit_uses_default(self):
        """Test that endpoints without specific limits use default."""
        app = create_test_app_with_rate_limiting(
            default_limit=3,
            endpoint_limits={
                "/v1/admin/reliability": {"limit": 100, "window": 60},
            },
        )
        client = TestClient(app)

        # Root endpoint should use default limit of 3
        for i in range(3):
            response = client.get("/")
            assert response.status_code == 200

        response = client.get("/")
        assert response.status_code == 429


class TestRateLimitMiddlewareErrorHandling:
    """Tests for error handling in middleware."""

    def test_rate_limit_response_structure(self):
        """Test that 429 response has correct structure."""
        app = create_test_app_with_rate_limiting(default_limit=1)
        client = TestClient(app)

        # Exhaust limit
        client.get("/")

        # Get rate limited response
        response = client.get("/")
        assert response.status_code == 429

        data = response.json()
        assert "error" in data
        assert data["error"] == "rate_limit_exceeded"
        assert "message" in data
        assert "retry_after" in data

    def test_retry_after_header_present_on_429(self):
        """Test that Retry-After header is present on 429 responses."""
        app = create_test_app_with_rate_limiting(default_limit=1)
        client = TestClient(app)

        # Exhaust limit
        client.get("/")

        # Get rate limited response
        response = client.get("/")
        assert response.status_code == 429
        assert "Retry-After" in response.headers


class TestRateLimitMiddlewareWithRealAdminEndpoints:
    """
    Tests simulating real admin endpoint rate limiting configuration.

    These tests verify the rate limiting configuration used in main.py.
    """

    def test_admin_reliability_rate_limit(self):
        """Test rate limiting for admin reliability endpoint."""
        # Simulate production config: 10 requests per minute
        app = create_test_app_with_rate_limiting(
            default_limit=100,
            endpoint_limits={
                "/v1/admin/reliability": {"limit": 10, "window": 60},
            },
        )
        client = TestClient(app)

        # Make 10 requests
        for i in range(10):
            response = client.get("/v1/admin/reliability")
            assert response.status_code == 200

        # 11th request should be rate limited
        response = client.get("/v1/admin/reliability")
        assert response.status_code == 429

    def test_expensive_operation_rate_limit(self):
        """Test stricter rate limiting for write operations."""
        # Simulate stricter limit for trigger endpoint: 5 per hour
        app = create_test_app_with_rate_limiting(
            default_limit=100,
            endpoint_limits={
                "/v1/admin/trigger": {"limit": 5, "window": 3600},
            },
        )
        client = TestClient(app)

        # Make 5 requests
        for i in range(5):
            response = client.post("/v1/admin/trigger")
            assert response.status_code == 200

        # 6th request should be rate limited
        response = client.post("/v1/admin/trigger")
        assert response.status_code == 429


class TestRateLimitMiddlewareIPExtraction:
    """
    Security tests for IP extraction in rate limiting.

    These tests verify that the middleware correctly uses secure IP extraction
    and cannot be bypassed by spoofing X-Forwarded-For or X-Real-IP headers.
    """

    def test_rate_limit_cannot_be_bypassed_with_spoofed_x_forwarded_for(self):
        """
        Test that spoofing X-Forwarded-For header does NOT bypass rate limiting.

        Security fix for BTS-221: Previously, attackers could bypass rate limiting
        by sending different X-Forwarded-For values with each request.
        """
        app = create_test_app_with_rate_limiting(default_limit=3)
        client = TestClient(app)

        # Make 3 requests with different spoofed X-Forwarded-For headers
        for i in range(3):
            response = client.get(
                "/", headers={"X-Forwarded-For": f"192.168.1.{i}"}  # Different IPs
            )
            assert response.status_code == 200

        # 4th request with yet another spoofed IP should STILL be rate limited
        # because we ignore X-Forwarded-For
        response = client.get("/", headers={"X-Forwarded-For": "192.168.1.99"})
        assert response.status_code == 429, (
            "Rate limit was bypassed by X-Forwarded-For spoofing! "
            "This is a security vulnerability."
        )

    def test_rate_limit_cannot_be_bypassed_with_spoofed_x_real_ip(self):
        """
        Test that spoofing X-Real-IP header does NOT bypass rate limiting.
        """
        app = create_test_app_with_rate_limiting(default_limit=3)
        client = TestClient(app)

        # Make 3 requests with different spoofed X-Real-IP headers
        for i in range(3):
            response = client.get("/", headers={"X-Real-IP": f"10.0.0.{i}"})
            assert response.status_code == 200

        # 4th request with yet another spoofed IP should STILL be rate limited
        response = client.get("/", headers={"X-Real-IP": "10.0.0.99"})
        assert response.status_code == 429, (
            "Rate limit was bypassed by X-Real-IP spoofing! "
            "This is a security vulnerability."
        )

    def test_rate_limit_uses_envoy_external_address_header(self):
        """
        Test that X-Envoy-External-Address header (Railway infrastructure) is trusted.

        Different X-Envoy-External-Address values should count as different clients.
        """
        app = create_test_app_with_rate_limiting(default_limit=2)
        client = TestClient(app)

        # Make 2 requests from "first" IP
        for _ in range(2):
            response = client.get(
                "/", headers={"X-Envoy-External-Address": "203.0.113.1"}
            )
            assert response.status_code == 200

        # 3rd request from same IP should be rate limited
        response = client.get("/", headers={"X-Envoy-External-Address": "203.0.113.1"})
        assert response.status_code == 429

        # Request from different IP should succeed (separate limit)
        response = client.get("/", headers={"X-Envoy-External-Address": "203.0.113.2"})
        assert response.status_code == 200

    def test_envoy_header_takes_priority_over_untrusted_headers(self):
        """
        Test that X-Envoy-External-Address takes priority over spoofed headers.
        """
        app = create_test_app_with_rate_limiting(default_limit=2)
        client = TestClient(app)

        # Make 2 requests with real Envoy header (even with spoofed X-Forwarded-For)
        for _ in range(2):
            response = client.get(
                "/",
                headers={
                    "X-Envoy-External-Address": "203.0.113.5",
                    "X-Forwarded-For": "1.2.3.4",  # Should be ignored
                    "X-Real-IP": "5.6.7.8",  # Should be ignored
                },
            )
            assert response.status_code == 200

        # Even with different spoofed headers, should still be rate limited
        # based on the same Envoy address
        response = client.get(
            "/",
            headers={
                "X-Envoy-External-Address": "203.0.113.5",
                "X-Forwarded-For": "different.ip.address",  # Should be ignored
            },
        )
        assert response.status_code == 429


class TestGetUserIdentifierSecurity:
    """Tests for get_user_identifier function security."""

    def _create_mock_request(
        self,
        user_id: str | None = None,
        envoy_ip: str | None = None,
        forwarded_for: str | None = None,
        real_ip: str | None = None,
        client_host: str = "127.0.0.1",
    ) -> MagicMock:
        """Create a mock request with specified headers and attributes."""
        request = MagicMock(spec=Request)

        # Mock request.state.user
        if user_id:
            request.state.user = MagicMock()
            request.state.user.id = user_id
        else:
            request.state.user = None

        # Mock headers
        headers = {}
        if envoy_ip:
            headers["X-Envoy-External-Address"] = envoy_ip
        if forwarded_for:
            headers["X-Forwarded-For"] = forwarded_for
        if real_ip:
            headers["X-Real-IP"] = real_ip
        request.headers.get = lambda key, default=None: headers.get(key, default)

        # Mock client
        request.client = MagicMock()
        request.client.host = client_host

        return request

    def test_authenticated_user_returns_user_id(self):
        """Test that authenticated users are identified by user ID."""
        request = self._create_mock_request(user_id="user-123")

        result = get_user_identifier(request)

        assert result == "user:user-123"

    def test_unauthenticated_uses_envoy_header(self):
        """Test that unauthenticated requests use X-Envoy-External-Address."""
        request = self._create_mock_request(envoy_ip="203.0.113.10")

        result = get_user_identifier(request)

        assert result == "ip:203.0.113.10"

    def test_ignores_x_forwarded_for_header(self):
        """
        Test that X-Forwarded-For is ignored (security fix BTS-221).

        This header can be spoofed by clients and must not be trusted.
        """
        request = self._create_mock_request(
            forwarded_for="1.2.3.4", client_host="192.168.1.100"
        )

        result = get_user_identifier(request)

        # Should use client.host, NOT the spoofed X-Forwarded-For
        assert result == "ip:192.168.1.100"
        assert "1.2.3.4" not in result

    def test_ignores_x_real_ip_header(self):
        """
        Test that X-Real-IP is ignored (security fix BTS-221).

        This header can be spoofed by clients and must not be trusted.
        """
        request = self._create_mock_request(
            real_ip="5.6.7.8", client_host="192.168.1.100"
        )

        result = get_user_identifier(request)

        # Should use client.host, NOT the spoofed X-Real-IP
        assert result == "ip:192.168.1.100"
        assert "5.6.7.8" not in result

    def test_envoy_header_takes_priority_over_spoofed_headers(self):
        """Test that Envoy header is used when present, ignoring spoofed headers."""
        request = self._create_mock_request(
            envoy_ip="203.0.113.99",
            forwarded_for="1.2.3.4",  # Should be ignored
            real_ip="5.6.7.8",  # Should be ignored
            client_host="192.168.1.100",  # Should be ignored
        )

        result = get_user_identifier(request)

        # Should use the trusted Envoy header
        assert result == "ip:203.0.113.99"

    def test_falls_back_to_client_host_without_envoy(self):
        """Test fallback to request.client.host when no Envoy header present."""
        request = self._create_mock_request(client_host="10.0.0.50")

        result = get_user_identifier(request)

        assert result == "ip:10.0.0.50"


class TestRateLimitDocumentedConfig:
    """
    Integration tests verifying the rate limit configuration in main.py
    matches the documented configuration in DEPLOYMENT.md.

    These tests use the real app factory to ensure the endpoint-specific
    limits documented for operators are actually enforced.
    """

    def _create_app(self, limit_override: int | None = None) -> "FastAPI":
        """Create the real app with rate limiting enabled."""
        from unittest.mock import patch as _patch

        from app.main import create_application

        with (
            _patch("app.main.settings.RATE_LIMIT_ENABLED", True),
            _patch(
                "app.main.settings.RATE_LIMIT_DEFAULT_LIMIT",
                limit_override or 100,
            ),
            _patch("app.main.settings.RATE_LIMIT_DEFAULT_WINDOW", 60),
            _patch("app.main.settings.RATE_LIMIT_STRATEGY", "token_bucket"),
            _patch("app.main.settings.RATE_LIMIT_STORAGE", "memory"),
        ):
            return create_application()

    def test_login_endpoint_limit_is_5_per_5_minutes(self):
        """Verify /v1/auth/login is limited to 5 requests per 5 minutes (documented)."""
        app = self._create_app()
        client = TestClient(app)

        # First 5 requests should succeed (may return 401 for bad creds, but not 429)
        for _ in range(5):
            response = client.post(
                "/v1/auth/login",
                json={
                    "email": "test@example.com",
                    "password": "wrong",  # pragma: allowlist secret
                },
            )
            assert response.status_code != 429

        # 6th request should be rate limited
        response = client.post(
            "/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrong",  # pragma: allowlist secret
            },
        )
        assert response.status_code == 429

    def test_register_endpoint_limit_is_3_per_hour(self):
        """Verify /v1/auth/register is limited to 3 requests per hour (documented)."""
        app = self._create_app()
        client = TestClient(app)

        for _ in range(3):
            response = client.post(
                "/v1/auth/register",
                json={
                    "email": "new@example.com",
                    "password": "Str0ng!Pass",  # pragma: allowlist secret
                    "display_name": "Test",
                },
            )
            assert response.status_code != 429

        # 4th request should be rate limited
        response = client.post(
            "/v1/auth/register",
            json={
                "email": "new2@example.com",
                "password": "Str0ng!Pass",  # pragma: allowlist secret
                "display_name": "Test",
            },
        )
        assert response.status_code == 429

    def test_refresh_endpoint_limit_is_10_per_minute(self):
        """Verify /v1/auth/refresh is limited to 10 requests per minute (documented)."""
        app = self._create_app()
        client = TestClient(app)

        for _ in range(10):
            response = client.post(
                "/v1/auth/refresh",
                json={"refresh_token": "fake-token"},
            )
            assert response.status_code != 429

        response = client.post(
            "/v1/auth/refresh",
            json={"refresh_token": "fake-token"},
        )
        assert response.status_code == 429

    def test_default_limit_is_100_per_minute(self):
        """Verify non-overridden endpoints use the default limit of 100/min."""
        app = self._create_app(limit_override=3)
        client = TestClient(app)

        # Use a non-overridden endpoint (health is skipped, so use another)
        for _ in range(3):
            response = client.get("/v1/user/profile")
            # May return 401 for unauthenticated, but not 429
            assert response.status_code != 429

        response = client.get("/v1/user/profile")
        assert response.status_code == 429

    def test_docs_endpoint_skips_rate_limiting(self):
        """Verify /v1/docs is excluded from rate limiting (documented)."""
        app = self._create_app(limit_override=2)
        client = TestClient(app)

        # Make many more requests than the limit — docs should be skipped
        for _ in range(10):
            response = client.get("/v1/docs")
            assert response.status_code != 429

    def test_rate_limit_429_logs_security_event(self):
        """Verify rate limit exceeded events are logged via SecurityAuditLogger."""
        from unittest.mock import patch as _patch

        app = self._create_app(limit_override=1)
        client = TestClient(app)

        with _patch(
            "app.ratelimit.middleware._security_logger"
        ) as mock_security_logger:
            # Exhaust limit
            client.get("/v1/user/profile")
            # Trigger 429
            client.get("/v1/user/profile")

            mock_security_logger.log_rate_limit_exceeded.assert_called_once()
            call_kwargs = mock_security_logger.log_rate_limit_exceeded.call_args[1]
            assert call_kwargs["path"] == "/v1/user/profile"
            assert call_kwargs["limit"] == 1


class TestRateLimitToggleIntegration:
    """
    Integration tests for the RATE_LIMIT_ENABLED toggle in create_application().

    Unlike unit tests above that use a synthetic test app, these tests exercise
    the actual app factory to verify the settings toggle controls whether rate
    limiting middleware is registered.
    """

    def _create_app_with_settings(self, enabled: bool, limit: int = 2) -> "FastAPI":
        """Create the real app with patched rate limit settings."""
        from unittest.mock import patch

        from app.main import create_application

        with (
            patch("app.main.settings.RATE_LIMIT_ENABLED", enabled),
            patch("app.main.settings.RATE_LIMIT_DEFAULT_LIMIT", limit),
            patch("app.main.settings.RATE_LIMIT_DEFAULT_WINDOW", 60),
            patch("app.main.settings.RATE_LIMIT_STRATEGY", "token_bucket"),
            patch("app.main.settings.RATE_LIMIT_STORAGE", "memory"),
        ):
            return create_application()

    def test_rate_limiting_enforced_when_enabled(self):
        """Requests exceeding the limit return 429 when RATE_LIMIT_ENABLED=True."""
        app = self._create_app_with_settings(enabled=True, limit=2)
        client = TestClient(app)

        # First 2 requests should succeed
        for _ in range(2):
            response = client.get("/v1/health")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" in response.headers

        # 3rd request should be rate limited
        response = client.get("/v1/health")
        assert response.status_code == 429
        assert response.json()["error"] == "rate_limit_exceeded"

    def test_rate_limiting_bypassed_when_disabled(self):
        """No requests are rate-limited when RATE_LIMIT_ENABLED=False."""
        app = self._create_app_with_settings(enabled=False)
        client = TestClient(app)

        # Make many more requests than the limit — none should be blocked
        for _ in range(20):
            response = client.get("/v1/health")
            assert response.status_code == 200
            assert "X-RateLimit-Limit" not in response.headers
