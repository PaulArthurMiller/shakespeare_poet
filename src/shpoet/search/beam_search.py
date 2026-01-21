"""Beam search implementation with checkpoints and rollback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from shpoet.common.types import GuidanceProfile
from shpoet.micro.reuse_lock import ReuseLock
from shpoet.micro.transition_engine import TransitionEngine
from shpoet.scoring.scoring_engine import ScoringEngine
from shpoet.search.avoid_memory import AvoidMemory
from shpoet.search.checkpoint import BeamState, CheckpointManager
from shpoet.search.rollback import RollbackManager


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """Result bundle for beam search."""

    best_path: List[str]
    best_score: float
    checkpoints_used: int


class BeamSearch:
    """Beam search controller for constrained sequence generation."""

    def __init__(self, chunks: List[Dict[str, object]]) -> None:
        """Initialize the beam search with the available chunks."""

        self._chunks = list(chunks)
        self._chunk_map = {str(chunk.get("chunk_id")): chunk for chunk in chunks}
        self._scoring = ScoringEngine()
        self._rollback = RollbackManager()

    def run(
        self,
        guidance: GuidanceProfile,
        beam_width: int,
        max_length: int,
        checkpoint_interval: int,
        avoid_memory: Optional[AvoidMemory] = None,
        initial_anchors: Optional[List[str]] = None,
    ) -> SearchResult:
        """Run beam search with checkpointing and rollback support."""

        if avoid_memory is None:
            avoid_memory = AvoidMemory()
        anchors_seed = list(initial_anchors or [])
        checkpoint_manager = CheckpointManager()

        beams = [BeamState(path_ids=[], score=0.0, anchors_seen=anchors_seed)]
        best_path: List[str] = []
        best_score = float("-inf")

        for depth in range(1, max_length + 1):
            candidates: List[BeamState] = []
            failed_paths: List[List[str]] = []

            for beam in beams:
                engine = self._build_transition_engine(beam.path_ids)
                previous_chunk_id = beam.path_ids[-1] if beam.path_ids else None
                result = engine.enumerate_candidates(
                    guidance=guidance,
                    anchors_seen=beam.anchors_seen,
                    previous_chunk_id=previous_chunk_id,
                )

                if not result.candidates:
                    failed_paths.append(list(beam.path_ids))
                    continue

                for candidate_id in result.candidates:
                    chunk = self._chunk_map.get(candidate_id)
                    if not chunk:
                        continue
                    scoring_result = self._scoring.score_candidate(chunk, guidance)
                    total_score = beam.score + scoring_result.score.total_score
                    total_score -= avoid_memory.penalty_for_path(beam.path_ids + [candidate_id])
                    updated_anchors = beam.anchors_seen + scoring_result.anchor_hits
                    candidates.append(
                        BeamState(
                            path_ids=beam.path_ids + [candidate_id],
                            score=total_score,
                            anchors_seen=updated_anchors,
                        )
                    )

            if not candidates:
                checkpoint = checkpoint_manager.latest()
                if checkpoint:
                    beams = self._rollback.rollback(checkpoint, avoid_memory, failed_paths)
                    continue
                logger.warning("Beam search terminated early at depth %s", depth)
                break

            candidates.sort(key=lambda beam_state: beam_state.score, reverse=True)
            beams = candidates[:beam_width]

            if beams:
                candidate_path = list(beams[0].path_ids)
                candidate_score = beams[0].score
                is_better_score = candidate_score > best_score
                is_longer_tie = candidate_score == best_score and len(candidate_path) > len(best_path)
                if is_better_score or is_longer_tie:
                    best_score = candidate_score
                    best_path = candidate_path

            if checkpoint_interval and depth % checkpoint_interval == 0:
                checkpoint_manager.save(depth, beams)

        logger.info("Beam search completed with best score %s", best_score)
        return SearchResult(
            best_path=best_path,
            best_score=best_score,
            checkpoints_used=checkpoint_manager.count(),
        )

    def _build_transition_engine(self, used_ids: List[str]) -> TransitionEngine:
        """Create a transition engine with a reuse lock seeded by used ids."""

        reuse_lock = ReuseLock()
        reuse_lock.mark_used_many(used_ids)
        return TransitionEngine(self._chunks, reuse_lock)
