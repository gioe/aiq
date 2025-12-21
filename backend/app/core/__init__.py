"""
Core module for application configuration and utilities.

Note: auth and security modules are not imported at package level to avoid
circular imports with app.models (which imports datetime_utils from app.core).
Import them directly: from app.core.auth import ... or from app.core.security import ...
"""
from .config import settings

__all__ = ["settings"]
