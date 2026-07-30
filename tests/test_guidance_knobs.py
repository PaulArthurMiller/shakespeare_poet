"""Tests that the artistic constraint knobs are emitted and actually take effect.

`macro/guidance.py` is the only place that decides which artistic constraints
turn on. Before M1 it emitted none of them, so the meter constraint was skipped
on every candidate and every artistic scoring term was multiplied by zero — with
no failing test anywhere to signal it.

These tests pin the whole chain: knob emitted -> constraint prunes -> score moves.
"""

from __future__ import annotations

import pytest

from shpoet.common.types import (
    AnchorPlan,
    AnchorRegistry,
    BeatObligation,
    BeatPlan,
    GuidanceProfile,
)
from shpoet.config.settings import get_settings, reset_settings
from shpoet.macro.guidance import GuidanceEmitter, GuidanceKnobs
from shpoet.micro.reuse_lock import ReuseLock
from shpoet.micro.transition_engine import TransitionEngine
from shpoet.scoring.scoring_engine import ScoringEngine


def _registry() -> AnchorRegistry:
    """Build a minimal anchor registry with a primary anchor."""

    return AnchorRegistry(
        primary_anchor="crown",
        anchors=[AnchorPlan(anchor_term="crown", related_terms=["orb"])],
    )


def _beat(beat_id: str = "act1_scene1_beat1") -> BeatPlan:
    """Build a beat carrying one required and one desired anchor."""

    return BeatPlan(
        beat_id=beat_id,
        objective="Confess a private doubt",
        rhetorical_mode="reflection",
        obligations=[
            BeatObligation(beat_id=beat_id, required_anchors=["crown"], desired_anchors=["orb"])
        ],
    )


