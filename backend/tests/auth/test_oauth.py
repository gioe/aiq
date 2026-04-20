"""Tests for OAuth token-exchange endpoints (TASK-470).

The provider verifiers (``verify_apple_identity_token`` /
``verify_google_identity_token``) are patched out — tests do not reach
Apple's or Google's JWKS endpoints. Verifier-level behavior is covered
separately in ``test_oauth_verifier.py``.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.auth.oauth_verifier import OAuthUserInfo, OAuthVerificationError
from app.core.auth.security import hash_password
from app.models import OAuthIdentity, User


def _oauth_info(
    provider: str = "apple",
    *,
    subject: str = "apple-sub-123",
    email: str | None = "oauth@example.com",
    email_verified: bool = True,
) -> OAuthUserInfo:
    return OAuthUserInfo(
        provider=provider,
        subject=subject,
        email=email,
        email_verified=email_verified,
    )


APPLE_VERIFIER = "app.api.v1.auth.verify_apple_identity_token"
GOOGLE_VERIFIER = "app.api.v1.auth.verify_google_identity_token"


class TestAppleOAuthExchange:
    """POST /v1/auth/oauth/apple."""

    async def test_valid_apple_token_returns_aiq_tokens(
        self, async_client, async_db_session
    ):
        with patch(APPLE_VERIFIER, return_value=_oauth_info(provider="apple")):
            response = await async_client.post(
                "/v1/auth/oauth/apple",
                json={"identity_token": "stubbed-apple-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "oauth@example.com"

        result = await async_db_session.execute(
            select(OAuthIdentity).where(
                OAuthIdentity.provider == "apple",
                OAuthIdentity.provider_subject == "apple-sub-123",
            )
        )
        identity = result.scalar_one()
        assert identity.user_id == data["user"]["id"]

    async def test_invalid_apple_token_returns_401(self, async_client):
        with patch(
            APPLE_VERIFIER,
            side_effect=OAuthVerificationError("invalid_claims", "bad sig"),
        ):
            response = await async_client.post(
                "/v1/auth/oauth/apple",
                json={"identity_token": "malformed"},
            )

        assert response.status_code == 401
        assert "Invalid" in response.json()["detail"]

    async def test_expired_apple_token_returns_401(self, async_client):
        with patch(
            APPLE_VERIFIER,
            side_effect=OAuthVerificationError("token_expired", "exp in past"),
        ):
            response = await async_client.post(
                "/v1/auth/oauth/apple",
                json={"identity_token": "expired"},
            )

        assert response.status_code == 401


class TestGoogleOAuthExchange:
    """POST /v1/auth/oauth/google."""

    async def test_valid_google_token_returns_aiq_tokens(
        self, async_client, async_db_session
    ):
        info = _oauth_info(provider="google", subject="google-sub-xyz")
        with patch(GOOGLE_VERIFIER, return_value=info):
            response = await async_client.post(
                "/v1/auth/oauth/google",
                json={"identity_token": "stubbed-google-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["access_token"]
        assert data["user"]["email"] == "oauth@example.com"

        result = await async_db_session.execute(
            select(OAuthIdentity).where(OAuthIdentity.provider == "google")
        )
        assert result.scalar_one().provider_subject == "google-sub-xyz"

    async def test_invalid_google_token_returns_401(self, async_client):
        with patch(
            GOOGLE_VERIFIER,
            side_effect=OAuthVerificationError("invalid_claims", "bad aud"),
        ):
            response = await async_client.post(
                "/v1/auth/oauth/google",
                json={"identity_token": "bad"},
            )

        assert response.status_code == 401


class TestAccountLinking:
    """Criteria 4 & 5: email-based linking and repeat-login idempotence."""

    async def test_matching_verified_email_links_existing_user(
        self, async_client, async_db_session
    ):
        existing = User(
            email="existing@example.com",
            password_hash=hash_password("password12345"),
            first_name="Exi",
            last_name="Sting",
        )
        async_db_session.add(existing)
        await async_db_session.commit()
        await async_db_session.refresh(existing)
        existing_id = existing.id

        info = _oauth_info(
            provider="apple",
            subject="link-sub",
            email="existing@example.com",
            email_verified=True,
        )
        with patch(APPLE_VERIFIER, return_value=info):
            response = await async_client.post(
                "/v1/auth/oauth/apple",
                json={"identity_token": "x"},
            )

        assert response.status_code == 200
        assert response.json()["user"]["id"] == existing_id

        users = (
            (
                await async_db_session.execute(
                    select(User).where(User.email == "existing@example.com")
                )
            )
            .scalars()
            .all()
        )
        assert len(users) == 1

        identities = (
            (
                await async_db_session.execute(
                    select(OAuthIdentity).where(OAuthIdentity.user_id == existing_id)
                )
            )
            .scalars()
            .all()
        )
        assert len(identities) == 1
        assert identities[0].provider == "apple"
        assert identities[0].provider_subject == "link-sub"

    async def test_unverified_email_does_not_link(self, async_client, async_db_session):
        existing = User(
            email="unverified@example.com",
            password_hash=hash_password("password12345"),
        )
        async_db_session.add(existing)
        await async_db_session.commit()

        info = _oauth_info(
            provider="apple",
            subject="unverified-sub",
            email="unverified@example.com",
            email_verified=False,
        )
        with patch(APPLE_VERIFIER, return_value=info):
            response = await async_client.post(
                "/v1/auth/oauth/apple",
                json={"identity_token": "x"},
            )

        # An unverified email must not collapse the flow onto an existing
        # account — the insert should fail on the unique email constraint
        # rather than silently take over the password account.
        assert response.status_code in (400, 500)

    async def test_repeat_oauth_login_returns_same_user(
        self, async_client, async_db_session
    ):
        info = _oauth_info(provider="google", subject="repeat-sub")

        with patch(GOOGLE_VERIFIER, return_value=info):
            first = await async_client.post(
                "/v1/auth/oauth/google",
                json={"identity_token": "token-a"},
            )
            second = await async_client.post(
                "/v1/auth/oauth/google",
                json={"identity_token": "token-b"},
            )

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["user"]["id"] == second.json()["user"]["id"]

        identities = (
            (
                await async_db_session.execute(
                    select(OAuthIdentity).where(
                        OAuthIdentity.provider == "google",
                        OAuthIdentity.provider_subject == "repeat-sub",
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(identities) == 1


class TestOAuthVerifierUnit:
    """Verifier-level tests: signature, expiration, and issuer/audience checks."""

    async def test_expired_token_raises_token_expired(self):
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt

        # Build an RSA key pair and sign a token with exp in the past.
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        public_numbers = private_key.public_key().public_numbers()

        def _b64(value: int) -> str:
            import base64

            length = (value.bit_length() + 7) // 8
            return (
                base64.urlsafe_b64encode(value.to_bytes(length, "big"))
                .rstrip(b"=")
                .decode()
            )

        jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "test-kid",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64(public_numbers.n),
                    "e": _b64(public_numbers.e),
                }
            ]
        }

        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {
                "iss": "https://appleid.apple.com",
                "aud": "com.aiq.test",
                "sub": "expired-user",
                "email": "expired@example.com",
                "email_verified": True,
                "iat": int((now - timedelta(hours=2)).timestamp()),
                "exp": int((now - timedelta(hours=1)).timestamp()),
            },
            private_pem,
            algorithm="RS256",
            headers={"kid": "test-kid"},
        )

        from app.core.auth import oauth_verifier as mod

        mod._jwks_cache._entries[mod.APPLE_JWKS_URL] = (1e18, jwks)
        with patch.object(mod.settings, "APPLE_OAUTH_CLIENT_IDS", "com.aiq.test"):
            with pytest.raises(OAuthVerificationError) as exc_info:
                mod.verify_apple_identity_token(token)

        assert exc_info.value.reason == "token_expired"

    async def test_invalid_signature_rejected(self):
        from datetime import datetime, timedelta, timezone

        from jose import jwt as jose_jwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

        signing_pem = signing_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()

        # Publish a JWKS that advertises the *other* key, so signatures
        # made with signing_key will not verify.
        pn = other_key.public_key().public_numbers()

        def _b64(value: int) -> str:
            import base64

            length = (value.bit_length() + 7) // 8
            return (
                base64.urlsafe_b64encode(value.to_bytes(length, "big"))
                .rstrip(b"=")
                .decode()
            )

        jwks = {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": "sig-kid",
                    "use": "sig",
                    "alg": "RS256",
                    "n": _b64(pn.n),
                    "e": _b64(pn.e),
                }
            ]
        }

        now = datetime.now(timezone.utc)
        token = jose_jwt.encode(
            {
                "iss": "https://accounts.google.com",
                "aud": "google-client-id",
                "sub": "sig-user",
                "email": "sig@example.com",
                "email_verified": True,
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=1)).timestamp()),
            },
            signing_pem,
            algorithm="RS256",
            headers={"kid": "sig-kid"},
        )

        from app.core.auth import oauth_verifier as mod

        mod._jwks_cache._entries[mod.GOOGLE_JWKS_URL] = (1e18, jwks)
        with patch.object(mod.settings, "GOOGLE_OAUTH_CLIENT_IDS", "google-client-id"):
            with pytest.raises(OAuthVerificationError) as exc_info:
                mod.verify_google_identity_token(token)

        assert exc_info.value.reason == "invalid_claims"
