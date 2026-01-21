"""Line chunking implementation.

Line chunks represent complete Shakespeare lines as single quotes.
These are the maximum-length quote unit (one original line = one chunk).
Each line chunk maintains full provenance for quote tracking and validation.

Line chunks are useful when:
- A complete line works as a standalone quote
- The full line is needed for context or meter
- Maximum quote length is acceptable for the generation context
"""

from __future__ import annotations

import logging
from typing import Dict, List

from shpoet.chunking.provenance import build_provenance, validate_provenance
from shpoet.ingest.canon_index import CanonicalLine


logger = logging.getLogger(__name__)


def build_line_chunks(lines: List[CanonicalLine]) -> List[Dict[str, object]]:
    """Build line chunks from canonical line entries.

    Each line becomes a single chunk containing the complete line text.
    This is the primary chunking unit - the maximum quote length allowed
    (no quote can exceed one original Shakespeare line).

    The chunk includes:
    - chunk_id: Stable identifier derived from line_id
    - text: The full line text
    - tokens: List of word tokens
    - token_count: Number of words
    - Full provenance (play, act, scene, line, word_index)

    Args:
        lines: List of CanonicalLine objects from the canonical index

    Returns:
        List of chunk dictionaries with text, tokens, and full provenance
    """
    chunks: List[Dict[str, object]] = []

    for line in lines:
        # Use line_id directly as chunk_id for full-line chunks
        chunk = {
            "chunk_id": line.line_id,
            "text": line.raw_text,
            "tokens": line.tokens,
            "token_count": len(line.tokens),
        }

        # Add full provenance metadata
        provenance = build_provenance(line)
        chunk.update(provenance)

        # Validate provenance before adding chunk
        if not validate_provenance(provenance):
            logger.warning(
                "Invalid provenance for line %s, skipping: %s",
                line.line_id, line.raw_text[:50]
            )
            continue

        chunks.append(chunk)

        logger.debug(
            "Created line chunk %s: '%s' (%d words)",
            chunk["chunk_id"], line.raw_text[:40], len(line.tokens)
        )

    logger.info("Built %d line chunks from %d input lines", len(chunks), len(lines))

    return chunks


def get_line_chunk_by_id(
    chunks: List[Dict[str, object]],
    chunk_id: str,
) -> Dict[str, object] | None:
    """Find a line chunk by its chunk_id.

    Useful for quote validation and lookup.

    Args:
        chunks: List of line chunk dictionaries
        chunk_id: The chunk_id to search for

    Returns:
        The matching chunk dictionary, or None if not found
    """
    for chunk in chunks:
        if chunk.get("chunk_id") == chunk_id:
            return chunk
    return None


def filter_unused_line_chunks(
    chunks: List[Dict[str, object]],
    used_line_ids: set,
) -> List[Dict[str, object]]:
    """Filter out line chunks that have already been used.

    For the quote map system - once a full line is used, it cannot
    be used again.

    Args:
        chunks: List of line chunk dictionaries
        used_line_ids: Set of line_ids that have been used

    Returns:
        List of chunks whose lines have not been used
    """
    available = [
        chunk for chunk in chunks
        if chunk.get("line_id") not in used_line_ids
    ]

    logger.debug(
        "Filtered line chunks: %d available out of %d total",
        len(available), len(chunks)
    )

    return available
