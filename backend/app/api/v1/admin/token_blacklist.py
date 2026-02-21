"""Token blacklist admin endpoints for monitoring."""

from fastapi import APIRouter, Depends

from app.core.auth.token_blacklist import get_token_blacklist
from app.schemas.token_blacklist import TokenBlacklistStatsResponse

from ._dependencies import logger, verify_admin_token

router = APIRouter()


@router.get(
    "/token-blacklist/stats",
    response_model=TokenBlacklistStatsResponse,
)
async def get_token_blacklist_stats(
    _: bool = Depends(verify_admin_token),
):
    r"""
    Get token blacklist statistics for monitoring.

    Returns storage statistics including key counts and backend type.
    Useful for monitoring token revocation health and storage usage.

    Requires X-Admin-Token header with valid admin token.
    """
    try:
        blacklist = get_token_blacklist()
        storage_type = blacklist.storage_type
        stats = blacklist.get_stats()

        return TokenBlacklistStatsResponse(
            storage_type=storage_type,
            **stats,
        )

    except RuntimeError as e:
        logger.error(f"Token blacklist not initialized: {e}")
        return TokenBlacklistStatsResponse(
            storage_type="unknown",
            total_keys=0,
            error=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get token blacklist stats: {e}")
        return TokenBlacklistStatsResponse(
            storage_type="unknown",
            total_keys=0,
            error=str(e),
        )
