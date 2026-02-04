"""
Token blacklist for JWT revocation.

Provides Redis-backed token blacklist with graceful fallback to in-memory storage.
"""
import logging
from typing import Optional, Union
from datetime import datetime

from app.core.datetime_utils import utc_now
from app.ratelimit.storage import InMemoryStorage, RedisStorage

logger = logging.getLogger(__name__)

# Connection pool configuration
# Based on expected concurrent logout operations per worker
REDIS_CONNECTION_POOL_SIZE = 10

# Timeout configuration (seconds)
# Short timeouts to fail fast if Redis is unresponsive
REDIS_SOCKET_TIMEOUT = 2.0
REDIS_SOCKET_CONNECT_TIMEOUT = 2.0

# In-memory blacklist configuration
# Cleanup interval (seconds) for expired entries
IN_MEMORY_CLEANUP_INTERVAL = 60
# Maximum keys to prevent memory exhaustion in single-worker deployments
# With 30-minute token expiry, 10k tokens supports ~333 logouts/minute sustained
IN_MEMORY_MAX_KEYS = 10000


class TokenBlacklist:
    """
    Token blacklist for revoking JWTs before expiration.

    Uses Redis for distributed blacklist across multiple workers when available.
    Falls back to in-memory storage if Redis is unavailable (logs warning).

    Design:
    - Stores revoked token JTIs (JWT IDs) with TTL matching token expiration
    - Automatic expiration prevents unbounded growth
    - Graceful degradation if Redis fails (allows request with warning)
    """

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize token blacklist with optional Redis backend.

        Args:
            redis_url: Redis connection URL. If None, uses in-memory storage.
        """
        self._storage: Union[RedisStorage, InMemoryStorage]
        self._use_redis = False
        use_in_memory = True  # Track whether we need in-memory fallback

        if redis_url:
            try:
                redis_storage = RedisStorage(
                    redis_url=redis_url,
                    key_prefix="token_blacklist:",
                    connection_pool_size=REDIS_CONNECTION_POOL_SIZE,
                    socket_timeout=REDIS_SOCKET_TIMEOUT,
                    socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                )

                # Test connection
                if redis_storage.is_connected():
                    self._storage = redis_storage
                    self._use_redis = True
                    use_in_memory = False
                    logger.info("Token blacklist using Redis storage")
                else:
                    logger.warning(
                        "Redis connection failed for token blacklist. "
                        "Falling back to in-memory storage. "
                        "Token revocation will only work within single worker."
                    )
            except ImportError:
                logger.warning(
                    "redis-py not installed. Token blacklist using in-memory storage. "
                    "Install redis-py for distributed token revocation."
                )
            except Exception as e:
                logger.error(f"Failed to initialize Redis for token blacklist: {e}")

        # Fallback to in-memory storage
        if use_in_memory:
            self._storage = InMemoryStorage(
                cleanup_interval=IN_MEMORY_CLEANUP_INTERVAL,
                max_keys=IN_MEMORY_MAX_KEYS,
            )
            logger.info("Token blacklist using in-memory storage")

    @property
    def storage_type(self) -> str:
        """Return the storage backend type: 'redis' or 'memory'."""
        return "redis" if self._use_redis else "memory"

    def revoke_token(self, jti: str, expires_at: datetime) -> bool:
        """
        Add a token to the blacklist.

        Args:
            jti: JWT ID (unique token identifier)
            expires_at: Token expiration timestamp (for TTL calculation)

        Returns:
            True if token was successfully blacklisted, False on error
        """
        try:
            # Calculate TTL based on token expiration
            now = utc_now()
            if expires_at <= now:
                # Token already expired, no need to blacklist
                logger.debug(f"Token {jti[:8]}... already expired, skipping blacklist")
                return True

            ttl_seconds = int((expires_at - now).total_seconds())

            # Store in blacklist with TTL
            self._storage.set(jti, {"revoked_at": now.isoformat()}, ttl=ttl_seconds)

            logger.info(f"Token {jti[:8]}... blacklisted (TTL: {ttl_seconds}s)")
            return True

        except Exception as e:
            logger.error(f"Failed to blacklist token {jti[:8]}...: {e}")
            # Graceful degradation: Log error but don't fail the request
            return False

    def is_revoked(self, jti: str) -> bool:
        """
        Check if a token is blacklisted.

        Args:
            jti: JWT ID to check

        Returns:
            True if token is revoked, False otherwise
        """
        try:
            result = self._storage.get(jti)
            return result is not None

        except Exception as e:
            logger.error(f"Error checking token blacklist for {jti[:8]}...: {e}")
            # Graceful degradation: On error, allow the request with warning
            logger.warning(
                "Token blacklist check failed. Allowing request. "
                "This could be a security issue if Redis is down."
            )
            return False

    def clear_all(self) -> None:
        """
        Clear all blacklisted tokens.

        WARNING: This should only be used in testing or emergency scenarios.
        """
        try:
            self._storage.clear()
            logger.warning("Token blacklist cleared (all revoked tokens removed)")
        except Exception as e:
            logger.error(f"Failed to clear token blacklist: {e}")

    def get_stats(self) -> dict:
        """
        Get blacklist statistics for monitoring.

        Returns:
            Dict with storage statistics
        """
        try:
            return self._storage.get_stats()
        except Exception as e:
            logger.error(f"Failed to get token blacklist stats: {e}")
            return {"error": str(e)}

    def close(self) -> None:
        """
        Close storage connection pools.

        Should be called on application shutdown to prevent resource leaks.
        """
        if hasattr(self._storage, "close"):
            self._storage.close()
            logger.info("Closed token blacklist storage connection pool")


# Global token blacklist instance (initialized in main.py)
_token_blacklist: Optional[TokenBlacklist] = None


def get_token_blacklist() -> TokenBlacklist:
    """
    Get the global token blacklist instance.

    Returns:
        TokenBlacklist instance

    Raises:
        RuntimeError: If blacklist hasn't been initialized
    """
    if _token_blacklist is None:
        raise RuntimeError(
            "Token blacklist not initialized. "
            "Call init_token_blacklist() in main.py startup."
        )
    return _token_blacklist


def init_token_blacklist(redis_url: Optional[str] = None) -> TokenBlacklist:
    """
    Initialize the global token blacklist instance.

    Should be called once during application startup.

    Args:
        redis_url: Optional Redis connection URL

    Returns:
        TokenBlacklist instance
    """
    global _token_blacklist
    _token_blacklist = TokenBlacklist(redis_url=redis_url)
    return _token_blacklist
