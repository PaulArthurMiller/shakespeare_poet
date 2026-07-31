"""Tests for the evaluation harness: scorecard metrics and the replay suite.

The module under test exists because the previous replay suite always returned
``passed=True``.  So these tests are written to answer one question above all
others: *would this suite notice?*  Each metric is checked on a hand-built play
whose properties are known exactly, and the suite itself is handed a seeded
regression and required to fail on it.

The second theme is the distinction between *unmeasured* and *zero*.  Chunks
that came through the vector index carry ``iambic_score``; chunks read off the
processed JSONL files do not.  A mean of 0.0 in the second case would read as
catastrophically bad verse, so several tests pin the ``None`` instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

import pytest
from pytest import MonkeyPatch

from shpoet.api.models import GenerationConfig
from shpoet.api.services import BeatSearchStats, GeneratedBeat, GeneratedPlay
from shpoet.common.types import (
    ActPlan,
    AnchorPlan,
    AnchorRegistry,
    BeatObligation,
    BeatPlan,
    CharacterInput,
    CriticReport,
    PlayPlan,
    SceneInput,
    ScenePlan,
    UserPlayInput,
)
from shpoet.config.settings import reset_settings
from shpoet.learning.eval_store import (
    list_scorecards,
    load_scorecard_dict,
    run_signature,
    save_scorecard,
    scorecard_filename,
)
from shpoet.learning.metrics import (
    PENTAMETER_SYLLABLES,
    compute_anchor_coverage,
    compute_line_length,
    compute_meter_conformity,
    compute_pentameter_share,
    compute_scorecard,
    compute_search_health,
    compute_source_diversity,
)
from shpoet.learning.play_run import (
    BeatRun,
    PlayRun,
    play_run_from_export,
    play_run_from_generation,
)
from shpoet.learning.replay_suite import (
    ARM_KNOBS_OFF,
    ARM_KNOBS_ON,
    GenerationInputs,
    ReplayScenario,
    ScenarioThresholds,
    build_default_scenarios,
    evaluate_scorecard,
    main,
    run_replay_suite,
    run_scenario,
)
from shpoet.macro.guidance import GuidanceKnobs
from shpoet.micro.corpus_store import CorpusStore
from shpoet.scripts.build_corpus import build_corpus
from shpoet.scripts.build_index import main as build_all_indexes
from shpoet.validation.chunk_resolver import JsonlChunkResolver
from shpoet.validation.quote_integrity import IntegrityReport, check_used_chunks


def _chunk(
    chunk_id: str,
    text: str,
    line_id: str,
    start: int,
    end: int,
    **extra: object,
) -> Dict[str, object]:
    """Build a chunk dict with the provenance every chunker writes."""

    chunk: Dict[str, object] = {
        "chunk_id": chunk_id,
        "text": text,
        "tokens": text.split(),
        "token_count": len(text.split()),
        "line_id": line_id,
        "start_word_idx": start,
        "end_word_idx": end,
    }
    chunk.update(extra)
    return chunk


def _beat(
    beat_id: str,
    chunks: List[Dict[str, object]],
    required: List[str] | None = None,
    desired: List[str] | None = None,
    act: int = 1,
    stats: BeatSearchStats | None = None,
) -> BeatRun:
    """Build a BeatRun from chunks, deriving its lines from their text."""

    return BeatRun(
        beat_id=beat_id,
        act=act,
        scene=1,
        required_anchors=list(required or []),
        desired_anchors=list(desired or []),
        lines=[str(chunk["text"]) for chunk in chunks],
        chunks=chunks,
        stats=stats,
    )


def _run(beats: List[BeatRun]) -> PlayRun:
    """Build a PlayRun whose integrity report is computed from its own chunks."""

    return PlayRun(
        plan_id="plan-test",
        title="A Test Play",
        beats=beats,
        integrity=check_used_chunks(
            [(beat.beat_id, chunk) for beat in beats for chunk in beat.chunks]
        ),
    )


# ---------------------------------------------------------------------------
# Anchor coverage
# ---------------------------------------------------------------------------


def test_anchor_coverage_counts_only_anchors_present_in_the_beats_lines() -> None:
    """An anchor counts as met only when it appears in its own beat's lines."""

    beats = [
        _beat(
            "b1",
            [_chunk("c1", "the crown is heavy", "l1", 0, 3)],
            required=["crown"],
        ),
        _beat(
            "b2",
            [_chunk("c2", "a silent hall", "l2", 0, 2)],
            required=["oath"],
        ),
    ]

    coverage = compute_anchor_coverage(beats)

    assert coverage.required_total == 2
    assert coverage.required_met == 1
    assert coverage.required_coverage == pytest.approx(0.5)
    assert coverage.unmet_beats == ["b2"]


