"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    observation_model: str = "auto"

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

    # Sentry
    sentry_dsn: str | None = None

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

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.env == "production"

    @property
    def is_test(self) -> bool:
        """Check if running in test mode."""
        return self.env == "test"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
