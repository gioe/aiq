"""
Main FastAPI application.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Union
from app.core import settings
from app.api.v1.api import api_router
from app.ratelimit import (
    RateLimiter,
    RateLimitMiddleware,
    RateLimitConfig,
    get_user_identifier,
    TokenBucketStrategy,
    SlidingWindowStrategy,
    FixedWindowStrategy,
    InMemoryStorage,
)
from app.middleware import SecurityHeadersMiddleware, RequestSizeLimitMiddleware

# OpenAPI tags metadata
tags_metadata = [
    {
        "name": "health",
        "description": "Health check endpoints for monitoring application status",
    },
    {
        "name": "auth",
        "description": "Authentication endpoints for user registration, login, and token management",
    },
    {
        "name": "user",
        "description": "User profile management endpoints",
    },
    {
        "name": "questions",
        "description": "Question retrieval endpoints for fetching unseen IQ test questions",
    },
    {
        "name": "test",
        "description": "Test session management, response submission, and results retrieval endpoints",
    },
]


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.
    """
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "**IQ Tracker API** - A backend service for tracking cognitive performance over time.\n\n"
            "This API provides:\n"
            "* User authentication and profile management\n"
            "* Periodic IQ testing with AI-generated questions\n"
            "* Test session management and response submission\n"
            "* Historical test results and trend analysis\n\n"
            "## Authentication\n\n"
            "Most endpoints require authentication using JWT Bearer tokens. "
            "Obtain tokens via the `/v1/auth/login` endpoint.\n\n"
            "## Testing Cadence\n\n"
            "Users are recommended to take tests every 6 months for optimal cognitive tracking."
        ),
        contact={
            "name": "IQ Tracker Support",
            "email": "support@iqtracker.example.com",
        },
        license_info={
            "name": "MIT",
        },
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        openapi_tags=tags_metadata,
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configure Security Headers
    # HSTS is enabled only in production to avoid issues with local development
    hsts_enabled = settings.ENV == "production"
    app.add_middleware(
        SecurityHeadersMiddleware,
        hsts_enabled=hsts_enabled,
        hsts_max_age=31536000,  # 1 year
        csp_enabled=True,
    )

    # Configure Request Size Limits
    # 1MB default, can be configured via environment variable
    max_body_size = 1024 * 1024  # 1MB
    app.add_middleware(RequestSizeLimitMiddleware, max_body_size=max_body_size)

    # Configure Rate Limiting
    if settings.RATE_LIMIT_ENABLED:
        # Create storage backend
        storage = InMemoryStorage()

        # Select strategy based on configuration
        strategy: Union[TokenBucketStrategy, SlidingWindowStrategy, FixedWindowStrategy]
        if settings.RATE_LIMIT_STRATEGY == "sliding_window":
            strategy = SlidingWindowStrategy(storage)
        elif settings.RATE_LIMIT_STRATEGY == "fixed_window":
            strategy = FixedWindowStrategy(storage)
        else:  # Default to token_bucket
            strategy = TokenBucketStrategy(storage)

        # Create rate limiter
        limiter = RateLimiter(
            strategy=strategy,
            storage=storage,
            default_limit=settings.RATE_LIMIT_DEFAULT_LIMIT,
            default_window=settings.RATE_LIMIT_DEFAULT_WINDOW,
        )

        # Create rate limit configuration with endpoint-specific limits
        # mypy: ignore - we're using the literal from settings
        rate_limit_config = RateLimitConfig(
            strategy=settings.RATE_LIMIT_STRATEGY,  # type: ignore[arg-type]
            default_limit=settings.RATE_LIMIT_DEFAULT_LIMIT,
            default_window=settings.RATE_LIMIT_DEFAULT_WINDOW,
            enabled=True,
            add_headers=True,
            skip_paths=[
                "/",
                "/health",
                f"{settings.API_V1_PREFIX}/docs",
                f"{settings.API_V1_PREFIX}/openapi.json",
                f"{settings.API_V1_PREFIX}/redoc",
            ],
            endpoint_limits={
                # Strict limits for auth endpoints to prevent abuse
                f"{settings.API_V1_PREFIX}/auth/login": {
                    "limit": 5,
                    "window": 300,
                },  # 5 per 5 min
                f"{settings.API_V1_PREFIX}/auth/register": {
                    "limit": 3,
                    "window": 3600,
                },  # 3 per hour
                f"{settings.API_V1_PREFIX}/auth/refresh": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min
            },
        )

        # Add rate limit middleware
        app.add_middleware(
            RateLimitMiddleware,
            limiter=limiter,
            identifier_resolver=get_user_identifier,
            skip_paths=rate_limit_config.skip_paths,
            add_headers=rate_limit_config.add_headers,
        )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_application()


@app.get("/")
async def root():
    """
    Root endpoint.
    """
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.APP_VERSION,
        "docs": f"{settings.API_V1_PREFIX}/docs",
    }
