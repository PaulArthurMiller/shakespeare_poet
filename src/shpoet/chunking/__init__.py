"""Chunking utilities for turning canonical lines into chunks.

This module provides three levels of chunking:
- Line chunks: Full lines as single quotes (maximum quote unit)
- Phrase chunks: Punctuation-delimited phrases (3+ words, semantic units)
- Fragment chunks: NLP-based semantic fragments (3-8 words, syntactic units)

All chunks maintain full provenance for quote tracking and validation.

Usage:
    from shpoet.chunking import build_line_chunks, build_phrase_chunks, build_fragment_chunks

    # Build all chunk types from canonical lines
    line_chunks = build_line_chunks(canonical_lines)
    phrase_chunks = build_phrase_chunks(canonical_lines)
    fragment_chunks = build_fragment_chunks(canonical_lines)  # requires spaCy
"""

from shpoet.chunking.line_chunker import (
    build_line_chunks,
    filter_unused_line_chunks,
    get_line_chunk_by_id,
)
from shpoet.chunking.phrase_chunker import (
    MIN_PHRASE_WORDS,
    PhraseSpan,
    build_phrase_chunks,
    get_available_phrases_for_line,
)
from shpoet.chunking.fragment_chunker import (
    MIN_FRAGMENT_WORDS,
    MAX_FRAGMENT_WORDS,
    FragmentSpan,
    build_fragment_chunks,
    extract_fragments_from_line,
    get_available_fragments_for_line,
)
from shpoet.chunking.provenance import (
    build_phrase_provenance,
    build_provenance,
    provenance_to_reference_string,
    validate_provenance,
)

__all__ = [
    # Line chunking
    "build_line_chunks",
    "get_line_chunk_by_id",
    "filter_unused_line_chunks",
    # Phrase chunking
    "build_phrase_chunks",
    "get_available_phrases_for_line",
    "PhraseSpan",
    "MIN_PHRASE_WORDS",
    # Fragment chunking
    "build_fragment_chunks",
    "extract_fragments_from_line",
    "get_available_fragments_for_line",
    "FragmentSpan",
    "MIN_FRAGMENT_WORDS",
    "MAX_FRAGMENT_WORDS",
    # Provenance
    "build_provenance",
    "build_phrase_provenance",
    "validate_provenance",
    "provenance_to_reference_string",
]
