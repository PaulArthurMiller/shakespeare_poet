"""Post-generation check that no source words are quoted twice.

``AGENTS.md`` states the rule this module enforces: *no quote fragment reused
anywhere in the generated play*.  ``ReuseLock`` enforces it during search, but a
constraint inside the search loop can only be trusted so far -- it depends on
the pool carrying provenance, on every path going through the lock, and on the
lock being seeded correctly at each beat.  This module checks the finished
artifact independently, so a wiring mistake shows up as a failed play rather
than as verse that quietly breaks the project's defining rule.

It reports three things, and the third matters as much as the second:

* ``violations``  -- pairs of quotes sharing source words.
* ``checked``     -- how many quotes were actually verified.
* ``unverifiable``-- quotes with no usable provenance.  These are *not* passes.
  A play built from chunks with no ``line_id`` would otherwise report zero
  violations while proving nothing at all.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from shpoet.common.spans import SourceSpan, span_from_chunk


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QuoteUsage:
    """One quotation as it appears in a generated play."""

    beat_id: str
    chunk_id: str
    text: str
    span: Optional[SourceSpan] = None

    def describe(self) -> str:
        """Return a short reference naming where this quote came from and landed."""

        location = self.span.describe() if self.span else f"{self.chunk_id} (no span)"
        return f"beat {self.beat_id}: {location}"


@dataclass(frozen=True)
class IntegrityViolation:
    """Two quotations in one play that draw on the same source words."""

    kind: str  # "span_overlap" or "chunk_repeat"
    first: QuoteUsage
    second: QuoteUsage
    line_id: str
    shared_word_indices: Tuple[int, ...] = ()

    def describe(self) -> str:
        """Return a human-readable account of the violation."""

        if self.kind == "chunk_repeat":
            return (
                f"chunk {self.first.chunk_id} used twice "
                f"({self.first.describe()} and {self.second.describe()})"
            )
        words = ", ".join(str(index) for index in self.shared_word_indices)
        return (
            f"source line {self.line_id} words [{words}] quoted twice: "
            f"{self.first.describe()} (\"{self.first.text}\") and "
            f"{self.second.describe()} (\"{self.second.text}\")"
        )

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable form for persistence on a run record."""

        return {
            "kind": self.kind,
            "line_id": self.line_id,
            "shared_word_indices": list(self.shared_word_indices),
            "first": {
                "beat_id": self.first.beat_id,
                "chunk_id": self.first.chunk_id,
                "text": self.first.text,
            },
            "second": {
                "beat_id": self.second.beat_id,
                "chunk_id": self.second.chunk_id,
                "text": self.second.text,
            },
        }


@dataclass(frozen=True)
class IntegrityReport:
    """The outcome of validating one play's quote integrity."""

    checked: int
    unverifiable: int
    violations: Tuple[IntegrityViolation, ...]

    @property
    def passed(self) -> bool:
        """True when no two quotes share source words.

        Unverifiable quotes do not fail the play -- their provenance is missing,
        not contradicted -- but they are reported so a caller can decide whether
        a "clean" result was actually measured.
        """

        return not self.violations

    def describe(self) -> str:
        """Return a one-line summary suitable for logs."""

        state = "passed" if self.passed else f"FAILED ({len(self.violations)} violations)"
        return (
            f"Quote integrity {state}: {self.checked} quotes checked, "
            f"{self.unverifiable} unverifiable"
        )

    def to_dict(self) -> Dict[str, object]:
        """Return a JSON-serializable form for persistence on a run record."""

        return {
            "passed": self.passed,
            "checked": self.checked,
            "unverifiable": self.unverifiable,
            "violations": [violation.to_dict() for violation in self.violations],
        }


def usage_from_chunk(beat_id: str, chunk: Mapping[str, object]) -> QuoteUsage:
    """Build a QuoteUsage from the chunk dict a beat actually selected."""

    return QuoteUsage(
        beat_id=beat_id,
        chunk_id=str(chunk.get("chunk_id", "")),
        text=str(chunk.get("text", "")),
        span=span_from_chunk(chunk),
    )


def check_quote_integrity(usages: Iterable[QuoteUsage]) -> IntegrityReport:
    """Validate that no two quotations in a play draw on the same source words.

    Quotes are compared against every earlier quote from the same source line;
    lines are short, so this stays close to linear in practice rather than
    quadratic in the length of the play.

    Args:
        usages: Every quotation in the play, in the order it appears.

    Returns:
        An IntegrityReport listing each overlapping pair.
    """

    violations: List[IntegrityViolation] = []
    by_line: Dict[str, List[QuoteUsage]] = {}
    by_chunk_id: Dict[str, QuoteUsage] = {}
    checked = 0
    unverifiable = 0

    for usage in usages:
        # An exact repeat is caught by id even when provenance is missing, which
        # is the one reuse an unverifiable chunk can still be held to.
        if usage.chunk_id:
            previous = by_chunk_id.get(usage.chunk_id)
            if previous is not None:
                violations.append(
                    IntegrityViolation(
                        kind="chunk_repeat",
                        first=previous,
                        second=usage,
                        line_id=usage.span.line_id if usage.span else "",
                    )
                )
            else:
                by_chunk_id[usage.chunk_id] = usage

        if usage.span is None:
            unverifiable += 1
            logger.warning(
                "Cannot verify quote integrity for %s: no source span on chunk %s",
                usage.beat_id, usage.chunk_id or "<unidentified>",
            )
            continue

        checked += 1
        earlier = by_line.setdefault(usage.span.line_id, [])
        for other in earlier:
            assert other.span is not None  # only spanned usages are stored here
            shared = usage.span.overlapping_indices(other.span)
            if shared:
                violations.append(
                    IntegrityViolation(
                        kind="span_overlap",
                        first=other,
                        second=usage,
                        line_id=usage.span.line_id,
                        shared_word_indices=shared,
                    )
                )
        earlier.append(usage)

    report = IntegrityReport(
        checked=checked,
        unverifiable=unverifiable,
        violations=tuple(violations),
    )
    if report.passed:
        logger.info(report.describe())
    else:
        logger.error(report.describe())
        for violation in report.violations:
            logger.error("Quote integrity violation: %s", violation.describe())
    return report


def check_used_chunks(
    used_chunks: Sequence[Tuple[str, Mapping[str, object]]],
) -> IntegrityReport:
    """Validate a play given the (beat_id, chunk) pairs it selected.

    The convenience entry point for the generation path, which holds the chunk
    dicts already.  Validating an exported play instead means resolving its
    stored chunk ids back to chunks first, then calling
    ``check_quote_integrity``.
    """

    return check_quote_integrity(
        usage_from_chunk(beat_id, chunk) for beat_id, chunk in used_chunks
    )
