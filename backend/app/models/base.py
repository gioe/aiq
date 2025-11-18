"""
Database base configuration for SQLAlchemy models.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool
from typing import Generator
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

# Create Base class for models
Base = declarative_base()


def get_db() -> Generator:
    """
    Dependency function to get database session.
    Yields a database session and closes it after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
