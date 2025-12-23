"""
API v1 router combining all v1 endpoints.
"""
from fastapi import APIRouter
from app.api.v1 import (
    health,
    auth,
    user,
    questions,
    test,
    notifications,
    question_analytics,
    client_analytics,
    admin,
)

api_router = APIRouter()

# Include all v1 routers
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(user.router, prefix="/user", tags=["user"])
api_router.include_router(questions.router, prefix="/questions", tags=["questions"])
api_router.include_router(test.router, prefix="/test", tags=["test"])
api_router.include_router(
    notifications.router, prefix="/notifications", tags=["notifications"]
)
api_router.include_router(
    question_analytics.router, prefix="/analytics", tags=["analytics"]
)
api_router.include_router(
    client_analytics.router, prefix="/analytics", tags=["analytics"]
)
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
