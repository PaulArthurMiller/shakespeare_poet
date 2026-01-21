"""Tests for scoring engine behavior."""

from __future__ import annotations

from shpoet.common.types import GuidanceProfile
from shpoet.scoring.scoring_engine import ScoringEngine


def test_scoring_engine_prefers_anchor_hits() -> None:
    """Ensure anchor hits add positive score contributions."""

    chunk_with_anchor = {
        "chunk_id": "c1",
        "text": "Love does not love",
        "tokens": ["Love", "does", "not", "love"],
        "token_count": 4,
    }
    chunk_without_anchor = {
        "chunk_id": "c2",
        "text": "The night is calm",
        "tokens": ["The", "night", "is", "calm"],
        "token_count": 4,
    }
    guidance = GuidanceProfile(
        beat_id="beat-1",
        anchor_targets=["love"],
        constraints={},
        priors={"anchor_presence": 2.0, "length_preference": 0.0},
    )

    engine = ScoringEngine()
    scored_anchor = engine.score_candidate(chunk_with_anchor, guidance)
    scored_no_anchor = engine.score_candidate(chunk_without_anchor, guidance)

    assert scored_anchor.score.total_score > scored_no_anchor.score.total_score
    assert scored_anchor.anchor_hits == ["love"]
