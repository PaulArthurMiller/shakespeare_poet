"""Candidate retrieval tests using stub embeddings.

These cover the piece that was missing from generation entirely: pulling a
per-beat pool out of the vector index and handing back chunks that still carry
the Tier-1/Tier-2 metadata the constraints and scoring layer read.
"""

from __future__ import annotations

import gc
import shutil
import sys
from pathlib import Path
from tempfile import mkdtemp
from typing import Iterator, List

import pytest

from shpoet.common.types import BeatObligation, BeatPlan
from shpoet.micro.candidate_pool import (
    CandidatePool,
    build_beat_query,
    rehydrate_chunk,
)
from shpoet.vectorstore import ChromaStore


_CHUNKS: List[dict] = [
    {
        "chunk_id": "line_1",
        "text": "To be, or not to be, that is the question",
        "line_id": "line_1",
        "play": "Hamlet",
        "act": 3,
        "scene": 1,
    },
    {
        "chunk_id": "line_2",
        "text": "The lady doth protest too much, methinks",
        "line_id": "line_2",
        "play": "Hamlet",
        "act": 3,
        "scene": 2,
    },
    {
        "chunk_id": "line_3",
        "text": "But soft, what light through yonder window breaks",
        "line_id": "line_3",
        "play": "Romeo and Juliet",
        "act": 2,
        "scene": 2,
    },
    {
        "chunk_id": "line_4",
        "text": "Now is the winter of our discontent",
        "line_id": "line_4",
        "play": "Richard III",
        "act": 1,
        "scene": 1,
    },
]


def _beat(beat_id: str = "act1_scene1_beat1") -> BeatPlan:
    """Build a minimal beat plan for query construction."""

    return BeatPlan(
        beat_id=beat_id,
        objective="Confess a private doubt before the court",
        rhetorical_mode="soliloquy",
        obligations=[
            BeatObligation(beat_id=beat_id, required_anchors=["crown"], desired_anchors=["night"])
        ],
    )


@pytest.fixture()
def indexed_dir() -> Iterator[Path]:
    """Build a small single-collection Chroma index and yield its directory."""

    tmpdir = Path(mkdtemp())
    persist_dir = tmpdir / "chroma"
    store = ChromaStore(persist_dir, collection_name="shpoet_lines")
    try:
        # apply_tier2=False keeps the fixture fast; Tier-2 round-tripping is
        # covered separately in test_pool_preserves_tier2_metadata.
        store.build_index(_CHUNKS, embedding_dimensions=8, apply_tier2=False)
    finally:
        store.close()
        gc.collect()

    try:
        yield persist_dir
    finally:
        try:
            shutil.rmtree(tmpdir)
        except PermissionError:
            if not sys.platform.startswith("win"):
                raise


class TestBuildBeatQuery:
    """Tests for beat query construction."""

    def test_query_includes_objective_mode_and_anchors(self) -> None:
        """The query text should carry all three signals."""

        query = build_beat_query(_beat(), ["crown", "night"])
        assert "Confess a private doubt" in query
        assert "soliloquy" in query
        assert "crown" in query
        assert "night" in query

    def test_query_falls_back_to_beat_id_when_empty(self) -> None:
        """An empty beat must still produce a non-empty query."""

        beat = BeatPlan(beat_id="beat_x", objective="", rhetorical_mode="")
        assert build_beat_query(beat, []) == "beat_x"

    def test_query_skips_blank_anchors(self) -> None:
        """Blank anchor entries should not add stray separators."""

        query = build_beat_query(_beat(), ["", "crown", ""])
        assert "crown" in query
        assert ".." not in query


class TestRehydrateChunk:
    """Tests for reconstructing chunks from Chroma result rows."""

    def test_restores_text_and_tokens(self) -> None:
        """Text comes from the document and tokens are re-derived."""

        chunk = rehydrate_chunk("line_1", "To be, or not to be", {"play": "Hamlet"})
        assert chunk["chunk_id"] == "line_1"
        assert chunk["text"] == "To be, or not to be"
        assert chunk["tokens"] == ["To", "be", "or", "not", "to", "be"]
        assert chunk["play"] == "Hamlet"

    def test_decodes_json_encoded_metadata(self) -> None:
        """Fields JSON-encoded for storage come back as structures."""

        chunk = rehydrate_chunk(
            "line_1",
            "To be",
            {"punctuation": '{"comma": 1}', "phonemes": '["T", "UW"]'},
        )
        assert chunk["punctuation"] == {"comma": 1}
        assert chunk["phonemes"] == ["T", "UW"]

    def test_keeps_unparseable_json_as_string(self) -> None:
        """A field that will not parse is preserved, not dropped."""

        chunk = rehydrate_chunk("line_1", "To be", {"phonemes": "not-json"})
        assert chunk["phonemes"] == "not-json"

    def test_handles_missing_metadata(self) -> None:
        """A result row with no metadata still yields a usable chunk."""

        chunk = rehydrate_chunk("line_1", "To be", None)
        assert chunk["chunk_id"] == "line_1"
        assert chunk["tokens"] == ["To", "be"]


