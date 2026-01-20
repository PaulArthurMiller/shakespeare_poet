"""Tests for macro guidance and state transitions."""

from __future__ import annotations

import pytest

from shpoet.common.types import CharacterInput, SceneInput, UserPlayInput
from shpoet.expander.expander import expand_play_input
from shpoet.macro.guidance import GuidanceEmitter
from shpoet.macro.macro_graph import MacroGraph
from shpoet.macro.state_manager import StateManager


def _build_input() -> UserPlayInput:
    """Construct a minimal input payload for macro tests."""

    return UserPlayInput(
        title="Ashes of the Crown",
        overview="A restless heir confronts fate and fire.",
        characters=[
            CharacterInput(
                name="Selene",
                description="An heir bound to prophecy and flame.",
                voice_traits=["measured", "haunted"],
            )
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A dim hall with guttering torches.",
                summary="Selene hears a warning and feels the first pull of doom.",
                participants=["Selene"],
            ),
            SceneInput(
                act=2,
                scene=1,
                setting="A ruined chapel at dusk.",
                summary="Selene debates whether to embrace the fire within.",
                participants=["Selene"],
            ),
        ],
    )


def test_macro_graph_orders_beats() -> None:
    """Ensure macro graph orders beats and provides next-beat lookups."""

    _, plan = expand_play_input(_build_input())
    graph = MacroGraph.from_play_plan(plan)

    first = graph.first_beat_id
    assert first is not None
    next_id = graph.next_beat(first)
    assert next_id is not None
    assert graph.is_next(first, next_id)


def test_state_manager_guarded_transitions() -> None:
    """Validate state manager enforces sequential beat transitions."""

    _, plan = expand_play_input(_build_input())
    graph = MacroGraph.from_play_plan(plan)
    manager = StateManager(graph)

    state = manager.initialize()
    next_id = graph.next_beat(state.beat_id)
    assert next_id is not None

    updated = manager.transition_to(next_id)
    assert updated.beat_id == next_id

    with pytest.raises(ValueError):
        manager.transition_to(state.beat_id)


def test_guidance_emits_anchor_targets() -> None:
    """Ensure guidance output reflects anchor obligations on beats."""

    _, plan = expand_play_input(_build_input())
    graph = MacroGraph.from_play_plan(plan)
    node = graph.get_node(graph.first_beat_id or "")
    beat = node.beat
    emitter = GuidanceEmitter(plan.anchors)

    guidance = emitter.guidance_for_beat(beat)

    required = [
        anchor
        for obligation in beat.obligations
        for anchor in obligation.required_anchors
    ]
    assert required
    for anchor in required:
        assert anchor in guidance.anchor_targets
    assert guidance.constraints["required_anchor_count"] == float(len(required))