def test_anchor_in_a_different_beat_does_not_satisfy_the_obligation() -> None:
    """Anchors are placed per beat, so landing elsewhere is not credit.

    The plan places anchors deliberately. An anchor that turns up three scenes
    from where it was asked for has not done the job the plan gave it, and a
    play-level count would score that as a hit.
    """

    beats = [
        # "oath" appears here, but it was required of b2.
        _beat("b1", [_chunk("c1", "a broken oath", "l1", 0, 2)], required=["crown"]),
        _beat("b2", [_chunk("c2", "the crown alone", "l2", 0, 2)], required=["oath"]),
    ]

    coverage = compute_anchor_coverage(beats)

    assert coverage.required_met == 0
    assert sorted(coverage.unmet_beats) == ["b1", "b2"]


def test_anchor_coverage_is_none_when_the_plan_asked_for_nothing() -> None:
    """No obligations means unmeasured, not perfect.

    Returning 1.0 here would let a plan that carried no anchors at all report
    full coverage -- the exact shape of false confidence this harness exists to
    remove.
    """

    coverage = compute_anchor_coverage(
        [_beat("b1", [_chunk("c1", "some words here", "l1", 0, 2)])]
    )

    assert coverage.required_total == 0
    assert coverage.required_coverage is None


def test_anchor_coverage_uses_indexed_tokens_over_naive_splitting() -> None:
    """Tokens from the indexer keep contractions whole, so anchors still match."""

    chunk = _chunk("c1", "'Tis Neptune's oath, forsworn.", "l1", 0, 3)
    # The indexer's tokenizer strips the trailing punctuation this test cares about.
    chunk["tokens"] = ["'Tis", "Neptune's", "oath", "forsworn"]

    coverage = compute_anchor_coverage([_beat("b1", [chunk], required=["oath"])])

    assert coverage.required_met == 1


def test_anchor_coverage_is_broken_out_by_act() -> None:
    """Per-act tallies are what show an anchor failing only in later acts."""

    beats = [
        _beat("b1", [_chunk("c1", "the crown", "l1", 0, 1)], required=["crown"], act=1),
        _beat("b2", [_chunk("c2", "a quiet room", "l2", 0, 2)], required=["crown"], act=5),
    ]

    coverage = compute_anchor_coverage(beats)

    assert coverage.required_by_act == {"1": [1, 1], "5": [0, 1]}


# ---------------------------------------------------------------------------
# Meter and line length: unmeasured is not zero
# ---------------------------------------------------------------------------


def test_meter_conformity_averages_only_chunks_that_carry_a_score() -> None:
    """The mean covers the measured chunks; the rest are counted, not averaged."""

    chunks = [
        _chunk("c1", "one", "l1", 0, 0, iambic_score=0.8),
        _chunk("c2", "two", "l2", 0, 0, iambic_score=0.6),
        _chunk("c3", "three", "l3", 0, 0),  # no Tier-2 metadata
    ]

    distribution = compute_meter_conformity(chunks)

    assert distribution.measured == 2
    assert distribution.unmeasured == 1
    assert distribution.mean == pytest.approx(0.7)
    assert distribution.coverage == pytest.approx(2 / 3)


def test_meter_conformity_is_none_when_no_chunk_carries_a_score() -> None:
    """A run with no Tier-2 metadata reports unmeasured, never 0.0.

    This is the failure this codebase keeps producing: the JSONL corpus carries
    no ``iambic_score``, and a 0.0 mean would look like verse that does not scan
    at all rather than a measurement that never happened.
    """

    distribution = compute_meter_conformity(
        [_chunk("c1", "one", "l1", 0, 0), _chunk("c2", "two", "l2", 0, 0)]
    )

    assert distribution.mean is None
    assert distribution.measured == 0
    assert distribution.unmeasured == 2


