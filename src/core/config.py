"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with defaults for all configuration options."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "gerald-gateway"
    app_version: str = "0.1.0"
    debug: bool = False

    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "postgresql://postgres:postgres@localhost:5432/gerald"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    bank_api_url: str = "http://localhost:8001"
    bank_api_timeout: float = 10.0

    ledger_webhook_url: str = "http://localhost:8002/mock-ledger"
    ledger_webhook_timeout: float = 5.0

    metrics_enabled: bool = True
    metrics_port: int = 9090

    log_level: str = "INFO"
    log_format: str = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
