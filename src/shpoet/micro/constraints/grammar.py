"""Grammar-like adjacency constraints for candidate chunks."""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple


logger = logging.getLogger(__name__)


class GrammarConstraint:
    """Apply simple adjacency rules using Tier-1 features."""

    def evaluate(
        self,
        previous_chunk: Optional[Dict[str, object]],
        candidate_chunk: Dict[str, object],
    ) -> Tuple[bool, str]:
        """Return whether a candidate chunk passes adjacency checks."""

        if not candidate_chunk.get("text"):
            return False, "empty_text"

        if previous_chunk is None:
            return True, "ok"

        prev_end_function = bool(previous_chunk.get("ends_with_function_word"))
        cand_start_function = bool(candidate_chunk.get("starts_with_function_word"))
        if prev_end_function and cand_start_function:
            return False, "function_word_collision"

        prev_last = str(previous_chunk.get("last_token", "")).lower()
        cand_first = str(candidate_chunk.get("first_token", "")).lower()
        if prev_last and cand_first and prev_last == cand_first:
            return False, "repeated_edge_token"

        return True, "ok"
