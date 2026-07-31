"""Global reuse lock preventing any source word from being quoted twice.

The lock used to key on ``chunk_id``, which does not express the rule it was
meant to enforce: overlapping chunks cut from one source line have different
ids, so a play could quote "the multitudinous seas incarnadine" as a phrase and
again inside a full line and still pass.  It now keys on the source word span
(see ``common/spans.py``); marking any chunk used locks every overlapping span
on that line, whichever chunker produced it.

Chunk ids are still tracked alongside spans.  They are the cheap first check,
and they remain the only available identity for a chunk whose provenance is
missing or malformed.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, List, Mapping, Set

from shpoet.common.spans import SourceSpan, span_from_chunk


logger = logging.getLogger(__name__)


class ReuseLock:
    """Track used chunk ids and used source spans to prevent quote reuse."""

    def __init__(self) -> None:
        """Initialize the reuse lock with nothing marked as used."""

        self._used_ids: Set[str] = set()
        # Keyed by line_id so an overlap check only scans spans from the same
        # source line -- a handful at most, since a line is ~10 words.
        self._used_spans: Dict[str, List[SourceSpan]] = {}
        self._unverifiable_ids: Set[str] = set()

    def mark_used(self, chunk: Mapping[str, object]) -> None:
        """Record a chunk as used, locking its id and its source span."""

        chunk_id = str(chunk.get("chunk_id", ""))
        if chunk_id:
            self._used_ids.add(chunk_id)

        span = span_from_chunk(chunk)
        if span is None:
            # Locking degrades to id-only for this chunk. Tracked rather than
            # ignored so a corpus that lost its provenance is visible instead of
            # quietly weakening the no-reuse rule.
            if chunk_id:
                self._unverifiable_ids.add(chunk_id)
            logger.warning(
                "Chunk %s has no usable source span; reuse locking falls back to chunk_id",
                chunk_id or "<unidentified>",
            )
            return

        self._used_spans.setdefault(span.line_id, []).append(span)
        logger.debug("Locked span %s (chunk %s)", span.describe(), chunk_id)

    def mark_used_many(self, chunks: Iterable[Mapping[str, object]]) -> None:
        """Record multiple chunks as used."""

        count = 0
        for chunk in chunks:
            self.mark_used(chunk)
            count += 1
        logger.debug("Marked %s chunks as used", count)

    def mark_id_used(self, chunk_id: str) -> None:
        """Record a bare chunk id as used, with no span information.

        For callers that hold only ids -- a persisted generation record, say.
        This cannot enforce the span rule, so prefer ``mark_used`` whenever the
        chunk dict is available.
        """

        if not chunk_id:
            return
        self._used_ids.add(chunk_id)
        self._unverifiable_ids.add(chunk_id)
        logger.debug("Locked chunk id %s (no span available)", chunk_id)

    def is_used(self, chunk: Mapping[str, object]) -> bool:
        """Return True if the chunk's id or any of its source words are used."""

        chunk_id = str(chunk.get("chunk_id", ""))
        if chunk_id and chunk_id in self._used_ids:
            return True

        span = span_from_chunk(chunk)
        if span is None:
            return False

        return any(span.overlaps(used) for used in self._used_spans.get(span.line_id, ()))

    def is_id_used(self, chunk_id: str) -> bool:
        """Return True if this exact chunk id has been marked used."""

        return chunk_id in self._used_ids

    @property
    def used_ids(self) -> Set[str]:
        """A copy of the chunk ids marked used so far."""

        return set(self._used_ids)

    @property
    def used_span_count(self) -> int:
        """Number of source spans currently locked."""

        return sum(len(spans) for spans in self._used_spans.values())

    @property
    def unverifiable_count(self) -> int:
        """Number of used chunks that carried no usable source span.

        Non-zero means the no-reuse rule is being enforced by id alone for that
        many chunks, which is weaker than the rule the project promises.
        """

        return len(self._unverifiable_ids)

    def reset(self) -> None:
        """Clear all tracked ids and spans."""

        self._used_ids.clear()
        self._used_spans.clear()
        self._unverifiable_ids.clear()
        logger.info("Reuse lock reset")
