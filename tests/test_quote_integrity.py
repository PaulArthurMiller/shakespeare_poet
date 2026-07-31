"""Tests for span-based reuse prevention and post-generation quote integrity.

The project's defining rule is that no fragment of the source text may be
quoted twice.  Enforcing it on ``chunk_id`` never could: the line chunker, the
phrase chunker, and the fragment chunker all cut overlapping text out of the
same lines, so the same words carry several ids.  These tests pin the rule to
the identity that actually expresses it -- the source word span -- at every
layer that has to honour it: the span type, the lock, the transition engine,
beam search, and the validator that judges the finished play.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import pytest
from pytest import MonkeyPatch

from shpoet.api.models import GenerationConfig
from shpoet.api.services import approve_plan, create_plan, generate_play
from shpoet.api.state import JobStore, PlanStore
from shpoet.common.spans import SourceSpan, span_from_chunk
from shpoet.common.types import (
    CharacterInput,
    GuidanceProfile,
    SceneInput,
    UserPlayInput,
)
from shpoet.config.settings import reset_settings
from shpoet.micro.candidate_pool import CandidatePool
from shpoet.micro.corpus_store import CorpusStore
from shpoet.micro.reuse_lock import ReuseLock
from shpoet.micro.transition_engine import TransitionEngine
from shpoet.scripts.build_corpus import build_corpus
from shpoet.scripts.build_index import main as build_all_indexes
from shpoet.search.beam_search import BeamSearch
from shpoet.validation.quote_integrity import (
    QuoteUsage,
    check_quote_integrity,
    check_used_chunks,
    usage_from_chunk,
)


def _chunk(
    chunk_id: str,
    text: str,
    line_id: str,
    start: int,
    end: int,
    **extra: object,
) -> Dict[str, object]:
    """Build a chunk dict carrying the provenance every chunker writes."""

    chunk: Dict[str, object] = {
        "chunk_id": chunk_id,
        "text": text,
        "tokens": text.split(),
        "token_count": len(text.split()),
        "line_id": line_id,
        "start_word_idx": start,
        "end_word_idx": end,
        "word_index": ",".join(str(i) for i in range(start, end + 1)),
    }
    chunk.update(extra)
    return chunk


class TestSourceSpanOverlap:
    """Overlap semantics, including the boundaries that must stay legal."""

    def test_identical_spans_overlap(self) -> None:
        """The same words on the same line are the same quote."""

        span = SourceSpan("ham_3_1_l56", 0, 9)
        assert span.overlaps(SourceSpan("ham_3_1_l56", 0, 9))

    def test_contained_span_overlaps(self) -> None:
        """A phrase cut out of a line shares that line's words."""

        line = SourceSpan("ham_3_1_l56", 0, 9)
        phrase = SourceSpan("ham_3_1_l56", 3, 5)
        assert line.overlaps(phrase)
        assert phrase.overlaps(line)

    def test_partial_overlap_detected(self) -> None:
        """Spans that share even one word overlap."""

        assert SourceSpan("l1", 0, 4).overlaps(SourceSpan("l1", 4, 8))

    def test_adjacent_spans_do_not_overlap(self) -> None:
        """0-3 and 4-7 quote different words and must both stay legal.

        This is the boundary the rule turns on: over-strict adjacency handling
        would delete half the usable phrase corpus for no reason.
        """

        assert not SourceSpan("l1", 0, 3).overlaps(SourceSpan("l1", 4, 7))
        assert not SourceSpan("l1", 4, 7).overlaps(SourceSpan("l1", 0, 3))

    def test_same_indices_on_different_lines_do_not_overlap(self) -> None:
        """Word 0-3 of one line is unrelated to word 0-3 of another.

        Resolves the open question in BUILD-PLAN M2: a sonnet line and a play
        line that happen to share text have different line_ids, so quoting both
        is not reuse. They are separate places in the canon.
        """

        assert not SourceSpan("son_18_l1", 0, 3).overlaps(SourceSpan("ham_3_1_l56", 0, 3))

    def test_overlapping_indices_are_exact(self) -> None:
        """The report must name which source words collided."""

        shared = SourceSpan("l1", 2, 6).overlapping_indices(SourceSpan("l1", 5, 9))
        assert shared == (5, 6)

    def test_overlapping_indices_empty_when_disjoint(self) -> None:
        """Disjoint spans share no words."""

        assert SourceSpan("l1", 0, 3).overlapping_indices(SourceSpan("l1", 4, 7)) == ()

    def test_inverted_span_rejected(self) -> None:
        """An inverted span would silently overlap nothing; refuse to build it."""

        with pytest.raises(ValueError):
            SourceSpan("l1", 5, 2)


