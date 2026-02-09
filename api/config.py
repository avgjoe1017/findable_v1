"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict

# Score band multipliers (confidence ranges)
SCORE_BAND_CONSERVATIVE = 0.85
SCORE_BAND_TYPICAL = 1.00
SCORE_BAND_GENEROUS = 1.15


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Environment
    env: Literal["development", "production", "test"] = "development"
    debug: bool = False
    log_level: str = "INFO"

    # API Server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 1
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    frontend_url: str = "http://localhost:3000"  # Production: https://getfindable.online
    rate_limit_enabled: bool = True  # Set to False to disable rate limiting in dev

    # Database
    database_url: PostgresDsn

    # Redis
    redis_url: RedisDsn

    # Authentication
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days

    # Observation Providers
    openrouter_api_key: str | None = None
    openai_api_key: str | None = None
    observation_model: str = "openai/gpt-4o-mini"  # Default to cost-effective model

    # Observation Guardrails
    observation_max_cost_per_run: float = 1.0  # Max USD per observation run
    observation_max_questions: int = 25  # Max questions per observation
    observation_timeout_seconds: float = 60.0  # Per-request timeout
    observation_total_timeout_seconds: float = 600.0  # Total run timeout
    observation_model_allowlist: list[str] = Field(
        default_factory=lambda: [
            # OpenRouter format (primary)
            "openai/gpt-4o-mini",
            "openai/gpt-4o",
            "openai/gpt-5-nano-2025-08-07",
            "anthropic/claude-3-haiku",
            "anthropic/claude-3-5-sonnet",
            # Direct OpenAI format (fallback)
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-5-nano-2025-08-07",
            "gpt-3.5-turbo",
        ]
    )

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384

    # Storage (S3-compatible)
    storage_bucket_name: str = "findable-artifacts"
    storage_endpoint_url: str | None = None
    storage_access_key: str | None = None
    storage_secret_key: str | None = None
    storage_region: str = "auto"

    # Crawler
    crawler_max_pages: int = 250
    crawler_max_depth: int = 3
    crawler_timeout: int = 30
    crawler_user_agent: str = "FindableBot/1.0 (+https://findable.ai/bot)"
    crawler_cache_enabled: bool = True  # Enable crawl result caching
    crawler_cache_ttl_seconds: int = 86400  # Cache TTL: 24 hours

    # Sentry
    sentry_dsn: str | None = None

    # Email (SendGrid or SES)
    email_provider: str = "sendgrid"  # "sendgrid" or "ses"
    sendgrid_api_key: str | None = None
    email_from_address: str = "noreply@findable.ai"
    email_from_name: str = "Findable"

    # Stripe (billing)
    stripe_secret_key: str | None = None
    stripe_publishable_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_starter_monthly: str | None = None
    stripe_price_starter_yearly: str | None = None
    stripe_price_professional_monthly: str | None = None
    stripe_price_professional_yearly: str | None = None
    stripe_price_agency_monthly: str | None = None
    stripe_price_agency_yearly: str | None = None

    # Calibration & Learning
    calibration_enabled: bool = True  # Enable calibration sample collection
    calibration_sample_collection: bool = True  # Collect samples from observation runs
    calibration_drift_check_enabled: bool = True  # Enable daily drift detection
    calibration_drift_threshold_accuracy: float = 0.10  # 10% accuracy drop triggers alert
    calibration_drift_threshold_bias: float = 0.20  # 20% bias triggers alert
    calibration_min_samples_for_analysis: int = 100  # Min samples for calibration analysis
    calibration_experiment_min_samples: int = 100  # Min samples per A/B experiment arm

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.env == "test"

    @property
    def observation_enabled(self) -> bool:
        """Check if observation is enabled (has at least one API key)."""
        return bool(self.openrouter_api_key or self.openai_api_key)

    def get_observation_model(self, requested: str | None = None) -> str:
        """Get a validated observation model, falling back to default if invalid."""
        model = requested or self.observation_model

        # Allow any model in test mode
        if self.is_test:
            return model

        # Validate against allowlist
        if model in self.observation_model_allowlist:
            return model

        # Fall back to default
        return "openai/gpt-4o-mini"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    try:
        return Settings()  # type: ignore[call-arg]
    except Exception as e:
        if "validation" in type(e).__name__.lower() or "required" in str(e).lower():
            raise RuntimeError(
                "Missing required environment variables. Set DATABASE_URL, REDIS_URL, and JWT_SECRET "
                "(e.g. in Railway: link PostgreSQL and Redis to this service, and add JWT_SECRET in Variables)."
            ) from e
        raise
