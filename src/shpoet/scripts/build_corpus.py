"""Build processed corpus artifacts from raw text."""

from __future__ import annotations

import json
from pathlib import Path

from shpoet.chunking.fragment_chunker import build_fragment_chunks
from shpoet.chunking.line_chunker import build_line_chunks
from shpoet.chunking.phrase_chunker import build_phrase_chunks
from shpoet.ingest.canon_index import build_canonical_index, canonical_lines_to_dicts
from shpoet.ingest.source_loader import load_lines


DEFAULT_SOURCE = Path("data/raw/shakespeare_sample.txt")
DEFAULT_OUTPUT = Path("data/processed")


def build_corpus(source_path: Path = DEFAULT_SOURCE, output_dir: Path = DEFAULT_OUTPUT) -> None:
    """Build canonical line index and all chunk types to the processed directory."""

    lines = load_lines(source_path)
    canonical_lines = build_canonical_index(lines)
    line_chunks = build_line_chunks(canonical_lines)
    phrase_chunks = build_phrase_chunks(canonical_lines)
    fragment_chunks = build_fragment_chunks(canonical_lines)

    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "line_index.jsonl"
    with index_path.open("w", encoding="utf-8") as file_handle:
        for entry in canonical_lines_to_dicts(canonical_lines):
            file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    for chunk_list, filename in (
        (line_chunks, "line_chunks.jsonl"),
        (phrase_chunks, "phrase_chunks.jsonl"),
        (fragment_chunks, "fragment_chunks.jsonl"),
    ):
        chunk_path = output_dir / filename
        with chunk_path.open("w", encoding="utf-8") as file_handle:
            for chunk in chunk_list:
                file_handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    build_corpus()
