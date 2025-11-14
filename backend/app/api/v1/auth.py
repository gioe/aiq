"""
Authentication endpoints for user registration and login.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.models import get_db, User
from app.schemas.auth import UserRegister, UserLogin, Token, TokenRefresh, UserResponse
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.core.auth import get_current_user, get_current_user_from_refresh_token

router = APIRouter()


@router.post(
    "/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
def register_user(user_data: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account.

    Args:
        user_data: User registration data
        db: Database session

    Returns:
        Created user information

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
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@router.post("/login", response_model=Token)
def login_user(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate user and return access + refresh tokens.

    Args:
        credentials: User login credentials
        db: Database session

    Returns:
        Access and refresh JWT tokens

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

    # Create tokens
    token_data = {"user_id": user.id, "email": user.email}
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token({"user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=TokenRefresh)
def refresh_access_token(
    current_user: User = Depends(get_current_user_from_refresh_token),
):
    """
    Refresh access token using refresh token.

    Args:
        current_user: Current authenticated user from refresh token

    Returns:
        New access token

    Raises:
        HTTPException: 401 if refresh token is invalid
    """
    # Create new access token
    token_data = {"user_id": current_user.id, "email": current_user.email}
    access_token = create_access_token(token_data)

    return {
        "access_token": access_token,
        "token_type": "bearer",
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
    # For JWT, logout is handled client-side by discarding tokens
    # This endpoint just validates the token is valid
    return None
