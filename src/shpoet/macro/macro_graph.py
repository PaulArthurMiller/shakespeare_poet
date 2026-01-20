"""Macro graph representations for play plan navigation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from shpoet.common.types import BeatPlan, PlayPlan


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MacroNode:
    """Node representation for a beat within the macro graph."""

    beat_id: str
    act: int
    scene: int
    beat_index: int
    beat: BeatPlan


class MacroGraph:
    """Deterministic macro-level adjacency model for beats in a play plan."""

    def __init__(self, nodes: Dict[str, MacroNode], ordered_beats: List[str]) -> None:
        """Initialize the macro graph with nodes and deterministic ordering."""

        self._nodes = nodes
        self._ordered_beats = ordered_beats
        self._adjacency = self._build_adjacency(ordered_beats)
        logger.info("MacroGraph initialized with %s beats", len(self._ordered_beats))

    @classmethod
    def from_play_plan(cls, plan: PlayPlan) -> "MacroGraph":
        """Construct a MacroGraph from a PlayPlan with act/scene ordering."""

        ordered_beats: List[str] = []
        nodes: Dict[str, MacroNode] = {}
        for act in plan.acts:
            for scene in act.scenes:
                for beat_index, beat in enumerate(scene.beats, start=1):
                    node = MacroNode(
                        beat_id=beat.beat_id,
                        act=scene.act,
                        scene=scene.scene,
                        beat_index=beat_index,
                        beat=beat,
                    )
                    nodes[beat.beat_id] = node
                    ordered_beats.append(beat.beat_id)

        logger.info(
            "MacroGraph built from plan %s with %s nodes",
            plan.plan_id,
            len(nodes),
        )
        return cls(nodes=nodes, ordered_beats=ordered_beats)

    def _build_adjacency(self, ordered_beats: List[str]) -> Dict[str, List[str]]:
        """Build adjacency lists using sequential beat ordering."""

        adjacency: Dict[str, List[str]] = {}
        for index, beat_id in enumerate(ordered_beats):
            next_id = ordered_beats[index + 1] if index + 1 < len(ordered_beats) else None
            adjacency[beat_id] = [next_id] if next_id else []
        return adjacency

    @property
    def ordered_beats(self) -> List[str]:
        """Return the ordered beat identifiers for the plan."""

        return list(self._ordered_beats)

    @property
    def first_beat_id(self) -> Optional[str]:
        """Return the first beat identifier, if available."""

        return self._ordered_beats[0] if self._ordered_beats else None

    def get_node(self, beat_id: str) -> MacroNode:
        """Return the MacroNode for a beat identifier, raising if missing."""

        if beat_id not in self._nodes:
            logger.error("MacroGraph missing beat_id=%s", beat_id)
            raise KeyError(f"Unknown beat_id: {beat_id}")
        return self._nodes[beat_id]

    def next_beat(self, beat_id: str) -> Optional[str]:
        """Return the next beat identifier in sequence, if any."""

        if beat_id not in self._adjacency:
            logger.error("MacroGraph missing adjacency for beat_id=%s", beat_id)
            raise KeyError(f"Unknown beat_id: {beat_id}")
        return self._adjacency[beat_id][0] if self._adjacency[beat_id] else None

    def is_next(self, current_beat_id: str, candidate_beat_id: str) -> bool:
        """Check if a candidate beat is the immediate successor to the current beat."""

        next_id = self.next_beat(current_beat_id)
        return candidate_beat_id == next_id
