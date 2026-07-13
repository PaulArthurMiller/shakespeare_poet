"""Build the Chroma index from all processed corpus chunk files."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from shpoet.vectorstore.build_index import build_index
from shpoet.config.settings import get_settings


logger = logging.getLogger(__name__)

DEFAULT_PROCESSED = Path("data/processed")
DEFAULT_CHROMA = Path("data/chroma")

CHUNK_FILES = [
    ("line_chunks.jsonl", "shpoet_lines"),
    ("phrase_chunks.jsonl", "shpoet_phrases"),
    ("fragment_chunks.jsonl", "shpoet_fragments"),
]


def main(
    processed_dir: Path = DEFAULT_PROCESSED,
    chroma_dir: Path = DEFAULT_CHROMA,
    resume: bool = False,
) -> None:
    """Index all available chunk types into their respective Chroma collections.

    With resume=True, chunks already present in a collection are skipped so
    an interrupted run can be continued without losing completed work.
    """
    settings = get_settings()
    dimensions = settings.embedding_dimensions

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logger.info(
        "Building index: provider=%s model=%s dims=%d resume=%s",
        settings.embedding_provider,
        settings.embedding_model,
        dimensions,
        resume,
    )

    indexed_total = 0
    for filename, collection_name in CHUNK_FILES:
        chunks_path = processed_dir / filename
        if not chunks_path.exists():
            logger.warning("Skipping missing chunk file: %s", chunks_path)
            continue
        logger.info("Indexing %s → collection '%s'", chunks_path, collection_name)
        count = build_index(
            chunks_path=chunks_path,
            persist_dir=chroma_dir,
            collection_name=collection_name,
            embedding_dimensions=dimensions,
            resume=resume,
        )
        logger.info("Added %d chunks into '%s'", count, collection_name)
        indexed_total += count

    logger.info("Done. Chunks added this run: %d", indexed_total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Chroma index from processed corpus chunks.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=DEFAULT_PROCESSED,
        help="Directory containing *_chunks.jsonl files (default: data/processed)",
    )
    parser.add_argument(
        "--chroma-dir",
        type=Path,
        default=DEFAULT_CHROMA,
        help="Directory for Chroma persistence (default: data/chroma)",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip chunks already present in the collection and continue from where the last run stopped.",
    )
    args = parser.parse_args()
    main(processed_dir=args.processed_dir, chroma_dir=args.chroma_dir, resume=args.resume)
