"""Macro-level state management with guarded transitions."""

from __future__ import annotations

import logging
from typing import Optional

from shpoet.common.types import StateBundle
from shpoet.macro.macro_graph import MacroGraph


logger = logging.getLogger(__name__)


class StateManager:
    """Manage canonical runtime state and enforce beat transitions."""

    def __init__(self, macro_graph: MacroGraph) -> None:
        """Initialize the state manager with a macro graph dependency."""

        self._macro_graph = macro_graph
        self._state: Optional[StateBundle] = None

    def initialize(self) -> StateBundle:
        """Initialize state at the first beat in the macro graph."""

        first_beat = self._macro_graph.first_beat_id
        if not first_beat:
            logger.error("Cannot initialize StateManager: MacroGraph is empty")
            raise ValueError("Cannot initialize state without beats")

        node = self._macro_graph.get_node(first_beat)
        self._state = StateBundle(
            act=node.act,
            scene=node.scene,
            beat_id=node.beat_id,
            speaker=None,
            characters_present=[],
            anchors_seen=[],
        )
        logger.info("Initialized state at beat %s", node.beat_id)
        return self._state

    def current_state(self) -> StateBundle:
        """Return the current state, initializing if needed."""

        if self._state is None:
            return self.initialize()
        return self._state

    def transition_to(self, beat_id: str) -> StateBundle:
        """Transition to the specified beat if it is the next legal step."""

        current = self.current_state()
        if not self._macro_graph.is_next(current.beat_id, beat_id):
            logger.error(
                "Illegal transition attempted from %s to %s",
                current.beat_id,
                beat_id,
            )
            raise ValueError(f"Illegal transition from {current.beat_id} to {beat_id}")

        node = self._macro_graph.get_node(beat_id)
        self._state = StateBundle(
            act=node.act,
            scene=node.scene,
            beat_id=node.beat_id,
            speaker=current.speaker,
            characters_present=list(current.characters_present),
            anchors_seen=list(current.anchors_seen),
        )
        logger.info("Transitioned to beat %s", node.beat_id)
        return self._state

    def advance(self) -> StateBundle:
        """Advance to the next beat in sequence, if available."""

        current = self.current_state()
        next_id = self._macro_graph.next_beat(current.beat_id)
        if not next_id:
            logger.error("No next beat available from %s", current.beat_id)
            raise ValueError("No next beat available")
        return self.transition_to(next_id)

    def mark_anchor_seen(self, anchor: str) -> StateBundle:
        """Record an anchor as seen in the current state."""

        current = self.current_state()
        updated = list(current.anchors_seen)
        if anchor not in updated:
            updated.append(anchor)
        self._state = StateBundle(
            act=current.act,
            scene=current.scene,
            beat_id=current.beat_id,
            speaker=current.speaker,
            characters_present=list(current.characters_present),
            anchors_seen=updated,
        )
        logger.debug("Anchor recorded: %s", anchor)
        return self._state
