"""Tests for Group, GroupMembership, and GroupInvite models."""

import string
from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.auth.security import hash_password
from app.core.datetime_utils import utc_now
from app.models import Group, GroupInvite, GroupMembership, GroupRole, User
from app.models.group import _generate_invite_code


# ---------------------------------------------------------------------------
# _generate_invite_code
# ---------------------------------------------------------------------------


class TestGenerateInviteCode:
    def test_default_length(self):
        code = _generate_invite_code()
        assert len(code) == 8

    def test_custom_length(self):
        for length in (1, 4, 16, 32):
            code = _generate_invite_code(length=length)
            assert len(code) == length

    def test_charset(self):
        allowed = set(string.ascii_uppercase + string.digits)
        for _ in range(50):
            code = _generate_invite_code()
            assert set(code).issubset(allowed)

    def test_uniqueness(self):
        codes = {_generate_invite_code() for _ in range(100)}
        assert len(codes) == 100


# ---------------------------------------------------------------------------
# GroupRole enum
# ---------------------------------------------------------------------------


class TestGroupRole:
    def test_values(self):
        assert GroupRole.OWNER.value == "owner"
        assert GroupRole.MEMBER.value == "member"

    def test_member_count(self):
        assert len(GroupRole) == 2

    def test_is_str_subclass(self):
        assert isinstance(GroupRole.OWNER, str)


# ---------------------------------------------------------------------------
# Model relationships and constraints
# ---------------------------------------------------------------------------


def _make_user(db_session, email: str) -> User:
    user = User(
        email=email,
        password_hash=hash_password("password123"),
        first_name="Test",
        last_name="User",
        notification_enabled=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_group(db_session, creator: User, name: str = "Test Group") -> Group:
    group = Group(name=name, created_by=creator.id)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)
    return group


class TestGroupModel:
    def test_create_with_defaults(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)

        assert group.id is not None
        assert group.name == "Test Group"
        assert group.created_by == user.id
        assert group.max_members == 10
        assert len(group.invite_code) == 8
        assert group.created_at is not None

    def test_creator_relationship(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)

        assert group.creator.id == user.id
        assert group.creator.email == "owner@test.com"

    def test_invite_code_unique_constraint(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        g1 = _make_group(db_session, user, "Group 1")

        g2 = Group(name="Group 2", created_by=user.id, invite_code=g1.invite_code)
        db_session.add(g2)
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestGroupMembershipModel:
    def test_create_membership(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)

        membership = GroupMembership(
            group_id=group.id, user_id=user.id, role=GroupRole.OWNER
        )
        db_session.add(membership)
        db_session.commit()
        db_session.refresh(membership)

        assert membership.id is not None
        assert membership.role == GroupRole.OWNER
        assert membership.joined_at is not None

    def test_relationship_to_group(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)

        membership = GroupMembership(
            group_id=group.id, user_id=user.id, role=GroupRole.OWNER
        )
        db_session.add(membership)
        db_session.commit()
        db_session.refresh(membership)

        assert membership.group.id == group.id
        assert group.memberships[0].id == membership.id

    def test_unique_group_user_constraint(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)

        m1 = GroupMembership(group_id=group.id, user_id=user.id, role=GroupRole.OWNER)
        db_session.add(m1)
        db_session.commit()

        m2 = GroupMembership(group_id=group.id, user_id=user.id, role=GroupRole.MEMBER)
        db_session.add(m2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_cascade_delete_on_group(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)

        membership = GroupMembership(
            group_id=group.id, user_id=user.id, role=GroupRole.OWNER
        )
        db_session.add(membership)
        db_session.commit()
        membership_id = membership.id

        db_session.delete(group)
        db_session.commit()

        assert (
            db_session.query(GroupMembership)
            .filter(GroupMembership.id == membership_id)
            .first()
            is None
        )


class TestGroupInviteModel:
    def test_create_invite(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)
        expires = utc_now() + timedelta(days=7)

        invite = GroupInvite(group_id=group.id, invited_by=user.id, expires_at=expires)
        db_session.add(invite)
        db_session.commit()
        db_session.refresh(invite)

        assert invite.id is not None
        assert len(invite.invite_code) == 8
        assert invite.accepted_by is None
        assert invite.accepted_at is None

    def test_relationship_to_group(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)
        expires = utc_now() + timedelta(days=7)

        invite = GroupInvite(group_id=group.id, invited_by=user.id, expires_at=expires)
        db_session.add(invite)
        db_session.commit()
        db_session.refresh(invite)

        assert invite.group.id == group.id
        assert invite.inviter.id == user.id
        assert group.invites[0].id == invite.id

    def test_acceptor_relationship(self, db_session):
        owner = _make_user(db_session, "owner@test.com")
        acceptor = _make_user(db_session, "member@test.com")
        group = _make_group(db_session, owner)
        expires = utc_now() + timedelta(days=7)

        invite = GroupInvite(
            group_id=group.id,
            invited_by=owner.id,
            expires_at=expires,
            accepted_by=acceptor.id,
            accepted_at=utc_now(),
        )
        db_session.add(invite)
        db_session.commit()
        db_session.refresh(invite)

        assert invite.acceptor.id == acceptor.id

    def test_invite_code_unique_constraint(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)
        expires = utc_now() + timedelta(days=7)

        inv1 = GroupInvite(group_id=group.id, invited_by=user.id, expires_at=expires)
        db_session.add(inv1)
        db_session.commit()

        inv2 = GroupInvite(
            group_id=group.id,
            invited_by=user.id,
            expires_at=expires,
            invite_code=inv1.invite_code,
        )
        db_session.add(inv2)
        with pytest.raises(IntegrityError):
            db_session.commit()

    def test_cascade_delete_on_group(self, db_session):
        user = _make_user(db_session, "owner@test.com")
        group = _make_group(db_session, user)
        expires = utc_now() + timedelta(days=7)

        invite = GroupInvite(group_id=group.id, invited_by=user.id, expires_at=expires)
        db_session.add(invite)
        db_session.commit()
        invite_id = invite.id

        db_session.delete(group)
        db_session.commit()

        assert (
            db_session.query(GroupInvite).filter(GroupInvite.id == invite_id).first()
            is None
        )
