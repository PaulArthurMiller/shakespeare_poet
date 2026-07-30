"""Chroma store wrapper with explicit lifecycle management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from shpoet.features.tier1_raw import apply_tier1_features
from shpoet.features.tier2_derived import apply_tier2_features
from shpoet.vectorstore.embeddings import embed_query, embed_texts_with_checkpointing


logger = logging.getLogger(__name__)

# Chunks per ChromaDB add() call. Each call embeds this many texts then
# persists them before moving on, so a crash loses at most one batch.
_INDEX_BATCH_SIZE = 500


class ChromaStore:
    """Owns a Chroma client and provides index/query operations."""

    def __init__(self, persist_dir: Path, collection_name: str = "shpoet_lines") -> None:
        """Initialize the Chroma client and collection."""

        self._persist_dir = persist_dir
        self._collection_name = collection_name
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        self._collection = self._client.get_or_create_collection(collection_name)

    def _sanitize_metadata(self, metadata: Dict[str, object]) -> Dict[str, object]:
        """Convert non-scalar metadata values into JSON strings for Chroma."""

        sanitized: Dict[str, object] = {}
        for key, value in metadata.items():
            if isinstance(value, (dict, list)):
                sanitized[key] = json.dumps(value, ensure_ascii=False)
            else:
                sanitized[key] = value
        return sanitized

    def reset_collection(self) -> None:
        """Clear existing documents from the collection."""

        existing = self._collection.get()
        existing_ids = existing.get("ids", [])
        if existing_ids:
            self._collection.delete(ids=existing_ids)

    def build_index(
        self,
        chunks: List[Dict[str, object]],
        embedding_dimensions: int = 8,
        apply_tier2: bool = True,
        resume: bool = False,
    ) -> int:
        """Build or rebuild the index from raw chunk dictionaries.

        Each batch is embedded (with a disk-backed embedding cache) and
        added to ChromaDB before the next batch begins.  A crash therefore
        loses at most _INDEX_BATCH_SIZE chunks of work, and re-running never
        re-pays API costs for embeddings that were already computed.

        Args:
            chunks: List of chunk dictionaries with text and tokens.
            embedding_dimensions: Advisory embedding size (used by stub embedder;
                real providers use their configured dimensions).
            apply_tier2: Whether to apply Tier-2 NLP features.
            resume: When True, skip chunks already present in the collection
                and continue from where a previous run left off.

        Returns:
            Number of chunks added in this call (excludes pre-existing).
        """
        # Tier-1 is fast; run on everything so we have IDs for the resume check.
        enriched = apply_tier1_features(chunks)

        if resume:
            existing_ids = set(self._collection.get(include=[]).get("ids", []))
            pending = [c for c in enriched if str(c.get("chunk_id")) not in existing_ids]
            logger.info(
                "Resume: %d already indexed, %d remaining in '%s'",
                len(existing_ids), len(pending), self._collection_name,
            )
        else:
            self.reset_collection()
            pending = enriched

        if not pending:
            logger.info("Nothing to index in '%s'", self._collection_name)
            return 0

        # Tier-2 (spaCy) only on the chunks we actually need to embed.
        if apply_tier2:
            pending = apply_tier2_features(pending)

        indexed = 0
        total = len(pending)
        for i in range(0, total, _INDEX_BATCH_SIZE):
            batch = pending[i : i + _INDEX_BATCH_SIZE]
            documents = [str(c.get("text", "")) for c in batch]
            ids = [str(c.get("chunk_id")) for c in batch]
            metadatas = [
                self._sanitize_metadata(
                    {k: v for k, v in c.items() if k not in {"text", "tokens"}}
                )
                for c in batch
            ]
            # embed_texts_with_checkpointing caches each batch to disk, so a
            # crash during embedding never forces a full re-embed on retry.
            embeddings = embed_texts_with_checkpointing(
                ids=ids,
                texts=documents,
                dimensions=embedding_dimensions,
                persist_dir=self._persist_dir,
                collection_name=self._collection_name,
            )
            self._collection.add(
                ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas
            )
            indexed += len(batch)
            logger.info(
                "Progress: %d/%d chunks indexed into '%s'",
                indexed, total, self._collection_name,
            )

        logger.info(
            "Done: %d chunks added; collection '%s' total = %d",
            indexed, self._collection_name, self._collection.count(),
        )
        return indexed

    def query(
        self,
        query_text: str,
        n_results: int = 3,
        metadata_filter: Optional[Dict[str, Any]] = None,
        embedding_dimensions: int = 8,
    ) -> Dict[str, Any]:
        """Query the collection for semantically similar chunks."""

        query_embedding = embed_query(query_text, dimensions=embedding_dimensions)
        results = self._collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=metadata_filter,
        )
        logger.info("Query returned %s results", len(results.get("ids", [[]])[0]))
        return results

    def embedding_dimension(self) -> Optional[int]:
        """Return the dimensionality of the stored vectors, if any exist.

        Used to catch a configuration mismatch up front: querying a 3072-dim
        collection with an 8-dim stub vector raises deep inside Chroma, once
        per query, which is easy to mistake for "no results" instead of
        "wrong embedding settings".
        """

        try:
            sample = self._collection.get(limit=1, include=["embeddings"])
        except Exception as exc:  # noqa: BLE001 - treated as "unknown", never fatal
            logger.debug("Could not read embedding dimension from '%s': %s", self._collection_name, exc)
            return None

        embeddings = sample.get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            return None
        return len(embeddings[0])

    def count(self) -> int:
        """Return the number of documents in the collection."""

        return int(self._collection.count())

    def close(self) -> None:
        """Release references to the underlying client."""

        self._collection = None
        self._client = None
