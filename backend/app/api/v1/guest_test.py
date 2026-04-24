"""
Guest test endpoints — unauthenticated test sessions (TASK-359).

Two endpoints are exposed:

    POST /v1/test/guest/start   — Start a guest test; returns questions + one-time token
    POST /v1/test/guest/submit  — Submit answers; returns IQ score

Design decisions
----------------
* Sentinel user: All guest DB rows (TestSession, Response, TestResult) reference
  GUEST_USER_ID (default -1).  That row must exist in the users table (inserted
  by an Alembic migration) because of the FK constraint on test_sessions.user_id.

* Guest token: A UUID string stored in a Redis-backed token store (with in-memory
  fallback).  Each token maps to {"session_id": int, "device_id": str,
  "question_ids": list, "created_at": str}.  The token is consumed (deleted) on
  first successful submit; a second submit with the same token returns 400.
  Redis storage ensures tokens are shared across gunicorn workers (TASK-463).

* Device limit: Enforced via the guest_device_limits table.  Tests-taken is
  incremented only after a successful submit so that a failed submit doesn't
  penalise the user.

* Seen-question filtering: We pass skip_seen_filter=True to skip the UserQuestion
  join entirely — same flag used by LLM benchmark runs.  We do NOT create
  UserQuestion rows for guests because the UNIQUE(user_id, question_id) constraint
  would conflict across multiple guest sessions sharing the sentinel user_id.
  Instead, valid question IDs are stored in the token payload for submit validation.
"""

import logging
import uuid
from datetime import timedelta
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, Depends, Header
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.datetime_utils import utc_now
from app.core.error_responses import (
    ErrorMessages,
    raise_bad_request,
    raise_conflict,
    raise_not_found,
)
from app.core.graceful_failure import graceful_failure
from app.core.question_utils import question_to_response
from app.core.scoring.test_composition import async_select_stratified_questions
from app.models import Question, TestSession, User, UserQuestion, get_db
from app.models.models import GuestDeviceLimit, Response, TestResult, TestStatus
from app.ratelimit.storage import InMemoryStorage, RedisStorage
from app.schemas.guest_test import (
    GuestClaimRequest,
    GuestClaimResponse,
    GuestStartTestResponse,
    GuestSubmitRequest,
    GuestSubmitTestResponse,
)
from app.schemas.responses import SubmitTestResponse
from app.schemas.test_sessions import TestSessionResponse
from app.core.auth.dependencies import get_current_user
from app.core.cache import invalidate_user_cache

