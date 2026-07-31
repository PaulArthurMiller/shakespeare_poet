"""A single generated play, normalized into the shape the metrics read.

Metrics need three things that live in three different places: the plan's
obligations (what the beat was supposed to do), the chunks actually selected
(what it did, and with which source words and Tier-2 features), and the search
telemetry (how hard it was). A live run holds all three; an exported play holds
only ids and text.

``PlayRun`` is the common shape both produce, so ``metrics.py`` never has to
know which it was handed -- and, just as importantly, so a metric can say
*unmeasured* rather than quietly returning zero when a source is absent. That
distinction is the whole point: this codebase's characteristic failure is a
missing field becoming a ``0.0`` that reads as a real measurement.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Optional

from shpoet.api.services import BeatSearchStats, GeneratedPlay
from shpoet.common.types import PlayPlan
from shpoet.macro.guidance import GuidanceKnobs
from shpoet.validation.chunk_resolver import ChunkResolver, iter_play_quotes
from shpoet.validation.quote_integrity import (
    IntegrityReport,
    QuoteUsage,
    check_quote_integrity,
    check_used_chunks,
    usage_from_chunk,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BeatRun:
    """One beat of a generated play, with everything needed to score it."""

    beat_id: str
    act: int
    scene: int
    required_anchors: List[str] = field(default_factory=list)
    desired_anchors: List[str] = field(default_factory=list)
    lines: List[str] = field(default_factory=list)
    # The chunk dicts behind those lines. Empty when ids could not be resolved,
    # which is not the same as a beat that produced nothing.
    chunks: List[Dict[str, object]] = field(default_factory=list)
    stats: Optional[BeatSearchStats] = None

    @property
    def has_obligations(self) -> bool:
        """True when the plan asked this beat to hit any anchors."""

        return bool(self.required_anchors or self.desired_anchors)


@dataclass(frozen=True)
class PlayRun:
    """A generated play plus the context needed to judge it."""

    plan_id: str
    title: str
    beats: List[BeatRun]
    integrity: IntegrityReport
    # None when the run's knob settings are not known (an old exported play).
    knobs: Optional[GuidanceKnobs] = None
    config: Dict[str, object] = field(default_factory=dict)
    # True when chunk provenance came from the plan's own selections rather than
    # being resolved after the fact; resolution can be partial.
    chunks_are_authoritative: bool = True

    @property
    def all_chunks(self) -> List[Dict[str, object]]:
        """Every chunk the play quoted, in play order."""

        return [chunk for beat in self.beats for chunk in beat.chunks]

    @property
    def line_count(self) -> int:
        """Total lines of verse produced."""

        return sum(len(beat.lines) for beat in self.beats)


def _obligations_by_beat(plan: PlayPlan) -> Dict[str, Dict[str, List[str]]]:
    """Flatten a plan's per-beat anchor obligations into a lookup by beat id."""

    obligations: Dict[str, Dict[str, List[str]]] = {}
    for act in plan.acts:
        for scene in act.scenes:
            for beat in scene.beats:
                required: List[str] = []
                desired: List[str] = []
                for obligation in beat.obligations:
                    required.extend(obligation.required_anchors)
                    desired.extend(obligation.desired_anchors)
                obligations[beat.beat_id] = {"required": required, "desired": desired}
    return obligations


def _beat_locations(plan: PlayPlan) -> Dict[str, tuple]:
    """Map each beat id to its (act, scene) position in the plan."""

    return {
        beat.beat_id: (act.act, scene.scene)
        for act in plan.acts
        for scene in act.scenes
        for beat in scene.beats
    }


def play_run_from_generation(
    plan: PlayPlan,
    generated: GeneratedPlay,
    knobs: Optional[GuidanceKnobs] = None,
    config: Optional[Mapping[str, object]] = None,
) -> PlayRun:
    """Build a PlayRun from a run this process just performed.

    The complete case: the chunks are the ones the search selected, so
    provenance and Tier-2 metadata are exactly what scoring saw.
    """

    obligations = _obligations_by_beat(plan)
    locations = _beat_locations(plan)
    stats_by_beat = {stats.beat_id: stats for stats in generated.beat_stats}

    chunks_by_beat: Dict[str, List[Dict[str, object]]] = {}
    for beat_id, chunk in generated.used_chunks:
        chunks_by_beat.setdefault(beat_id, []).append(chunk)

    beats: List[BeatRun] = []
    for beat_output in generated.beat_outputs:
        beat_id = beat_output.beat_id
        act, scene = locations.get(beat_id, (0, 0))
        anchors = obligations.get(beat_id, {"required": [], "desired": []})
        beats.append(
            BeatRun(
                beat_id=beat_id,
                act=act,
                scene=scene,
                required_anchors=list(anchors["required"]),
                desired_anchors=list(anchors["desired"]),
                lines=list(beat_output.lines),
                chunks=list(chunks_by_beat.get(beat_id, [])),
                stats=stats_by_beat.get(beat_id),
            )
        )

    return PlayRun(
        plan_id=plan.plan_id,
        title=plan.title,
        beats=beats,
        integrity=generated.quote_integrity,
        knobs=knobs,
        config=dict(config or {}),
        chunks_are_authoritative=True,
    )


