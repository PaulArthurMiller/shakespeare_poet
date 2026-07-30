"""Guidance emission helpers for macro-level planning.

This module is the single junction box for the artistic constraints. Every
downstream consumer reads its knobs out of the GuidanceProfile emitted here:

    TransitionEngine  gates the meter constraint on constraints["meter_strictness"]
    ScoringEngine     weights its terms with priors["meter_preference"],
                      priors["length_preference"], priors["emotion_alignment"]

If a knob is not emitted here, the machinery it controls does nothing — the
constraint is skipped and the score term is multiplied by zero. That was the
state of the system before this module learned to emit them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from shpoet.common.types import AnchorRegistry, BeatObligation, BeatPlan, GuidanceProfile
from shpoet.config.settings import get_settings


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GuidanceKnobs:
    """Artistic constraint settings applied to every beat.

    Held as an explicit value object rather than read from global config inside
    the emitter, so that guidance stays a pure function of its inputs and tests
    can vary the knobs without touching the environment.
    """

    meter_strictness: float = 0.3
    meter_preference: float = 1.0
    length_preference: float = 0.1
    emotion_alignment: float = 0.0
    target_valence: float = 0.0

    @classmethod
    def from_settings(cls) -> "GuidanceKnobs":
        """Build the knob set from application configuration."""

        settings = get_settings()
        return cls(
            meter_strictness=settings.meter_strictness,
            meter_preference=settings.meter_preference,
            length_preference=settings.length_preference,
            emotion_alignment=settings.emotion_alignment,
            target_valence=settings.target_valence,
        )

    @classmethod
    def all_off(cls) -> "GuidanceKnobs":
        """Build a knob set that reproduces pre-M1 behaviour exactly.

        The control group for quality comparisons: meter is not enforced or
        scored, and emotion is ignored. Length keeps its historical 0.1 because
        ScoringEngine always applied that weight by default.
        """

        return cls(
            meter_strictness=0.0,
            meter_preference=0.0,
            length_preference=0.1,
            emotion_alignment=0.0,
            target_valence=0.0,
        )


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

    def __init__(
        self,
        anchor_registry: AnchorRegistry,
        knobs: Optional[GuidanceKnobs] = None,
    ) -> None:
        """Initialize the guidance emitter with anchor and knob configuration.

        Args:
            anchor_registry: Anchor plan for the play being generated.
            knobs: Artistic constraint settings. Defaults to the configured
                values; pass an explicit set to override, e.g. GuidanceKnobs.all_off()
                to reproduce pre-M1 behaviour for a control run.
        """

        self._anchor_registry = anchor_registry
        self._knobs = knobs if knobs is not None else GuidanceKnobs.from_settings()

    def guidance_for_beat(self, beat: BeatPlan) -> GuidanceProfile:
        """Emit a guidance profile for a specific beat plan."""

        anchor_info = _collect_obligation_anchors(beat.obligations)
        required = anchor_info["required"]
        desired = anchor_info["desired"]
        anchor_targets = _merge_anchor_targets(required, desired)

        constraints = {
            "required_anchor_count": float(len(required)),
            "desired_anchor_count": float(len(desired)),
            # Read by TransitionEngine; at 0.0 the meter constraint is skipped.
            "meter_strictness": self._knobs.meter_strictness,
        }

        # Priors are the scoring layer's term weights. Anchor presence is derived
        # per beat from its obligations; the rest are configured knobs.
        priors = {
            "anchor_presence": 1.0 + 0.2 * len(required) + 0.1 * len(desired),
            "meter_preference": self._knobs.meter_preference,
            "length_preference": self._knobs.length_preference,
            "emotion_alignment": self._knobs.emotion_alignment,
            "target_valence": self._knobs.target_valence,
        }
        if self._anchor_registry.primary_anchor:
            priors["primary_anchor_weight"] = 0.5

        guidance = GuidanceProfile(
            beat_id=beat.beat_id,
            anchor_targets=anchor_targets,
            constraints=constraints,
            priors=priors,
        )
        logger.info(
            "Guidance emitted for beat %s (meter_strictness=%.2f meter_preference=%.2f "
            "length_preference=%.2f emotion_alignment=%.2f)",
            beat.beat_id,
            self._knobs.meter_strictness,
            self._knobs.meter_preference,
            self._knobs.length_preference,
            self._knobs.emotion_alignment,
        )
        return guidance
