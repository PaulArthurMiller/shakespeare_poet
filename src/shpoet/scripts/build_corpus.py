"""Build processed corpus artifacts from raw text."""

from __future__ import annotations

import json
from pathlib import Path

from shpoet.chunking.line_chunker import build_line_chunks
from shpoet.ingest.canon_index import build_canonical_index, canonical_lines_to_dicts
from shpoet.ingest.source_loader import load_lines


DEFAULT_SOURCE = Path("data/raw/shakespeare_sample.txt")
DEFAULT_OUTPUT = Path("data/processed")


def build_corpus(source_path: Path = DEFAULT_SOURCE, output_dir: Path = DEFAULT_OUTPUT) -> None:
    """Build canonical line index and line chunks to the processed directory."""

    lines = load_lines(source_path)
    canonical_lines = build_canonical_index(lines)
    line_chunks = build_line_chunks(canonical_lines)

    output_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "line_index.jsonl"
    with index_path.open("w", encoding="utf-8") as file_handle:
        for entry in canonical_lines_to_dicts(canonical_lines):
            file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    chunks_path = output_dir / "line_chunks.jsonl"
    with chunks_path.open("w", encoding="utf-8") as file_handle:
        for chunk in line_chunks:
            file_handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    build_corpus()
