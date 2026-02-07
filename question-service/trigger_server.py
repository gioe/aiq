#!/usr/bin/env python3
"""
Simple HTTP server for manually triggering question generation.

This provides a web interface for triggering the question generation job
on-demand via HTTP requests, instead of waiting for the cron schedule.

Triggers the EXACT same command as the cron job:
  python run_generation.py --count 50 --verbose
"""
import logging
import os
import secrets
import subprocess
import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from prometheus_client import REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings

logger = logging.getLogger(__name__)

# Rate limiting constants
RATE_LIMIT_REQUESTS = 10  # Maximum requests per window
RATE_LIMIT_WINDOW = 60  # Window size in seconds (1 minute)
RATE_LIMIT_CLEANUP_INTERVAL = 120  # Clean up old entries every 2 minutes

# Rate limit storage: {client_id: {window_id: count}}
_rate_limit_data: Dict[str, Dict[int, int]] = {}
_rate_limit_lock = threading.Lock()
_last_cleanup = time.time()


class RateLimiter:
    """
    Thread-safe fixed-window rate limiter.

    Uses fixed time windows to track request counts per client.
    Automatically cleans up expired entries to prevent memory leaks.
    """

    @staticmethod
    def _get_client_id(request: Request) -> str:
        """
        Securely extract client identifier from request.

        Uses trusted proxy headers to prevent IP spoofing attacks.

        Security notes:
        - X-Forwarded-For is UNTRUSTED: clients can inject arbitrary values
        - X-Real-IP is UNTRUSTED: clients can inject arbitrary values
        - X-Envoy-External-Address is TRUSTED: set by Railway's Envoy proxy
        - request.client.host is RELIABLE: direct connection IP

        Args:
            request: FastAPI Request object

        Returns:
            Client IP address as identifier
        """
        # Priority 1: X-Envoy-External-Address (Railway-specific, infrastructure-set)
        # This header is set by Railway's Envoy proxy and cannot be spoofed
        envoy_ip = request.headers.get("X-Envoy-External-Address")
        if envoy_ip:
            return envoy_ip.split(",")[0].strip()

        # Priority 2: Direct client IP (for local development without proxy)
        if request.client:
            return request.client.host

        # Priority 3: Unknown fallback
        return "unknown"

    @staticmethod
    def _cleanup_expired_entries(current_time: float) -> None:
        """
        Remove expired rate limit entries to prevent memory leaks.

        Called periodically when cleanup interval has elapsed.

        Args:
            current_time: Current timestamp
        """
        global _last_cleanup

        if current_time - _last_cleanup < RATE_LIMIT_CLEANUP_INTERVAL:
            return

        # Calculate cutoff window (keep current and previous window)
        current_window = int(current_time // RATE_LIMIT_WINDOW)
        cutoff_window = current_window - 1

        # Remove expired entries
        clients_to_remove = []
        for client_id, windows in _rate_limit_data.items():
            # Remove old windows
            expired_windows = [w for w in windows if w < cutoff_window]
            for window in expired_windows:
                del windows[window]

            # Mark client for removal if no active windows
            if not windows:
                clients_to_remove.append(client_id)

        # Remove clients with no active windows
        for client_id in clients_to_remove:
            del _rate_limit_data[client_id]

        _last_cleanup = current_time
        logger.debug(
            f"Rate limit cleanup: removed {len(clients_to_remove)} expired clients"
        )

    @staticmethod
    def check_rate_limit(request: Request) -> Dict[str, int]:
        """
        Check if request is within rate limit.

        Args:
            request: FastAPI Request object

        Returns:
            Dictionary with rate limit metadata:
                - limit: Maximum requests per window
                - remaining: Requests remaining in current window
                - reset: Unix timestamp when window resets

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        current_time = time.time()
        window_id = int(current_time // RATE_LIMIT_WINDOW)
        client_id = RateLimiter._get_client_id(request)

        with _rate_limit_lock:
            # Periodic cleanup to prevent memory leaks
            RateLimiter._cleanup_expired_entries(current_time)

            # Get or initialize client data
            if client_id not in _rate_limit_data:
                _rate_limit_data[client_id] = {}

            client_windows = _rate_limit_data[client_id]

            # Get current window count
            current_count = client_windows.get(window_id, 0)

            # Check if limit exceeded
            if current_count >= RATE_LIMIT_REQUESTS:
                reset_at = (window_id + 1) * RATE_LIMIT_WINDOW
                retry_after = int(reset_at - current_time)

                logger.warning(
                    f"Rate limit exceeded for client {client_id} on {request.url.path}: "
                    f"{current_count}/{RATE_LIMIT_REQUESTS} requests in window"
                )

                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded. Try again in {retry_after} seconds.",
                    headers={
                        "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(int(reset_at)),
                        "Retry-After": str(retry_after),
                    },
                )

            # Increment counter
            client_windows[window_id] = current_count + 1

            # Calculate metadata
            remaining = RATE_LIMIT_REQUESTS - (current_count + 1)
            reset_at = (window_id + 1) * RATE_LIMIT_WINDOW

            return {
                "limit": RATE_LIMIT_REQUESTS,
                "remaining": remaining,
                "reset": int(reset_at),
            }


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies rate limiting to all endpoints except those in skip_paths.
    Adds rate limit headers to all responses.
    """

    def __init__(self, app, skip_paths: Optional[list[str]] = None):
        """
        Initialize rate limit middleware.

        Args:
            app: FastAPI application
            skip_paths: List of paths to skip rate limiting (e.g., ["/health"])
        """
        super().__init__(app)
        self.skip_paths = skip_paths or []

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Skip rate limiting for excluded paths
        if request.url.path in self.skip_paths:
            return await call_next(request)

        # Check rate limit
        try:
            rate_limit_info = RateLimiter.check_rate_limit(request)

            # Process request
            response = await call_next(request)

            # Add rate limit headers to response
            response.headers["X-RateLimit-Limit"] = str(rate_limit_info["limit"])
            response.headers["X-RateLimit-Remaining"] = str(
                rate_limit_info["remaining"]
            )
            response.headers["X-RateLimit-Reset"] = str(rate_limit_info["reset"])

            return response

        except HTTPException as exc:
            # Rate limit exceeded - return 429 with headers
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=exc.headers,
            )


