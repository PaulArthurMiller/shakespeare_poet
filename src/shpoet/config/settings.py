"""Application settings loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

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
    db_path: str = Field(
        default=":memory:",
        description="SQLite database path. Set SHPOET_DB_PATH to a file path for persistent storage.",
        validation_alias="SHPOET_DB_PATH",
    )
    output_dir: Optional[Path] = Field(
        default=None,
        description="Directory for exported play files. Disabled when unset.",
        validation_alias="SHPOET_OUTPUT_DIR",
    )

    # LLM (Anthropic — critic & chooser)
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    llm_model: str = Field(
        default="claude-haiku-4-5-20251001",
        description="Anthropic model for critic/chooser. Haiku is fast and economical for checkpoint evals.",
        validation_alias="SHPOET_LLM_MODEL",
    )
    use_critic: bool = Field(
        default=True,
        description="Enable LLM critic at beam-search checkpoints (requires ANTHROPIC_API_KEY).",
        validation_alias="SHPOET_USE_CRITIC",
    )
    use_chooser: bool = Field(
        default=False,
        description="Enable LLM chooser for high-entropy decisions (requires ANTHROPIC_API_KEY).",
        validation_alias="SHPOET_USE_CHOOSER",
    )

    # Embeddings
    embedding_provider: str = Field(
        default="openai",
        description="Embedding provider: openai | voyage. Falls back to stub when no key is set.",
        validation_alias="SHPOET_EMBEDDING_PROVIDER",
    )
    embedding_model: str = Field(
        default="text-embedding-3-large",
        description="Embedding model name. For Voyage AI use e.g. voyage-3-large.",
        validation_alias="SHPOET_EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(
        default=3072,
        description="Output dimensions. 3072 for text-embedding-3-large; 1024 for voyage-3-large.",
        validation_alias="SHPOET_EMBEDDING_DIMENSIONS",
    )
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    voyage_api_key: str = Field(default="", validation_alias="VOYAGE_API_KEY")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance for consistent configuration access."""

    return Settings()


def reset_settings() -> None:
    """Clear cached settings to allow environment refresh in tests."""

    # get_settings may have been monkeypatched to a plain callable by a test
    # (e.g. to inject a fake Settings double); nothing to clear in that case.
    if hasattr(get_settings, "cache_clear"):
        get_settings.cache_clear()
