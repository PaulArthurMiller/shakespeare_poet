"""Guidance emission helpers for macro-level planning."""

from __future__ import annotations

import logging
from typing import Dict, List

from shpoet.common.types import AnchorRegistry, BeatObligation, BeatPlan, GuidanceProfile


logger = logging.getLogger(__name__)


def _collect_obligation_anchors(obligations: List[BeatObligation]) -> Dict[str, List[str]]:
    """Collect required and desired anchors from beat obligations."""

    required: List[str] = []
    desired: List[str] = []
    for obligation in obligations:
        required.extend(obligation.required_anchors)
        desired.extend(obligation.desired_anchors)
    logger.debug("Collected %s required and %s desired anchors", len(required), len(desired))
    return {"required": required, "desired": desired}


def _merge_anchor_targets(required: List[str], desired: List[str]) -> List[str]:
    """Merge anchor targets while preserving required anchors first."""

    seen: set[str] = set()
    targets: List[str] = []
    for anchor in required + desired:
        if anchor in seen:
            continue
        seen.add(anchor)
        targets.append(anchor)
    return targets


class GuidanceEmitter:
    """Emit GuidanceProfile entries based on beat obligations and anchor registry."""

    def __init__(self, anchor_registry: AnchorRegistry) -> None:
        """Initialize the guidance emitter with anchor configuration."""

        self._anchor_registry = anchor_registry

    def guidance_for_beat(self, beat: BeatPlan) -> GuidanceProfile:
        """Emit a guidance profile for a specific beat plan."""

        anchor_info = _collect_obligation_anchors(beat.obligations)
        required = anchor_info["required"]
        desired = anchor_info["desired"]
        anchor_targets = _merge_anchor_targets(required, desired)

        constraints = {
            "required_anchor_count": float(len(required)),
            "desired_anchor_count": float(len(desired)),
        }

        # The anchor presence prior gives the scoring layer a simple numeric hint.
        priors = {
            "anchor_presence": 1.0 + 0.2 * len(required) + 0.1 * len(desired),
        }
        if self._anchor_registry.primary_anchor:
            priors["primary_anchor_weight"] = 0.5

        guidance = GuidanceProfile(
            beat_id=beat.beat_id,
            anchor_targets=anchor_targets,
            constraints=constraints,
            priors=priors,
        )
        logger.info("Guidance emitted for beat %s", beat.beat_id)
        return guidance
