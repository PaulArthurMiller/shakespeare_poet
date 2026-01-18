"""Validation helpers for expander outputs."""

from __future__ import annotations

from typing import List

from shpoet.common.errors import PlanInvalidError
from shpoet.common.types import AnchorRegistry, BeatPlan, PlayDesignBrief, PlayPlan


def _ensure_non_empty_beats(beats: List[BeatPlan]) -> None:
    """Ensure every scene includes at least one beat with obligations."""

    for beat in beats:
        if not beat.obligations:
            raise PlanInvalidError(f"Beat {beat.beat_id} missing anchor obligations")


def validate_anchor_registry(anchors: AnchorRegistry) -> None:
    """Validate anchor registry is populated with at least one anchor."""

    if not anchors.anchors:
        raise PlanInvalidError("Anchor registry must contain at least one anchor")


def validate_play_plan(plan: PlayPlan) -> None:
    """Validate the core play plan structure and anchor obligations."""

    if not plan.acts:
        raise PlanInvalidError("Play plan must include acts")

    validate_anchor_registry(plan.anchors)

    for act in plan.acts:
        if not act.scenes:
            raise PlanInvalidError(f"Act {act.act} missing scenes")
        for scene in act.scenes:
            if not scene.beats:
                raise PlanInvalidError(f"Scene {scene.scene_id} missing beats")
            _ensure_non_empty_beats(scene.beats)


def validate_design_brief(brief: PlayDesignBrief) -> None:
    """Validate the design brief contains required content."""

    if not brief.markdown.strip():
        raise PlanInvalidError("Design brief markdown cannot be empty")
    validate_anchor_registry(brief.anchors)
