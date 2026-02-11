"""
Database base configuration for SQLAlchemy models.

This module uses SQLAlchemy 2.0 style with DeclarativeBase and Mapped types
for proper type checking support. See BCQ-035 for migration details.

Async support (TASK-1161): async_engine, AsyncSessionLocal, and get_async_db
are provided alongside the sync equivalents for incremental migration.
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, QueuePool
from typing import AsyncGenerator, Generator
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

# Create SQLAlchemy engine with connection pooling
engine = create_engine(
    DATABASE_URL,
    echo=DEBUG,  # Only log SQL queries in debug mode
    poolclass=QueuePool,
    pool_size=POOL_SIZE,
    max_overflow=POOL_MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,  # Verify connections are alive before using them
)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Async engine and session (TASK-1161) ---
# Convert sync URL to async driver URL:
#   postgresql://...  -> postgresql+asyncpg://...
#   sqlite:///...     -> sqlite+aiosqlite:///...
_ASYNC_DATABASE_URL = DATABASE_URL.replace(
    "postgresql://", "postgresql+asyncpg://"
).replace("sqlite:///", "sqlite+aiosqlite:///")

async_engine = create_async_engine(
    _ASYNC_DATABASE_URL,
    echo=DEBUG,
    poolclass=AsyncAdaptedQueuePool,
    pool_size=POOL_SIZE,
    max_overflow=POOL_MAX_OVERFLOW,
    pool_timeout=POOL_TIMEOUT,
    pool_recycle=POOL_RECYCLE,
    pool_pre_ping=POOL_PRE_PING,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 declarative base class with type annotation support.

    Using DeclarativeBase instead of declarative_base() enables proper
    type checking for model attributes when using Mapped[] annotations.
    """

    pass


def get_db() -> Generator:
    """
    Dependency function to get database session.

    Yields a database session and ensures proper cleanup:
    - On success: session is closed (letting SQLAlchemy handle commit/rollback)
    - On exception: explicit rollback to ensure transaction cleanup, then re-raises

    Note: Explicit rollback on exception prevents transactions from being left
    in an inconsistent state, which can occur if relying solely on connection
    closure for cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency function to get database session.

    Yields an async database session and ensures proper cleanup.
    Mirrors get_db() behavior for async endpoints.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
