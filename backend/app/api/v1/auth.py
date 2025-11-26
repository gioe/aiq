"""
Authentication endpoints for user registration and login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models import get_db, User
from app.schemas.auth import UserRegister, UserLogin, Token, TokenRefresh
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.auth import get_current_user, get_current_user_from_refresh_token
from app.core.analytics import AnalyticsTracker

router = APIRouter()


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        Created user information with access and refresh tokens

    Raises:
        HTTPException: 409 if email already exists
    """
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        # Optional demographic data for norming study (P13-001)
        birth_year=user_data.birth_year,
        education_level=user_data.education_level,
        country=user_data.country,
        region=user_data.region,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Track analytics event
    AnalyticsTracker.track_user_registered(
        user_id=int(new_user.id),  # type: ignore
        email=new_user.email,  # type: ignore
    )

    # Create tokens for immediate login after registration
    token_data = {"user_id": new_user.id, "email": new_user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"user_id": new_user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": new_user,
    }


@router.post("/login", response_model=Token)
def login_user(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return access + refresh tokens.

    Args:
        credentials: User login credentials
        db: Database session

    Returns:
        Access and refresh JWT tokens with user information

    Raises:
        HTTPException: 401 if credentials are invalid
    """
    # Find user by email
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(credentials.password, user.password_hash):  # type: ignore
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)  # type: ignore
    db.commit()
    db.refresh(user)

    # Track analytics event
    AnalyticsTracker.track_user_login(
        user_id=int(user.id),  # type: ignore
        email=user.email,  # type: ignore
    )

    # Create tokens
    token_data = {"user_id": user.id, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user,
    }


@router.post("/refresh", response_model=TokenRefresh)
def refresh_access_token(
    current_user: User = Depends(get_current_user_from_refresh_token),
    db: Session = Depends(get_db),
):
    """
    Refresh access token using refresh token.

    Args:
        current_user: Current authenticated user from refresh token
        db: Database session

    Returns:
        New access and refresh tokens with user information

    Raises:
        HTTPException: 401 if refresh token is invalid
    """
    # Track analytics event
    from app.core.analytics import EventType

    AnalyticsTracker.track_event(
        EventType.TOKEN_REFRESHED,
        user_id=int(current_user.id),  # type: ignore
    )

    # Refresh user data from database to ensure it's current
    db.refresh(current_user)

    # Create new tokens
    token_data = {"user_id": current_user.id, "email": current_user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"user_id": current_user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": current_user,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout_user(current_user: User = Depends(get_current_user)):
    """
    Logout user (client-side token invalidation).

    Note: Since we're using stateless JWT tokens, actual logout happens
    on the client side by discarding the tokens. This endpoint validates
    that the user is authenticated and allows the client to confirm logout.

    Args:
        current_user: Current authenticated user

    Returns:
        No content (204)
    """
    # Track analytics event
    from app.core.analytics import EventType

    AnalyticsTracker.track_event(
        EventType.USER_LOGOUT,
        user_id=int(current_user.id),  # type: ignore
    )

    # For JWT, logout is handled client-side by discarding tokens
    # This endpoint just validates the token is valid
    return None
