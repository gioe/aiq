"""Shared fixtures for rate limiting tests.

All tests in this directory MUST use the lightweight test app created by
create_test_app_with_rate_limiting(). Never import or call
create_application() from app.main — it boots the full production stack
(async DB, Sentry, OpenTelemetry) which causes event-loop conflicts in tests.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ratelimit import InMemoryStorage, RateLimiter, RateLimitMiddleware


def create_test_app_with_rate_limiting(
    default_limit: int = 100,
    default_window: int = 60,
    endpoint_limits: dict | None = None,
    skip_paths: list | None = None,
) -> FastAPI:
    """Create a lightweight FastAPI app with rate limiting middleware.

    Registers stub routes that return fixed responses — no database,
    no auth, no observability. Use this for all rate limiting tests.
    """
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

    @app.get("/v1/health")
    async def health_v1():
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

    @app.post("/v1/auth/login")
    async def auth_login():
        return {"error": "Invalid credentials"}, 401

    @app.post("/v1/auth/register")
    async def auth_register():
        return {"error": "Invalid credentials"}, 401

    @app.post("/v1/auth/refresh")
    async def auth_refresh():
        return {"error": "Invalid token"}, 401

    @app.get("/v1/user/profile")
    async def user_profile():
        return {"error": "Unauthorized"}, 401

    @app.get("/v1/docs")
    async def docs():
        return {"docs": "openapi"}

    return app


@pytest.fixture
def rate_limited_app() -> FastAPI:
    """A lightweight FastAPI app with rate limiting (default: 100 req/60s)."""
    return create_test_app_with_rate_limiting()


@pytest.fixture
def rate_limited_client(rate_limited_app: FastAPI) -> TestClient:
    """A TestClient wrapping the lightweight rate-limited app."""
    return TestClient(rate_limited_app)