def test_meter_conformity_keeps_a_genuine_zero_score() -> None:
    """A stored 0.0 is a measurement and must not be confused with absence."""

    distribution = compute_meter_conformity(
        [_chunk("c1", "one", "l1", 0, 0, iambic_score=0.0)]
    )

    assert distribution.measured == 1
    assert distribution.unmeasured == 0
    assert distribution.mean == pytest.approx(0.0)


def test_line_length_summarises_syllable_counts() -> None:
    """Line length reports the spread of syllables actually recorded."""

    chunks = [
        _chunk("c1", "a", "l1", 0, 0, syllable_count=10),
        _chunk("c2", "b", "l2", 0, 0, syllable_count=12),
        _chunk("c3", "c", "l3", 0, 0, syllable_count=8),
    ]

    distribution = compute_line_length(chunks)

    assert distribution.mean == pytest.approx(10.0)
    assert distribution.minimum == pytest.approx(8.0)
    assert distribution.maximum == pytest.approx(12.0)


def test_pentameter_share_counts_lines_within_tolerance() -> None:
    """Lines more than two syllables from ten fall outside the pentameter band."""

    chunks = [
        _chunk("c1", "a", "l1", 0, 0, syllable_count=PENTAMETER_SYLLABLES),
        _chunk("c2", "b", "l2", 0, 0, syllable_count=PENTAMETER_SYLLABLES + 2),
        _chunk("c3", "c", "l3", 0, 0, syllable_count=PENTAMETER_SYLLABLES + 5),
        _chunk("c4", "d", "l4", 0, 0, syllable_count=3),
    ]

    assert compute_pentameter_share(chunks) == pytest.approx(0.5)


def test_pentameter_share_is_none_without_syllable_data() -> None:
    """No syllable metadata means the question cannot be answered."""

    assert compute_pentameter_share([_chunk("c1", "a", "l1", 0, 0)]) is None


# ---------------------------------------------------------------------------
# Source diversity
# ---------------------------------------------------------------------------


def test_source_diversity_counts_distinct_plays_and_lines() -> None:
    """Diversity distinguishes a play that ranges widely from one that does not."""

    chunks = [
        _chunk("c1", "a", "ham_l1", 0, 0, play="Hamlet"),
        _chunk("c2", "b", "ham_l2", 0, 0, play="Hamlet"),
        _chunk("c3", "c", "lr_l1", 0, 0, play="King Lear"),
    ]

    diversity = compute_source_diversity(chunks)

    assert diversity.distinct_plays == 2
    assert diversity.distinct_source_lines == 3
    assert diversity.top_play_share == pytest.approx(2 / 3)


def test_source_diversity_reports_chunks_with_no_attribution() -> None:
    """A chunk with no ``play`` field is counted, not silently dropped."""

    diversity = compute_source_diversity(
        [_chunk("c1", "a", "l1", 0, 0, play="Hamlet"), _chunk("c2", "b", "l2", 0, 0)]
    )

    assert diversity.unattributed == 1
    assert diversity.distinct_plays == 1


# ---------------------------------------------------------------------------
# Search health
# ---------------------------------------------------------------------------


def _stats(beat_id: str, **overrides: object) -> BeatSearchStats:
    """Build a BeatSearchStats with sensible defaults for the fields not tested."""

    values: Dict[str, object] = {
        "beat_id": beat_id,
        "pool_size": 800,
        "lines_produced": 3,
        "dead_ends": 0,
        "rollbacks": 0,
        "checkpoints": 1,
        "depth_reached": 3,
        "exhausted": False,
        "relaxed_anchors": False,
        "critic_reports": [],
    }
    values.update(overrides)
    return BeatSearchStats(**values)  # type: ignore[arg-type]


def test_search_health_sums_dead_ends_and_rollbacks_across_beats() -> None:
    """Search strain is a property of the run, so it aggregates over beats."""

    beats = [
        _beat("b1", [], stats=_stats("b1", dead_ends=4, rollbacks=1)),
        _beat("b2", [], stats=_stats("b2", dead_ends=2, rollbacks=3)),
    ]

    health = compute_search_health(beats)

    assert health.dead_ends == 6
    assert health.rollbacks == 4
    assert health.measured is True


