"""Secrets management abstraction layer for question-service.

Provides a unified interface for retrieving secrets from different backends:
- Environment variables (default)
- Doppler (placeholder for future implementation)

This module ensures secrets are loaded securely and consistently, with proper
error handling and validation. It supports Railway's sealed variables and can be
extended to support Doppler SDK integration.
"""

import logging
import os
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class SecretsBackend(str, Enum):
    """Available secrets management backends."""

    ENV = "env"  # Environment variables (default)
    DOPPLER = "doppler"  # Doppler secrets management (future)


class SecretsError(Exception):
    """Base exception for secrets management errors."""

    def __init__(
        self,
        message: str,
        secret_name: Optional[str] = None,
        backend: Optional[str] = None,
    ):
        """Initialize SecretsError with context.

        Args:
            message: Human-readable error description
            secret_name: Name of the secret that caused the error
            backend: Backend being used when error occurred
        """
        self.message = message
        self.secret_name = secret_name
        self.backend = backend
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with context."""
        parts = [self.message]
        if self.secret_name:
            parts.append(f"(secret: {self.secret_name})")
        if self.backend:
            parts.append(f"(backend: {self.backend})")
        return " ".join(parts)


class SecretsManager:
    """Manages secret retrieval from configured backend.

    This class provides a unified interface for accessing secrets regardless of
    the underlying storage mechanism. It supports:
    - Environment variables (default, works with Railway sealed variables)
    - Doppler SDK (placeholder for future implementation)

    Usage:
        manager = SecretsManager(backend=SecretsBackend.ENV)
        api_key = manager.get_secret("openai_api_key")
    """

    def __init__(self, backend: Optional[SecretsBackend] = None):
        """Initialize SecretsManager with specified backend.

        Args:
            backend: Secrets backend to use. If None, reads from
                    SECRETS_BACKEND environment variable or defaults to ENV.

        Raises:
            SecretsError: If backend is invalid or initialization fails
        """
        if backend is None:
            backend_str = os.environ.get("SECRETS_BACKEND", "env").lower()
            try:
                backend = SecretsBackend(backend_str)
            except ValueError as e:
                raise SecretsError(
                    f"Invalid SECRETS_BACKEND value: {backend_str}. "
                    f"Must be one of: {', '.join(b.value for b in SecretsBackend)}",
                    backend=backend_str,
                ) from e

        self.backend = backend
        logger.info(f"Initialized SecretsManager with backend: {self.backend.value}")

        # Initialize backend-specific clients
        if self.backend == SecretsBackend.DOPPLER:
            self._initialize_doppler()

    def _initialize_doppler(self) -> None:
        """Initialize Doppler SDK client.

        Raises:
            SecretsError: If Doppler initialization fails
        """
        # Placeholder for future Doppler SDK integration
        # This would initialize the Doppler client using DOPPLER_TOKEN env var
        raise SecretsError(
            "Doppler backend is not yet implemented. Use SECRETS_BACKEND=env",
            backend=self.backend.value,
        )

    def get_secret(self, name: str) -> Optional[str]:
        """Retrieve a secret by name from the configured backend.

        Args:
            name: Secret name (e.g., "openai_api_key", "database_url")

        Returns:
            Secret value as string, or None if not found

        Raises:
            SecretsError: If backend access fails or encounters an error
        """
        try:
            if self.backend == SecretsBackend.ENV:
                return self._get_from_env(name)
            elif self.backend == SecretsBackend.DOPPLER:
                return self._get_from_doppler(name)
            else:
                # This should never happen due to enum validation, but defend against it
                raise SecretsError(
                    f"Unsupported backend: {self.backend}",
                    secret_name=name,
                    backend=self.backend.value,
                )
        except SecretsError:
            # Re-raise SecretsError as-is
            raise
        except Exception as e:
            # Wrap unexpected errors
            logger.exception(f"Unexpected error retrieving secret '{name}'")
            raise SecretsError(
                f"Failed to retrieve secret: {str(e)}",
                secret_name=name,
                backend=self.backend.value,
            ) from e

    def _get_from_env(self, name: str) -> Optional[str]:
        """Retrieve secret from environment variable.

        Args:
            name: Environment variable name

        Returns:
            Variable value or None if not set
        """
        # Convert to uppercase for environment variable lookup
        env_name = name.upper()
        value = os.environ.get(env_name)

        if value is None:
            logger.debug(f"Secret '{name}' not found in environment")
        else:
            # Log that we found it without revealing the value
            logger.debug(f"Retrieved secret '{name}' from environment")

        return value

    def _get_from_doppler(self, name: str) -> Optional[str]:
        """Retrieve secret from Doppler.

        Args:
            name: Secret name in Doppler

        Returns:
            Secret value or None if not found

        Raises:
            SecretsError: If Doppler access fails
        """
        # Placeholder for future Doppler SDK integration
        raise SecretsError(
            "Doppler backend is not yet implemented",
            secret_name=name,
            backend=self.backend.value,
        )

    def validate_required_secrets(self, required_secrets: list[str]) -> None:
        """Validate that all required secrets are present.

        Args:
            required_secrets: List of secret names that must be present

        Raises:
            SecretsError: If any required secret is missing
        """
        missing = []
        for secret_name in required_secrets:
            value = self.get_secret(secret_name)
            if value is None or value.strip() == "":
                missing.append(secret_name)

        if missing:
            raise SecretsError(
                f"Missing required secrets: {', '.join(missing)}. "
                "Please configure these secrets in your environment.",
                backend=self.backend.value,
            )

        logger.info(f"Validated {len(required_secrets)} required secrets")


# Global secrets manager instance
# This is initialized lazily on first access to support different backends
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    """Get or create the global SecretsManager instance.

    Returns:
        Global SecretsManager instance

    Raises:
        SecretsError: If manager initialization fails
    """
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager


def get_secret(name: str) -> Optional[str]:
    """Convenience function to retrieve a secret.

    This is the primary function applications should use for retrieving secrets.

    Args:
        name: Secret name

    Returns:
        Secret value or None if not found

    Raises:
        SecretsError: If secret retrieval fails
    """
    manager = get_secrets_manager()
    return manager.get_secret(name)


def validate_required_secrets(required_secrets: list[str]) -> None:
    """Convenience function to validate required secrets.

    Args:
        required_secrets: List of secret names that must be present

    Raises:
        SecretsError: If any required secret is missing
    """
    manager = get_secrets_manager()
    manager.validate_required_secrets(required_secrets)
