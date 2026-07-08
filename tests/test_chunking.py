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


def test_canonical_index_handles_scene_prologue() -> None:
    """Ensure "SCENE PROLOGUE" (Chorus speeches) is not skipped.

    Regression test: the scene regex only matched Roman/Arabic numerals, so
    "SCENE PROLOGUE" (used in Henry IV Pt.2, Henry V, Henry VIII, Pericles,
    Romeo and Juliet, Troilus and Cressida, and Two Noble Kinsmen) left
    `scene` as None, silently dropping every line up to the next numbered
    SCENE header.
    """

    sample_lines = [
        "THE LIFE OF KING HENRY THE FIFTH",
        "ACT I",
        "SCENE PROLOGUE",
        "O for a Muse of fire, that would ascend",
        "SCENE I. London. An ante-chamber in the King's palace.",
        "My lord, I'll tell you that self bill is urged,",
    ]

    canonical = build_canonical_index(sample_lines)

    assert len(canonical) == 2
    assert canonical[0].line_id == "the_life_of_king_henry_the_fifth_act1_scene0_line1"
    assert canonical[1].line_id == "the_life_of_king_henry_the_fifth_act1_scene1_line1"


def test_canonical_index_handles_act_induction() -> None:
    """Ensure "ACT INDUCTION" (The Taming of the Shrew) gets its own act number.

    Regression test: the act regex `^ACT\\s+([IVXLC]+)` had no trailing word
    boundary, so it partially matched the leading "I" in "INDUCTION" and
    mislabeled the Induction as ACT 1 — colliding its line_ids with the real
    Act 1 Scene 1/2 that follows.
    """

    sample_lines = [
        "THE TAMING OF THE SHREW",
        "ACT INDUCTION",
        "SCENE I",
        "I'll pheeze you, in faith.",
        "ACT I",
        "SCENE I. Padua. A public place.",
        "Tranio, since for the great desire I had",
    ]

    canonical = build_canonical_index(sample_lines)

    assert len(canonical) == 2
    assert canonical[0].line_id == "the_taming_of_the_shrew_act0_scene1_line1"
    assert canonical[1].line_id == "the_taming_of_the_shrew_act1_scene1_line1"


def test_canonical_index_handles_semicolon_in_play_title() -> None:
    """Ensure play titles containing a semicolon are recognized as headers.

    Regression test: "TWELFTH NIGHT; OR, WHAT YOU WILL" failed the play
    header regex (semicolon wasn't in the allowed character class), so the
    header line was never detected. The play name silently stayed whatever
    the previous play was, colliding every subsequent line_id with that
    play's lines.
    """

    sample_lines = [
        "TWELFTH NIGHT; OR, WHAT YOU WILL",
        "ACT I",
        "SCENE I. An Apartment in the Duke's Palace.",
        "If music be the food of love, play on,",
    ]

    canonical = build_canonical_index(sample_lines)

    assert len(canonical) == 1
    assert canonical[0].play == "Twelfth Night; Or, What You Will"
    assert canonical[0].line_id == "twelfth_night_or_what_you_will_act1_scene1_line1"


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