def test_search_health_flags_low_scoring_critic_reports() -> None:
    """A critic score at or below the flag threshold is counted as a flag."""

    reports = [
        CriticReport(window_id="w1", score=0.9, notes=[], recommendations={}),
        CriticReport(window_id="w2", score=0.2, notes=["weak"], recommendations={}),
        # The critic returns 0.0 for unparseable responses too, which also
        # deserves a human look.
        CriticReport(window_id="w3", score=0.0, notes=["Invalid JSON"], recommendations={}),
    ]
    beats = [_beat("b1", [], stats=_stats("b1", critic_reports=reports))]

    health = compute_search_health(beats)

    assert health.critic_calls == 3
    assert health.critic_flags == 2
    assert health.critic_mean_score == pytest.approx((0.9 + 0.2) / 3)


def test_search_health_reports_unmeasured_when_no_beat_carries_stats() -> None:
    """A play scored from an export has no telemetry, and says so."""

    health = compute_search_health([_beat("b1", [_chunk("c1", "a", "l1", 0, 0)])])

    assert health.measured is False
    assert health.dead_ends == 0


def test_search_health_counts_beats_that_had_to_drop_required_anchors() -> None:
    """Relaxed beats are the visible symptom of a pool too thin to satisfy the plan."""

    beats = [
        _beat("b1", [], stats=_stats("b1", relaxed_anchors=True)),
        _beat("b2", [], stats=_stats("b2", relaxed_anchors=False)),
    ]

    assert compute_search_health(beats).beats_relaxed_anchors == 1


# ---------------------------------------------------------------------------
# Scorecard assembly and persistence
# ---------------------------------------------------------------------------


def test_scorecard_reports_a_reused_span_as_an_integrity_failure() -> None:
    """A play that quotes the same source words twice fails, whatever its ids."""

    beats = [
        _beat("b1", [_chunk("c1", "the multitudinous seas", "l1", 0, 2)]),
        # A different chunk id over overlapping words on the same source line.
        _beat("b2", [_chunk("c1_p0", "multitudinous seas incarnadine", "l1", 1, 3)]),
    ]

    scorecard = compute_scorecard(_run(beats), label="reuse-case")

    assert scorecard.quote_integrity.passed is False
    assert scorecard.quote_integrity.violations == 1
    assert "l1" in scorecard.quote_integrity.examples[0]


def test_scorecard_passes_a_play_using_adjacent_but_distinct_spans() -> None:
    """Adjacency is not overlap: 0-3 and 4-7 on one line are different words."""

    beats = [
        _beat("b1", [_chunk("c1", "one two three four", "l1", 0, 3)]),
        _beat("b2", [_chunk("c2", "five six seven eight", "l1", 4, 7)]),
    ]

    scorecard = compute_scorecard(_run(beats), label="adjacent-case")

    assert scorecard.quote_integrity.passed is True
    assert scorecard.quote_integrity.violations == 0


def test_scorecard_round_trips_through_the_eval_directory(tmp_path: Path) -> None:
    """A stored scorecard reloads with its headline numbers intact."""

    beats = [
        _beat(
            "b1",
            [_chunk("c1", "the crown", "l1", 0, 1, play="Hamlet", iambic_score=0.9)],
            required=["crown"],
        )
    ]
    scorecard = compute_scorecard(_run(beats), label="round-trip")

    path = save_scorecard(scorecard, tmp_path)
    reloaded = load_scorecard_dict(path)

    assert reloaded["label"] == "round-trip"
    assert reloaded["meter"]["mean"] == pytest.approx(0.9)
    assert reloaded["anchors"]["required_coverage"] == pytest.approx(1.0)
    assert reloaded["quote_integrity"]["passed"] is True
    assert list_scorecards(tmp_path, label_prefix="round-trip") == [path]


def test_scorecard_filenames_separate_runs_that_differ_in_configuration() -> None:
    """Two arms of an A/B must not overwrite each other's scorecard."""

    off = run_signature({"beam_width": 3}, GuidanceKnobs.all_off().__dict__)
    on = run_signature({"beam_width": 3}, GuidanceKnobs().__dict__)

    assert off != on


def test_scorecard_filenames_are_stable_across_reruns_of_one_configuration() -> None:
    """The same experiment run twice overwrites itself rather than accumulating."""

    beats = [_beat("b1", [_chunk("c1", "a", "l1", 0, 0)])]
    first = compute_scorecard(_run(beats), label="stable")
    second = compute_scorecard(_run(beats), label="stable")

    assert scorecard_filename(first) == scorecard_filename(second)


