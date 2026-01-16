"""Build the Chroma index from processed corpus data."""

from __future__ import annotations

from pathlib import Path

from shpoet.vectorstore.build_index import build_index


DEFAULT_CHUNKS = Path("data/processed/line_chunks.jsonl")
DEFAULT_CHROMA = Path("data/chroma")


def main() -> None:
    """Run the Chroma index build using default paths."""

    build_index(chunks_path=DEFAULT_CHUNKS, persist_dir=DEFAULT_CHROMA)


if __name__ == "__main__":
    main()
