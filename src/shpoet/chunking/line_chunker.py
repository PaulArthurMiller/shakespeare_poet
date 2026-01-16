"""Line chunking implementation."""

from __future__ import annotations

import logging
from typing import Dict, List

from shpoet.chunking.provenance import build_provenance
from shpoet.ingest.canon_index import CanonicalLine


logger = logging.getLogger(__name__)


def build_line_chunks(lines: List[CanonicalLine]) -> List[Dict[str, object]]:
    """Build line chunks from canonical line entries."""

    chunks: List[Dict[str, object]] = []
    for line in lines:
        chunk = {
            "chunk_id": line.line_id,
            "text": line.raw_text,
            "tokens": line.tokens,
            "token_count": len(line.tokens),
        }
        chunk.update(build_provenance(line))
        chunks.append(chunk)

    logger.info("Built %s line chunks", len(chunks))
    return chunks