# ---------------------------------------------------------------------------
# Threshold evaluation: the suite must be able to fail
# ---------------------------------------------------------------------------


def _passing_scorecard():
    """Build a scorecard that meets every threshold used in these tests."""

    beats = [
        _beat(
            "b1",
            [
                _chunk("c1", "the crown", "l1", 0, 1, play="Hamlet", iambic_score=0.9),
                _chunk("c2", "an oath", "l2", 0, 1, play="King Lear", iambic_score=0.7),
            ],
            required=["crown"],
        )
    ]
    return compute_scorecard(_run(beats), label="passing")


def test_thresholds_pass_a_healthy_scorecard() -> None:
    """The baseline: a good run produces no failures."""

    failures = evaluate_scorecard(
        _passing_scorecard(),
        ScenarioThresholds(
            min_lines=2,
            min_required_anchor_coverage=1.0,
            min_mean_iambic_score=0.5,
            min_distinct_source_plays=2,
            require_measured_meter=True,
        ),
    )

    assert failures == []


def test_thresholds_fail_on_a_quote_integrity_violation() -> None:
    """The defining rule is a hard failure, not a warning."""

    beats = [
        _beat("b1", [_chunk("c1", "the crown is", "l1", 0, 2)]),
        _beat("b2", [_chunk("c1_p0", "crown is heavy", "l1", 1, 3)]),
    ]
    scorecard = compute_scorecard(_run(beats), label="violating")

    failures = evaluate_scorecard(scorecard, ScenarioThresholds())

    assert len(failures) == 1
    assert "quote integrity" in failures[0]


def test_thresholds_fail_when_a_required_metric_was_never_measured() -> None:
    """An assertion that could not be evaluated has not been satisfied.

    This is the rule that would have caught the placeholder suite: if meter is
    required and no chunk carries an ``iambic_score``, the correct verdict is
    failure, because nothing was checked.
    """

    beats = [_beat("b1", [_chunk("c1", "no tier two here", "l1", 0, 3)])]
    scorecard = compute_scorecard(_run(beats), label="unmeasured")

    failures = evaluate_scorecard(
        scorecard,
        ScenarioThresholds(min_mean_iambic_score=0.3, require_measured_meter=True),
    )

    assert len(failures) == 2
    assert any("iambic_score" in failure for failure in failures)


def test_thresholds_fail_when_quotes_could_not_be_verified() -> None:
    """Provenance-less quotes make the integrity check partial, which is not a pass."""

    chunk = {"chunk_id": "c1", "text": "orphaned words", "tokens": ["orphaned", "words"]}
    scorecard = compute_scorecard(_run([_beat("b1", [chunk])]), label="unverifiable")

    failures = evaluate_scorecard(scorecard, ScenarioThresholds())

    assert scorecard.quote_integrity.passed is True
    assert scorecard.quote_integrity.fully_verified is False
    assert any("no source span" in failure for failure in failures)


def test_thresholds_fail_on_an_empty_play() -> None:
    """A run that produced nothing is a failure however clean it looks."""

    scorecard = compute_scorecard(_run([]), label="empty")

    failures = evaluate_scorecard(scorecard, ScenarioThresholds(min_lines=1))

    assert any("lines" in failure for failure in failures)


def test_thresholds_fail_on_a_play_drawn_from_too_few_sources() -> None:
    """Forty lines from one scene is a different artifact from forty across twenty plays."""

    beats = [
        _beat(
            "b1",
            [
                _chunk("c1", "a", "l1", 0, 0, play="Hamlet"),
                _chunk("c2", "b", "l2", 0, 0, play="Hamlet"),
            ],
        )
    ]
    scorecard = compute_scorecard(_run(beats), label="narrow")

    failures = evaluate_scorecard(scorecard, ScenarioThresholds(min_distinct_source_plays=3))

    assert any("source diversity" in failure for failure in failures)


# ---------------------------------------------------------------------------
# PlayRun construction from a live run and from an export
# ---------------------------------------------------------------------------


