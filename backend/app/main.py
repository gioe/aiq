"""
Main FastAPI application.
"""
import logging
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Union
from urllib.parse import urlparse

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.api import api_router
from app.core.config import settings
from app.tracing import setup_tracing, shutdown_tracing
from libs.observability import observability

from app.core.analytics import AnalyticsTracker
from app.core.logging_config import setup_logging
from app.core.process_registry import process_registry
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
    RateLimiterStorage,
    SlidingWindowStrategy,
    TokenBucketStrategy,
    get_user_identifier,
)

# Initialize logging configuration at startup
setup_logging()

logger = logging.getLogger(__name__)


def _sanitize_redis_url(url: str) -> str:
    """
    Remove password from Redis URL for safe logging.

    Args:
        url: Redis connection URL (e.g., redis://:password@host:port/db)

    Returns:
        URL with password redacted
    """
    parsed = urlparse(url)
    if parsed.password:
        # Reconstruct URL without password
        netloc = parsed.hostname or "localhost"
        if parsed.port:
            netloc = f"{netloc}:{parsed.port}"
        return f"{parsed.scheme}://{netloc}{parsed.path}"
    return url


def _create_rate_limit_storage() -> RateLimiterStorage:
    """
    Create rate limit storage backend based on configuration.

    Attempts to create the configured storage backend (memory or redis).
    If Redis is configured but unavailable, falls back to in-memory storage.

    Returns:
        RateLimiterStorage: The configured storage backend
    """
    if settings.RATE_LIMIT_STORAGE == "redis":
        try:
            # Import RedisStorage only when needed (redis-py is optional)
            from app.ratelimit.storage import RedisStorage

            storage = RedisStorage(redis_url=settings.RATE_LIMIT_REDIS_URL)
            # Test connection - RedisStorage logs warning if it fails
            if storage.is_connected():
                logger.info(
                    f"Rate limiting using Redis storage at {_sanitize_redis_url(settings.RATE_LIMIT_REDIS_URL)}"
                )
                return storage
            else:
                logger.warning(
                    "Redis not available for rate limiting, falling back to in-memory storage. "
                    "Rate limits will NOT be shared across workers."
                )
                return InMemoryStorage(max_keys=settings.RATE_LIMIT_MAX_KEYS)
        except ImportError:
            logger.warning(
                "Redis storage configured but redis-py not installed. "
                "Falling back to in-memory storage. "
                "Install redis-py with: pip install redis"
            )
            return InMemoryStorage(max_keys=settings.RATE_LIMIT_MAX_KEYS)
        except Exception as e:
            logger.warning(
                f"Failed to initialize Redis storage: {e}. "
                "Falling back to in-memory storage."
            )
            return InMemoryStorage(max_keys=settings.RATE_LIMIT_MAX_KEYS)
    else:
        max_keys = settings.RATE_LIMIT_MAX_KEYS
        logger.info(
            f"Rate limiting using in-memory storage "
            f"(max_keys={max_keys}, LRU={'enabled' if max_keys > 0 else 'disabled'})"
        )
        return InMemoryStorage(max_keys=max_keys)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan event handler.

    Manages startup and shutdown events for the application.
    - On startup: Registers signal handlers for graceful process shutdown
    - On shutdown: Terminates any running background processes and closes connections
    """
    # Startup
    # Initialize observability (Sentry + OTEL via unified facade)
    observability.init(
        config_path="config/observability.yaml",
        service_name="aiq-backend",
        environment=settings.ENV,
    )

    process_registry.register_shutdown_handler()
    logger.info("Process registry shutdown handlers registered")

    # Initialize token blacklist for JWT revocation
    from app.core.token_blacklist import init_token_blacklist

    redis_url = (
        settings.TOKEN_BLACKLIST_REDIS_URL
        if settings.TOKEN_BLACKLIST_REDIS_URL
        else None
    )
    token_blacklist = init_token_blacklist(redis_url=redis_url)
    app.state.token_blacklist = token_blacklist
    logger.info("Token blacklist initialized")

    # Setup OpenTelemetry tracing, metrics, and logging
    setup_tracing(app)

    # Initialize custom application metrics
    from app.observability import metrics

    metrics.initialize()
    logger.info("Application metrics initialized")

    # Setup database query instrumentation
    if settings.OTEL_ENABLED and settings.OTEL_METRICS_ENABLED:
        try:
            from app.db.instrumentation import setup_db_instrumentation
            from app.models import engine

            setup_db_instrumentation(engine)
        except Exception as e:
            logger.warning(f"Failed to setup database query instrumentation: {e}")

    yield

    # Shutdown
    shutdown_tracing()

    # Shutdown observability backends (flushes pending data to Sentry/OTEL)
    observability.shutdown()

    stats = process_registry.get_stats()
    if stats["running"] > 0:
        logger.info(
            f"Application shutting down with {stats['running']} "
            "running background jobs - terminating..."
        )
        process_registry.shutdown_all(timeout=10.0)
    else:
        logger.info("Application shutting down - no running background jobs")

    # Close rate limit storage connection pools if using Redis
    if hasattr(app.state, "rate_limit_storage"):
        storage = app.state.rate_limit_storage
        if hasattr(storage, "close"):
            storage.close()
            logger.info("Closed global rate limit storage connection pool")

    # Close feedback rate limiter storage connection pool
    # This is initialized at module load time in app.api.v1.feedback
    try:
        from app.api.v1.feedback import feedback_storage

        if hasattr(feedback_storage, "close"):
            feedback_storage.close()
            logger.info("Closed feedback rate limit storage connection pool")
    except ImportError:
        pass  # Module not imported yet, nothing to close

    # Close token blacklist storage connection pool
    try:
        from app.core.token_blacklist import get_token_blacklist

        blacklist = get_token_blacklist()
        blacklist.close()
    except RuntimeError:
        pass  # Blacklist not initialized, nothing to close


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
        lifespan=lifespan,
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
    # Security: Explicitly list allowed methods and headers instead of wildcards
    # Methods: REST verbs used by iOS app and admin dashboard
    # Headers: Authorization (JWT), Content-Type (JSON), X-Platform/X-App-Version (telemetry)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Platform", "X-App-Version"],
    )

    # Configure Request Logging
    # Add first to log all incoming requests and responses
    app.add_middleware(RequestLoggingMiddleware)

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
        # Create storage backend based on configuration
        storage: RateLimiterStorage = _create_rate_limit_storage()

        # Store storage in app state for cleanup on shutdown
        app.state.rate_limit_storage = storage

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
            strategy=settings.RATE_LIMIT_STRATEGY,
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
                f"{settings.API_V1_PREFIX}/auth/logout-all": {
                    "limit": 3,
                    "window": 300,
                },  # 3 per 5 min - prevent abuse of mass token revocation
                # Password reset rate limits (TASK-503)
                f"{settings.API_V1_PREFIX}/auth/request-password-reset": {
                    "limit": 3,
                    "window": 900,
                },  # 3 per 15 min - prevent email spam abuse
                f"{settings.API_V1_PREFIX}/auth/reset-password": {
                    "limit": 5,
                    "window": 3600,
                },  # 5 per hour - prevent brute force attempts
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
                f"{settings.API_V1_PREFIX}/admin/calibration-status": {
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

            # Capture error to observability (Sentry + OTEL)
            observability.capture_error(
                exc,
                context={
                    "path": str(request.url.path),
                    "method": request.method,
                    "status_code": exc.status_code,
                },
                tags={"error_type": "HTTPException"},
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

        # Capture error to observability (Sentry + OTEL)
        observability.capture_error(
            exc,
            context={
                "path": str(request.url.path),
                "method": request.method,
                "validation_errors": errors,
            },
            tags={"error_type": "ValidationError"},
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

        # Capture error to observability (Sentry + OTEL)
        observability.capture_error(
            exc,
            context={
                "path": str(request.url.path),
                "method": request.method,
                "error_id": error_id,
            },
            tags={"error_type": exc.__class__.__name__},
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
