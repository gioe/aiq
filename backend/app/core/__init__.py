"""
Core module for application configuration and utilities.

Note: No modules are imported at package level to avoid circular imports
and premature settings validation. Import modules directly:
  - from app.core.config import settings
  - from app.core.auth.dependencies import get_current_user
  - from app.core.auth.security import create_access_token
  - from app.core.datetime_utils import utc_now
"""

__all__: list[str] = []