class TestCandidatePool:
    """Tests for per-beat retrieval behaviour."""

    def test_returns_search_ready_chunks(self, indexed_dir: Path) -> None:
        """Retrieved chunks must have the keys the search layer reads."""

        pool = CandidatePool(
            indexed_dir,
            collection_names=["shpoet_lines"],
            embedding_dimensions=8,
            pool_size=10,
        )
        try:
            result = pool.for_beat(_beat(), ["crown"])
        finally:
            pool.close()
            gc.collect()

        assert result.size > 0
        for chunk in result.chunks:
            assert chunk["chunk_id"]
            assert chunk["text"]
            assert isinstance(chunk["tokens"], list)
            # Tier-1 features are applied at index time; without them the
            # grammar constraint silently degrades to an empty-text check.
            assert "first_token" in chunk
            assert "last_token" in chunk
            assert "starts_with_function_word" in chunk

    def test_excludes_used_chunk_ids(self, indexed_dir: Path) -> None:
        """Already-consumed chunks must not reappear in a later beat's pool."""

        pool = CandidatePool(
            indexed_dir,
            collection_names=["shpoet_lines"],
            embedding_dimensions=8,
            pool_size=10,
        )
        try:
            everything = pool.for_beat(_beat(), [])
            assert everything.size >= 2
            victim = str(everything.chunks[0]["chunk_id"])

            filtered = pool.for_beat(_beat(), [], exclude_ids={victim})
        finally:
            pool.close()
            gc.collect()

        returned_ids = {str(chunk["chunk_id"]) for chunk in filtered.chunks}
        assert victim not in returned_ids
        assert filtered.excluded >= 1

    def test_respects_pool_size_cap(self, indexed_dir: Path) -> None:
        """The pool must not exceed the configured budget."""

        pool = CandidatePool(
            indexed_dir,
            collection_names=["shpoet_lines"],
            embedding_dimensions=8,
            pool_size=2,
        )
        try:
            result = pool.for_beat(_beat(), [])
        finally:
            pool.close()
            gc.collect()

        assert result.size == 2
        assert result.requested == 2

    def test_ordering_is_deterministic(self, indexed_dir: Path) -> None:
        """Two identical queries must return the same order."""

        pool = CandidatePool(
            indexed_dir,
            collection_names=["shpoet_lines"],
            embedding_dimensions=8,
            pool_size=10,
        )
        try:
            first = [str(c["chunk_id"]) for c in pool.for_beat(_beat(), ["crown"]).chunks]
            second = [str(c["chunk_id"]) for c in pool.for_beat(_beat(), ["crown"]).chunks]
        finally:
            pool.close()
            gc.collect()

        assert first == second

    def test_no_duplicate_chunk_ids(self, indexed_dir: Path) -> None:
        """Merging collections must not yield the same chunk twice."""

        pool = CandidatePool(
            indexed_dir,
            collection_names=["shpoet_lines", "shpoet_lines"],
            embedding_dimensions=8,
            pool_size=10,
        )
        try:
            result = pool.for_beat(_beat(), [])
        finally:
            pool.close()
            gc.collect()

        ids = [str(chunk["chunk_id"]) for chunk in result.chunks]
        assert len(ids) == len(set(ids))

    def test_excluding_everything_yields_empty_pool(self, indexed_dir: Path) -> None:
        """Exhausting the corpus returns an empty pool rather than raising."""

        pool = CandidatePool(
            indexed_dir,
            collection_names=["shpoet_lines"],
            embedding_dimensions=8,
            pool_size=10,
        )
        try:
            all_ids = {str(c["chunk_id"]) for c in pool.for_beat(_beat(), []).chunks}
            result = pool.for_beat(_beat(), [], exclude_ids=all_ids)
        finally:
            pool.close()
            gc.collect()

        assert result.size == 0
        assert result.chunks == []

    def test_missing_index_raises(self, tmp_path: Path) -> None:
        """A directory with no collections must fail loudly at construction."""

        with pytest.raises(FileNotFoundError):
            CandidatePool(
                tmp_path / "nonexistent",
                collection_names=[],
                embedding_dimensions=8,
                pool_size=10,
            )

    def test_rejects_invalid_pool_size(self, indexed_dir: Path) -> None:
        """A non-positive pool size is a configuration error."""

        with pytest.raises(ValueError):
            CandidatePool(indexed_dir, collection_names=["shpoet_lines"], pool_size=0)


def test_pool_preserves_tier2_metadata() -> None:
    """Tier-2 features must survive the round trip into the search layer.

    This is the property the whole retrieval step exists for: meter and
    emotion scoring read these keys off the chunk dict, and they are absent
    from the processed JSONL files the old path loaded.
    """

    tmpdir = Path(mkdtemp())
    persist_dir = tmpdir / "chroma"
    store = ChromaStore(persist_dir, collection_name="shpoet_lines")
    try:
        store.build_index(_CHUNKS[:2], embedding_dimensions=8, apply_tier2=True)
    finally:
        store.close()
        gc.collect()

    pool = CandidatePool(
        persist_dir,
        collection_names=["shpoet_lines"],
        embedding_dimensions=8,
        pool_size=10,
    )
    try:
        result = pool.for_beat(_beat(), [])
    finally:
        pool.close()
        gc.collect()
        try:
            shutil.rmtree(tmpdir)
        except PermissionError:
            if not sys.platform.startswith("win"):
                raise

    assert result.size > 0
    chunk = result.chunks[0]
    for key in ("stress_pattern", "rhyme_class", "syllable_count", "iambic_score", "emotion_valence"):
        assert key in chunk, f"Tier-2 key {key} lost in retrieval"
    # syllable_count must be a real measurement, not the 0 default that
    # build_scoring_features falls back to.
    assert int(chunk["syllable_count"]) > 0
