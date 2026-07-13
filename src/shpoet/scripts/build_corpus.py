"""Build processed corpus artifacts from raw text."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

from shpoet.chunking.fragment_chunker import build_fragment_chunks
from shpoet.chunking.line_chunker import build_line_chunks
from shpoet.chunking.phrase_chunker import build_phrase_chunks
from shpoet.ingest.canon_index import build_canonical_index, canonical_lines_to_dicts
from shpoet.ingest.source_loader import load_lines


logger = logging.getLogger(__name__)

DEFAULT_SOURCE = Path("data/raw/shakespeare_sample.txt")
DEFAULT_OUTPUT = Path("data/processed")


def _write_jsonl(path: Path, items: Iterable[object]) -> int:
    """Write items as newline-delimited JSON; return the count written."""
    count = 0
    with path.open("w", encoding="utf-8") as fh:
        for item in items:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
            count += 1
    return count


def build_corpus(
    source_path: Path = DEFAULT_SOURCE,
    output_dir: Path = DEFAULT_OUTPUT,
    resume: bool = False,
) -> None:
    """Build canonical line index and all chunk types to the processed directory.

    Each output file is written immediately after its chunk type is built, so if
    the run is interrupted (e.g. during the slower fragment-chunking step), the
    already-completed files are preserved on disk.

    With resume=True, any output file that already exists is skipped, allowing
    an interrupted run to continue from where it left off.
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    output_dir.mkdir(parents=True, exist_ok=True)

    lines = load_lines(source_path)
    canonical_lines = build_canonical_index(lines)
    logger.info("Loaded %d canonical lines from %s", len(canonical_lines), source_path)

    index_path = output_dir / "line_index.jsonl"
    if resume and index_path.exists():
        logger.info("Skipping %s (already exists)", index_path.name)
    else:
        count = _write_jsonl(index_path, canonical_lines_to_dicts(canonical_lines))
        logger.info("Wrote %d entries to %s", count, index_path.name)

    # Each step builds and writes immediately so partial progress is preserved.
    for builder, filename in (
        (lambda: build_line_chunks(canonical_lines), "line_chunks.jsonl"),
        (lambda: build_phrase_chunks(canonical_lines), "phrase_chunks.jsonl"),
        (lambda: build_fragment_chunks(canonical_lines), "fragment_chunks.jsonl"),
    ):
        out_path = output_dir / filename
        if resume and out_path.exists():
            logger.info("Skipping %s (already exists)", filename)
            continue
        logger.info("Building %s …", filename)
        chunks = builder()
        count = _write_jsonl(out_path, chunks)
        logger.info("Wrote %d chunks to %s", count, filename)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build processed corpus artifacts from raw text.")
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"Path to raw Shakespeare text file (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Directory for processed output files (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip output files that already exist and continue from where the last run stopped.",
    )
    args = parser.parse_args()
    build_corpus(source_path=args.source, output_dir=args.output_dir, resume=args.resume)