def _toy_plan() -> PlayPlan:
    """Build a two-beat plan with anchor obligations on both beats."""

    def beat(beat_id: str, required: List[str]) -> BeatPlan:
        return BeatPlan(
            beat_id=beat_id,
            objective="Advance the scene",
            rhetorical_mode="reflection",
            obligations=[BeatObligation(beat_id=beat_id, required_anchors=required)],
        )

    return PlayPlan(
        plan_id="plan-1",
        title="A Toy Play",
        acts=[
            ActPlan(
                act=1,
                scenes=[ScenePlan(scene_id="a1s1", act=1, scene=1, beats=[beat("b1", ["crown"])])],
            ),
            ActPlan(
                act=2,
                scenes=[ScenePlan(scene_id="a2s1", act=2, scene=1, beats=[beat("b2", ["oath"])])],
            ),
        ],
        anchors=AnchorRegistry(
            primary_anchor="crown", anchors=[AnchorPlan(anchor_term="crown")]
        ),
    )


def test_play_run_from_generation_pairs_obligations_with_selected_chunks() -> None:
    """A live run carries plan obligations, chunks, and telemetry into one view."""

    plan = _toy_plan()
    chunk_a = _chunk("c1", "the crown is heavy", "l1", 0, 3, play="Hamlet")
    chunk_b = _chunk("c2", "a broken oath", "l2", 0, 2, play="King Lear")
    generated = GeneratedPlay(
        output_lines=["the crown is heavy", "a broken oath"],
        beat_outputs=[
            GeneratedBeat(beat_id="b1", line_ids=["c1"], lines=["the crown is heavy"]),
            GeneratedBeat(beat_id="b2", line_ids=["c2"], lines=["a broken oath"]),
        ],
        markdown="",
        play_json={},
        quote_integrity=check_used_chunks([("b1", chunk_a), ("b2", chunk_b)]),
        beat_stats=[_stats("b1", dead_ends=2), _stats("b2")],
        used_chunks=[("b1", chunk_a), ("b2", chunk_b)],
    )

    run = play_run_from_generation(plan, generated, knobs=GuidanceKnobs())
    scorecard = compute_scorecard(run, label="live")

    assert run.beats[1].act == 2
    assert run.beats[0].required_anchors == ["crown"]
    assert scorecard.anchors.required_coverage == pytest.approx(1.0)
    assert scorecard.search.dead_ends == 2
    assert scorecard.chunks_are_authoritative is True


