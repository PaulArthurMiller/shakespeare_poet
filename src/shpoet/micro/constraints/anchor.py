"""Anchor constraints for enforcing motif coverage."""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple


logger = logging.getLogger(__name__)


class AnchorConstraint:
    """Constraint ensuring anchor targets appear when required."""

    def __init__(self, anchor_targets: List[str], required_count: int) -> None:
        """Initialize anchor constraint with target anchors and required count."""

        self._anchor_targets = [anchor.lower() for anchor in anchor_targets]
        self._required_count = required_count

    def evaluate(
        self,
        candidate_chunk: Dict[str, object],
        anchors_seen: List[str],
    ) -> Tuple[bool, str]:
        """Return whether a candidate satisfies anchor obligations."""

        if self._required_count <= 0:
            return True, "ok"

        if not self._anchor_targets:
            logger.warning("AnchorConstraint has required_count but no targets")
            return False, "missing_anchor_targets"

        if len(anchors_seen) >= self._required_count:
            return True, "ok"

        text = str(candidate_chunk.get("text", "")).lower()
        for anchor in self._anchor_targets:
            if anchor and anchor in text:
                return True, "ok"

        return False, "anchor_missing"