# Import the submit-pipeline helpers from the authenticated test module.
# These are pure module-level functions — no class ownership — so they can be
# imported and reused here without any refactoring.
from app.api.v1.test import (
    _process_responses,
    _complete_session_and_calculate_score,
    _analyze_response_times,
    _run_validity_analysis,
    _calculate_sem_and_ci,
    _run_post_submission_updates,
    _trigger_shadow_cat,
    build_test_result_response,
    get_test_session_or_404,
    verify_session_in_progress,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Guest token store (Redis-backed with in-memory fallback)
# ---------------------------------------------------------------------------
# Keys:   UUID token string
# Values: {"token_type": str, "session_id": int, "device_id": str,
#          "question_ids": list, "result_id": int, "created_at": str (ISO 8601)}
# TTL:    GUEST_TOKEN_TTL_MINUTES (default 45 minutes)
#
# Uses Redis when GUEST_TOKEN_REDIS_URL is configured so that tokens are shared
# across gunicorn workers.  Falls back to in-memory storage for single-worker
# or development deployments.

GuestTokenPayload = Dict[str, Any]  # session_id, device_id, created_at

# Global store — initialised in init_guest_token_store() called from main.py
_token_store: Optional[Union[RedisStorage, InMemoryStorage]] = None


def init_guest_token_store(
    redis_url: Optional[str] = None,
) -> Union[RedisStorage, InMemoryStorage]:
    """
    Initialise the global guest-token storage backend.

    Called once during application startup (main.py lifespan).

    Args:
        redis_url: Optional Redis connection URL.  If empty/None, uses in-memory.

    Returns:
        The storage instance that was assigned to the module global.
    """
    global _token_store

    if redis_url:
        try:
            store = RedisStorage(
                redis_url=redis_url,
                key_prefix="guest_token:",
                connection_pool_size=10,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            if store.is_connected():
                _token_store = store
                logger.info("Guest token store using Redis storage")
                return _token_store
            else:
                logger.warning(
                    "Redis not available for guest token store. "
                    "Falling back to in-memory storage. "
                    "Tokens will NOT be shared across workers."
                )
        except ImportError:
            logger.warning(
                "redis-py not installed. Guest token store using in-memory storage."
            )
        except Exception as e:
            logger.error(f"Failed to initialise Redis for guest token store: {e}")

    _token_store = InMemoryStorage(cleanup_interval=60, max_keys=10_000)
    logger.info("Guest token store using in-memory storage")
    return _token_store


def _get_token_store() -> Union[RedisStorage, InMemoryStorage]:
    """Return the initialised token store, or lazily create an in-memory one."""
    global _token_store
    if _token_store is None:
        _token_store = InMemoryStorage(cleanup_interval=60, max_keys=10_000)
        logger.warning(
            "Guest token store accessed before init_guest_token_store() — "
            "using in-memory fallback"
        )
    return _token_store


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_TOKEN_TTL_SECONDS = settings.GUEST_TOKEN_TTL_MINUTES * 60


def _generate_guest_token(
    session_id: int, device_id: str, question_ids: list[int]
) -> str:
    """
    Generate a UUID token, store it in the shared token store, and return it.

    Args:
        session_id:   The TestSession.id to associate with this token.
        device_id:    The device identifier from X-Device-Id header.
        question_ids: IDs of questions served in this session (for submit validation).

    Returns:
        A fresh UUID4 token string.
    """
    token = str(uuid.uuid4())
    payload: GuestTokenPayload = {
        "session_id": session_id,
        "device_id": device_id,
        "question_ids": question_ids,
        "token_type": "submit",
        "created_at": utc_now().isoformat(),
    }
    _get_token_store().set(token, payload, ttl=_TOKEN_TTL_SECONDS)
    logger.debug(
        "Guest token created for session_id=%s device_id=%s",
        session_id,
        device_id,
    )
    return token


def _consume_guest_token(token: str) -> Optional[GuestTokenPayload]:
    """
    Look up and atomically remove a token from the store (single-use).

    Returns None if the token is missing or has already expired/been consumed.

    Args:
        token: The token string from the client request.

    Returns:
        GuestTokenPayload dict if valid, else None.
    """
    store = _get_token_store()
    payload = store.get(token)
    if payload is None or payload.get("token_type", "submit") != "submit":
        logger.warning(
            "Guest token lookup failed (expired or already consumed): %s", token
        )
        return None
    store.delete(token)
    return payload


def _generate_guest_claim_token(session_id: int, result_id: int) -> str:
    """
    Generate a short-lived token for claiming a completed guest result.

    Claim tokens are not consumed on successful claim. Keeping them in the
    store until TTL expiry lets repeated attempts return a clear already-claimed
    response instead of collapsing into an indistinguishable invalid-token error.
    """
    token = str(uuid.uuid4())
    payload: GuestTokenPayload = {
        "token_type": "claim",
        "session_id": session_id,
        "result_id": result_id,
        "created_at": utc_now().isoformat(),
    }
    _get_token_store().set(token, payload, ttl=_TOKEN_TTL_SECONDS)
    logger.debug(
        "Guest claim token created for session_id=%s result_id=%s",
        session_id,
        result_id,
    )
    return token


def _get_guest_claim_token(token: str) -> Optional[GuestTokenPayload]:
    """Look up a guest claim token without consuming it."""
    payload = _get_token_store().get(token)
    if payload is None or payload.get("token_type") != "claim":
        logger.warning("Guest claim token lookup failed: %s", token)
        return None
    return payload


async def _get_or_create_device_limit(
    db: AsyncSession,
    device_id: str,
) -> GuestDeviceLimit:
    """
    Fetch the GuestDeviceLimit row for *device_id*, creating it if absent.

    Uses an INSERT … ON CONFLICT DO NOTHING pattern via a try/flush/rollback
    cycle to be safe against concurrent requests from the same device.

    Args:
        db:        Async database session.
        device_id: The client's device identifier string.

    Returns:
        GuestDeviceLimit ORM object (not yet committed by this helper).
    """
    stmt = select(GuestDeviceLimit).where(GuestDeviceLimit.device_id == device_id)
    result = await db.execute(stmt)
    device_limit = result.scalar_one_or_none()

    if device_limit is None:
        device_limit = GuestDeviceLimit(
            device_id=device_id,
            tests_taken=0,
            first_test_at=utc_now(),
            last_test_at=utc_now(),
        )
        db.add(device_limit)
        try:
            await db.flush()
        except IntegrityError:
            # Race condition: another request inserted the row between our
            # SELECT and INSERT.  Rollback the flush and re-fetch.
            await db.rollback()
            result = await db.execute(stmt)
            device_limit = result.scalar_one()

    return device_limit


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/start", response_model=GuestStartTestResponse)
async def start_guest_test(
    x_device_id: str = Header(
        ...,
        alias="X-Device-Id",
        description=(
            "Unique identifier for this device. "
            "Used to enforce the per-device guest test limit."
        ),
    ),
    db: AsyncSession = Depends(get_db),
) -> GuestStartTestResponse:
    """
    Start a new guest test session.

    No authentication required. Returns all questions upfront (fixed-form),
    plus a one-time *guest_token* that must be included when submitting answers.

    Args:
        x_device_id: Client-supplied device identifier (from X-Device-Id header).
        db:          Database session.

    Returns:
        GuestStartTestResponse with questions, guest_token, and tests_remaining.

    Raises:
        HTTPException 400: X-Device-Id header is blank.
        HTTPException 404: No active questions found.
        HTTPException 429: Device has reached the guest test limit.
    """
    # 1. Validate device ID
    device_id = x_device_id.strip()
    if not device_id:
        raise_bad_request(ErrorMessages.GUEST_DEVICE_ID_REQUIRED)

    # 2. Enforce per-device test limit
    device_limit = await _get_or_create_device_limit(db, device_id)

    if device_limit.tests_taken >= settings.GUEST_TEST_LIMIT:
        logger.info(
            "Guest test blocked: device_id=%s tests_taken=%d limit=%d",
            device_id,
            device_limit.tests_taken,
            settings.GUEST_TEST_LIMIT,
        )
        from fastapi import HTTPException, status

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"Guest test limit reached ({settings.GUEST_TEST_LIMIT} tests). "
                "Please create an account to continue."
            ),
            headers={"Retry-After": "0", "X-Tests-Remaining": "0"},
        )

    # 3. Abandon stale IN_PROGRESS guest sessions older than the token TTL.
    #    Housekeeping only — the unique index now excludes GUEST_USER_ID so
    #    concurrent guest starts no longer conflict.
    ttl_cutoff = utc_now() - timedelta(minutes=settings.GUEST_TOKEN_TTL_MINUTES)
    await db.execute(
        update(TestSession)
        .where(
            TestSession.user_id == settings.GUEST_USER_ID,
            TestSession.status == TestStatus.IN_PROGRESS,
            TestSession.started_at < ttl_cutoff,
        )
        .values(status=TestStatus.ABANDONED)
    )

    # 4. Select questions using the sentinel user (skip seen-question filter because
    #    the sentinel user has no UserQuestion records — every question looks "unseen"
    #    — and we want a randomly stratified selection, not the full pool).
    question_count = settings.TEST_TOTAL_QUESTIONS
    (
        unseen_questions,
        composition_metadata,
    ) = await async_select_stratified_questions(
        db=db,
        user_id=settings.GUEST_USER_ID,
        total_count=question_count,
        skip_seen_filter=True,
    )

    if not unseen_questions:
        raise_not_found(ErrorMessages.NO_QUESTIONS_AVAILABLE)

    # 5. Create TestSession linked to sentinel user
    test_session = TestSession(
        user_id=settings.GUEST_USER_ID,
        status=TestStatus.IN_PROGRESS,
        started_at=utc_now(),
        composition_metadata=composition_metadata,
        is_adaptive=False,
    )
    db.add(test_session)

    await db.flush()  # Obtain session ID without committing

    # NOTE: We intentionally do NOT create UserQuestion rows for guests.
    # The UserQuestion table has a UNIQUE(user_id, question_id) constraint,
    # and since all guest sessions share the sentinel user_id, inserting the
    # same question across two guest sessions would violate the constraint.
    # Instead, valid question IDs are stored in the token payload and used
    # for validation at submit time.

    await db.commit()
    await db.refresh(test_session)

    # 6. Mint one-time token (includes question IDs for submit validation)
    question_ids = [q.id for q in unseen_questions]
    guest_token = _generate_guest_token(
        session_id=test_session.id,
        device_id=device_id,
        question_ids=question_ids,
    )

    tests_remaining = max(0, settings.GUEST_TEST_LIMIT - device_limit.tests_taken - 1)

    logger.info(
        "Guest test started: session_id=%d device_id=%s questions=%d tests_remaining=%d",
        test_session.id,
        device_id,
        len(unseen_questions),
        tests_remaining,
    )

    questions_response = [
        question_to_response(q, include_explanation=False) for q in unseen_questions
    ]

    return GuestStartTestResponse(
        session=TestSessionResponse.model_validate(test_session),
        questions=questions_response,
        total_questions=len(questions_response),
        guest_token=guest_token,
        tests_remaining=tests_remaining,
    )


