"""Build a Chroma index from processed chunks."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

from shpoet.vectorstore.chroma_store import ChromaStore


logger = logging.getLogger(__name__)


def _load_chunks(chunks_path: Path) -> List[Dict[str, object]]:
    """Load chunk dictionaries from a JSONL file."""

    if not chunks_path.exists():
        raise FileNotFoundError(f"Missing chunks file: {chunks_path}")
    with chunks_path.open("r", encoding="utf-8") as file_handle:
        return [json.loads(line) for line in file_handle if line.strip()]


def build_index(
    chunks_path: Path,
    persist_dir: Path,
    collection_name: str = "shpoet_lines",
    embedding_dimensions: int = 8,
) -> int:
    """Build or rebuild a Chroma index for the provided chunk file."""

    chunks = _load_chunks(chunks_path)
    persist_dir.mkdir(parents=True, exist_ok=True)
    store = ChromaStore(persist_dir, collection_name=collection_name)
    try:
        count = store.build_index(chunks, embedding_dimensions=embedding_dimensions)
    finally:
        store.close()

    return count
