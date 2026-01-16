"""Corpus store for retrieving chunks and metadata."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List


logger = logging.getLogger(__name__)


class CorpusStore:
    """Lightweight store for line chunks and canonical metadata."""

    def __init__(self, processed_dir: Path) -> None:
        """Initialize the store with a processed data directory."""

        self._processed_dir = processed_dir
        self._chunks: List[Dict[str, object]] = []

    def load(self) -> None:
        """Load line chunks from the processed directory."""

        chunks_path = self._processed_dir / "line_chunks.jsonl"
        if not chunks_path.exists():
            raise FileNotFoundError(f"Missing processed chunk file: {chunks_path}")

        with chunks_path.open("r", encoding="utf-8") as file_handle:
            self._chunks = [json.loads(line) for line in file_handle if line.strip()]

        logger.info("Loaded %s chunks from %s", len(self._chunks), chunks_path)

    def list_chunks(self) -> List[Dict[str, object]]:
        """Return all loaded chunks."""

        return list(self._chunks)

    def get_chunk(self, chunk_id: str) -> Dict[str, object]:
        """Retrieve a chunk by its identifier."""

        for chunk in self._chunks:
            if chunk.get("chunk_id") == chunk_id:
                return chunk
        raise KeyError(f"Chunk not found: {chunk_id}")