class TestSpanFromChunk:
    """Span extraction must never invent provenance it does not have."""

    def test_reads_explicit_indices(self) -> None:
        """The normal path: start/end written by chunking/provenance.py."""

        span = span_from_chunk(_chunk("c", "to be or not", "l1", 0, 3))
        assert span == SourceSpan("l1", 0, 3)

    def test_accepts_float_indices_from_chroma(self) -> None:
        """Chroma may hand integer metadata back as floats."""

        span = span_from_chunk(
            {"chunk_id": "c", "line_id": "l1", "start_word_idx": 2.0, "end_word_idx": 5.0}
        )
        assert span == SourceSpan("l1", 2, 5)

    def test_falls_back_to_word_index(self) -> None:
        """A chunk with only the comma-separated word_index is still usable."""

        span = span_from_chunk({"chunk_id": "c", "line_id": "l1", "word_index": "4,5,6"})
        assert span == SourceSpan("l1", 4, 6)

    def test_missing_line_id_is_unverifiable(self) -> None:
        """No line_id means no span -- and must not default to something safe."""

        assert span_from_chunk({"chunk_id": "c", "start_word_idx": 0, "end_word_idx": 3}) is None

    def test_no_provenance_at_all_is_unverifiable(self) -> None:
        """A bare chunk yields None rather than a fabricated span."""

        assert span_from_chunk({"chunk_id": "c", "text": "to be"}) is None

    def test_inverted_indices_are_unverifiable(self) -> None:
        """Malformed provenance is reported as absent, not silently reordered."""

        assert span_from_chunk(
            {"chunk_id": "c", "line_id": "l1", "start_word_idx": 7, "end_word_idx": 2}
        ) is None


class TestReuseLockLocksSpans:
    """The regression this milestone exists for."""

    def test_using_a_line_locks_phrases_cut_from_it(self) -> None:
        """A phrase inside a used line is the same words and must be locked."""

        line = _chunk("l1", "To be or not to be that is the question", "l1", 0, 9)
        phrase = _chunk("l1_p0", "To be or not", "l1", 0, 3)

        lock = ReuseLock()
        lock.mark_used(line)

        assert lock.is_used(phrase)
        # ... and the id-level check alone would have missed it.
        assert not lock.is_id_used("l1_p0")

    def test_using_a_phrase_locks_the_whole_line(self) -> None:
        """The rule is symmetric: the line contains the phrase's words."""

        line = _chunk("l1", "To be or not to be that is the question", "l1", 0, 9)
        phrase = _chunk("l1_p0", "To be or not", "l1", 0, 3)

        lock = ReuseLock()
        lock.mark_used(phrase)

        assert lock.is_used(line)

    def test_adjacent_phrase_from_a_used_line_stays_available(self) -> None:
        """Locking words 0-3 must not cost the rest of the line."""

        first = _chunk("l1_p0", "To be or not", "l1", 0, 3)
        second = _chunk("l1_p1", "to be that is", "l1", 4, 7)

        lock = ReuseLock()
        lock.mark_used(first)

        assert not lock.is_used(second)

    def test_identical_text_on_another_line_stays_available(self) -> None:
        """Reuse is about source position, not about words matching."""

        used = _chunk("son_18_l1", "Shall I compare thee", "son_18_l1", 0, 3)
        elsewhere = _chunk("ham_1_1_l4", "Shall I compare thee", "ham_1_1_l4", 0, 3)

        lock = ReuseLock()
        lock.mark_used(used)

        assert not lock.is_used(elsewhere)

    def test_chunk_without_provenance_locks_by_id_and_is_counted(self) -> None:
        """Degraded locking must be visible, not silent."""

        lock = ReuseLock()
        lock.mark_used({"chunk_id": "orphan", "text": "no provenance here"})

        assert lock.is_used({"chunk_id": "orphan"})
        assert lock.unverifiable_count == 1
        assert lock.used_span_count == 0

    def test_mark_id_used_locks_without_a_span(self) -> None:
        """Callers holding only ids can still lock, and are counted as degraded."""

        lock = ReuseLock()
        lock.mark_id_used("l1_p0")

        assert lock.is_id_used("l1_p0")
        assert lock.unverifiable_count == 1

    def test_reset_clears_spans_and_ids(self) -> None:
        """A reset lock must free everything it held."""

        lock = ReuseLock()
        lock.mark_used(_chunk("l1", "To be or not", "l1", 0, 3))
        lock.reset()

        assert lock.used_span_count == 0
        assert not lock.is_used(_chunk("l1_p0", "To be", "l1", 0, 1))


