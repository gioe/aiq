"""
Database base configuration for SQLAlchemy models.

This module uses SQLAlchemy 2.0 style with DeclarativeBase and Mapped types
for proper type checking support. See BCQ-035 for migration details.

Async database support (TASK-1161): The primary database dependency is
async (get_db yields AsyncSession). The sync engine and SessionLocal are
retained for background jobs that run in threads.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import AsyncAdaptedQueuePool, QueuePool
from typing import AsyncGenerator
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database URL from environment.
# If DATABASE_URL resolves to an empty string it usually means a Railway reference
# variable (e.g. ${{Postgres.DATABASE_URL}}) didn't resolve because the service name
# in the reference doesn't exactly match the Postgres service name in the dashboard.
# Fix: open Railway dashboard → Postgres service → copy the exact service name →
# update the variable to ${{<ExactName>.DATABASE_URL}}.
_DATABASE_URL_RAW = os.getenv("DATABASE_URL", "")
_is_production = os.getenv("ENV", "development").lower() == "production"
if not _DATABASE_URL_RAW:
    if _is_production:
        raise RuntimeError(
            "DATABASE_URL is not set or is empty. "
            "On Railway, the reference variable is not resolving — check that the "
            "service name in ${{<Name>.DATABASE_URL}} exactly matches the Postgres "
            "service name shown in your Railway dashboard."
        )
    DATABASE_URL = "postgresql://localhost:5432/aiq_dev"
else:
    DATABASE_URL = _DATABASE_URL_RAW

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

# --- Sync engine (retained for background jobs / batch scripts) ---
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

# Sync session factory — used by background jobs (calibration_runner,
# data_export, reliability reports) that run in threads.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# --- Async engine and session (primary for all FastAPI endpoints) ---
# Build the async URL by string-prefix replacement on the raw DATABASE_URL.
# We intentionally avoid the make_url() → set(drivername) → str() round-trip
# because SQLAlchemy's URL serialiser strips underscores from hostnames
# (e.g. postgres-6_4y.railway.internal becomes postgres-64y), which causes
# asyncpg to connect to the wrong host and surface a misleading auth error.
_SYNC_PREFIX_MAP = {
    "postgresql+psycopg2://": "postgresql+asyncpg://",
    "postgresql://": "postgresql+asyncpg://",
    "sqlite://": "sqlite+aiosqlite://",
}
_ASYNC_DATABASE_URL: str = ""
for _sync_prefix, _async_prefix in _SYNC_PREFIX_MAP.items():
    if DATABASE_URL.startswith(_sync_prefix):
        _ASYNC_DATABASE_URL = _async_prefix + DATABASE_URL[len(_sync_prefix) :]
        break
if not _ASYNC_DATABASE_URL:
    raise ValueError(
        f"No async driver mapping for DATABASE_URL prefix. "
        f"Supported prefixes: {list(_SYNC_PREFIX_MAP.keys())}"
    )

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


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Async dependency function to get database session.

    Yields an async database session and ensures proper cleanup.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
        except Exception:
            await db.rollback()
            raise
