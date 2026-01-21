"""Avoid-memory helper for penalizing failed search paths."""

from __future__ import annotations

import logging
from typing import Iterable, List, Set, Tuple


logger = logging.getLogger(__name__)


class AvoidMemory:
    """Track avoided paths to discourage repeated failures."""

    def __init__(self, penalty: float = 5.0) -> None:
        """Initialize the avoid memory with a fixed penalty."""

        self._penalty = penalty
        self._avoid_paths: Set[Tuple[str, ...]] = set()

    def register_avoid(self, path_ids: Iterable[str]) -> None:
        """Register a path to avoid in future searches."""

        path_tuple = tuple(path_ids)
        if not path_tuple:
            return
        self._avoid_paths.add(path_tuple)
        logger.info("Registered avoid path of length %s", len(path_tuple))

    def penalty_for_path(self, path_ids: Iterable[str]) -> float:
        """Return the penalty associated with a given path."""

        path_tuple = tuple(path_ids)
        if path_tuple in self._avoid_paths:
            logger.debug("Applied avoid penalty for path length %s", len(path_tuple))
            return self._penalty
        return 0.0

    def avoided_paths(self) -> List[Tuple[str, ...]]:
        """Return the list of avoided paths for reporting."""

        return list(self._avoid_paths)
