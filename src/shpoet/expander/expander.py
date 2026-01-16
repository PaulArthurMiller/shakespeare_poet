"""Expander module for generating play design artifacts."""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from typing import Dict, List, Tuple

from shpoet.common.types import (
    ActPlan,
    BeatObligation,
    BeatPlan,
    PlayDesignBrief,
    PlayPlan,
    SceneInput,
    ScenePlan,
    UserPlayInput,
)
from shpoet.expander.anchor_planner import plan_anchors
from shpoet.expander.play_design_brief import render_brief
from shpoet.expander.validators import validate_design_brief, validate_play_plan


logger = logging.getLogger(__name__)


def _build_beat_plan(scene: SceneInput, index: int) -> BeatPlan:
    """Build a single beat plan entry for a scene."""

    beat_id = f"act{scene.act}_scene{scene.scene}_beat{index}"
    objective = f"Advance the scene intent: {scene.summary}"
    rhetorical_mode = "reflection"
    return BeatPlan(
        beat_id=beat_id,
        objective=objective,
        rhetorical_mode=rhetorical_mode,
        obligations=[],
    )


def _build_scene_plan(scene: SceneInput) -> ScenePlan:
    """Build a ScenePlan from a SceneInput entry."""

    beat = _build_beat_plan(scene, index=1)
    scene_id = f"act{scene.act}_scene{scene.scene}"
    return ScenePlan(scene_id=scene_id, act=scene.act, scene=scene.scene, beats=[beat])


def _build_act_plans(scenes: List[SceneInput]) -> List[ActPlan]:
    """Group scenes into act plans with a default single beat per scene."""

    scenes_by_act: Dict[int, List[SceneInput]] = defaultdict(list)
    for scene in scenes:
        scenes_by_act[scene.act].append(scene)

    act_plans: List[ActPlan] = []
    for act_number in sorted(scenes_by_act.keys()):
        scene_plans = [_build_scene_plan(scene) for scene in scenes_by_act[act_number]]
        act_plans.append(ActPlan(act=act_number, scenes=scene_plans))

    logger.info("Built %s act plans", len(act_plans))
    return act_plans


def _map_beats_by_act(acts: List[ActPlan]) -> Dict[int, List[str]]:
    """Map beat identifiers grouped by act for anchor placement planning."""

    beat_ids_by_act: Dict[int, List[str]] = defaultdict(list)
    for act in acts:
        for scene in act.scenes:
            for beat in scene.beats:
                beat_ids_by_act[act.act].append(beat.beat_id)
    return beat_ids_by_act


def _apply_beat_obligations(
    acts: List[ActPlan],
    obligations: Dict[str, BeatObligation],
) -> None:
    """Attach anchor obligations to beat plans in-place."""

    for act in acts:
        for scene in act.scenes:
            for beat in scene.beats:
                obligation = obligations.get(beat.beat_id)
                if obligation:
                    beat.obligations.append(obligation)


def expand_play_input(user_input: UserPlayInput) -> Tuple[PlayDesignBrief, PlayPlan]:
    """Expand user input into a design brief and structured play plan."""

    plan_id = str(uuid.uuid4())
    logger.info("Generating play plan %s", plan_id)

    act_plans = _build_act_plans(user_input.scenes)
    beat_ids_by_act = _map_beats_by_act(act_plans)
    anchors, obligations = plan_anchors(user_input, beat_ids_by_act)
    _apply_beat_obligations(act_plans, obligations)

    plan = PlayPlan(plan_id=plan_id, title=user_input.title, acts=act_plans, anchors=anchors)
    brief_markdown = render_brief(user_input, plan, anchors)
    brief = PlayDesignBrief(plan_id=plan_id, markdown=brief_markdown, anchors=anchors)

    validate_play_plan(plan)
    validate_design_brief(brief)

    logger.info("Plan %s validated with %s acts", plan_id, len(plan.acts))
    return brief, plan
