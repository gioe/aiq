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
    min_arbiter_score: float = 0.7

    # Arbiter Configuration
    arbiter_config_path: str = "./config/arbiters.yaml"

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
    arbiter_config_version: Optional[str] = None  # Version of arbiter config


# Global settings instance
settings = Settings()
