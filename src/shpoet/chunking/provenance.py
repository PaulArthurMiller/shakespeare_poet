"""Provenance helpers for chunk generation.

Provenance tracking is critical for:
1. Quote validation - independently verify any quote against source
2. Reuse prevention - track which words have been used via the quote map
3. Attribution - maintain full reference chain (play, act, scene, line, word indices)

The word_index field uses comma-separated indices representing which words
from the original line are included in this chunk. For example:
- "0,1,2,3,4" means words 0-4 (a 5-word phrase)
- "6,7,8,9" means words 6-9 (a 4-word phrase starting mid-line)
"""

from __future__ import annotations

from typing import Dict

from shpoet.ingest.canon_index import CanonicalLine


def build_provenance(line: CanonicalLine) -> Dict[str, object]:
    """Build provenance metadata for a full-line chunk.

    This function creates provenance for chunks that span the entire line.
    The word_index includes all words in the line.

    Args:
        line: The canonical line entry

    Returns:
        Dictionary with complete provenance metadata
    """
    return {
        "line_id": line.line_id,
        "play": line.play,
        "act": line.act,
        "scene": line.scene,
        "line_in_scene": line.line_in_scene,
        "word_index": line.word_index,  # All words: "0,1,2,..."
        "start_word_idx": 0,
        "end_word_idx": len(line.tokens) - 1 if line.tokens else 0,
        "source_line_text": line.raw_text,
        "source_line_token_count": len(line.tokens),
    }


def build_phrase_provenance(
    line: CanonicalLine,
    start_word_idx: int,
    end_word_idx: int,
) -> Dict[str, object]:
    """Build provenance metadata for a phrase chunk within a line.

    This function creates provenance for chunks that span a subset of words
    within a line. The word_index field contains only the indices of words
    included in this phrase.

    Args:
        line: The canonical line entry this phrase comes from
        start_word_idx: Starting word index (inclusive, 0-based)
        end_word_idx: Ending word index (inclusive, 0-based)

    Returns:
        Dictionary with complete provenance metadata including word range
    """
    # Build the word index string for just this phrase's words
    word_indices = list(range(start_word_idx, end_word_idx + 1))
    word_index_str = ",".join(str(idx) for idx in word_indices)

    return {
        "line_id": line.line_id,
        "play": line.play,
        "act": line.act,
        "scene": line.scene,
        "line_in_scene": line.line_in_scene,
        "word_index": word_index_str,
        "start_word_idx": start_word_idx,
        "end_word_idx": end_word_idx,
        "source_line_text": line.raw_text,
        "source_line_token_count": len(line.tokens),
    }


def validate_provenance(provenance: Dict[str, object]) -> bool:
    """Validate that provenance metadata is complete and consistent.

    Used to verify chunks have proper attribution for the quote map
    and validation systems.

    Args:
        provenance: Dictionary with provenance fields

    Returns:
        True if provenance is valid, False otherwise
    """
    required_fields = [
        "line_id", "play", "act", "scene", "line_in_scene", "word_index"
    ]

    # Check all required fields exist and are non-empty
    for field in required_fields:
        if field not in provenance:
            return False
        if provenance[field] is None:
            return False
        if isinstance(provenance[field], str) and not provenance[field]:
            return False

    # Validate word_index format (comma-separated integers)
    word_index = str(provenance["word_index"])
    if word_index:
        try:
            indices = [int(x) for x in word_index.split(",")]
            # Indices should be sequential
            for i in range(1, len(indices)):
                if indices[i] != indices[i-1] + 1:
                    return False
        except ValueError:
            return False

    return True


def provenance_to_reference_string(provenance: Dict[str, object]) -> str:
    """Convert provenance to a human-readable reference string.

    Useful for logging, debugging, and displaying quote sources.

    Args:
        provenance: Dictionary with provenance fields

    Returns:
        Reference string like "Hamlet, Act 3, Scene 1, Line 56, Words 0-9"
    """
    play = provenance.get("play", "Unknown")
    act = provenance.get("act", "?")
    scene = provenance.get("scene", "?")
    line = provenance.get("line_in_scene", "?")
    word_index = provenance.get("word_index", "")

    # Parse word range from word_index
    if word_index:
        indices = [int(x) for x in str(word_index).split(",")]
        if len(indices) == 1:
            word_range = f"Word {indices[0]}"
        else:
            word_range = f"Words {indices[0]}-{indices[-1]}"
    else:
        word_range = "All words"

    return f"{play}, Act {act}, Scene {scene}, Line {line}, {word_range}"
