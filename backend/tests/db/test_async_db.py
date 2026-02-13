"""
Tests for async SQLAlchemy infrastructure (TASK-1161).

Validates that the async engine, session, and fixtures work correctly.
"""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, get_db
from app.core.security import hash_password


async def test_async_engine_connects(async_db_session: AsyncSession):
    """Async engine can execute a basic query."""
    result = await async_db_session.execute(text("SELECT 1"))
    assert result.scalar() == 1


async def test_async_session_crud(async_db_session: AsyncSession):
    """Async session can create and read a record."""
    user = User(
        email="async@test.com",
        password_hash=hash_password("password123"),
        first_name="Async",
        last_name="Test",
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)

    assert user.id is not None
    assert user.email == "async@test.com"

    # Read back
    result = await async_db_session.execute(
        text("SELECT email FROM users WHERE id = :id"), {"id": user.id}
    )
    assert result.scalar() == "async@test.com"


async def test_get_db_yields_session():
    """get_db dependency yields an AsyncSession."""
    gen = get_db()
    try:
        session = await gen.__anext__()
        assert isinstance(session, AsyncSession)
    finally:
        await gen.aclose()


async def test_async_session_rollback_on_error(async_db_session: AsyncSession):
    """Async session properly handles rollback."""
    user = User(
        email="rollback@test.com",
        password_hash=hash_password("password123"),
        first_name="Rollback",
        last_name="Test",
    )
    async_db_session.add(user)
    await async_db_session.commit()

    # Try to insert duplicate email (should fail)
    duplicate = User(
        email="rollback@test.com",
        password_hash=hash_password("password123"),
        first_name="Duplicate",
        last_name="Test",
    )
    async_db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        await async_db_session.commit()

    await async_db_session.rollback()

    # Session should still be usable after rollback
    result = await async_db_session.execute(text("SELECT COUNT(*) FROM users"))
    assert result.scalar() == 1
