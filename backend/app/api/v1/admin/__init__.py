"""
Admin API endpoints.

This module provides administrative endpoints for managing and monitoring the
AIQ backend. All endpoints require authentication via X-Admin-Token header
(or X-Service-Key for service-to-service communication).

Submodules:
    - generation: Question generation job management and run tracking
    - calibration: Question difficulty calibration and validation
    - analytics: Response time analytics and factor analysis
    - distractors: Distractor effectiveness analysis
    - validity: Test session validity assessment and management
    - config: Weighted scoring configuration
    - discrimination: Item discrimination analysis and quality flags
    - reliability: Reliability metrics (Cronbach's alpha, test-retest, split-half)
    - notifications: Push notification management (Day 30 reminders)
"""
from fastapi import APIRouter

from . import (
    analytics,
    calibration,
    config,
    discrimination,
    distractors,
    generation,
    notifications,
    reliability,
    validity,
)

# Create the main admin router
router = APIRouter()

# Include all sub-routers
# Each sub-router handles a specific domain of admin functionality
router.include_router(
    generation.router,
    tags=["Admin - Generation"],
)

router.include_router(
    calibration.router,
    tags=["Admin - Calibration"],
)

router.include_router(
    analytics.router,
    tags=["Admin - Analytics"],
)

router.include_router(
    distractors.router,
    tags=["Admin - Distractors"],
)

router.include_router(
    validity.router,
    tags=["Admin - Validity"],
)

router.include_router(
    config.router,
    tags=["Admin - Config"],
)

router.include_router(
    discrimination.router,
    tags=["Admin - Discrimination"],
)

router.include_router(
    reliability.router,
    tags=["Admin - Reliability"],
)

router.include_router(
    notifications.router,
    tags=["Admin - Notifications"],
)
