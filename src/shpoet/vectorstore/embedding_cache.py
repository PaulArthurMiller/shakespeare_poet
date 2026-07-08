"""Per-batch checkpointing cache for embedding computation.

Embedding calls to external APIs (OpenAI, Voyage) are slow and cost money for
a corpus with hundreds of thousands of chunks. This cache persists embeddings
to disk immediately after each batch completes, so an interrupted build_index
run (crashed process, network failure, killed terminal) can resume from where
it left off instead of re-embedding — and re-paying for — chunks that were
already processed.

Cache files live next to the Chroma persistence directory, one pair per
collection:
  .embed_cache_<collection>.jsonl       chunk_id -> content_hash + embedding
  .embed_cache_<collection>.meta.json   provider/model/dimensions fingerprint

The meta file guards against silently reusing embeddings computed under a
different model or dimensionality; if the fingerprint doesn't match the
current settings, the whole cache is discarded rather than mixed in.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def content_hash(text: str) -> str:
    """Stable hash of chunk text, used to detect stale cache entries."""

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class EmbeddingCache:
    """Disk-backed cache mapping chunk_id -> embedding for one collection."""

    def __init__(
        self,
        persist_dir: Path,
        collection_name: str,
        provider: str,
        model: str,
        dimensions: int,
    ) -> None:
        """Load any existing cache for this collection, validating its fingerprint."""

        self._cache_path = persist_dir / f".embed_cache_{collection_name}.jsonl"
        self._meta_path = persist_dir / f".embed_cache_{collection_name}.meta.json"
        self._meta = {"provider": provider, "model": model, "dimensions": dimensions}
        self._entries: Dict[str, Tuple[str, List[float]]] = {}
        self._load()

    def _load(self) -> None:
        """Populate in-memory entries from disk, discarding a stale-config cache."""

        if not self._meta_path.exists() or not self._cache_path.exists():
            return

        try:
            cached_meta = json.loads(self._meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read embedding cache metadata (%s); starting fresh", exc)
            self.clear()
            return

        if cached_meta != self._meta:
            logger.info(
                "Embedding config changed (cached=%s, current=%s); discarding stale cache",
                cached_meta,
                self._meta,
            )
            self.clear()
            return

        try:
            with self._cache_path.open("r", encoding="utf-8") as file_handle:
                for line in file_handle:
                    line = line.strip()
                    if not line:
                        continue
                    record = json.loads(line)
                    self._entries[record["chunk_id"]] = (record["content_hash"], record["embedding"])
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Embedding cache file is corrupt (%s); starting fresh", exc)
            self._entries = {}
            self.clear()
            return

        logger.info("Loaded %d cached embeddings from %s", len(self._entries), self._cache_path)

    def get(self, chunk_id: str, chunk_hash: str) -> Optional[List[float]]:
        """Return the cached embedding if present and the source text hasn't changed."""

        entry = self._entries.get(chunk_id)
        if entry is None:
            return None
        cached_hash, embedding = entry
        if cached_hash != chunk_hash:
            return None
        return embedding

    def append_batch(
        self,
        chunk_ids: List[str],
        chunk_hashes: List[str],
        embeddings: List[List[float]],
    ) -> None:
        """Persist a freshly computed batch to disk immediately — this is the checkpoint."""

        self._meta_path.write_text(json.dumps(self._meta), encoding="utf-8")
        with self._cache_path.open("a", encoding="utf-8") as file_handle:
            for chunk_id, chunk_hash, embedding in zip(chunk_ids, chunk_hashes, embeddings):
                record = {"chunk_id": chunk_id, "content_hash": chunk_hash, "embedding": embedding}
                file_handle.write(json.dumps(record) + "\n")
                self._entries[chunk_id] = (chunk_hash, embedding)

    def clear(self) -> None:
        """Remove the cache from disk, e.g. after a config change invalidates it."""

        self._cache_path.unlink(missing_ok=True)
        self._meta_path.unlink(missing_ok=True)
        self._entries = {}