app = FastAPI(
    title="Question Generation Trigger Service",
    description=(
        "HTTP API for manually triggering AIQ question generation jobs. "
        "This service provides on-demand execution of the question generation pipeline, "
        "bypassing the scheduled cron job. Requires admin authentication. "
        "Rate limited to 10 requests per minute per IP address."
    ),
    version="1.0.0",
    contact={
        "name": "AIQ Team",
    },
    license_info={
        "name": "Proprietary",
    },
)

# Add rate limiting middleware (skip health check and metrics)
app.add_middleware(RateLimitMiddleware, skip_paths=["/health", "/metrics"])

# Prometheus metrics instrumentation
if settings.enable_prometheus_metrics:
    # Clear FastAPI Instrumentator's default HTTP collectors to avoid duplicate
    # registration on module reload (common in test scenarios with importlib.reload).
    # These collectors are recreated by instrumentator.instrument() below.
    # Guard to test/dev only: REGISTRY._names_to_collectors is a private attribute
    # that could change in future prometheus_client versions. In production with
    # single-module-load, this cleanup is unnecessary (no reload occurs).
    if settings.env in ("development", "test"):
        collectors_to_remove = [
            c
            for c in list(REGISTRY._names_to_collectors.values())
            if hasattr(c, "_name")
            and c._name.startswith(("http_requests", "http_request"))
        ]
        for collector in collectors_to_remove:
            try:
                REGISTRY.unregister(collector)
            except (ValueError, KeyError) as e:
                logger.debug(f"Failed to unregister Prometheus collector: {e}")

    instrumentator = Instrumentator(
        excluded_handlers=["/health", "/metrics"],
        should_instrument_requests_inprogress=True,
    )
    instrumentator.instrument(
        app, metric_namespace="aiq", metric_subsystem="question_service"
    )
    instrumentator.expose(app, include_in_schema=False)
    logger.info("Prometheus metrics enabled at /metrics")

# Admin token from environment
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")

# Job state tracking for concurrency control
_running_job: Optional[threading.Thread] = None
_job_lock = threading.Lock()


async def verify_admin_token(
    x_admin_token: str = Header(
        ...,
        description="Admin authentication token. Must match the ADMIN_TOKEN environment variable.",
        json_schema_extra={"example": "your-secret-admin-token"},
    ),
) -> bool:
    """Verify admin token from request header using constant-time comparison."""
    if not ADMIN_TOKEN:
        logger.error("Admin token not configured - rejecting request")
        raise HTTPException(
            status_code=500,
            detail="Admin token not configured",
        )

    if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        logger.warning("Invalid admin token provided")
        raise HTTPException(
            status_code=401,
            detail="Invalid admin token",
        )

    return True


class TriggerRequest(BaseModel):
    """Request body for triggering a question generation job."""

    count: Optional[int] = Field(
        default=50,
        ge=1,
        le=500,
        description="Number of questions to generate. Must be between 1 and 500.",
        json_schema_extra={"example": 50},
    )
    dry_run: bool = Field(
        default=False,
        description="If true, simulates the job without persisting generated questions.",
        json_schema_extra={"example": False},
    )
    verbose: bool = Field(
        default=True,
        description="If true, enables detailed logging during generation.",
        json_schema_extra={"example": True},
    )