def play_run_from_export(
    play_json: Mapping[str, object],
    resolver: ChunkResolver,
    plan: Optional[PlayPlan] = None,
) -> PlayRun:
    """Build a PlayRun from an exported play in ``data/output/``.

    The partial case, and the caller should know which parts are partial:

    * Chunks are resolved from ids, so an id the resolver cannot find yields no
      chunk. Quote integrity counts those as unverifiable rather than clean.
    * Anchor coverage needs the plan's obligations, which the export does not
      carry. Without ``plan`` the beats report no obligations and coverage comes
      back unmeasured.
    * Tier-2 metrics depend on the resolver: the JSONL backend does not carry
      ``iambic_score`` or ``syllable_count`` at all.
    """

    # Resolve once and reuse: the integrity check and the per-beat chunk lists
    # want the same chunks, and a Chroma-backed resolver pays a lookup per call.
    quotes = iter_play_quotes(play_json)
    resolved = resolver.resolve([chunk_id for _, chunk_id, _ in quotes])

    usages: List[QuoteUsage] = []
    for beat_id, chunk_id, exported_text in quotes:
        chunk = resolved.get(chunk_id)
        if chunk is None:
            # No span means unverifiable, not clean. Keeping the usage keeps it
            # in the denominator instead of silently shrinking the check.
            usages.append(
                QuoteUsage(beat_id=beat_id, chunk_id=chunk_id, text=exported_text, span=None)
            )
            continue
        usages.append(usage_from_chunk(beat_id, chunk))

    quotes_by_beat: Dict[str, List[str]] = {}
    obligations = _obligations_by_beat(plan) if plan is not None else {}

    beats: List[BeatRun] = []
    for act_payload in play_json.get("acts") or []:
        if not isinstance(act_payload, Mapping):
            continue
        act_number = int(act_payload.get("act", 0) or 0)
        for scene_payload in act_payload.get("scenes") or []:
            if not isinstance(scene_payload, Mapping):
                continue
            scene_number = int(scene_payload.get("scene", 0) or 0)
            for beat_payload in scene_payload.get("beats") or []:
                if not isinstance(beat_payload, Mapping):
                    continue
                beat_id = str(beat_payload.get("beat_id", ""))
                chunk_ids = [str(value) for value in beat_payload.get("line_ids") or []]
                quotes_by_beat[beat_id] = chunk_ids
                anchors = obligations.get(beat_id, {"required": [], "desired": []})
                beats.append(
                    BeatRun(
                        beat_id=beat_id,
                        act=act_number,
                        scene=scene_number,
                        required_anchors=list(anchors["required"]),
                        desired_anchors=list(anchors["desired"]),
                        lines=[str(line) for line in beat_payload.get("lines") or []],
                        chunks=[
                            resolved[chunk_id]
                            for chunk_id in chunk_ids
                            if chunk_id in resolved
                        ],
                        stats=None,
                    )
                )

    unresolved = sum(
        1
        for chunk_ids in quotes_by_beat.values()
        for chunk_id in chunk_ids
        if chunk_id not in resolved
    )
    if unresolved:
        logger.warning(
            "%d of this play's chunk ids did not resolve; metrics computed from "
            "chunk metadata will be short by that many quotes",
            unresolved,
        )

    return PlayRun(
        plan_id=str(play_json.get("plan_id", "")),
        title=str(play_json.get("title", "")),
        beats=beats,
        integrity=check_quote_integrity(usages),
        knobs=None,
        config={},
        chunks_are_authoritative=False,
    )


def integrity_for_run(run: PlayRun) -> IntegrityReport:
    """Recheck quote integrity from a run's chunks.

    Used by the seeded-regression path in the replay suite: a hand-built run can
    carry chunks that violate the rule without any stored report saying so.
    """

    return check_used_chunks(
        [(beat.beat_id, chunk) for beat in run.beats for chunk in beat.chunks]
    )
