"""Source-span identity for quoted text.

The project's defining rule is that no fragment of the source text may appear
twice in a generated play (``AGENTS.md``).  Chunk ids cannot express that rule.
Three chunkers run over the same corpus, so a single Shakespeare line yields a
full-line chunk, one or more phrase chunks, and several fragment chunks -- all
carrying different ids and all made of the same words.  ``ham_3_1_l56``,
``ham_3_1_l56_p0`` and ``ham_3_1_l56_f2`` are three identities for one piece of
text, so locking on ``chunk_id`` lets the same words be quoted repeatedly.

The identity that actually matters is the span of source words a chunk occupies:
``(line_id, start_word_idx .. end_word_idx)``.  Every chunker writes that triple
through ``chunking/provenance.py``, and Chroma stores all three as scalars, so
the span is available wherever a chunk dict is -- both on the retrieval path and
on the processed-JSONL fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple


logger = logging.getLogger(__name__)


@dataclass(frozen=True, order=True)
class SourceSpan:
    """A contiguous run of words on one canonical source line.

    Both bounds are inclusive, matching ``chunking/provenance.py``: a chunk
    covering the first four words of a line is ``0..3``, not ``0..4``.
    """

    line_id: str
    start_word_idx: int
    end_word_idx: int

    def __post_init__(self) -> None:
        """Reject inverted spans, which would silently never overlap anything."""

        if self.end_word_idx < self.start_word_idx:
            raise ValueError(
                f"Inverted source span on {self.line_id}: "
                f"start={self.start_word_idx} end={self.end_word_idx}"
            )

    @property
    def word_count(self) -> int:
        """Number of source words this span covers."""

        return self.end_word_idx - self.start_word_idx + 1

    def overlaps(self, other: "SourceSpan") -> bool:
        """Return True when the two spans share at least one source word.

        Adjacency is deliberately *not* overlap: ``0..3`` and ``4..7`` on the
        same line quote different words and may both appear in a play.
        """

        if self.line_id != other.line_id:
            return False
        return self.start_word_idx <= other.end_word_idx and other.start_word_idx <= self.end_word_idx

    def overlapping_indices(self, other: "SourceSpan") -> Tuple[int, ...]:
        """Return the source word indices shared with another span."""

        if not self.overlaps(other):
            return ()
        first = max(self.start_word_idx, other.start_word_idx)
        last = min(self.end_word_idx, other.end_word_idx)
        return tuple(range(first, last + 1))

    def describe(self) -> str:
        """Return a short human-readable reference for logs and violations."""

        if self.word_count == 1:
            return f"{self.line_id}[{self.start_word_idx}]"
        return f"{self.line_id}[{self.start_word_idx}-{self.end_word_idx}]"


def _coerce_index(value: object) -> Optional[int]:
    """Convert a stored word index to int, tolerating Chroma's float round-trip.

    Chroma stores numeric metadata as scalars but may hand integers back as
    floats, and the JSONL path hands back real ints.  Anything that is not a
    whole number is treated as absent rather than guessed at.
    """

    if isinstance(value, bool):  # bool is an int subclass; never a word index
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value) if value.is_integer() else None
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError:
            return None
    return None


def _span_from_word_index(line_id: str, word_index: object) -> Optional[SourceSpan]:
    """Recover a span from the comma-separated ``word_index`` provenance field.

    A fallback for chunk dicts that carry ``word_index`` but not the explicit
    ``start_word_idx``/``end_word_idx`` pair.  ``provenance.validate_provenance``
    already guarantees the indices are sequential, so first and last bound it.
    """

    if not isinstance(word_index, str) or not word_index.strip():
        return None
    try:
        indices = [int(part) for part in word_index.split(",") if part.strip()]
    except ValueError:
        return None
    if not indices:
        return None
    return SourceSpan(line_id=line_id, start_word_idx=indices[0], end_word_idx=indices[-1])


def span_from_chunk(chunk: Mapping[str, object]) -> Optional[SourceSpan]:
    """Extract the source span a chunk occupies, or None if it cannot be known.

    Returns None rather than a guess when provenance is absent or malformed.
    Callers must treat None as *unverifiable*, not as *safe*: a chunk whose span
    is unknown cannot be span-locked, so it falls back to id-level locking and
    is counted as unverifiable by the integrity validator.  Silently defaulting
    here is exactly the failure mode this codebase keeps producing.
    """

    line_id = chunk.get("line_id")
    if not isinstance(line_id, str) or not line_id.strip():
        return None
    line_id = line_id.strip()

    start = _coerce_index(chunk.get("start_word_idx"))
    end = _coerce_index(chunk.get("end_word_idx"))

    if start is None or end is None:
        return _span_from_word_index(line_id, chunk.get("word_index"))

    if end < start:
        logger.warning(
            "Discarding inverted span on %s (start=%s end=%s) for chunk %s",
            line_id, start, end, chunk.get("chunk_id"),
        )
        return None

    return SourceSpan(line_id=line_id, start_word_idx=start, end_word_idx=end)