def _guidance() -> GuidanceProfile:
    """Build guidance that constrains nothing but reuse."""

    return GuidanceProfile(
        beat_id="beat-1",
        anchor_targets=[],
        constraints={"required_anchor_count": 0.0},
        priors={"anchor_presence": 1.0, "length_preference": 0.0},
    )


def _overlapping_pool() -> List[Dict[str, object]]:
    """A pool where three chunks are cut from one source line."""

    return [
        _chunk("l1", "To be or not to be that is", "l1", 0, 7),
        _chunk("l1_p0", "To be or not", "l1", 0, 3),
        _chunk("l1_p1", "to be that is", "l1", 4, 7),
        _chunk("l2", "The rest is silence", "l2", 0, 3),
        _chunk("l3", "Now is the winter", "l3", 0, 3),
    ]


class TestTransitionEnginePrunesOverlaps:
    """The search layer must see the span rule, not just the id rule."""

    def test_overlapping_chunk_pruned_after_line_used(self) -> None:
        """A phrase from an already-quoted line must be pruned as reuse."""

        chunks = _overlapping_pool()
        lock = ReuseLock()
        lock.mark_used(chunks[0])  # the full line l1

        engine = TransitionEngine(chunks, lock)
        result = engine.enumerate_candidates(_guidance(), anchors_seen=[])

        assert "l1_p0" not in result.candidates
        assert "l1_p1" not in result.candidates
        assert "l1_p0" in result.pruned_reasons.get("reuse", [])
        assert "l2" in result.candidates

    def test_unrelated_lines_survive(self) -> None:
        """Span locking must not prune material from other source lines."""

        chunks = _overlapping_pool()
        lock = ReuseLock()
        lock.mark_used(chunks[1])  # phrase l1_p0, words 0-3

        engine = TransitionEngine(chunks, lock)
        result = engine.enumerate_candidates(_guidance(), anchors_seen=[])

        assert set(result.candidates) >= {"l1_p1", "l2", "l3"}
        assert "l1" not in result.candidates


class TestBeamSearchNeverReusesSpans:
    """End-to-end regression: two chunks sharing a span cannot both be selected."""

    def test_selected_path_has_no_overlapping_spans(self) -> None:
        """No two lines in one beat may quote the same source words."""

        search = BeamSearch(_overlapping_pool())
        result = search.run(
            guidance=_guidance(),
            beam_width=3,
            max_length=3,
            checkpoint_interval=0,
        )

        assert len(result.best_path) >= 2
        by_id = {str(c["chunk_id"]): c for c in _overlapping_pool()}
        spans = [span_from_chunk(by_id[chunk_id]) for chunk_id in result.best_path]
        for i, first in enumerate(spans):
            for second in spans[i + 1:]:
                assert first is not None and second is not None
                assert not first.overlaps(second), (
                    f"beam search selected overlapping spans "
                    f"{first.describe()} and {second.describe()}"
                )