def test_play_run_from_export_resolves_chunk_ids_back_into_chunks(tmp_path: Path) -> None:
    """The M2 gap: an exported play holds only ids, and they must resolve.

    Without resolution every quote is unverifiable, so a clean report would
    prove nothing at all. This is the path scripts/score_play.py runs.
    """

    chunks_path = tmp_path / "line_chunks.jsonl"
    stored = [
        _chunk("c1", "the crown is heavy", "l1", 0, 3, play="Hamlet"),
        _chunk("c2", "a broken oath", "l2", 0, 2, play="King Lear"),
    ]
    chunks_path.write_text(
        "\n".join(json.dumps(chunk) for chunk in stored), encoding="utf-8"
    )

    play_json = {
        "plan_id": "plan-1",
        "title": "A Toy Play",
        "acts": [
            {
                "act": 1,
                "scenes": [
                    {
                        "scene_id": "a1s1",
                        "scene": 1,
                        "beats": [
                            {
                                "beat_id": "b1",
                                "line_ids": ["c1", "c2"],
                                "lines": ["the crown is heavy", "a broken oath"],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    run = play_run_from_export(play_json, JsonlChunkResolver(tmp_path))
    scorecard = compute_scorecard(run, label="export")

    assert scorecard.quote_integrity.checked == 2
    assert scorecard.quote_integrity.unverifiable == 0
    assert scorecard.diversity.distinct_plays == 2
    assert scorecard.chunks_are_authoritative is False


def test_play_run_from_export_counts_ids_that_do_not_resolve(tmp_path: Path) -> None:
    """An id the corpus no longer holds is unverifiable, not absent.

    Dropping it would shrink the denominator and let a play whose corpus has
    drifted underneath it report a clean bill of health.
    """

    (tmp_path / "line_chunks.jsonl").write_text(
        json.dumps(_chunk("c1", "the crown is heavy", "l1", 0, 3)), encoding="utf-8"
    )

    play_json = {
        "plan_id": "plan-1",
        "title": "Drifted",
        "acts": [
            {
                "act": 1,
                "scenes": [
                    {
                        "scene": 1,
                        "beats": [
                            {
                                "beat_id": "b1",
                                "line_ids": ["c1", "vanished_chunk"],
                                "lines": ["the crown is heavy", "gone"],
                            }
                        ],
                    }
                ],
            }
        ],
    }

    run = play_run_from_export(play_json, JsonlChunkResolver(tmp_path))

    assert run.integrity.checked == 1
    assert run.integrity.unverifiable == 1


def test_play_run_from_export_reports_meter_unmeasured_on_the_jsonl_path(
    tmp_path: Path,
) -> None:
    """The JSONL corpus carries no Tier-2 metadata, and the scorecard says so.

    Pinned because the alternative -- a 0.0 mean -- is indistinguishable from
    verse that does not scan, and that confusion is exactly what BUILD-PLAN
    calls the metadata boundary.
    """

    (tmp_path / "line_chunks.jsonl").write_text(
        json.dumps(_chunk("c1", "the crown is heavy", "l1", 0, 3)), encoding="utf-8"
    )
    play_json = {
        "acts": [
            {
                "act": 1,
                "scenes": [
                    {"scene": 1, "beats": [{"beat_id": "b1", "line_ids": ["c1"], "lines": ["x"]}]}
                ],
            }
        ]
    }

    run = play_run_from_export(play_json, JsonlChunkResolver(tmp_path))
    scorecard = compute_scorecard(run, label="jsonl")

    assert scorecard.meter.mean is None
    assert scorecard.meter.unmeasured == 1


# ---------------------------------------------------------------------------
# The suite end to end, against a real fixture corpus and index
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_inputs(tmp_path: Path, monkeypatch: MonkeyPatch):
    """Build a small real corpus and index, and open a pool over them.

    The suite is worth little if it only runs against hand-built dicts, so this
    exercises the same retrieval path production uses -- just over the fixture
    text rather than the full 447k-chunk index.
    """

    build_corpus(source_path=Path("tests/fixtures/sample_lines.txt"), output_dir=tmp_path)

    chroma_dir = tmp_path / "chroma"
    monkeypatch.setenv("SHPOET_PROCESSED_DIR", str(tmp_path))
    monkeypatch.setenv("SHPOET_CHROMA_DIR", str(chroma_dir))
    # Must match the stub embedder forced by conftest or the pool refuses to open.
    monkeypatch.setenv("SHPOET_EMBEDDING_DIMENSIONS", "8")
    monkeypatch.setenv("SHPOET_RETRIEVAL_POOL_SIZE", "200")
    reset_settings()
    build_all_indexes(processed_dir=tmp_path, chroma_dir=chroma_dir)

    corpus = CorpusStore(tmp_path)
    corpus.load()
    inputs = GenerationInputs(chunks=corpus.list_chunks())
    yield inputs
    inputs.close()


def _fixture_scenario(**threshold_overrides: object) -> ReplayScenario:
    """Build a scenario small enough to run against the fixture corpus."""

    thresholds = ScenarioThresholds(
        max_integrity_violations=0,
        max_unverifiable_quotes=0,
        min_lines=1,
        **threshold_overrides,  # type: ignore[arg-type]
    )
    return ReplayScenario(
        name="fixture-scenario",
        description="A minimal scenario for the fixture corpus.",
        tags=["smoke"],
        user_input=UserPlayInput(
            title="The Ashen Mirror",
            overview="A ruler confronts a mirror that remembers every oath.",
            characters=[
                CharacterInput(
                    name="Cassia",
                    description="A cautious sovereign testing prophecy.",
                    voice_traits=["measured"],
                )
            ],
            scenes=[
                SceneInput(
                    act=1,
                    scene=1,
                    setting="A dim hall with a tarnished mirror.",
                    summary="Cassia sees old vows shimmer across the glass.",
                    participants=["Cassia"],
                )
            ],
        ),
        config=GenerationConfig(
            beam_width=2, max_length=2, checkpoint_interval=2, use_critic=False
        ),
        thresholds=thresholds,
    )


def test_suite_produces_a_real_scorecard_and_writes_it(
    fixture_inputs: GenerationInputs, tmp_path: Path
) -> None:
    """A scenario run end to end yields a scorecard with real, non-placeholder numbers."""

    eval_dir = tmp_path / "eval"
    result = run_scenario(_fixture_scenario(), fixture_inputs, eval_dir=eval_dir)

    print(f"[test] scenario passed={result.passed} failures={result.failures}")
    assert result.scorecard is not None
    assert result.scorecard.line_count > 0
    assert result.scorecard.quote_integrity.checked > 0
    assert result.scorecard_path is not None and result.scorecard_path.exists()
    assert load_scorecard_dict(result.scorecard_path)["label"] == "fixture-scenario/knobs-on"


def test_suite_fails_a_scenario_whose_threshold_is_not_met(
    fixture_inputs: GenerationInputs, tmp_path: Path
) -> None:
    """The seeded regression: an unreachable threshold must produce a failure.

    The point of this test is the one the old suite could never satisfy -- that
    ``passed`` is capable of being False for a real generated play.
    """

    scenario = _fixture_scenario(min_distinct_source_plays=999)
    result = run_scenario(scenario, fixture_inputs, eval_dir=tmp_path / "eval")

    print(f"[test] seeded regression failures={result.failures}")
    assert result.passed is False
    assert any("source diversity" in failure for failure in result.failures)


def test_suite_ab_mode_produces_two_comparable_scorecards(
    fixture_inputs: GenerationInputs, tmp_path: Path
) -> None:
    """One command, two arms, two separately stored scorecards."""

    eval_dir = tmp_path / "eval"
    results = run_replay_suite(
        scenarios=[_fixture_scenario()], inputs=fixture_inputs, eval_dir=eval_dir, ab=True
    )

    assert [result.arm for result in results] == [ARM_KNOBS_OFF, ARM_KNOBS_ON]
    paths = {result.scorecard_path for result in results}
    assert len(paths) == 2, "each arm must get its own scorecard file"

    off, on = results
    assert off.scorecard is not None and on.scorecard is not None
    # The control arm must reproduce pre-M1 scoring exactly.
    assert off.scorecard.knobs["meter_preference"] == 0.0
    assert on.scorecard.knobs["meter_preference"] > 0.0


def test_suite_cli_returns_non_zero_on_a_failing_scenario(
    fixture_inputs: GenerationInputs, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A failing suite must fail a build, not just print sadly.

    Exercised through ``main`` rather than ``run_replay_suite`` because the exit
    code is the contract a CI step depends on.
    """

    monkeypatch.setattr(
        "shpoet.learning.replay_suite.build_default_scenarios",
        lambda: [_fixture_scenario(min_distinct_source_plays=999)],
    )
    monkeypatch.setattr(
        "shpoet.learning.replay_suite.build_generation_inputs",
        lambda use_critic=False: fixture_inputs,
    )

    exit_code = main(["--no-critic", "--eval-dir", str(tmp_path / "eval")])

    assert exit_code == 1


def test_suite_cli_returns_zero_when_every_scenario_passes(
    fixture_inputs: GenerationInputs, tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """The other half of the contract: a healthy run exits clean."""

    monkeypatch.setattr(
        "shpoet.learning.replay_suite.build_default_scenarios",
        lambda: [_fixture_scenario()],
    )
    monkeypatch.setattr(
        "shpoet.learning.replay_suite.build_generation_inputs",
        lambda use_critic=False: fixture_inputs,
    )

    exit_code = main(["--no-critic", "--eval-dir", str(tmp_path / "eval")])

    assert exit_code == 0


def test_cli_rejects_an_unknown_scenario_name(monkeypatch: MonkeyPatch) -> None:
    """A typo in --scenario must not silently run nothing and report success."""

    assert main(["--scenario", "no-such-scenario"]) == 2


def test_default_scenarios_declare_thresholds_that_can_actually_fail() -> None:
    """Guard against the placeholder returning by another route.

    A scenario whose thresholds assert nothing is the same failure as the old
    ``passed=True``, just spelled differently.
    """

    for scenario in build_default_scenarios():
        thresholds = scenario.thresholds
        assert thresholds.min_lines >= 1
        assert thresholds.require_measured_meter, (
            f"{scenario.name} does not assert that Tier-2 metadata arrived, so it "
            f"would pass on a run with no retrieval at all"
        )
