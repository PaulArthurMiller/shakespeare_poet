"""Chunking and ingestion tests for stable IDs and provenance."""

from shpoet.chunking.line_chunker import build_line_chunks
from shpoet.ingest.canon_index import build_canonical_index


def test_canonical_index_generates_stable_ids() -> None:
    """Ensure line IDs and word indices are stable for sample input."""

    sample_lines = [
        "THE TRAGEDY OF HAMLET, PRINCE OF DENMARK",
        "ACT I",
        "SCENE I. Elsinore. A platform before the Castle.",
        "Who's there?",
        "Nay, answer me. Stand and unfold yourself.",
    ]

    canonical = build_canonical_index(sample_lines)

    assert canonical[0].line_id == "the_tragedy_of_hamlet_prince_of_denmark_act1_scene1_line1"
    assert canonical[0].word_index == "0,1"
    assert canonical[1].line_id.endswith("line2")


def test_line_chunks_include_provenance() -> None:
    """Ensure line chunks include provenance metadata."""

    sample_lines = [
        "THE TRAGEDY OF HAMLET, PRINCE OF DENMARK",
        "ACT I",
        "SCENE I. Elsinore. A platform before the Castle.",
        "Who's there?",
    ]

    canonical = build_canonical_index(sample_lines)
    chunks = build_line_chunks(canonical)

    assert chunks[0]["chunk_id"] == canonical[0].line_id
    assert chunks[0]["line_id"] == canonical[0].line_id
    assert chunks[0]["word_index"] == canonical[0].word_index
