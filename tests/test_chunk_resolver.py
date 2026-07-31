"""Tests for resolving an exported play's chunk ids back into chunks.

M2 enforced quote integrity during generation, where the chunk dicts are in
hand. An exported play in ``data/output/`` holds only ids, so validating one
needs the ids resolved first -- and if that resolution is wrong or silently
partial, the validator reports a clean play while checking nothing.

These tests cover both backends and, above all, the failure modes: an id that
does not resolve, a corpus file that is missing, and the metadata difference
between the two backends that determines which metrics are even answerable.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest
from pytest import MonkeyPatch

from shpoet.config.settings import reset_settings
from shpoet.scripts.build_corpus import build_corpus
from shpoet.scripts.build_index import main as build_all_indexes
from shpoet.validation.chunk_resolver import (
    ChromaChunkResolver,
    JsonlChunkResolver,
    build_resolver,
    check_exported_play,
    iter_play_quotes,
    load_play_json,
    usages_from_play_json,
)


def _chunk(chunk_id: str, text: str, line_id: str, start: int, end: int) -> Dict[str, object]:
    """Build a chunk dict carrying the provenance every chunker writes."""

    return {
        "chunk_id": chunk_id,
        "text": text,
        "tokens": text.split(),
        "token_count": len(text.split()),
        "line_id": line_id,
        "start_word_idx": start,
        "end_word_idx": end,
        "play": "Hamlet",
    }


def _write_chunks(directory: Path, filename: str, chunks) -> None:
    """Write chunk dicts to a processed JSONL file."""

    (directory / filename).write_text(
        "\n".join(json.dumps(chunk) for chunk in chunks), encoding="utf-8"
    )


def _play_json(*beats) -> Dict[str, object]:
    """Build an exported-play payload from (beat_id, chunk_ids, lines) triples."""

    return {
        "plan_id": "plan-1",
        "title": "A Test Play",
        "acts": [
            {
                "act": 1,
                "scenes": [
                    {
                        "scene_id": "a1s1",
                        "scene": 1,
                        "beats": [
                            {"beat_id": beat_id, "line_ids": list(ids), "lines": list(lines)}
                            for beat_id, ids, lines in beats
                        ],
                    }
                ],
            }
        ],
    }


# ---------------------------------------------------------------------------
# Walking the export
# ---------------------------------------------------------------------------


def test_iter_play_quotes_returns_quotes_in_play_order() -> None:
    """Order matters: integrity reports name the earlier quote of a clashing pair."""

    play_json = _play_json(
        ("b1", ["c1", "c2"], ["first", "second"]),
        ("b2", ["c3"], ["third"]),
    )

    assert iter_play_quotes(play_json) == [
        ("b1", "c1", "first"),
        ("b1", "c2", "second"),
        ("b2", "c3", "third"),
    ]


def test_iter_play_quotes_tolerates_a_play_with_no_acts() -> None:
    """A malformed export yields nothing rather than raising mid-validation."""

    assert iter_play_quotes({"title": "Empty"}) == []


def test_iter_play_quotes_handles_fewer_lines_than_ids() -> None:
    """Text is cosmetic here; a missing line must not drop the id it belongs to."""

    quotes = iter_play_quotes(_play_json(("b1", ["c1", "c2"], ["only one"])))

    assert [chunk_id for _, chunk_id, _ in quotes] == ["c1", "c2"]
    assert quotes[1][2] == ""


# ---------------------------------------------------------------------------
# The JSONL backend
# ---------------------------------------------------------------------------


def test_jsonl_resolver_finds_chunks_across_all_three_files(tmp_path: Path) -> None:
    """Line, phrase, and fragment chunks all resolve; the play may quote any."""

    _write_chunks(tmp_path, "line_chunks.jsonl", [_chunk("c_line", "a whole line", "l1", 0, 2)])
    _write_chunks(tmp_path, "phrase_chunks.jsonl", [_chunk("c_p0", "a whole", "l1", 0, 1)])
    _write_chunks(tmp_path, "fragment_chunks.jsonl", [_chunk("c_f0", "whole line", "l1", 1, 2)])

    resolved = JsonlChunkResolver(tmp_path).resolve(["c_line", "c_p0", "c_f0"])

    assert set(resolved) == {"c_line", "c_p0", "c_f0"}
    assert resolved["c_p0"]["start_word_idx"] == 0


def test_jsonl_resolver_omits_ids_it_cannot_find(tmp_path: Path) -> None:
    """A missing id is absent from the result, never invented."""

    _write_chunks(tmp_path, "line_chunks.jsonl", [_chunk("c1", "present", "l1", 0, 0)])

    resolved = JsonlChunkResolver(tmp_path).resolve(["c1", "c_missing"])

    assert set(resolved) == {"c1"}


def test_jsonl_resolver_survives_a_missing_corpus_file(tmp_path: Path) -> None:
    """A corpus built before the fragment chunker existed still resolves what it has."""

    _write_chunks(tmp_path, "line_chunks.jsonl", [_chunk("c1", "present", "l1", 0, 0)])

    resolved = JsonlChunkResolver(tmp_path).resolve(["c1"])

    assert set(resolved) == {"c1"}


def test_jsonl_resolver_skips_a_malformed_line_without_losing_the_rest(
    tmp_path: Path,
) -> None:
    """One corrupt row must not cost the whole file."""

    (tmp_path / "line_chunks.jsonl").write_text(
        "\n".join(
            [
                json.dumps(_chunk("c1", "first", "l1", 0, 0)),
                "{not valid json",
                json.dumps(_chunk("c2", "second", "l2", 0, 0)),
            ]
        ),
        encoding="utf-8",
    )

    resolved = JsonlChunkResolver(tmp_path).resolve(["c1", "c2"])

    assert set(resolved) == {"c1", "c2"}


def test_jsonl_resolver_caches_so_a_second_call_needs_no_reread(tmp_path: Path) -> None:
    """Resolution is streamed per call, so repeats must come from cache.

    Checked by deleting the corpus between calls: if the second call still
    answers, it did not touch the disk.
    """

    path = tmp_path / "line_chunks.jsonl"
    _write_chunks(tmp_path, "line_chunks.jsonl", [_chunk("c1", "present", "l1", 0, 0)])
    resolver = JsonlChunkResolver(tmp_path)

    assert set(resolver.resolve(["c1"])) == {"c1"}
    path.unlink()

    assert set(resolver.resolve(["c1"])) == {"c1"}


# ---------------------------------------------------------------------------
# Validating an exported play
# ---------------------------------------------------------------------------


def test_check_exported_play_flags_a_reused_span(tmp_path: Path) -> None:
    """The whole point: overlapping spans under different ids must fail."""

    _write_chunks(
        tmp_path,
        "line_chunks.jsonl",
        [
            _chunk("c1", "the multitudinous seas", "l1", 0, 2),
            _chunk("c1_p0", "multitudinous seas incarnadine", "l1", 1, 3),
        ],
    )
    play_json = _play_json(
        ("b1", ["c1"], ["the multitudinous seas"]),
        ("b2", ["c1_p0"], ["multitudinous seas incarnadine"]),
    )

    report = check_exported_play(play_json, JsonlChunkResolver(tmp_path))

    assert report.passed is False
    assert len(report.violations) == 1
    assert report.violations[0].shared_word_indices == (1, 2)


def test_check_exported_play_passes_adjacent_spans(tmp_path: Path) -> None:
    """Adjacent spans quote different words and stay legal."""

    _write_chunks(
        tmp_path,
        "line_chunks.jsonl",
        [
            _chunk("c1", "one two three four", "l1", 0, 3),
            _chunk("c2", "five six seven eight", "l1", 4, 7),
        ],
    )
    play_json = _play_json(("b1", ["c1", "c2"], ["one two three four", "five six seven eight"]))

    report = check_exported_play(play_json, JsonlChunkResolver(tmp_path))

    assert report.passed is True
    assert report.checked == 2


def test_unresolvable_ids_are_counted_unverifiable_not_dropped(tmp_path: Path) -> None:
    """A clean report over quotes that were never checked is the worst outcome.

    If the resolver silently dropped ids it could not find, a play whose corpus
    has been rebuilt underneath it would report zero violations having verified
    nothing -- precisely the false confidence this harness exists to remove.
    """

    _write_chunks(tmp_path, "line_chunks.jsonl", [_chunk("c1", "present", "l1", 0, 0)])
    play_json = _play_json(("b1", ["c1", "gone_a", "gone_b"], ["present", "?", "?"]))

    report = check_exported_play(play_json, JsonlChunkResolver(tmp_path))

    assert report.checked == 1
    assert report.unverifiable == 2
    # passed is True only because nothing contradicted it; the count says so.
    assert report.passed is True


def test_usages_keep_exported_text_for_ids_that_do_not_resolve(tmp_path: Path) -> None:
    """An unresolved quote still names itself in the report."""

    _write_chunks(tmp_path, "line_chunks.jsonl", [])
    usages = usages_from_play_json(
        _play_json(("b1", ["gone"], ["the vanished line"])), JsonlChunkResolver(tmp_path)
    )

    assert usages[0].text == "the vanished line"
    assert usages[0].span is None


def test_load_play_json_rejects_a_non_object(tmp_path: Path) -> None:
    """A JSON array is not a play; fail loudly rather than half-validating it."""

    path = tmp_path / "bad.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(ValueError, match="not a JSON object"):
        load_play_json(path)


def test_load_play_json_reports_a_missing_file(tmp_path: Path) -> None:
    """A mistyped path must not look like an empty play."""

    with pytest.raises(FileNotFoundError):
        load_play_json(tmp_path / "nope.json")


# ---------------------------------------------------------------------------
# The Chroma backend, against a real fixture index
# ---------------------------------------------------------------------------


@pytest.fixture
def fixture_index(tmp_path: Path, monkeypatch: MonkeyPatch):
    """Build a real corpus and Chroma index over the fixture text."""

    build_corpus(source_path=Path("tests/fixtures/sample_lines.txt"), output_dir=tmp_path)
    chroma_dir = tmp_path / "chroma"
    monkeypatch.setenv("SHPOET_PROCESSED_DIR", str(tmp_path))
    monkeypatch.setenv("SHPOET_CHROMA_DIR", str(chroma_dir))
    monkeypatch.setenv("SHPOET_EMBEDDING_DIMENSIONS", "8")
    reset_settings()
    build_all_indexes(processed_dir=tmp_path, chroma_dir=chroma_dir)
    return tmp_path, chroma_dir


def _first_chunk_ids(processed_dir: Path, count: int) -> list:
    """Read the first few chunk ids out of the processed line chunks."""

    ids = []
    with (processed_dir / "line_chunks.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            ids.append(str(json.loads(line)["chunk_id"]))
            if len(ids) == count:
                break
    return ids


def test_chroma_resolver_returns_tier2_metadata_the_jsonl_path_lacks(
    fixture_index,
) -> None:
    """The reason both backends exist.

    Tier-2 features are computed at index time and stored only in Chroma, so
    this is the only resolver that can answer a question about meter. Pinned as
    a test because the difference is invisible until a metric quietly reports
    everything as unmeasured.
    """

    processed_dir, chroma_dir = fixture_index
    chunk_ids = _first_chunk_ids(processed_dir, 3)

    with ChromaChunkResolver(chroma_dir) as resolver:
        from_index = resolver.resolve(chunk_ids)
    from_jsonl = JsonlChunkResolver(processed_dir).resolve(chunk_ids)

    assert set(from_index) == set(chunk_ids)
    assert all("iambic_score" in chunk for chunk in from_index.values())
    assert all("iambic_score" not in chunk for chunk in from_jsonl.values())
    # Provenance survives the round trip through the index, which is what makes
    # the span rule enforceable on a resolved play at all.
    for chunk_id in chunk_ids:
        assert from_index[chunk_id]["line_id"] == from_jsonl[chunk_id]["line_id"]
        assert from_index[chunk_id]["start_word_idx"] == from_jsonl[chunk_id]["start_word_idx"]


def test_chroma_resolver_omits_ids_that_are_not_indexed(fixture_index) -> None:
    """An unknown id comes back missing rather than as an empty chunk."""

    _, chroma_dir = fixture_index

    with ChromaChunkResolver(chroma_dir) as resolver:
        resolved = resolver.resolve(["definitely_not_a_real_chunk_id"])

    assert resolved == {}


def test_build_resolver_falls_back_to_jsonl_when_there_is_no_index(
    tmp_path: Path,
) -> None:
    """A fresh clone with no index must still be able to check quote integrity."""

    _write_chunks(tmp_path, "line_chunks.jsonl", [_chunk("c1", "present", "l1", 0, 0)])

    resolver = build_resolver(processed_dir=tmp_path, chroma_dir=tmp_path / "no_such_index")

    assert isinstance(resolver, JsonlChunkResolver)
    assert set(resolver.resolve(["c1"])) == {"c1"}


def test_chroma_resolver_refuses_a_directory_that_holds_no_index(
    tmp_path: Path,
) -> None:
    """Opening a non-index path must raise, not yield a resolver that finds nothing.

    ``PersistentClient`` creates its directory and ``get_or_create_collection``
    creates empty collections inside it, so without this guard a typo'd path
    produces a working-looking resolver under which every quote in the play is
    unverifiable -- a silent wrong answer where an error belongs.
    """

    with pytest.raises(FileNotFoundError, match="No Chroma index directory"):
        ChromaChunkResolver(tmp_path / "never_built")


def test_chroma_resolver_refuses_an_index_with_no_chunks_in_it(tmp_path: Path) -> None:
    """An empty index resolves nothing, so it is not a usable backend."""

    empty_index = tmp_path / "empty_chroma"
    empty_index.mkdir()

    with pytest.raises(FileNotFoundError, match="No populated Chroma collections"):
        ChromaChunkResolver(empty_index)


def test_build_resolver_prefers_the_index_when_one_exists(fixture_index) -> None:
    """Given a choice, take the backend that carries Tier-2 metadata."""

    processed_dir, chroma_dir = fixture_index

    resolver = build_resolver(processed_dir=processed_dir, chroma_dir=chroma_dir)
    try:
        assert isinstance(resolver, ChromaChunkResolver)
    finally:
        resolver.close()