@router.post("/submit", response_model=GuestSubmitTestResponse)
async def submit_guest_test(
    submission: GuestSubmitRequest,
    db: AsyncSession = Depends(get_db),
) -> SubmitTestResponse:
    """
    Submit answers for a guest test session.

    The *guest_token* from the start response is consumed here — a second call
    with the same token returns 400.

    Args:
        submission: Guest submit request with guest_token, responses, and
                    optional time_limit_exceeded flag.
        db:         Database session.

    Returns:
        GuestSubmitTestResponse (identical structure to SubmitTestResponse).

    Raises:
        HTTPException 400: Invalid or expired guest token, empty responses,
                          or invalid question IDs.
        HTTPException 404: Session or question not found.
        HTTPException 409: Duplicate response for a question.
    """
    from app.schemas.responses import ResponseSubmission

    # 1. Validate and consume the token (single-use)
    token_payload = _consume_guest_token(submission.guest_token)
    if token_payload is None:
        raise_bad_request(ErrorMessages.GUEST_TOKEN_INVALID)

    session_id: int = token_payload["session_id"]
    device_id: str = token_payload["device_id"]
    token_question_ids: list[int] = token_payload["question_ids"]

    logger.info(
        "Guest test submit: session_id=%d device_id=%s",
        session_id,
        device_id,
    )

    # 2. Fetch and validate the session
    test_session = await get_test_session_or_404(db, session_id)
    verify_session_in_progress(test_session)

    # Confirm session belongs to the sentinel user (defensive check)
    if test_session.user_id != settings.GUEST_USER_ID:
        logger.error(
            "Guest token pointed to non-guest session %d (user_id=%d)",
            session_id,
            test_session.user_id,
        )
        raise_bad_request(ErrorMessages.GUEST_TOKEN_INVALID)

    # 3. Validate responses list is not empty
    if not submission.responses:
        raise_bad_request(ErrorMessages.EMPTY_RESPONSE_LIST)

    # 4. Validate that submitted question IDs belong to this session.
    #    Question IDs are stored in the token payload (not UserQuestion rows,
    #    because the sentinel user's UNIQUE(user_id, question_id) constraint
    #    would conflict across multiple guest sessions).
    valid_question_ids = set(token_question_ids)

    submitted_question_ids = {resp.question_id for resp in submission.responses}
    invalid_questions = submitted_question_ids - valid_question_ids
    if invalid_questions:
        raise_bad_request(ErrorMessages.invalid_question_ids(invalid_questions))

    # 5. Fetch question objects for scoring
    q_result = await db.execute(
        select(Question).where(Question.id.in_(submitted_question_ids))
    )
    questions_dict = {q.id: q for q in q_result.scalars().all()}

    # 6. Build a ResponseSubmission-compatible object so we can pass it to the
    #    shared pipeline helpers unchanged.
    proxy_submission = ResponseSubmission(
        session_id=session_id,
        responses=submission.responses,
        time_limit_exceeded=submission.time_limit_exceeded,
    )

    # 7. Process responses (creates Response rows, updates distractor stats)
    processing_result = await _process_responses(
        db=db,
        submission=proxy_submission,
        test_session=test_session,
        user_id=settings.GUEST_USER_ID,
        questions_dict=questions_dict,
    )
    response_count: int = processing_result["response_count"]
    correct_count: int = processing_result["correct_count"]
    response_objects: list = processing_result["response_objects"]

    # 8. Complete session and calculate IQ score
    (
        completion_time,
        completion_time_seconds,
        domain_scores,
        score_result,
        percentile,
    ) = await _complete_session_and_calculate_score(
        db=db,
        test_session=test_session,
        submission=proxy_submission,
        response_objects=response_objects,
        questions_dict=questions_dict,
        correct_count=correct_count,
        response_count=response_count,
    )

    # 9. Analyze response times (non-critical)
    response_time_flags = await _analyze_response_times(db, test_session.id)

    # 10. Validity analysis (non-critical)
    validity_result = _run_validity_analysis(
        session_id=test_session.id,
        submission=proxy_submission,
        questions_dict=questions_dict,
        correct_count=correct_count,
    )

    # 11. SEM and confidence interval (non-critical)
    sem_result = await _calculate_sem_and_ci(
        db=db,
        session_id=test_session.id,
        iq_score=score_result.iq_score,
    )

    # 12. Create TestResult record
    test_result = TestResult(
        test_session_id=test_session.id,
        user_id=settings.GUEST_USER_ID,
        iq_score=score_result.iq_score,
        percentile_rank=percentile,
        total_questions=score_result.total_questions,
        correct_answers=score_result.correct_answers,
        completion_time_seconds=completion_time_seconds,
        completed_at=completion_time,
        response_time_flags=response_time_flags,
        domain_scores=domain_scores,
        validity_status=validity_result["validity_status"],
        validity_flags=validity_result["validity_flags"],
        validity_checked_at=validity_result["validity_checked_at"],
        standard_error=sem_result["standard_error"],
        ci_lower=sem_result["ci_lower"],
        ci_upper=sem_result["ci_upper"],
    )
    db.add(test_result)

    # 13. Commit all changes (session status, responses, test result)
    try:
        await db.commit()
        await db.refresh(test_session)
        await db.refresh(test_result)
    except IntegrityError as e:
        await db.rollback()
        logger.debug(
            "IntegrityError during guest test submission (session_id=%s): %s",
            session_id,
            type(e).__name__,
        )
        from app.core.error_responses import raise_conflict

        raise_conflict(
            "A response has already been submitted for one or more questions in this session."
        )

    # 14. Increment device test counter — only after a successful commit so that
    #     a submit failure doesn't permanently consume one of the device's tests.
    with graceful_failure(
        f"increment guest device test counter for device {device_id}",
        logger,
    ):
        device_stmt = select(GuestDeviceLimit).where(
            GuestDeviceLimit.device_id == device_id
        )
        device_result = await db.execute(device_stmt)
        device_limit = device_result.scalar_one_or_none()

        if device_limit is not None:
            device_limit.tests_taken += 1
            device_limit.last_test_at = utc_now()
            await db.commit()
        else:
            # Edge case: row was deleted between start and submit.  Re-create it
            # with tests_taken=1 so the limit is tracked going forward.
            logger.warning(
                "GuestDeviceLimit row missing for device_id=%s during submit; recreating.",
                device_id,
            )
            new_limit = GuestDeviceLimit(
                device_id=device_id,
                tests_taken=1,
                first_test_at=utc_now(),
                last_test_at=utc_now(),
            )
            db.add(new_limit)
            await db.commit()

    # 15. Non-critical post-submission pipeline (question stats, distractor quartiles)
    await _run_post_submission_updates(
        db=db,
        session_id=test_session.id,
        correct_count=correct_count,
        response_count=response_count,
    )

    # 16. Trigger shadow CAT comparison (non-critical, daemon thread)
    with graceful_failure(
        f"trigger shadow CAT for guest session {test_session.id}",
        logger,
    ):
        _trigger_shadow_cat(test_session.id)

    # 17. Build and return response
    result_response = await build_test_result_response(test_result, db=db)
    claim_token = _generate_guest_claim_token(
        session_id=test_session.id,
        result_id=test_result.id,
    )

    logger.info(
        "Guest test completed: session_id=%d device_id=%s iq_score=%d",
        test_session.id,
        device_id,
        score_result.iq_score,
    )

    return GuestSubmitTestResponse(
        session=TestSessionResponse.model_validate(test_session),
        result=result_response,
        responses_count=response_count,
        message=f"Test completed! IQ Score: {score_result.iq_score}",
        claim_token=claim_token,
    )


