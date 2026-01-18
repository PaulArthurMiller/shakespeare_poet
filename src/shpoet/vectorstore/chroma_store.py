"""Chroma store wrapper with explicit lifecycle management."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import chromadb

from shpoet.features.tier1_raw import apply_tier1_features
from shpoet.vectorstore.embeddings import embed_query, embed_texts


logger = logging.getLogger(__name__)


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

    def build_index(self, chunks: List[Dict[str, object]], embedding_dimensions: int = 8) -> int:
        """Build or rebuild the index from raw chunk dictionaries."""

        enriched_chunks = apply_tier1_features(chunks)
        documents = [str(chunk.get("text", "")) for chunk in enriched_chunks]
        ids = [str(chunk.get("chunk_id")) for chunk in enriched_chunks]
        metadatas = []
        for chunk in enriched_chunks:
            raw_metadata = {key: value for key, value in chunk.items() if key not in {"text", "tokens"}}
            metadatas.append(self._sanitize_metadata(raw_metadata))

        embeddings = embed_texts(documents, dimensions=embedding_dimensions)

        self.reset_collection()
        self._collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

        logger.info("Indexed %s chunks into collection %s", len(ids), self._collection_name)
        return len(ids)

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

    def close(self) -> None:
        """Release references to the underlying client."""

        self._collection = None
        self._client = None
