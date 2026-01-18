"""Signature helpers for deterministic state hashing."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict

from shpoet.common.types import StateBundle


def _stable_json(payload: Dict[str, Any]) -> str:
    """Serialize a payload into a stable JSON string for hashing."""

    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash_payload(payload: Dict[str, Any]) -> str:
    """Return a SHA-256 hex digest for the provided payload."""

    stable_json = _stable_json(payload)
    return hashlib.sha256(stable_json.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class StateSignature:
    """Signature representing a canonical runtime state snapshot."""

    signature: str

    @staticmethod
    def from_state(state: StateBundle) -> "StateSignature":
        """Create a deterministic signature from a StateBundle."""

        payload = {
            "act": state.act,
            "scene": state.scene,
            "beat_id": state.beat_id,
            "speaker": state.speaker,
            "characters_present": sorted(state.characters_present),
            "anchors_seen": sorted(state.anchors_seen),
        }
        return StateSignature(signature=_hash_payload(payload))


@dataclass(frozen=True)
class TailSignature:
    """Signature representing a tail of generated content."""

    signature: str

    @staticmethod
    def from_tail(tail_tokens: list[str]) -> "TailSignature":
        """Create a deterministic signature for a list of tail tokens."""

        payload = {"tail_tokens": tail_tokens}
        return TailSignature(signature=_hash_payload(payload))


@dataclass(frozen=True)
class FailureSignature:
    """Signature representing a deterministic failure state for avoidance."""

    signature: str

    @staticmethod
    def from_failure(reason: str, state: StateBundle) -> "FailureSignature":
        """Create a deterministic signature from a failure reason and state."""

        payload = {
            "reason": reason,
            "state_signature": StateSignature.from_state(state).signature,
        }
        return FailureSignature(signature=_hash_payload(payload))