@router.post("/claim", response_model=GuestClaimResponse)
async def claim_guest_result(
    request: GuestClaimRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GuestClaimResponse:
    """
    Attach a completed guest test result to the authenticated user's account.

    The claim token is returned by POST /v1/test/guest/submit. The token must
    point to a completed, still-unclaimed guest session and result.
    """
    token_payload = _get_guest_claim_token(request.claim_token)
    if token_payload is None:
        raise_bad_request(ErrorMessages.GUEST_CLAIM_TOKEN_INVALID)

    session_id: int = token_payload["session_id"]
    result_id: int = token_payload["result_id"]

    session_result = await db.execute(
        select(TestSession).where(TestSession.id == session_id)
    )
    test_session = session_result.scalar_one_or_none()
    if test_session is None:
        raise_bad_request(ErrorMessages.GUEST_CLAIM_TOKEN_INVALID)

    result_result = await db.execute(
        select(TestResult).where(
            TestResult.id == result_id,
            TestResult.test_session_id == session_id,
        )
    )
    test_result = result_result.scalar_one_or_none()
    if test_result is None or test_session.status != TestStatus.COMPLETED:
        raise_bad_request(ErrorMessages.GUEST_CLAIM_TOKEN_INVALID)

    if (
        test_session.user_id != settings.GUEST_USER_ID
        or test_result.user_id != settings.GUEST_USER_ID
    ):
        raise_conflict(ErrorMessages.GUEST_RESULT_ALREADY_CLAIMED)

    session_update = await db.execute(
        update(TestSession)
        .where(
            TestSession.id == session_id,
            TestSession.user_id == settings.GUEST_USER_ID,
        )
        .values(user_id=current_user.id)
    )
    result_update = await db.execute(
        update(TestResult)
        .where(
            TestResult.id == result_id,
            TestResult.user_id == settings.GUEST_USER_ID,
        )
        .values(user_id=current_user.id)
    )
    response_update = await db.execute(
        update(Response)
        .where(
            Response.test_session_id == session_id,
            Response.user_id == settings.GUEST_USER_ID,
        )
        .values(user_id=current_user.id)
    )

    if (
        session_update.rowcount != 1
        or result_update.rowcount != 1
        or response_update.rowcount == 0
    ):
        await db.rollback()
        raise_conflict(ErrorMessages.GUEST_RESULT_ALREADY_CLAIMED)

    response_question_result = await db.execute(
        select(Response.question_id).where(Response.test_session_id == session_id)
    )
    response_question_ids = list(response_question_result.scalars().all())
    existing_seen_result = await db.execute(
        select(UserQuestion.question_id).where(
            UserQuestion.user_id == current_user.id,
            UserQuestion.question_id.in_(response_question_ids),
        )
    )
    existing_seen_ids = set(existing_seen_result.scalars().all())
    db.add_all(
        UserQuestion(
            user_id=current_user.id,
            question_id=question_id,
            test_session_id=session_id,
        )
        for question_id in response_question_ids
        if question_id not in existing_seen_ids
    )
    await db.commit()

    refreshed_session_result = await db.execute(
        select(TestSession).where(
            TestSession.id == session_id,
            TestSession.user_id == current_user.id,
        )
    )
    refreshed_session = refreshed_session_result.scalar_one()
    refreshed_result_result = await db.execute(
        select(TestResult).where(
            TestResult.id == result_id,
            TestResult.user_id == current_user.id,
        )
    )
    refreshed_result = refreshed_result_result.scalar_one()
    response_count_result = await db.execute(
        select(func.count(Response.id)).where(
            Response.test_session_id == session_id,
            Response.user_id == current_user.id,
        )
    )
    responses_count = response_count_result.scalar_one()

    invalidate_user_cache(current_user.id)

    logger.info(
        "Guest result claimed: session_id=%d result_id=%d user_id=%d",
        session_id,
        result_id,
        current_user.id,
    )

    return GuestClaimResponse(
        session=TestSessionResponse.model_validate(refreshed_session),
        result=await build_test_result_response(refreshed_result, db=db),
        responses_count=responses_count,
        message="Guest result claimed successfully.",
    )
