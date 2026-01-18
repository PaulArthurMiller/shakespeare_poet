"""Provenance helpers for chunk generation."""

from __future__ import annotations

from typing import Dict

from shpoet.ingest.canon_index import CanonicalLine


def build_provenance(line: CanonicalLine) -> Dict[str, object]:
    """Build provenance metadata for a chunk from a canonical line."""

    return {
        "line_id": line.line_id,
        "play": line.play,
        "act": line.act,
        "scene": line.scene,
        "line_in_scene": line.line_in_scene,
        "word_index": line.word_index,
    }
