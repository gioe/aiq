"""
Application configuration settings.
"""

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Dict, List, Literal, Self

from app.models.models import QuestionType


# Tolerance for floating-point weight summation checks
_WEIGHT_SUM_TOLERANCE = 1e-6


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "AIQ API"
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
    # Enabled by default to protect all deployments. Set to False via .env for local development if needed.
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STRATEGY: Literal["token_bucket", "sliding_window", "fixed_window"] = (
        "token_bucket"
    )
    RATE_LIMIT_DEFAULT_LIMIT: int = 100  # requests
    RATE_LIMIT_DEFAULT_WINDOW: int = 60  # seconds
    # Storage backend: "memory" for single-worker, "redis" for multi-worker deployments
    RATE_LIMIT_STORAGE: Literal["memory", "redis"] = "memory"
    # Redis connection URL (required if RATE_LIMIT_STORAGE="redis")
    RATE_LIMIT_REDIS_URL: str = "redis://localhost:6379/0"
    # Maximum keys for in-memory storage (0 = unlimited, recommended: 10000-100000)
    # Prevents memory exhaustion attacks by using LRU eviction when limit is reached
    RATE_LIMIT_MAX_KEYS: int = 100000

    # Token Blacklist (for JWT revocation)
    # Redis connection URL for token blacklist (optional, uses in-memory if not set)
    # Production: Use rediss:// (TLS) with strong password
    TOKEN_BLACKLIST_REDIS_URL: str = ""

    # Notification Scheduling
    TEST_CADENCE_DAYS: int = 90  # 3 months = 90 days
    NOTIFICATION_ADVANCE_DAYS: int = 0  # Days before test is due to send notification
    NOTIFICATION_REMINDER_DAYS: int = 7  # Days after due date to send reminder

    # Test Composition (P11-004: Standard IQ Test Structure)
    # Based on IQ_TEST_RESEARCH_FINDINGS.txt, Part 5.4 (Test Construction)
    # and IQ_METHODOLOGY_DIVERGENCE_ANALYSIS.txt, Divergence #8
    TEST_TOTAL_QUESTIONS: int = 25
    TEST_DIFFICULTY_DISTRIBUTION: dict = {
        "easy": 0.20,  # 20% easy (5 questions)
        "medium": 0.50,  # 50% medium (~13 questions)
        "hard": 0.30,  # 30% hard (~7 questions)
    }
    # Weighted domain distribution based on CHC theory g-loadings.
    # Gf (Fluid Reasoning) has the highest g-loading (~0.70-0.80) and is split
    # across pattern + logic. Gc, Gv, Gq, and Gsm receive progressively lower
    # weights reflecting their empirical g-saturation (McGrew 2009; Carroll 1993).
    # Keys must match QuestionType enum values in app/models/models.py
    TEST_DOMAIN_WEIGHTS: Dict[str, float] = {
        "pattern": 0.22,  # Gf — perceptual/matrix reasoning (highest g-loading)
        "logic": 0.20,  # Gf — deductive/inductive reasoning
        "verbal": 0.19,  # Gc — verbal comprehension
        "spatial": 0.16,  # Gv — visual-spatial processing
        "math": 0.13,  # Gq — quantitative reasoning
        "memory": 0.10,  # Gsm — working memory (lowest g-loading)
    }

    # CAT (Computerized Adaptive Testing) readiness thresholds (TASK-835)
    # These control when the system considers the question bank ready for adaptive testing
    CAT_MIN_CALIBRATED_ITEMS_PER_DOMAIN: int = 30
    CAT_MAX_SE_DIFFICULTY: float = 0.50
    CAT_MAX_SE_DISCRIMINATION: float = 0.30
    CAT_MIN_ITEMS_PER_DIFFICULTY_BAND: int = 5

    # A/B Testing Configuration (TASK-885)
    # Percentage of users to assign to adaptive (CAT) testing mode
    # Can be ramped from 0% (all fixed) to 100% (all adaptive) for gradual rollout
    ADAPTIVE_TEST_PERCENTAGE: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage of users assigned to adaptive testing (0.0-100.0)",
    )

    # Apple Push Notification Service (APNs)
    APNS_KEY_ID: str = ""  # APNs Auth Key ID (10 characters)
    APNS_TEAM_ID: str = ""  # Apple Developer Team ID (10 characters)
    APNS_BUNDLE_ID: str = ""  # iOS app bundle identifier
    APNS_KEY_PATH: str = ""  # Path to .p8 key file
    APNS_USE_SANDBOX: bool = True  # Use sandbox APNs server for development

    # Admin Dashboard
    ADMIN_ENABLED: bool = False  # Set to True to enable admin dashboard
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD_HASH: str = Field(
        default="",
        description="Bcrypt-hashed admin dashboard password (required when ADMIN_ENABLED=True). "
        "Generate with: python -c \"import bcrypt; print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())\"",
    )
    ADMIN_TOKEN: str = Field(
        default="",
        description="Admin API token for triggering jobs (required for admin endpoints)",
    )

    # Service-to-Service Authentication
    SERVICE_API_KEY: str = Field(
        default="",
        description="API key for service-to-service authentication (e.g., question-service)",
    )

    # Sentry Error Tracking
    SENTRY_DSN: str = Field(
        default="",
        description="Sentry DSN for error tracking (leave empty to disable)",
    )
    SENTRY_TRACES_SAMPLE_RATE: float = Field(
        default=0.1,
        ge=0.0,
        le=1.0,
        description="Sentry traces sample rate (0.0-1.0, 0.1 = 10% of transactions)",
    )

    # OpenTelemetry Distributed Tracing and Observability
    OTEL_ENABLED: bool = False
    OTEL_SERVICE_NAME: str = "aiq-backend"
    OTEL_EXPORTER: Literal["console", "otlp", "none"] = "console"
    OTEL_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_TRACES_SAMPLE_RATE: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Trace sample rate (0.0-1.0, 1.0 = 100%)",
    )
    # Metrics configuration
    OTEL_METRICS_ENABLED: bool = False
    OTEL_METRICS_EXPORT_INTERVAL_MILLIS: int = 60000  # 60 seconds
    # Prometheus metrics endpoint
    PROMETHEUS_METRICS_ENABLED: bool = False
    # Logs configuration
    OTEL_LOGS_ENABLED: bool = False
    # Grafana Cloud / OTLP authentication
    OTEL_EXPORTER_OTLP_HEADERS: str = Field(
        default="",
        repr=False,
        description="OTLP exporter headers (e.g., 'Authorization=Bearer <token>' for Grafana Cloud)",
    )

    # Email/SMTP Settings (for feedback notifications)
    # NOTE: Email functionality is not yet implemented - these are placeholder settings
    SMTP_HOST: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname",
    )
    SMTP_PORT: int = Field(
        default=587,
        description="SMTP server port (587 for TLS, 465 for SSL)",
    )
    SMTP_USERNAME: str = Field(
        default="",
        description="SMTP authentication username",
    )
    SMTP_PASSWORD: str = Field(
        default="",
        description="SMTP authentication password",
    )
    SMTP_FROM_EMAIL: str = Field(
        default="noreply@aiq.app",
        description="Email address to send from",
    )
    SMTP_FROM_NAME: str = Field(
        default="AIQ Support",
        description="Display name for sent emails",
    )
    ADMIN_EMAIL: str = Field(
        default="admin@aiq.app",
        description="Admin email address for feedback notifications",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields from .env not defined in Settings
    )

    @model_validator(mode="after")
    def validate_admin_config(self) -> Self:
        """Validate admin dashboard configuration at startup."""
        if self.ADMIN_ENABLED and not self.ADMIN_PASSWORD_HASH:
            raise ValueError(
                "ADMIN_PASSWORD_HASH must be set when ADMIN_ENABLED=True. "
                'Generate with: python -c "import bcrypt; '
                "print(bcrypt.hashpw(b'your_password', bcrypt.gensalt()).decode())\""
            )
        return self

    @model_validator(mode="after")
    def validate_domain_weights(self) -> Self:
        """Validate TEST_DOMAIN_WEIGHTS: positive values summing to 1.0."""
        weights = self.TEST_DOMAIN_WEIGHTS
        expected_domains = {qt.value for qt in QuestionType}
        if set(weights.keys()) != expected_domains:
            raise ValueError(
                f"TEST_DOMAIN_WEIGHTS keys must be {sorted(expected_domains)}, "
                f"got {sorted(weights.keys())}"
            )
        non_positive = [k for k, v in weights.items() if v <= 0]
        if non_positive:
            raise ValueError(
                f"All domain weights must be positive, got non-positive: {non_positive}"
            )
        total = sum(weights.values())
        if abs(total - 1.0) > _WEIGHT_SUM_TOLERANCE:
            raise ValueError(f"TEST_DOMAIN_WEIGHTS must sum to 1.0, got {total}")
        return self


# mypy doesn't understand that pydantic_settings loads required fields from env vars
settings = Settings()  # type: ignore[call-arg]
