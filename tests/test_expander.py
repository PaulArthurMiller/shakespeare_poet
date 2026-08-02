"""Expander output shape tests."""

import pytest
from pydantic import ValidationError

from shpoet.common.errors import PlanInvalidError
from shpoet.common.types import (
    ActPlan,
    AnchorPlan,
    AnchorRegistry,
    BeatObligation,
    BeatPlan,
    CharacterInput,
    PlayPlan,
    SceneInput,
    ScenePlan,
    UserPlayInput,
)
from shpoet.expander.expander import expand_play_input
from shpoet.expander.validators import validate_play_plan


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


def _build_two_scene_act_input() -> UserPlayInput:
    """One act with two scenes -- the exact shape that used to raise PlanInvalidError.

    Regression case for the bug recorded in PROGRESS.md 2026-07-31:
    ``plan_anchors`` attached an obligation to only the first beat of each
    *act*, while the validator required every beat in the act to carry one,
    so the second scene's beat always failed validation.
    """

    return UserPlayInput(
        title="The Ashen Mirror",
        overview="A ruler confronts a mirror that remembers every broken oath.",
        characters=[
            CharacterInput(
                name="Cassia",
                description="A cautious sovereign testing prophecy against memory.",
                voice_traits=["measured", "wary"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A dim hall with a tarnished mirror.",
                summary="Cassia sees old vows shimmer across the glass.",
                participants=["Cassia"],
            ),
            SceneInput(
                act=1,
                scene=2,
                setting="The same hall, one candle fewer.",
                summary="Cassia weighs the crown against the oath that bought it.",
                participants=["Cassia"],
            ),
        ],
    )


def test_act_with_multiple_scenes_plans_successfully() -> None:
    """An act with more than one scene must plan without raising.

    Before the fix, expand_play_input raised PlanInvalidError for exactly
    this input: 'Beat act1_scene2_beat1 missing anchor obligations'.
    """

    brief, plan = expand_play_input(_build_two_scene_act_input())

    assert brief.plan_id == plan.plan_id
    assert len(plan.acts) == 1
    assert len(plan.acts[0].scenes) == 2

    for scene in plan.acts[0].scenes:
        assert any(beat.obligations for beat in scene.beats), (
            f"scene {scene.scene_id} has no obligation-bearing beat"
        )


def test_scene_beat_count_expands_to_multiple_beats() -> None:
    """SceneInput.beat_count controls how many beats a scene expands to."""

    user_input = UserPlayInput(
        title="The Ember Crown",
        overview="Ambition rises as a kingdom trembles under prophecy.",
        characters=[
            CharacterInput(
                name="Lyra",
                description="A cautious heir weighing rebellion and duty.",
                voice_traits=["measured"],
            ),
        ],
        scenes=[
            SceneInput(
                act=1,
                scene=1,
                setting="A throne room at dawn.",
                summary="Lyra receives a troubling omen.",
                participants=["Lyra"],
                beat_count=3,
            ),
        ],
    )

    _, plan = expand_play_input(user_input)
    scene = plan.acts[0].scenes[0]

    assert [beat.beat_id for beat in scene.beats] == [
        "act1_scene1_beat1",
        "act1_scene1_beat2",
        "act1_scene1_beat3",
    ]
    # Only the scene's first beat carries the anchor obligation; later beats
    # are free to develop the scene without repeating it into the reuse lock.
    assert scene.beats[0].obligations
    assert not scene.beats[1].obligations
    assert not scene.beats[2].obligations


def test_scene_input_rejects_beat_count_below_one() -> None:
    """beat_count has a floor of 1 -- a scene cannot expand to zero beats."""

    with pytest.raises(ValidationError):
        SceneInput(
            act=1,
            scene=1,
            setting="A throne room at dawn.",
            summary="Lyra receives a troubling omen.",
            participants=["Lyra"],
            beat_count=0,
        )


def test_scene_input_beat_count_defaults_to_one() -> None:
    """Existing callers that never set beat_count keep single-beat scenes."""

    scene = SceneInput(
        act=1,
        scene=1,
        setting="A throne room at dawn.",
        summary="Lyra receives a troubling omen.",
        participants=["Lyra"],
    )

    assert scene.beat_count == 1


def _minimal_plan_with_scene_beats(beats: list[BeatPlan]) -> PlayPlan:
    """Build a minimal PlayPlan around one scene's beats for validator tests."""

    return PlayPlan(
        plan_id="plan-1",
        title="Probe",
        acts=[ActPlan(act=1, scenes=[ScenePlan(scene_id="act1_scene1", act=1, scene=1, beats=beats)])],
        anchors=AnchorRegistry(
            primary_anchor="fate",
            anchors=[AnchorPlan(anchor_term="fate", related_terms=[], recurrence_rules=[], placements=[])],
        ),
    )


def test_validator_passes_when_only_one_beat_in_scene_has_obligations() -> None:
    """A scene with several beats is valid as long as one beat carries the obligation."""

    beats = [
        BeatPlan(
            beat_id="act1_scene1_beat1",
            objective="Advance the scene intent (beat 1 of 2): omen",
            rhetorical_mode="reflection",
            obligations=[
                BeatObligation(beat_id="act1_scene1_beat1", required_anchors=["fate"], desired_anchors=[])
            ],
        ),
        BeatPlan(
            beat_id="act1_scene1_beat2",
            objective="Advance the scene intent (beat 2 of 2): omen",
            rhetorical_mode="reflection",
            obligations=[],
        ),
    ]

    validate_play_plan(_minimal_plan_with_scene_beats(beats))


def test_validator_raises_when_no_beat_in_scene_has_obligations() -> None:
    """A scene where every beat lacks an obligation must fail validation."""

    beats = [
        BeatPlan(
            beat_id="act1_scene1_beat1",
            objective="Advance the scene intent: omen",
            rhetorical_mode="reflection",
            obligations=[],
        ),
    ]

    with pytest.raises(PlanInvalidError, match="act1_scene1"):
        validate_play_plan(_minimal_plan_with_scene_beats(beats))
