"""
Application configuration settings.
"""
from pydantic import Field
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

    # Security
    # IMPORTANT: These MUST be set in .env file - no defaults for security
    SECRET_KEY: str = Field(..., description="Application secret key (required)")
    JWT_SECRET_KEY: str = Field(..., description="JWT signing secret key (required)")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Rate Limiting
    # IMPORTANT: Set to True in production via .env file
    RATE_LIMIT_ENABLED: bool = False
    RATE_LIMIT_STRATEGY: str = (
        "token_bucket"  # token_bucket, sliding_window, fixed_window
    )
    RATE_LIMIT_DEFAULT_LIMIT: int = 100  # requests
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # seconds

    # Notification Scheduling
    TEST_CADENCE_DAYS: int = 90  # 3 months = 90 days
    NOTIFICATION_ADVANCE_DAYS: int = 0  # Days before test is due to send notification
    NOTIFICATION_REMINDER_DAYS: int = 7  # Days after due date to send reminder

    # Test Composition (P11-004: Standard IQ Test Structure)
    # Based on IQ_TEST_RESEARCH_FINDINGS.txt, Part 5.4 (Test Construction)
    # and IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #8
    TEST_TOTAL_QUESTIONS: int = 20
    TEST_DIFFICULTY_DISTRIBUTION: dict = {
        "easy": 0.30,  # 30% easy (6 questions)
        "medium": 0.40,  # 40% medium (8 questions)
        "hard": 0.30,  # 30% hard (6 questions)
    }
    # Target ~3-4 questions per cognitive domain for balanced assessment
    # Domains: pattern, logic, spatial, math, verbal, memory (6 domains)

    # Apple Push Notification Service (APNs)
    APNS_KEY_ID: str = ""  # APNs Auth Key ID (10 characters)
    APNS_TEAM_ID: str = ""  # Apple Developer Team ID (10 characters)
    APNS_BUNDLE_ID: str = ""  # iOS app bundle identifier
    APNS_KEY_PATH: str = ""  # Path to .p8 key file
    APNS_USE_SANDBOX: bool = True  # Use sandbox APNs server for development

    # Admin Dashboard
    ADMIN_ENABLED: bool = False  # Set to True to enable admin dashboard
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = Field(
        default="",
        description="Admin dashboard password (required when ADMIN_ENABLED=True)",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from .env not defined in Settings
    )


settings = Settings()  # type: ignore[call-arg]  # Pydantic loads from .env
