"""
Group endpoints for social features.

Provides CRUD operations for groups, membership management, invite link
generation, and a per-group leaderboard based on test results.
"""

import logging
from datetime import timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select, func, and_
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth.dependencies import get_current_user
from app.core.datetime_utils import utc_now
from app.core.error_responses import (
    ErrorMessages,
    raise_bad_request,
    raise_conflict,
    raise_forbidden,
    raise_not_found,
    raise_server_error,
)
from app.models import get_db, User
from app.models.group import Group, GroupInvite, GroupMembership, GroupRole
from app.models.models import TestResult
from app.schemas.groups import (
    CreateGroupRequest,
    GroupDetailResponse,
    GroupInviteResponse,
    GroupMemberResponse,
    GroupResponse,
    JoinGroupRequest,
    LeaderboardEntryResponse,
    LeaderboardResponse,
    TransferOwnershipRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Named constants
# ---------------------------------------------------------------------------

_INVITE_EXPIRY_DAYS = 7  # GroupInvite validity window


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


async def _get_membership(
    db: AsyncSession,
    group_id: int,
    user_id: int,
) -> Optional[GroupMembership]:
    """Return the GroupMembership for (group_id, user_id), or None."""
    result = await db.execute(
        select(GroupMembership).where(
            and_(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id == user_id,
            )
        )
    )
    return result.scalar_one_or_none()


async def _require_membership(
    db: AsyncSession,
    group_id: int,
    user_id: int,
) -> GroupMembership:
    """Return the membership or raise 403 if the user is not a member."""
    membership = await _get_membership(db, group_id, user_id)
    if membership is None:
        raise_forbidden("You are not a member of this group.")
    return membership  # type: ignore[return-value]


async def _get_group_or_404(db: AsyncSession, group_id: int) -> Group:
    """Return the Group by PK or raise 404."""
    result = await db.execute(select(Group).where(Group.id == group_id))
    group = result.scalar_one_or_none()
    if group is None:
        raise_not_found("Group not found.")
    return group  # type: ignore[return-value]


async def _member_count(db: AsyncSession, group_id: int) -> int:
    """Return the current member count for a group."""
    result = await db.execute(
        select(func.count())
        .select_from(GroupMembership)
        .where(GroupMembership.group_id == group_id)
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/",
    response_model=GroupResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_group(
    body: CreateGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupResponse:
    """
    Create a new group.

    Creates the group and automatically adds the creator as the owner.

    Args:
        body: CreateGroupRequest containing the group name.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        GroupResponse with member_count=1.
    """
    try:
        group = Group(name=body.name, created_by=current_user.id)
        db.add(group)
        await db.flush()  # Populate group.id before creating membership

        membership = GroupMembership(
            group_id=group.id,
            user_id=current_user.id,
            role=GroupRole.OWNER,
        )
        db.add(membership)
        await db.commit()
        await db.refresh(group)
    except SQLAlchemyError:
        await db.rollback()
        logger.error(
            "Failed to create group for user %s", current_user.id, exc_info=True
        )
        raise_server_error(ErrorMessages.database_operation_failed("create group"))

    return GroupResponse(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        invite_code=group.invite_code,
        max_members=group.max_members,
        member_count=1,
    )


@router.get("/", response_model=List[GroupResponse])
async def list_groups(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[GroupResponse]:
    """
    List all groups the current user belongs to.

    Args:
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        List of GroupResponse objects, each with a current member_count.
    """
    # Subquery: member count per group
    count_subq = (
        select(
            GroupMembership.group_id,
            func.count(GroupMembership.id).label("member_count"),
        )
        .group_by(GroupMembership.group_id)
        .subquery()
    )

    stmt = (
        select(Group, count_subq.c.member_count)
        .join(GroupMembership, GroupMembership.group_id == Group.id)
        .outerjoin(count_subq, count_subq.c.group_id == Group.id)
        .where(GroupMembership.user_id == current_user.id)
        .order_by(Group.created_at.desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        GroupResponse(
            id=group.id,
            name=group.name,
            created_by=group.created_by,
            created_at=group.created_at,
            invite_code=group.invite_code,
            max_members=group.max_members,
            member_count=count or 0,
        )
        for group, count in rows
    ]


@router.get("/{group_id}", response_model=GroupDetailResponse)
async def get_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupDetailResponse:
    """
    Return full group detail including the member list.

    Requires the caller to be a member of the group.

    Args:
        group_id: Primary key of the group.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        GroupDetailResponse with members list.
    """
    group = await _get_group_or_404(db, group_id)
    await _require_membership(db, group_id, current_user.id)

    # Fetch all members with their user first_name in one query
    stmt = (
        select(GroupMembership, User.first_name)
        .join(User, GroupMembership.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(GroupMembership.joined_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    members = [
        GroupMemberResponse(
            user_id=membership.user_id,
            first_name=first_name or "",
            role=membership.role.value,
            joined_at=membership.joined_at,
        )
        for membership, first_name in rows
    ]

    count = await _member_count(db, group_id)

    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        invite_code=group.invite_code,
        max_members=group.max_members,
        member_count=count,
        members=members,
    )


@router.post("/{group_id}/invite", response_model=GroupInviteResponse)
async def generate_invite(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupInviteResponse:
    """
    Generate a new invite link for the group.

    Only the group owner can generate invites.

    Args:
        group_id: Primary key of the group.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        GroupInviteResponse with the new invite code and expiry.
    """
    await _get_group_or_404(db, group_id)

    membership = await _get_membership(db, group_id, current_user.id)
    if membership is None or membership.role != GroupRole.OWNER:
        raise_forbidden("Only the group owner can perform this action.")

    try:
        expires_at = utc_now() + timedelta(days=_INVITE_EXPIRY_DAYS)
        invite = GroupInvite(
            group_id=group_id,
            invited_by=current_user.id,
            expires_at=expires_at,
        )
        db.add(invite)
        await db.commit()
        await db.refresh(invite)
    except SQLAlchemyError:
        await db.rollback()
        logger.error(
            "Failed to create invite for group %s by user %s",
            group_id,
            current_user.id,
            exc_info=True,
        )
        raise_server_error(
            ErrorMessages.database_operation_failed("create group invite")
        )

    return invite  # type: ignore[return-value]


@router.post("/join", response_model=GroupResponse)
async def join_group(
    body: JoinGroupRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupResponse:
    """
    Join a group using an invite code.

    Accepts either a generated GroupInvite code (with expiry enforcement) or
    the permanent Group.invite_code. Generated invites are checked first; if
    a valid, unexpired invite is found, the acceptor is recorded on it.

    Args:
        body: JoinGroupRequest containing the invite_code.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        GroupResponse for the joined group.
    """
    group: Optional[Group] = None
    invite: Optional[GroupInvite] = None

    # 1. Try generated GroupInvite codes first (respects expiry)
    result = await db.execute(
        select(GroupInvite).where(GroupInvite.invite_code == body.invite_code)
    )
    invite = result.scalar_one_or_none()
    if invite is not None:
        now = utc_now()
        if invite.expires_at < now:
            raise_bad_request("This invite code has expired.")
        if invite.accepted_by is not None:
            raise_conflict("This invite code has already been used.")
        # Resolve the group from the invite
        group_result = await db.execute(
            select(Group).where(Group.id == invite.group_id)
        )
        group = group_result.scalar_one_or_none()
    else:
        # 2. Fall back to the permanent Group.invite_code
        group_result = await db.execute(
            select(Group).where(Group.invite_code == body.invite_code)
        )
        group = group_result.scalar_one_or_none()

    if group is None:
        raise_not_found("Invalid invite code.")

    # Check not already a member
    existing = await _get_membership(db, group.id, current_user.id)
    if existing is not None:
        raise_conflict("You are already a member of this group.")

    # Enforce member cap (use the per-group max_members, not a global constant)
    count = await _member_count(db, group.id)
    if count >= group.max_members:
        raise_bad_request("This group has reached its maximum member limit.")

    try:
        membership = GroupMembership(
            group_id=group.id,
            user_id=current_user.id,
            role=GroupRole.MEMBER,
        )
        db.add(membership)

        # Record acceptance on the invite if one was used
        if invite is not None:
            invite.accepted_by = current_user.id
            invite.accepted_at = utc_now()

        await db.commit()
    except IntegrityError:
        # Race condition: another request created the membership concurrently
        await db.rollback()
        raise_conflict("You are already a member of this group.")
    except SQLAlchemyError as e:
        await db.rollback()
        logger.error(
            "Failed to add user %s to group %s: %s",
            current_user.id,
            group.id,
            e,
        )
        raise_server_error(ErrorMessages.database_operation_failed("join group"))

    new_count = await _member_count(db, group.id)

    return GroupResponse(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        invite_code=group.invite_code,
        max_members=group.max_members,
        member_count=new_count,
    )


@router.get("/{group_id}/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    days: Optional[int] = Query(
        None,
        ge=1,
        le=3650,
        description="Only include test results from the last N days",
    ),
    limit: Optional[int] = Query(
        None,
        ge=1,
        le=100,
        description="Maximum number of entries to return",
    ),
    offset: Optional[int] = Query(
        None,
        ge=0,
        description="Number of entries to skip (requires limit)",
    ),
) -> LeaderboardResponse:
    """
    Return a ranked leaderboard for all group members.

    Members with no test results appear at the bottom with scores of 0.
    Requires the caller to be a member of the group.

    Supports an optional time-window filter (``days``) that restricts score
    aggregation to results completed within the last *N* days, and optional
    pagination via ``limit`` / ``offset``.

    Args:
        group_id: Primary key of the group.
        current_user: Authenticated user making the request.
        db: Async database session.
        days: Optional time window — only aggregate results from the last N days.
        limit: Optional page size for pagination.
        offset: Optional offset for pagination (requires limit).

    Returns:
        LeaderboardResponse with ranked entries for every group member.
    """
    group = await _get_group_or_404(db, group_id)
    await _require_membership(db, group_id, current_user.id)

    # Subquery: best and average IQ score per user (scoped to group members)
    member_ids = select(GroupMembership.user_id).where(
        GroupMembership.group_id == group_id
    )
    score_stmt = select(
        TestResult.user_id,
        func.max(TestResult.iq_score).label("best_score"),
        func.avg(TestResult.iq_score).label("average_score"),
    ).where(TestResult.user_id.in_(member_ids))
    if days is not None:
        cutoff = utc_now() - timedelta(days=days)
        score_stmt = score_stmt.where(TestResult.completed_at >= cutoff)
    score_subq = score_stmt.group_by(TestResult.user_id).subquery()

    # Join group members with scores; left-join so zero-result members appear
    stmt = (
        select(
            GroupMembership.user_id,
            User.first_name,
            score_subq.c.best_score,
            score_subq.c.average_score,
        )
        .join(User, GroupMembership.user_id == User.id)
        .outerjoin(score_subq, GroupMembership.user_id == score_subq.c.user_id)
        .where(GroupMembership.group_id == group_id)
        .order_by(func.coalesce(score_subq.c.best_score, 0).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()
    total_count = len(rows)

    # Apply pagination after ranking so rank values are globally correct
    if limit is not None:
        start = offset or 0
        rows = rows[start : start + limit]
    elif offset is not None:
        rows = rows[offset:]

    entries = [
        LeaderboardEntryResponse(
            rank=(offset or 0) + idx + 1,
            user_id=user_id,
            first_name=first_name or "",
            best_score=best_score if best_score is not None else 0,
            average_score=float(average_score) if average_score is not None else 0.0,
        )
        for idx, (user_id, first_name, best_score, average_score) in enumerate(rows)
    ]

    return LeaderboardResponse(
        group_id=group.id,
        group_name=group.name,
        entries=entries,
        total_count=total_count,
        limit=limit,
        offset=offset if limit is not None else None,
        has_more=(
            ((offset or 0) + limit < total_count) if limit is not None else False
        ),
        days=days,
    )


@router.delete(
    "/{group_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_member(
    group_id: int,
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Remove a member from a group (leave or kick).

    A user may remove themselves (leave). The group owner may remove any
    non-owner member. The owner cannot be removed via this endpoint.

    Args:
        group_id: Primary key of the group.
        user_id: ID of the user to remove.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        No content (204) on success.
    """
    await _get_group_or_404(db, group_id)

    caller_membership = await _get_membership(db, group_id, current_user.id)
    if caller_membership is None:
        raise_forbidden("You are not a member of this group.")

    # Determine whether this is a self-removal or a kick
    is_self = current_user.id == user_id
    is_owner = caller_membership.role == GroupRole.OWNER

    if not is_self and not is_owner:
        raise_forbidden("Only the group owner can remove other members.")

    # Resolve the target membership
    target_membership: GroupMembership
    if is_self:
        target_membership = caller_membership
    else:
        maybe_target = await _get_membership(db, group_id, user_id)
        if maybe_target is None:
            raise_not_found("Member not found in this group.")
        target_membership = maybe_target

    # Owners cannot be removed
    if target_membership.role == GroupRole.OWNER:
        raise_bad_request("The group owner cannot be removed.")

    try:
        await db.delete(target_membership)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        logger.error(
            "Failed to remove user %s from group %s", user_id, group_id, exc_info=True
        )
        raise_server_error(
            ErrorMessages.database_operation_failed("remove group member")
        )

    return None


@router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_group(
    group_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a group and all associated memberships and invites.

    Only the group owner can delete the group. Cascade deletes on the ORM
    relationships handle memberships and invites automatically.

    Args:
        group_id: Primary key of the group.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        No content (204) on success.
    """
    group = await _get_group_or_404(db, group_id)

    membership = await _get_membership(db, group_id, current_user.id)
    if membership is None or membership.role != GroupRole.OWNER:
        raise_forbidden("Only the group owner can perform this action.")

    try:
        await db.delete(group)
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        logger.error(
            "Failed to delete group %s by user %s",
            group_id,
            current_user.id,
            exc_info=True,
        )
        raise_server_error(ErrorMessages.database_operation_failed("delete group"))

    return None


@router.put("/{group_id}/transfer-ownership", response_model=GroupDetailResponse)
async def transfer_ownership(
    group_id: int,
    body: TransferOwnershipRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GroupDetailResponse:
    """
    Transfer group ownership to another member.

    Only the current owner can transfer ownership. The new owner must already
    be a member of the group. After transfer, the previous owner becomes a
    regular member.

    Args:
        group_id: Primary key of the group.
        body: TransferOwnershipRequest containing the new_owner_id.
        current_user: Authenticated user making the request.
        db: Async database session.

    Returns:
        GroupDetailResponse reflecting the updated roles.
    """
    group = await _get_group_or_404(db, group_id)

    # Caller must be the current owner
    caller_membership = await _get_membership(db, group_id, current_user.id)
    if caller_membership is None or caller_membership.role != GroupRole.OWNER:
        raise_forbidden("Only the group owner can transfer ownership.")

    # Cannot transfer to yourself
    if body.new_owner_id == current_user.id:
        raise_bad_request("You are already the owner of this group.")

    # New owner must be a current member
    new_owner_membership = await _get_membership(db, group_id, body.new_owner_id)
    if new_owner_membership is None:
        raise_not_found("The specified user is not a member of this group.")

    try:
        caller_membership.role = GroupRole.MEMBER
        new_owner_membership.role = GroupRole.OWNER
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        logger.error(
            "Failed to transfer ownership of group %s from user %s to user %s",
            group_id,
            current_user.id,
            body.new_owner_id,
            exc_info=True,
        )
        raise_server_error(
            ErrorMessages.database_operation_failed("transfer group ownership")
        )

    # Build the response with refreshed member list
    stmt = (
        select(GroupMembership, User.first_name)
        .join(User, GroupMembership.user_id == User.id)
        .where(GroupMembership.group_id == group_id)
        .order_by(GroupMembership.joined_at)
    )
    result = await db.execute(stmt)
    rows = result.all()

    members = [
        GroupMemberResponse(
            user_id=membership.user_id,
            first_name=first_name or "",
            role=membership.role.value,
            joined_at=membership.joined_at,
        )
        for membership, first_name in rows
    ]

    count = await _member_count(db, group_id)

    return GroupDetailResponse(
        id=group.id,
        name=group.name,
        created_by=group.created_by,
        created_at=group.created_at,
        invite_code=group.invite_code,
        max_members=group.max_members,
        member_count=count,
        members=members,
    )
