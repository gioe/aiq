"""Configuration management for question generation service."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

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

    # LLM API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    xai_api_key: Optional[str] = None

    # Question Generation Settings
    questions_per_run: int = 50
    min_judge_score: float = 0.7

    # Judge Configuration
    judge_config_path: str = "./config/judges.yaml"

    # Alert Configuration
    enable_email_alerts: bool = False
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    alert_from_email: Optional[str] = None
    alert_to_emails: Optional[str] = None  # Comma-separated list
    alert_file_path: str = "./logs/alerts.log"

    # Run Reporter Configuration
    enable_run_reporting: bool = True  # Enable/disable reporting to backend API
    backend_api_url: Optional[str] = None  # Backend API base URL
    backend_service_key: Optional[str] = None  # API key for service-to-service auth
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
    dedup_similarity_threshold: float = 0.85  # Semantic similarity threshold (0.0-1.0)
    dedup_embedding_model: str = "text-embedding-3-small"  # OpenAI embedding model


# Global settings instance
settings = Settings()
