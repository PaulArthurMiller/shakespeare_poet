"""Build a Chroma index from processed chunks."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List

import chromadb

from shpoet.features.tier1_raw import apply_tier1_features
from shpoet.vectorstore.embeddings import embed_texts


logger = logging.getLogger(__name__)


def _load_chunks(chunks_path: Path) -> List[Dict[str, object]]:
    """Load chunk dictionaries from a JSONL file."""

    if not chunks_path.exists():
        raise FileNotFoundError(f"Missing chunks file: {chunks_path}")
    with chunks_path.open("r", encoding="utf-8") as file_handle:
        return [json.loads(line) for line in file_handle if line.strip()]


def _sanitize_metadata(metadata: Dict[str, object]) -> Dict[str, object]:
    """Convert non-scalar metadata values into JSON strings for Chroma."""

    sanitized: Dict[str, object] = {}
    for key, value in metadata.items():
        if isinstance(value, (dict, list)):
            sanitized[key] = json.dumps(value, ensure_ascii=False)
        else:
            sanitized[key] = value
    return sanitized


def build_index(
    chunks_path: Path,
    persist_dir: Path,
    collection_name: str = "shpoet_lines",
    embedding_dimensions: int = 8,
) -> int:
    """Build or rebuild a Chroma index for the provided chunk file."""

    chunks = _load_chunks(chunks_path)
    enriched_chunks = apply_tier1_features(chunks)

    documents = [str(chunk.get("text", "")) for chunk in enriched_chunks]
    ids = [str(chunk.get("chunk_id")) for chunk in enriched_chunks]
    metadatas = []
    for chunk in enriched_chunks:
        raw_metadata = {key: value for key, value in chunk.items() if key not in {"text", "tokens"}}
        metadatas.append(_sanitize_metadata(raw_metadata))

    embeddings = embed_texts(documents, dimensions=embedding_dimensions)

    persist_dir.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(persist_dir))
    collection = client.get_or_create_collection(collection_name)

    existing = collection.get()
    existing_ids = existing.get("ids", [])
    if existing_ids:
        collection.delete(ids=existing_ids)
    collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

    logger.info("Indexed %s chunks into collection %s", len(ids), collection_name)
    return len(ids)
