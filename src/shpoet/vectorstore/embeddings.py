"""Deterministic stub embeddings for local development and tests."""

from __future__ import annotations

import hashlib
import logging
from typing import List


logger = logging.getLogger(__name__)


def _hash_to_floats(text: str, dimensions: int) -> List[float]:
    """Convert a text hash into a list of floats for embeddings."""

    digest = hashlib.sha256(text.encode("utf-8")).digest()
    floats: List[float] = []
    for idx in range(dimensions):
        byte = digest[idx % len(digest)]
        floats.append(byte / 255.0)
    return floats


def embed_texts(texts: List[str], dimensions: int = 8) -> List[List[float]]:
    """Return deterministic embeddings for a list of texts."""

    embeddings = [_hash_to_floats(text, dimensions) for text in texts]
    logger.info("Generated %s embeddings with %s dimensions", len(embeddings), dimensions)
    return embeddings


def embed_query(query: str, dimensions: int = 8) -> List[float]:
    """Return a deterministic embedding for a query string."""

    return _hash_to_floats(query, dimensions)
