"""
Database base configuration for SQLAlchemy models.

This module uses SQLAlchemy 2.0 style with DeclarativeBase and Mapped types
for proper type checking support. See BCQ-035 for migration details.

Supports both sync and async database operations:
- Async: Modern async/await pattern using AsyncSession (primary interface)
- Sync: Backward compatibility for Alembic migrations and background threads
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import QueuePool
from typing import AsyncGenerator
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost:5432/aiq_dev")

# Environment setting - echo SQL in development only
DEBUG = os.getenv("DEBUG", "True").lower() in ("true", "1", "yes")

# Database connection pool settings
# These values are optimized for typical web applications
# Adjust based on expected load and database server capacity
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))  # Number of connections to maintain
POOL_MAX_OVERFLOW = int(
    os.getenv("DB_POOL_MAX_OVERFLOW", "20")
)  # Max extra connections when pool exhausted
POOL_TIMEOUT = int(
    os.getenv("DB_POOL_TIMEOUT", "30")
)  # Seconds to wait for available connection
POOL_RECYCLE = int(
    os.getenv("DB_POOL_RECYCLE", "3600")
)  # Recycle connections after 1 hour
POOL_PRE_PING = os.getenv("DB_POOL_PRE_PING", "True").lower() in (
    "true",
    "1",
    "yes",
)  # Test connections before use


def _get_async_database_url(url: str) -> str:
    """
    Convert sync database URL to async URL.

    - PostgreSQL: postgresql:// -> postgresql+asyncpg://
    - SQLite: sqlite:/// -> sqlite+aiosqlite:///
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///")
    else:
        # Already async URL or unsupported dialect
        return url


# Async database URL for async engine
ASYNC_DATABASE_URL = _get_async_database_url(DATABASE_URL)

# Create sync SQLAlchemy engine for Alembic migrations and background threads
# Uses QueuePool for connection pooling
sync_engine = create_engine(
    DATABASE_URL,
    echo=DEBUG,  # Only log SQL queries in debug mode
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=POOL_MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,  # Verify connections are alive before using them
)

# Create async SQLAlchemy engine for FastAPI endpoints
# Connection pool parameters are passed directly to create_async_engine
async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=DEBUG,
    pool_size=POOL_SIZE,
    max_overflow=POOL_MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
)

# Sync session factory for Alembic and background threads
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

# Async session factory for FastAPI endpoints
# expire_on_commit=False allows accessing attributes after commit without triggering lazy loads
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Backward compatibility: export sync_engine as 'engine' for Alembic
engine = sync_engine


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 declarative base class with type annotation support.

    Using DeclarativeBase instead of declarative_base() enables proper
    type checking for model attributes when using Mapped[] annotations.
    """

    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency function to get database session.

    Yields an async database session and ensures proper cleanup:
    - On success: session is closed (letting SQLAlchemy handle commit/rollback)
    - On exception: explicit rollback to ensure transaction cleanup, then re-raises

    Note: Explicit rollback on exception prevents transactions from being left
    in an inconsistent state, which can occur if relying solely on connection
    closure for cleanup.

    Usage in FastAPI endpoints:
        @router.get("/items")
        async def get_items(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(Item))
            return result.scalars().all()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
