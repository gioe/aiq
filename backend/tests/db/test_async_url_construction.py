"""
Regression tests for async database URL construction (TASK-1218 / TASK-1221).

SQLAlchemy's make_url(url).set(drivername=...) → str() round-trip silently
strips underscores from hostnames (e.g. postgres-6_4y.railway.internal
becomes postgres-64y), causing asyncpg to connect to the wrong host and
surface a misleading auth error.

The fix in base.py uses string-prefix replacement instead.  These tests
document the breakage that motivated the fix and verify the correct behaviour
for all supported URL prefixes.
"""

import pytest
from sqlalchemy.engine.url import make_url

from app.models.base import _build_async_url


# ---------------------------------------------------------------------------
# Correct behaviour: underscore hostname is preserved
# ---------------------------------------------------------------------------


def test_postgresql_underscore_hostname_preserved():
    url = "postgresql://postgres-6_4y.railway.internal:5432/railway"
    result = _build_async_url(url)
    assert result == "postgresql+asyncpg://postgres-6_4y.railway.internal:5432/railway"


def test_postgresql_psycopg2_underscore_hostname_preserved():
    url = "postgresql+psycopg2://postgres-6_4y.railway.internal:5432/railway"
    result = _build_async_url(url)
    assert result == "postgresql+asyncpg://postgres-6_4y.railway.internal:5432/railway"


def test_sqlite_url_converted():
    url = "sqlite:///relative/path/test.db"
    result = _build_async_url(url)
    assert result == "sqlite+aiosqlite:///relative/path/test.db"


def test_sqlite_absolute_path_converted():
    url = "sqlite:////tmp/test.db"
    result = _build_async_url(url)
    assert result == "sqlite+aiosqlite:////tmp/test.db"


def test_postgresql_no_underscore_still_works():
    url = "postgresql://standardhost.railway.internal:5432/railway"
    result = _build_async_url(url)
    assert result == "postgresql+asyncpg://standardhost.railway.internal:5432/railway"


def test_unsupported_prefix_raises():
    with pytest.raises(ValueError, match="No async driver mapping"):
        _build_async_url("mysql://host/db")


# ---------------------------------------------------------------------------
# Document the old SQLAlchemy round-trip breakage
# This test deliberately shows WHY the fix was needed.
# ---------------------------------------------------------------------------


def test_sqlalchemy_roundtrip_bug_is_documented():
    """Document the SQLAlchemy URL serialisation bug that motivated the fix.

    In some SQLAlchemy versions, make_url(url).set(drivername=...) → str()
    silently strips underscores from hostnames (e.g. postgres-6_4y becomes
    postgres-64y).  This was observed on Railway when DATABASE_URL contained
    a hostname like postgres-6_4y.railway.internal — asyncpg then attempted to
    connect to postgres-64y, causing a misleading auth error.

    SQLAlchemy 2.0.36+ appears to have fixed the serialisation issue; the
    workaround in _build_async_url() is retained as a safety net and because
    string-prefix replacement is simpler with no ambiguity.

    NOTE: If this test fails with `strict=True` it means the bug has returned
    in the current SQLAlchemy version — investigate before updating the guard.
    """
    original = "postgresql://postgres-6_4y.railway.internal:5432/railway"
    sqlalchemy_result = str(make_url(original).set(drivername="postgresql+asyncpg"))

    # Our fix must always produce the correct URL, regardless of SQLAlchemy.
    assert _build_async_url(original) == (
        "postgresql+asyncpg://postgres-6_4y.railway.internal:5432/railway"
    )

    if "postgres-6_4y" not in sqlalchemy_result:
        # Bug is present in the current SQLAlchemy — the workaround is still needed.
        assert "postgres-64y" in sqlalchemy_result, (
            "SQLAlchemy mangled the hostname in an unexpected way: "
            f"{sqlalchemy_result!r}"
        )
    # else: current SQLAlchemy preserves underscores — the workaround is a no-op
    # but is harmless and guards against future regressions or downgrades.
