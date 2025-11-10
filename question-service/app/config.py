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

    # LLM API Keys
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Question Generation Settings
    questions_per_run: int = 50
    min_arbiter_score: float = 0.7

    # Arbiter Configuration
    arbiter_config_path: str = "./config/arbiters.yaml"


# Global settings instance
settings = Settings()
