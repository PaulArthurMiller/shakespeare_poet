"""Tests for deterministic transition engine behavior."""

from __future__ import annotations

from typing import Dict, List

from shpoet.common.types import GuidanceProfile
from shpoet.micro.reuse_lock import ReuseLock
from shpoet.micro.transition_engine import TransitionEngine


def _build_chunks() -> List[Dict[str, object]]:
    """Construct a tiny chunk list with Tier-1-style metadata."""

    return [
        {
            "chunk_id": "c1",
            "text": "And now the night begins",
            "starts_with_function_word": True,
            "ends_with_function_word": False,
            "first_token": "and",
            "last_token": "begins",
        },
        {
            "chunk_id": "c2",
            "text": "Night calls to night",
            "starts_with_function_word": False,
            "ends_with_function_word": False,
            "first_token": "night",
            "last_token": "night",
        },
        {
            "chunk_id": "c3",
            "text": "The crown remembers fire",
            "starts_with_function_word": True,
            "ends_with_function_word": False,
            "first_token": "the",
            "last_token": "fire",
        },
    ]


def _build_guidance(required_anchor_count: int) -> GuidanceProfile:
    """Construct a guidance profile with anchor targets for tests."""

    return GuidanceProfile(
        beat_id="act1_scene1_beat1",
        anchor_targets=["fire", "crown"],
        constraints={"required_anchor_count": float(required_anchor_count)},
        priors={},
    )


def test_transition_engine_enforces_reuse_and_anchor() -> None:
    """Ensure reuse lock and anchor constraint prune candidates."""

    reuse_lock = ReuseLock()
    reuse_lock.mark_used("c2")

    engine = TransitionEngine(_build_chunks(), reuse_lock)
    guidance = _build_guidance(required_anchor_count=1)

    result = engine.enumerate_candidates(guidance, anchors_seen=[], previous_chunk_id="c2")

    assert "c2" not in result.candidates
    assert "c2" in result.pruned_reasons.get("reuse", [])
    assert result.candidates == ["c3"]


def test_transition_engine_allows_when_no_required_anchor() -> None:
    """Verify candidates are allowed when no anchors are required."""

    reuse_lock = ReuseLock()
    engine = TransitionEngine(_build_chunks(), reuse_lock)
    guidance = _build_guidance(required_anchor_count=0)

    result = engine.enumerate_candidates(guidance, anchors_seen=[], previous_chunk_id=None)

    assert set(result.candidates) == {"c1", "c2", "c3"}
