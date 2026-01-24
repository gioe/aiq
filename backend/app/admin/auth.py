"""
Admin authentication for the dashboard.
"""
import secrets

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.config import settings
from app.core.security import verify_password


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

        # Early return if credentials are missing or username doesn't match
        if not username or not password or username != settings.ADMIN_USERNAME:
            return False

        # Verify password hash is configured
        if not settings.ADMIN_PASSWORD_HASH:
            return False

        # Verify password against bcrypt hash
        if verify_password(str(password), settings.ADMIN_PASSWORD_HASH):
            # Generate secure session token
            token = secrets.token_urlsafe(32)
            request.session.update({"token": token})
            return True

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
