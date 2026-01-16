"""Signature stability tests."""

from shpoet.common.signatures import FailureSignature, StateSignature, TailSignature
from shpoet.common.types import StateBundle


def test_state_signature_stability() -> None:
    """Ensure identical state produces identical signatures."""

    state = StateBundle(
        act=1,
        scene=2,
        beat_id="act1_scene2_beat1",
        speaker="Hamlet",
        characters_present=["Hamlet", "Horatio"],
        anchors_seen=["orb", "world"],
    )

    signature_one = StateSignature.from_state(state).signature
    signature_two = StateSignature.from_state(state).signature

    assert signature_one == signature_two


def test_tail_signature_stability() -> None:
    """Ensure tail signatures are deterministic for identical token lists."""

    tokens = ["to", "be", "or", "not", "to", "be"]

    signature_one = TailSignature.from_tail(tokens).signature
    signature_two = TailSignature.from_tail(tokens).signature

    assert signature_one == signature_two


def test_failure_signature_stability() -> None:
    """Ensure failure signatures are deterministic for same reason and state."""

    state = StateBundle(
        act=2,
        scene=1,
        beat_id="act2_scene1_beat3",
        speaker="Ophelia",
        characters_present=["Ophelia"],
        anchors_seen=["moon"],
    )

    signature_one = FailureSignature.from_failure("dead_end", state).signature
    signature_two = FailureSignature.from_failure("dead_end", state).signature

    assert signature_one == signature_two
