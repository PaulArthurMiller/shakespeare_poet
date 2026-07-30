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
    chroma_dir: Path = Field(
        default=Path("data/chroma"),
        description="Directory holding the persisted Chroma collections used for candidate retrieval.",
        validation_alias="SHPOET_CHROMA_DIR",
    )
    retrieval_pool_size: int = Field(
        default=800,
        description=(
            "Candidate chunks retrieved per beat, summed across collections. "
            "Set to 0 to disable retrieval and fall back to the full processed corpus."
        ),
        validation_alias="SHPOET_RETRIEVAL_POOL_SIZE",
    )
    # Artistic constraint knobs.
    #
    # These are engineering knobs, not user-facing sliders (ARCHITECTURE.md §9).
    # They live in config rather than being hardcoded so that setting them all to
    # zero reproduces the pre-M1 behaviour exactly — that is the control group for
    # any quality comparison.
    meter_strictness: float = Field(
        default=0.4,
        ge=0.0,
        le=1.0,
        description=(
            "Acceptance threshold for iambic flow between adjacent chunks; higher "
            "prunes more. Because normalized stress is binary, adjacency scores "
            "take only three values (1.0, 0.9, 0.3), so this knob has exactly "
            "three regimes rather than a smooth range:\n"
            "  0.0-0.3  off: nothing is pruned on meter\n"
            "  0.4-0.9  reject same-stress collisions (measured: ~36% of a real "
            "800-chunk pool survives)\n"
            "  0.95+    accept only perfect stressed->unstressed transitions "
            "(measured: ~22% survives)\n"
            "0.4 is the default: it enforces real metrical flow while leaving "
            "roughly 290 candidates per beat, which is ample for beam search. "
            "Going to 0.95+ starves the pool and drives rollback loops."
        ),
        validation_alias="SHPOET_METER_STRICTNESS",
    )
    meter_preference: float = Field(
        default=1.0,
        ge=0.0,
        description=(
            "Scoring weight on a candidate's iambic_score (0.0-1.0). At 1.0 a "
            "perfectly iambic line is worth roughly one anchor hit."
        ),
        validation_alias="SHPOET_METER_PREFERENCE",
    )
    length_preference: float = Field(
        default=0.1,
        ge=0.0,
        description=(
            "Scoring penalty per syllable of deviation from the 10-syllable "
            "pentameter target. 0.1 matches the value ScoringEngine used implicitly."
        ),
        validation_alias="SHPOET_LENGTH_PREFERENCE",
    )
    emotion_alignment: float = Field(
        default=0.0,
        ge=0.0,
        description=(
            "Scoring weight on emotional valence match. DEFAULTS TO OFF, and that "
            "is deliberate: emotion_valence is degenerate across the corpus (89% of "
            "chunks are exactly 0.0), so with target_valence at 0.0 this term pays "
            "every neutral line and pays nothing to the emotionally marked ones — "
            "it would actively reward blandness. Leave off until features/semantics.py "
            "produces a real distribution (BUILD-PLAN.md M7)."
        ),
        validation_alias="SHPOET_EMOTION_ALIGNMENT",
    )
    target_valence: float = Field(
        default=0.0,
        ge=-1.0,
        le=1.0,
        description=(
            "Emotional valence the scorer aims for, -1.0 (bleak) to 1.0 (bright). "
            "Only has effect when emotion_alignment is above zero."
        ),
        validation_alias="SHPOET_TARGET_VALENCE",
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
