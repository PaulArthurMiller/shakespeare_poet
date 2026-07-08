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


def test_canonical_index_handles_arabic_numbered_sonnet_scenes() -> None:
    """Ensure Sonnets (Arabic-numbered scenes) are not skipped like Roman-numbered plays.

    Regression test: the Sonnets number each poem "SCENE 1", "SCENE 2", ... instead of
    "SCENE I", "SCENE II", ... like the plays. The scene regex previously only matched
    Roman numerals, so `scene` stayed None and every sonnet line was silently dropped.
    """

    sample_lines = [
        "THE SONNETS",
        "ACT I",
        "SCENE 1",
        "From fairest creatures we desire increase,",
        "SCENE 2",
        "When forty winters shall besiege thy brow,",
    ]

    canonical = build_canonical_index(sample_lines)

    assert len(canonical) == 2
    assert canonical[0].line_id == "the_sonnets_act1_scene1_line1"
    assert canonical[1].line_id == "the_sonnets_act1_scene2_line1"


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
