"""Meter constraint for candidate chunk filtering.

Ensures adjacent chunks maintain proper iambic meter flow
when concatenated.
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

from shpoet.features.meter import check_meter_adjacency

logger = logging.getLogger(__name__)


class MeterConstraint:
    """Apply meter-based adjacency rules for chunk transitions.

    Checks that the stress pattern at chunk boundaries maintains
    good iambic flow (alternating stressed/unstressed syllables).
    """

    def __init__(self, strictness: float = 0.5) -> None:
        """Initialize the meter constraint.

        Args:
            strictness: 0.0 (lenient) to 1.0 (strict)
                       Controls how strictly iambic meter is enforced
        """
        self._strictness = strictness

    def evaluate(
        self,
        previous_chunk: Optional[Dict[str, object]],
        candidate_chunk: Dict[str, object],
    ) -> Tuple[bool, str]:
        """Check if a candidate chunk passes meter adjacency rules.

        Args:
            previous_chunk: The chunk before (None if first in sequence)
            candidate_chunk: The chunk being evaluated

        Returns:
            Tuple of (passed, reason) where reason explains failure
        """
        if previous_chunk is None:
            # First chunk - always accept
            return True, "ok"

        # Get stress patterns from metadata
        prev_pattern = str(previous_chunk.get("stress_pattern", ""))
        curr_pattern = str(candidate_chunk.get("stress_pattern", ""))

        if not prev_pattern or not curr_pattern:
            # Can't evaluate without patterns - accept
            return True, "ok"

        # Check meter adjacency
        acceptable, score = check_meter_adjacency(
            prev_pattern, curr_pattern, self._strictness
        )

        if acceptable:
            return True, "ok"

        # Determine specific failure reason
        if score < 0.4:
            return False, "meter_clash"
        return False, "weak_meter_flow"

    def set_strictness(self, strictness: float) -> None:
        """Update the strictness level.

        Args:
            strictness: 0.0 (lenient) to 1.0 (strict)
        """
        self._strictness = max(0.0, min(1.0, strictness))
