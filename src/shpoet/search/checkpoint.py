"""Checkpoint helpers for beam search."""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass
from typing import List


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BeamState:
    """State snapshot for a single beam path."""

    path_ids: List[str]
    score: float
    anchors_seen: List[str]


@dataclass(frozen=True)
class Checkpoint:
    """Checkpoint snapshot storing beam states at a depth."""

    depth: int
    beams: List[BeamState]


class CheckpointManager:
    """Manage a stack of checkpoints during beam search."""

    def __init__(self) -> None:
        """Initialize the checkpoint manager with an empty stack."""

        self._checkpoints: List[Checkpoint] = []

    def save(self, depth: int, beams: List[BeamState]) -> None:
        """Save a checkpoint with deep-copied beam states."""

        snapshot = [
            BeamState(
                path_ids=copy.deepcopy(beam.path_ids),
                score=beam.score,
                anchors_seen=copy.deepcopy(beam.anchors_seen),
            )
            for beam in beams
        ]
        self._checkpoints.append(Checkpoint(depth=depth, beams=snapshot))
        logger.info("Checkpoint saved at depth %s", depth)

    def latest(self) -> Checkpoint | None:
        """Return the most recent checkpoint if available."""

        if not self._checkpoints:
            return None
        return self._checkpoints[-1]

    def count(self) -> int:
        """Return the number of checkpoints stored."""

        return len(self._checkpoints)
