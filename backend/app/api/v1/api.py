"""
API v1 router combining all v1 endpoints.
"""
from fastapi import APIRouter
from app.api.v1 import health

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(health.router, tags=["health"])
