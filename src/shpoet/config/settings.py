"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed settings for the Shakespearean Poet service."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = Field(default="Shakespearean Poet")
    log_config_path: Path = Field(default=Path("src/shpoet/config/logging.yaml"))
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)
    processed_dir: Path = Field(
        default=Path("data/processed"),
        validation_alias="SHPOET_PROCESSED_DIR",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for consistent configuration access."""

    return Settings()


def reset_settings() -> None:
    """Clear cached settings to allow environment refresh in tests."""

    get_settings.cache_clear()
