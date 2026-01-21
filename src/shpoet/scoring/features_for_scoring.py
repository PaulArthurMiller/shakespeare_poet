"""Feature extraction helpers for scoring candidates."""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List


logger = logging.getLogger(__name__)


def _normalize_tokens(tokens: Iterable[str]) -> List[str]:
    """Normalize tokens to lowercase for matching."""

    return [token.lower() for token in tokens]


def _extract_tokens(chunk: Dict[str, object]) -> List[str]:
    """Extract tokens from a chunk or fall back to splitting text."""

    raw_tokens = chunk.get("tokens")
    if isinstance(raw_tokens, list):
        return [str(token) for token in raw_tokens]
    text = str(chunk.get("text", ""))
    return [token for token in text.replace("\n", " ").split(" ") if token]


def compute_anchor_hits(tokens: Iterable[str], anchor_targets: Iterable[str]) -> List[str]:
    """Return the list of anchor targets that appear in the token list."""

    normalized_tokens = set(_normalize_tokens(tokens))
    hits = [anchor for anchor in anchor_targets if anchor.lower() in normalized_tokens]
    logger.debug("Anchor hits computed: %s", hits)
    return hits


def build_scoring_features(
    chunk: Dict[str, object],
    anchor_targets: Iterable[str],
) -> Dict[str, object]:
    """Build a minimal scoring feature bundle from a chunk dictionary."""

    tokens = _extract_tokens(chunk)
    anchor_hits = compute_anchor_hits(tokens, anchor_targets)
    features: Dict[str, object] = {
        "token_count": int(chunk.get("token_count", len(tokens))),
        "anchor_hits": anchor_hits,
        "anchor_hit_count": len(anchor_hits),
    }
    logger.debug("Scoring features built for chunk %s", chunk.get("chunk_id"))
    return features
