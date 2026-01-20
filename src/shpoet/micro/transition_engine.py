"""Deterministic transition engine for enumerating next chunks."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from shpoet.common.types import GuidanceProfile
from shpoet.micro.constraints.anchor import AnchorConstraint
from shpoet.micro.constraints.grammar import GrammarConstraint
from shpoet.micro.reuse_lock import ReuseLock


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransitionResult:
    """Result bundle for candidate enumeration."""

    candidates: List[str]
    pruned_reasons: Dict[str, List[str]]


class TransitionEngine:
    """Enumerate candidate chunks with deterministic constraints."""

    def __init__(self, chunks: List[Dict[str, object]], reuse_lock: ReuseLock) -> None:
        """Initialize the engine with a chunk list and reuse lock."""

        self._chunks = list(chunks)
        self._reuse_lock = reuse_lock
        self._grammar = GrammarConstraint()

    def enumerate_candidates(
        self,
        guidance: GuidanceProfile,
        anchors_seen: List[str],
        previous_chunk_id: Optional[str] = None,
    ) -> TransitionResult:
        """Enumerate candidates that satisfy reuse, grammar, and anchor rules."""

        previous_chunk = None
        if previous_chunk_id:
            previous_chunk = self._find_chunk(previous_chunk_id)

        required_count = int(guidance.constraints.get("required_anchor_count", 0))
        anchor_constraint = AnchorConstraint(guidance.anchor_targets, required_count)

        candidates: List[str] = []
        pruned: Dict[str, List[str]] = {}

        for chunk in self._chunks:
            chunk_id = str(chunk.get("chunk_id", ""))
            if not chunk_id:
                continue

            if self._reuse_lock.is_used(chunk_id):
                pruned.setdefault("reuse", []).append(chunk_id)
                continue

            grammar_ok, grammar_reason = self._grammar.evaluate(previous_chunk, chunk)
            if not grammar_ok:
                pruned.setdefault(grammar_reason, []).append(chunk_id)
                continue

            anchor_ok, anchor_reason = anchor_constraint.evaluate(chunk, anchors_seen)
            if not anchor_ok:
                pruned.setdefault(anchor_reason, []).append(chunk_id)
                continue

            candidates.append(chunk_id)

        logger.info("Enumerated %s candidates", len(candidates))
        return TransitionResult(candidates=candidates, pruned_reasons=pruned)

    def _find_chunk(self, chunk_id: str) -> Dict[str, object]:
        """Locate a chunk dictionary by identifier."""

        for chunk in self._chunks:
            if chunk.get("chunk_id") == chunk_id:
                return chunk
        raise KeyError(f"Chunk not found: {chunk_id}")
