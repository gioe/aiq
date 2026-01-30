"""Configuration management for question generation service."""

import logging
from typing import Optional

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Self

from app.secrets import get_secret

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Sensitive values (API keys, passwords) are loaded through the secrets
    management abstraction layer, which supports multiple backends:
    - Environment variables (default, works with Railway sealed variables)
    - Doppler (future integration)

    Configure the secrets backend via SECRETS_BACKEND environment variable:
    - "env" (default): Read from environment variables
    - "doppler": Use Doppler SDK (not yet implemented)
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database Configuration
    database_url: str = ""

    # Application Settings
    env: str = "development"
    debug: bool = True
    log_level: str = "INFO"
    log_file: str = "./logs/question_service.log"

    # LLM API Keys - loaded via secrets management
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None

    # Question Generation Settings
    questions_per_run: int = 50
    min_judge_score: float = 0.7

    # Judge Configuration
    judge_config_path: str = "./config/judges.yaml"

    # Generator Configuration (specialist routing)
    generator_config_path: str = "./config/generators.yaml"

    # Alert Configuration
    enable_email_alerts: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None  # Loaded via secrets management
    alert_from_email: Optional[str] = None
    alert_to_emails: Optional[str] = None  # Comma-separated list
    alert_file_path: str = "./logs/alerts.log"

    # Run Reporter Configuration
    enable_run_reporting: bool = True  # Enable/disable reporting to backend API
    backend_api_url: Optional[str] = None  # Backend API base URL
    backend_service_key: Optional[str] = None  # Loaded via secrets management
    prompt_version: Optional[str] = None  # Version of prompts used
    judge_config_version: Optional[str] = None  # Version of judge config

    # Provider Retry Configuration
    provider_max_retries: int = 3  # Max retry attempts for transient failures
    provider_retry_base_delay: float = (
        1.0  # Base delay in seconds for exponential backoff
    )
    provider_retry_max_delay: float = 60.0  # Maximum delay between retries in seconds
    provider_retry_exponential_base: float = 2.0  # Multiplier for exponential backoff

    # Circuit Breaker Configuration
    circuit_breaker_enabled: bool = True  # Enable/disable circuit breaker
    circuit_breaker_failure_threshold: int = (
        5  # Consecutive failures before opening circuit
    )
    circuit_breaker_error_rate_threshold: float = (
        0.5  # Error rate (0.0-1.0) to open circuit
    )
    circuit_breaker_recovery_timeout: float = 60.0  # Seconds before attempting recovery
    circuit_breaker_success_threshold: int = (
        2  # Successes in half-open to close circuit
    )
    circuit_breaker_window_size: int = 10  # Sliding window for error rate calculation

    # Deduplication Configuration
    dedup_similarity_threshold: float = 0.98  # Semantic similarity threshold (0.0-1.0)
    dedup_embedding_model: str = "text-embedding-3-small"  # OpenAI embedding model

    # Redis Embedding Cache Configuration
    redis_url: Optional[
        str
    ] = None  # Redis connection URL (e.g., redis://localhost:6379/0)
    embedding_cache_ttl: Optional[
        int
    ] = None  # TTL for cached embeddings in seconds (None = no expiration)

    # Runtime Model Validation Configuration
    provider_model_cache_ttl: int = 3600  # Cache duration in seconds (default: 1 hour)
    enable_runtime_model_validation: bool = (
        True  # Enable/disable runtime model validation
    )

    # Batch Generation Configuration (for providers that support it)
    enable_batch_generation: bool = True  # Enable/disable batch API generation
    batch_generation_size: int = 100  # Maximum prompts per batch (Google limit: 1000)
    batch_generation_timeout: float = (
        3600.0  # Timeout for batch job completion (seconds)
    )

    @field_validator("batch_generation_size")
    @classmethod
    def validate_batch_generation_size(cls, v: int) -> int:
        """Validate batch_generation_size is within Google's API limits."""
        if v < 1 or v > 1000:
            raise ValueError(
                f"batch_generation_size must be between 1 and 1000, got {v}"
            )
        return v

    @field_validator("batch_generation_timeout")
    @classmethod
    def validate_batch_generation_timeout(cls, v: float) -> float:
        """Validate batch_generation_timeout is within reasonable bounds."""
        min_timeout = 60.0  # 1 minute minimum
        max_timeout = 7200.0  # 2 hours maximum
        if v < min_timeout or v > max_timeout:
            raise ValueError(
                f"batch_generation_timeout must be between {min_timeout} and "
                f"{max_timeout} seconds, got {v}"
            )
        return v

    @model_validator(mode="after")
    def load_secrets_and_validate(self) -> Self:
        """Load secrets from secrets management backend and validate configuration.

        This validator:
        1. Loads sensitive values (API keys, passwords) from the secrets backend
        2. Validates that at least one LLM API key is configured
        3. Ensures critical secrets are present when features are enabled

        Returns:
            Self with secrets loaded

        Raises:
            ValueError: If validation fails (no LLM keys, missing required secrets)
        """
        # Load LLM API keys from secrets backend.
        # Note: The walrus operator (:=) only assigns if the value is truthy.
        # This means empty strings from the secrets backend will NOT override
        # existing env var values, which is the desired behavior - we treat
        # empty strings as "not configured" consistently with validate_required_secrets.
        if secret_value := get_secret("openai_api_key"):
            self.openai_api_key = secret_value
        if secret_value := get_secret("anthropic_api_key"):
            self.anthropic_api_key = secret_value
        if secret_value := get_secret("google_api_key"):
            self.google_api_key = secret_value
        if secret_value := get_secret("xai_api_key"):
            self.xai_api_key = secret_value

        # Load other sensitive values
        if secret_value := get_secret("smtp_password"):
            self.smtp_password = secret_value
        if secret_value := get_secret("backend_service_key"):
            self.backend_service_key = secret_value

        # Validate that at least one LLM API key is configured
        llm_keys_configured = [
            self.openai_api_key,
            self.anthropic_api_key,
            self.google_api_key,
            self.xai_api_key,
        ]
        if not any(llm_keys_configured):
            raise ValueError(
                "At least one LLM API key must be configured. "
                "Set one of: OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY, XAI_API_KEY"
            )

        # Log which LLM providers are available (without revealing keys)
        available_providers = []
        if self.openai_api_key:
            available_providers.append("OpenAI")
        if self.anthropic_api_key:
            available_providers.append("Anthropic")
        if self.google_api_key:
            available_providers.append("Google")
        if self.xai_api_key:
            available_providers.append("xAI")

        logger.info(f"Configured LLM providers: {', '.join(available_providers)}")

        # Validate email alert configuration
        if self.enable_email_alerts:
            if not self.smtp_password:
                raise ValueError(
                    "SMTP_PASSWORD must be configured when ENABLE_EMAIL_ALERTS=true"
                )
            if not self.smtp_username:
                raise ValueError(
                    "SMTP_USERNAME must be configured when ENABLE_EMAIL_ALERTS=true"
                )
            if not self.alert_to_emails:
                raise ValueError(
                    "ALERT_TO_EMAILS must be configured when ENABLE_EMAIL_ALERTS=true"
                )

        # Validate run reporting configuration
        # Only enforce in non-development environments to allow testing
        if self.enable_run_reporting and self.env not in ("development", "test"):
            if not self.backend_service_key:
                raise ValueError(
                    "BACKEND_SERVICE_KEY must be configured when ENABLE_RUN_REPORTING=true"
                )
            if not self.backend_api_url:
                raise ValueError(
                    "BACKEND_API_URL must be configured when ENABLE_RUN_REPORTING=true"
                )

        return self


# Global settings instance
settings = Settings()
