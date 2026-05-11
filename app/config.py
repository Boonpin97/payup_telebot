"""Application configuration loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")

    google_cloud_project: str = Field(default="", alias="GOOGLE_CLOUD_PROJECT")
    firestore_database_id: str = Field(default="(default)", alias="FIRESTORE_DATABASE_ID")

    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # 3-minute multi-step session timeout, per the spec.
    session_ttl_seconds: int = Field(default=180, alias="SESSION_TTL_SECONDS")

    default_currency: str = Field(default="SGD", alias="DEFAULT_CURRENCY")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
