"""
Tests for SQLAlchemy enum DB value behavior (TASK-130).

Documents and guards against the assumption that SA sends .value (lowercase)
to PostgreSQL. By default, SA sends .name (UPPERCASE). TASK-122 uncovered
a migration written with the wrong assumption; this test prevents recurrence.
"""

import sqlalchemy as sa

from app.models.models import GenerationRunStatus


def test_default_sa_enum_sends_name_uppercase():
    """SA sends .name (UPPERCASE) to the DB when no values_callable is set."""
    enum_type = sa.Enum(GenerationRunStatus)
    for member in GenerationRunStatus:
        assert enum_type._db_value_for_elem(member) == member.name


def test_default_sa_enum_db_value_for_each_member():
    """Assert exact uppercase DB labels for each GenerationRunStatus member."""
    enum_type = sa.Enum(GenerationRunStatus)
    assert enum_type._db_value_for_elem(GenerationRunStatus.RUNNING) == "RUNNING"
    assert enum_type._db_value_for_elem(GenerationRunStatus.SUCCESS) == "SUCCESS"
    assert (
        enum_type._db_value_for_elem(GenerationRunStatus.PARTIAL_FAILURE)
        == "PARTIAL_FAILURE"
    )
    assert enum_type._db_value_for_elem(GenerationRunStatus.FAILED) == "FAILED"


def test_values_callable_override_sends_value_lowercase():
    """With values_callable=lambda obj: [e.value for e in obj], SA sends .value (lowercase)."""
    enum_type = sa.Enum(
        GenerationRunStatus,
        values_callable=lambda obj: [e.value for e in obj],
    )
    for member in GenerationRunStatus:
        assert enum_type._db_value_for_elem(member) == member.value


def test_name_vs_value_differ_for_all_members():
    """Guards that .name and .value are always distinct for GenerationRunStatus members.

    If they ever converge (e.g. someone redefines the enum with uppercase values),
    the migration risk disappears — but this test would catch that change too.
    """
    for member in GenerationRunStatus:
        assert member.name != member.value, (
            f"{member}: .name ({member.name!r}) == .value ({member.value!r}); "
            "if these converge the SA default-vs-values_callable distinction no longer matters"
        )
