"""
Health check and status endpoints.
"""
from fastapi import APIRouter
from app.core.datetime_utils import utc_now
from app.core import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns basic health status of the API.
    """
    return {
        "status": "healthy",
        "timestamp": utc_now().isoformat(),
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for basic connectivity testing.
    """
    return {"message": "pong"}
