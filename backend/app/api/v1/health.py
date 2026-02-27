"""
Health check and status endpoints.
"""

import logging
from fastapi import APIRouter
from sqlalchemy import text
from app.core.datetime_utils import utc_now
from app.core.config import settings
from app.models.base import async_engine

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns basic health status of the API, including database connectivity.
    Database check is non-fatal: the endpoint always returns 200 but reports
    the database status so outages are immediately visible in the response body.
    """
    db_status = "ok"
    db_error: str | None = None
    try:
        async with async_engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = "error"
        db_error = str(exc)
        logger.error("Health check database connectivity failed: %s", exc)

    return {
        "status": "healthy",
        "timestamp": utc_now().isoformat(),
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
        **({"database_error": db_error} if db_error else {}),
    }


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for basic connectivity testing.
    """
    return {"message": "pong"}
