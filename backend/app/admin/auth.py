"""
Admin authentication for the dashboard.
"""
import logging
import secrets

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.config import settings
from app.core.security import verify_password

logger = logging.getLogger(__name__)


class AdminAuth(AuthenticationBackend):
    """
    Basic HTTP authentication for admin dashboard.

    Uses username and password from environment variables.
    Sessions are stored in secure cookies.
    """

    async def login(self, request: Request) -> bool:
        """
        Authenticate admin user with username and password.

        Password is verified against a bcrypt hash stored in ADMIN_PASSWORD_HASH.

        Args:
            request: Starlette request object with form data

        Returns:
            bool: True if authentication successful
        """
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        # Early return if credentials are missing, non-string, or username doesn't match
        # Note: Generic error messages prevent username enumeration attacks
        if (
            not username
            or not password
            or not isinstance(username, str)
            or not isinstance(password, str)
            or username != settings.ADMIN_USERNAME
        ):
            logger.warning("Admin login failed: invalid credentials")
            return False

        # Verify password hash is configured (startup validation should catch this,
        # but check here for defense-in-depth)
        if not settings.ADMIN_PASSWORD_HASH:
            logger.error("Admin login failed: ADMIN_PASSWORD_HASH not configured")
            return False

        # Verify password against bcrypt hash
        if verify_password(password, settings.ADMIN_PASSWORD_HASH):
            logger.info("Admin login successful")
            # Generate secure session token
            token = secrets.token_urlsafe(32)
            request.session.update({"token": token})
            return True

        logger.warning("Admin login failed: invalid credentials")
        return False

    async def logout(self, request: Request) -> bool:
        """
        Logout admin user by clearing session.

        Args:
            request: Starlette request object

        Returns:
            bool: Always returns True
        """
        request.session.clear()
        return True

    async def authenticate(self, request: Request) -> bool:
        """
        Check if user is authenticated via session token.

        Args:
            request: Starlette request object

        Returns:
            bool: True if authenticated, False otherwise (which triggers redirect to login)
        """
        token = request.session.get("token")
        return bool(token)
