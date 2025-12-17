"""
Tests for RateLimitMiddleware with per-endpoint rate limits.
"""
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ratelimit import RateLimiter, RateLimitMiddleware, InMemoryStorage


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
