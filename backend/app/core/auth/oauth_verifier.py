"""Verify OIDC identity tokens from Apple and Google.

Both providers sign their identity tokens with RS256 and publish their
public keys via a JWKS endpoint. This module fetches and caches those
keys, verifies the token signature and standard claims (iss, aud, exp),
and returns the subject + email so the auth endpoints can resolve or
create the matching AIQ user.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import time
from dataclasses import dataclass
from typing import Iterable, Optional

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)


APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_ISSUER = "https://appleid.apple.com"

GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("https://accounts.google.com", "accounts.google.com")

# Pinned signing algorithms. Apple and Google both publish RS256 keys; we
# refuse to evaluate anything else so a crafted header (e.g. alg=HS256 or
# alg=none) cannot downgrade verification to a secret the attacker knows.
ALLOWED_SIGNING_ALGORITHMS = ("RS256",)


class OAuthVerificationError(Exception):
    """Raised when an identity token cannot be verified.

    Carries a short ``reason`` code suitable for structured logging — the
    user-facing response is always a generic 401 so we don't leak which
    specific check failed.
    """

    def __init__(self, reason: str, detail: str = ""):
        """Store the short reason code and a human-readable detail string."""
        super().__init__(detail or reason)
        self.reason = reason


@dataclass(frozen=True)
class OAuthUserInfo:
    """Verified subset of an OIDC identity token.

    ``email_verified`` reflects the *provider's* own claim after
    normalization (Apple sometimes sends the string "true"/"false"); a
    False value means the provider has not itself validated the address.
    """

    provider: str
    subject: str
    email: Optional[str]
    email_verified: bool


class _JWKSCache:
    """Tiny TTL cache for provider JWKS documents.

    A single instance is shared across the process; refreshes happen lazily
    on the request path after the TTL expires. A hard refresh is triggered
    on any token whose `kid` isn't in the cached set, so key rotation is
    picked up without waiting for the TTL. A per-URL lock collapses a
    cache-miss stampede into a single outbound fetch.
    """

    def __init__(self) -> None:
        """Initialize with an empty per-URL cache."""
        self._entries: dict[str, tuple[float, dict]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, url: str) -> asyncio.Lock:
        lock = self._locks.get(url)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[url] = lock
        return lock

    async def get(self, url: str, *, force: bool = False) -> dict:
        ttl = settings.OAUTH_JWKS_CACHE_TTL_SECONDS
        now = time.monotonic()
        cached = self._entries.get(url)
        if cached and not force and (now - cached[0]) < ttl:
            return cached[1]

        async with self._lock_for(url):
            # Re-check under lock: another coroutine may have just refreshed.
            cached = self._entries.get(url)
            now = time.monotonic()
            if cached and not force and (now - cached[0]) < ttl:
                return cached[1]
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                response.raise_for_status()
                jwks = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                if cached:
                    logger.warning(
                        "JWKS fetch failed for %s (%s); serving cached copy",
                        url,
                        exc,
                    )
                    return cached[1]
                raise OAuthVerificationError(
                    "jwks_unavailable", f"Unable to fetch JWKS from {url}: {exc}"
                ) from exc
            self._entries[url] = (now, jwks)
            return jwks


_jwks_cache = _JWKSCache()


def _select_key(jwks: dict, kid: str) -> Optional[dict]:
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return None


def _accepted_audiences(raw: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in raw.split(",") if item.strip())


async def _verify_oidc_token(
    token: str,
    *,
    provider: str,
    jwks_url: str,
    issuers: Iterable[str],
    audiences: tuple[str, ...],
    expected_nonce_hash: Optional[str] = None,
) -> OAuthUserInfo:
    if not audiences:
        raise OAuthVerificationError(
            "provider_disabled", f"{provider} sign-in is not configured"
        )

    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise OAuthVerificationError("malformed_token", str(exc)) from exc

    # Refuse any algorithm outside our pinned list before looking up keys —
    # the JWT "alg" header is attacker-controlled (algorithm-confusion attack).
    header_alg = unverified_header.get("alg")
    if header_alg not in ALLOWED_SIGNING_ALGORITHMS:
        raise OAuthVerificationError(
            "unsupported_alg", f"alg={header_alg!r} not accepted"
        )

    kid = unverified_header.get("kid")
    if not kid:
        raise OAuthVerificationError("missing_kid", "Identity token missing kid header")

    jwks = await _jwks_cache.get(jwks_url)
    key = _select_key(jwks, kid)
    if key is None:
        # Force-refresh the JWKS once — keys rotate without notice.
        jwks = await _jwks_cache.get(jwks_url, force=True)
        key = _select_key(jwks, kid)
    if key is None:
        raise OAuthVerificationError("unknown_kid", f"kid={kid} not in JWKS")

    issuer_list = list(issuers)
    last_error: Optional[Exception] = None
    for audience in audiences:
        for issuer in issuer_list:
            try:
                payload = jwt.decode(
                    token,
                    key,
                    algorithms=list(ALLOWED_SIGNING_ALGORITHMS),
                    audience=audience,
                    issuer=issuer,
                )
                break
            except ExpiredSignatureError as exc:
                raise OAuthVerificationError("token_expired", str(exc)) from exc
            except JWTError as exc:
                last_error = exc
                continue
        else:
            continue
        break
    else:
        raise OAuthVerificationError(
            "invalid_claims", str(last_error) if last_error else "claims rejected"
        )

    subject = payload.get("sub")
    if not subject:
        raise OAuthVerificationError("missing_subject", "Identity token missing sub")

    if expected_nonce_hash is not None:
        token_nonce = payload.get("nonce")
        if not token_nonce:
            raise OAuthVerificationError(
                "missing_nonce", "Identity token missing nonce"
            )
        if not hmac.compare_digest(str(token_nonce), expected_nonce_hash):
            raise OAuthVerificationError(
                "nonce_mismatch", "Identity token nonce mismatch"
            )

    email = payload.get("email")
    # Apple sends email_verified as either a bool or the string "true"/"false".
    raw_verified = payload.get("email_verified")
    email_verified = raw_verified is True or raw_verified == "true"

    return OAuthUserInfo(
        provider=provider,
        subject=str(subject),
        email=str(email) if email else None,
        email_verified=email_verified,
    )


async def verify_apple_identity_token(token: str, *, nonce: str) -> OAuthUserInfo:
    audiences = _accepted_audiences(settings.APPLE_OAUTH_CLIENT_IDS)
    nonce_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
    return await _verify_oidc_token(
        token,
        provider="apple",
        jwks_url=APPLE_JWKS_URL,
        issuers=(APPLE_ISSUER,),
        audiences=audiences,
        expected_nonce_hash=nonce_hash,
    )


async def verify_google_identity_token(token: str) -> OAuthUserInfo:
    audiences = _accepted_audiences(settings.GOOGLE_OAUTH_CLIENT_IDS)
    return await _verify_oidc_token(
        token,
        provider="google",
        jwks_url=GOOGLE_JWKS_URL,
        issuers=GOOGLE_ISSUERS,
        audiences=audiences,
    )
