"""Tests for secrets management module."""

import os
from unittest.mock import patch

import pytest

from app.config.secrets import (
    SecretsBackend,
    SecretsError,
    SecretsManager,
    get_secret,
    get_secrets_manager,
    reset_secrets_manager,
    validate_required_secrets,
)


class TestSecretsBackend:
    """Tests for SecretsBackend enum."""

    def test_backend_values(self):
        """Test that all expected backends are defined."""
        assert SecretsBackend.ENV.value == "env"
        assert SecretsBackend.DOPPLER.value == "doppler"

    def test_backend_string_conversion(self):
        """Test backend enum can be created from string."""
        assert SecretsBackend("env") == SecretsBackend.ENV
        assert SecretsBackend("doppler") == SecretsBackend.DOPPLER

    def test_invalid_backend_raises_error(self):
        """Test that invalid backend string raises ValueError."""
        with pytest.raises(ValueError):
            SecretsBackend("invalid")


class TestSecretsError:
    """Tests for SecretsError exception."""

    def test_error_with_message_only(self):
        """Test error with just message."""
        error = SecretsError("Test error")
        assert "Test error" in str(error)
        assert error.message == "Test error"
        assert error.secret_name is None
        assert error.backend is None

    def test_error_with_secret_name(self):
        """Test error includes secret name in message."""
        error = SecretsError("Test error", secret_name="openai_api_key")
        error_str = str(error)
        assert "Test error" in error_str
        assert "openai_api_key" in error_str
        assert error.secret_name == "openai_api_key"

    def test_error_with_backend(self):
        """Test error includes backend in message."""
        error = SecretsError("Test error", backend="env")
        error_str = str(error)
        assert "Test error" in error_str
        assert "backend: env" in error_str
        assert error.backend == "env"

    def test_error_with_all_context(self):
        """Test error with all context information."""
        error = SecretsError("Test error", secret_name="api_key", backend="doppler")
        error_str = str(error)
        assert "Test error" in error_str
        assert "api_key" in error_str
        assert "doppler" in error_str


class TestSecretsManagerInitialization:
    """Tests for SecretsManager initialization."""

    def test_init_with_env_backend(self):
        """Test initialization with ENV backend."""
        manager = SecretsManager(backend=SecretsBackend.ENV)
        assert manager.backend == SecretsBackend.ENV

    def test_init_with_doppler_backend_raises_error(self):
        """Test that Doppler backend raises not implemented error."""
        with pytest.raises(SecretsError) as exc_info:
            SecretsManager(backend=SecretsBackend.DOPPLER)
        assert "not yet implemented" in str(exc_info.value)

    def test_init_from_env_variable_default(self):
        """Test initialization reads backend from environment (default)."""
        with patch.dict(os.environ, {}, clear=False):
            # Remove SECRETS_BACKEND if set
            os.environ.pop("SECRETS_BACKEND", None)
            manager = SecretsManager()
            assert manager.backend == SecretsBackend.ENV

    def test_init_from_env_variable_explicit(self):
        """Test initialization reads backend from SECRETS_BACKEND env var."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "env"}, clear=False):
            manager = SecretsManager()
            assert manager.backend == SecretsBackend.ENV

    def test_init_from_env_variable_case_insensitive(self):
        """Test backend selection is case-insensitive."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "ENV"}, clear=False):
            manager = SecretsManager()
            assert manager.backend == SecretsBackend.ENV

    def test_init_with_invalid_env_variable(self):
        """Test invalid SECRETS_BACKEND raises error."""
        with patch.dict(os.environ, {"SECRETS_BACKEND": "invalid"}, clear=False):
            with pytest.raises(SecretsError) as exc_info:
                SecretsManager()
            assert "Invalid SECRETS_BACKEND" in str(exc_info.value)
            assert "invalid" in str(exc_info.value)


