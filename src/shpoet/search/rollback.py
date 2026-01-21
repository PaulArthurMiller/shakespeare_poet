"""Rollback helpers for beam search."""

from __future__ import annotations

import logging
from typing import Iterable, List

from shpoet.search.avoid_memory import AvoidMemory
from shpoet.search.checkpoint import BeamState, Checkpoint


logger = logging.getLogger(__name__)


class RollbackManager:
    """Manage rollback behavior for beam search."""

    def rollback(
        self,
        checkpoint: Checkpoint,
        avoid_memory: AvoidMemory,
        failed_paths: Iterable[Iterable[str]],
    ) -> List[BeamState]:
        """Rollback to a checkpoint and register failed paths for avoidance."""

        for path in failed_paths:
            avoid_memory.register_avoid(path)
        logger.warning("Rollback triggered at depth %s", checkpoint.depth)
        return list(checkpoint.beams)
