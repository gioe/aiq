"""
Client analytics events endpoint (ICG-004).

Provides endpoint for iOS and other clients to submit analytics events
for user behavior tracking, performance monitoring, and product insights.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.models import get_db, User, ClientAnalyticsEvent
from app.schemas.client_analytics import (
    AnalyticsEventsBatch,
    AnalyticsEventsResponse,
)
from app.core.auth import get_current_user_optional
from app.core.db_error_handling import async_handle_db_error

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/events", response_model=AnalyticsEventsResponse)
async def submit_analytics_events(
    batch: AnalyticsEventsBatch,
    current_user: Optional[User] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db),
):
    """
    Submit a batch of analytics events from the client.

    This endpoint accepts analytics events from iOS and other clients.
    Events are stored for product analytics, debugging, and user
    experience insights.

    Authentication is optional - pre-auth events (like app launch)
    can be submitted without a token.

    Args:
        batch: Batch of analytics events to submit
        current_user: Current authenticated user (optional)
        db: Database session

    Returns:
        Response indicating how many events were received

    Example:
        POST /api/v1/analytics/events
        {
            "events": [
                {
                    "event_name": "user.login",
                    "timestamp": "2024-01-15T10:30:00Z",
                    "properties": {"email_domain": "gmail.com"}
                }
            ],
            "client_platform": "ios",
            "app_version": "1.2.0"
        }
    """
    user_id = current_user.id if current_user else None

    events_saved = 0
    async with async_handle_db_error(db, "submit analytics events"):
        for event in batch.events:
            db_event = ClientAnalyticsEvent(
                event_name=event.event_name,
                client_timestamp=event.timestamp,
                user_id=user_id,
                properties=event.properties,
                client_platform=batch.client_platform,
                app_version=batch.app_version,
                device_id=batch.device_id,
            )
            db.add(db_event)
            events_saved += 1

        await db.commit()

    logger.info(
        f"Received {events_saved} analytics events from "
        f"user_id={user_id}, platform={batch.client_platform}, "
        f"version={batch.app_version}"
    )

    return AnalyticsEventsResponse(
        success=True,
        events_received=events_saved,
        message=f"Successfully received {events_saved} analytics events",
    )