class TestKnobsAreEmitted:
    """The guidance profile must carry every key its consumers read."""

    def test_all_consumer_keys_present(self) -> None:
        """Each knob read downstream must exist in the emitted profile."""

        guidance = GuidanceEmitter(_registry()).guidance_for_beat(_beat())

        # Read by TransitionEngine
        assert "meter_strictness" in guidance.constraints
        # Read by ScoringEngine
        for key in ("meter_preference", "length_preference", "emotion_alignment", "target_valence"):
            assert key in guidance.priors, f"ScoringEngine reads priors[{key!r}]"

    def test_defaults_enable_meter(self) -> None:
        """Shipped defaults must actually switch the meter machinery on."""

        guidance = GuidanceEmitter(_registry()).guidance_for_beat(_beat())

        assert guidance.constraints["meter_strictness"] > 0.0
        assert guidance.priors["meter_preference"] > 0.0

    def test_emotion_defaults_off(self) -> None:
        """Emotion stays off by default: corpus valence is 89% zeros."""

        guidance = GuidanceEmitter(_registry()).guidance_for_beat(_beat())

        assert guidance.priors["emotion_alignment"] == 0.0

    def test_anchor_priors_still_derived_per_beat(self) -> None:
        """Knob wiring must not flatten the per-beat anchor prior."""

        guidance = GuidanceEmitter(_registry()).guidance_for_beat(_beat())

        # 1.0 + 0.2 * one required + 0.1 * one desired
        assert guidance.priors["anchor_presence"] == pytest.approx(1.3)
        assert guidance.constraints["required_anchor_count"] == 1.0

    def test_explicit_knobs_override_settings(self) -> None:
        """An injected knob set must win over configuration."""

        knobs = GuidanceKnobs(meter_strictness=0.75, meter_preference=2.5)
        guidance = GuidanceEmitter(_registry(), knobs=knobs).guidance_for_beat(_beat())

        assert guidance.constraints["meter_strictness"] == 0.75
        assert guidance.priors["meter_preference"] == 2.5

    def test_all_off_reproduces_pre_m1_behaviour(self) -> None:
        """The control group must disable meter entirely."""

        guidance = GuidanceEmitter(_registry(), knobs=GuidanceKnobs.all_off()).guidance_for_beat(_beat())

        assert guidance.constraints["meter_strictness"] == 0.0
        assert guidance.priors["meter_preference"] == 0.0
        assert guidance.priors["emotion_alignment"] == 0.0

    def test_knobs_read_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment configuration must reach the emitted profile."""

        monkeypatch.setenv("SHPOET_METER_STRICTNESS", "0.9")
        monkeypatch.setenv("SHPOET_METER_PREFERENCE", "3.0")
        reset_settings()
        try:
            guidance = GuidanceEmitter(_registry()).guidance_for_beat(_beat())
            assert guidance.constraints["meter_strictness"] == 0.9
            assert guidance.priors["meter_preference"] == 3.0
        finally:
            reset_settings()

    def test_settings_expose_knob_defaults(self) -> None:
        """Settings must carry every knob the emitter needs."""

        settings = get_settings()
        for field in (
            "meter_strictness",
            "meter_preference",
            "length_preference",
            "emotion_alignment",
            "target_valence",
        ):
            assert hasattr(settings, field), f"settings.{field} missing"


class TestMeterConstraintActuallyPrunes:
    """The emitted knob must reach TransitionEngine and change its output."""

    @staticmethod
    def _chunks() -> list[dict]:
        """Two chunks whose stress patterns collide at the boundary."""

        return [
            {
                "chunk_id": "prev",
                "text": "and so the crown",
                "tokens": ["and", "so", "the", "crown"],
                "stress_pattern": "0101",
                "first_token": "and",
                "last_token": "crown",
            },
            {
                # Starts stressed right after a stressed ending -> score 0.3 clash.
                "chunk_id": "clashing",
                "text": "bright orb of night",
                "tokens": ["bright", "orb", "of", "night"],
                "stress_pattern": "1010",
                "first_token": "bright",
                "last_token": "night",
            },
            {
                # Starts unstressed -> perfect transition, score 1.0.
                "chunk_id": "flowing",
                "text": "the orb doth rise",
                "tokens": ["the", "orb", "doth", "rise"],
                "stress_pattern": "0101",
                "first_token": "the",
                "last_token": "rise",
            },
        ]

    def _enumerate(self, knobs: GuidanceKnobs) -> tuple[list[str], dict]:
        """Run candidate enumeration after 'prev' with the given knobs."""

        guidance = GuidanceEmitter(_registry(), knobs=knobs).guidance_for_beat(
            BeatPlan(beat_id="b", objective="o", rhetorical_mode="reflection")
        )
        chunks = self._chunks()
        lock = ReuseLock()
        lock.mark_used_many(chunk for chunk in chunks if chunk["chunk_id"] == "prev")
        engine = TransitionEngine(chunks, lock)
        result = engine.enumerate_candidates(
            guidance=guidance, anchors_seen=[], previous_chunk_id="prev"
        )
        return result.candidates, result.pruned_reasons

    def test_clashing_chunk_pruned_when_meter_on(self) -> None:
        """With meter enabled the colliding chunk must be rejected."""

        candidates, pruned = self._enumerate(GuidanceKnobs(meter_strictness=0.4))

        assert "clashing" not in candidates
        assert "flowing" in candidates
        assert "meter_clash" in pruned

    def test_clashing_chunk_survives_when_meter_off(self) -> None:
        """The control group must not prune on meter at all."""

        candidates, pruned = self._enumerate(GuidanceKnobs.all_off())

        assert "clashing" in candidates
        assert "meter_clash" not in pruned
        assert "weak_meter_flow" not in pruned

    def test_default_knobs_prune_clashes(self) -> None:
        """Shipped defaults must reject a same-stress collision."""

        candidates, _ = self._enumerate(GuidanceKnobs.from_settings())

        assert "clashing" not in candidates


class TestMeterScoringIsLive:
    """The emitted prior must reach ScoringEngine and move the total."""

    @staticmethod
    def _chunk() -> dict:
        """A ten-syllable, strongly iambic candidate."""

        return {
            "chunk_id": "c1",
            "text": "to be or not to be that is the question",
            "tokens": ["to", "be", "or", "not", "to", "be", "that", "is", "the", "question"],
            "token_count": 10,
            "syllable_count": 10,
            "iambic_score": 0.9,
            "emotion_valence": 0.0,
        }

    def _score(self, knobs: GuidanceKnobs):
        """Score the sample chunk under the given knobs."""

        guidance = GuidanceEmitter(_registry(), knobs=knobs).guidance_for_beat(
            BeatPlan(beat_id="b", objective="o", rhetorical_mode="reflection")
        )
        return ScoringEngine().score_candidate(self._chunk(), guidance)

    def test_meter_score_non_zero_by_default(self) -> None:
        """The headline regression: meter must stop being multiplied by zero."""

        result = self._score(GuidanceKnobs.from_settings())

        assert result.score.breakdown["meter_score"] > 0.0

    def test_meter_score_zero_in_control_group(self) -> None:
        """Knobs off must reproduce the old all-zero artistic scoring."""

        result = self._score(GuidanceKnobs.all_off())

        assert result.score.breakdown["meter_score"] == 0.0
        assert result.score.breakdown["emotion_score"] == 0.0

    def test_meter_preference_scales_the_term(self) -> None:
        """Doubling the weight must double the contribution."""

        single = self._score(GuidanceKnobs(meter_preference=1.0)).score.breakdown["meter_score"]
        double = self._score(GuidanceKnobs(meter_preference=2.0)).score.breakdown["meter_score"]

        assert double == pytest.approx(single * 2.0)

    def test_iambic_candidate_outscores_unmetrical_one(self) -> None:
        """With meter on, the better-scanning line must win."""

        guidance = GuidanceEmitter(_registry(), knobs=GuidanceKnobs.from_settings()).guidance_for_beat(
            BeatPlan(beat_id="b", objective="o", rhetorical_mode="reflection")
        )
        engine = ScoringEngine()

        iambic = engine.score_candidate(self._chunk(), guidance)
        clumsy_chunk = dict(self._chunk(), chunk_id="c2", iambic_score=0.1)
        clumsy = engine.score_candidate(clumsy_chunk, guidance)

        assert iambic.score.total_score > clumsy.score.total_score

    def test_length_preference_penalises_deviation(self) -> None:
        """A line far from pentameter must score below one at target length."""

        guidance = GuidanceEmitter(_registry(), knobs=GuidanceKnobs.from_settings()).guidance_for_beat(
            BeatPlan(beat_id="b", objective="o", rhetorical_mode="reflection")
        )
        engine = ScoringEngine()

        at_target = engine.score_candidate(self._chunk(), guidance)
        too_long = engine.score_candidate(
            dict(self._chunk(), chunk_id="c3", syllable_count=20), guidance
        )

        assert too_long.score.breakdown["length_score"] < at_target.score.breakdown["length_score"]
