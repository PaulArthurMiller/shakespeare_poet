"""Beam search implementation with checkpoints and rollback."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from shpoet.common.types import CriticReport, GuidanceProfile
from shpoet.llm.chooser import ChoiceOption, Chooser
from shpoet.llm.critic import Critic
from shpoet.micro.reuse_lock import ReuseLock
from shpoet.micro.transition_engine import TransitionEngine
from shpoet.scoring.scoring_engine import ScoringEngine
from shpoet.search.avoid_memory import AvoidMemory
from shpoet.search.checkpoint import BeamState, CheckpointManager
from shpoet.search.rollback import RollbackManager


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SearchResult:
    """Result bundle for beam search.

    The counters after ``critic_reports`` are search-health telemetry, not
    outputs. They exist because a beat can return a perfectly reasonable-looking
    path having thrashed through dozens of dead ends to get there, and the
    evaluation harness (BUILD-PLAN.md M3) needs to see that -- particularly as
    span-based reuse locking shrinks the effective corpus through later acts.
    They default to zero so callers that build a SearchResult by hand (tests,
    stubs) do not have to know about them.
    """

    best_path: List[str]
    best_score: float
    checkpoints_used: int
    critic_reports: List[CriticReport]
    # Beam expansions that produced no legal continuation at all.
    dead_ends: int = 0
    # Times the search fell back to a checkpoint because every beam died.
    rollbacks: int = 0
    # Deepest depth actually reached; below max_length means an early stop.
    depth_reached: int = 0
    # Depths abandoned with no checkpoint to roll back to.
    exhausted: bool = False


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
        critic: Optional[Critic] = None,
        chooser: Optional[Chooser] = None,
    ) -> SearchResult:
        """Run beam search with checkpointing and rollback support."""

        if avoid_memory is None:
            avoid_memory = AvoidMemory()
        anchors_seed = list(initial_anchors or [])
        checkpoint_manager = CheckpointManager()

        beams = [BeamState(path_ids=[], score=0.0, anchors_seen=anchors_seed)]
        best_path: List[str] = []
        best_score = float("-inf")
        critic_reports: List[CriticReport] = []
        dead_ends = 0
        rollbacks = 0
        depth_reached = 0
        exhausted = False

        for depth in range(1, max_length + 1):
            depth_reached = depth
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
                    dead_ends += 1
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
                    rollbacks += 1
                    beams = self._rollback.rollback(checkpoint, avoid_memory, failed_paths)
                    continue
                exhausted = True
                logger.warning("Beam search terminated early at depth %s", depth)
                break

            candidates.sort(key=lambda beam_state: beam_state.score, reverse=True)
            candidates = self._apply_chooser(candidates, guidance, depth, chooser)
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
                if critic and beams:
                    window_text = self._render_window_text(beams[0].path_ids)
                    report = critic.evaluate_window(
                        window_id=f"depth-{depth}",
                        guidance=guidance,
                        window_text=window_text,
                        anchors_seen=beams[0].anchors_seen,
                    )
                    critic_reports.append(report)

        logger.info(
            "Beam search completed with best score %s "
            "(depth=%d dead_ends=%d rollbacks=%d exhausted=%s)",
            best_score, depth_reached, dead_ends, rollbacks, exhausted,
        )
        return SearchResult(
            best_path=best_path,
            best_score=best_score,
            checkpoints_used=checkpoint_manager.count(),
            critic_reports=critic_reports,
            dead_ends=dead_ends,
            rollbacks=rollbacks,
            depth_reached=depth_reached,
            exhausted=exhausted,
        )

    def _build_transition_engine(self, used_ids: List[str]) -> TransitionEngine:
        """Create a transition engine with a reuse lock seeded by this beam's path.

        The lock is seeded with the chunk *dicts*, not the ids: it locks the
        source word spans those chunks occupy, so a beam cannot extend itself
        with a phrase cut from a line it has already quoted.
        """

        reuse_lock = ReuseLock()
        for chunk_id in used_ids:
            chunk = self._chunk_map.get(chunk_id)
            if chunk is None:
                # Should not happen -- paths are built from this pool -- but an
                # id with no chunk still has to stay locked.
                logger.warning("Path chunk %s not in pool; locking by id only", chunk_id)
                reuse_lock.mark_id_used(chunk_id)
                continue
            reuse_lock.mark_used(chunk)
        return TransitionEngine(self._chunks, reuse_lock)

    def _render_window_text(self, path_ids: List[str]) -> str:
        """Render a window of chunk text for critic evaluation."""

        lines = []
        for chunk_id in path_ids:
            chunk = self._chunk_map.get(chunk_id)
            if not chunk:
                continue
            text = str(chunk.get("text", "")).strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    def _apply_chooser(
        self,
        candidates: List[BeamState],
        guidance: GuidanceProfile,
        depth: int,
        chooser: Optional[Chooser],
    ) -> List[BeamState]:
        """Optionally reorder candidates using the chooser decision."""

        if not chooser or not candidates:
            return candidates

        options = [
            ChoiceOption(
                option_id=beam.path_ids[-1],
                score=beam.score,
                preview=self._chunk_preview(beam.path_ids[-1]),
            )
            for beam in candidates
            if beam.path_ids
        ]
        if not options:
            return candidates

        decision = chooser.choose(window_id=f"depth-{depth}", guidance=guidance, options=options)
        if not decision.chosen_id:
            return candidates

        chosen = [beam for beam in candidates if beam.path_ids and beam.path_ids[-1] == decision.chosen_id]
        remaining = [
            beam
            for beam in candidates
            if not beam.path_ids or beam.path_ids[-1] != decision.chosen_id
        ]
        return chosen + remaining

    def _chunk_preview(self, chunk_id: str) -> str:
        """Return a short preview of a chunk for chooser context."""

        chunk = self._chunk_map.get(chunk_id, {})
        text = str(chunk.get("text", "")).strip()
        return text[:120]