class TestSecretsManagerEnvBackend:
    """Tests for SecretsManager with ENV backend."""

    def test_get_secret_from_env(self):
        """Test retrieving existing secret from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-123"}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            value = manager.get_secret("openai_api_key")
            assert value == "sk-test-123"

    def test_get_secret_case_insensitive(self):
        """Test secret name lookup is case-insensitive."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-123"}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            # Test lowercase input
            assert manager.get_secret("openai_api_key") == "sk-test-123"
            # Test uppercase input
            assert manager.get_secret("OPENAI_API_KEY") == "sk-test-123"

    def test_get_secret_not_found_returns_none(self):
        """Test that missing secret returns None."""
        manager = SecretsManager(backend=SecretsBackend.ENV)
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NONEXISTENT_KEY", None)
            value = manager.get_secret("nonexistent_key")
            assert value is None

    def test_get_secret_empty_string_returns_empty(self):
        """Test that empty string secret is returned as-is."""
        with patch.dict(os.environ, {"EMPTY_KEY": ""}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            value = manager.get_secret("empty_key")
            assert value == ""

    def test_get_secret_with_whitespace(self):
        """Test that secrets with whitespace are preserved."""
        with patch.dict(os.environ, {"KEY_WITH_SPACE": "  value  "}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            value = manager.get_secret("key_with_space")
            assert value == "  value  "

    def test_get_multiple_secrets(self):
        """Test retrieving multiple secrets."""
        env_vars = {
            "OPENAI_API_KEY": "sk-openai-123",
            "ANTHROPIC_API_KEY": "sk-ant-456",
            "GOOGLE_API_KEY": "google-789",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            assert manager.get_secret("openai_api_key") == "sk-openai-123"
            assert manager.get_secret("anthropic_api_key") == "sk-ant-456"
            assert manager.get_secret("google_api_key") == "google-789"


class TestSecretsManagerDopplerBackend:
    """Tests for SecretsManager with Doppler backend (placeholder)."""

    def test_get_secret_from_doppler_raises_not_implemented(self):
        """Test that Doppler backend is not yet implemented."""
        # Doppler initialization itself should fail
        with pytest.raises(SecretsError) as exc_info:
            SecretsManager(backend=SecretsBackend.DOPPLER)
        assert "not yet implemented" in str(exc_info.value)


class TestSecretsManagerValidation:
    """Tests for required secrets validation."""

    def test_validate_all_required_secrets_present(self):
        """Test validation passes when all required secrets are present."""
        env_vars = {
            "SECRET_ONE": "value1",
            "SECRET_TWO": "value2",
            "SECRET_THREE": "value3",
        }
        with patch.dict(os.environ, env_vars, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            # Should not raise
            manager.validate_required_secrets(
                ["secret_one", "secret_two", "secret_three"]
            )

    def test_validate_single_missing_secret(self):
        """Test validation fails with descriptive error for missing secret."""
        with patch.dict(os.environ, {"SECRET_ONE": "value1"}, clear=False):
            os.environ.pop("SECRET_TWO", None)
            manager = SecretsManager(backend=SecretsBackend.ENV)
            with pytest.raises(SecretsError) as exc_info:
                manager.validate_required_secrets(["secret_one", "secret_two"])
            error_msg = str(exc_info.value)
            assert "Missing required secrets" in error_msg
            assert "secret_two" in error_msg

    def test_validate_multiple_missing_secrets(self):
        """Test validation lists all missing secrets."""
        with patch.dict(os.environ, {"SECRET_ONE": "value1"}, clear=False):
            os.environ.pop("SECRET_TWO", None)
            os.environ.pop("SECRET_THREE", None)
            manager = SecretsManager(backend=SecretsBackend.ENV)
            with pytest.raises(SecretsError) as exc_info:
                manager.validate_required_secrets(
                    ["secret_one", "secret_two", "secret_three"]
                )
            error_msg = str(exc_info.value)
            assert "Missing required secrets" in error_msg
            assert "secret_two" in error_msg
            assert "secret_three" in error_msg

    def test_validate_empty_string_counts_as_missing(self):
        """Test that empty string values are considered missing."""
        with patch.dict(
            os.environ, {"SECRET_ONE": "value1", "SECRET_TWO": ""}, clear=False
        ):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            with pytest.raises(SecretsError) as exc_info:
                manager.validate_required_secrets(["secret_one", "secret_two"])
            assert "secret_two" in str(exc_info.value)

    def test_validate_whitespace_only_counts_as_missing(self):
        """Test that whitespace-only values are considered missing."""
        with patch.dict(
            os.environ, {"SECRET_ONE": "value1", "SECRET_TWO": "   "}, clear=False
        ):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            with pytest.raises(SecretsError) as exc_info:
                manager.validate_required_secrets(["secret_one", "secret_two"])
            assert "secret_two" in str(exc_info.value)

    def test_validate_empty_required_list(self):
        """Test validation with empty required list succeeds."""
        manager = SecretsManager(backend=SecretsBackend.ENV)
        # Should not raise
        manager.validate_required_secrets([])


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_get_secrets_manager_returns_singleton(self):
        """Test that get_secrets_manager returns the same instance."""
        reset_secrets_manager()

        manager1 = get_secrets_manager()
        manager2 = get_secrets_manager()
        assert manager1 is manager2

    def test_get_secret_convenience_function(self):
        """Test convenience function for getting secrets."""
        with patch.dict(os.environ, {"TEST_SECRET": "test-value"}, clear=False):
            reset_secrets_manager()

            value = get_secret("test_secret")
            assert value == "test-value"

    def test_get_secret_not_found(self):
        """Test convenience function returns None for missing secret."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("NONEXISTENT", None)
            reset_secrets_manager()

            value = get_secret("nonexistent")
            assert value is None

    def test_validate_required_secrets_convenience_function(self):
        """Test convenience function for validation."""
        with patch.dict(
            os.environ,
            {"REQUIRED_ONE": "value1", "REQUIRED_TWO": "value2"},
            clear=False,
        ):
            reset_secrets_manager()

            # Should not raise
            validate_required_secrets(["required_one", "required_two"])

    def test_validate_required_secrets_convenience_function_failure(self):
        """Test convenience validation function raises on missing secrets."""
        with patch.dict(os.environ, {"REQUIRED_ONE": "value1"}, clear=False):
            os.environ.pop("REQUIRED_TWO", None)
            reset_secrets_manager()

            with pytest.raises(SecretsError):
                validate_required_secrets(["required_one", "required_two"])


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_get_secret_with_special_characters(self):
        """Test secrets with special characters in names."""
        # Environment variable names typically use underscores
        with patch.dict(os.environ, {"MY_API_KEY": "special-value"}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            value = manager.get_secret("my_api_key")
            assert value == "special-value"

    def test_get_secret_with_numeric_value(self):
        """Test secrets that are numeric strings."""
        with patch.dict(os.environ, {"NUMERIC_SECRET": "12345"}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            value = manager.get_secret("numeric_secret")
            assert value == "12345"
            assert isinstance(value, str)

    def test_get_secret_with_boolean_string(self):
        """Test secrets that are boolean strings."""
        with patch.dict(os.environ, {"BOOL_SECRET": "true"}, clear=False):
            manager = SecretsManager(backend=SecretsBackend.ENV)
            value = manager.get_secret("bool_secret")
            assert value == "true"
            assert isinstance(value, str)

    def test_concurrent_access_to_global_manager(self):
        """Test that global manager can be accessed multiple times safely."""
        reset_secrets_manager()

        with patch.dict(os.environ, {"SECRET": "value"}, clear=False):
            # Multiple calls should work
            value1 = get_secret("secret")
            value2 = get_secret("secret")
            assert value1 == value2 == "value"
