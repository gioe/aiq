"""
Application configuration settings.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "IQ Tracker API"
    APP_VERSION: str = "0.1.0"
    ENV: str = "development"
    DEBUG: bool = True

    # API
    API_V1_PREFIX: str = "/v1"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8081",
    ]

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from .env not defined in Settings
    )


settings = Settings()
