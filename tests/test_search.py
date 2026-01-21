"""Tests for beam search behavior."""

from __future__ import annotations

from shpoet.common.types import GuidanceProfile
from shpoet.search.beam_search import BeamSearch


def test_beam_search_generates_without_reuse() -> None:
    """Verify beam search returns a path without reuse."""

    chunks = [
        {
            "chunk_id": "c1",
            "text": "Love is bright",
            "tokens": ["Love", "is", "bright"],
            "token_count": 3,
        },
        {
            "chunk_id": "c2",
            "text": "The night grows",
            "tokens": ["The", "night", "grows"],
            "token_count": 3,
        },
        {
            "chunk_id": "c3",
            "text": "Stars above us",
            "tokens": ["Stars", "above", "us"],
            "token_count": 3,
        },
    ]
    guidance = GuidanceProfile(
        beat_id="beat-1",
        anchor_targets=["love"],
        constraints={"required_anchor_count": 0.0},
        priors={"anchor_presence": 1.0, "length_preference": 0.0},
    )

    search = BeamSearch(chunks)
    result = search.run(
        guidance=guidance,
        beam_width=2,
        max_length=2,
        checkpoint_interval=1,
    )

    assert len(result.best_path) == 2
    assert len(set(result.best_path)) == len(result.best_path)
