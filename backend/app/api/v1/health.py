"""
Health check and status endpoints.
"""

import asyncio
import logging
from fastapi import APIRouter
from sqlalchemy import text
from app.core.datetime_utils import utc_now
from app.core.config import settings
from app.models.base import async_engine

logger = logging.getLogger(__name__)

router = APIRouter()

_DB_HEALTH_TIMEOUT = 3.0  # seconds


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns basic health status of the API, including database connectivity.
    Database check is non-fatal: the endpoint always returns 200 but reports
    the database status so outages are immediately visible in the response body.
    Times out after 3 seconds to avoid hanging Railway's health check.
    """
    db_status = "ok"
    db_error: str | None = None
    try:

        async def _ping() -> None:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

        await asyncio.wait_for(_ping(), timeout=_DB_HEALTH_TIMEOUT)
    except asyncio.TimeoutError:
        db_status = "error"
        db_error = f"database ping timed out after {_DB_HEALTH_TIMEOUT}s"
        logger.error("Health check database connectivity timed out")
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)
        logger.error("Health check database connectivity failed: %s", exc)

    response: dict = {
        "status": "healthy",
        "timestamp": utc_now().isoformat(),
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
    }
    if db_error and settings.ENV != "production":
        response["database_error"] = db_error
    return response


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for basic connectivity testing.
    """
    return {"message": "pong"}
