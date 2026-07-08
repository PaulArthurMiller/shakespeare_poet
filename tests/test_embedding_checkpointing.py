"""Tests for embedding checkpointing: cache persistence and resume-after-interruption."""

from pathlib import Path

import pytest

from shpoet.vectorstore import embeddings as embeddings_module
from shpoet.vectorstore.embedding_cache import EmbeddingCache, content_hash


class _FakeEmbedder:
    """Test double that counts calls and can simulate a crash mid-run."""

    batch_size = 2

    def __init__(self, fail_after_calls: int | None = None) -> None:
        self.fail_after_calls = fail_after_calls
        self.call_count = 0
        self.embedded_texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.call_count += 1
        if self.fail_after_calls is not None and self.call_count > self.fail_after_calls:
            raise ConnectionError("simulated network failure")
        self.embedded_texts.extend(texts)
        return [[float(len(text))] * 3 for text in texts]

    def embed_query(self, query: str) -> list[float]:
        return [float(len(query))] * 3


def test_embedding_cache_round_trip(tmp_path: Path) -> None:
    """A fresh EmbeddingCache instance should reload entries written by a prior one."""

    cache = EmbeddingCache(tmp_path, "coll", provider="stub", model="test-model", dimensions=3)
    cache.append_batch(
        ["a", "b"],
        [content_hash("A text"), content_hash("B text")],
        [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]],
    )

    reloaded = EmbeddingCache(tmp_path, "coll", provider="stub", model="test-model", dimensions=3)
    assert reloaded.get("a", content_hash("A text")) == [1.0, 2.0, 3.0]
    assert reloaded.get("b", content_hash("B text")) == [4.0, 5.0, 6.0]


def test_embedding_cache_invalidated_by_config_change(tmp_path: Path) -> None:
    """Changing model/dimensions must discard the old cache rather than mixing incompatible embeddings."""

    cache = EmbeddingCache(tmp_path, "coll", provider="stub", model="model-a", dimensions=3)
    cache.append_batch(["a"], [content_hash("A text")], [[1.0, 2.0, 3.0]])

    reloaded = EmbeddingCache(tmp_path, "coll", provider="stub", model="model-b", dimensions=3)
    assert reloaded.get("a", content_hash("A text")) is None


def test_embedding_cache_rejects_stale_text(tmp_path: Path) -> None:
    """If a chunk's text changed since it was cached, the stale embedding must not be reused."""

    cache = EmbeddingCache(tmp_path, "coll", provider="stub", model="model-a", dimensions=3)
    cache.append_batch(["a"], [content_hash("original text")], [[1.0, 2.0, 3.0]])

    assert cache.get("a", content_hash("changed text")) is None


def test_checkpointing_resumes_after_interruption(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted embedding run must not re-embed chunks already checkpointed to disk."""

    fake_settings = type(
        "FakeSettings", (), {"embedding_provider": "fake", "embedding_model": "fake-model"}
    )()
    monkeypatch.setattr("shpoet.config.settings.get_settings", lambda: fake_settings)

    ids = ["a", "b", "c", "d", "e"]
    texts = ["alpha", "beta", "gamma", "delta", "epsilon"]

    crashing_embedder = _FakeEmbedder(fail_after_calls=1)
    monkeypatch.setattr(embeddings_module, "_get_embedder", lambda: crashing_embedder)

    with pytest.raises(ConnectionError):
        embeddings_module.embed_texts_with_checkpointing(
            ids=ids,
            texts=texts,
            dimensions=3,
            persist_dir=tmp_path,
            collection_name="coll",
        )

    # Batch 1 (a, b) completed and was checkpointed before the crash on batch 2.
    assert crashing_embedder.embedded_texts == ["alpha", "beta"]

    resumed_embedder = _FakeEmbedder()
    monkeypatch.setattr(embeddings_module, "_get_embedder", lambda: resumed_embedder)

    results = embeddings_module.embed_texts_with_checkpointing(
        ids=ids,
        texts=texts,
        dimensions=3,
        persist_dir=tmp_path,
        collection_name="coll",
    )

    assert len(results) == 5
    # Only the chunks that weren't already cached should have been re-embedded.
    assert resumed_embedder.embedded_texts == ["gamma", "delta", "epsilon"]


def test_checkpointing_ignores_cache_when_source_text_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Editing a chunk's text after a checkpoint should re-embed just that chunk, not the whole run."""

    fake_settings = type(
        "FakeSettings", (), {"embedding_provider": "fake", "embedding_model": "fake-model"}
    )()
    monkeypatch.setattr("shpoet.config.settings.get_settings", lambda: fake_settings)

    first_embedder = _FakeEmbedder()
    monkeypatch.setattr(embeddings_module, "_get_embedder", lambda: first_embedder)
    embeddings_module.embed_texts_with_checkpointing(
        ids=["a", "b"],
        texts=["alpha", "beta"],
        dimensions=3,
        persist_dir=tmp_path,
        collection_name="coll",
    )

    second_embedder = _FakeEmbedder()
    monkeypatch.setattr(embeddings_module, "_get_embedder", lambda: second_embedder)
    embeddings_module.embed_texts_with_checkpointing(
        ids=["a", "b"],
        texts=["alpha-revised", "beta"],
        dimensions=3,
        persist_dir=tmp_path,
        collection_name="coll",
    )

    assert second_embedder.embedded_texts == ["alpha-revised"]
