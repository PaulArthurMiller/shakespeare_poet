"""Query utilities for the Chroma vector store."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import chromadb

from shpoet.vectorstore.embeddings import embed_query


logger = logging.getLogger(__name__)


def query_index(
    query_text: str,
    persist_dir: Path,
    collection_name: str = "shpoet_lines",
    n_results: int = 3,
    metadata_filter: Optional[Dict[str, Any]] = None,
    embedding_dimensions: int = 8,
) -> Dict[str, Any]:
    """Query the Chroma index for semantically similar chunks."""

    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(collection_name)

    query_embedding = embed_query(query_text, dimensions=embedding_dimensions)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        where=metadata_filter,
    )
    logger.info("Query returned %s results", len(results.get("ids", [[]])[0]))
    return results
