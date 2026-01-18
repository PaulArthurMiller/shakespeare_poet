"""Query utilities for the Chroma vector store."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

from shpoet.vectorstore.chroma_store import ChromaStore


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

    store = ChromaStore(persist_dir, collection_name=collection_name)
    try:
        results = store.query(
            query_text,
            n_results=n_results,
            metadata_filter=metadata_filter,
            embedding_dimensions=embedding_dimensions,
        )
    finally:
        store.close()

    return results
