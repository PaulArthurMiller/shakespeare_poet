"""Expander output shape tests."""

from shpoet.common.types import CharacterInput, SceneInput, UserPlayInput
from shpoet.expander.expander import expand_play_input


def _build_input() -> UserPlayInput:
    """Construct a minimal input payload for expander tests."""

    return UserPlayInput(
        title="The Ember Crown",
        overview="Ambition rises as a kingdom trembles under prophecy.",
        characters=[
            CharacterInput(
                name="Lyra",
                description="A cautious heir weighing rebellion and duty.",
                voice_traits=["measured", "doubtful"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A throne room at dawn.",
                summary="Lyra receives a troubling omen.",
                participants=["Lyra"],
            ),
            SceneInput(
                act=2,
                scene=1,
                setting="A garden of fading roses.",
                summary="Lyra debates a risky alliance.",
                participants=["Lyra"],
            ),
        ],
    )


def test_expander_outputs_have_anchors_and_beats() -> None:
    """Ensure expander returns anchors and beat obligations."""

    brief, plan = expand_play_input(_build_input())

    assert brief.plan_id == plan.plan_id
    assert plan.anchors.anchors
    assert plan.acts
    beat_obligations = [
        beat.obligations
        for act in plan.acts
        for scene in act.scenes
        for beat in scene.beats
    ]
    assert any(beat_obligations)
