"""
Admin authentication for the dashboard.
"""
import secrets

from sqladmin.authentication import AuthenticationBackend
from starlette.requests import Request

from app.core.config import settings


class AdminAuth(AuthenticationBackend):
    """
    Basic HTTP authentication for admin dashboard.

    Uses username and password from environment variables.
    Sessions are stored in secure cookies.
    """

    async def login(self, request: Request) -> bool:
        """
        Authenticate admin user with username and password.

        Args:
            request: Starlette request object with form data

        Returns:
            bool: True if authentication successful
        """
        form = await request.form()
        username = form.get("username")
        password = form.get("password")

        # Validate credentials against environment variables
        if username == settings.ADMIN_USERNAME and password == settings.ADMIN_PASSWORD:
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
