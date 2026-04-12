"""Group models for social features."""

from __future__ import annotations

import enum
import secrets
import string
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from sqlalchemy import ForeignKey, String, DateTime, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.datetime_utils import utc_now
from .base import Base

if TYPE_CHECKING:
    from .models import User  # noqa: F401


def _generate_invite_code(length: int = 8) -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class GroupRole(str, enum.Enum):
    OWNER = "owner"
    MEMBER = "member"


class Group(Base):
    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(30))
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    invite_code: Mapped[str] = mapped_column(
        String(8), unique=True, index=True, default=_generate_invite_code
    )
    max_members: Mapped[int] = mapped_column(default=10)

    # Relationships
    creator: Mapped["User"] = relationship(foreign_keys=[created_by])
    memberships: Mapped[List["GroupMembership"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    invites: Mapped[List["GroupInvite"]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMembership(Base):
    __tablename__ = "group_memberships"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    # GroupRole is a VARCHAR-backed enum (not a native PG enum type).
    # String(10) is specified explicitly to prevent Alembic autogenerate from
    # emitting false ALTER COLUMN statements (same pattern as CalibrationRunStatus
    # and CalibrationTrigger on CalibrationRun — see TASK-1238).
    role: Mapped[GroupRole] = mapped_column(String(10))
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship()

    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_membership_group_user"),
        Index("ix_group_memberships_user_id", "user_id"),
    )


class GroupInvite(Base):
    __tablename__ = "group_invites"

    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id", ondelete="CASCADE"))
    invited_by: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    invite_code: Mapped[str] = mapped_column(
        String(8), unique=True, index=True, default=_generate_invite_code
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    group: Mapped["Group"] = relationship(back_populates="invites")
    inviter: Mapped["User"] = relationship(foreign_keys=[invited_by])
    acceptor: Mapped[Optional["User"]] = relationship(foreign_keys=[accepted_by])
