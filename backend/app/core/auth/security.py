"""
Security utilities for password hashing and JWT token management.
"""
from datetime import timedelta
import uuid

from app.core.datetime_utils import utc_now
from typing import Optional, Dict, Any
import bcrypt
from jose import JWTError, jwt
from app.core.config import settings


def hash_password(password: str) -> str:
    """
    Hash a plain text password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Hashed password string
    """
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain text password against a hashed password.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def _create_token(
    data: Dict[str, Any],
    token_type: str,
    expires_delta: Optional[timedelta],
    default_expires: timedelta,
) -> str:
    """
    Internal helper to create a JWT token.

    Args:
        data: Dictionary of data to encode in the token
        token_type: Type of token ("access" or "refresh")
        expires_delta: Optional custom expiration time delta
        default_expires: Default expiration delta if expires_delta is None

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    now = utc_now()
    expire = now + (expires_delta or default_expires)
    # Add JTI (JWT ID) for token blacklist support
    jti = str(uuid.uuid4())
    # Add iat (issued-at) for user-level revocation epoch checking
    to_encode.update({"exp": expire, "iat": now, "type": token_type, "jti": jti})
    return jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )


def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Dictionary of data to encode in the token (typically user_id, email)
        expires_delta: Optional custom expiration time delta

    Returns:
        Encoded JWT token string
    """
    return _create_token(
        data=data,
        token_type="access",
        expires_delta=expires_delta,
        default_expires=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    """
    Create a JWT refresh token.

    Args:
        data: Dictionary of data to encode in the token (typically user_id)
        expires_delta: Optional custom expiration time delta

    Returns:
        Encoded JWT refresh token string
    """
    return _create_token(
        data=data,
        token_type="refresh",
        expires_delta=expires_delta,
        default_expires=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Decode and verify a JWT token.

    Args:
        token: JWT token string to decode

    Returns:
        Decoded token payload if valid, None if invalid
    """
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def verify_token_type(payload: Dict[str, Any], expected_type: str) -> bool:
    """
    Verify that a token payload has the expected type.

    Args:
        payload: Decoded token payload
        expected_type: Expected token type ("access" or "refresh")

    Returns:
        True if token type matches expected type, False otherwise
    """
    token_type = payload.get("type")
    return token_type == expected_type
