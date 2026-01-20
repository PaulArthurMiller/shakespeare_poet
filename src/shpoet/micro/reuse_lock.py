"""Global reuse lock to prevent chunk reuse."""

from __future__ import annotations

import logging
from typing import Iterable, Set


logger = logging.getLogger(__name__)


class ReuseLock:
    """Track globally used chunk identifiers to prevent reuse."""

    def __init__(self) -> None:
        """Initialize the reuse lock with an empty used set."""

        self._used: Set[str] = set()

    def mark_used(self, chunk_id: str) -> None:
        """Record a chunk identifier as used."""

        self._used.add(chunk_id)
        logger.debug("Chunk marked as used: %s", chunk_id)

    def mark_used_many(self, chunk_ids: Iterable[str]) -> None:
        """Record multiple chunk identifiers as used."""

        chunk_list = list(chunk_ids)
        for chunk_id in chunk_list:
            self._used.add(chunk_id)
        logger.debug("Marked %s chunks as used", len(chunk_list))

    def is_used(self, chunk_id: str) -> bool:
        """Return True if a chunk identifier has been used."""

        return chunk_id in self._used

    def reset(self) -> None:
        """Clear all tracked chunk identifiers."""

        self._used.clear()
        logger.info("Reuse lock reset")
