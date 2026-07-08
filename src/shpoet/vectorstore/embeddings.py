"""Embedding providers: stub (default), OpenAI, and Voyage AI.

The active provider is selected at runtime from settings:
  SHPOET_EMBEDDING_PROVIDER = openai | voyage   (default: openai)
  SHPOET_EMBEDDING_MODEL    = model name        (default: text-embedding-3-large)
  SHPOET_EMBEDDING_DIMENSIONS = int             (default: 3072)
  OPENAI_API_KEY / VOYAGE_API_KEY

Falls back to stub (hash-based, 8-dim) when no API key is configured,
so tests and offline runs continue to work without changes.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Models that accept an explicit output dimension (truncation)
_OPENAI_DIMENSION_MODELS = frozenset({"text-embedding-3-small", "text-embedding-3-large"})
_OPENAI_BATCH = 500   # well inside token limits for short Shakespeare quotes
_VOYAGE_BATCH = 128   # Voyage AI hard limit


# ── Stub ─────────────────────────────────────────────────────────────────────

class StubEmbedder:
    """Deterministic hash-based embedder for tests and offline development."""

    dimensions: int = 8
    batch_size: int = 500

    def embed(self, texts: List[str]) -> List[List[float]]:
        return [_hash_to_floats(t, self.dimensions) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        return _hash_to_floats(query, self.dimensions)


def _hash_to_floats(text: str, dims: int) -> List[float]:
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return [digest[i % len(digest)] / 255.0 for i in range(dims)]


# ── OpenAI ───────────────────────────────────────────────────────────────────

class OpenAIEmbedder:
    """Embedder backed by the OpenAI Embeddings API."""

    batch_size: int = _OPENAI_BATCH

    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self.dimensions = dimensions

    def embed(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        total = len(texts)
        for i in range(0, total, _OPENAI_BATCH):
            batch = texts[i : i + _OPENAI_BATCH]
            kwargs = {"input": batch, "model": self._model}
            if self._model in _OPENAI_DIMENSION_MODELS:
                kwargs["dimensions"] = self.dimensions  # type: ignore[assignment]
            response = self._client.embeddings.create(**kwargs)
            results.extend(item.embedding for item in response.data)
            if total > _OPENAI_BATCH:
                logger.info("OpenAI embed progress: %d/%d", min(i + _OPENAI_BATCH, total), total)
        return results

    def embed_query(self, query: str) -> List[float]:
        kwargs = {"input": [query], "model": self._model}
        if self._model in _OPENAI_DIMENSION_MODELS:
            kwargs["dimensions"] = self.dimensions  # type: ignore[assignment]
        response = self._client.embeddings.create(**kwargs)
        return response.data[0].embedding


# ── Voyage AI ────────────────────────────────────────────────────────────────

class VoyageAIEmbedder:
    """Embedder backed by the Voyage AI Embeddings API."""

    batch_size: int = _VOYAGE_BATCH

    def __init__(self, api_key: str, model: str, dimensions: int) -> None:
        import voyageai
        self._client = voyageai.Client(api_key=api_key)
        self._model = model
        self.dimensions = dimensions

    def embed(self, texts: List[str]) -> List[List[float]]:
        results: List[List[float]] = []
        total = len(texts)
        for i in range(0, total, _VOYAGE_BATCH):
            batch = texts[i : i + _VOYAGE_BATCH]
            result = self._client.embed(batch, model=self._model, input_type="document")
            results.extend(result.embeddings)
            if total > _VOYAGE_BATCH:
                logger.info("Voyage embed progress: %d/%d", min(i + _VOYAGE_BATCH, total), total)
        if results:
            self.dimensions = len(results[0])
        return results

    def embed_query(self, query: str) -> List[float]:
        result = self._client.embed([query], model=self._model, input_type="query")
        return result.embeddings[0]


# ── Module-level singleton ────────────────────────────────────────────────────

_embedder: Optional[object] = None


def _build_embedder() -> object:
    from shpoet.config.settings import get_settings
    settings = get_settings()
    provider = settings.embedding_provider.lower()

    if provider == "openai" and settings.openai_api_key:
        logger.info(
            "Using OpenAI embedder: model=%s dims=%d",
            settings.embedding_model,
            settings.embedding_dimensions,
        )
        return OpenAIEmbedder(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    if provider == "voyage" and settings.voyage_api_key:
        logger.info(
            "Using Voyage AI embedder: model=%s dims=%d",
            settings.embedding_model,
            settings.embedding_dimensions,
        )
        return VoyageAIEmbedder(
            api_key=settings.voyage_api_key,
            model=settings.embedding_model,
            dimensions=settings.embedding_dimensions,
        )

    if provider not in ("stub", ""):
        logger.warning(
            "No API key found for embedding provider %r; falling back to stub embeddings",
            provider,
        )
    return StubEmbedder()


def _get_embedder() -> object:
    global _embedder
    if _embedder is None:
        _embedder = _build_embedder()
    return _embedder


def reset_embedder() -> None:
    """Clear the cached embedder (useful after settings changes in tests)."""
    global _embedder
    _embedder = None


# ── Public API (backward-compatible) ─────────────────────────────────────────

def embed_texts(texts: List[str], dimensions: int = 8) -> List[List[float]]:
    """Return embeddings for a list of document texts."""
    return _get_embedder().embed(texts)  # type: ignore[attr-defined]


def embed_query(query: str, dimensions: int = 8) -> List[float]:
    """Return an embedding for a query string."""
    return _get_embedder().embed_query(query)  # type: ignore[attr-defined]


def embed_texts_with_checkpointing(
    ids: List[str],
    texts: List[str],
    dimensions: int,
    persist_dir: Path,
    collection_name: str,
) -> List[List[float]]:
    """Embed texts in batches, checkpointing each batch to disk as it completes.

    If the process is interrupted partway through (network error, killed
    process), rerunning this against the same persist_dir/collection_name
    resumes from the last completed batch instead of re-embedding — and
    re-paying the API cost for — chunks that were already done.
    """
    from shpoet.config.settings import get_settings
    from shpoet.vectorstore.embedding_cache import EmbeddingCache, content_hash

    settings = get_settings()
    embedder = _get_embedder()
    batch_size: int = getattr(embedder, "batch_size", len(texts) or 1)

    cache = EmbeddingCache(
        persist_dir=persist_dir,
        collection_name=collection_name,
        provider=settings.embedding_provider,
        model=settings.embedding_model,
        dimensions=dimensions,
    )

    total = len(ids)
    hashes = [content_hash(text) for text in texts]
    results: List[Optional[List[float]]] = [None] * total

    for start in range(0, total, batch_size):
        end = min(start + batch_size, total)
        batch_ids = ids[start:end]
        batch_texts = texts[start:end]
        batch_hashes = hashes[start:end]

        pending_offsets: List[int] = []
        pending_texts: List[str] = []
        for offset, (chunk_id, chunk_hash) in enumerate(zip(batch_ids, batch_hashes)):
            cached_embedding = cache.get(chunk_id, chunk_hash)
            if cached_embedding is not None:
                results[start + offset] = cached_embedding
            else:
                pending_offsets.append(offset)
                pending_texts.append(batch_texts[offset])

        if pending_texts:
            computed = embedder.embed(pending_texts)  # type: ignore[attr-defined]
            computed_ids = [batch_ids[offset] for offset in pending_offsets]
            computed_hashes = [batch_hashes[offset] for offset in pending_offsets]
            cache.append_batch(computed_ids, computed_hashes, computed)
            for offset, embedding in zip(pending_offsets, computed):
                results[start + offset] = embedding

        logger.info("Embedding checkpoint: %d/%d chunks ready", end, total)

    missing = sum(1 for embedding in results if embedding is None)
    if missing:
        raise RuntimeError(f"Failed to compute embeddings for {missing} of {total} chunks")

    return results  # type: ignore[return-value]