class TriggerResponse(BaseModel):
    """Response returned after successfully starting a generation job."""

    message: str = Field(
        description="Human-readable status message describing the triggered job.",
        json_schema_extra={
            "example": "Question generation job started (count=50, dry_run=False)"
        },
    )
    status: str = Field(
        description="Job status. Will be 'started' when job is successfully triggered.",
        json_schema_extra={"example": "started"},
    )
    timestamp: str = Field(
        description="ISO 8601 timestamp when the job was triggered.",
        json_schema_extra={"example": "2026-01-21T10:30:00.000000"},
    )


class HealthResponse(BaseModel):
    """Response from the health check endpoint."""

    status: str = Field(
        description="Service health status.",
        json_schema_extra={"example": "healthy"},
    )
    service: str = Field(
        description="Name of the service.",
        json_schema_extra={"example": "question-generation-trigger"},
    )


class HTTPErrorResponse(BaseModel):
    """Standard error response body."""

    detail: str = Field(
        description="Human-readable error message.",
        json_schema_extra={"example": "Invalid admin token"},
    )


class RateLimitExceededResponse(BaseModel):
    """Response returned when rate limit is exceeded (HTTP 429)."""

    detail: str = Field(
        description="Human-readable error message with retry information.",
        json_schema_extra={"example": "Rate limit exceeded. Try again in 42 seconds."},
    )


def run_generation_job(count: int, dry_run: bool, verbose: bool) -> None:
    """
    Run the generation job in a separate process.

    This runs the EXACT same command as the Railway cron job.

    Args:
        count: Number of questions to generate
        dry_run: Whether to run in dry-run mode
        verbose: Whether to run in verbose mode
    """
    # Build the exact same command as the cron job
    cmd = ["python", "run_generation.py", "--count", str(count)]

    if verbose:
        cmd.append("--verbose")

    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"Starting generation job: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hour timeout
        )

        if result.returncode == 0:
            logger.info(
                f"Generation job completed successfully (exit code: {result.returncode})"
            )
        else:
            logger.error(
                f"Generation job failed (exit code: {result.returncode})\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )
    except subprocess.TimeoutExpired:
        logger.error("Generation job timed out after 3600 seconds")
    except Exception as e:
        logger.exception(f"Generation job crashed with exception: {e}")


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns the health status of the trigger service. Used by load balancers and monitoring systems.",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="healthy", service="question-generation-trigger")


@app.post(
    "/trigger",
    response_model=TriggerResponse,
    summary="Trigger question generation",
    description=(
        "Manually trigger the question generation job. This executes the same pipeline "
        "as the scheduled cron job. The job runs asynchronously in the background; "
        "this endpoint returns immediately after starting the job. Only one job can "
        "run at a time. Rate limited to 10 requests per minute per IP address."
    ),
    tags=["Generation"],
    responses={
        200: {
            "description": "Job successfully started",
            "model": TriggerResponse,
        },
        401: {
            "description": "Invalid or missing admin token",
            "model": HTTPErrorResponse,
        },
        409: {
            "description": "A generation job is already running",
            "model": HTTPErrorResponse,
        },
        429: {
            "description": "Rate limit exceeded - too many requests",
            "model": RateLimitExceededResponse,
        },
        500: {
            "description": "Server configuration error (admin token not set)",
            "model": HTTPErrorResponse,
        },
    },
)
async def trigger_generation(
    request: TriggerRequest,
    _: bool = Depends(verify_admin_token),
) -> TriggerResponse:
    """Trigger question generation job."""
    global _running_job

    logger.info(
        f"Received generation trigger request: count={request.count}, "
        f"dry_run={request.dry_run}, verbose={request.verbose}"
    )

    with _job_lock:
        # Clean up completed job reference to avoid memory leaks
        if _running_job is not None and not _running_job.is_alive():
            _running_job = None

        # Check if a job is already running
        if _running_job is not None:
            logger.warning("Generation job already running - rejecting request")
            raise HTTPException(
                status_code=409,
                detail="A generation job is already running. Please wait for it to complete.",
            )

        # Create thread and set reference BEFORE starting to prevent race condition
        thread = threading.Thread(
            target=run_generation_job,
            args=(request.count, request.dry_run, request.verbose),
            daemon=True,
        )
        _running_job = thread
        thread.start()

    logger.info(
        f"Started generation job in background thread: "
        f"count={request.count}, dry_run={request.dry_run}"
    )

    return TriggerResponse(
        message=f"Question generation job started (count={request.count}, dry_run={request.dry_run})",
        status="started",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
