"""Post-generation validation of finished play artifacts.

Distinct from ``micro/constraints``: constraints prune candidates *during*
search, while validation judges the artifact the search produced.  A validator
must be able to fail a play the search believed was legal, and must be runnable
against a play exported weeks ago, so it lives outside the search path.
"""

from shpoet.validation.chunk_resolver import (
    ChromaChunkResolver,
    ChunkResolver,
    JsonlChunkResolver,
    build_resolver,
    check_exported_play,
    load_play_json,
    usages_from_play_json,
)
from shpoet.validation.quote_integrity import (
    IntegrityReport,
    IntegrityViolation,
    QuoteUsage,
    check_quote_integrity,
    check_used_chunks,
    usage_from_chunk,
)

__all__ = [
    "ChromaChunkResolver",
    "ChunkResolver",
    "IntegrityReport",
    "IntegrityViolation",
    "JsonlChunkResolver",
    "QuoteUsage",
    "build_resolver",
    "check_exported_play",
    "check_quote_integrity",
    "check_used_chunks",
    "load_play_json",
    "usage_from_chunk",
    "usages_from_play_json",
]
