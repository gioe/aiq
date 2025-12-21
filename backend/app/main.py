"""
Main FastAPI application.
"""
import logging
import uuid
from typing import Union

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.core.analytics import AnalyticsTracker
from app.core.logging_config import setup_logging
from app.middleware import (
    PerformanceMonitoringMiddleware,
    RequestLoggingMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.ratelimit import (
    FixedWindowStrategy,
    InMemoryStorage,
    RateLimitConfig,
    RateLimiter,
    RateLimitMiddleware,
    SlidingWindowStrategy,
    TokenBucketStrategy,
    get_user_identifier,
)

# Initialize logging configuration at startup
setup_logging()

logger = logging.getLogger(__name__)

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
            "**AIQ API** - A backend service for AI-generated cognitive assessments.\n\n"
            "This API provides:\n"
            "* User authentication and profile management\n"
            "* Periodic cognitive testing with AI-generated questions\n"
            "* Test session management and response submission\n"
            "* Historical test results and trend analysis\n\n"
            "## Authentication\n\n"
            "Most endpoints require authentication using JWT Bearer tokens. "
            "Obtain tokens via the `/v1/auth/login` endpoint.\n\n"
            "## Testing Cadence\n\n"
            "Users are recommended to take tests every 3 months for optimal cognitive tracking."
        ),
        contact={
            "name": "AIQ Support",
            "email": "support@aiq.app",
        },
        license_info={
            "name": "MIT",
        },
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        openapi_tags=tags_metadata,
    )

    # Configure Session Middleware (required for admin authentication)
    # Only add if admin is enabled
    if settings.ADMIN_ENABLED:
        app.add_middleware(
            SessionMiddleware,
            secret_key=settings.SECRET_KEY,
            session_cookie="admin_session",
            max_age=14400,  # 4 hours
            same_site="lax",
            https_only=settings.ENV == "production",
        )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configure Request Logging
    # Add first to log all incoming requests and responses
    app.add_middleware(
        RequestLoggingMiddleware,
        log_request_body=True,  # Log request bodies (except sensitive endpoints)
        log_response_body=False,  # Don't log response bodies (can be verbose)
    )

    # Configure Performance Monitoring
    # Add before other middleware to measure total request time
    app.add_middleware(
        PerformanceMonitoringMiddleware,
        slow_request_threshold=1.0,  # Log requests taking > 1 second
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
                # Rate limits for admin endpoints to prevent abuse
                # Computationally expensive endpoints have stricter limits
                f"{settings.API_V1_PREFIX}/admin/reliability": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                f"{settings.API_V1_PREFIX}/admin/analytics/factor-analysis": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                f"{settings.API_V1_PREFIX}/admin/questions/discrimination-report": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                f"{settings.API_V1_PREFIX}/admin/questions/distractor-summary": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                f"{settings.API_V1_PREFIX}/admin/questions/calibration-health": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                f"{settings.API_V1_PREFIX}/admin/validity-report": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                f"{settings.API_V1_PREFIX}/admin/analytics/response-times": {
                    "limit": 10,
                    "window": 60,
                },  # 10 per min - expensive calculation
                # Write operations have stricter limits
                f"{settings.API_V1_PREFIX}/admin/trigger-question-generation": {
                    "limit": 5,
                    "window": 3600,
                },  # 5 per hour - triggers expensive background job
                f"{settings.API_V1_PREFIX}/admin/questions/recalibrate": {
                    "limit": 5,
                    "window": 3600,
                },  # 5 per hour - modifies question data
            },
        )

        # Add rate limit middleware
        app.add_middleware(
            RateLimitMiddleware,
            limiter=limiter,
            identifier_resolver=get_user_identifier,
            skip_paths=rate_limit_config.skip_paths,
            add_headers=rate_limit_config.add_headers,
            endpoint_limits=rate_limit_config.endpoint_limits,
        )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # Setup Admin Dashboard (only if enabled)
    if settings.ADMIN_ENABLED:
        from sqladmin import Admin
        from app.admin import (
            AdminAuth,
            UserAdmin,
            QuestionAdmin,
            UserQuestionAdmin,
            TestSessionAdmin,
            ResponseAdmin,
            TestResultAdmin,
        )
        from app.models import engine

        admin = Admin(
            app=app,
            engine=engine,
            title="AIQ Admin",
            base_url="/admin",
            authentication_backend=AdminAuth(secret_key=settings.SECRET_KEY),
        )

        # Register admin views
        admin.add_view(UserAdmin)
        admin.add_view(QuestionAdmin)
        admin.add_view(UserQuestionAdmin)
        admin.add_view(TestSessionAdmin)
        admin.add_view(ResponseAdmin)
        admin.add_view(TestResultAdmin)

        logger.info("Admin dashboard enabled at /admin")

    # Exception handlers for error tracking
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """
        Handle HTTP exceptions and track them in analytics.
        """
        # Track API error for 4xx and 5xx errors
        if exc.status_code >= 400:
            # Extract user ID if available from request state
            user_id = getattr(request.state, "user_id", None)

            AnalyticsTracker.track_api_error(
                method=request.method,
                path=str(request.url.path),
                error_type="HTTPException",
                error_message=str(exc.detail),
                user_id=user_id,
            )

        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """
        Handle request validation errors.
        """
        # Track validation errors
        user_id = getattr(request.state, "user_id", None)

        # Convert errors to serializable format
        errors = []
        for error in exc.errors():
            error_dict = {
                "loc": list(error.get("loc", [])),
                "msg": str(error.get("msg", "")),
                "type": str(error.get("type", "")),
            }
            # Include input if it's serializable
            if "input" in error:
                try:
                    error_dict["input"] = error["input"]
                except (TypeError, ValueError):
                    pass
            errors.append(error_dict)

        AnalyticsTracker.track_api_error(
            method=request.method,
            path=str(request.url.path),
            error_type="ValidationError",
            error_message=str(errors),
            user_id=user_id,
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": errors},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        """
        Handle unexpected exceptions and track them.

        Generates a unique error_id (UUID) for each exception to enable
        support teams to trace specific errors in logs. The error_id is
        included in the response body and logged with the full exception.
        """
        # Generate unique error ID for tracing
        error_id = str(uuid.uuid4())

        # Log the full exception with error_id for tracing
        logger.exception(
            f"Unhandled exception [error_id={error_id}]: {exc}",
            extra={"error_id": error_id},
        )

        # Track the error with analytics
        user_id = getattr(request.state, "user_id", None)

        AnalyticsTracker.track_api_error(
            method=request.method,
            path=str(request.url.path),
            error_type=exc.__class__.__name__,
            error_message=str(exc),
            user_id=user_id,
        )

        # Return error response with tracking ID (don't leak internal details)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "error_id": error_id,
            },
        )

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