class TestQuoteIntegrityValidator:
    """The validator must fail plays the search believed were legal."""

    def test_flags_a_play_that_reuses_a_span(self) -> None:
        """A hand-built play quoting one line twice must fail."""

        report = check_used_chunks(
            [
                ("beat-1", _chunk("l1", "To be or not to be", "l1", 0, 5)),
                ("beat-2", _chunk("l2", "The rest is silence", "l2", 0, 3)),
                ("beat-3", _chunk("l1_p0", "or not to be", "l1", 2, 5)),
            ]
        )

        assert not report.passed
        assert len(report.violations) == 1
        violation = report.violations[0]
        assert violation.kind == "span_overlap"
        assert violation.line_id == "l1"
        assert violation.shared_word_indices == (2, 3, 4, 5)
        assert violation.first.beat_id == "beat-1"
        assert violation.second.beat_id == "beat-3"

    def test_passes_adjacent_spans_from_one_line(self) -> None:
        """Quoting words 0-3 and 4-7 of a line is legal and must not be flagged."""

        report = check_used_chunks(
            [
                ("beat-1", _chunk("l1_p0", "To be or not", "l1", 0, 3)),
                ("beat-2", _chunk("l1_p1", "to be that is", "l1", 4, 7)),
            ]
        )

        assert report.passed
        assert report.checked == 2
        assert report.unverifiable == 0

    def test_flags_an_exact_chunk_repeat(self) -> None:
        """The same chunk twice is reuse even before spans are consulted."""

        chunk = _chunk("l1", "To be or not", "l1", 0, 3)
        report = check_used_chunks([("beat-1", chunk), ("beat-2", chunk)])

        assert not report.passed
        assert any(violation.kind == "chunk_repeat" for violation in report.violations)

    def test_counts_unverifiable_quotes_instead_of_passing_them(self) -> None:
        """A play with no provenance proves nothing and must say so."""

        report = check_quote_integrity(
            [
                QuoteUsage(beat_id="beat-1", chunk_id="a", text="To be or not"),
                QuoteUsage(beat_id="beat-2", chunk_id="b", text="The rest is silence"),
            ]
        )

        assert report.checked == 0
        assert report.unverifiable == 2
        assert "2 unverifiable" in report.describe()

    def test_empty_play_passes_with_nothing_checked(self) -> None:
        """No quotes means no violations, and the counts must show why."""

        report = check_used_chunks([])

        assert report.passed
        assert report.checked == 0

    def test_report_serializes_for_persistence(self) -> None:
        """The record stored on a generation job must be JSON-shaped."""

        report = check_used_chunks(
            [
                ("beat-1", _chunk("l1", "To be or not to be", "l1", 0, 5)),
                ("beat-2", _chunk("l1_p0", "or not to be", "l1", 2, 5)),
            ]
        )
        payload = report.to_dict()

        assert payload["passed"] is False
        assert payload["checked"] == 2
        assert payload["violations"][0]["line_id"] == "l1"
        assert payload["violations"][0]["shared_word_indices"] == [2, 3, 4, 5]

    def test_usage_from_chunk_carries_span_and_text(self) -> None:
        """Usages built from chunks must keep enough to name the violation."""

        usage = usage_from_chunk("beat-1", _chunk("l1_p0", "To be or not", "l1", 0, 3))

        assert usage.span == SourceSpan("l1", 0, 3)
        assert usage.text == "To be or not"
        assert "beat-1" in usage.describe()


class TestGeneratedPlayIntegrity:
    """A real generated play must pass -- and must actually have been checked."""

    def test_generated_play_passes_quote_integrity(
        self, tmp_path: Path, monkeypatch: MonkeyPatch
    ) -> None:
        """Generate against a real index and assert the validator verified it.

        ``unverifiable == 0`` is the assertion that matters most: it proves the
        provenance survived chunking, indexing, retrieval, and rehydration. A
        play whose chunks lost their line_ids would report zero violations while
        checking nothing at all.
        """

        fixture_path = Path("tests/fixtures/sample_lines.txt")
        build_corpus(source_path=fixture_path, output_dir=tmp_path)

        chroma_dir = tmp_path / "chroma"
        monkeypatch.setenv("SHPOET_PROCESSED_DIR", str(tmp_path))
        monkeypatch.setenv("SHPOET_CHROMA_DIR", str(chroma_dir))
        # Must match the stub embedder forced by conftest, or the pool refuses.
        monkeypatch.setenv("SHPOET_EMBEDDING_DIMENSIONS", "8")
        reset_settings()

        build_all_indexes(processed_dir=tmp_path, chroma_dir=chroma_dir)

        plan_store = PlanStore()
        job_store = JobStore()
        user_input = UserPlayInput(
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
        )
        plan_record = create_plan(user_input, plan_store)
        approve_plan(plan_record.plan.plan_id, plan_store, regenerate=False)

        pool = CandidatePool(chroma_dir, embedding_dimensions=8, pool_size=50)
        try:
            record = generate_play(
                plan_id=plan_record.plan.plan_id,
                plan_store=plan_store,
                job_store=job_store,
                corpus_store=CorpusStore(tmp_path),
                config=GenerationConfig(use_critic=False, use_chooser=False),
                candidate_pool=pool,
            )
        finally:
            pool.close()

        print(f"[test] quote integrity: {record.quote_integrity}")
        assert record.output_lines, "generation produced no lines to validate"
        assert record.quote_integrity["checked"] > 0
        assert record.quote_integrity["unverifiable"] == 0
        assert record.quote_integrity["passed"] is True, record.quote_integrity["violations"]

        # The report must survive persistence, not just live on the return value.
        stored = job_store.get(record.job_id)
        assert stored is not None
        assert stored.quote_integrity == record.quote_integrity
